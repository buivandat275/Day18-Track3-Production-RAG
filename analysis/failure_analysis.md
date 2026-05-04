# Failure Analysis - Lab 18: Production RAG

**Nhóm:** C401 - A4
**Thành viên:** [Nguyễn Minh Quân → M1] · [Trịnh Đức Anh → M2] · [Bùi Văn Đạt → M3] · [Nguyễn Minh Trí → M4] · [Hoàng Quốc Chung → M5]
**Đánh giá:** 5 câu hỏi trong `test_set.json`
**Chế độ chạy:** heuristic fallback vì môi trường hiện tại không truy cập được OpenAI/HuggingFace và Qdrant dense không sẵn sàng.

## RAGAS Scores

| Metric | Naive Baseline | Production | Delta |
| --- | ---: | ---: | ---: |
| Faithfulness | 1.0000 | 1.0000 | +0.0000 |
| Answer Relevancy | 0.9766 | 0.9118 | -0.0648 |
| Context Precision | 0.5103 | 0.5936 | +0.0834 |
| Context Recall | 1.0000 | 1.0000 | +0.0000 |

## Bottom-5 Failures

### #1

- **Question:** Mật khẩu tài khoản công ty phải thay đổi sau bao nhiêu ngày?
- **Expected:** Mật khẩu tài khoản công ty phải được thay đổi định kỳ mỗi 90 ngày.
- **Worst metric:** context_precision = 0.6042
- **Error Tree:** Output gần đúng -> Context có chứa đáp án -> Context còn nhiễu
- **Root cause:** Chunk liên quan đến mật khẩu bị ghép với nội dung thử việc/VPN do child chunk cắt theo kích thước ký tự.
- **Suggested fix:** Cải thiện structure-aware chunking cho markdown section hoặc thêm metadata filter theo topic.

### #2

- **Question:** Thời gian thử việc tiêu chuẩn là bao lâu?
- **Expected:** Thời gian thử việc tiêu chuẩn là 60 ngày.
- **Worst metric:** context_precision = 0.4815
- **Error Tree:** Output đúng -> Context có đáp án -> Context còn nhiễu
- **Root cause:** Top context có cả nghỉ phép và mật khẩu vì BM25 fallback hoạt động lexical, chưa có dense/Qdrant.
- **Suggested fix:** Chạy Qdrant + dense embedding thật, hoặc rerank theo section metadata trước khi đưa vào LLM.

### #3

- **Question:** Dữ liệu cá nhân được thu thập và xử lý cho mục đích như thế nào?
- **Expected:** Dữ liệu cá nhân chỉ được thu thập và xử lý cho mục đích hợp pháp, rõ ràng và đã được thông báo cho chủ thể dữ liệu.
- **Worst metric:** context_precision = 0.4912
- **Error Tree:** Output đúng -> Context có đáp án -> Context còn nhiễu
- **Root cause:** Context trả về thêm phần nghỉ phép/mật khẩu, làm precision thấp dù recall đạt 1.0.
- **Suggested fix:** Ưu tiên section "Bảo vệ dữ liệu cá nhân" bằng metadata `topic`/`category`.

### #4

- **Question:** Khi làm việc từ xa, nhân viên phải dùng gì để truy cập hệ thống nội bộ?
- **Expected:** Nhân viên làm việc từ xa phải sử dụng VPN của công ty khi truy cập hệ thống nội bộ.
- **Worst metric:** context_precision = 0.5965
- **Error Tree:** Output đúng -> Context có đáp án -> Context còn nhiễu
- **Root cause:** Chunk VPN nằm gần chunk mật khẩu nên retrieval đưa cả hai nội dung.
- **Suggested fix:** Giảm child size hoặc chunk theo header để tách "Chính sách mật khẩu" và "Truy cập VPN".

### #5

- **Question:** Nhân viên chính thức được nghỉ phép năm bao nhiêu ngày?
- **Expected:** Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm.
- **Worst metric:** context_precision = 0.7949
- **Error Tree:** Output đúng -> Context đúng -> Không có lỗi nghiêm trọng
- **Root cause:** Context hơi dài nhưng vẫn chứa đúng section nghỉ phép.
- **Suggested fix:** Theo dõi thêm trên test set lớn hơn; có thể giảm top-k context khi LLM generate.

## Case Study

**Question chọn phân tích:** Thời gian thử việc tiêu chuẩn là bao lâu?

**Error Tree walkthrough:**

1. Output đúng: pipeline trả lời được "60 ngày".
2. Context đúng: có chunk chứa quy định thử việc.
3. Query rewrite/enrichment hỗ trợ match tốt hơn, nhưng context vẫn nhiễu vì dense search và cross-encoder không chạy trong môi trường hiện tại.
4. Fix ưu tiên: bật Qdrant + embedding model, sau đó dùng reranker thật để lọc top-3 gọn hơn.

**Nếu có thêm 1 giờ, sẽ optimize:**

- Chạy Qdrant thật và cache model `BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3`.
- Chunk theo markdown header thay vì cắt child thuần theo độ dài.
- Dùng metadata `topic` từ M5 để filter trước rerank.
