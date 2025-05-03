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
| **`indicators.py`** | *Pipeline* : lit les chandeliers Parquet générés au Sprint S1, calcule SMA 50, EMA 21, RSI 14, MACD (12‑26‑9), Bollinger Bands et enregistre le résultat dans `data/<symb>_<interval>_ta.parquet`. | `python indicators.py --interval 1m`<br>(adapter `--interval` : `15m`, `1h`, etc.) |
| **`tests/test_indicators.py`** | *Smoke‑test* : vérifie que le fichier TA existe, que les colonnes clés (`sma50`, `ema21`, `rsi14`, `MACD_12_26_9`, `BBU_20_2.0`) sont présentes et qu’il n’y a plus de NaN après la période d’amorçage. | `pytest tests/test_indicators.py` |
| **`preview.py`** | *Visualisation rapide* : trace dans Matplotlib (ou Jupyter) :<br>1) prix + SMA/EMA + bandes de Bollinger,<br>2) RSI 14 avec zones 30/70,<br>3) MACD + histogramme. | `python preview.py --interval 1m --rows 1000` |