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
| Hoàng Quốc Chung | M5: Enrichment    | ✅          | 10/10     |

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
> M2 (hybrid search — Trịnh Đức Anh): kết hợp **BM25** (`rank_bm25.BM25Okapi`) và **dense retrieval** (Qdrant cosine + `SentenceTransformer` theo `EMBEDDING_MODEL`, mặc định `BAAI/bge-m3`). Truy vấn BM25 được **tách từ tiếng Việt** bằng `underthesea.word_tokenize` (nếu thư viện chưa có thì fallback giữ nguyên chuỗi). Hai danh sách xếp hạng được gộp bằng **RRF** (Reciprocal Rank Fusion, `k=60`), gom trùng theo nội dung `text`, điểm cuối là tổng RRF và `method="hybrid"`. `HybridSearch` index song song (BM25 in-memory + upsert Qdrant) và search lấy `BM25_TOP_K` / `DENSE_TOP_K` (mỗi nhánh 20) rồi trả `HYBRID_TOP_K` (20) sau fusion — so với naive baseline chỉ dense, pipeline production bổ sung lớp khớp từ khóa/lexical cho tiếng Việt.
>
> M3 (reranking — Bùi Văn Đạt): triển khai `CrossEncoderReranker` với `sentence_transformers.CrossEncoder`, model mặc định `BAAI/bge-reranker-v2-m3`, nhận ~top-20 đoạn từ hybrid search và trả về top-k (theo `config.RERANK_TOP_K`, thường 3) đã sắp xếp theo `rerank_score` giảm dần; mỗi kết quả có `original_score`, `metadata`, `rank`. Thêm `FlashrankReranker` (tùy chọn, `pip install flashrank`) làm lựa chọn rerank nhẹ trên CPU. Hàm `benchmark_reranker()` đo latency trung bình / min / max (ms) qua nhiều lần chạy để báo cáo và so sánh với yêu cầu lab (< 5s sau khi model đã load). **Liên hệ bài giảng:** đúng luồng slide *Reranking — Highest ROI Optimization* (retrieve nhanh → cross-encoder rerank → top-3 cho LLM; chọn `bge-reranker-v2-m3` cho tiếng Việt; Flashrank tương ứng tùy chọn siêu nhẹ trên slide).
2. **Biggest challenge:**
> (M3 / theo slide Reranking): cân bằng **độ trễ cross-encoder** (slide minh họa ~50 ms sau warm-up) với **chất lượng top-3** đưa vào LLM; lần đầu chạy còn phụ thuộc tải weight Hugging Face và CPU/GPU máy nhóm — cần cache model trước khi demo hoặc eval hàng loạt.
3. **Surprise finding:**
> (M3 / theo slide): reranking được định vị là **tối ưu ROI cao nhất** trong pipeline (overhead cỡ chục ms đổi lại +precision đáng kể); khi đo RAGAS, nhóm có thể quan sát **Context Precision** nhạy với bước rerank hơn một số metric khác nếu retrieval đã đủ recall nhưng thứ hạng chunk nhiễu.

## Presentation Notes (5 phút)

1. RAGAS scores (naive vs production):
2. Biggest win — module nào, tại sao:
3. Case study — 1 failure, Error Tree walkthrough:
4. Next optimization nếu có thêm 1 giờ:
