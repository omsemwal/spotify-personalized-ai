// Mirrors packages/graph-schema/constraints.py — kept here too as the
// canonical migration artifact with a version number, per §5.5 Maintainability
// "Migrations require compatibility checks and rollback plans."
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE;
CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE;
CREATE INDEX memory_status_idx IF NOT EXISTS FOR (m:Memory) ON (m.status);
CREATE INDEX memory_valid_to_idx IF NOT EXISTS FOR (m:Memory) ON (m.valid_to);

// Rollback (manual — Neo4j constraint drops are safe/idempotent):
// DROP CONSTRAINT memory_id_unique IF EXISTS;
// DROP CONSTRAINT user_id_unique IF EXISTS;
// DROP CONSTRAINT entity_name_unique IF EXISTS;
// DROP INDEX memory_status_idx IF EXISTS;
// DROP INDEX memory_valid_to_idx IF EXISTS;
