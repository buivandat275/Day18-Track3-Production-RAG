"""
Module 1: Advanced Chunking Strategies
======================================
Implement semantic, hierarchical, and structure-aware chunking.
Compare them with the basic paragraph chunking baseline.

Test: pytest tests/test_m1.py
"""

import glob
import math
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    DATA_DIR,
    HIERARCHICAL_CHILD_SIZE,
    HIERARCHICAL_PARENT_SIZE,
    SEMANTIC_THRESHOLD,
)


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    parent_id: str | None = None


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """Load markdown, text, and extractable PDF files from data/."""
    docs = []
    for pattern in ("*.md", "*.txt"):
        for fp in sorted(glob.glob(os.path.join(data_dir, pattern))):
            with open(fp, encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                docs.append({"text": text, "metadata": {"source": os.path.basename(fp)}})

    for fp in sorted(glob.glob(os.path.join(data_dir, "*.pdf"))):
        text = _extract_pdf_text(fp)
        if text:
            docs.append({"text": text, "metadata": {"source": os.path.basename(fp)}})
    return docs


def _extract_pdf_text(path: str) -> str:
    """Try several optional PDF text extractors; return empty for scanned PDFs."""
    for extractor in (
        _extract_pdf_with_pypdf,
        _extract_pdf_with_pdfplumber,
        _extract_pdf_with_pymupdf,
    ):
        text = extractor(path)
        if text:
            return text
    return ""


def _extract_pdf_with_pypdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return ""
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _extract_pdf_with_pdfplumber(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        return ""
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _extract_pdf_with_pymupdf(path: str) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    try:
        with fitz.open(path) as doc:
            pages = [page.get_text("text") or "" for page in doc]
    except Exception:
        return ""
    return "\n\n".join(page.strip() for page in pages if page.strip())


# Baseline: Basic Chunking


def chunk_basic(text: str, chunk_size: int = 500, metadata: dict | None = None) -> list[Chunk]:
    """
    Basic chunking: split by paragraph.
    This is the baseline used for comparison.
    """
    metadata = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(Chunk(text=current.strip(), metadata={**metadata, "chunk_index": len(chunks)}))
    return chunks


# Strategy 1: Semantic Chunking


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _token_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in re.findall(r"\w+", text.lower(), flags=re.UNICODE):
        counts[token] = counts.get(token, 0) + 1
    return counts


def _cosine_similarity(left: str, right: str) -> float:
    left_counts = _token_counts(left)
    right_counts = _token_counts(right)
    if not left_counts or not right_counts:
        return 0.0

    common = set(left_counts) & set(right_counts)
    dot = sum(left_counts[token] * right_counts[token] for token in common)
    left_norm = math.sqrt(sum(count * count for count in left_counts.values()))
    right_norm = math.sqrt(sum(count * count for count in right_counts.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _chunk_stats(chunks: list[Chunk]) -> dict:
    lengths = [len(c.text) for c in chunks]
    return {
        "num_chunks": len(chunks),
        "avg_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
    }


def chunk_semantic(
    text: str,
    threshold: float = SEMANTIC_THRESHOLD,
    metadata: dict | None = None,
) -> list[Chunk]:
    """
    Group nearby sentences by cosine similarity.

    Topic 1: semantic chunking
    - Split text into sentences.
    - Compare consecutive sentence vectors with cosine similarity.
    - Start a new chunk when similarity falls below the threshold.
    """
    metadata = metadata or {}
    # Topic 1: Semantic chunking
    # - Split text into sentences.
    # - Compare consecutive sentence vectors with cosine similarity.
    # - Start a new chunk when similarity falls below the threshold.
    if not text.strip():
        return []

    sections = chunk_structure_aware(text, metadata)
    if len(sections) > 1:
        return [
            Chunk(
                text=section.text,
                metadata={
                    **section.metadata,
                    "chunk_index": i,
                    "strategy": "semantic",
                    "semantic_method": "section_fallback",
                },
            )
            for i, section in enumerate(sections)
        ]

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_group = [sentences[0]]
    for sentence in sentences[1:]:
        sim = _cosine_similarity(current_group[-1], sentence)
        if sim < threshold and current_group:
            chunks.append(Chunk(
                text=" ".join(current_group).strip(),
                metadata={
                    **metadata,
                    "chunk_index": len(chunks),
                    "strategy": "semantic",
                    "semantic_method": "token_cosine",
                },
            ))
            current_group = []
        current_group.append(sentence)

    if current_group:
        chunks.append(Chunk(
            text=" ".join(current_group).strip(),
            metadata={
                **metadata,
                "chunk_index": len(chunks),
                "strategy": "semantic",
                "semantic_method": "token_cosine",
            },
        ))
    return chunks


# Strategy 2: Hierarchical Chunking


def chunk_hierarchical(
    text: str,
    parent_size: int = HIERARCHICAL_PARENT_SIZE,
    child_size: int = HIERARCHICAL_CHILD_SIZE,
    metadata: dict | None = None,
) -> tuple[list[Chunk], list[Chunk]]:
    """
    Build parent chunks and smaller child chunks linked by parent_id.

    Topic 2: hierarchical chunking
    - Group paragraphs into parent chunks up to parent_size.
    - Split each parent into child chunks up to child_size.
    - Index children, then use parent_id to recover wider context.
    """
    metadata = metadata or {}
    # Topic 2: Hierarchical chunking
    # - Group paragraphs into parent chunks up to parent_size.
    # - Split each parent into child chunks up to child_size.
    # - Store parent_id on every child chunk.
    if not text.strip():
        return [], []

    parents: list[Chunk] = []
    children: list[Chunk] = []
    paragraphs = _split_paragraphs(text) or [text.strip()]
    current: list[str] = []
    current_len = 0

    def flush_parent() -> None:
        if not current:
            return
        parent_text = "\n\n".join(current).strip()
        parent_index = len(parents)
        parent_id = f"{metadata.get('source', 'doc')}_parent_{parent_index}"
        parents.append(Chunk(
            text=parent_text,
            metadata={
                **metadata,
                "chunk_index": parent_index,
                "chunk_type": "parent",
                "parent_id": parent_id,
                "strategy": "hierarchical",
            },
        ))

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len + 2 > parent_size:
            flush_parent()
            current = []
            current_len = 0

        if para_len > parent_size:
            for start in range(0, para_len, parent_size):
                piece = para[start:start + parent_size].strip()
                if piece:
                    current.append(piece)
                    current_len += len(piece)
                    flush_parent()
                    current = []
                    current_len = 0
            continue

        current.append(para)
        current_len += para_len + 2

    flush_parent()

    for parent in parents:
        parent_id = parent.metadata["parent_id"]
        words = parent.text.split()
        if not words:
            continue

        child_parts: list[str] = []
        current_child: list[str] = []
        current_len = 0
        for word in words:
            next_len = len(word) + (1 if current_child else 0)
            if current_child and current_len + next_len > child_size:
                child_parts.append(" ".join(current_child))
                current_child = []
                current_len = 0
            current_child.append(word)
            current_len += next_len
        if current_child:
            child_parts.append(" ".join(current_child))

        for child_text in child_parts:
            children.append(Chunk(
                text=child_text,
                metadata={
                    **metadata,
                    "chunk_index": len(children),
                    "chunk_type": "child",
                    "parent_id": parent_id,
                    "strategy": "hierarchical",
                },
                parent_id=parent_id,
            ))

    return parents, children


# Strategy 3: Structure-Aware Chunking


def chunk_structure_aware(text: str, metadata: dict | None = None) -> list[Chunk]:
    """
    Split markdown by headers while preserving the header with its section.

    Topic 3: structure-aware chunking
    - Detect markdown headers with regex.
    - Pair each header with its following content.
    - Store the current section in metadata.
    """
    metadata = metadata or {}
    # Topic 3: Structure-aware chunking
    # - Detect markdown headers with regex.
    # - Pair each header with its following content.
    # - Store the current section in metadata.
    if not text.strip():
        return []

    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", flags=re.MULTILINE)
    matches = list(header_pattern.finditer(text))
    if not matches:
        return [
            Chunk(
                text=text.strip(),
                metadata={**metadata, "chunk_index": 0, "section": "", "strategy": "structure"},
            )
        ]

    chunks: list[Chunk] = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        chunks.append(Chunk(
            text=preamble,
            metadata={**metadata, "chunk_index": len(chunks), "section": "", "strategy": "structure"},
        ))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue
        header = match.group(0).strip()
        chunks.append(Chunk(
            text=section_text,
            metadata={
                **metadata,
                "chunk_index": len(chunks),
                "section": header,
                "header_level": len(match.group(1)),
                "strategy": "structure",
            },
        ))

    return chunks


# A/B Test: Compare All Strategies


def compare_strategies(documents: list[dict]) -> dict:
    """
    Run all strategies on documents and return summary statistics.

    Topic 4: compare strategies
    - Run basic, semantic, hierarchical, and structure-aware chunking.
    - Collect num_chunks, avg_length, min_length, and max_length.
    - Print a compact comparison table.
    """
    # Topic 4: Compare all chunking strategies
    # - Run basic, semantic, hierarchical, and structure-aware chunking.
    # - Collect num_chunks, avg_length, min_length, and max_length.
    # - Print a compact comparison table for A/B comparison.
    all_basic: list[Chunk] = []
    all_semantic: list[Chunk] = []
    all_parents: list[Chunk] = []
    all_children: list[Chunk] = []
    all_structure: list[Chunk] = []

    for doc_index, doc in enumerate(documents):
        doc_metadata = {**doc.get("metadata", {}), "doc_index": doc_index}
        text = doc.get("text", "")
        all_basic.extend(chunk_basic(text, metadata=doc_metadata))
        all_semantic.extend(chunk_semantic(text, metadata=doc_metadata))
        parents, children = chunk_hierarchical(text, metadata=doc_metadata)
        all_parents.extend(parents)
        all_children.extend(children)
        all_structure.extend(chunk_structure_aware(text, metadata=doc_metadata))

    results = {
        "basic": _chunk_stats(all_basic),
        "semantic": _chunk_stats(all_semantic),
        "hierarchical": {
            **_chunk_stats(all_children),
            "num_parent_chunks": len(all_parents),
            "num_child_chunks": len(all_children),
            "avg_parent_length": round(
                sum(len(c.text) for c in all_parents) / len(all_parents), 2
            ) if all_parents else 0,
        },
        "structure": _chunk_stats(all_structure),
    }

    print(f"{'Strategy':<14} | {'Chunks':>10} | {'Avg Len':>8} | {'Min':>5} | {'Max':>5}")
    print("-" * 55)
    for name in ("basic", "semantic", "hierarchical", "structure"):
        stats = results[name]
        chunk_label = (
            f"{stats['num_parent_chunks']}p/{stats['num_child_chunks']}c"
            if name == "hierarchical"
            else str(stats["num_chunks"])
        )
        print(
            f"{name:<14} | {chunk_label:>10} | "
            f"{stats['avg_length']:>8} | {stats['min_length']:>5} | {stats['max_length']:>5}"
        )

    return results


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")
    results = compare_strategies(docs)
    for name, stats in results.items():
        print(f"  {name}: {stats}")
