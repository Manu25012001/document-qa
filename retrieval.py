"""NumPy cosine similarity ranking for in-memory document chunks."""
import numpy as np


def cosine_similarity(left, right) -> float:
    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    if a.size == 0 or a.size != b.size:
        return 0.0
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0 or not np.isfinite(denominator):
        return 0.0
    score = float(np.dot(a, b) / denominator)
    return score if np.isfinite(score) else 0.0


def retrieve(chunks: list[dict], question_embedding, top_k: int = 3) -> list[dict]:
    if not chunks or top_k <= 0:
        return []
    ranked = []
    for chunk in chunks:
        score = cosine_similarity(question_embedding, chunk.get("embedding", []))
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [{**chunk, "similarity": score} for score, chunk in ranked[:top_k]]
