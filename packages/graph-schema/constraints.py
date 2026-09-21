"""
Neo4j schema constraints and indexes.
Spec ref: §5.4 "Use graph constraints and idempotent upserts to protect entity
and relationship integrity" and §7.8 step 3 "Apply graph constraints... with
rollback artifacts."

Run once per environment via `python constraints.py` (or as a migration step,
see infrastructure/database-migrations/).
"""
from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password_secure")

# Uniqueness constraints double as indexes in Neo4j and make MERGE idempotent.
CONSTRAINTS = [
    "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE",
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
    # Subject-partition index: every retrieval query filters by subject_id first,
    # so this index is what keeps cross-subject queries fast AND enforceable.
    "CREATE INDEX memory_status_idx IF NOT EXISTS FOR (m:Memory) ON (m.status)",
    "CREATE INDEX memory_valid_to_idx IF NOT EXISTS FOR (m:Memory) ON (m.valid_to)",
]


def apply_constraints():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
    driver.close()
    print(f"Applied {len(CONSTRAINTS)} constraints/indexes.")


if __name__ == "__main__":
    apply_constraints()
