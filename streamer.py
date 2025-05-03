"""
streamer.py – Binance kline listener (raw WebSocket only)
---------------------------------------------------------
Écoute les bougies **1 min** d’un symbole via WebSocket public et stocke les
bougies fermées dans SQLite.

Avantages :
* Pas de dépendance au SDK `binance‑connector`, uniquement `websocket-client`.
* Fonctionne immédiatement en prod (`stream.binance.com`) et sur le testnet
  (`testnet.binance.vision`) si `BINANCE_TESTNET=1` dans le `.env`.
"""

from __future__ import annotations

import json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

import websocket  # websocket‑client (pip install websocket-client)
from config import TESTNET  # lit BINANCE_TESTNET depuis .env (0/1)

# ───────── Paramètres ─────────
SYMBOL   = os.getenv("WS_SYMBOL", "btcusdc").lower()
INTERVAL = "1m"  # changerez en "5m", "1h"… si besoin
DB_PATH  = Path("data/realtime.db"); DB_PATH.parent.mkdir(exist_ok=True)

print(f"▶ TESTNET={TESTNET} | SYMBOL={SYMBOL}")

# ───────── SQLite ─────────
conn = sqlite3.connect(DB_PATH, isolation_level=None)
conn.execute(
    """CREATE TABLE IF NOT EXISTS kline (
        open_time   INTEGER PRIMARY KEY,
        open        REAL,
        high        REAL,
        low         REAL,
        close       REAL,
        volume      REAL,
        close_time  INTEGER
    )"""
)

# ───────── Handler bougie ─────────

def handle_kline(k: dict[str, str]):
    if not k.get("x"):
        return  # bougie pas close
    record = (
        k["t"], k["o"], k["h"], k["l"], k["c"], k["v"], k["T"]
    )
    conn.execute("INSERT OR REPLACE INTO kline VALUES (?,?,?,?,?,?,?)", record)
    ts = datetime.fromtimestamp(k["T"] / 1000, tz=timezone.utc)
    print(f"✅ {ts:%Y-%m-%d %H:%M} candle stored | vol={k['v']}")

# ───────── WebSocket brut ─────────

def run_ws():
    domain = "testnet.binance.vision" if TESTNET else "stream.binance.com:9443"
    url    = f"wss://{domain}/ws/{SYMBOL}@kline_{INTERVAL}"
    print("🔄 Connecting to", url)

    def on_open(ws):
        print("🟢 WS opened — waiting for data…")

    def on_message(ws, raw):  # noqa: N802
        try:
            msg = json.loads(raw)
            handle_kline(msg["k"])
        except Exception as e:
            print("msg error", e)

    def on_error(ws, err):  # noqa: N802
        print("WS error", err)

    def on_close(ws, *_):  # noqa: N802
        print("WS closed — reconnecting in 5 s…"); time.sleep(5); run_ws()

    wsapp = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    wsapp.run_forever(ping_interval=20, ping_timeout=10)

# ───────── Entrée ─────────

if __name__ == "__main__":
    try:
        run_ws()  # boucle bloquante
    except KeyboardInterrupt:
        print("▶ interrupted by user")
        conn.close()
