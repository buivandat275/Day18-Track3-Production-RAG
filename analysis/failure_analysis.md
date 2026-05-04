# Failure Analysis - Lab 18: Production RAG

**Nhóm:** C401 - A4  
**Thành viên:** [Nguyễn Minh Quân → M1] · [Trịnh Đức Anh → M2] · [Bùi Văn Đạt → M3] · [Nguyễn Minh Trí → M4] · [Hoàng Quốc Chung → M5]  
**Đánh giá:** 20 câu hỏi trong `test_set.json` (aggregate lấy từ `reports/naive_baseline_report.json` và `reports/ragas_report.json`).  
**Chế độ chạy:** `evaluation_mode: heuristic` (RAGAS heuristic fallback theo report đã generate).

## RAGAS Scores

| Metric | Naive Baseline | Production | Delta |
| --- | ---: | ---: | ---: |
| Faithfulness | 1.0000 | 0.7508 | -0.2492 |
| Answer Relevancy | 0.5699 | 0.2611 | -0.3089 |
| Context Precision | 0.3369 | 0.3877 | +0.0508 |
| Context Recall | 0.6705 | 0.6544 | -0.0162 |

Delta = Production − Naive. Production **cao hơn** naive ở **Context Precision** (+0.05) nhưng **thấp hơn** ở faithfulness, answer relevancy và context recall trên cùng bộ 20 câu — phản ánh nhiều câu hỏi mở rộng **không có** trong corpus đã index, khiến pipeline trả *"Không tìm thấy"* hoặc câu trả lời ngắn không khớp embedding judge.

## Bottom-5 Failures

(Chọn theo tổng `answer_relevancy + faithfulness` thấp nhất trong `reports/ragas_report.json`.)

### #1

- **Question:** Khi nghe chuông báo cháy tòa nhà, nhân viên phải làm gì?
- **Expected:** Khi có báo cháy, nhân viên cần sơ tán ngay lập tức bằng thang bộ và tập trung tại điểm tập kết (Assembly Point) ở tầng trệt, tuyệt đối không dùng thang máy.
- **Actual (rút gọn):** Không tìm thấy thông tin.
- **Scores:** faithfulness ≈ 0.60 · answer_relevancy ≈ 0.02 · context_precision ≈ 0.22 · context_recall ≈ 0.38
- **Error Tree:** Corpus gap → retrieval không đưa được đoạn chứa quy trình PCCC → generator abstain.
- **Root cause:** Nội dung **báo cháy / sơ tán** không có (hoặc gần như không có) trong tài liệu `sample_policy.md` đã chunk; test set mở rộng vượt coverage.
- **Suggested fix:** Bổ sung handbook an toàn / FAQ nội bộ vào corpus hoặc đánh dấu câu ngoài phạm vi (router + template “không có trong sổ tay”).

### #2

- **Question:** Lao động nữ được nghỉ thai sản trong thời gian bao lâu?
- **Expected:** Thời gian nghỉ thai sản tiêu chuẩn cho lao động nữ là 6 tháng theo quy định của pháp luật và công ty.
- **Actual:** Không tìm thấy.
- **Scores:** faithfulness ≈ 0.67 · answer_relevancy = 0 · context_precision ≈ 0.28 · context_recall ≈ 0.44
- **Error Tree:** Same as #1 — abstain khi không có evidence trong context.
- **Root cause:** Chính sách **thai sản** không nằm trong bộ tài liệu hiện tại.
- **Suggested fix:** Mở rộng HR policy trong data; hoặc enrichment (M5) map intent HR → doc đúng section nếu đã có file.

### #3

- **Question:** Hồ sơ thanh toán công tác phí phải được nộp trong vòng bao nhiêu ngày?
- **Expected:** …15 ngày làm việc… (Kế toán).
- **Actual:** Không tìm thấy.
- **Scores:** faithfulness ≈ 0.67 · answer_relevancy = 0 · context_precision ≈ 0.35 · context_recall ≈ 0.55
- **Root cause:** Quy định **công tác phí / deadline nộp hồ sơ** không có trong corpus.
- **Suggested fix:** Thêm policy tài chính – công tác; cải thiện metadata `topic` để filter trước khi rerank khi corpus lớn.

### #4

- **Question:** Giờ làm việc tiêu chuẩn của văn phòng bắt đầu và kết thúc lúc mấy giờ?
- **Expected:** 8:30 – 17:30, thứ Hai–thứ Sáu.
- **Actual:** Không tìm thấy.
- **Scores:** faithfulness ≈ 0.67 · answer_relevancy = 0 · context_precision ≈ 0.23 · context_recall = 0.50
- **Root cause:** **Giờ làm việc** không được mô tả trong tài liệu đã index.
- **Suggested fix:** Ingest employee handbook phần “Working hours”; kiểm tra chunk không cắt ngang bảng giờ nếu có.

### #5

- **Question:** Tài liệu của công ty được phân loại thành mấy cấp độ bảo mật?
- **Expected:** 3 cấp: Công khai, Nội bộ, Confidential.
- **Actual:** Không tìm thấy.
- **Scores:** faithfulness ≈ 0.67 · answer_relevancy = 0 · context_precision ≈ 0.41 · context_recall ≈ 0.63
- **Root cause:** **Phân loại mức độ bảo mật tài liệu** không xuất hiện trong policy đã dùng cho lab.
- **Suggested fix:** Thêm section Information Security / data classification vào knowledge base.

## Case Study

**Question chọn phân tích:** Khi nghe chuông báo cháy tòa nhà, nhân viên phải làm gì?

**Error Tree walkthrough:**

1. **Coverage:** Ground truth mô tả quy trình PCCC; corpus lab chủ yếu là `sample_policy.md` (nghỉ phép, thử việc, mật khẩu, VPN, dữ liệu cá nhân) — **không chứa** quy định báo cháy/sơ tán.
2. **Retrieval:** Hybrid search vẫn trả các chunk “gần” chủ đề chung (an toàn / nội bộ) nhưng **không** chứa atomic fact trong expected answer → context_recall thấp.
3. **Generation:** Pipeline trả *“Không tìm thấy thông tin.”* — trung thực với context nhưng **answer_relevancy** đối với ground truth rất thấp; faithfulness trung bình vì judge so sánh với context lẫn expected.
4. **Fix ưu tiên:** Bổ sung tài liệu đúng domain hoặc thu hẹp test set theo coverage; tùy chọn: classifier “out of scope” để tránh mix với câu có trong sổ tay.

**Nếu có thêm 1 giờ, sẽ optimize:**

- Đối chiếu `test_set.json` với từng heading trong corpus để gắn nhãn câu **in-scope / OOD** trước khi chạy RAGAS batch.
- Thêm 1–2 file markdown ngắn (PCCC + HR misc) và re-index để giảm tỷ lệ “Không tìm thấy” giả.
- Giữ Qdrant + hybrid + rerank; tune `HYBRID_TOP_K` / `RERANK_TOP_K` sau khi corpus đã đủ phủ.
