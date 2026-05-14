"""Lab 24 Main: orchestrate Phase A, B, C evaluation and guardrails."""

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

from src.lab24_phase_a import (
    cluster_failures,
    evaluate_ragas,
    failure_analysis,
    load_test_set_expanded,
    save_report as save_report_a,
)
from src.lab24_phase_b import (
    absolute_judge,
    bias_analysis,
    compute_cohen_kappa,
    load_human_judgments,
    pairwise_judge,
    save_report as save_report_b,
    swap_and_average,
)
from src.lab24_phase_c import (
    compute_latency_stats,
    load_adversarial_set,
    run_guardrails_check,
    save_report as save_report_c,
)


def generate_demo_answers(test_set: list[dict], pipeline_type: str = "baseline") -> list[str]:
    """Generate deterministic answers for CI; production swaps this for the RAG pipeline."""
    answers = []
    for item in test_set:
        ground_truth = item["ground_truth"]
        if pipeline_type == "baseline":
            answer = ground_truth
        elif pipeline_type == "good":
            answer = f"Theo chính sách công ty: {ground_truth}"
        else:
            parts = ground_truth.split(".")
            answer = parts[0] + "." if parts else "Không rõ."
        answers.append(answer)
    return answers


def generate_demo_contexts(test_set: list[dict]) -> list[list[str]]:
    """Generate deterministic contexts for CI."""
    contexts = []
    for item in test_set:
        contexts.append(
            [
                item["ground_truth"],
                f"Policy excerpt liên quan đến câu hỏi: {item['question'][:80]}",
            ]
        )
    return contexts


def main():
    print("=" * 70)
    print("LAB 24: EVALUATION + GUARDRAIL STACK FOR RAG PIPELINE")
    print("=" * 70)

    overall_start = time.time()
    os.makedirs("reports", exist_ok=True)
    test_set = load_test_set_expanded()
    questions = [item["question"] for item in test_set]
    ground_truths = [item["ground_truth"] for item in test_set]
    print(f"Loaded {len(test_set)} expanded test questions")

    # Phase A
    print("\n" + "=" * 70)
    print("PHASE A: RAGAS EVALUATION")
    print("=" * 70)
    phase_a_start = time.time()
    answers_baseline = generate_demo_answers(test_set, "baseline")
    contexts = generate_demo_contexts(test_set)
    eval_result = evaluate_ragas(questions, answers_baseline, contexts, ground_truths)
    failures = failure_analysis(eval_result["per_question"], bottom_n=10)
    clusters = cluster_failures(failures)
    save_report_a(eval_result, failures, clusters)
    phase_a_duration = time.time() - phase_a_start
    print(f"Phase A duration: {phase_a_duration:.1f}s")

    # Phase B
    print("\n" + "=" * 70)
    print("PHASE B: LLM-JUDGE EVALUATION")
    print("=" * 70)
    phase_b_start = time.time()
    answers_good = generate_demo_answers(test_set, "good")
    answers_mediocre = generate_demo_answers(test_set, "mediocre")

    pairwise_results = pairwise_judge(questions, answers_good, answers_mediocre)
    averaged_results = swap_and_average(pairwise_results)
    absolute_results = absolute_judge(questions, answers_good)
    bias_report = bias_analysis(pairwise_results, averaged_results)

    judgments_a = [r.winner for r in pairwise_results]
    judgments_b = [r.winner for r in pairwise_judge(questions, answers_good, answers_mediocre, llm_version="strict")]
    cohen_result = compute_cohen_kappa(judgments_a, judgments_b)

    human_labels = load_human_judgments()
    final_by_question = {r["question"]: r["final_winner"] for r in averaged_results}
    human_pairs = []
    for item in human_labels:
        if "question_index" in item:
            idx = int(item["question_index"])
            if 0 <= idx < len(averaged_results):
                human_pairs.append((averaged_results[idx]["final_winner"], item["human_winner"]))
        elif item.get("question") in final_by_question:
            human_pairs.append((final_by_question[item["question"]], item["human_winner"]))
    human_agreement = None
    if human_pairs:
        llm_subset, human_subset = zip(*human_pairs)
        human_kappa = compute_cohen_kappa(list(llm_subset), list(human_subset))
        human_agreement = {
            "num_human_labels": len(human_pairs),
            "cohen_kappa_vs_human": human_kappa.cohen_kappa,
            "observed_agreement": human_kappa.p_o,
            "expected_agreement": human_kappa.p_e,
            "agreement_matrix": human_kappa.agreement_matrix,
            "labels_source": "human_judgments_10.json",
        }

    save_report_b(pairwise_results, averaged_results, absolute_results, bias_report, cohen_result, human_agreement)
    phase_b_duration = time.time() - phase_b_start
    print(f"Phase B duration: {phase_b_duration:.1f}s")

    # Phase C
    print("\n" + "=" * 70)
    print("PHASE C: GUARDRAILS STACK")
    print("=" * 70)
    phase_c_start = time.time()
    guardrail_results, latencies = run_guardrails_check(questions, answers_baseline)

    adversarial_set = load_adversarial_set()
    adversarial_questions = [item["question"] for item in adversarial_set]
    adversarial_answers = [item["answer"] for item in adversarial_set]
    adversarial_results, adversarial_latencies = run_guardrails_check(adversarial_questions, adversarial_answers)

    latency_stats = compute_latency_stats(latencies + adversarial_latencies)
    save_report_c(guardrail_results, latency_stats, adversarial_results=adversarial_results)
    phase_c_duration = time.time() - phase_c_start
    print(f"Phase C duration: {phase_c_duration:.1f}s")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("Reports generated:")
    print("  reports/lab24_phase_a_report.json")
    print("  reports/lab24_phase_b_report.json")
    print("  reports/lab24_phase_c_report.json")
    print(f"Total: {time.time() - overall_start:.1f}s")


if __name__ == "__main__":
    main()
