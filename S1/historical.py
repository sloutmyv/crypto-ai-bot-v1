"""
historical.py – Télécharge les chandeliers Binance sans en perdre.
* Télécharge par tranches de MAX_SPAN_DAYS (200 j) ;
* À l’intérieur d’une tranche, boucle tant que l’API renvoie MAX_LIMIT (=1 000)
  bougies, en avançant le curseur startTime d’1 ms après la dernière bougie.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time, argparse, pandas as pd
from config import rest_client

SYMBOL          = "BTCUSDC"
DATA_DIR        = Path("data"); DATA_DIR.mkdir(exist_ok=True)
MAX_LIMIT       = 1000                   # limite officielle de l’API
MAX_SPAN_DAYS   = 200

COLUMNS = [
    "open_time","open","high","low","close","volume",
    "close_time","quote_asset_volume","nb_trades",
    "taker_buy_base","taker_buy_quote","ignore"
]

def iso_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000)

def fetch_interval(symbol: str, interval: str,
                   start: datetime, end: datetime) -> list[pd.DataFrame]:
    """Récupère toutes les bougies entre start et end (boucle interne)."""
    spot = rest_client()
    frames = []
    cur = start
    while cur < end:
        kl = spot.klines(
            symbol, interval,
            startTime=iso_ms(cur),
            endTime=iso_ms(end),
            limit=MAX_LIMIT
        )
        if not kl:          # plus de données
            break
        df = (pd.DataFrame(kl, columns=COLUMNS)
                .astype({"open_time":"int64","close_time":"int64",
                         **{c:"float64" for c in ["open","high","low","close","volume"]}}))
        frames.append(df)
        if len(kl) < MAX_LIMIT:
            break           # bloc terminé
        # avancer 1 ms après la dernière close_time récupérée
        last_close_ms = int(df.iloc[-1]["close_time"])
        cur = datetime.fromtimestamp((last_close_ms + 1) / 1000, tz=timezone.utc)
        time.sleep(0.25)    # garde‑fou limite poids
    return frames

def main(interval: str, days: int):
    target = DATA_DIR / f"btc_usdc_{interval}.parquet"
    end_date   = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    print(f"Downloading {SYMBOL} {interval}  –  {start_date:%Y-%m-%d} → {end_date:%Y-%m-%d}")

    frames = []
    cur_blk = start_date
    while cur_blk < end_date:
        blk_end = min(cur_blk + timedelta(days=MAX_SPAN_DAYS), end_date)
        print(f"  ▸ Block {cur_blk:%Y-%m-%d} → {blk_end:%Y-%m-%d}")
        frames.extend(fetch_interval(SYMBOL, interval, cur_blk, blk_end))
        cur_blk = blk_end
        time.sleep(0.35)

    if not frames:
        print("❌ Aucun kline récupéré.")
        return

    full = (pd.concat(frames, ignore_index=True)
              .drop_duplicates("open_time")
              .sort_values("open_time")
              .reset_index(drop=True))

    full["open_dt"]  = pd.to_datetime(full["open_time"],  unit="ms", utc=True)
    full["close_dt"] = pd.to_datetime(full["close_time"], unit="ms", utc=True)

    full.to_parquet(target, index=False)
    print(f"✅ Saved {len(full):,} rows to {target}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1h", help="1m / 15m / 1h / 1d …")
    ap.add_argument("--days", type=int, default=365, help="Nb de jours à récupérer")
    args = ap.parse_args()
    main(args.interval, args.days)
