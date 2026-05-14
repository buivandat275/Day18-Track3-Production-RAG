"""Lab 24 Phase B: LLM-Judge - pairwise, absolute, swap, Cohen kappa."""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from statistics import mean

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class PairwiseResult:
    question: str
    answer_a: str
    answer_b: str
    winner: str  # "A", "B", or "TIE"
    confidence: float  # 0-1
    reason: str


@dataclass
class AbsoluteJudgeResult:
    question: str
    answer: str
    score: float  # 1-5
    rating: str
    reason: str


@dataclass
class CohenKappaResult:
    rater1_judgments: list[str]
    rater2_judgments: list[str]
    agreement_matrix: dict
    cohen_kappa: float
    p_o: float
    p_e: float


def compute_cohen_kappa(judgments_a: list[str], judgments_b: list[str]) -> CohenKappaResult:
    """Compute Cohen kappa between two raters."""
    if len(judgments_a) != len(judgments_b):
        raise ValueError("Judgments must have equal length")
    if not judgments_a:
        raise ValueError("Judgments must not be empty")

    categories = sorted(set(judgments_a) | set(judgments_b))
    n = len(judgments_a)

    contingency = {cat: {c: 0 for c in categories} for cat in categories}
    for j_a, j_b in zip(judgments_a, judgments_b):
        contingency[j_a][j_b] += 1

    p_o = sum(contingency[cat][cat] for cat in categories) / n

    p_e = 0.0
    for cat in categories:
        p_cat_a = sum(contingency[cat].values()) / n
        p_cat_b = sum(contingency[c][cat] for c in categories) / n
        p_e += p_cat_a * p_cat_b

    # If both raters assign one identical class on the small 10-human subset,
    # observed agreement is perfect. We keep this explicit for the lab report.
    kappa = 1.0 if p_o == 1.0 and p_e == 1.0 else ((p_o - p_e) / (1 - p_e) if p_e < 1.0 else 0.0)

    return CohenKappaResult(
        rater1_judgments=judgments_a,
        rater2_judgments=judgments_b,
        agreement_matrix={k: dict(v) for k, v in contingency.items()},
        cohen_kappa=max(0.0, min(1.0, kappa)),
        p_o=p_o,
        p_e=p_e,
    )


def simulate_llm_judge(
    question: str,
    answer_a: str,
    answer_b: str,
    llm_version: str = "base",
) -> PairwiseResult:
    """Simulate an LLM pairwise judge with a deterministic CI fallback."""

    def _score(answer: str) -> float:
        lower = answer.lower()
        length_score = min(1.0, len(answer) / 220)
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        relevance = len(q_words & a_words) / len(q_words) if q_words else 0.5
        grounding_bonus = 0.12 if "theo chính sách" in lower or "theo chinh sach" in lower else 0.0
        uncertainty_penalty = 0.18 if "không rõ" in lower or "khong ro" in lower else 0.0
        version_offset = 0.01 if llm_version == "strict" and "theo chính sách" in lower else 0.0
        return length_score * 0.45 + relevance * 0.45 + grounding_bonus + version_offset - uncertainty_penalty

    score_a = _score(answer_a)
    score_b = _score(answer_b)
    diff = abs(score_a - score_b)

    if score_a > score_b and diff > 0.03:
        winner = "A"
        confidence = min(1.0, 0.55 + diff)
    elif score_b > score_a and diff > 0.03:
        winner = "B"
        confidence = min(1.0, 0.55 + diff)
    else:
        winner = "TIE"
        confidence = 1.0 - diff

    reasons = {
        "A": "Answer A is more complete, grounded, and relevant.",
        "B": "Answer B is more complete, grounded, and relevant.",
        "TIE": "Both answers are close under the rubric.",
    }
    return PairwiseResult(question, answer_a, answer_b, winner, confidence, reasons[winner])


def absolute_judge(questions: list[str], answers: list[str]) -> list[AbsoluteJudgeResult]:
    """Score answers on a 1-5 absolute quality rubric."""
    if len(questions) != len(answers):
        raise ValueError("Questions and answers must have equal length")

    results = []
    for question, answer in zip(questions, answers):
        q_terms = {w.lower() for w in question.split() if len(w) > 2}
        a_terms = {w.lower() for w in answer.split() if len(w) > 2}
        relevance = len(q_terms & a_terms) / max(1, len(q_terms))
        completeness = min(1.0, len(answer) / 220)
        grounded = 1.0 if "theo chính sách" in answer.lower() or "theo chinh sach" in answer.lower() else 0.75
        score = round(max(1.0, min(5.0, 1 + 4 * (0.45 * relevance + 0.40 * completeness + 0.15 * grounded))), 2)

        if score >= 4.5:
            rating = "excellent"
        elif score >= 3.5:
            rating = "good"
        elif score >= 2.5:
            rating = "acceptable"
        else:
            rating = "poor"

        results.append(
            AbsoluteJudgeResult(
                question=question,
                answer=answer,
                score=score,
                rating=rating,
                reason=f"relevance={relevance:.2f}, completeness={completeness:.2f}, grounded={grounded:.2f}",
            )
        )
    return results


def pairwise_judge(
    questions: list[str],
    answers_a: list[str],
    answers_b: list[str],
    llm_version: str = "base",
) -> list[PairwiseResult]:
    """Run pairwise comparisons between two answer sets."""
    if not (len(questions) == len(answers_a) == len(answers_b)):
        raise ValueError("All lists must have equal length")
    return [simulate_llm_judge(q, a_a, a_b, llm_version) for q, a_a, a_b in zip(questions, answers_a, answers_b)]


def swap_and_average(pairwise_results: list[PairwiseResult]) -> list[dict]:
    """Swap (A, B), normalize the swapped winner, and average."""
    swapped_results = [
        simulate_llm_judge(result.question, result.answer_b, result.answer_a, "base")
        for result in pairwise_results
    ]

    averaged = []
    for orig, swap in zip(pairwise_results, swapped_results):
        winner_score_orig = {"A": 1, "B": -1, "TIE": 0}[orig.winner]
        winner_score_swap = {"B": 1, "A": -1, "TIE": 0}[swap.winner]
        avg_score = (winner_score_orig + winner_score_swap) / 2
        avg_confidence = (orig.confidence + swap.confidence) / 2

        if avg_score > 0.1:
            final_winner = "A"
        elif avg_score < -0.1:
            final_winner = "B"
        else:
            final_winner = "TIE"

        normalized_swapped_winner = {"A": "B", "B": "A", "TIE": "TIE"}[swap.winner]
        averaged.append(
            {
                "question": orig.question,
                "original_judgment": orig.winner,
                "swapped_judgment": swap.winner,
                "normalized_swapped_judgment": normalized_swapped_winner,
                "position_bias_detected": orig.winner != normalized_swapped_winner,
                "final_winner": final_winner,
                "final_confidence": avg_confidence,
            }
        )
    return averaged


def bias_analysis(pairwise_results: list[PairwiseResult], averaged_results: list[dict] | None = None) -> dict:
    """Analyze judge bias before and after swap normalization."""
    total = len(pairwise_results)
    winners = [r.winner for r in pairwise_results]
    confidences = [r.confidence for r in pairwise_results]
    swap_bias_count = sum(1 for r in (averaged_results or []) if r["position_bias_detected"])

    return {
        "total_comparisons": total,
        "position_bias": {
            "answer_a_wins": winners.count("A"),
            "answer_b_wins": winners.count("B"),
            "ties": winners.count("TIE"),
        },
        "position_bias_ratio": (winners.count("A") - winners.count("B")) / max(1, total - winners.count("TIE")),
        "swap_inconsistency_count": swap_bias_count,
        "swap_inconsistency_rate": round(swap_bias_count / max(1, total), 3),
        "avg_confidence": mean(confidences) if confidences else 0.0,
        "min_confidence": min(confidences) if confidences else 0.0,
        "max_confidence": max(confidences) if confidences else 0.0,
        "bias_mitigations": [
            "Run original and swapped order.",
            "Normalize swapped labels back to original answer identity.",
            "Use final_winner from averaged signed score.",
            "Keep answer IDs hidden from the judge prompt.",
        ],
        "interpretation": _interpret_bias(winners, swap_bias_count, total),
    }


def _interpret_bias(winners: list[str], swap_bias_count: int, total: int) -> str:
    a_wins = winners.count("A")
    b_wins = winners.count("B")
    ratio = (a_wins - b_wins) / max(1, a_wins + b_wins)
    if swap_bias_count:
        return f"Swap check found {swap_bias_count}/{total} inconsistent judgments; use averaged winner."
    if abs(ratio) < 0.1:
        return "No significant position bias after swap normalization."
    return f"Raw judgments favor Answer {'A' if ratio > 0 else 'B'}; swap normalization is required."


def load_human_judgments(path: str = "human_judgments_10.json") -> list[dict]:
    """Load the 10 human labels required for judge agreement."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_report(
    pairwise_results: list[PairwiseResult],
    averaged_results: list[dict],
    absolute_results: list[AbsoluteJudgeResult],
    bias_report: dict,
    cohen_kappa_result: CohenKappaResult | None,
    human_agreement: dict | None = None,
    path: str = "reports/lab24_phase_b_report.json",
):
    """Save Phase B report."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    report = {
        "phase": "B: LLM-Judge",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pairwise_comparisons": [asdict(r) for r in pairwise_results],
        "swap_and_average": averaged_results,
        "absolute_judge": [asdict(r) for r in absolute_results],
        "bias_analysis": bias_report,
        "inter_annotator_agreement": None,
        "human_agreement_10": human_agreement,
    }

    if cohen_kappa_result:
        report["inter_annotator_agreement"] = {
            "cohen_kappa": float(cohen_kappa_result.cohen_kappa),
            "observed_agreement": float(cohen_kappa_result.p_o),
            "expected_agreement": float(cohen_kappa_result.p_e),
            "agreement_matrix": cohen_kappa_result.agreement_matrix,
            "interpretation": _interpret_kappa(cohen_kappa_result.cohen_kappa),
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Phase B report saved to {path}")


def _interpret_kappa(kappa: float) -> str:
    if kappa < 0:
        return "Poor agreement (kappa < 0)"
    if kappa < 0.2:
        return "Slight agreement (kappa < 0.2)"
    if kappa < 0.4:
        return "Fair agreement (0.2 <= kappa < 0.4)"
    if kappa < 0.6:
        return "Moderate agreement (0.4 <= kappa < 0.6)"
    if kappa < 0.8:
        return "Substantial agreement (0.6 <= kappa < 0.8)"
    return "Almost perfect agreement (kappa >= 0.8)"


if __name__ == "__main__":
    questions = ["Nhan vien duoc nghi phep bao nhieu ngay?", "Thoi gian thu viec la bao lau?"]
    answers_a = ["Theo chính sách công ty: 12 ngày mỗi năm.", "Theo chính sách công ty: 60 ngày thử việc."]
    answers_b = ["12 ngày.", "60 ngày."]
    results = pairwise_judge(questions, answers_a, answers_b)
    print(f"Ran {len(results)} pairwise comparisons")
