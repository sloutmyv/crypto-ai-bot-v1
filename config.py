from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from binance.spot import Spot as Client                     # ← import corrigé
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient

load_dotenv()
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TESTNET            = bool(int(os.getenv("BINANCE_TESTNET", "0")))

def rest_client() -> Client:
    base = "https://testnet.binance.vision" if TESTNET else "https://api.binance.com"
    return Client(api_key=BINANCE_API_KEY,
                  api_secret=BINANCE_API_SECRET,
                  base_url=base)

def ws_client(on_msg):
    url = "wss://testnet.binance.vision/ws" if TESTNET else None
    return SpotWebsocketStreamClient(on_message=on_msg, stream_url=url)
