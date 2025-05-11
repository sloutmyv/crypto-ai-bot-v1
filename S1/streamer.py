from __future__ import annotations

import json
import os
import sqlite3
import time
import argparse # Ajout de argparse
from datetime import datetime, timezone
from pathlib import Path

import websocket  # websocket‑client (pip install websocket-client)
from config import TESTNET  # lit BINANCE_TESTNET depuis .env (0/1)

# ───────── Constantes (Intervalle peut aussi devenir un argument plus tard si besoin) ─────────
INTERVAL = "1m"

# Les variables globales pour la connexion DB et le symbole seront initialisées dans main()
DB_CONN: sqlite3.Connection | None = None
CURRENT_SYMBOL: str = ""


# ───────── SQLite ─────────
def init_db(symbol: str) -> sqlite3.Connection:
    """Initialise la base de données SQLite et la table pour le symbole donné."""
    safe_symbol = symbol.lower().replace('/', '').replace('-', '')
    db_filename = f"{safe_symbol}_{INTERVAL}_realtime.db" # Nom de fichier dynamique
    db_path = Path("data") / db_filename
    db_path.parent.mkdir(exist_ok=True)

    print(f"🗂️  Database will be at: {db_path}")

    conn = sqlite3.connect(db_path, isolation_level=None) # Pas de check_same_thread pour l'instant, mais à surveiller
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS kline_{safe_symbol} (
            open_time   INTEGER PRIMARY KEY,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      REAL,
            close_time  INTEGER
        )"""
    ) # Nom de table dynamique aussi, ou garder 'kline' si vous préférez une table par DB
      # Pour l'instant, une table nommée d'après le symbole dans un fichier DB nommé d'après le symbole.
      # Si vous voulez une seule table 'kline' par fichier, changez le f-string ci-dessus.
      # Je vais opter pour un nom de table fixe 'kline' pour la simplicité avec le reste du code.
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
    return conn

# ───────── Handler bougie ─────────
def handle_kline(k: dict[str, str]):
    global DB_CONN
    if not DB_CONN:
        print("❌ DB connection not available in handle_kline.")
        return

    if not k.get("x"):  # 'x' est le booléen indiquant si la bougie est clôturée
        return  # bougie pas close

    record = (
        k["t"],  # Kline start time (open_time)
        k["o"],  # Open price
        k["h"],  # High price
        k["l"],  # Low price
        k["c"],  # Close price
        k["v"],  # Base asset volume
        k["T"],  # Kline close time
    )
    try:
        # Utiliser le nom de table fixe 'kline'
        DB_CONN.execute("INSERT OR REPLACE INTO kline VALUES (?,?,?,?,?,?,?)", record)
        ts_close = datetime.fromtimestamp(int(k["T"]) / 1000, tz=timezone.utc)
        print(f"✅ [{CURRENT_SYMBOL.upper()}] {ts_close:%Y-%m-%d %H:%M} candle stored | O:{k['o']} H:{k['h']} L:{k['l']} C:{k['c']} V:{k['v']}")
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e} when inserting record for {CURRENT_SYMBOL}")
    except Exception as e:
        print(f"❌ Error in handle_kline: {e}")


# ───────── WebSocket brut ─────────
def run_ws(symbol_to_stream: str):
    global DB_CONN # Pour pouvoir le fermer proprement
    domain = "testnet.binance.vision" if TESTNET else "stream.binance.com:9443"
    # Le symbole dans l'URL du stream doit être en minuscules
    stream_symbol_lower = symbol_to_stream.lower()
    url = f"wss://{domain}/ws/{stream_symbol_lower}@kline_{INTERVAL}"
    print(f"🔄 Connecting to {url}")

    ws_app = None # Pour pouvoir le fermer

    def on_open(ws):
        print(f"🟢 WS opened for {symbol_to_stream.upper()} — waiting for data…")

    def on_message(ws, raw_message):
        try:
            msg = json.loads(raw_message)
            if "k" in msg: # S'assurer que c'est bien un message kline
                handle_kline(msg["k"])
            # else: print(f"ℹ️  Received non-kline message: {msg}") # Pour débugger d'autres types de messages
        except json.JSONDecodeError:
            print(f"⚠️  Could not decode JSON: {raw_message}")
        except Exception as e:
            print(f"❌ Error processing message: {e} | Raw: {raw_message}")

    def on_error(ws, error):
        print(f"🔴 WS error for {symbol_to_stream.upper()}: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"🟡 WS closed for {symbol_to_stream.upper()} (Code: {close_status_code}, Msg: {close_msg}) — reconnecting in 5s…")
        time.sleep(5)
        # Il faut relancer avec le symbole original
        run_ws(symbol_to_stream) # Appel récursif pour la reconnexion

    ws_app = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    try:
        ws_app.run_forever(ping_interval=20, ping_timeout=10, reconnect=5) # Ajout de l'option reconnect
    except Exception as e:
        print(f"❌ WebSocketApp run_forever error: {e}")
    finally:
        if DB_CONN:
            print(f"Closing DB connection for {symbol_to_stream.upper()}")
            DB_CONN.close()

# ───────── Entrée ─────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binance Kline Streamer to SQLite.")
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT", # Changé le défaut pour un plus commun, mais ETHUSDC est bien aussi
        help="Trading symbol to stream (e.g., BTCUSDT, ETHUSDC). Default: BTCUSDT",
    )
    # Tu pourrais aussi ajouter --interval ici si tu voulais le rendre configurable
    # parser.add_argument("--interval", type=str, default="1m", help="Kline interval (e.g., 1m, 5m, 1h)")

    args = parser.parse_args()

    CURRENT_SYMBOL = args.symbol # Définit le symbole global pour l'affichage
    print(f"▶ Binance Kline Streamer")
    print(f"▶ Config: TESTNET={TESTNET} | SYMBOL={CURRENT_SYMBOL.upper()} | INTERVAL={INTERVAL}")

    try:
        DB_CONN = init_db(CURRENT_SYMBOL)
        run_ws(CURRENT_SYMBOL)  # Boucle bloquante
    except KeyboardInterrupt:
        print(f"\n▶ Interrupted by user. Closing resources for {CURRENT_SYMBOL.upper()}...")
    except Exception as e:
        print(f"❌ An unexpected error occurred in main: {e}")
    finally:
        if DB_CONN:
            print(f"Ensuring DB connection is closed for {CURRENT_SYMBOL.upper()}.")
            DB_CONN.close()
        print("▶ Streamer stopped.")