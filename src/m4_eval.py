"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
from dataclasses import dataclass
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH

# Import ragas and datasets
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

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


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    # Setup LLM for evaluation
    base_url = os.getenv("BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    # RAGAS 0.4.x uses Langchain models for evaluation
    evaluator_llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=api_key,
        base_url=base_url
    )

    dataset_dict = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }
    dataset = Dataset.from_dict(dataset_dict)

    # Note: Ragas metrics typically require LLM and Embeddings. 
    # For some metrics, embeddings might be needed (e.g., answer_relevancy if using embedding-based version).
    # Defaulting to LLM-based metrics as specified in the TODO.
    
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm
    )

    df = result.to_pandas()
    
    per_question = []
    for i, (_, row) in enumerate(df.iterrows()):
        row_dict = row.to_dict()
        
        # Safely extract data with fallbacks to input lists
        q = row_dict.get("question", questions[i])
        a = row_dict.get("answer", answers[i])
        c = row_dict.get("contexts", contexts[i])
        gt = row_dict.get("ground_truth", ground_truths[i])
        
        # Safely extract metrics
        f = row_dict.get("faithfulness", 0.0)
        ar = row_dict.get("answer_relevancy", 0.0)
        cp = row_dict.get("context_precision", 0.0)
        cr = row_dict.get("context_recall", 0.0)
        
        per_question.append(EvalResult(
            question=str(q),
            answer=str(a),
            contexts=c if isinstance(c, list) else [str(c)],
            ground_truth=str(gt),
            faithfulness=float(f) if f is not None else 0.0,
            answer_relevancy=float(ar) if ar is not None else 0.0,
            context_precision=float(cp) if cp is not None else 0.0,
            context_recall=float(cr) if cr is not None else 0.0
        ))

    # 6. Extract scores and return
    # Initializing with default 0.0
    final_results = {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_precision": 0.0,
        "context_recall": 0.0,
        "per_question": per_question
    }

    # Safe extraction of aggregate scores
    try:
        for metric_name in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            if metric_name in result:
                val = result[metric_name]
                final_results[metric_name] = float(val) if val is not None else 0.0
    except Exception as e:
        print(f"Warning: Could not extract aggregate scores: {e}")

    return final_results







def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    if not eval_results:
        return []

    # 1. Calculate average score for each result
    scored_results = []
    for r in eval_results:
        avg_score = (r.faithfulness + r.answer_relevancy + r.context_precision + r.context_recall) / 4
        scored_results.append((avg_score, r))

    # 2. Sort by avg_score ascending → take bottom_n
    scored_results.sort(key=lambda x: x[0])
    worst_results = scored_results[:bottom_n]

    analysis = []
    for avg, r in worst_results:
        # 3. For each failed question, find the worst metric
        metrics = [
            ("faithfulness", r.faithfulness),
            ("answer_relevancy", r.answer_relevancy),
            ("context_precision", r.context_precision),
            ("context_recall", r.context_recall)
        ]
        worst_metric, worst_score = min(metrics, key=lambda x: x[1])

        diagnosis = "Unknown issue"
        fix = "Further investigation needed"

        # Diagnostic Mapping based on thresholds
        if worst_metric == "faithfulness" and worst_score < 0.85:
            diagnosis = "LLM hallucinating"
            fix = "Tighten prompt, lower temperature"
        elif worst_metric == "context_recall" and worst_score < 0.75:
            diagnosis = "Missing relevant chunks"
            fix = "Improve chunking or add BM25"
        elif worst_metric == "context_precision" and worst_score < 0.75:
            diagnosis = "Too many irrelevant chunks"
            fix = "Add reranking or metadata filter"
        elif worst_metric == "answer_relevancy" and worst_score < 0.80:
            diagnosis = "Answer doesn't match question"
            fix = "Improve prompt template"

        analysis.append({
            "question": r.question,
            "worst_metric": worst_metric,
            "score": float(worst_score),
            "diagnosis": diagnosis,
            "suggested_fix": fix
        })

    return analysis


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")

