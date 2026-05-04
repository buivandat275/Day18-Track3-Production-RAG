# Individual Reflection — Lab 18

**Tên:** Nguyễn Minh Trí  
**Module phụ trách:** M4 (Evaluation)

---

## 1. Đóng góp kỹ thuật

- Module đã implement: Module 4 (Evaluation) - RAGAS Pipeline & Failure Analysis.
- Các hàm/class chính đã viết: `evaluate_ragas`, `failure_analysis`, `EvalResult`.
- Số tests pass: 4/4 (`test_load_test_set`, `test_evaluate_returns_metrics`, `test_failure_analysis_returns`, `test_failure_has_diagnosis`).

## 2. Kiến thức học được

- Khái niệm mới nhất: Cách thức hoạt động của các metrics RAGAS (Faithfulness, Answer Relevancy, Context Precision, Context Recall) và cách sử dụng LLM làm "Judge" để đánh giá chất lượng câu trả lời.
- Điều bất ngờ nhất: RAGAS yêu cầu môi trường rất khắt khe về phiên bản (dependency) và có thể trả về giá trị `None` hoặc `NaN` nếu đánh giá thất bại, đòi hỏi code phải có cơ chế xử lý lỗi (hardening) cực tốt để không làm crash pipeline.
- Kết nối với bài giảng (slide nào): Slide về "Evaluation & Failure Analysis" - áp dụng Error Tree để chẩn đoán lỗi từ RAGAS scores.

## 3. Khó khăn & Cách giải quyết

- Khó khăn lớn nhất: Lỗi môi trường trên Windows (thiếu C++ Build Tools cho `greenlet`) và lỗi tương thích cú pháp Python 3.10 (`|` union type) trên môi trường Python 3.9 của lab.
- Cách giải quyết: Sử dụng `pip install --only-binary=:all:` để bỏ qua việc build source và cài đặt `eval_type_backport` để hỗ trợ cú pháp mới trên Python cũ. Gia cố code với `try-except` và `.get()` để xử lý các kết quả evaluation bị lỗi từ API.
- Thời gian debug: Khoảng 45 phút cho riêng phần môi trường và dependency.

## 4. Nếu làm lại

- Sẽ làm khác điều gì: Sẽ kiểm tra kỹ danh sách dependency (`requirements.txt`) và chuẩn bị môi trường Docker ổn định hơn ngay từ đầu để tránh mất thời gian build source.
- Module nào muốn thử tiếp: Module 5 (Enrichment) vì nó giúp cải thiện trực tiếp chất lượng dữ liệu đầu vào, từ đó nâng cao mọi metrics ở Module 4.

## 5. Tự đánh giá

| Tiêu chí | Tự chấm (1-5) |
|----------|---------------|
| Hiểu bài giảng | 5 |
| Code quality | 5 |
| Teamwork | 4 |
| Problem solving | 5 |

