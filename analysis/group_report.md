# Group Report — Lab 18: Production RAG

**Nhóm:** [Tên]  
**Ngày:**

## Thành viên & Phân công

| Tên              | Module            | Hoàn thành | Tests pass |
| ---------------- | ----------------- | ---------- | ---------- |
| Nguyễn Minh Quân | M1: Chunking      | ✅          | 13/13      |
| Trịnh Đức Anh    | M2: Hybrid Search | ✅          | 5/5        |
| Bùi Văn Đạt      | M3: Reranking     | ✅          | 5/5        |
|                  | M4: Evaluation    | ☐          | /4         |

## Kết quả RAGAS

| Metric            | Naive | Production | Δ   |
| ----------------- | ----- | ---------- | --- |
| Faithfulness      |       |            |     |
| Answer Relevancy  |       |            |     |
| Context Precision |       |            |     |
| Context Recall    |       |            |     |

## Key Findings

1. **Biggest improvement:**
> M1:  đã implement 3 chiến lược chunking nâng cao: semantic chunking, hierarchical parent-child chunking và structure-aware chunking. Hierarchical chunking tạo parent chunks để giữ ngữ cảnh rộng và child chunks để retrieval chính xác hơn, mỗi child có `parent_id` trỏ về parent. Structure-aware chunking giữ nguyên markdown headers và lưu `section` trong metadata.
>
> M3 (reranking — Bùi Văn Đạt): triển khai `CrossEncoderReranker` với `sentence_transformers.CrossEncoder`, model mặc định `BAAI/bge-reranker-v2-m3`, nhận ~top-20 đoạn từ hybrid search và trả về top-k (theo `config.RERANK_TOP_K`, thường 3) đã sắp xếp theo `rerank_score` giảm dần; mỗi kết quả có `original_score`, `metadata`, `rank`. Thêm `FlashrankReranker` (tùy chọn, `pip install flashrank`) làm lựa chọn rerank nhẹ trên CPU. Hàm `benchmark_reranker()` đo latency trung bình / min / max (ms) qua nhiều lần chạy để báo cáo và so sánh với yêu cầu lab (< 5s sau khi model đã load).
2. **Biggest challenge:**
3. **Surprise finding:**

## Presentation Notes (5 phút)

1. RAGAS scores (naive vs production):
2. Biggest win — module nào, tại sao:
3. Case study — 1 failure, Error Tree walkthrough:
4. Next optimization nếu có thêm 1 giờ:
