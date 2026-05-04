"""Module 3: Reranking - cross-encoder with lexical fallback."""

import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from statistics import mean

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RERANK_TOP_K


@dataclass
class RerankResult:
    text: str
    original_score: float
    rerank_score: float
    metadata: dict
    rank: int


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name)
            except Exception as exc:
                print(f"Reranker model unavailable, using lexical fallback: {exc}")
                self._model = False
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        """Rerank documents from top-N to top-k."""
        if not documents:
            return []

        model = self._load_model()
        if model:
            try:
                pairs = [[query, doc["text"]] for doc in documents]
                scores = model.predict(pairs, show_progress_bar=False)
                if hasattr(scores, "tolist"):
                    scores = scores.tolist()
            except Exception as exc:
                print(f"Reranker inference failed, using lexical fallback: {exc}")
                scores = [_lexical_score(query, doc["text"]) for doc in documents]
        else:
            scores = [_lexical_score(query, doc["text"]) for doc in documents]

        combined = list(zip(scores, documents))
        combined.sort(key=lambda item: item[0], reverse=True)
        combined = combined[: min(top_k, len(combined))]

        return [
            RerankResult(
                text=doc["text"],
                original_score=float(doc.get("score", 0.0)),
                rerank_score=float(rerank_score),
                metadata=dict(doc.get("metadata") or {}),
                rank=rank,
            )
            for rank, (rerank_score, doc) in enumerate(combined, start=1)
        ]


class FlashrankReranker:
    """Lightweight optional alternative. Requires ``pip install flashrank``."""

    def __init__(self):
        self._model = None

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        if not documents:
            return []
        try:
            from flashrank import Ranker, RerankRequest
        except ImportError:
            return []

        if self._model is None:
            self._model = Ranker()

        passages = [{"id": i, "text": d["text"]} for i, d in enumerate(documents)]
        ranked = self._model.rerank(RerankRequest(query=query, passages=passages))
        ranked = ranked[: min(top_k, len(ranked))]

        out: list[RerankResult] = []
        for rank, item in enumerate(ranked, start=1):
            idx = int(item["id"])
            doc = documents[idx]
            out.append(
                RerankResult(
                    text=doc["text"],
                    original_score=float(doc.get("score", 0.0)),
                    rerank_score=float(item["score"]),
                    metadata=dict(doc.get("metadata") or {}),
                    rank=rank,
                )
            )
        return out


def benchmark_reranker(reranker, query: str, documents: list[dict], n_runs: int = 5) -> dict:
    """Benchmark reranking latency over n_runs."""
    times_ms: list[float] = []
    for _ in range(max(1, n_runs)):
        start = time.perf_counter()
        reranker.rerank(query, documents)
        times_ms.append((time.perf_counter() - start) * 1000.0)
    return {
        "avg_ms": mean(times_ms),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
    }


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _tokens(text: str) -> set[str]:
    normalized = _strip_accents((text or "").lower())
    stopwords = {"la", "va", "cua", "cho", "duoc", "bao", "nhieu", "gi", "khi", "trong"}
    return {
        token
        for token in re.findall(r"\w+", normalized, flags=re.UNICODE)
        if len(token) > 1 and token not in stopwords
    }


def _lexical_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens) / len(query_tokens)
    number_bonus = 0.1 * len(set(re.findall(r"\d+", query)) & set(re.findall(r"\d+", text)))
    return overlap + number_bonus


if __name__ == "__main__":
    query = "Nhân viên được nghỉ phép bao nhiêu ngày?"
    docs = [
        {"text": "Nhân viên được nghỉ 12 ngày/năm.", "score": 0.8, "metadata": {}},
        {"text": "Mật khẩu thay đổi mỗi 90 ngày.", "score": 0.7, "metadata": {}},
        {"text": "Thời gian thử việc là 60 ngày.", "score": 0.75, "metadata": {}},
    ]
    reranker = CrossEncoderReranker()
    for r in reranker.rerank(query, docs):
        print(f"[{r.rank}] {r.rerank_score:.4f} | {r.text}")
