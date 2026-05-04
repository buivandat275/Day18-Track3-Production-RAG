# Individual Reflection — Lab 18

**Tên:** [Nguyễn Minh Quân]  
**Module phụ trách:** [M1]

---

## 1. Đóng góp kỹ thuật

- Module đã implement: Module 1 - Xử lý, làm sạch và áp dụng các chiến lược phân mảnh dữ liệu (Basic, Semantic, Hierarchical, Structure-Aware) cho hệ thống Production RAG.
- Các hàm/class chính đã viết:
>load_documents(): Quản lý đọc file đa định dạng.
> _extract_pdf_text() (và các hàm con _extract_pdf_with_...): Cơ chế đọc PDF với Fallback.
> Các hàm logic: chunk_semantic(), chunk_hierarchical(), chunk_structure_aware().
> compare_strategies(): Hàm chạy A/B Testing để thống kê hiệu năng cắt.
- Số tests pass: 13 / 13

## 2. Kiến thức học được

- Khái niệm mới nhất: Hierarchical Chunking (tách chunk cha/con và dùng parent_id để LLM có ngữ cảnh rộng hơn khi trả lời) và Semantic Chunking (dùng Cosine Similarity để nhóm các câu cùng ngữ nghĩa).

- Điều bất ngờ nhất: Việc đọc dữ liệu PDF trong thực tế phức tạp và dễ lỗi mội trường hơn lý thuyết rất nhiều (đặc biệt là sự đụng độ của các thư viện như fitz hay pdfplumber). Code trong Production bắt buộc phải có cơ chế Fallback (try... except).

- Kết nối với bài giảng (slide nào): Fix OFFLINE — Ingestion Pipeline và Enrichment Pipeline(slide 7 -14 )

## 3. Khó khăn & Cách giải quyết

- Khó khăn lớn nhất: Lỗi đụng độ môi trường khi cài đặt các thư viện đọc PDF, cụ thể là lỗi "ModuleNotFoundError" do nhầm lẫn giữa tên import (fitz) và tên gói cài đặt (PyMuPDF), cùng với các lỗi liên quan đến backend C++ của thư viện.

- Cách giải quyết: Gỡ cài đặt gói sai (pip uninstall fitz), cài lại đúng tên thư viện. Trong lúc debug, tạm thời điều hướng mã nguồn sử dụng thư viện pypdf làm mặc định để hệ thống vẫn chạy được, không làm chậm tiến độ nhận dữ liệu của Thành viên 2 (người làm Hybrid Search).

- Thời gian debug: Khoảng 1 - 2 giờ để tìm hiểu ngọn ngành lỗi thư viện và ổn định lại môi trường.

## 4. Nếu làm lại

- Sẽ làm khác điều gì: Tích hợp thêm công nghệ OCR (như pytesseract hoặc easyocr) vào một hàm _extract_pdf_with_ocr() để giải quyết triệt để trường hợp đầu vào là tài liệu PDF dạng ảnh (Scanned PDF).

- Module nào muốn thử tiếp: Module 2 (Hybrid Search) hoặc Module 3 (Reranking).

## 5. Tự đánh giá

| Tiêu chí | Tự chấm (1-5) |
|----------|---------------|
| Hiểu bài giảng | 5 |
| Code quality | 4 |
| Teamwork | 5 |
| Problem solving | 4 |
