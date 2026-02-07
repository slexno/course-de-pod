# F1 Tabletop Manager

Jeu local (localhost) inspiré de F1 Manager / Motorsport Manager, piloté par un MJ.

## Lancer

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Ensuite ouvrir http://127.0.0.1:5000

## Règles implémentées

- Le circuit est chargé depuis `circuit.xlsx` (feuille `Circuit`).
- 4 joueurs créent une voiture avec:
  - engine power
  - downforce
  - driver skill
  - reliability
- Dépassement = jet d20 + modificateur (borné entre -4 et +5).
- Le MJ décide manuellement “réussi/raté”.

## Features ajoutées

- **Pit stops**: bouton stand, réduit l’usure pneus et comptabilise les arrêts.
- **Météo dynamique**: sec / nuageux / pluie / orage avec impact direct sur les modificateurs.
- **Fiabilité moteur**: sur très mauvais jet, possible casse moteur (DNF) selon la stat de fiabilité.
- **Compétence pilote**: `driver skill` influence chaque tentative de dépassement.
- **Usure pneus**: augmente à chaque activation (plus forte en virage et sous mauvaise météo).

## Dépannage

- Si l’interface ne répond pas, ouvre la console navigateur (F12) et regarde la bannière d’erreur en haut.
- Le serveur lit `circuit.xlsx` via un chemin absolu basé sur `app.py`.
- Sous Spyder/Jupyter, le serveur est lancé sans reloader pour éviter `SystemExit: 1`.
