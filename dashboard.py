"""Run with: python -m streamlit run dashboard.py"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import time

import altair as alt
import pandas as pd
import streamlit as st

from netscope.analytics import collector_state, weighted_loss
from netscope.storage import DEFAULT_DB, Store


st.set_page_config(page_title="NetScope · Network observatory", page_icon="◉", layout="wide")
st.markdown("""<style>
    .block-container {max-width:1440px; padding-top:3.5rem;}
    h1 {letter-spacing:-.055em; font-weight:750 !important;}
    [data-testid="stMetric"] {background:#141f31; border:1px solid #25334a;
        padding:18px; border-radius:12px;}
    [data-testid="stMetricLabel"] {color:#a8b8cc;}
    [data-testid="stCaptionContainer"] {color:#a8b8cc;}
    [data-testid="stSidebar"] {border-right:1px solid #25334a;}
</style>""", unsafe_allow_html=True)

st.caption("NETSCOPE  /  LOCAL NETWORK OBSERVATORY")
st.title("Your network, in focus.")
st.write("Real interface traffic. Measured latency. A history you can explore.")

db_path = Path(os.environ.get("NETSCOPE_DB", str(DEFAULT_DB))).expanduser().resolve()
store = Store(db_path)
with st.sidebar:
    st.markdown("### ◉ NetScope")
    st.caption("PHASE 01 · WINDOWS MONITOR")
    st.divider()

if not db_path.exists():
    st.info("No measurements yet. Start the collector in a separate terminal, then refresh this page.")
    st.code(".\\.venv\\Scripts\\python.exe -m netscope collect", language="powershell")
    st.button("Refresh")
    st.stop()

try:
    sessions = store.sessions()
except (sqlite3.Error, RuntimeError) as exc:
    st.error(f"Cannot read the NetScope database: {exc}")
    st.stop()
if not sessions:
    st.info("The database is ready. Start the collector to record your first session.")
    st.button("Refresh")
    st.stop()


def session_label(session: dict) -> str:
    stamp = datetime.fromtimestamp(session["started_at"], timezone.utc).strftime("%d %b · %H:%M UTC")
    return f"{stamp} · {session['target']} · {session['id'][:6]}"


with st.sidebar:
    session_id = st.selectbox("Recording session", [s["id"] for s in sessions],
                              format_func=lambda value: session_label(next(s for s in sessions if s["id"] == value)))
    session = next(s for s in sessions if s["id"] == session_id)
    try:
        interfaces = store.interfaces(session_id)
    except sqlite3.Error as exc:
        st.error(f"Cannot read interfaces: {exc}")
        st.stop()
    if not interfaces:
        st.info("Waiting for interface samples. Refresh in a few seconds.")
        st.button("Refresh")
        st.stop()
    preferred = next((name for name in interfaces if "wi-fi" in name.lower() or "wlan" in name.lower()), interfaces[0])
    interface = st.selectbox("Network interface", interfaces, index=interfaces.index(preferred))
    minutes = st.selectbox("History window", [5, 15, 60], index=1, format_func=lambda n: f"Last {n} minutes")
    live_refresh = st.toggle("Refresh every 2 seconds", value=True)
    st.divider()
    st.caption(f"Probe target: {session['target']}")
    st.caption(f"Traffic interval: {session['sample_interval']:g}s · ICMP interval: {session['probe_interval']:g}s")
    st.caption("ICMP follows Windows routing. It is not pinned to the selected interface.")
    st.caption("Measurements stay in your local SQLite database.")


def format_metric(value: float | None, suffix: str) -> str:
    return "—" if value is None else f"{value:.2f} {suffix}"


@st.fragment(run_every=2 if live_refresh else None)
def render_measurements():
    try:
        samples, probes = store.history(session_id, interface, minutes)
        current_session = next((s for s in store.sessions() if s["id"] == session_id), session)
    except sqlite3.Error as exc:
        st.error(f"History is temporarily unavailable: {exc}")
        return
    if not samples:
        st.info("No samples for this interface in the selected window.")
        return
    latest = samples[-1]
    # Link-state freshness for this interface is deliberately separate from ICMP freshness.
    state = collector_state(current_session, latest["timestamp"], time.time())
    timestamp = datetime.fromtimestamp(latest["timestamp"], timezone.utc).strftime("%H:%M:%S UTC")
    badge, detail = st.columns([1, 3])
    with badge:
        st.badge(f"{state} · {interface}", color="green" if state == "Live" else "orange")
    with detail:
        st.caption(f"Last interface sample {timestamp} · Link {'up' if latest['is_up'] else 'down'} · Times shown in UTC")
    if state != "Live":
        st.warning(f"{state} recording. Values below are historical, last recorded measurements.")
    if latest["quality"] != "ok":
        st.info(f"Traffic rate unavailable: {latest['quality'].replace('_', ' ')}. A valid pair of samples is required.")
    last_probe = probes[-1] if probes else None
    probe_age = time.time() - last_probe["timestamp"] if last_probe else None
    probe_stale = probe_age is not None and probe_age > max(
        20, session["probe_interval"] * 3 + 10)
    latency = last_probe["mean_ms"] if last_probe and not last_probe["error"] else None
    cols = st.columns(4)
    cols[0].metric("↓ Download · latest", format_metric(latest["download_mbps"], "Mbps"))
    cols[1].metric("↑ Upload · latest", format_metric(latest["upload_mbps"], "Mbps"))
    cols[2].metric("Round-trip · last batch", format_metric(latency, "ms"))
    cols[3].metric("Probe loss · window", format_metric(weighted_loss(probes), "%"))
    if last_probe:
        st.caption(f"ICMP: {last_probe['received']}/{last_probe['sent']} replies in last batch · "
                   f"{last_probe['statuses']} · Observed {max(0, probe_age):.0f}s ago · Target {session['target']}")
        if last_probe["error"]:
            st.warning(f"Probe measurement error: {last_probe['error']}. This batch is excluded from loss calculations.")
        elif probe_stale:
            st.warning("Probe readings are old. The latency card shows the last recorded batch.")
        elif last_probe["received"] == 0:
            st.warning("No echo replies in the last batch. ICMP may be filtered; this alone does not prove an internet outage.")
    else:
        st.caption("Waiting for the first ICMP batch. Traffic recording is independent of probes.")

    traffic_tab, history_tab, about_tab = st.tabs(["Overview", "Recorded data", "Measurement guide"])
    frame = pd.DataFrame(samples)
    frame["time"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    frame["utc_label"] = frame["time"].dt.strftime("%H:%M:%S UTC")
    probe_frame = pd.DataFrame(probes)
    with traffic_tab:
        st.subheader("Interface traffic")
        st.caption("Observed throughput in decimal megabits per second · Hover or drag to explore")
        long = frame.melt(id_vars=["time", "utc_label"], value_vars=["download_mbps", "upload_mbps"],
                          var_name="direction", value_name="Mbps")
        long["direction"] = long["direction"].map({"download_mbps": "Download", "upload_mbps": "Upload"})
        chart = alt.Chart(long).mark_line(point=True).encode(
            x=alt.X("time:T", title="Time (UTC)", scale=alt.Scale(type="utc")),
            y=alt.Y("Mbps:Q", title="Mbps", scale=alt.Scale(zero=True)),
            color=alt.Color("direction:N", title=None,
                            scale=alt.Scale(domain=["Download", "Upload"], range=["#43d9ba", "#829cff"])),
            tooltip=[alt.Tooltip("utc_label:N", title="Time"), "direction:N", alt.Tooltip("Mbps:Q", format=".4f")],
        ).properties(height=270).interactive()
        st.altair_chart(chart, width="stretch")
        left, right = st.columns(2)
        with left:
            st.subheader("Round-trip latency")
            if not probe_frame.empty:
                probe_frame["time"] = pd.to_datetime(probe_frame["timestamp"], unit="s", utc=True)
                probe_frame["utc_label"] = probe_frame["time"].dt.strftime("%H:%M:%S UTC")
                valid = probe_frame["error"].isna()
                probe_frame.loc[~valid, ["mean_ms", "loss_percent"]] = float("nan")
                st.altair_chart(alt.Chart(probe_frame).mark_line(point=True, color="#829cff").encode(
                    x=alt.X("time:T", title="Time (UTC)", scale=alt.Scale(type="utc")),
                    y=alt.Y("mean_ms:Q", title="Mean RTT (ms)", scale=alt.Scale(zero=True)),
                    tooltip=[alt.Tooltip("utc_label:N", title="Time"), alt.Tooltip("mean_ms:Q", format=".2f"), "received:Q", "sent:Q"],
                ).properties(height=190), width="stretch")
            else:
                st.info("Waiting for ICMP measurements.")
        with right:
            st.subheader("Probe packet loss")
            if not probe_frame.empty:
                st.altair_chart(alt.Chart(probe_frame).mark_circle(color="#43d9ba", size=60).encode(
                    x=alt.X("time:T", title="Time (UTC)", scale=alt.Scale(type="utc")),
                    y=alt.Y("loss_percent:Q", title="Unanswered echoes (%)", scale=alt.Scale(domain=[0, 100])),
                    tooltip=[alt.Tooltip("utc_label:N", title="Time"), alt.Tooltip("loss_percent:Q", format=".1f"), "statuses:N"],
                ).properties(height=190), width="stretch")
            else:
                st.info("Waiting for ICMP measurements.")
        st.caption(f"{len(samples):,} interface samples · {len(probes):,} probe batches in view · "
                   "History is anchored to the session's last interface sample.")
    with history_tab:
        st.subheader("Export this view")
        st.caption("CSV files contain local interface names, timings and the probe target.")
        a, b = st.columns(2)
        a.download_button("Download interface CSV", frame.drop(columns="session_id").to_csv(index=False).encode("utf-8"),
                          "netscope-interfaces.csv", "text/csv")
        if not probe_frame.empty:
            b.download_button("Download probe CSV", probe_frame.drop(columns="session_id").to_csv(index=False).encode("utf-8"),
                              "netscope-probes.csv", "text/csv")
        st.dataframe(frame.drop(columns="session_id"), hide_index=True, width="stretch")
        if not probe_frame.empty:
            st.dataframe(probe_frame.drop(columns="session_id"), hide_index=True, width="stretch")
    with about_tab:
        st.markdown("""
**Traffic:** rate = change in byte counter × 8 ÷ elapsed seconds ÷ 1,000,000.
The first sample, a reset counter, and a reconnected interface need a new baseline.
Adapters are shown separately because VPN and virtual adapter traffic can overlap.

**Latency:** mean round-trip time of successful echo replies in the last batch.
Windows reports integer milliseconds; a local reply may report 0 ms.

**Packet loss:** unanswered echo requests ÷ completed echo requests × 100.
The window card weights each valid batch by its number of requests. Probe execution
errors are excluded. Small batches give coarse estimates; filtered or deprioritized
ICMP can differ from application traffic.

**Scope:** this observes the laptop's interfaces and the route to one IP target.
It does not measure every device on Wi-Fi, identify applications, or run a speed test.
The collector runs in its own terminal; closing this page does not stop recording.
""")


render_measurements()
