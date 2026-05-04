# Individual Reflection - Lab 18

**Tên:** Hoàng Quốc Chung  
**Module phụ trách:** M5 - Enrichment Pipeline

---

## 1. Đóng góp kỹ thuật

- Module đã implement: **M5 - Enrichment Pipeline**, làm giàu chunk trước khi embedding để tăng chất lượng retrieval.
- Các kỹ thuật chính đã hoàn thiện:
  - `summarize_chunk()`: tạo tóm tắt ngắn cho chunk, có fallback extractive khi không gọi được LLM.
  - `generate_hypothesis_questions()`: sinh câu hỏi giả định mà chunk có thể trả lời, giúp bridge vocabulary gap giữa câu hỏi người dùng và nội dung tài liệu.
  - `contextual_prepend()`: thêm một câu ngữ cảnh vào trước chunk để retrieval hiểu chunk thuộc tài liệu/chủ đề nào.
  - `extract_metadata()`: trích xuất metadata như `topic`, `entities`, `category`, `language`.
  - `enrich_chunks()`: ghép toàn bộ các kỹ thuật trên thành pipeline trả về `EnrichedChunk`.
- Số tests pass: **10/10** với `tests/test_m5.py`.

## 2. Kiến thức học được

- Enrichment là bước chạy offline trước indexing, nhưng có tác động lên mọi query sau đó.
- Contextual prepend giúp chunk nhỏ không bị mất ngữ cảnh khi được đưa vào vector DB hoặc BM25.
- HyQA hữu ích khi người dùng hỏi bằng cách diễn đạt khác với tài liệu gốc. Ví dụ tài liệu ghi "12 ngày làm việc mỗi năm", còn người dùng hỏi "nghỉ phép bao nhiêu ngày".
- Metadata tự động giúp pipeline có thể filter hoặc rerank tốt hơn theo chủ đề, loại tài liệu và thực thể.

## 3. Khó khăn & Cách giải quyết

- Khó khăn lớn nhất: M5 có thể phụ thuộc OpenAI API, nhưng môi trường lab không phải lúc nào cũng có mạng/API ổn định.
- Cách giải quyết: Thiết kế tất cả hàm theo hướng **best-effort LLM + deterministic fallback**. Nếu có API thì dùng `gpt-4o-mini`; nếu lỗi import, lỗi mạng hoặc thiếu key thì vẫn trả kết quả hợp lệ bằng rule-based fallback.
- Một điểm cần chú ý khác là tiếng Việt phải có dấu đầy đủ ở output. Em đã đảm bảo các câu hỏi HyQA, contextual prepend, metadata topic/entities và demo đều dùng tiếng Việt có dấu.

## 4. Nếu làm lại

- Em sẽ thêm cache cho enrichment để không gọi lại LLM nhiều lần trên cùng một chunk.
- Em sẽ mở rộng metadata extraction để nhận diện thêm loại tài liệu như pháp lý, tài chính, nhân sự và bảo mật.
- Em muốn thử tích hợp metadata từ M5 vào M2/M3 để filter hoặc boost kết quả trước reranking.

## 5. Tự đánh giá

| Tiêu chí | Tự chấm (1-5) |
| --- | ---: |
| Hiểu bài giảng | 4 |
| Code quality | 4 |
| Teamwork | 5 |
| Problem solving | 5 |

