"""
Streamlit app – Interactive TA dashboard for BTC/USDC
====================================================

Launch :
    streamlit run streamlit_app.py -- --symbol btc_usdc --interval 1h

Required packages :
    pip install streamlit plotly pandas pyarrow        # parquet I/O
    # (your df already contains TA columns; if not, add pandas-ta)
"""

from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ───────────────────────────── CLI (for symbol/interval) ─────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--symbol", default="btc_usdc")
parser.add_argument("--interval", default="1h")
cli_args, _ = parser.parse_known_args()

# ───────────────────────────── Config & data loading ─────────────────────────
DATA_DIR = Path("data")

@st.cache_data(ttl=600)
def load_data(symbol: str, interval: str) -> pd.DataFrame:
    src = DATA_DIR / f"{symbol}_{interval}_ta.parquet"
    if not src.exists():
        st.error(f"Source file not found: {src}")
        st.stop()
    df = pd.read_parquet(src)
    # Ensure datetime index/column
    if "open_dt" in df.columns:
        df["open_dt"] = pd.to_datetime(df["open_dt"])
    else:
        df["open_dt"] = pd.to_datetime(df.index)
    return df

df = load_data(cli_args.symbol, cli_args.interval)

# ───────────────────────────── Sidebar controls ──────────────────────────────
st.sidebar.header("Settings")
period = st.sidebar.selectbox("Display last …", [100, 500, 1000, 5000, "All"], index=1)
if period != "All":
    df_view = df.tail(int(period))
else:
    df_view = df

# ───────────────────────────── Build Plotly figure ───────────────────────────
fig = make_subplots(
    rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
    row_heights=[0.35, 0.15, 0.15, 0.15, 0.2],
    specs=[[{"type": "candlestick"}], [{"type": "scatter"}], [{"type": "scatter"}],
           [{"type": "scatter"}], [{"type": "bar"}]]
)

# Row 1 – Candles
fig.add_trace(
    go.Candlestick(
        x=df_view["open_dt"],
        open=df_view["open"], high=df_view["high"],
        low=df_view["low"], close=df_view["close"], name="OHLC"),
    row=1, col=1
)
# Overlay: SMA50, EMA21, Bollinger
if "sma50" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["sma50"],
                             line=dict(width=1, color="orange"), name="SMA50"), row=1, col=1)
if "ema21" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["ema21"],
                             line=dict(width=1, color="green"), name="EMA21"), row=1, col=1)
if "BBU_20_2.0" in df_view.columns and "BBL_20_2.0" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["BBU_20_2.0"],
                             line=dict(width=0), name="BBU", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["BBL_20_2.0"],
                             line=dict(width=0), fill="tonexty", fillcolor="rgba(176,196,222,0.2)",
                             name="Bollinger", showlegend=True), row=1, col=1)

# Row 2 – RSI
if "rsi14" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["rsi14"],
                             line=dict(color="crimson", width=1), name="RSI14"), row=2, col=1)
    fig.add_hline(y=70, row=2, col=1, line=dict(dash="dash", width=0.8, color="darkred"))
    fig.add_hline(y=30, row=2, col=1, line=dict(dash="dash", width=0.8, color="darkgreen"))

# Row 3 – MACD
if "MACD_12_26_9" in df_view.columns:
    colors = ["green" if v >= 0 else "red" for v in df_view["MACDh_12_26_9"]]
    fig.add_trace(go.Bar(x=df_view["open_dt"], y=df_view["MACDh_12_26_9"],
                         marker_color=colors, opacity=0.6, name="MACD hist"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["MACD_12_26_9"],
                             line=dict(color="royalblue", width=1), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["MACDs_12_26_9"],
                             line=dict(color="orange", width=1), name="Signal"), row=3, col=1)

# Row 4 – ATR & NATR (secondary axis)
if "atr14" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["atr14"],
                             line=dict(color="royalblue", width=1), name="ATR14"), row=4, col=1)
if "natr14" in df_view.columns:
    fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["natr14"],
                             line=dict(color="tomato", width=1, dash="dash"), name="NATR14 (%)",
                             yaxis="y4"), row=4, col=1)

# Row 5 – Volume
fig.add_trace(go.Bar(x=df_view["open_dt"], y=df_view["volume"],
                     marker_color="#888", name="Volume"), row=5, col=1)

# Layout tweaks
fig.update_layout(
    title=f"{cli_args.symbol.upper()} {cli_args.interval} – Interactive TA dashboard",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", y=1.02, x=0),
    height=900,
)
# Secondary y‑axis for NATR
fig.update_yaxes(title_text="ATR", row=4, col=1)
fig.update_yaxes(title_text="NATR (%)", row=4, col=1, secondary_y=True)

# ───────────────────────────── Streamlit display ─────────────────────────────
st.title("Trading Indicators Dashboard")
st.plotly_chart(fig, use_container_width=True)
