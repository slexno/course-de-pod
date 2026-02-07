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
- 4 joueurs créent une voiture (engine power, downforce de 1 à 10).
- Dépassement = jet d20 + modificateur calculé selon la section:
  - Ligne droite: basé sur `engine power` + bonus de longueur.
  - Virage: basé sur `downforce` + bonus/malus selon type (rapide, lent, chicane, épingle).
- L'application **n'annonce pas automatiquement la réussite**: le MJ/joueurs décident via boutons.

## Idées de features ensuite

- Pit stops + usure pneus
- Météo dynamique
- Fiabilité mécanique
- Compétence pilote séparée de la voiture
