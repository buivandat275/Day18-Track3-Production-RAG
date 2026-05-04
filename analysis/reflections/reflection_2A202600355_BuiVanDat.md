# Individual Reflection — Lab 18

**Tên:** Bùi Văn Đạt  
**Mã học viên:** 2A202600355  
**Module phụ trách:** M3 — Reranking  

---

## 1. Đóng góp kỹ thuật

- Module đã implement: **Module 3** — rerank danh sách đoạn sau hybrid retrieval (top-k rút gọn, ví dụ 20 → 3) bằng cross-encoder, kèm benchmark độ trễ và lựa chọn reranker nhẹ tùy chọn.
- Các hàm/class chính đã viết:
  - `RerankResult` (dataclass): `text`, `original_score`, `rerank_score`, `metadata`, `rank`.
  - `CrossEncoderReranker`: `_load_model()` lazy-load `sentence_transformers.CrossEncoder` với `BAAI/bge-reranker-v2-m3`; `rerank(query, documents, top_k)` ghép cặp query–passage, `predict` điểm, sắp xếp giảm dần, trả về top-k.
  - `FlashrankReranker` (tùy chọn): dùng `flashrank.Ranker` + `RerankRequest` khi đã cài `flashrank`; không có package thì `rerank` trả về rỗng để không chặn pipeline.
  - `benchmark_reranker()`: lặp `n_runs`, đo `time.perf_counter()`, trả về `avg_ms` / `min_ms` / `max_ms`.
- Số tests pass: **5 / 5** (`pytest tests/test_m3.py`).

---

## 2. Kiến thức học được

- Khái niệm mới / đi sâu hơn: **cross-encoder reranking** — cùng lúc mã hóa cặp (query, passage) để cho điểm liên quan, khác **bi-encoder** (embed query và doc **tách riêng**, rất nhanh ~1 ms nhưng không tương tác trực tiếp giữa hai phía khi encode). Slide nhấn mạnh pipeline hai tầng: **retrieve top-20 (nhanh)** → **cross-encoder rerank (~50 ms, cộng thêm khoảng +15–25% precision)** → **chỉ top-3 vào LLM** — đúng với lab (hybrid trả ~20, `RERANK_TOP_K` = 3).
- Điều bất ngờ nhất: slide gọi rerank là **“Highest ROI optimization”** — overhead chỉ cỡ **30–50 ms** nhưng đổi lại cải thiện precision đáng kể; thực tế triển khai, phần “đau” nhất lần đầu là **tải model** từ Hugging Face + chạy trên CPU, chứ sau khi cache ổn thì pattern top-20 → rerank → top-3 khớp hoàn toàn lý thuyết trên lớp.
- **Kết nối với bài giảng:** Nội dung **“Reranking — Highest ROI Optimization”** (phần **Enrichment Pipeline** trong lộ trình RAG của thầy Trần Minh Tú — AICB). Slide mô tả công thức **Retrieve top-20 → Rerank → Keep top-3 → LLM generate**, so sánh bi-encoder vs cross-encoder, và bảng chọn model: em áp dụng **`bge-reranker-v2-m3`** vì slide ghi **miễn phí, đa ngôn ngữ, tiếng Việt tốt** — khớp với corpus/policy tiếng Việt của lab; **`Flashrank`** trong code tương ứng dòng **Ultra-light, dưới ~5 ms** trên slide (lựa chọn thay thế khi cần latency cực thấp, không bắt buộc). Các hướng **Cohere / Jina (API)** hay **LLM-as-reranker** slide chỉ là tham chiếu production/em chi phí — em chưa tích hợp nhưng hiểu vị trí của chúng so với rerank cục bộ.

---

## 3. Khó khăn & Cách giải quyết

- Khó khăn lớn nhất: chờ **tải model** và chạy cross-encoder trên **CPU** trong môi trường Windows (cảnh báo symlink cache Hugging Face, tốc độ mạng, lần đầu `pytest` có vẻ “treo” nhưng thực chất đang load model).
- Cách giải quyết: chạy một lần `rerank` hoặc `pytest` khi mạng ổn để cache model; giữ `show_progress_bar=False` trong predict để log gọn; đồng bộ format `documents` với `pipeline.py` (`text`, `score`, `metadata`) để không lỗi runtime khi ghép nhóm.
- Thời gian / công sức: phần lớn dành cho **môi trường + lần đầu tải model**; logic rerank và benchmark sau khi model sẵn sàng thì ổn định.

---

## 4. Nếu làm lại

- Sẽ làm khác điều gì: thử **batch predict** hoặc giới hạn độ dài passage trước rerank để tiệm cận mức **~50 ms** slide minh họa (khi có GPU / cấu hình tối ưu); ghi rõ trong README nhóm: lần đầu cần chờ tải **`bge-reranker-v2-m3`**. Nếu triển khai thật theo slide “Production default”, có thể thử nhánh **API rerank** (Cohere / Jina) để đổi chi phí dollar lấy ổn định latency và bớt phụ thuộc máy local.
- Module nào muốn thử tiếp: **M2 (Hybrid Search)** để khớp trọn tầng retrieve top-20 với slide, hoặc **M4 (RAGAS)** để đo rerank có đẩy **Context Precision** (gần với “+precision” slide nói tới) trên tập 20 câu.

---

## 5. Tự đánh giá

| Tiêu chí | Tự chấm (1–5) |
|----------|----------------|
| Hiểu bài giảng | 3 |
| Code quality | 5 |
| Teamwork | 4 |
| Problem solving | 4 |
