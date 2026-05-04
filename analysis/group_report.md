# Group Report - Lab 18: Production RAG

**Nhóm:** C401 - A4
**Ngày:** 2026-05-04

## Thành viên & Phân công

| Tên | Module | Hoàn thành | Tests pass |
| --- | --- | --- | --- |
| Nguyễn Minh Quân | M1: Chunking | ✅ | 13/13 |
| Trịnh Đức Anh | M2: Hybrid Search | ✅ | 5/5 |
| Bùi Văn Đạt | M3: Reranking | ✅ | 5/5 |
| Nguyễn Minh Trí | M4: Evaluation | ✅ | 4/4 |
| Hoàng Quốc Chung | M5: Enrichment | ✅ | 10/10 |

## Kết quả RAGAS

Nguồn số liệu: `reports/naive_baseline_report.json` (naive) và `reports/ragas_report.json` (production), **20 câu**, `evaluation_mode: heuristic`.

| Metric | Naive | Production | Delta |
| --- | ---: | ---: | ---: |
| Faithfulness | 1.0000 | 0.7508 | -0.2492 |
| Answer Relevancy | 0.5699 | 0.2611 | -0.3089 |
| Context Precision | 0.3369 | 0.3877 | +0.0508 |
| Context Recall | 0.6705 | 0.6544 | -0.0162 |

Delta = Production − Naive. **Context Precision** tăng nhẹ khi dùng pipeline production (chunking nâng cao + hybrid + rerank + enrichment), nhưng các câu **ngoài corpus** trong `test_set.json` mở rộng làm **answer relevancy** và **faithfulness** aggregate giảm so với naive (naive vẫn trả lời dài từ context trộn nhiều section nên heuristic đôi khi “đủ điểm” hơn câu trả lời ngắn / “Không tìm thấy” của production).

## Key Findings

1. **Biggest improvement:**
> M1:  đã implement 3 chiến lược chunking nâng cao: semantic chunking, hierarchical parent-child chunking và structure-aware chunking. Hierarchical chunking tạo parent chunks để giữ ngữ cảnh rộng và child chunks để retrieval chính xác hơn, mỗi child có `parent_id` trỏ về parent. Structure-aware chunking giữ nguyên markdown headers và lưu `section` trong metadata.
>
> M2 (hybrid search — Trịnh Đức Anh): kết hợp **BM25** (`rank_bm25.BM25Okapi`) và **dense retrieval** (Qdrant cosine + `SentenceTransformer` theo `EMBEDDING_MODEL`, mặc định `BAAI/bge-m3`). Truy vấn BM25 được **tách từ tiếng Việt** bằng `underthesea.word_tokenize` (nếu thư viện chưa có thì fallback giữ nguyên chuỗi). Hai danh sách xếp hạng được gộp bằng **RRF** (Reciprocal Rank Fusion, `k=60`), gom trùng theo nội dung `text`, điểm cuối là tổng RRF và `method="hybrid"`. `HybridSearch` index song song (BM25 in-memory + upsert Qdrant) và search lấy `BM25_TOP_K` / `DENSE_TOP_K` (mỗi nhánh 20) rồi trả `HYBRID_TOP_K` (20) sau fusion — so với naive baseline chỉ dense, pipeline production bổ sung lớp khớp từ khóa/lexical cho tiếng Việt.
>
> M3 (reranking — Bùi Văn Đạt): triển khai `CrossEncoderReranker` với `sentence_transformers.CrossEncoder`, model mặc định `BAAI/bge-reranker-v2-m3`, nhận ~top-20 đoạn từ hybrid search và trả về top-k (theo `config.RERANK_TOP_K`, thường 3) đã sắp xếp theo `rerank_score` giảm dần; mỗi kết quả có `original_score`, `metadata`, `rank`. Thêm `FlashrankReranker` (tùy chọn, `pip install flashrank`) làm lựa chọn rerank nhẹ trên CPU. Hàm `benchmark_reranker()` đo latency trung bình / min / max (ms) qua nhiều lần chạy để báo cáo và so sánh với yêu cầu lab (< 5s sau khi model đã load).
>
> M4 (evaluation — Nguyễn Minh Trí): triển khai đánh giá bằng **RAGAS**, đánh giá 4 metrics: faithfulness, answer_relevancy, context_precision, context_recall. Sử dụng `ChatOpenAI` làm LLM đánh giá (gpt-4o-mini), kết quả trả về dưới dạng `EvalResult`, có thể convert sang pandas để xử lý. Sử dụng `ragas.evaluate` để đánh giá toàn bộ dataset, kết quả trả về `Dataset` chứa các metrics. Phân tích lỗi bằng `failure_analysis` để tìm ra các câu trả lời kém chất lượng và đưa ra đề xuất cải thiện.
> 
2. **Biggest challenge:**
3. **Surprise finding:**

## Presentation Notes (5 phút)

1. RAGAS scores (naive vs production):
2. Biggest win — module nào, tại sao:
3. Case study — 1 failure, Error Tree walkthrough:
4. Next optimization nếu có thêm 1 giờ:
