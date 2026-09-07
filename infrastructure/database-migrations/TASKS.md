# 🗄️ Database Migrations Guide & Tasks

**Folder**: `infrastructure/database-migrations/`  
**Purpose**: Version-controlled migration scripts for Postgres relational tables, Neo4j graph constraints, and Qdrant vector collections.

---

## 📋 What We Do Inside
1. **Postgres Migrations (`/postgres`)**:
   - Alembic / Flyway SQL scripts creating tables for `deletion_jobs`, user profiles, audit logs, and consent policies.
2. **Neo4j Graph Constraints (`/neo4j`)**:
   - Cypher setup scripts defining uniqueness constraints (`m.memory_id IS UNIQUE`) and indexes on `subject_id`.
3. **Qdrant Vector Schema (`/qdrant`)**:
   - Initialization scripts configuring vector collection dimensions, distance metrics (Cosine), and payload index fields.
