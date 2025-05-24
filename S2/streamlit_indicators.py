"""
Streamlit app – Interactive TA dashboard for klines.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Launch:
    streamlit run streamlit_app.py

Dependencies:
    pip install streamlit plotly pandas pyarrow
"""

from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta # MODIFIÉ: timedelta importé directement
import datetime # Pour datetime.datetime
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ───────────────────────────── Page config ────────────────────────────────
st.set_page_config(page_title="Trading Dashboard", layout="wide")

DATA_DIR = Path("data")

# ───────────────────────────── File Scanning and Selection ───────────────────

@st.cache_data(ttl=600)
def get_available_ta_files() -> dict:
    # ... (code inchangé pour get_available_ta_files) ...
    ta_files_info = {}
    file_pattern = re.compile(r"^ta_([\w-]+)_([\w\d]+)_(\d+d)_(\d{6})\.parquet$")
    if not DATA_DIR.exists():
        st.error(f"Data directory not found: {DATA_DIR}")
        return {}
    for f_path in DATA_DIR.glob("ta_*.parquet"):
        match = file_pattern.match(f_path.name)
        if match:
            symbol, interval, days_str, gen_date_str = match.groups()
            original_filename_stem = f"{symbol}_{interval}_{days_str}_{gen_date_str}"
            display_name = (
                f"{symbol.upper()} - {interval} - {days_str} "
                f"(Data: {gen_date_fmt(gen_date_str)})"
            )
            ta_files_info[original_filename_stem] = {
                "path": f_path, "display_name": display_name, "symbol": symbol,
                "interval": interval, "days": days_str, "gen_date": gen_date_str
            }
    sorted_items = sorted(ta_files_info.items(), key=lambda item: item[1]['display_name'])
    return {k: v for k, v in sorted_items}

def gen_date_fmt(date_str_yymmdd):
    """Formats YYMMDD string to DD/MM/YY"""
    return f"{date_str_yymmdd[4:6]}/{date_str_yymmdd[2:4]}/{date_str_yymmdd[0:2]}"


available_files_dict = get_available_ta_files()

if not available_files_dict:
    st.error("No 'ta_*.parquet' files found. Run indicators.py script first.")
    st.stop()

st.sidebar.header("File Selection")
file_options_map = {info['display_name']: key for key, info in available_files_dict.items()}
# Utiliser st.session_state pour le fichier sélectionné afin de le préserver lors des interactions avec les boutons
if 'selected_file_display_name' not in st.session_state:
    st.session_state.selected_file_display_name = list(file_options_map.keys())[0] if file_options_map else None

selected_display_name = st.sidebar.selectbox(
    "Select TA File:",
    options=list(file_options_map.keys()),
    key='selected_file_display_name' # Lier au session_state
)

selected_file_key = file_options_map.get(st.session_state.selected_file_display_name)
selected_file_info = available_files_dict.get(selected_file_key) if selected_file_key else None

if not selected_file_info:
    st.error("Could not retrieve file info. Please select a file.")
    st.stop()

# ───────────────────────────── Data loading (cached) ───────────────────────
@st.cache_data(ttl=600)
def load_data(file_path: Path) -> pd.DataFrame:
    # ... (code inchangé pour load_data) ...
    if not file_path.exists():
        st.error(f"Source file not found: {file_path}")
        st.stop()
    df = pd.read_parquet(file_path)
    if "open_dt" in df.columns:
        df["open_dt"] = pd.to_datetime(df["open_dt"], errors="coerce", utc=True)
    elif "open_time" in df.columns:
        df["open_dt"] = pd.to_datetime(df["open_time"], unit="ms", errors="coerce", utc=True)
        st.info("Converted 'open_time' to 'open_dt'.")
    else:
        st.error("Neither 'open_dt' nor 'open_time' column found.")
        st.stop()
    if df["open_dt"].isnull().any():
        st.warning("Some 'open_dt' values were NaT. Rows removed.")
        df = df.dropna(subset=["open_dt"])
    return df

# Charger les données une seule fois par sélection de fichier
# La clé de cache pour load_data est file_path, donc c'est déjà efficace.
df = load_data(selected_file_info["path"])

if df.empty:
    st.error(f"Loaded data is empty for {selected_file_info['display_name']}.")
    st.stop()

# ───────────────────────────── Sidebar – date range picker & Quick Buttons ────────────────
st.sidebar.header("Parameters")

if "open_dt" not in df.columns or df["open_dt"].isnull().all():
    st.error("Critical: 'open_dt' column missing or all invalid after loading.")
    st.stop()

min_date_available = df["open_dt"].min().date()
max_date_available = df["open_dt"].max().date()

# Utiliser st.session_state pour stocker start_date et end_date
# Initialiser si elles n'existent pas ou si le fichier a changé (nécessite une logique de réinitialisation)
# Pour simplifier, on recalcule les défauts à chaque run si le fichier change (implicite car df change)

if 'current_file_key_for_dates' not in st.session_state or \
   st.session_state.current_file_key_for_dates != selected_file_key:
    # Fichier a changé ou première initialisation, réinitialiser les dates
    st.session_state.current_file_key_for_dates = selected_file_key
    default_timedelta = timedelta(days=90)
    calculated_default_start = max_date_available - default_timedelta
    st.session_state.start_date = max(min_date_available, calculated_default_start)
    st.session_state.end_date = max_date_available


# DatePickers liés au session_state
# Note: st.date_input ne met pas directement à jour st.session_state.
# Il faut récupérer sa valeur et la remettre dans session_state si on veut une synchronisation bidirectionnelle complète
# ou utiliser les callbacks on_change (plus complexe pour ce cas simple).
# Ici, on lira simplement la valeur des date_input et mettra à jour session_state via les boutons.

start_date_picker_val = st.sidebar.date_input(
    "Start date",
    value=st.session_state.start_date,
    min_value=min_date_available,
    max_value=max_date_available,
    key="date_picker_start" # Clé unique pour le widget
)
end_date_picker_val = st.sidebar.date_input(
    "End date",
    value=st.session_state.end_date,
    min_value=min_date_available,
    max_value=max_date_available,
    key="date_picker_end" # Clé unique pour le widget
)

# Mettre à jour st.session_state.start_date/end_date avec les valeurs des pickers
# Cela est important si l'utilisateur change les dates manuellement avec les pickers
st.session_state.start_date = start_date_picker_val
st.session_state.end_date = end_date_picker_val


# Quick Range Buttons
st.sidebar.write("Quick Select Range:")
cols = st.sidebar.columns(3)
button_ranges = {
    "1W": timedelta(weeks=1), "1M": timedelta(days=30), "3M": timedelta(days=90),
    "6M": timedelta(days=180), "1Y": timedelta(days=365), "YTD": "ytd", "All": "all"
}

def set_date_range(period_key):
    end = max_date_available
    start = min_date_available # Par défaut pour "All"

    if period_key == "ytd":
        start = date(max_date_available.year, 1, 1)
    elif period_key == "all":
        pass # start est déjà min_date_available
    else: # Cas timedelta
        delta = button_ranges[period_key]
        start = end - delta

    # Assurer que start n'est pas avant la date min disponible
    st.session_state.start_date = max(min_date_available, start)
    st.session_state.end_date = end # end est toujours max_date_available pour ces boutons
    # Il faut forcer un rerun pour que les date_input reflètent le changement de session_state
    # Alternative: utiliser des callbacks sur les boutons (plus propre)
    # Pour une solution simple sans callbacks complexes:
    # Les widgets date_input liront st.session_state au prochain rerun.

button_idx = 0
for name, _ in button_ranges.items():
    with cols[button_idx % 3]:
        if st.button(name, key=f"btn_{name}", use_container_width=True):
            set_date_range(name)
            # st.experimental_rerun() # Force un rerun pour mettre à jour les date_pickers
            # Remplacé par la gestion via session_state qui est lue au début du script pour les date_input

button_idx += 1


# Utiliser les valeurs de st.session_state pour le filtrage
current_start_date = st.session_state.start_date
current_end_date = st.session_state.end_date

if isinstance(current_start_date, date) and not isinstance(current_end_date, date):
    current_end_date = max_date_available
if not current_start_date or not current_end_date:
    st.warning("Please select a valid start and end date.")
    st.stop()
if current_start_date > current_end_date:
    current_start_date, current_end_date = current_end_date, current_start_date

start_datetime_utc = pd.Timestamp(current_start_date, tz='UTC')
end_datetime_utc = pd.Timestamp(current_end_date, tz='UTC')

mask = (df["open_dt"].dt.normalize() >= start_datetime_utc) & \
       (df["open_dt"].dt.normalize() <= end_datetime_utc)
df_view = df.loc[mask].copy()

if df_view.empty:
    st.warning(f"No data for {selected_file_info['symbol'].upper()} between {current_start_date} and {current_end_date}.")
    # Ne pas faire st.stop() ici, laisser le graphique vide ou un message.
    # st.stop() # Commenté pour permettre au reste de l'UI de s'afficher

# ───────────────────────────── Build Plotly figure ────────────────────────
# ... (code inchangé pour la création de la figure Plotly) ...
fig = make_subplots(
    rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
    row_heights=[0.35, 0.15, 0.15, 0.15, 0.2],
    specs=[[{"type": "candlestick"}], [{"type": "scatter"}], [{"type": "scatter"}],
           [{"secondary_y": True}], [{"type": "bar"}]]
)

# Vérifier si df_view est vide avant de tracer pour éviter les erreurs
if not df_view.empty:
    # Row 1 – Candles & overlays
    fig.add_trace(go.Candlestick(x=df_view["open_dt"], open=df_view["open"], high=df_view["high"], low=df_view["low"], close=df_view["close"], name="OHLC"), row=1, col=1)
    if "sma50" in df_view.columns:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["sma50"], line=dict(width=1, color="orange"), name="SMA50"), row=1, col=1)
    if "ema21" in df_view.columns:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view["ema21"], line=dict(width=1, color="green"), name="EMA21"), row=1, col=1)
    bb_upper_col = next((col for col in df_view.columns if col.startswith("BBU_")), None)
    bb_lower_col = next((col for col in df_view.columns if col.startswith("BBL_")), None)
    if bb_upper_col and bb_lower_col:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[bb_upper_col], line=dict(width=0), name="BBU", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[bb_lower_col], line=dict(width=0), fill="tonexty", fillcolor="rgba(176,196,222,0.2)", name="Bollinger", showlegend=True), row=1, col=1)

    # Row 2 – RSI
    rsi_col = next((col for col in df_view.columns if col.startswith("RSI_")), "rsi14")
    if rsi_col in df_view.columns:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[rsi_col], line=dict(color="crimson", width=1), name=rsi_col.upper()), row=2, col=1)
        fig.add_hline(y=70, row=2, col=1, line=dict(dash="dash", width=0.8, color="darkred"))
        fig.add_hline(y=30, row=2, col=1, line=dict(dash="dash", width=0.8, color="darkgreen"))

    # Row 3 – MACD
    macd_line_col = next((col for col in df_view.columns if col.startswith("MACD_") and not col.endswith("signal") and not col.endswith("hist") and not col.startswith("MACDh_") and not col.startswith("MACDs_")), None)
    macd_signal_col = next((col for col in df_view.columns if col.startswith("MACDs_") or (macd_line_col and col == macd_line_col.replace("MACD_","MACDs_") ) or (macd_line_col and col == macd_line_col + "s" )), None)
    if not macd_signal_col : macd_signal_col = next((col for col in df_view.columns if col.startswith("MACD_") and col.endswith("signal")), None)
    macd_hist_col = next((col for col in df_view.columns if col.startswith("MACDh_")), None)
    if macd_line_col and macd_signal_col and macd_hist_col:
        colors = ["green" if v >= 0 else "red" for v in df_view[macd_hist_col]]
        fig.add_trace(go.Bar(x=df_view["open_dt"], y=df_view[macd_hist_col], marker_color=colors, opacity=0.6, name="MACD Hist"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[macd_line_col], line=dict(color="royalblue", width=1), name="MACD"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[macd_signal_col], line=dict(color="orange", width=1), name="Signal"), row=3, col=1)
    # else: # Commenté pour éviter trop de warnings dans la sidebar
        # st.sidebar.warning(f"MACD columns not fully found. Line: {macd_line_col}, Signal: {macd_signal_col}, Hist: {macd_hist_col}")

    # Row 4 – ATR & NATR
    atr_col = next((col for col in df_view.columns if col.startswith("ATR_")), "atr14")
    natr_col = next((col for col in df_view.columns if col.startswith("NATR_")), "natr14")
    if atr_col in df_view.columns:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[atr_col], line=dict(color="royalblue", width=1), name=atr_col.upper()), row=4, col=1)
    if natr_col in df_view.columns:
        fig.add_trace(go.Scatter(x=df_view["open_dt"], y=df_view[natr_col], line=dict(color="tomato", width=1, dash="dash"), name=f"{natr_col.upper()} (%)"), row=4, col=1, secondary_y=True)

    # Row 5 – Volume
    if "volume" in df_view.columns:
        fig.add_trace(go.Bar(x=df_view["open_dt"], y=df_view["volume"], marker_color="#888", name="Volume"), row=5, col=1)
    # else: # Commenté pour éviter trop de messages si volume non présent
        # st.info("Volume data not found.")
else:
    # Afficher un message si df_view est vide, au lieu d'un graphique vide ou d'une erreur
    fig.add_annotation(text="No data to display for the selected period.",
                       xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False,
                       font=dict(size=20))


# Layout
gen_date_fmt_val = selected_file_info['gen_date']
gen_date_display_val = gen_date_fmt(gen_date_fmt_val) # Utiliser la fonction pour formater
fig.update_layout(
    title=f"{selected_file_info['symbol'].upper()} {selected_file_info['interval']} (Data: {gen_date_display_val}) – TA Dashboard",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    autosize=True, height=1100, margin=dict(l=50, r=50, t=80, b=50)
)
fig.update_yaxes(title_text="Price", row=1, col=1, title_standoff=10)
fig.update_yaxes(title_text="RSI", row=2, col=1, title_standoff=10)
fig.update_yaxes(title_text="MACD", row=3, col=1, title_standoff=10)
fig.update_yaxes(title_text="ATR", row=4, col=1, title_standoff=10)
fig.update_yaxes(title_text="NATR (%)", row=4, col=1, secondary_y=True, title_standoff=10)
fig.update_yaxes(title_text="Volume", row=5, col=1, title_standoff=10)


# ───────────────────────────── Display ─────────────────────────────────────
st.title("Trading Indicators Dashboard")
st.info(f"Displaying: {selected_file_info['display_name']}")
st.plotly_chart(fig, use_container_width=True)

if st.checkbox("Show raw data table for selected range", key="cb_raw_data"):
    if not df_view.empty:
        st.dataframe(df_view)
    else:
        st.write("No data in the selected range to display in table.")

if st.checkbox("Show file details", key="cb_file_details"):
    st.json({k: str(v) if isinstance(v, Path) else v for k, v in selected_file_info.items()})