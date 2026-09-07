# 📊 Data Directory Guide & Tasks

**Folder**: `data/`  
**Purpose**: Holds test datasets, synthetic evaluation scenarios, and raw schema contracts.

---

## 📁 Subdirectory Breakdown & What We Do Inside

### 1. `data/synthetic/`
- **What we do**: Synthetic interaction event datasets simulating user music chat logs, playlist actions, and artist preferences.
- **Used for**: Local development seeding, load testing, and offline pipeline execution.

### 2. `data/golden-sets/`
- **What we do**: Benchmark "Golden Sets" containing ground-truth query-memory pairs.
- **Used for**: Evaluating memory retrieval accuracy (Precision@K, Recall@K) in `packages/evaluation/`.

### 3. `data/schemas/`
- **What we do**: JSON and Avro schema files defining raw event structures and database payload formats.
