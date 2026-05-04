# Individual Reflection — Lab 18

**Tên:** Trịnh Đức Anh  
**mã học viên** 2A202600499
**Module phụ trách:** m2 — Hybrid Search (BM25 + Dense + RRF)

---

## 1. Đóng góp kỹ thuật

- Module đã implement: **M2 — Hybrid Search**: truy hồi kết hợp lexical (BM25) và semantic (embedding + Qdrant), gộp xếp hạng bằng Reciprocal Rank Fusion (RRF); hỗ trợ tiếng Việt qua tách từ trước khi tokenize cho BM25.
- Các hàm/class chính đã viết: `SearchResult`, `segment_vietnamese`, `BM25Search`, `DenseSearch`, `reciprocal_rank_fusion`, `HybridSearch` (trong `src/m2_search.py`).
- Số tests pass: **5/5** (`tests/test_m2.py`: segment, BM25 search/relevance, RRF merge và `method="hybrid"`).

## 2. Kiến thức học được

- Khái niệm mới nhất: **RRF** để hợp nhất hai (hoặc nhiều) danh sách đã xếp hạng mà không cần chuẩn hóa điểm số giữa BM25 và cosine similarity; cách **BM25Okapi** hoạt động trên corpus đã tokenize; tích hợp **Qdrant** với vector cosine cùng `SentenceTransformer` (`BAAI/bge-m3`).
- Điều bất ngờ nhất: Chỉ cần **khóa gộp theo `text`** là đủ cho lab-scale, nhưng ở production cần id chunk ổn định nếu hai chunk trùng nội dung khác metadata — điều này ảnh hưởng cách thiết kế payload Qdrant sau này.
- Kết nối với bài giảng (slide nào): Phần **hybrid retrieval** / **sparse + dense** và **fusion of rankers** trong chương Production RAG (tương ứng nội dung về BM25 + dense vectors và các chiến lược merge rank).

## 3. Khó khăn & Cách giải quyết

- Khó khăn lớn nhất: BM25 trên tiếng Việt **không tách từ** thì token rất thô, dễ miss khớp truy vấn tự nhiên; đồng thời cần đảm bảo môi trường chạy được khi **chưa cài** `underthesea`.
- Cách giải quyết: Dùng `underthesea.word_tokenize(..., format="text")` rồi `.split()` cho cả document và query; bọc `try/except` và **fallback** trả về chuỗi gốc nếu thư viện lỗi hoặc chưa có. Kiểm thử với các truy vấn tiếng Việt có dấu trong `test_m2.py`.
- Thời gian debug: *(điền thực tế của bạn, ví dụ: ~2–4 giờ cho tích hợp Qdrant + chỉnh tokenize + chạy pytest)*

## 4. Nếu làm lại

- Sẽ làm khác điều gì: Gộp RRF theo **id chunk** (payload) thay vì chỉ `text`; có thể thêm tham số `k` RRF vào `config.py` để tune; viết test tích hợp nhỏ có Qdrant mock hoặc container để `DenseSearch` không chỉ phụ thuộc chạy thủ công.
- Module nào muốn thử tiếp: **M3 Reranking** (Cross-Encoder) để xem tác động end-to-end lên chất lượng top-k sau hybrid, hoặc **M4 Evaluation** để đo RAGAS trước/sau khi bật hybrid.

## 5. Tự đánh giá

| Tiêu chí | Tự chấm (1-5) |
|----------|---------------|
| Hiểu bài giảng | 4 |
| Code quality | 4 |
| Teamwork | 5 |
| Problem solving | 5 |

*(Điều chỉnh điểm tự chấm và mục 3 “Thời gian debug” cho sát thực tế làm bài của bạn.)*
