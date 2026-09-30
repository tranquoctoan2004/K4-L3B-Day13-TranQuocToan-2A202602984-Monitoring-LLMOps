# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-2A202602984`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` kéo dài 5 phút
- Ảnh hưởng tới người dùng: Trải nghiệm người dùng giảm sút đáng kể do thời gian phản hồi câu hỏi kéo dài quá 3 giây.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Latency trên Dashboard để xác định khoảng thời gian Spike.
  2. Tra cứu `data/logs.jsonl` tìm các request có `latency_ms > 3000` và trích xuất `correlation_id`.
  3. Tra cứu `correlation_id` trên Langfuse Tracing để kiểm tra xem độ trễ đến từ bước `retrieval` hay `generation`.
- Mitigation tạm thời: Rollback phiên bản prompt hoặc giảm tải request nếu LLM đang bị rate limit.
- Owner: `student-2A202602984`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỉ lệ lỗi trên tổng số request (`request_failed / total_requests`)
- Điều kiện và thời gian duy trì: `error_rate > 2%` kéo dài trong 3 phút
- Ảnh hưởng tới người dùng: Người dùng nhận phản hồi lỗi 500 từ hệ thống API không thể lấy câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors trên Dashboard để kiểm tra tỉ lệ lỗi hiện tại.
  2. Tìm các log mang mức `level: ERROR` trong `data/logs.jsonl` để lấy thông tin `error_type` và `detail`.
  3. Kiểm tra trạng thái hệ thống downstream (LLM provider, Vector Database) trên Langfuse Traces.
- Mitigation tạm thời: Tắt incident đang kích hoạt nếu do thử nghiệm, chuyển sang fallback model.
- Owner: `student-2A202602984`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỉ lệ `tool_success == True` trên tổng các sự kiện liên quan đến retrieval
- Điều kiện và thời gian duy trì: `retrieval_success_rate < 90%` kéo dài trong 5 phút
- Ảnh hưởng tới người dùng: Agent không lấy đủ tài liệu bổ trợ làm chất lượng câu trả lời bị suy giảm hoặc gây lỗi câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel Retrieval Success Rate trên Dashboard.
  2. Lọc log sự kiện có `tool_name: retrieval` và `tool_success: false` trong `data/logs.jsonl`.
  3. Mở span `retrieval` trên Langfuse Trace tương ứng để xem lỗi truy vấn database.
- Mitigation tạm thời: Chuyển cấu hình tìm kiếm sang chế độ fallback hoặc khởi động lại dịch vụ retrieval database.
- Owner: `student-2A202602984`
