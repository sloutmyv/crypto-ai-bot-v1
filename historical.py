"""
historical.py  –  Télécharge les klines via binance‑connector Spot. 
"""
from __future__ import annotations
import argparse, math, time
from datetime import datetime, timedelta, timezone         # ← timezone aware
from pathlib import Path
import pandas as pd
from config import rest_client

SYMBOL = "BTCUSDC"
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
MAX_LIMIT = 1500
MAX_SPAN_DAYS = 200

def iso_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000)

def fetch_chunk(start: datetime, interval: str) -> pd.DataFrame:
    end = min(start + timedelta(days=MAX_SPAN_DAYS),
              datetime.now(timezone.utc))
    spot = rest_client()
    klines = spot.klines(
        SYMBOL, interval,
        startTime=iso_ms(start),
        endTime=iso_ms(end),
        limit=MAX_LIMIT
    )
    cols = [
        "open_time","open","high","low","close","volume",
        "close_time","quote_asset_volume","nb_trades",
        "taker_buy_base","taker_buy_quote","ignore"
    ]
    df = pd.DataFrame(klines, columns=cols).astype({
        "open_time": "int64",
        "close_time": "int64",
        **{c: "float64" for c in ["open","high","low","close","volume"]}
    })
    df["open_dt"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
    df["close_dt"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df

def main(interval: str, days: int):
    target = DATA_DIR / f"btc_usdc_{interval}.parquet"
    end_date = datetime.now(timezone.utc)                   # ← plus de warning
    start_date = end_date - timedelta(days=days)
    frames, cur = [], start_date
    while cur < end_date:
        print(f"Fetching {cur:%Y-%m-%d} → {(cur+timedelta(days=MAX_SPAN_DAYS)):%Y-%m-%d}")
        frames.append(fetch_chunk(cur, interval))
        time.sleep(0.35)                                    # garde‑fou rate‑limit
        cur += timedelta(days=MAX_SPAN_DAYS)
    full = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
    full.to_parquet(target, index=False)
    print("✅ Saved", len(full), "rows to", target)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1m")
    ap.add_argument("--days", type=int, default=365*3)
    args = ap.parse_args()
    main(args.interval, args.days)
