"""Main entry point: baseline -> production pipeline -> comparison."""

import json
import os
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    print("=" * 60)
    print("LAB 18: PRODUCTION RAG PIPELINE")
    print("=" * 60)
    start = time.time()

    os.makedirs("reports", exist_ok=True)

    print("\nSTEP 1: Running Basic RAG Baseline...")
    print("-" * 40)
    from naive_baseline import main as run_baseline

    run_baseline()

    print("\nSTEP 2: Running Production Pipeline...")
    print("-" * 40)
    from src.pipeline import build_pipeline, evaluate_pipeline

    search, reranker = build_pipeline()
    evaluate_pipeline(search, reranker)

    for filename in ["ragas_report.json", "naive_baseline_report.json"]:
        if os.path.exists(filename):
            destination = os.path.join("reports", filename)
            if os.path.exists(destination):
                os.remove(destination)
            shutil.copyfile(filename, destination)
            try:
                os.remove(filename)
            except PermissionError:
                pass

    print("\nSTEP 3: Comparison")
    print("-" * 40)
    _print_comparison()

    elapsed = time.time() - start
    print(f"\nTotal time: {elapsed:.1f}s")
    print("\nNext steps:")
    print("  1. Điền analysis/failure_analysis.md")
    print("  2. Điền analysis/group_report.md")
    print("  3. Chạy: python check_lab.py")


def _print_comparison():
    naive_path = os.path.join("reports", "naive_baseline_report.json")
    prod_path = os.path.join("reports", "ragas_report.json")
    if not (os.path.exists(naive_path) and os.path.exists(prod_path)):
        print("Missing reports, cannot compare.")
        return

    with open(naive_path, encoding="utf-8") as f:
        naive = json.load(f)
    with open(prod_path, encoding="utf-8") as f:
        prod = json.load(f)

    print(f"\n{'Metric':<25} {'Basic':>8} {'Production':>12} {'Delta':>8}")
    print("-" * 58)
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        naive_score = float(naive.get("aggregate", {}).get(metric, 0))
        prod_score = float(prod.get("aggregate", {}).get(metric, 0))
        delta = prod_score - naive_score
        status = "✓" if prod_score >= 0.75 else " "
        print(f"{status} {metric:<23} {naive_score:>8.4f} {prod_score:>12.4f} {delta:>+8.4f}")


if __name__ == "__main__":
    main()
