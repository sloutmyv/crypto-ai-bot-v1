from __future__ import annotations
from datetime import datetime, timedelta, timezone # Assurez-vous que timezone est importé
from pathlib import Path
import time, argparse, pandas as pd
from config import rest_client # Assurez-vous que config.py et rest_client sont accessibles

# SYMBOL n'est plus une constante globale ici, il sera passé en argument
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
            symbol, interval, # Utilisation du symbol passé en argument
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

# Modification de la signature de main pour accepter symbol
def main(symbol: str, interval: str, days: int):
    # Nettoyage du symbole pour le nom de fichier (ex: ETH/USDC -> ethusdc)
    # et construction dynamique du nom de fichier
    safe_symbol = symbol.lower().replace('/', '').replace('-', '')

    # <<< MODIFICATION ICI >>>
    # Obtenir la date actuelle au format YYMMDD
    # Vous pouvez utiliser datetime.now() pour l'heure locale ou datetime.now(timezone.utc) pour UTC.
    # Pour la cohérence avec end_date, utilisons UTC.
    current_date_str = datetime.now(timezone.utc).strftime("%y%m%d")
    filename = f"{safe_symbol}_{interval}_{days}d_{current_date_str}.parquet"
    # <<< FIN MODIFICATION >>>

    target = DATA_DIR / filename

    end_date   = datetime.now(timezone.utc) # Ceci est la date de fin des données, pas nécessairement la date pour le nom du fichier
    start_date = end_date - timedelta(days=days)

    # Utilisation du symbol passé en argument dans le message
    print(f"Downloading {symbol} {interval}  –  {start_date:%Y-%m-%d} → {end_date:%Y-%m-%d}")
    print(f"Target filename: {target}") # Ajout pour vérifier le nom du fichier

    frames = []
    cur_blk = start_date
    while cur_blk < end_date:
        blk_end = min(cur_blk + timedelta(days=MAX_SPAN_DAYS), end_date)
        print(f"  ▸ Block {cur_blk:%Y-%m-%d} → {blk_end:%Y-%m-%d}")
        # Passage du symbol à fetch_interval
        frames.extend(fetch_interval(symbol, interval, cur_blk, blk_end))
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
    ap = argparse.ArgumentParser(description="Télécharge les chandeliers Binance et les sauvegarde en Parquet.")
    # Ajout de l'argument --symbol
    ap.add_argument("--symbol", default="ETHUSDC", help="La paire de trading (ex: BTCUSDT, ETHUSDC). Défaut: ETHUSDC")
    ap.add_argument("--interval", default="1h", help="L'intervalle des chandeliers (ex: 1m, 15m, 1h, 1d). Défaut: 1h")
    ap.add_argument("--days", type=int, default=365, help="Le nombre de jours de données à récupérer. Défaut: 365")
    args = ap.parse_args()

    # Passage des arguments à la fonction main
    main(args.symbol, args.interval, args.days)