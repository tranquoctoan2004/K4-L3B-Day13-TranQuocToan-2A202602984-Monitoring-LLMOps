"""Dashboard 6 panel cho Day 13. Nguon du lieu: data/logs.jsonl.
Ten panel, don vi, threshold, time range va refresh lay tu config/dashboard.yaml.

Chay:  streamlit run dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
LOG_PATH = ROOT / "data" / "logs.jsonl"
PANELS = {p["id"]: p for p in CFG["panels"]}

st.set_page_config(page_title=CFG["title"], layout="wide")

with st.sidebar:
    st.header("Cai dat")
    minutes = st.number_input("Time range (phut)", 1, 1440, int(CFG["time_range_minutes"]))
    anchor = st.checkbox("Tinh cua so tu log moi nhat (demo/chup anh)", value=False)
    st.caption(f"Refresh moi {CFG['refresh_seconds']}s")


def load_logs() -> pd.DataFrame:
    rows = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def threshold_layer(value: float):
    return alt.Chart(pd.DataFrame({"y": [value]})).mark_rule(color="red", strokeDash=[6, 4]).encode(y="y:Q")


def line(df: pd.DataFrame, cols: list[str], thr: float | None = None):
    if df.empty:
        st.info("Chua co du lieu trong time range.")
        return
    long = df.reset_index().melt(id_vars="ts", value_vars=cols, var_name="series", value_name="value")
    chart = alt.Chart(long).mark_line(point=True).encode(x="ts:T", y="value:Q", color="series:N")
    if thr is not None:
        chart = chart + threshold_layer(thr)
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:  # Streamlit cu
        st.altair_chart(chart, use_container_width=True)


def badge(ok: bool) -> str:
    return "OK" if ok else "VUOT NGUONG"


def header(pid: str):
    p = PANELS[pid]
    t = p["threshold"]
    st.subheader(p["title"])
    st.caption(f"Don vi: {p['unit']} | Threshold: {t['aggregation']} {t['operator']} {t['value']} | Range: {minutes} phut")
    return t


@st.fragment(run_every=int(CFG["refresh_seconds"]))
def render() -> None:
    df = load_logs()
    if df.empty:
        st.warning("Chua co log. Hay chay API va scripts/load_test.py.")
        return
    end = df["ts"].max() if anchor else pd.Timestamp.now(tz="UTC")
    start = end - pd.Timedelta(minutes=int(minutes))
    w = df[(df["ts"] >= start) & (df["ts"] <= end)].copy()
    st.title(CFG["title"])
    st.caption(f"Cua so: {start:%Y-%m-%d %H:%M} -> {end:%H:%M} UTC | {len(w)} log records")

    resp = w[w["event"] == "response_sent"]
    recv = w[w["event"] == "request_received"]
    fail = w[w["event"] == "request_failed"]
    per_min = lambda s, how: s.set_index("ts").resample("1min").agg(how) if not s.empty else s

    c1, c2, c3 = st.columns(3)
    # 1. Latency
    with c1:
        t = header("latency")
        if resp.empty:
            st.info("Chua co response_sent.")
        else:
            p50, p95, p99 = resp["latency_ms"].quantile([0.5, 0.95, 0.99])
            ttft95 = resp["ttft_ms"].quantile(0.95)
            m = st.columns(4)
            m[0].metric("P50", f"{p50:.0f} ms")
            m[1].metric("P95", f"{p95:.0f} ms", badge(p95 <= t["value"]), delta_color="off")
            m[2].metric("P99", f"{p99:.0f} ms")
            m[3].metric("TTFT P95", f"{ttft95:.0f} ms")
            g = resp.set_index("ts")[["latency_ms", "ttft_ms"]].resample("1min").quantile(0.95).dropna(how="all")
            line(g.rename(columns={"latency_ms": "latency_p95_ms", "ttft_ms": "ttft_p95_ms"}),
                 ["latency_p95_ms", "ttft_p95_ms"], t["value"])
    # 2. Traffic
    with c2:
        t = header("traffic")
        rpm = len(recv) / max(int(minutes), 1)
        st.metric("Tong request", len(recv))
        st.metric("Request/phut (TB)", f"{rpm:.2f}", badge(rpm >= t["value"]), delta_color="off")
        if not recv.empty:
            g = recv.set_index("ts").resample("1min").size().to_frame("requests_per_minute")
            line(g, ["requests_per_minute"], t["value"])
    # 3. Errors
    with c3:
        t = header("errors")
        err = 100 * len(fail) / len(recv) if len(recv) else 0.0
        tool = w["tool_success"].dropna() if "tool_success" in w else pd.Series(dtype=bool)
        succ = 100 * tool.astype(bool).mean() if len(tool) else float("nan")
        m = st.columns(2)
        m[0].metric("Error rate", f"{err:.2f} %", badge(err <= t["value"]), delta_color="off")
        m[1].metric("Retrieval success", "n/a" if pd.isna(succ) else f"{succ:.1f} %")
        if fail.empty:
            st.success("Khong co request_failed trong range.")
        else:
            st.bar_chart(fail["error_type"].value_counts())

    c4, c5, c6 = st.columns(3)
    # 4. Cost
    with c4:
        t = header("cost")
        total = resp["cost_usd"].sum() if not resp.empty else 0.0
        st.metric("Tong chi phi", f"${total:.4f}", badge(total <= t["value"]), delta_color="off")
        if not resp.empty:
            g = resp.set_index("ts")["cost_usd"].resample("1min").sum().to_frame("cost_usd_per_min")
            line(g, ["cost_usd_per_min"])
    # 5. Tokens
    with c5:
        t = header("tokens")
        ti, to = (resp["tokens_in"].sum(), resp["tokens_out"].sum()) if not resp.empty else (0, 0)
        m = st.columns(2)
        m[0].metric("Tokens in", f"{ti:,.0f}")
        m[1].metric("Tokens out", f"{to:,.0f}")
        st.caption(badge(max(ti, to) <= t["value"]) + f" (nguong {t['value']:,} / field)")
        if not resp.empty:
            g = resp.set_index("ts")[["tokens_in", "tokens_out"]].resample("1min").sum()
            line(g, ["tokens_in", "tokens_out"], t["value"])
    # 6. Quality
    with c6:
        t = header("quality")
        q = resp["quality_score"].mean() if not resp.empty else float("nan")
        st.metric("Quality TB", "n/a" if pd.isna(q) else f"{q:.2f}",
                  "" if pd.isna(q) else badge(q >= t["value"]), delta_color="off")
        if not resp.empty:
            g = resp.set_index("ts")["quality_score"].resample("1min").mean().dropna().to_frame("quality_mean")
            line(g, ["quality_mean"], t["value"])


render()
