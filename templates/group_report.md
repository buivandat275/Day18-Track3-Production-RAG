# Group Report — Lab 18

**Nhóm:** [C401-A4]  
**Ngày:**

## Thành viên & Module

| Tên | Module | Hoàn thành | Tests pass |
|-----|--------|-----------|-----------|
|Nguyễn Minh Quân| M1: Chunking | ✅ | 13/13 |
| | M2: Search | ☐ | /5 |
| | M3: Rerank | ☐ | /5 |
| | M4: Eval | ☐ | /4 |

## Kết quả

| Metric | Naive | Production | Δ |
|--------|-------|-----------|---|
| Faithfulness | | | |
| Answer Relevancy | | | |
| Context Precision | | | |
| Context Recall | | | |

## Key Findings

1. **Biggest improvement:**
> M1:  đã implement 3 chiến lược chunking nâng cao: semantic chunking, hierarchical parent-child chunking và structure-aware chunking. Hierarchical chunking tạo parent chunks để giữ ngữ cảnh rộng và child chunks để retrieval chính xác hơn, mỗi child có `parent_id` trỏ về parent. Structure-aware chunking giữ nguyên markdown headers và lưu `section` trong metadata.
2. **Biggest challenge:**
3. **Surprise finding:**

## Presentation Notes

1. RAGAS scores (naive vs production):
2. Biggest win — module nào, tại sao:
3. Case study — 1 failure, Error Tree:
4. Next optimization nếu có thêm 1 giờ:
