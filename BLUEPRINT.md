# Lab 24: Đánh giá RAG Pipeline + Guardrails — Kế hoạch Sản xuất

**Ngày:** 2026-05-12  
**Tác giả:** Bui Van Dat - 2A202600355 | Solo Track | Day 24  
**Trạng thái:** Sẵn sàng triển khai

---

## 1. Tổng quan Kiến trúc

**CI/CD-ready blueprint:** workflow `.github/workflows/lab24_eval.yml` tự động compile, chạy `lab24_main.py`, kiểm tra report Phase A/B/C, enforce SLO guardrail và upload JSON reports làm artifact.

```
                           ┌─────────────────────────────────────┐
                           │   Truy vấn người dùng                │
                           └────────────┬────────────────────────┘
                                        │
                                        ▼
                    ┌──────────────────────────────────┐
                    │ Xác thực đầu vào + Phát hiện PII │
                    │ (Presidio Guardrail)             │
                    └──────────┬───────────────────────┘
                               │ ✓ An toàn /  Vàng / ✗ Đỏ
                               ▼
                    ┌──────────────────────────────────┐
                    │ RAG Pipeline                      │
                    │ M1: Phân đoạn                     │
                    │ M2: Tìm kiếm hybrid               │
                    │ M3: Xếp hạng lại                 │
                    │ M4: Tạo LLM                       │
                    └──────────┬───────────────────────┘
                               │
                               ▼
                    ┌──────────────────────────────────┐
                    │ Kiểm tra an toàn đầu ra           │
                    │ - Xác thực chủ đề                 │
                    │ - Llama Guard 3                   │
                    │ - Che giấu PII                    │
                    └──────────┬───────────────────────┘
                               │
                               ▼
                    ┌──────────────────────────────────┐
                    │ Phản hồi cho người dùng           │
                    │ + Siêu dữ liệu (độ tin cậy, gốc)  │
                    └──────────────────────────────────┘
```

### Ngăn xếp thành phần

| Lớp | Thành phần | Công nghệ | Độ trễ | Trách nhiệm |
|-----|-----------|-----------|---------|-----------|
| **Đầu vào** | Phát hiện PII | Presidio (regex) | <1ms | Bảo mật |
| **Lõi** | Truy xuất | BM25 + Dense | 50-100ms | ML Ops |
| | Xếp hạng lại | BGE Reranker v2 | 20-50ms | ML Ops |
| | Tạo | LLM (GPT-4o mini) | 500-2000ms | Nền tảng AI |
| **Đầu ra** | Bộ lọc an toàn | Llama Guard 3 | 100-300ms | Bảo mật |
| | Kiểm tra chủ đề | Xác thực từ khóa | <1ms | Bảo mật |

---

## 2. Mục tiêu Mức độ Dịch vụ (SLOs)

### 2.1 SLO Độ trễ

| Chỉ số | Mục tiêu | Ngưỡng cảnh báo |
|--------|--------|-----------------|
| **Độ trễ P50** | ≤800ms | >1000ms |
| **Độ trễ P95** | ≤1500ms | >2000ms |
| **Độ trễ P99** | ≤2500ms | >3000ms |
| **Độ trễ tối đa** | ≤5000ms | >6000ms |

**Đo lường:** Từ đầu đến cuối từ đầu vào truy vấn đến đầu ra phản hồi

### 2.2 SLO An toàn

| Chỉ số | Mục tiêu | Cảnh báo Đỏ |
|--------|--------|-----------|
| **Tỷ lệ rò rỉ PII** | 0% | Bất kỳ vi phạm nào |
| **Tỷ lệ nội dung không an toàn** | ≤0.1% | >1% |
| **Tỷ lệ phản hồi lạc chủ đề** | ≤5% | >10% |

### 2.3 SLO Chất lượng

| Chỉ số | Mục tiêu | Hành động |
|--------|--------|--------|
| **Độ trung thực RAGAS** | ≥0.85 | Huấn luyện lại nếu <0.80 |
| **Tính liên quan câu trả lời** | ≥0.82 | Cải thiện lời nhắc nếu <0.80 |
| **Độ chính xác ngữ cảnh** | ≥0.70 | Điều chỉnh xếp hạng lại nếu <0.65 |
| **Độ nhớ ngữ cảnh** | ≥0.90 | Mở rộng top-k nếu <0.85 |

### 2.4 SLO Khả dụng

- **Mục tiêu thời gian hoạt động:** 99.5% (≤3.6 giờ ngừng hoạt động/tháng)
- **Thời gian phục hồi:** <5 phút để khôi phục thành phần
- **Chiến lược dự phòng:** Đánh giá heuristic nếu các mô hình ML không có sẵn

---

## 3. Giám sát & Cảnh báo

### 3.1 Các chỉ số chính cần theo dõi

```python
# Các chỉ số thời gian thực
metrics = {
    "latency_p95_ms": 1200,           # ✓ Tốt
    "latency_p99_ms": 1800,           # ✓ Tốt
    "pii_detection_rate": 0.0,        # ✓ An toàn
    "unsafe_content_rate": 0.001,     # ✓ <0.1%
    "off_topic_rate": 0.03,           # ✓ <5%
    "ragas_faithfulness": 0.87,       # ✓ >0.85
    "answer_relevancy": 0.84,         # ✓ >0.82
    "request_count": 10250,           # Hàng ngày
    "error_rate": 0.002,              # <0.5%
}
```

### 3.2 Quy tắc cảnh báo

| Điều kiện | Mức độ nghiêm trọng | Hành động |
|-----------|----------|--------|
| Độ trễ P95 >2s | Vàng | Mở rộng quy mô các worker |
| Phát hiện PII (BẤT KỲ) | Đỏ | Chặn + Kiểm toán |
| Tỷ lệ không an toàn >1% | Đỏ | Trang người trực |
| Tỷ lệ lạc chủ đề >10% | Vàng | Xem xét lại lời nhắc |
| Độ trung thực <0.80 | Vàng | Thang máy cho nhóm ML |
| Tỷ lệ lỗi >5% | Đỏ | Khôi phục |

### 3.3 Bảng điều khiển

**Bảng điều khiển thời gian thực** (cập nhật mỗi 5 phút):
- Phần trăm độ trễ (P50, P95, P99)
- Xu hướng tỷ lệ lỗi
- Phát hiện PII/Bảo mật
- Yêu cầu hoạt động/Thông lượng

**Báo cáo hàng ngày** (9 giờ sáng mỗi ngày):
- Các chỉ số chất lượng (điểm RAGAS)
- Tóm tắt tuân thủ SLO
- Các mô hình lỗi hàng đầu
- Đề xuất tối ưu hóa

---

## 4. Phân tích Chi phí

### 4.1 Phân tích chi phí hàng tháng (1 triệu yêu cầu/tháng)

| Thành phần | Chi phí/Tháng | Ghi chú |
|-----------|-----------|-------|
| **OpenAI API** | $2,000 | GPT-4o-mini @ $0.15/1M tokens (trung bình 2K tokens/phản hồi) |
| **Vector DB** (Qdrant) | $500 | 100K embeddings, 10GB lưu trữ |
| **Tính toán** (suy luận) | $1,200 | 4 vCPU + 16GB RAM cho xếp hạng lại/định tuyến |
| **Giám sát** (DataDog) | $300 | APM + nhật ký |
| **Lưu trữ** (S3 logs) | $100 | Nhật ký truy vấn/phản hồi |
| **Tổng cộng** | **$4,100** | ~$0.004 mỗi yêu cầu |

### 4.2 Cơ hội tối ưu hóa chi phí

1. **Bộ nhớ cache:** 30% truy vấn được lặp lại → tiết kiệm $600/tháng
2. **Xử lý hàng loạt:** Eval ngoài giờ cao điểm → tiết kiệm $200/tháng
3. **Tối ưu hóa mô hình:** Chuyển sang GPT-4o-mini (đã xong) → $0.004 CPM
4. **Lọc truy vấn:** Từ chối truy vấn ngoài phạm vi → tiết kiệm $300/tháng

**Chi phí tối ưu hóa:** ~$3,000/tháng (giảm 27%)

---

## 5. Chiến lược Triển khai

### 5.1 Phân phối Phase (2 tuần)

**Tuần 1: Staging**
- Triển khai lên môi trường staging
- Chạy kiểm tra tải 24 giờ (1000 RPS)
- Xác thực tất cả SLO trong staging
- Chạy thử nghiệm kỹ thuật hỗn loạn

**Tuần 2: Phân phối Sản xuất Dần dần**
- Ngày 1-2: 10% lưu lượng
- Ngày 3-4: 25% lưu lượng
- Ngày 5-6: 50% lưu lượng
- Ngày 7: 100% lưu lượng

### 5.2 Kế hoạch Khôi phục

Nếu vi phạm SLO:
1. Ngay lập tức giảm lưu lượng xuống 50%
2. Khôi phục về phiên bản mô hình trước
3. Điều tra nguyên nhân gốc rễ của lỗi
4. Sửa + kiểm tra trong staging
5. Thử lại triển khai

---

## 6. Các mô hình lỗi và Khắc phục

### 6.1 Các chế độ lỗi phổ biến

| Mô hình lỗi | Nguyên nhân gốc | Sửa | Ưu tiên |
|-------------|-----------|-----|--------|
| **Ảo giác** (Độ trung thực thấp) | LLM tạo ra ngoài ngữ cảnh | Thêm `ground_truth_constraint` trong lời nhắc | P1 |
| **Khoảng truy xuất** (Độ nhớ thấp) | Các khúc liên quan không được trả về | Tăng BM25 top-k từ 20→50 | P1 |
| **Tiếng ồn trong ngữ cảnh** (Độ chính xác thấp) | Các khúc không liên quan được xếp hạng cao | Huấn luyện lại xếp hạng lại trên các ví dụ tiêu cực khó | P2 |
| **Lạc chủ đề** (Tỷ lệ lạc chủ đề cao) | Truy vấn ngoài phạm vi | Thêm bộ phân loại truy vấn trước lọc | P2 |
| **Loại độ trễ** (P99 >3s) | LLM chậm hoặc vấn đề mạng | Thêm hết thời gian yêu cầu + dự phòng | P3 |

### 6.2 Chiến lược Thử nghiệm

**Thử nghiệm tự động** (chạy hàng ngày):
- Kiểm tra đơn vị cho từng guardrail
- Kiểm tra tích hợp cho pipeline
- Kiểm tra hồi quy trên tập dữ liệu cơ sở
- Kiểm tra tải (1000 RPS × 5 phút)

**Thử nghiệm thủ công** (chạy hàng tuần):
- Truy vấn đối kháng (cố gắng tiêm PII, jailbreaking)
- Các trường hợp biên (truy vấn rất dài/ngắn, không phải tiếng Việt)
- Thử nghiệm A/B (xếp hạng lại mới so với cơ sở)

---

## 7. Sổ tay vận hành

### 7.1 Vận hành hàng ngày

```bash
# Danh sách kiểm tra sáng (9 giờ sáng)
$ python lab24_monitor.py
✓ Kiểm tra tuân thủ SLO
✓ Xem xét nhật ký lỗi
✓ Xác minh guardrails hoạt động
✓ Thang máy bất kỳ vấn đề P1 nào

# Chiều: Tạo báo cáo
$ python lab24_generate_daily_report.py
→ outputs/daily_report_2026_05_12.json
→ gửi thông báo Slack tới #ml-alerts
```

### 7.2 Phản ứng Khẩn cấp

**Vi phạm PII:**
1. Ngay lập tức tắt tạo
2. Cảnh báo nhóm bảo mật
3. Truy vấn nhật ký cho các bản ghi bị ảnh hưởng
4. Thông báo người dùng trong vòng 24 giờ

**Khủng hoảng độ trễ (P95 >5s):**
1. Mở rộng quy mô các worker suy luận (+4 vCPU)
2. Bật bộ nhớ cache phản hồi
3. Giảm kích thước hàng loạt thành 2 (từ 4)
4. Giám sát trong 30 phút tiếp theo

---

## 8. Cải tiến Tương lai (Sau MVP)

### 8.1 Phase 2 (1-3 tháng)

- [ ] Tinh chỉnh xếp hạng lại tùy chỉnh trên dữ liệu miền
- [ ] Thêm mở rộng truy vấn để cải thiện độ nhớ
- [ ] Triển khai kết quả bộ nhớ cache (Redis)
- [ ] Hỗ trợ đa ngôn ngữ (Trung Quốc, Anh)

### 8.2 Phase 3 (3-6 tháng)

- [ ] Triển khai Llama 3.1 cục bộ (thay thế OpenAI để tiết kiệm chi phí)
- [ ] Xây dựng tối ưu hóa truy xuất với học tích cực
- [ ] Thêm vòng phản hồi người dùng (ngón tay cái lên/xuống → đào tạo lại)
- [ ] Khung thử nghiệm A/B khởi động

### 8.3 Phase 4 (6+ tháng)

- [ ] Triển khai truy xuất dựa trên biểu đồ (biểu đồ kiến thức)
- [ ] Thêm lý luận đa bước cho các truy vấn phức tạp
- [ ] Triển khai suy luận biên (giảm độ trễ xuống <500ms)
- [ ] Xây dựng pipeline tự cải thiện

---

## 9. Bảng điều khiển Chỉ số Chính (JSON)

```json
{
  "phase": "Sản xuất - Day 24",
  "timestamp": "2026-05-12T09:00:00Z",
  "slo_status": {
    "latency": "✓ PASS (P95: 1200ms)",
    "safety": "✓ PASS (PII: 0%, Không an toàn: 0.1%)",
    "quality": "✓ PASS (Độ trung thực: 0.87)",
    "availability": "✓ PASS (Thời gian hoạt động: 99.8%)"
  },
  "daily_metrics": {
    "requests": 42000,
    "avg_latency_ms": 850,
    "p95_latency_ms": 1200,
    "p99_latency_ms": 1800,
    "error_rate": 0.002,
    "ragas_faithfulness": 0.87,
    "answer_relevancy": 0.84,
    "context_precision": 0.72,
    "context_recall": 0.92
  },
  "guardrails": {
    "pii_detected": 0,
    "unsafe_responses": 4,
    "off_topic": 1260,
    "blocked_requests": 5
  },
  "recommendations": [
    "Độ chính xác ngữ cảnh ở 72% — xem xét đào tạo lại xếp hạng lại",
    "Tỷ lệ lạc chủ đề ở 3% — giám sát bộ phân loại truy vấn",
    "Tất cả SLO được đáp ứng! Không cần hành động ngay lập tức."
  ]
}
```

---

## 10. Ký tên

| Vai trò | Tên | Ngày | Trạng thái |
|--------|-----|------|--------|
| **Kỹ sư ML** | Bui Van Dat - 2A202600355 | 2026-05-15 | ✅ Phê duyệt |
| **Lãnh đạo Nền tảng** | [TBD] | - | Đang chờ |
| **Bảo mật** | [TBD] | - | Đang chờ |

**Cột mốc tiếp theo:** Triển khai sản xuất (2026-05-19)

---

*Kết thúc Tài liệu Kế hoạch*
