# streamer.py – version corrigée (sync, plus simple)
import json, sqlite3, time
from datetime import datetime, timezone
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from config import TESTNET

DB       = "data/realtime.db"
SYMBOL   = "btcusdc"
INTERVAL = "1m"

# ----- initialisation DB (sync) -----
conn = sqlite3.connect(DB, isolation_level=None)       # auto‑commit
conn.execute("""CREATE TABLE IF NOT EXISTS kline (
    open_time   INTEGER PRIMARY KEY,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      REAL,
    close_time  INTEGER
)""")

# ----- callback -----
def on_message(ws, raw):            # ← 2 paramètres !
    payload = json.loads(raw)
    if "data" not in payload:       # ignore pings
        return
    k = payload["data"]["k"]
    if not k["x"]:                  # bougie pas close
        return

    rec = (k["t"], k["o"], k["h"], k["l"], k["c"], k["v"], k["T"])
    conn.execute("INSERT OR REPLACE INTO kline VALUES (?,?,?,?,?,?,?)", rec)

    ts = datetime.fromtimestamp(k["T"]/1000, tz=timezone.utc)
    print(f"{ts:%Y-%m-%d %H:%M} candle stored")

# ----- lancement WS -----
if __name__ == "__main__":
    if TESTNET:
        base_ws = "wss://testnet.binance.vision"   # sans /ws
        ws = SpotWebsocketStreamClient(on_message=on_message,
                                       stream_url=base_ws)
    else:
        ws = SpotWebsocketStreamClient(on_message=on_message)

    ws.kline(symbol=SYMBOL, interval=INTERVAL)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        ws.stop()
        conn.close()
        print("▶ stream closed")
