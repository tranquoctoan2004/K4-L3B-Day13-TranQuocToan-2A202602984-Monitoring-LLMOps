"""Hỗ trợ CP3: đi từ Metrics -> Logs bằng dữ liệu thật trong data/logs.jsonl.

Script chỉ ĐỌC log và config/challenge.json, không sửa file nào và không gọi mạng.
Bước Traces (Langfuse) phải làm thủ công bằng correlation_id mà script in ra.

Cách dùng (sau khi đã chạy inject_incident.py và load_test.py --challenge):
    python scripts/investigate_incident.py
    python scripts/investigate_incident.py --log data/logs.jsonl --top 3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge
from app.cli import configure_utf8_stdio
from app.metrics import percentile  # dùng đúng công thức percentile của dashboard


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "ts" in row and "event" in row:
            rows.append(row)
    rows.sort(key=lambda r: r["ts"])
    return rows


def summarize(rows: list[dict], failed: list[dict], threshold_ms: int) -> dict:
    lat = [int(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
    ttft = [int(r["ttft_ms"]) for r in rows if r.get("ttft_ms") is not None]
    n = len(rows)
    total = n + len(failed)
    avg = lambda key: (sum(float(r.get(key) or 0) for r in rows) / n) if n else 0.0
    return {
        "requests_ok": n,
        "requests_failed": len(failed),
        "error_rate_pct": round(100 * len(failed) / total, 2) if total else 0.0,
        "latency_p50": percentile(lat, 50),
        "latency_p95": percentile(lat, 95),
        "latency_max": float(max(lat)) if lat else 0.0,
        "ttft_p95": percentile(ttft, 95),
        "avg_tokens_out": round(avg("tokens_out"), 1),
        "avg_cost_usd": round(avg("cost_usd"), 6),
        "avg_quality": round(avg("quality_score"), 3),
        "over_threshold": sum(1 for v in lat if v > threshold_ms),
    }


def ratio(after: float, before: float) -> str:
    if before <= 0:
        return "n/a"
    return f"x{after / before:.2f}"


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--log", default="data/logs.jsonl")
    parser.add_argument("--challenge", default="config/challenge.json")
    parser.add_argument("--top", type=int, default=3, help="Số request chậm nhất cần in ra")
    args = parser.parse_args()

    challenge = load_challenge(args.challenge)
    threshold = challenge.latency_threshold_ms
    rows = load_rows(Path(args.log))

    enabled = [r for r in rows if r["event"] == "incident_enabled"
               and (r.get("payload") or {}).get("name") == challenge.incident]
    if not enabled:
        sys.exit(
            f"Không thấy event incident_enabled cho '{challenge.incident}' trong {args.log}.\n"
            "Hãy chạy: python scripts/inject_incident.py  rồi  "
            "python scripts/load_test.py --challenge --concurrency 5"
        )
    t_on = enabled[-1]["ts"]
    disabled = [r for r in rows if r["event"] == "incident_disabled" and r["ts"] > t_on
                and (r.get("payload") or {}).get("name") == challenge.incident]
    t_off = disabled[0]["ts"] if disabled else None

    def in_feature(r: dict) -> bool:
        return r.get("feature") == challenge.affected_feature

    ok_before = [r for r in rows if r["event"] == "response_sent" and r["ts"] < t_on and in_feature(r)]
    fail_before = [r for r in rows if r["event"] == "request_failed" and r["ts"] < t_on and in_feature(r)]
    in_window = lambda r: r["ts"] >= t_on and (t_off is None or r["ts"] <= t_off)
    ok_after = [r for r in rows if r["event"] == "response_sent" and in_window(r) and in_feature(r)]
    fail_after = [r for r in rows if r["event"] == "request_failed" and in_window(r) and in_feature(r)]

    before = summarize(ok_before, fail_before, threshold)
    after = summarize(ok_after, fail_after, threshold)

    print("=" * 72)
    print(f"Challenge ID : {challenge.challenge_id}   (cohort {challenge.cohort}, seed {challenge.seed})")
    print(f"Incident     : {challenge.incident}   feature bị ảnh hưởng: {challenge.affected_feature}")
    print(f"Ngưỡng       : latency_ms > {threshold}")
    print(f"Cửa sổ       : {t_on}  ->  {t_off or 'cuối log (chưa disable)'}")
    print("=" * 72)

    print("\n[1] METRICS  (before = trước inject, after = trong cửa sổ incident)")
    print(f"{'metric':<18}{'before':>12}{'after':>12}{'đổi':>10}")
    for key in ("requests_ok", "requests_failed", "error_rate_pct", "latency_p50", "latency_p95",
                "latency_max", "ttft_p95", "avg_tokens_out", "avg_cost_usd", "avg_quality", "over_threshold"):
        print(f"{key:<18}{before[key]:>12}{after[key]:>12}{ratio(after[key], before[key]):>10}")

    print("\n    Gợi ý đọc số liệu (giả thuyết cần kiểm chứng ở trace, chưa phải kết luận):")
    if not ok_after:
        print("    - Không có response_sent nào trong cửa sổ: chạy lại load_test --challenge.")
    else:
        lat_up = after["latency_p95"] > max(before["latency_p95"], 1) * 1.5 or after["over_threshold"] > 0
        ttft_flat = after["ttft_p95"] <= max(before["ttft_p95"], 1) * 1.3
        tok_flat = after["avg_tokens_out"] <= max(before["avg_tokens_out"], 1) * 1.5
        err_flat = after["requests_failed"] == 0
        print(f"    - Latency tăng rõ rệt         : {lat_up}")
        print(f"    - TTFT gần như không đổi      : {ttft_flat}  (LLM bắt đầu sinh token vẫn nhanh)")
        print(f"    - Token/cost không đột biến   : {tok_flat}")
        print(f"    - Không có lỗi                : {err_flat}")
        if lat_up and ttft_flat and tok_flat and err_flat:
            print("    => Chậm nhưng không lỗi, TTFT/token bình thường: nghi bước KHÔNG phải LLM")
            print("       (retrieval/tool). Phải xác nhận bằng duration từng span trong trace.")

    print("\n[2] LOGS  request bất thường trong cửa sổ (sắp theo latency giảm dần)")
    slow = sorted((r for r in ok_after if int(r.get("latency_ms") or 0) > threshold),
                  key=lambda r: -int(r["latency_ms"]))
    if not slow:
        print("    Không có request nào vượt ngưỡng.")
    for r in slow[: args.top]:
        print(f"    {r['ts']}  correlation_id={r['correlation_id']}  latency_ms={r['latency_ms']}  "
              f"ttft_ms={r.get('ttft_ms')}  session={r.get('session_id')}")
    if slow:
        pick = slow[0]
        print("\n    Log line đại diện (dán/chụp làm evidence 01-incident-log):")
        print("    " + json.dumps(pick, ensure_ascii=False))
        print("\n[3] TRACES  bước thủ công trên Langfuse (project cá nhân của bạn)")
        print(f"    1. Traces -> chọn time range chứa {t_on[:16]} -> tìm correlation_id = {pick['correlation_id']}")
        print("       (trace có metadata.correlation_id; dùng ô search/filter theo metadata).")
        print("    2. Mở trace, expand: lab-agent-run -> retrieval / generation.")
        print("    3. So sánh duration: span nào chiếm gần hết latency_ms của log line ở trên?")
        print("    4. Ghi trace ID + duration từng span vào REPORT.md mục 7, chụp ảnh 03-incident-trace.")
        others = [r["correlation_id"] for r in slow[1: args.top]]
        if others:
            print(f"    Đối chiếu thêm (nếu cần): {', '.join(others)}")


if __name__ == "__main__":
    main()
