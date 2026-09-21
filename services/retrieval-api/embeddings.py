"""
Embedding generation. Production path uses SentenceTransformers (§6.2). The
pilot ships a lightweight, deterministic hashing-based local embedder so the
service runs without downloading model weights (no network in constrained
environments) — swap `LocalHashEmbedder` for `SentenceTransformerEmbedder`
by setting EMBEDDING_BACKEND=sentence_transformers.

Both implement the same `embed(text: str) -> List[float]` interface, and
vectors are always stored under the same `memory_id` used in the graph
(§5.4 "Embeddings and Retrieval").
"""
import hashlib
import math
import os
import re

VECTOR_DIM = 64


class LocalHashEmbedder:
    """Deterministic bag-of-words hashing embedding — good enough for pilot
    demonstration of the retrieval *pipeline*, not a production-quality model."""

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * VECTOR_DIM
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for tok in tokens:
            # md5 here is a fast, stable bucket hash for a bag-of-words vector,
            # never a security primitive.
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)  # noqa: S324
            idx = h % VECTOR_DIM
            sign = 1.0 if (h // VECTOR_DIM) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def get_embedder():
    backend = os.getenv("EMBEDDING_BACKEND", "local_hash")
    if backend == "sentence_transformers":
        try:
            from sentence_transformers import SentenceTransformer

            class SentenceTransformerEmbedder:
                def __init__(self):
                    self.model = SentenceTransformer("all-MiniLM-L6-v2")

                def embed(self, text: str) -> list[float]:
                    return self.model.encode(text).tolist()

            return SentenceTransformerEmbedder()
        except Exception:
            pass
    return LocalHashEmbedder()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
