# crypto-ai-bot-v1

## Python

Python
```
python3 --version          # affiche la version actuellement active
which python3              # montre son emplacement
brew --version             # vérifie Homebrew
git --version              # vérifie Git
brew uninstall python@3.13 # retire le Python Homebrew s’il est en 3.13
```

## Installation de Python 3.12 avec pyenv

```
brew install pyenv
echo 'eval "$(pyenv init --path)"' >> ~/.zprofile
exec $SHELL                   # recharge le shell
pyenv versions
pyenv install 3.12.3
pyenv global 3.12.3
python --version              # doit maintenant afficher 3.12.3
```

## Création du projet et de l’environnement virtuel

```
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

# Sprint S1 - Extraire les données de binance
| Fichier | Rôle dans l’architecture | Commandes clés |
|---------|--------------------------|----------------|
| **`config.py`** | Charge le `.env` et fournit :<br>• client REST (`Spot`)<br>• client WebSocket (`SpotWebsocketStreamClient`) | *Aucun lancement direct* – importé par les autres modules |
| **`historical.py`** | Télécharge l’historique de chandeliers **BTCUSDC** (par pas de 200 j / 1500 bougies) et l’enregistre en **Parquet** | ```python historical.py --interval 1m --days 1095  \npython historical.py --interval 1h --days 1825       # 5 ans, 1 h\n``` |
| **`streamer.py`** | Écoute le flux WebSocket **kline 1 min** en temps réel et insère / met à jour les bougies dans **SQLite (data/realtime.db)** | ```python streamer.py          # boucle continue, Ctrl‑C pour arrêter\n``` |
| *(optionnel)* **`tests/test_data.py`** | Smoke‑tests : vérifie que le Parquet existe et que la table SQLite reçoit des lignes | ```pytest tests/``` |

# Sprint S2 - Calcul des indicateurs techniques
| Fichier | Objectif / rôle | Commande principale |
|---------|-----------------|---------------------|
| **`indicators.py`** | *Pipeline* : lit les chandeliers Parquet générés au Sprint S1, calcule SMA 50, EMA 21, RSI 14, MACD (12‑26‑9), Bollinger Bands et enregistre le résultat dans `data/<symb>_<interval>_ta.parquet`. | `python S2/indicators.py --interval 1h`<br>(adapter `--interval` : `15m`, `1h`, etc.) |
| **`tests/test_indicators.py`** | *Smoke‑test* : vérifie que le fichier TA existe, que les colonnes clés (`sma50`, `ema21`, `rsi14`, `MACD_12_26_9`, `BBU_20_2.0`) sont présentes et qu’il n’y a plus de NaN après la période d’amorçage. | `pytest tests/test_indicators.py` |
| **`preview.py`** | *Visualisation rapide* : trace dans Matplotlib (ou Jupyter) :<br>1) prix + SMA/EMA + bandes de Bollinger,<br>2) RSI 14 avec zones 30/70,<br>3) MACD + histogramme. | `python preview.py --interval 1m --rows 1000` |
| **`preview_streamlit.py `** | *Interactive app* : visualises OHLCV data **plus technical indicators** (SMA 50, EMA 21, Bollinger Bands, RSI 14, MACD 12‑26‑9, ATR 14 & NATR 14 %) and volume. :<br>1) prix + SMA/EMA + bandes de Bollinger,<br>2) RSI 14 avec zones 30/70,<br>3) MACD + histogramme. | `streamlit run spreview_streamlit.py -- --symbol btc_usdc --interval ` |


# Feuille de route : 
| Sprint | Objectif principal | Livrables clés |
|--------|-------------------|----------------|
| **S0 — Bootstrap** | Poser l’environnement : repo Git, venv Python 3.12, dépendances de base, README, clés API dans `.env`. | • Repo initial<br>• README (+ archi)<br>• Smoke‑test imports |
| **S1 — Collecte données** | Obtenir l’historique + flux temps réel BTC/USDC (spot) via Binance. | • `historical.py` (REST)<br>• `streamer.py` (WS raw, SQLite)<br>• Parquets & DB<br>• Tests de remplissage |
| **S2 — Indicateurs techniques** | Calculer SMA / EMA / RSI / MACD / Bollinger et créer un dataset enrichi. | • `indicators.py`<br>• Parquet *_ta*<br>• Tests indicateurs<br>• Notebooks de visualisation |
| **S3 — Sentiment LLM** | Pipeline qui interroge Crypto‑news + X/Twitter, classe « bullish/neutral/bearish » via LLM, produit un `sentiment_score` horodaté. | • `sentiment.py` (ingest + LLM)<br>• Parquet sentiment<br>• Tests classification |
| **S4 — Fusion signaux** | Combiner règles TA + sentiment pour générer des signaux d’achat/vente paramétrables. | • `decision.py` (rules YAML)<br>• Tests unitaires règles |
| **S5 — Backtesting** | Évaluer la stratégie sur plusieurs années ; métriques : CAGR, Sharpe, Max DD. | • `backtest.py` (vectorbt)<br>• Rapport HTML/Notebook<br>• Script Optuna hyper‑param |
| **S6 — Gestion du risque** | Position sizing (fix %, ATR stop‑loss, Kelly) + drawdown kill‑switch. | • `risk.py`<br>• Tests de stress<br>• Alertes webhook |
| **S7 — Paper‑trading** | Exécuter la strat sur le testnet Binance, journaliser les ordres. | • `executor.py` (testnet)<br>• Log JSON + alertes |
| **S8 — Production locale 24/7** | Service de trading réel (spot/marge) tournant en continu sur Mac/VPS. | • Script daemon + auto‑restart<br>• Dashboard Streamlit |
| **S9 — Durcissement & Cloud** | Dockerisation, déploiement sur serveur, monitoring Prometheus/Grafana. | • `Dockerfile` + docker‑compose<br>• Grafana dashboards |