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

# Sprint S1
| Fichier | Rôle dans l’architecture | Commandes clés |
|---------|--------------------------|----------------|
| **`config.py`** | Charge le `.env` et fournit :<br>• client REST (`Spot`)<br>• client WebSocket (`SpotWebsocketStreamClient`) | *Aucun lancement direct* – importé par les autres modules |
| **`historical.py`** | Télécharge l’historique de chandeliers **BTCUSDC** (par pas de 200 j / 1500 bougies) et l’enregistre en **Parquet** | ```bash\npython historical.py --interval 1m --days 1095   # 3 ans, 1 min\npython historical.py --interval 1h --days 1825       # 5 ans, 1 h\n``` |
| **`streamer.py`** | Écoute le flux WebSocket **kline 1 min** en temps réel et insère / met à jour les bougies dans **SQLite (data/realtime.db)** | ```bash\npython streamer.py          # boucle continue, Ctrl‑C pour arrêter\n``` |
| *(optionnel)* **`tests/test_data.py`** | Smoke‑tests : vérifie que le Parquet existe et que la table SQLite reçoit des lignes | ```bash\npytest tests/\n``` |