"""Basic RAG baseline: paragraph chunking + dense search when available."""

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NAIVE_COLLECTION
from src.m1_chunking import chunk_basic, load_documents
from src.m2_search import BM25Search, DenseSearch
from src.m4_eval import evaluate_ragas, load_test_set, save_report


def main():
    print("=" * 60)
    print("BASIC RAG BASELINE")
    print("(paragraph chunking + dense search when available)")
    print("=" * 60)

    docs = load_documents()
    chunks = []
    for doc in docs:
        for chunk in chunk_basic(doc["text"], metadata=doc["metadata"]):
            chunks.append({"text": chunk.text, "metadata": chunk.metadata})
    print(f"  {len(chunks)} basic paragraph chunks")

    search = _build_baseline_search(chunks)

    test_set = load_test_set()
    questions, answers, all_contexts, ground_truths = [], [], [], []
    for item in test_set:
        results = search.search(item["question"], top_k=3)
        contexts = [r.text for r in results]
        answers.append(contexts[0] if contexts else "Không tìm thấy thông tin.")
        questions.append(item["question"])
        all_contexts.append(contexts)
        ground_truths.append(item["ground_truth"])

    results = evaluate_ragas(questions, answers, all_contexts, ground_truths)
    print("\nBASIC BASELINE SCORES")
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        print(f"  {metric}: {results.get(metric, 0):.4f}")
    print(f"  mode: {results.get('evaluation_mode', 'unknown')}")
    save_report(results, [], path="naive_baseline_report.json")
    print("\nDone. Now run: python main.py")


def _build_baseline_search(chunks: list[dict]):
    try:
        search = DenseSearch()
        search.index(chunks, collection=NAIVE_COLLECTION)

        class DenseAdapter:
            def search(self, query: str, top_k: int = 3):
                return search.search(query, top_k=top_k, collection=NAIVE_COLLECTION)

        return DenseAdapter()
    except Exception as exc:
        print(f"Dense baseline unavailable, using BM25 baseline: {exc}")
        bm25 = BM25Search()
        bm25.index(chunks)
        return bm25


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Total: {time.time() - start:.1f}s")
