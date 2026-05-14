# Lab 24 Reflection: Evaluation + Guardrails

**Sinh vien:** Bui Van Dat  
**Ma so:** 2A202600355  
**Ngay:** 2026-05-15

## What I Built

I built a complete evaluation and guardrail stack for the Day 18 RAG pipeline:

- Phase A: 50-question evaluation set, 4 RAGAS-compatible metrics, bottom-10 failure analysis, and failure clustering.
- Phase B: pairwise judge, absolute judge, swap-and-average bias mitigation, Cohen kappa for LLM-vs-LLM, and Cohen kappa against 10 human labels.
- Phase C: Presidio-compatible PII detection, topic validation, Llama Guard 3 style safety filtering, 20 adversarial tests, and P95 latency measurement.
- Blueprint: SLOs, architecture diagram, alert playbook, cost analysis, and CI/CD workflow.

## Lessons Learned

Evaluation is only useful when it is repeatable. The CI workflow makes the lab reproducible by compiling the modules, running the full stack, checking report outputs, and enforcing guardrail gates.

Bias mitigation matters for LLM judges. A single A/B order can hide position bias, so I used swapped order, normalized the swapped result back to the original answer identity, and reported the final averaged winner.

Guardrails should be measured like production code. The report includes PII rate, unsafe rate, topic rate, adversarial detection rate, and P95 latency instead of only saying the guardrail exists.

## Remaining Production Work

The offline version uses deterministic fallbacks when external services are unavailable. In production, the same interfaces should call real RAGAS with an evaluator LLM, real Presidio models, and an actual Llama Guard 3 endpoint.
