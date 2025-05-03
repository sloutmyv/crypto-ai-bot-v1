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