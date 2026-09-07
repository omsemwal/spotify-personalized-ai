# 🎯 Evaluation Framework Package

**Folder**: `packages/evaluation/`  
**Purpose**: Automated benchmarking package to measure retrieval quality, relevance, context efficiency, and memory accuracy.

---

## 📋 What We Do Inside
1. **Retrieval Benchmark Evaluator**:
   - Computes **Precision@K**, **Recall@K**, and **MRR (Mean Reciprocal Rank)** against ground-truth golden sets (`data/golden-sets/`).
2. **Context Relevance Evaluator**:
   - Evaluates whether retrieved memories contained unnecessary noise or succeeded under tight token budgets.
3. **Fact Consistency Checker**:
   - Verifies if superseded or expired memories are properly excluded from evaluation benchmarks.
