"""
Module 5: Enrichment Pipeline
==============================
Enrich chunks before embedding: summarization, HyQA, contextual prepend,
and automatic metadata extraction.

Test: pytest tests/test_m5.py
"""

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY


OPENAI_MODEL = os.getenv("OPENAI_ENRICHMENT_MODEL", "gpt-4o-mini")
_OPENAI_FAILED = False


@dataclass
class EnrichedChunk:
    """A chunk with retrieval-oriented enrichment fields."""

    original_text: str
    enriched_text: str
    summary: str
    hypothesis_questions: list[str]
    auto_metadata: dict
    method: str  # "contextual", "summary", "hyqa", "full"


def _has_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        return False
    placeholders = {"sk-...", "...", "your-api-key", "your_openai_api_key"}
    return key.lower() not in placeholders and not key.endswith("...")


def _call_openai(system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
    """Best-effort OpenAI call; falls back silently when unavailable."""
    global _OPENAI_FAILED

    if _OPENAI_FAILED or not _has_openai_key():
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY, timeout=8.0)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        _OPENAI_FAILED = True
        return None


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return sentences or [text]


def _clean_lines(text: str, limit: int | None = None) -> list[str]:
    lines = []
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*[-*+\d.)]+\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines[:limit] if limit is not None else lines


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _infer_metadata(text: str) -> dict:
    lower = (text or "").lower()
    normalized_lower = _strip_accents(lower)

    rules = [
        (
            ("nghỉ", "phép", "12"),
            "chính sách nghỉ phép",
            "hr",
            ["nhân viên", "nghỉ phép năm"],
        ),
        (
            ("thử việc", "trial", "probation", "60"),
            "thử việc",
            "hr",
            ["nhân viên", "thử việc"],
        ),
        (
            ("mật khẩu", "password", "90", "vpn", "wireguard", "aes"),
            "an toàn thông tin",
            "it",
            ["mật khẩu", "VPN"],
        ),
        (
            ("dữ liệu", "data", "privacy", "personal"),
            "bảo vệ dữ liệu cá nhân",
            "policy",
            ["dữ liệu cá nhân", "quyền riêng tư"],
        ),
        (
            ("báo cáo", "tài chính", "finance", "revenue", "profit"),
            "báo cáo tài chính",
            "finance",
            ["báo cáo tài chính"],
        ),
    ]

    for keywords, topic, category, entities in rules:
        if any(keyword in lower or _strip_accents(keyword) in normalized_lower for keyword in keywords):
            return {
                "topic": topic,
                "entities": entities,
                "category": category,
                "language": "vi" if any(ord(ch) > 127 for ch in text or "") else "en",
            }

    return {
        "topic": "thông tin chung",
        "entities": [],
        "category": "policy",
        "language": "vi" if any(ord(ch) > 127 for ch in text or "") else "en",
    }


def summarize_chunk(text: str) -> str:
    """
    Create a short summary for a chunk.

    Uses OpenAI when available; otherwise returns an extractive summary so the
    enrichment pipeline remains usable offline.
    """
    text = (text or "").strip()
    if not text:
        return ""

    llm_summary = _call_openai(
        "Tóm tắt đoạn văn bằng tiếng Việt có đầy đủ dấu trong 2 câu ngắn gọn. "
        "Giữ lại các con số và thuật ngữ chính sách quan trọng.",
        text,
        max_tokens=150,
    )
    if llm_summary:
        return llm_summary

    sentences = _split_sentences(text)
    summary = " ".join(sentences[:2]).strip()
    if len(summary) > 500:
        summary = summary[:497].rstrip() + "..."
    return summary


def generate_hypothesis_questions(text: str, n_questions: int = 3) -> list[str]:
    """
    Generate questions that the chunk can answer.

    HyQA helps bridge vocabulary mismatch between user queries and document text.
    """
    if n_questions <= 0:
        return []

    text = (text or "").strip()
    if not text:
        return []

    llm_questions = _call_openai(
        f"Dựa trên đoạn văn, viết {n_questions} câu hỏi tiếng Việt có đầy đủ dấu "
        "mà đoạn văn có thể trả lời. Trả về mỗi câu hỏi trên một dòng.",
        text,
        max_tokens=220,
    )
    if llm_questions:
        questions = _clean_lines(llm_questions, limit=n_questions)
        if questions:
            return questions

    meta = _infer_metadata(text)
    topic = meta["topic"]
    category = meta["category"]

    if category == "hr" and topic == "chính sách nghỉ phép":
        questions = [
            "Nhân viên được nghỉ phép bao nhiêu ngày?",
            "Quy định về nghỉ phép năm là gì?",
            "Ngày nghỉ phép tăng theo thâm niên như thế nào?",
        ]
    elif category == "hr" and topic == "thử việc":
        questions = [
            "Thời gian thử việc là bao nhiêu ngày?",
            "Quy định về thử việc của nhân viên là gì?",
            "Nhân viên cần biết gì về giai đoạn thử việc?",
        ]
    elif category == "it":
        questions = [
            "Quy định bảo mật công nghệ thông tin là gì?",
            "Mật khẩu cần thay đổi sau bao nhiêu ngày?",
            "VPN hoặc tài khoản truy cập được quy định như thế nào?",
        ]
    elif category == "finance":
        questions = [
            "Đoạn này nói về thông tin tài chính nào?",
            "Báo cáo tài chính đề cập đến chỉ số nào?",
            "Nội dung tài chính quan trọng trong đoạn là gì?",
        ]
    else:
        questions = [
            f"Đoạn văn này nói về {topic} như thế nào?",
            "Thông tin quan trọng trong đoạn văn là gì?",
            "Người đọc cần nắm quy định nào từ đoạn này?",
        ]

    return questions[:n_questions]


def contextual_prepend(text: str, document_title: str = "") -> str:
    """
    Prepend a short retrieval context while preserving the original text.
    """
    text = (text or "").strip()
    title = (document_title or "tài liệu nguồn").strip()

    llm_context = _call_openai(
        "Viết đúng một câu tiếng Việt có đầy đủ dấu, mô tả đoạn này thuộc tài liệu "
        "nào và nói về chủ đề gì. Không trả lời nội dung của đoạn.",
        f"Tài liệu: {title}\n\nĐoạn văn:\n{text}",
        max_tokens=80,
    )

    if llm_context:
        context = llm_context
    else:
        meta = _infer_metadata(text)
        context = f"Trích từ {title}, đoạn này nói về {meta['topic']}."

    return f"{context}\n\n{text}" if text else context


def extract_metadata(text: str) -> dict:
    """
    Extract retrieval metadata: topic, entities, category, and language.
    """
    text = (text or "").strip()
    if not text:
        return {
            "topic": "trống",
            "entities": [],
            "category": "policy",
            "language": "unknown",
        }

    llm_metadata = _call_openai(
        'Trích xuất metadata từ đoạn văn. Trả về JSON hợp lệ với các khóa: '
        '"topic", "entities", "category", "language". Các giá trị tiếng Việt '
        'như "topic" và "entities" phải có đầy đủ dấu. "category" phải là một '
        'trong các giá trị "policy", "hr", "it", "finance".',
        text,
        max_tokens=180,
    )
    if llm_metadata:
        match = re.search(r"\{.*\}", llm_metadata, flags=re.DOTALL)
        raw_json = match.group(0) if match else llm_metadata
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict):
                fallback = _infer_metadata(text)
                return {
                    "topic": str(data.get("topic") or fallback["topic"]),
                    "entities": data.get("entities") if isinstance(data.get("entities"), list) else fallback["entities"],
                    "category": str(data.get("category") or fallback["category"]),
                    "language": str(data.get("language") or fallback["language"]),
                }
        except json.JSONDecodeError:
            pass

    return _infer_metadata(text)


def enrich_chunks(
    chunks: list[dict],
    methods: list[str] | None = None,
) -> list[EnrichedChunk]:
    """
    Run enrichment over a list of {"text": str, "metadata": dict} chunks.
    """
    if methods is None:
        methods = ["contextual", "hyqa", "metadata"]

    normalized_methods = [m.lower() for m in methods]
    use_full = "full" in normalized_methods
    method_label = "+".join(normalized_methods) if normalized_methods else "raw"
    enriched = []

    for chunk in chunks:
        text = str(chunk.get("text", "") if isinstance(chunk, dict) else "")
        metadata = dict(chunk.get("metadata") or {}) if isinstance(chunk, dict) else {}

        summary = summarize_chunk(text) if use_full or "summary" in normalized_methods else ""
        questions = (
            generate_hypothesis_questions(text)
            if use_full or "hyqa" in normalized_methods
            else []
        )
        enriched_text = (
            contextual_prepend(text, metadata.get("source", ""))
            if use_full or "contextual" in normalized_methods
            else text
        )
        auto_meta = extract_metadata(text) if use_full or "metadata" in normalized_methods else {}

        extra_sections = []
        if summary:
            extra_sections.append(f"Tóm tắt: {summary}")
        if questions:
            extra_sections.append("Câu hỏi giả định:\n" + "\n".join(questions))
        if extra_sections:
            enriched_text = "\n\n".join([enriched_text, *extra_sections])

        enriched.append(
            EnrichedChunk(
                original_text=text,
                enriched_text=enriched_text,
                summary=summary,
                hypothesis_questions=questions,
                auto_metadata={**metadata, **auto_meta},
                method=method_label,
            )
        )

    return enriched


if __name__ == "__main__":
    sample = (
        "Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm. "
        "Số ngày nghỉ phép tăng thêm 1 ngày cho mỗi 5 năm thâm niên công tác."
    )

    print("=== Demo Pipeline Làm Giàu Chunk ===\n")
    print(f"Văn bản gốc: {sample}\n")
    print(f"Tóm tắt: {summarize_chunk(sample)}\n")
    print(f"Câu hỏi HyQA: {generate_hypothesis_questions(sample)}\n")
    print(f"Ngữ cảnh: {contextual_prepend(sample, 'Sổ tay nhân viên')}\n")
    print(f"Metadata tự động: {extract_metadata(sample)}")
