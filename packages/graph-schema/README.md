# packages/graph-schema

**What this is:** The temporal graph memory layer — Neo4j node/relationship
constraints and the read/write access pattern for versioned memory facts.
Spec ref: §5.4 "Temporal Graph Memory Layer", §6.1 step 3, §6.2 (Neo4j).

## Files
- `graph.py` — `TemporalGraphStore`: production Neo4j implementation. Writes are
  idempotent `MERGE`s. `correct_memory()` implements supersession: it closes the
  old fact's `valid_to`, sets `status='superseded'`, and links `(new)-[:SUPERSEDES]->(old)` —
  **it never deletes or silently overwrites history**, per the Graph Platform Lead's
  requirement in §4.
- `constraints.py` — uniqueness constraints (`Memory.memory_id`, `User.id`,
  `Entity.name`) and indexes (`status`, `valid_to`). Run once per environment;
  see `infrastructure/database-migrations/`.
- `memory_store.py` — `InMemoryGraphStore`, an interface-identical test double
  used by `tests/unit/` and local development so this logic is verifiable
  without a live Neo4j instance.

## Graph shape
```
(User {id}) -[:HAS_MEMORY]-> (Memory {memory_id, fact_text, memory_type,
    confidence, policy_class, valid_from, valid_to, recorded_at, status})
(Memory) -[:ABOUT]-> (Entity {name})
(Memory) -[:SUPERSEDES]-> (Memory)   # correction chain, never deleted
```

## Subject isolation
Every read method takes `subject_id` as a required first-class filter. There is
no method that returns memories without a subject scope — this is the
enforcement point for §5.4's "prevent traversal across unauthorized identity
scopes."

## Run constraints
```bash
python constraints.py   # requires NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars
```
