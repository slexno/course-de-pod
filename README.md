# F1 Tabletop Manager

Jeu local (localhost) inspiré de F1 Manager / Motorsport Manager, piloté par un MJ.

## Fichiers à garder (noms exacts)

- `app.py`
- `circuit.xlsx`
- `circuit.png`
- `templates/index.html`
- `static/app.js`
- `static/style.css`
- `requirements.txt`

## Lancer

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Puis ouvrir http://127.0.0.1:5000

## Règles principales

- Stats de 0 à 20 avec modificateur D&D (`0 => -5`, `20 => +5`).
- `engine power`: bonus en ligne droite uniquement.
- `downforce`: bonus en virage uniquement.
- `dextérité`: bonus global de conduite + défense.
- `agressivité`: bonus en virage, et seuil de risque de malus en dépassement dangereux.
- Météo: sec (0), venteux (-1 dex), pluie légère (-2 dex), orage (-4 dex).

## Modes/actions

- Dépassement normal (attaque vs défense simultanées).
- Dépassement dangereux (+2 attaque mais risque de malus -3 sur les 3 prochaines sections).
- Préparation (+2 défense au prochain duel subi).
- Prochaine section (+1 attaque sur la prochaine tentative).
- Passer (avancer sans duel).

## Systèmes avancés

- Qualification auto avant la course (1 tour simulé par pilote).
- Usure pneus progressive (plus forte lors des actions agressives).
- Bonus de sortie de virage qui influence la ligne droite suivante.
- Affichage des positions des joueurs sur la carte `circuit.png`.


## Nouveautés

- Nombre de joueurs configurable de **3 à 10**.
- En fin de course, panneau statistiques avec **podium**, reste du classement, et pour chaque pilote: dépassements réussis, défenses réussies, malus subis.
