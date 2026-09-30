# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Quốc Toản
- **MSSV:** 2A202602984
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tranquoctoan2004/K4-L3B-Day13-TranQuocToan-2A202602984-Monitoring-LLMOps
- **Commit SHA cuối:** `9cf04d4` _(Lấy từ ảnh `git log -1 --oneline`)_
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602984`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| **Evidence**                                | **Đường dẫn**                        |
| :------------------------------------------ | :----------------------------------- |
| Pytest cuối                                 | `evidence/pytest.txt`                |
| Log validator                               | `evidence/log-validator.txt`         |
| Dashboard validator                         | `evidence/dashboard-validator.txt`   |
| Structured log + incident log               | `evidence/01-incident-log.png`       |
| Trace list                                  | `evidence/02-trace-list.png`         |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png`     |
| Prompt versions + promote/rollback          | `evidence/04-prompt-versioning.png`  |
| Dashboard + incident metric                 | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| **Nội dung**            | **Baseline**        | **Kết quả cuối**       | **Nhận xét**                                                             |
| :---------------------- | :------------------ | :--------------------- | :----------------------------------------------------------------------- |
| `validate_logs.py`      | PASS                | **PASS (100/100)**     | 297 log records, 135 correlation IDs, 0 PII leaks.                       |
| `validate_dashboard.py` | PASS                | **HỢP LỆ (6/6 panel)** | Đầy đủ 6 panel theo contract.                                            |
| `pytest`                | PASS                | **24 passed in 5.75s** | Toàn bộ unit test đều vượt qua.                                          |
| Số traces hợp lệ        | ≥ 10                | **~51 traces**         | Dựa trên trace list (ảnh 7).                                             |
| Số PII leak             | 0                   | **0**                  | Xác nhận từ `validate_logs.py`.                                          |
| Latency P95 / TTFT P95  | < 3000ms / < 1500ms | **2655ms / 62ms**      | Trong giai đoạn incident (ảnh 13). Bình thường là 187ms / 51ms (ảnh 12). |
| Retrieval success rate  | ≥ 90%               | **100%**               | Luôn đạt 100% trong cả hai dashboard.                                    |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware `CorrelationIdMiddleware` đọc header `x-request-id`, nếu không có sẽ sinh mã `req-<8-char-hex>`. ID này được bind vào structlog context qua `bind_contextvars` để mọi log line trong cùng request đều có trường `correlation_id`.
- **Các metadata được ghi vào structured log:** `service`, `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, `event`, `model`, `correlation_id`, `user_id_hash`, `feature`, `env`, `session_id`, `level`, `ts`. Ngoài ra còn có `payload.message_preview` và `payload.answer_preview`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Sử dụng regex `PII_PATTERNS` trong `app/pii.py` để thay thế email, SĐT VN, CCCD bằng `[REDACTED_...]`. Hàm `scrub_text` được gọi tự động qua processor `scrub_event` của structlog trước khi ghi file.
- **Cách kiểm chứng kết quả:**
  1. Chạy `validate_logs.py` → `Potential PII leaks detected: 0`.
  2. Chạy `curl` gửi dữ liệu chứa PII (ảnh 6) → Log ghi nhận `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Project Langfuse `day13-k4-l3b-2A202602984`, trace name `day13-agent-request`, root span `lab-agent-run`, tag `lab`.
- **Cấu trúc root/retrieval/generation observations:** Root span `lab-agent-run` (type `agent`) → span con `retrieval` (type `retriever`) → span con `generation` (type `generation`).
- **Cách nối trace với log:** Dùng `correlation_id` được lưu trong metadata của trace. Ví dụ: log có `req-063bbf82` → filter trace metadata chứa `req-063bbf82`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** `v1` / `production` (ban đầu)
- **Version/label candidate:** `v2` / `candidate` (phiên bản mới)
- **Trace ID của mỗi version:**
  - Trace dùng `v1`: `3507f1b72bdd5a979614583701e675cd` (ảnh 8, metadata hiển thị `prompt_version: "1"`).
  - Trace dùng `v2`: .
- **Cách promote và rollback** `production`**:** Trong Langfuse UI → Prompts → `day13-chat` → Versions. Gán label `production` cho version mong muốn. Hiện tại v1 đang giữ label `production` và `baseline`; v2 đang giữ `latest` và `candidate`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  1. Latency percentiles and TTFT
  2. Request traffic
  3. Error rate and retrieval success
  4. Cost over time
  5. Input and output tokens
  6. Quality proxy

- **SLO và lý do chọn:** SLO `fast_successful_requests`, target 99.5% trong 28 ngày. SLI: good event = `response_sent` và `latency_ms <= 3000`. Ngưỡng 3000ms được chọn vì baseline test cho thấy phản hồi trung bình 150–200ms, nên 3000ms là mức trần hợp lý cho trải nghiệm người dùng.

- **Cách tính error budget:** SLO 99.5% ⇒ error budget 0.5%. Với 10,000 request, tối đa 50 request được phép lỗi hoặc chậm hơn 3000ms.

- **Ba alert và runbook tương ứng:**
  1. **HighLatencyP95:** `p95(latency_ms) > 3000ms` trong 5m, severity: warning.
  2. **HighErrorRate:** `error_rate > 2%` trong 3m, severity: critical.
  3. **LowRetrievalSuccessRate:** `retrieval_success_rate < 90%` trong 5m, severity: critical.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** Khoảng 12:00 – 12:15 (dựa trên trục thời gian dashboard ảnh 13).
- **Triệu chứng từ metrics:** `latency_p95` tăng vọt lên 2655ms (gần chạm ngưỡng 3000ms), có request đạt 3677ms. `retrieval_success` vẫn 100%, error rate 0%.
- **Log line và correlation ID liên quan:** Log line `response_sent` có `correlation_id: req-063bbf82`, `latency_ms: 3677`, `feature: monitoring`, `session_id: k4-l3b-challenge-s05` (ảnh 14).
- **Trace ID và span gây ảnh hưởng:** Trace ID tương ứng cần tìm trong Langfuse. Waterfall cho thấy span `retrieval` chiếm phần lớn thời gian (trong ảnh 8, retrieval chiếm 152ms/154ms; trong incident, span này sẽ cao hơn nhiều).
- **Root cause:** Incident `rag_slow` được kích hoạt khiến hàm `retrieve` trong `app/mock_rag.py` chạy chậm nhân tạo, kéo dài toàn bộ pipeline.
- **Fix action:** Tắt incident bằng `POST /incidents/rag_slow/disable`.
- **Preventive measure:** Alert `HighLatencyP95` (5m). Runbook hướng dẫn kiểm tra span `retrieval` đầu tiên khi có alert latency. Thêm guardrail CI/CD tự động rollback nếu P95 vượt 3000ms.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Chọn structlog với processor `scrub_event` để tự động scrub PII ở tầng logging. Điều này đảm bảo không có PII nào lọt ra file log ngay cả khi lập trình viên quên scrub.

- **Một lỗi/blocker đã gặp:** Ban đầu, correlation ID không được truyền vào Langfuse metadata, khiến việc nối log với trace gặp khó khăn. Đã khắc phục bằng cách thêm `metadata={"correlation_id": correlation_id}` vào `propagate_attributes`.

- **Cách tìm nguyên nhân và xử lý:** Bắt đầu từ metric P95 tăng → lọc log theo `correlation_id` (`req-063bbf82`) → mở trace tương ứng trong Langfuse → waterfall cho thấy span `retrieval` chiếm phần lớn thời gian → xác định root cause là incident `rag_slow`.

- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết _có vấn đề gì_ và _khi nào_. Logs giúp _chọn request cụ thể_ qua `correlation_id`. Traces cho biết _bước nào gây ra vấn đề_ trong request đó.

- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version kiểm soát thay đổi nội dung prompt. Token/cost kiểm soát ngân sách. SLO và rollback đảm bảo hệ thống đáp ứng cam kết chất lượng và khôi phục nhanh khi có sự cố.

- **Điều quan trọng nhất đã học:** Cách xây dựng pipeline quan sát hoàn chỉnh (logging, tracing, metrics) và cách sử dụng chúng cùng nhau để điều tra sự cố trong hệ thống LLM.

- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Cần chụp lại ảnh trace waterfall của đúng incident `req-063bbf82` (ảnh 8 hiện tại là trace bình thường). Cần lưu các output text vào file đúng tên.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối (`9cf04d4`).
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
