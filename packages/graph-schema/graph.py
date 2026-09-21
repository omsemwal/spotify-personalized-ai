import os
from datetime import datetime
from typing import Any

from neo4j import GraphDatabase

DEFAULT_URI = "bolt://localhost:7687"


def connection_settings() -> tuple[str, str, str]:
    """Read connection settings from the environment, at call time.

    These used to be module-level constants, which froze the configuration at
    import. That is wrong in two ways: a process could not be pointed at a
    different database after the module was first imported, and it made the
    behaviour depend on *when* the import happened rather than on the
    environment — which is exactly the kind of implicit state this unit is
    removing.
    """
    return (
        os.getenv("NEO4J_URI", DEFAULT_URI),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "neo4j_password_secure"),
    )


class TemporalGraphStore:
    def __init__(self):
        uri, user, password = connection_settings()
        self.uri = uri
        # Bounded timeouts. The driver's defaults retry for ~30 seconds, which
        # turns "Neo4j is down" into a request that appears to hang. Failing in
        # a few seconds is what lets the health check and the 250 ms retrieval
        # budget (§5.5 Performance) stay meaningful.
        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "5")),
            max_transaction_retry_time=float(os.getenv("NEO4J_MAX_RETRY_TIME", "5")),
        )

    def close(self):
        self.driver.close()

    def verify_connectivity(self) -> None:
        """Prove the database is actually reachable.

        The Neo4j driver connects lazily, so constructing GraphDatabase.driver()
        succeeds even when nothing is listening. Without this check a service
        would start "successfully" and fail on its first real query instead.
        Raises the driver's own exception, which carries the useful detail.
        """
        self.driver.verify_connectivity()

    def write_memory(self, memory_dict: dict[str, Any]) -> str:
        """Upsert memory node and link to User and Entity nodes in Neo4j."""
        query = """
        MERGE (u:User {id: $subject_id})
        MERGE (m:Memory {memory_id: $memory_id})
        SET m.fact_text = $fact_text,
            m.memory_type = $memory_type,
            m.confidence = $confidence,
            m.policy_class = $policy_class,
            m.source_event_id = $source_event_id,
            m.valid_from = $valid_from,
            m.status = $status,
            m.recorded_at = $recorded_at
        MERGE (u)-[:HAS_MEMORY]->(m)
        WITH m
        UNWIND $entities AS entity_name
        MERGE (e:Entity {name: entity_name})
        MERGE (m)-[:ABOUT]->(e)
        RETURN m.memory_id AS memory_id
        """
        with self.driver.session() as session:
            result = session.run(
                query,
                subject_id=memory_dict["subject_id"],
                memory_id=memory_dict["memory_id"],
                fact_text=memory_dict["fact_text"],
                memory_type=memory_dict["memory_type"],
                confidence=memory_dict["confidence"],
                policy_class=memory_dict["policy_class"],
                source_event_id=memory_dict["source_event_id"],
                valid_from=str(memory_dict.get("valid_from", datetime.utcnow().isoformat())),
                status=memory_dict.get("status", "active"),
                recorded_at=str(memory_dict.get("recorded_at", datetime.utcnow().isoformat())),
                entities=memory_dict.get("entities", [])
            )
            record = result.single()
            return record["memory_id"] if record else memory_dict["memory_id"]

    def correct_memory(self, old_memory_id: str, new_memory_dict: dict[str, Any]) -> str:
        """Close valid_to on old memory and link new memory with SUPERSEDES relationship."""
        # 1. Write the new memory first
        new_memory_id = self.write_memory(new_memory_dict)

        # 2. Update old memory status and create SUPERSEDES relationship
        query = """
        MATCH (old:Memory {memory_id: $old_memory_id})
        MATCH (new:Memory {memory_id: $new_memory_id})
        SET old.valid_to = $now,
            old.status = 'superseded'
        MERGE (new)-[:SUPERSEDES]->(old)
        RETURN new.memory_id AS memory_id
        """
        with self.driver.session() as session:
            session.run(
                query,
                old_memory_id=old_memory_id,
                new_memory_id=new_memory_id,
                now=datetime.utcnow().isoformat()
            )
        return new_memory_id

    def set_embedding(self, memory_id: str, vector: list[float]) -> None:
        """Store the vector on the same node as the fact, under the same
        memory_id (§5.4 "store vectors under the same stable memory identifier
        used in the graph"). Deleting the node deletes the vector with it, so
        graph and vector state cannot drift apart."""
        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        CALL db.create.setNodeVectorProperty(m, 'embedding', $vector)
        """
        with self.driver.session() as session:
            session.run(query, memory_id=memory_id, vector=vector)

    def vector_search(self, subject_id: str, query_vector: list[float], top_k: int = 20):
        """Semantic candidates from the Neo4j vector index (§6.2 "Neo4j vector
        indexes"), filtered to one subject so the index can never return another
        subject's memories."""
        query = """
        CALL db.index.vector.queryNodes('memory_embedding_idx', $top_k, $vector)
        YIELD node AS m, score
        MATCH (u:User {id: $subject_id})-[:HAS_MEMORY]->(m)
        RETURN m.memory_id AS memory_id, score
        """
        with self.driver.session() as session:
            result = session.run(query, top_k=top_k, vector=query_vector, subject_id=subject_id)
            return [(r["memory_id"], r["score"]) for r in result]

    def expire_memory(self, memory_id: str) -> None:
        """Close valid-time and mark expired. History is preserved — the node
        stays in the graph with status='expired' (§5.4: expiry is not erasure)."""
        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        SET m.valid_to = $now, m.status = 'expired'
        """
        with self.driver.session() as session:
            session.run(query, memory_id=memory_id, now=datetime.utcnow().isoformat())

    def delete_memory(self, memory_id: str) -> None:
        """Hard delete for cross-store erasure (deletion-orchestrator). Unlike
        expire, this is irreversible and removes the node and its relationships
        (§5.4 privacy rules / §6.4 deletion propagation)."""
        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        DETACH DELETE m
        """
        with self.driver.session() as session:
            session.run(query, memory_id=memory_id)

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Single memory lookup by stable ID, used by correction/expiry paths."""
        query = """
        MATCH (u:User)-[:HAS_MEMORY]->(m:Memory {memory_id: $memory_id})
        OPTIONAL MATCH (m)-[:ABOUT]->(e:Entity)
        RETURN m.memory_id AS memory_id, u.id AS subject_id, m.fact_text AS fact_text,
               m.memory_type AS memory_type, m.confidence AS confidence,
               m.policy_class AS policy_class, m.source_event_id AS source_event_id,
               m.valid_from AS valid_from, m.valid_to AS valid_to, m.status AS status,
               m.recorded_at AS recorded_at, collect(e.name) AS entities
        """
        with self.driver.session() as session:
            record = session.run(query, memory_id=memory_id).single()
            return record.data() if record else None

    def get_all_for_subject(self, subject_id: str) -> list[dict[str, Any]]:
        """Every memory belonging to one subject, scoped by subject_id so a
        query can never traverse into another subject's memories (§5.4 subject
        isolation at the query boundary)."""
        query = """
        MATCH (u:User {id: $subject_id})-[:HAS_MEMORY]->(m:Memory)
        OPTIONAL MATCH (m)-[:ABOUT]->(e:Entity)
        RETURN m.memory_id AS memory_id, u.id AS subject_id, m.fact_text AS fact_text,
               m.memory_type AS memory_type, m.confidence AS confidence,
               m.policy_class AS policy_class, m.source_event_id AS source_event_id,
               m.valid_from AS valid_from, m.valid_to AS valid_to, m.status AS status,
               m.recorded_at AS recorded_at, collect(e.name) AS entities
        """
        with self.driver.session() as session:
            result = session.run(query, subject_id=subject_id)
            return [record.data() for record in result]

    def traverse_related(self, subject_id: str, intent_entities: list[str]) -> list[dict[str, Any]]:
        """Retrieve active memories linked to user and matching entities."""
        query = """
        MATCH (u:User {id: $subject_id})-[:HAS_MEMORY]->(m:Memory)-[:ABOUT]->(e:Entity)
        WHERE m.status = 'active' AND e.name IN $intent_entities
        RETURN m.memory_id AS memory_id, m.fact_text AS fact_text, m.memory_type AS memory_type, m.confidence AS confidence
        """
        with self.driver.session() as session:
            result = session.run(query, subject_id=subject_id, intent_entities=intent_entities)
            return [record.data() for record in result]
