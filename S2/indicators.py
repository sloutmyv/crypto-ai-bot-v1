"""
indicators.py – Compute TA features for klines.

requirements:
    pip install pandas ta-lib pandas-ta tqdm
"""

from __future__ import annotations
import argparse
from pathlib import Path
import re # Pour la validation du nom de fichier

import pandas as pd
import pandas_ta as ta # pandas-ta importe ta-lib si disponible
from tqdm.auto import tqdm

DATA_DIR = Path("data")
# Les constantes SYMBOL et DEFAULT_INTERVAL ne sont plus nécessaires ici
# car nous allons scanner le répertoire.

def compute_ta(df: pd.DataFrame) -> pd.DataFrame:
    """Add TA columns to the OHLCV DataFrame and return it.
    Note: Modifié pour retourner un nouveau DataFrame au lieu de modifier in-place.
    """
    # Créer une copie pour éviter les SettingWithCopyWarning et pour être explicite
    df_ta = df.copy()

    # 1. Moyennes mobiles
    df_ta["sma50"] = ta.sma(df_ta["close"], length=50)
    df_ta["ema21"] = ta.ema(df_ta["close"], length=21)

    # 2. RSI
    df_ta["rsi14"] = ta.rsi(df_ta["close"], length=14)

    # 3. MACD — on concatène le résultat
    macd = ta.macd(df_ta["close"], fast=12, slow=26, signal=9)
    df_ta = pd.concat([df_ta, macd], axis=1)

    # 4. Bollinger Bands — idem
    bb = ta.bbands(df_ta["close"], length=20, std=2)
    df_ta = pd.concat([df_ta, bb], axis=1)

    # 5. Volatilité : ATR & NATR
    df_ta["atr14"]  = ta.atr(df_ta["high"], df_ta["low"], df_ta["close"], length=14)
    df_ta["natr14"] = ta.natr(df_ta["high"], df_ta["low"], df_ta["close"], length=14)
    
    # Il est préférable de supprimer les NaN après tous les calculs.
    # dropna() va supprimer les lignes où *au moins un* des indicateurs est NaN,
    # ce qui est généralement ce que l'on veut car les indicateurs ont des "warm-up periods".
    df_ta = df_ta.dropna().reset_index(drop=True)

    return df_ta


def main(overwrite: bool):
    print(f"Scanning for Parquet files in {DATA_DIR}...")
    
    # Regex pour identifier les fichiers sources valides:
    # exemple: btcusdc_1h_365d_240525.parquet
    # 1. Ne commence pas par "ta_"
    # 2. Structure symbol_interval_daysd_YYMMDD.parquet
    source_file_pattern = re.compile(r"^(?!ta_)([\w-]+)_([\w\d]+)_(\d+d)_(\d{6})\.parquet$")
    
    files_to_process = []
    for f_path in DATA_DIR.glob("*.parquet"):
        match = source_file_pattern.match(f_path.name)
        if match:
            files_to_process.append(f_path)

    if not files_to_process:
        print("No source Parquet files found matching the pattern (e.g., symbol_interval_daysd_YYMMDD.parquet).")
        return

    print(f"Found {len(files_to_process)} source file(s) to process.")

    processed_count = 0
    skipped_count = 0

    for src_path in tqdm(files_to_process, desc="Processing files"):
        # Construire le nom du fichier de destination
        # Le nom du fichier source est src_path.name
        # Le nom du fichier destination sera "ta_" + src_path.name
        dst_path = DATA_DIR / f"ta_{src_path.name}"

        if dst_path.exists() and not overwrite:
            tqdm.write(f"⏭️  Skipping {src_path.name}, target {dst_path.name} already exists. Use --overwrite to recompute.")
            skipped_count += 1
            continue
        
        tqdm.write(f"⚙️ Processing {src_path.name}...")
        try:
            df = pd.read_parquet(src_path)
            if df.empty:
                tqdm.write(f"⚠️  Skipping {src_path.name} as it is empty.")
                continue

            # Vérifier les colonnes nécessaires pour pandas-ta (au minimum high, low, close)
            required_cols = {'high', 'low', 'close'}
            if not required_cols.issubset(df.columns):
                tqdm.write(f"⚠️  Skipping {src_path.name}: missing one or more required columns ({required_cols}). Found: {df.columns.tolist()}")
                continue

            tqdm.write(f"  Loaded {len(df):,} rows – computing TA features…")
            df_with_ta = compute_ta(df)

            if df_with_ta.empty:
                tqdm.write(f"⚠️  Resulting DataFrame for {src_path.name} is empty after TA computation and dropna (possibly due to insufficient data for indicator warm-up).")
                continue

            df_with_ta.to_parquet(dst_path, index=False)
            tqdm.write(f"✅ Saved {dst_path} with {len(df_with_ta.columns)} columns, {len(df_with_ta):,} rows")
            processed_count += 1
        except FileNotFoundError:
            tqdm.write(f"❌ Error: Source file {src_path} not found during processing loop (should not happen if scan was correct).")
        except Exception as e:
            tqdm.write(f"❌ Error processing {src_path.name}: {e}")
            # Optionnel: supprimer le fichier destination partiel s'il a été créé
            if dst_path.exists():
                try:
                    dst_path.unlink()
                    tqdm.write(f"  Partial destination file {dst_path.name} removed.")
                except Exception as del_e:
                    tqdm.write(f"  Could not remove partial destination file {dst_path.name}: {del_e}")


    print("\n--- Summary ---")
    print(f"Total files processed: {processed_count}")
    print(f"Total files skipped (already exist): {skipped_count}")
    print(f"Total source files found: {len(files_to_process)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Compute Technical Analysis features for Parquet kline files.")
    p.add_argument(
        "--overwrite",
        action="store_true", # Crée une option booléenne, True si présente
        help="Overwrite existing TA files if they already exist."
    )
    # L'argument --interval n'est plus nécessaire car on traite tous les fichiers correspondants
    args = p.parse_args()
    
    if not DATA_DIR.exists():
        print(f"❌ Error: Data directory {DATA_DIR} does not exist. Please create it or check the path.")
    else:
        main(args.overwrite)