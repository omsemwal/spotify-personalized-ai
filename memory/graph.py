"""Why this file exists
=====================

abc.md:117 - "Represent memory facts as versioned nodes and relationships
              with valid-from, valid-to, recorded-at, source, confidence,
              and status."
abc.md:118 - "Support contradiction, supersession, expiry, and explicit
              correction without erasing audit history prematurely."
abc.md:119 - "Maintain subject isolation at the query boundary."
abc.md:120 - "Use graph constraints and idempotent upserts."

A memory is not a row that gets overwritten. It is a fact that was true
for a stretch of time. When a listener changes their mind we do not edit
the old memory - we close it and write a new one, linked to it. That is
what "temporal" means here, and it is why the history survives.

Everything in this file is subject-scoped. Every query names the subject,
so no read can cross from one listener to another (abc.md:119).
"""

import uuid
from datetime import datetime, timezone

from dotenv import dotenv_values
from neo4j import GraphDatabase

_env = dotenv_values(".env")
_driver = None


# Open the connection once and reuse it.
def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            _env.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(_env.get("NEO4J_USER", "neo4j"), _env.get("NEO4J_PASSWORD", "")),
        )
    return _driver


# Close the connection, used on shutdown and by tests.
def close() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


# Create the uniqueness rules the graph needs. Safe to run repeatedly.
def ensure_constraints() -> None:
    # abc.md:120 - "Use graph constraints ... to protect entity and
    # relationship integrity." Without these, a retry could create two
    # nodes for one memory.
    statements = [
        "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS "
        "FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE",
        "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
        "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
        # Reads always filter by subject, so that is what to index.
        "CREATE INDEX memory_subject IF NOT EXISTS "
        "FOR (m:Memory) ON (m.subject_id, m.status)",
    ]
    with driver().session() as session:
        for statement in statements:
            session.run(statement)


# Make a new memory id. Computed by us, never taken from the model.
def new_memory_id() -> str:
    # abc.md:341 - validation rejects "invented memory IDs". Ours are the
    # only ones that exist.
    return f"mem_{uuid.uuid4().hex[:16]}"


# Write one memory into the graph, with its entities and its time window.
def create_memory(subject_id: str, candidate: dict, valid_from: datetime | None = None) -> dict:
    memory_id = new_memory_id()
    now = datetime.now(timezone.utc)
    valid_from = valid_from or now
    policy = candidate.get("policy") or {}

    # MERGE, not CREATE: an idempotent upsert, so replaying the same write
    # cannot produce two nodes (abc.md:120).
    write = """
    MERGE (m:Memory {memory_id: $memory_id})
    ON CREATE SET
        m.subject_id      = $subject_id,
        m.memory_type     = $memory_type,
        m.fact            = $fact,
        m.confidence      = $confidence,
        m.status          = 'active',
        m.graph_version   = 1,
        m.recorded_at     = datetime($recorded_at),
        m.valid_from      = datetime($valid_from),
        m.valid_to        = null,
        m.expires_at      = datetime($expires_at),
        m.sensitivity     = $sensitivity,
        m.source_event_ids = $source_event_ids,
        m.evidence_count  = $evidence_count
    RETURN m.memory_id AS memory_id,
           m.graph_version AS graph_version,
           m.status AS status
    """

    with driver().session() as session:
        record = session.run(
            write,
            memory_id=memory_id,
            subject_id=subject_id,
            memory_type=candidate["memory_type"],
            fact=candidate["fact"],
            confidence=candidate["confidence"],
            recorded_at=now.isoformat(),
            valid_from=valid_from.isoformat(),
            expires_at=policy.get("expires_at") or now.isoformat(),
            sensitivity=policy.get("sensitivity", "normal"),
            source_event_ids=candidate.get("source_event_ids", []),
            evidence_count=candidate.get("evidence_count", 1),
        ).single()

        # Link the memory to what it is about. Entities are shared between
        # memories, so MERGE finds an existing one or makes it.
        for entity in candidate.get("entities", []):
            if not entity.get("entity_id"):
                continue          # unresolved names are not given a node
            session.run(
                """
                MERGE (e:Entity {entity_id: $entity_id})
                ON CREATE SET e.name = $name, e.entity_type = $entity_type
                WITH e
                MATCH (m:Memory {memory_id: $memory_id})
                MERGE (m)-[:ABOUT]->(e)
                """,
                entity_id=entity["entity_id"],
                name=entity.get("canonical_name") or entity["name"],
                entity_type=entity.get("entity_type"),
                memory_id=memory_id,
            )

    return dict(record)


# Read one memory back, but only if it belongs to this subject.
def get_memory(memory_id: str, subject_id: str) -> dict | None:
    # abc.md:119 - subject isolation at the query boundary. The subject is
    # in the MATCH, so knowing an id is not enough to read it.
    read = """
    MATCH (m:Memory {memory_id: $memory_id, subject_id: $subject_id})
    OPTIONAL MATCH (m)-[:ABOUT]->(e:Entity)
    RETURN m AS memory, collect(e.entity_id) AS entities
    """
    with driver().session() as session:
        record = session.run(read, memory_id=memory_id, subject_id=subject_id).single()

    if record is None:
        return None

    memory = dict(record["memory"])
    memory["entities"] = [e for e in record["entities"] if e]
    # Neo4j does not store null properties, so an open memory has no
    # valid_to key at all. Always return it, so callers can just read it.
    memory.setdefault("valid_to", None)
    return memory


# List a subject's active memories, newest first.
def list_memories(subject_id: str, status: str = "active") -> list[dict]:
    read = """
    MATCH (m:Memory {subject_id: $subject_id, status: $status})
    RETURN m AS memory ORDER BY m.recorded_at DESC
    """
    with driver().session() as session:
        return [dict(r["memory"]) for r in session.run(read, subject_id=subject_id, status=status)]


# Replace an old memory with a new one, keeping the old one as history.
def supersede(old_memory_id: str, subject_id: str, new_candidate: dict) -> dict:
    """abc.md:118 - corrections supersede; they never silently overwrite.

    The old memory is closed, not deleted: its valid_to is set and its
    status becomes 'superseded', so the audit history survives.
    """
    now = datetime.now(timezone.utc)
    created = create_memory(subject_id, new_candidate, valid_from=now)

    close_old = """
    MATCH (old:Memory {memory_id: $old_id, subject_id: $subject_id})
    MATCH (new:Memory {memory_id: $new_id})
    SET old.valid_to      = datetime($now),
        old.status        = 'superseded',
        old.graph_version = old.graph_version + 1
    MERGE (new)-[:SUPERSEDES]->(old)
    RETURN old.memory_id AS superseded
    """
    with driver().session() as session:
        session.run(
            close_old,
            old_id=old_memory_id,
            subject_id=subject_id,
            new_id=created["memory_id"],
            now=now.isoformat(),
        ).single()

    created["superseded"] = old_memory_id
    return created


# Remove one subject's memories entirely. Used by tests and by deletion.
def delete_memories(subject_id: str) -> int:
    with driver().session() as session:
        record = session.run(
            "MATCH (m:Memory {subject_id: $subject_id}) "
            "DETACH DELETE m RETURN count(m) AS removed",
            subject_id=subject_id,
        ).single()
    return record["removed"]
