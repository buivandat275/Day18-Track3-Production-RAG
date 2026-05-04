"""Production RAG Pipeline: M1 + M2 + M3 + M4 + M5."""

import os
import re
import sys
import time
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OPENAI_API_KEY, RERANK_TOP_K
from src.m1_chunking import chunk_hierarchical, load_documents
from src.m2_search import HybridSearch
from src.m3_rerank import CrossEncoderReranker
from src.m4_eval import evaluate_ragas, failure_analysis, load_test_set, save_report
from src.m5_enrichment import enrich_chunks

_OPENAI_GENERATION_FAILED = False


def build_pipeline():
    """Build the production RAG pipeline."""
    print("=" * 60)
    print("PRODUCTION RAG PIPELINE")
    print("=" * 60)

    print("\n[1/4] Chunking documents...")
    docs = load_documents()
    all_chunks = []
    for doc in docs:
        parents, children = chunk_hierarchical(doc["text"], metadata=doc["metadata"])
        source_chunks = children or parents
        for chunk in source_chunks:
            all_chunks.append(
                {
                    "text": chunk.text,
                    "metadata": {**chunk.metadata, "parent_id": chunk.parent_id},
                }
            )
    print(f"  {len(all_chunks)} chunks from {len(docs)} documents")

    if not all_chunks:
        raise RuntimeError("No chunks available. Add .md/.txt data or extractable PDFs under data/.")

    print("\n[2/4] Enriching chunks (M5)...")
    enriched = enrich_chunks(all_chunks, methods=["contextual", "hyqa", "metadata"])
    if enriched:
        all_chunks = [{"text": e.enriched_text, "metadata": e.auto_metadata} for e in enriched]
        print(f"  Enriched {len(enriched)} chunks")
    else:
        print("  M5 returned no enriched chunks, using raw chunks")

    print("\n[3/4] Indexing (BM25 + Dense when available)...")
    search = HybridSearch()
    search.index(all_chunks)

    print("\n[4/4] Preparing reranker...")
    reranker = CrossEncoderReranker()

    return search, reranker


def run_query(query: str, search: HybridSearch, reranker: CrossEncoderReranker) -> tuple[str, list[str]]:
    """Run a single query through search, reranking, and answer generation."""
    try:
        results = search.search(query)
    except Exception as exc:
        print(f"Search failed for query '{query}', returning empty context: {exc}")
        results = []

    docs = [{"text": r.text, "score": r.score, "metadata": r.metadata} for r in results]
    try:
        reranked = reranker.rerank(query, docs, top_k=RERANK_TOP_K)
    except Exception as exc:
        print(f"Rerank failed for query '{query}', using search order: {exc}")
        reranked = []

    contexts = [r.text for r in reranked] if reranked else [r.text for r in results[:RERANK_TOP_K]]
    answer = _generate_answer(query, contexts)
    return answer, contexts


def evaluate_pipeline(search: HybridSearch, reranker: CrossEncoderReranker):
    """Run evaluation on the configured test set."""
    print("\n[Eval] Running queries...")
    test_set = load_test_set()
    questions, answers, all_contexts, ground_truths = [], [], [], []

    for i, item in enumerate(test_set):
        answer, contexts = run_query(item["question"], search, reranker)
        questions.append(item["question"])
        answers.append(answer)
        all_contexts.append(contexts)
        ground_truths.append(item["ground_truth"])
        print(f"  [{i + 1}/{len(test_set)}] {item['question'][:70]}...")

    print("\n[Eval] Running evaluation...")
    results = evaluate_ragas(questions, answers, all_contexts, ground_truths)

    print("\n" + "=" * 60)
    print("PRODUCTION RAG SCORES")
    print("=" * 60)
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        score = results.get(metric, 0)
        print(f"  {'✓' if score >= 0.75 else '✗'} {metric}: {score:.4f}")
    print(f"  mode: {results.get('evaluation_mode', 'unknown')}")

    failures = failure_analysis(results.get("per_question", []))
    save_report(results, failures)
    return results


def _has_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        return False
    return key.lower() not in {"sk-...", "...", "your-api-key"} and not key.endswith("...")


def _generate_answer(query: str, contexts: list[str]) -> str:
    global _OPENAI_GENERATION_FAILED

    if not contexts:
        return "Không tìm thấy thông tin trong tài liệu."

    if _has_openai_key() and not _OPENAI_GENERATION_FAILED:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY, timeout=15.0)
            context_text = "\n\n".join(contexts[:RERANK_TOP_K])
            response = client.chat.completions.create(
                model=os.getenv("ANSWER_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Trả lời bằng tiếng Việt có dấu, ngắn gọn, chỉ dựa trên context. "
                            "Nếu context không đủ thông tin, nói rõ là không tìm thấy."
                        ),
                    },
                    {"role": "user", "content": f"Context:\n{context_text}\n\nCâu hỏi: {query}"},
                ],
                temperature=0,
                max_tokens=220,
            )
            content = response.choices[0].message.content
            if content:
                return content.strip()
        except Exception as exc:
            _OPENAI_GENERATION_FAILED = True
            print(f"OpenAI generation unavailable, using extractive fallback: {exc}")

    return _extractive_answer(query, contexts)


def _extractive_answer(query: str, contexts: list[str]) -> str:
    sentences = []
    for context in contexts:
        sentences.extend([s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", context) if s.strip()])
    if not sentences:
        return contexts[0]

    query_tokens = _tokens(query)
    best_sentence = max(sentences, key=lambda sentence: len(query_tokens & _tokens(sentence)))
    return best_sentence


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


if __name__ == "__main__":
    start = time.time()
    pipeline_search, pipeline_reranker = build_pipeline()
    evaluate_pipeline(pipeline_search, pipeline_reranker)
    print(f"\nTotal: {time.time() - start:.1f}s")
