"""Lab 24 Phase A: RAGAS Evaluation - 50+ questions, 4 metrics, failure analysis + clustering."""

import json
import math
import os
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from statistics import mean, stdev

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set_expanded(path: str = "test_set_expanded.json") -> list[dict]:
    """Load expanded 50+ test set."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _has_openai_key() -> bool:
    if os.getenv("RAGAS_USE_OPENAI", "").strip() != "1":
        return False
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return False
    return key.lower() not in {"sk-...", "...", "your-api-key"} and not key.endswith("...")


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _tokens(text: str) -> set[str]:
    normalized = _strip_accents((text or "").lower())
    stopwords = {
        "la", "va", "cua", "cho", "khi", "duoc", "trong", "nhu", "the",
        "nao", "bao", "nhieu", "gi", "de", "voi", "mot", "cac", "can",
    }
    return {
        token
        for token in __import__("re").findall(r"\w+", normalized, flags=__import__("re").UNICODE)
        if len(token) > 1 and token not in stopwords
    }


def _overlap_score(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _clamp(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _heuristic_eval(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict:
    """Fallback heuristic evaluation when OpenAI not available."""
    per_question: list[EvalResult] = []

    for question, answer, ctxs, ground_truth in zip(questions, answers, contexts, ground_truths):
        context_text = "\n".join(ctxs or [])
        answer_text = answer or ""
        reference_text = f"{question}\n{ground_truth}"

        faithfulness = _overlap_score(answer_text, context_text)
        answer_relevancy = mean([
            _overlap_score(ground_truth, answer_text),
            _overlap_score(question, answer_text),
        ])
        if ctxs:
            context_precision = mean(_overlap_score(reference_text, ctx) for ctx in ctxs)
        else:
            context_precision = 0.0
        context_recall = _overlap_score(ground_truth, context_text)

        per_question.append(
            EvalResult(
                question=question,
                answer=answer_text,
                contexts=ctxs or [],
                ground_truth=ground_truth,
                faithfulness=_clamp(faithfulness),
                answer_relevancy=_clamp(answer_relevancy),
                context_precision=_clamp(context_precision),
                context_recall=_clamp(context_recall),
            )
        )

    return {
        "faithfulness": mean([r.faithfulness for r in per_question]) if per_question else 0.0,
        "answer_relevancy": mean([r.answer_relevancy for r in per_question]) if per_question else 0.0,
        "context_precision": mean([r.context_precision for r in per_question]) if per_question else 0.0,
        "context_recall": mean([r.context_recall for r in per_question]) if per_question else 0.0,
        "per_question": per_question,
        "evaluation_mode": "heuristic",
    }


def _try_ragas_eval(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict | None:
    """Try RAGAS evaluation with OpenAI."""
    if not _has_openai_key():
        return None

    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except Exception:
        return None

    try:
        dataset = Dataset.from_dict(
            {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
            }
        )
        evaluator_llm = ChatOpenAI(
            model=os.getenv("RAGAS_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("BASE_URL") or None,
            temperature=0,
        )
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=evaluator_llm,
        )
        df = result.to_pandas()
        metric_cols = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        metric_values = []
        for col in metric_cols:
            if col in df:
                metric_values.extend([float(v) for v in df[col].fillna(0.0).tolist()])
        if not metric_values or all(v == 0.0 for v in metric_values):
            print("RAGAS returned empty/zero metrics; using heuristic fallback")
            return None
    except Exception as exc:
        print(f"⚠️  RAGAS unavailable: {exc}")
        return None

    per_question: list[EvalResult] = []
    for i, row in df.iterrows():
        row_dict = row.to_dict()
        per_question.append(
            EvalResult(
                question=str(row_dict.get("question", questions[i])),
                answer=str(row_dict.get("answer", answers[i])),
                contexts=row_dict.get("contexts", contexts[i]),
                ground_truth=str(row_dict.get("ground_truth", ground_truths[i])),
                faithfulness=_clamp(float(row_dict.get("faithfulness") or 0.0)),
                answer_relevancy=_clamp(float(row_dict.get("answer_relevancy") or 0.0)),
                context_precision=_clamp(float(row_dict.get("context_precision") or 0.0)),
                context_recall=_clamp(float(row_dict.get("context_recall") or 0.0)),
            )
        )

    return {
        "faithfulness": mean([r.faithfulness for r in per_question]) if per_question else 0.0,
        "answer_relevancy": mean([r.answer_relevancy for r in per_question]) if per_question else 0.0,
        "context_precision": mean([r.context_precision for r in per_question]) if per_question else 0.0,
        "context_recall": mean([r.context_recall for r in per_question]) if per_question else 0.0,
        "per_question": per_question,
        "evaluation_mode": "ragas",
    }


def evaluate_ragas(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict:
    """Run RAGAS or fallback to heuristic."""
    if not (len(questions) == len(answers) == len(contexts) == len(ground_truths)):
        raise ValueError("questions, answers, contexts, and ground_truths must have same length")

    ragas_result = _try_ragas_eval(questions, answers, contexts, ground_truths)
    if ragas_result is not None:
        return ragas_result
    print("ℹ️  Using heuristic evaluation (no OpenAI key)")
    return _heuristic_eval(questions, answers, contexts, ground_truths)


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N failures and diagnose issues."""
    if not eval_results:
        return []

    scored_results = []
    for result in eval_results:
        avg_score = mean([
            result.faithfulness,
            result.answer_relevancy,
            result.context_precision,
            result.context_recall,
        ])
        scored_results.append((avg_score, result))

    failures = []
    for avg_score, result in sorted(scored_results, key=lambda item: item[0])[:bottom_n]:
        metrics = {
            "faithfulness": result.faithfulness,
            "answer_relevancy": result.answer_relevancy,
            "context_precision": result.context_precision,
            "context_recall": result.context_recall,
        }
        worst_metric, worst_score = min(metrics.items(), key=lambda item: item[1])

        if worst_metric == "faithfulness" and worst_score < 0.85:
            diagnosis = "Hallucination: LLM suy diễn ngoài context"
            fix = "Siết system prompt, set temperature=0, thêm constraints"
        elif worst_metric == "context_recall" and worst_score < 0.75:
            diagnosis = "Retrieval gap: Thiếu chunk liên quan"
            fix = "Optimize chunking, tăng top-k BM25/Dense, hybrid search"
        elif worst_metric == "context_precision" and worst_score < 0.75:
            diagnosis = "Noise: Context có nội dung không liên quan"
            fix = "Cải thiện reranking, thêm semantic filter, metadata constraints"
        elif worst_metric == "answer_relevancy" and worst_score < 0.80:
            diagnosis = "Off-topic: Câu trả lời không bám sát câu hỏi"
            fix = "Query rewriting, better few-shot examples, tighter prompts"
        else:
            diagnosis = "Minor issue"
            fix = "Monitor trên larger test set"

        failures.append(
            {
                "question": result.question,
                "ground_truth": result.ground_truth,
                "answer": result.answer,
                "contexts": result.contexts,
                "worst_metric": worst_metric,
                "score": float(worst_score),
                "avg_score": float(avg_score),
                "metrics": metrics,
                "diagnosis": diagnosis,
                "suggested_fix": fix,
            }
        )

    return failures


def cluster_failures(failures: list[dict]) -> dict:
    """Cluster failures by diagnosis pattern."""
    clusters = {}
    for f in failures:
        diagnosis = f["diagnosis"]
        if diagnosis not in clusters:
            clusters[diagnosis] = []
        clusters[diagnosis].append(f)
    
    return {
        "num_clusters": len(clusters),
        "clusters": {k: {"count": len(v), "samples": [x["question"] for x in v[:3]]} for k, v in clusters.items()},
    }


def save_report(
    results: dict,
    failures: list[dict],
    clusters: dict,
    path: str = "reports/lab24_phase_a_report.json",
):
    """Save Phase A report."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    per_question = results.get("per_question", [])
    report = {
        "phase": "A: RAGAS Evaluation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "num_questions": len(per_question),
        "evaluation_mode": results.get("evaluation_mode", "unknown"),
        "aggregate_metrics": {
            "faithfulness": float(results.get("faithfulness", 0.0)),
            "answer_relevancy": float(results.get("answer_relevancy", 0.0)),
            "context_precision": float(results.get("context_precision", 0.0)),
            "context_recall": float(results.get("context_recall", 0.0)),
        },
        "metric_stats": _compute_metric_stats(per_question),
        "top_10_failures": failures,
        "failure_clusters": clusters,
        "per_question": [asdict(r) for r in per_question],
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ Phase A report saved to {path}")


def _compute_metric_stats(per_question: list[EvalResult]) -> dict:
    """Compute statistics for each metric."""
    if not per_question:
        return {}
    
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    stats = {}
    
    for metric in metrics:
        values = [getattr(r, metric) for r in per_question]
        stats[metric] = {
            "mean": round(mean(values), 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "std": round(stdev(values), 3) if len(values) > 1 else 0.0,
        }
    
    return stats


if __name__ == "__main__":
    # Demo: Load test set and show structure
    test_set = load_test_set_expanded()
    print(f"✅ Loaded {len(test_set)} expanded test questions")
    print(f"Sample question: {test_set[0]['question']}")
    print("Run lab24_main.py to execute full pipeline with Phase A evaluation.")
