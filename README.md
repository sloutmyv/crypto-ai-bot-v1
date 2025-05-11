
# Sprint S1 - Extraire les données de binance
| Fichier | Rôle dans l’architecture | Commandes clés |
|---------|--------------------------|----------------|
| **`config.py`** | Charge le `.env` et fournit :<br>• client REST (`Spot`)<br>• client WebSocket (`SpotWebsocketStreamClient`) | *Aucun lancement direct* – importé par les autres modules |
| **`historical.py`** | Télécharge l’historique de chandeliers pour une **paire spécifiée** (défaut: `ETHUSDC`), un **intervalle** et un nombre de **jours** donnés. Enregistre les données en **Parquet** (ex: `data/ethusdc_1h_365d.parquet`). Gère la pagination de l'API (200 jours / 1000 bougies max par requête). | ```Pour BTCUSDT, 15m, 90 jours:``` <br> ```python S1/historical.py --symbol BTCUSDT --interval 15m --days 90``` |
| **`streamer.py`** | Écoute le flux WebSocket **kline 1 min** pour une **paire spécifiée** (défaut: `BTCUSDT`) en temps réel. Insère/met à jour les bougies dans un fichier **SQLite dédié** (ex: `data/btcusdt_1m_realtime.db`). | ```bash# Pour BTCUSDT (défaut):``` <br> ```python S1/streamer.py``` <br><br> ```bash# Pour ETHUSDC:``` <br> ```python S1/streamer.py --symbol ETHUSDC``` <br> *(boucle continue, Ctrl‑C pour arrêter)* |
| **`visualize_price_volume.ipynb`** | Notebook Jupyter pour visualiser interactivement le **prix de clôture** et le **volume** à partir des fichiers Parquet générés par `historical.py`. Permet de sélectionner le fichier de données et une plage de dates. | Ouvrir et exécuter les cellules dans Jupyter Notebook/Lab.<br>Ex : `jupyter notebook S1/notebooks/visualize_price_volume.ipynb` |
| **`tests/test_S1.py`** | Tests (pytest) pour S1 :<br>• Vérifie la création et la structure de base du fichier Parquet généré par `historical.py`.<br>• Vérifie la création du fichier SQLite et la structure de la table `kline` par `streamer.py`. | ```pytest tests/test_S1.py``` <br>ou ```pytest tests/``` |

# Sprint S2 - Calcul des indicateurs techniques
| Fichier | Objectif / rôle | Commande principale |
|---------|-----------------|---------------------|
| **`indicators.py`** | *Pipeline* : lit les chandeliers Parquet générés au Sprint S1 (ex: `data/ethusdc_1h_365d.parquet`), calcule SMA 50, EMA 21, RSI 14, MACD (12‑26‑9), Bollinger Bands et enregistre le résultat dans `data/<symb>_<interval>_<days>d_ta.parquet`. | ```bash# S'assure d'abord que les données historiques existent, ex:``` <br> ```python S1/historical.py --symbol ETHUSDC --interval 1h --days 365``` <br> ```bash# Puis calcule les indicateurs:``` <br> ```python S2/indicators.py --symbol ETHUSDC --interval 1h --days 365``` <br> *(Adapter `--symbol`, `--interval`, `--days` selon le fichier source)* |
| **`tests/test_indicators.py`** | *Smoke‑test* : vérifie que le fichier TA existe, que les colonnes clés (`sma50`, `ema21`, `rsi14`, `MACD_12_26_9`, `BBU_20_2.0`) sont présentes et qu’il n’y a plus de NaN après la période d’amorçage. | `pytest tests/test_indicators.py` |
| **`preview.py`** | *Visualisation rapide* : trace dans Matplotlib (ou Jupyter) :<br>1) prix + SMA/EMA + bandes de Bollinger,<br>2) RSI 14 avec zones 30/70,<br>3) MACD + histogramme.<br> **Doit être adapté pour charger les nouveaux noms de fichiers.** | ```python S2/preview.py --symbol ETHUSDC --interval 1h --days 365 --rows 1000``` <br> *(Adapter les paramètres pour correspondre au fichier `_ta.parquet` à visualiser)* |
| **`preview_streamlit.py`** | *Interactive app* : visualises OHLCV data **plus technical indicators** (SMA 50, EMA 21, Bollinger Bands, RSI 14, MACD 12‑26‑9, ATR 14 & NATR 14 %) and volume.<br> **Doit être adapté pour charger les nouveaux noms de fichiers.** | ```streamlit run S2/preview_streamlit.py -- --symbol ethusdc --interval 1h --days 365``` <br> *(Note: les arguments après `--` sont passés à `preview_streamlit.py`. Adapter pour correspondre au fichier `_ta.parquet`)* |


# Feuille de route :
| Sprint | Objectif principal | Livrables clés |
|--------|-------------------|----------------|
| **S0 — Bootstrap** | Poser l’environnement : repo Git, venv Python 3.12, dépendances de base, README, clés API dans `.env`. | • Repo initial<br>• README (+ archi)<br>• Smoke‑test imports |
| **S1 — Collecte données** | Obtenir l’historique (configurable par **symbole, intervalle, période**) + flux temps réel (symbole à configurer) via Binance. | • `historical.py` (REST, **configurable symbol & period**)<br>• `streamer.py` (WS raw, SQLite)<br>• Parquets (ex: **`ethusdc_1h_365d.parquet`**) & DB<br>• Tests de remplissage |
| **S2 — Indicateurs techniques** | Calculer SMA / EMA / RSI / MACD / Bollinger et créer un dataset enrichi **à partir des données du S1**. | • `indicators.py` (**adapté pour les nouveaux noms de fichiers**)<br>• Parquet *_ta* (ex: **`ethusdc_1h_365d_ta.parquet`**)<br>• Tests indicateurs<br>• Notebooks/scripts de visualisation (**adaptés**) |
| **S3 — Sentiment LLM** | Pipeline qui interroge Crypto‑news + X/Twitter, classe « bullish/neutral/bearish » via LLM, produit un `sentiment_score` horodaté. | • `sentiment.py` (ingest + LLM)<br>• Parquet sentiment<br>• Tests classification |
| **S4 — Fusion signaux** | Combiner règles TA + sentiment pour générer des signaux d’achat/vente paramétrables. | • `decision.py` (rules YAML)<br>• Tests unitaires règles |
| **S5 — Backtesting** | Évaluer la stratégie sur plusieurs années ; métriques : CAGR, Sharpe, Max DD. | • `backtest.py` (vectorbt)<br>• Rapport HTML/Notebook<br>• Script Optuna hyper‑param |
| **S6 — Gestion du risque** | Position sizing (fix %, ATR stop‑loss, Kelly) + drawdown kill‑switch. | • `risk.py`<br>• Tests de stress<br>• Alertes webhook |
| **S7 — Paper‑trading** | Exécuter la strat sur le testnet Binance, journaliser les ordres. | • `executor.py` (testnet)<br>• Log JSON + alertes |
| **S8 — Production locale 24/7** | Service de trading réel (spot/marge) tournant en continu sur Mac/VPS. | • Script daemon + auto‑restart<br>• Dashboard Streamlit |
| **S9 — Durcissement & Cloud** | Dockerisation, déploiement sur serveur, monitoring Prometheus/Grafana. | • `Dockerfile` + docker‑compose<br>• Grafana dashboards |