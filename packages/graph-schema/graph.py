from neo4j import GraphDatabase
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password_secure")

class TemporalGraphStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def write_memory(self, memory_dict: Dict[str, Any]) -> str:
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

    def correct_memory(self, old_memory_id: str, new_memory_dict: Dict[str, Any]) -> str:
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

    def traverse_related(self, subject_id: str, intent_entities: List[str]) -> List[Dict[str, Any]]:
        """Retrieve active memories linked to user and matching entities."""
        query = """
        MATCH (u:User {id: $subject_id})-[:HAS_MEMORY]->(m:Memory)-[:ABOUT]->(e:Entity)
        WHERE m.status = 'active' AND e.name IN $intent_entities
        RETURN m.memory_id AS memory_id, m.fact_text AS fact_text, m.memory_type AS memory_type, m.confidence AS confidence
        """
        with self.driver.session() as session:
            result = session.run(query, subject_id=subject_id, intent_entities=intent_entities)
            return [record.data() for record in result]
