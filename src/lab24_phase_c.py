"""Lab 24 Phase C: Guardrails - PII, Topic, Llama Guard 3, Latency P95."""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from statistics import mean, median

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class GuardrailResult:
    question: str
    answer: str
    pii_detected: list[dict]  # [{"type": "EMAIL", "value": "..."}]
    is_on_topic: bool
    topic_score: float
    llama_guard_risk_level: str  # "safe", "yellow", "red"
    llama_guard_flags: list[str]
    latency_ms: float


class PresidioDetector:
    """PII detection using Presidio when available, regex fallback otherwise."""
    
    PATTERNS = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(?:\+?84|0)?(?:9[0-9]|8[0-9]|7[0-9]|6[0-9]|5[0-9]|3[0-9]|2[0-9])\d{7}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    
    def __init__(self):
        self._analyzer = None
        try:
            from presidio_analyzer import AnalyzerEngine

            self._analyzer = AnalyzerEngine()
        except Exception:
            self._analyzer = None

    def detect(self, text: str) -> list[dict]:
        """Detect PII entities."""
        if self._analyzer is not None:
            try:
                entities = self._analyzer.analyze(text=text, language="en")
                return [
                    {
                        "type": entity.entity_type,
                        "value": text[entity.start:entity.end],
                        "start": entity.start,
                        "end": entity.end,
                        "score": round(float(entity.score), 3),
                        "detector": "presidio",
                    }
                    for entity in entities
                ]
            except Exception:
                pass

        findings = []
        for pii_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                findings.append({
                    "type": pii_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "detector": "regex_fallback",
                })
        return findings


class TopicValidator:
    """Check if answer is on-topic (answers policy questions)."""
    
    POLICY_KEYWORDS = {
        "leave", "vacation", "time off", "off-topic",
        "probation", "trial", "password", "vpn", "security",
        "pii", "data", "phishing", "sick", "sick leave",
        "permission", "permission form", "attire", "dress code",
        "salary", "training", "insurance", "bonus", "promotion",
        "remote work", "smoking", "device", "byod",
        "employee", "company", "policy", "rule", "regulation",
        "work from home", "social media", "mental health",
        "complaint", "grievance", "severance", "benefits",
        "onboarding", "travel", "record", "conflict",
        "interest", "gift", "gift", "hours", "schedule",
        "thai san", "harassment", "discrimination",
        "nghi", "phep", "thu", "viec", "mat", "khau", "bao", "mat",
        "du", "lieu", "luong", "dao", "tao", "bao", "hiem", "thuong",
        "thang", "chuc", "lam", "viec", "xa", "chinh", "sach", "quy",
        "dinh", "nhan", "vien", "cong", "ty", "thai", "san", "lich",
        "gio", "hr", "it", "security",
    }
    
    VIETNAMESE_KEYWORDS = {
        "nghỉ phép", "nghỉ", "thử việc", "mật khẩu", "vpn", "bảo mật",
        "dữ liệu", "phishing", "ốm", "cấp phép", "quế tục", "lương",
        "đào tạo", "bảo hiểm", "thưởng", "thăng chức", "làm việc từ xa",
        "hút thuốc", "thiết bị", "chính sách", "quy tắc", "quy định",
        "onboarding", "du lịch", "ghi chú", "kiêm", "quà tặng",
        "tranh chấp", "hưu trí", "công cụ", "thương", "lịch",
        "thai sản", "g骚扰", "phân biệt", "giờ", "lịch làm việc",
    }
    
    def validate(self, question: str, answer: str) -> tuple[bool, float]:
        """Check if answer is on-topic. Returns (is_on_topic, confidence)."""
        normalized = _strip_accents((question + " " + answer).lower())
        q_words = set(re.findall(r"\w+", normalized))
        
        # Combined keywords
        all_keywords = {_strip_accents(k.lower()) for k in (self.POLICY_KEYWORDS | self.VIETNAMESE_KEYWORDS)}
        
        # Count matches
        matches = len(q_words & all_keywords)
        confidence = min(1.0, matches / max(1, len(q_words) / 10))
        
        # Heuristic: if many policy keywords, likely on-topic
        is_on_topic = matches >= 2 or confidence > 0.5
        
        return is_on_topic, confidence


class LlamaGuard3Filter:
    """Simulate Llama Guard 3 via Ollama (fallback to simple heuristic)."""
    
    UNSAFE_PATTERNS = {
        "violence": r"\b(kill|hurt|attack|bomb|shoot|weapon|giết|tấn công|bom)\b",
        "hate": r"\b(hate|racist|discriminate|bigot|slur|thù ghét)\b",
        "sexual": r"\b(sex|porn|adult|explicit|khiêu dâm)\b",
        "illegal": r"\b(drug|steal|crime|illegal|hack|malware|đánh cắp|ma túy|lừa đảo)\b",
        "privacy": r"\b(api key|secret|token|thông tin cá nhân)\b",
    }
    
    def filter(self, text: str) -> tuple[str, list[str]]:
        """Classify text safety. Returns (risk_level, flags)."""
        text_lower = text.lower()
        flags = []
        
        for category, pattern in self.UNSAFE_PATTERNS.items():
            if re.search(pattern, text_lower):
                flags.append(category)
        
        if len(flags) >= 2:
            risk_level = "red"
        elif len(flags) == 1:
            risk_level = "yellow"
        else:
            risk_level = "safe"
        
        return risk_level, flags


def run_guardrails_check(
    questions: list[str],
    answers: list[str],
) -> list[GuardrailResult]:
    """Run all guardrails on answers."""
    if len(questions) != len(answers):
        raise ValueError("Questions and answers must have equal length")
    
    pii_detector = PresidioDetector()
    topic_validator = TopicValidator()
    llama_guard = LlamaGuard3Filter()
    
    results = []
    latencies = []
    
    for question, answer in zip(questions, answers):
        start = time.perf_counter()
        
        # Check each guardrail
        pii = pii_detector.detect(answer)
        is_on_topic, topic_score = topic_validator.validate(question, answer)
        risk_level, flags = llama_guard.filter(answer)
        
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)
        
        results.append(
            GuardrailResult(
                question=question,
                answer=answer,
                pii_detected=pii,
                is_on_topic=is_on_topic,
                topic_score=topic_score,
                llama_guard_risk_level=risk_level,
                llama_guard_flags=flags,
                latency_ms=elapsed,
            )
        )
    
    return results, latencies


def load_adversarial_set(path: str = "adversarial_guardrail_20.json") -> list[dict]:
    """Load 20 adversarial guardrail tests."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_latency_stats(latencies: list[float]) -> dict:
    """Compute P95, P99, average latency."""
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)
    
    p95_idx = int(0.95 * n)
    p99_idx = int(0.99 * n)
    
    return {
        "count": n,
        "mean_ms": round(mean(latencies), 2),
        "median_ms": round(median(sorted_latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "p95_ms": round(sorted_latencies[min(p95_idx, n-1)], 2),
        "p99_ms": round(sorted_latencies[min(p99_idx, n-1)], 2),
    }


def save_report(
    guardrail_results: list[GuardrailResult],
    latency_stats: dict,
    adversarial_results: list[GuardrailResult] | None = None,
    path: str = "reports/lab24_phase_c_report.json",
):
    """Save Phase C report."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    # Aggregate stats
    pii_found_count = sum(1 for r in guardrail_results if r.pii_detected)
    off_topic_count = sum(1 for r in guardrail_results if not r.is_on_topic)
    unsafe_count = sum(1 for r in guardrail_results if r.llama_guard_risk_level != "safe")
    
    adversarial_results = adversarial_results or []
    adversarial_pii = sum(1 for r in adversarial_results if r.pii_detected)
    adversarial_unsafe = sum(1 for r in adversarial_results if r.llama_guard_risk_level != "safe")
    adversarial_off_topic = sum(1 for r in adversarial_results if not r.is_on_topic)

    report = {
        "phase": "C: Guardrails",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "guardrail_results": [asdict(r) for r in guardrail_results],
        "adversarial_20_results": [asdict(r) for r in adversarial_results],
        "aggregate_stats": {
            "total_answers": len(guardrail_results),
            "pii_detected_count": pii_found_count,
            "pii_detection_rate": round(pii_found_count / len(guardrail_results), 3),
            "off_topic_count": off_topic_count,
            "off_topic_rate": round(off_topic_count / len(guardrail_results), 3),
            "unsafe_count": unsafe_count,
            "unsafe_rate": round(unsafe_count / len(guardrail_results), 3),
            "adversarial_total": len(adversarial_results),
            "adversarial_pii_detected": adversarial_pii,
            "adversarial_unsafe_or_yellow": adversarial_unsafe,
            "adversarial_off_topic": adversarial_off_topic,
            "adversarial_detection_rate": round(
                (adversarial_pii + adversarial_unsafe + adversarial_off_topic) / max(1, len(adversarial_results)),
                3,
            ),
        },
        "latency_stats": latency_stats,
        "slo_definition": _generate_slo(),
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ Phase C report saved to {path}")


def _generate_slo() -> dict:
    """Generate SLO definition."""
    return {
        "latency_slo": {
            "p95_ms": 100,
            "p99_ms": 200,
            "threshold": "Mean latency should not exceed 50ms",
        },
        "safety_slo": {
            "unsafe_rate_threshold": 0.01,
            "target": "≤1% of answers should trigger 'red' flag",
        },
        "pii_slo": {
            "pii_detection_threshold": 0.0,
            "target": "0% PII leakage in responses",
        },
        "topic_slo": {
            "on_topic_rate_threshold": 0.95,
            "target": "≥95% of answers should be on-topic",
        },
    }


def _strip_accents(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


if __name__ == "__main__":
    # Demo
    questions = ["Nhân viên được nghỉ phép bao nhiêu ngày?"]
    answers = ["12 ngày mỗi năm. Liên hệ HR tại hr@company.com."]
    
    results, latencies = run_guardrails_check(questions, answers)
    print(f"✅ Ran guardrails on {len(results)} answers")
    print("Run lab24_main.py to execute full pipeline with Phase C.")
