"""
indicators.py – Compute TA features for BTC/USDC klines.

requirements:
    pip install pandas ta-lib pandas-ta tqdm
"""

from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd
import pandas_ta as ta
from tqdm.auto import tqdm

DATA_DIR = Path("data")
SYMBOL   = "btc_usdc"  # adapt if you switched to btcusdt
DEFAULT_INTERVAL = "1h"

def compute_ta(df: pd.DataFrame) -> pd.DataFrame:
    """Add TA columns to the OHLCV DataFrame in‑place and return it.

    Nouveautés (2025‑05‑04)
    ----------------------
    • `atr14`  : Average True Range (volatilité absolue)
    • `natr14` : ATR normalisé en % (volatilité relative)
    """

    # 1. Moyennes mobiles
    df["sma50"] = ta.sma(df["close"], length=50)  # moyenne arithmétique
    df["ema21"] = ta.ema(df["close"], length=21)  # moyenne exponentielle

    # 2. RSI
    df["rsi14"] = ta.rsi(df["close"], length=14)

    # 3. MACD — on concatène le résultat
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # 4. Bollinger Bands — idem
    bb = ta.bbands(df["close"], length=20, std=2)
    df = pd.concat([df, bb], axis=1)

    # 5. Volatilité : ATR & NATR
    df["atr14"]  = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["natr14"] = ta.natr(df["high"], df["low"], df["close"], length=14)

    return df


def main(interval: str):
    src = DATA_DIR / f"{SYMBOL}_{interval}.parquet"
    if not src.exists():
        raise FileNotFoundError(src)
    dst = DATA_DIR / f"{SYMBOL}_{interval}_ta.parquet"

    df = pd.read_parquet(src)
    print(f"Loaded {len(df):,} rows – computing TA …")
    df_ta = compute_ta(df).dropna().reset_index(drop=True)

    df_ta.to_parquet(dst, index=False)
    print(f"✅ saved {dst} with {len(df_ta.columns)} columns, {len(df_ta):,} rows")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", default=DEFAULT_INTERVAL, help="1m / 15m / 1h / 1d …")
    args = p.parse_args()
    main(args.interval)
