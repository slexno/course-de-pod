# -*- coding: utf-8 -*-
"""
Created on Sat Feb  7 01:15:18 2026

@author: killian
"""

#!/usr/bin/env python3
"""Générateur de circuit type Formule 1.

- Demande le nombre de virages rapides/lents, chicanes et épingles.
- Génère un tracé fermé qui revient sur la ligne droite des stands.
- Exporte une image PNG du circuit.
- Met à jour le fichier Excel `circuit.xlsx` avec le détail de chaque section.
"""



import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
from openpyxl import Workbook, load_workbook


@dataclass
class Segment:
    index: int
    type_segment: str
    categorie: str
    longueur_m: float
    angle_deg: float
    debut_x: float
    debut_y: float
    fin_x: float
    fin_y: float


TURN_LIBRARY = {
    "virage_rapide": {"angle": (25, 45), "radius": (90, 150)},
    "virage_lent": {"angle": (55, 95), "radius": (35, 75)},
    "chicane": {"angle": (28, 45), "radius": (30, 55)},
    "epingle": {"angle": (130, 170), "radius": (18, 28)},
}


def ask_int(prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            print("Veuillez entrer un entier positif (0 accepté).")


def generate_turn_segments(counts: dict[str, int]) -> List[str]:
    turns: List[str] = []
    for key, count in counts.items():
        turns.extend([key] * count)
    random.shuffle(turns)
    return turns


def add_straight(
    segments: List[Segment],
    points: List[Tuple[float, float]],
    heading: float,
    length: float,
    category: str = "ligne_droite",
) -> None:
    x0, y0 = points[-1]
    x1 = x0 + length * math.cos(math.radians(heading))
    y1 = y0 + length * math.sin(math.radians(heading))

    segments.append(
        Segment(
            index=len(segments) + 1,
            type_segment="ligne_droite",
            categorie=category,
            longueur_m=round(length, 2),
            angle_deg=0.0,
            debut_x=round(x0, 2),
            debut_y=round(y0, 2),
            fin_x=round(x1, 2),
            fin_y=round(y1, 2),
        )
    )
    points.append((x1, y1))


def add_arc(
    segments: List[Segment],
    points: List[Tuple[float, float]],
    heading: float,
    turn_type: str,
    direction: int,
) -> float:
    profile = TURN_LIBRARY[turn_type]
    angle = random.uniform(*profile["angle"])
    radius = random.uniform(*profile["radius"])

    sweep = direction * angle
    arc_len = radius * math.radians(angle)

    x0, y0 = points[-1]

    # Centre du cercle selon la direction du virage
    cx = x0 - direction * radius * math.sin(math.radians(heading))
    cy = y0 + direction * radius * math.cos(math.radians(heading))

    start_theta = math.degrees(math.atan2(y0 - cy, x0 - cx))
    end_theta = start_theta + sweep

    # Échantillonne l'arc pour le dessin
    steps = max(8, int(abs(angle) // 3))
    for i in range(1, steps + 1):
        t = start_theta + sweep * (i / steps)
        x = cx + radius * math.cos(math.radians(t))
        y = cy + radius * math.sin(math.radians(t))
        points.append((x, y))

    x1, y1 = points[-1]

    segments.append(
        Segment(
            index=len(segments) + 1,
            type_segment="virage",
            categorie=turn_type,
            longueur_m=round(arc_len, 2),
            angle_deg=round(sweep, 2),
            debut_x=round(x0, 2),
            debut_y=round(y0, 2),
            fin_x=round(x1, 2),
            fin_y=round(y1, 2),
        )
    )

    return heading + sweep


def build_track(counts: dict[str, int]) -> Tuple[List[Segment], List[Tuple[float, float]]]:
    turns = generate_turn_segments(counts)
    segments: List[Segment] = []
    points: List[Tuple[float, float]] = [(0.0, 0.0)]

    # Ligne des stands (droite de départ)
    heading = 0.0
    pit_length = random.uniform(220, 360)
    add_straight(segments, points, heading, pit_length, category="ligne_des_stands")

    # Alterne droites aléatoires et virages
    for i, turn_type in enumerate(turns):
        if turn_type == "chicane":
            dir_a = random.choice([-1, 1])
            heading = add_arc(segments, points, heading, turn_type, dir_a)
            short_straight = random.uniform(45, 90)
            add_straight(segments, points, heading, short_straight, category="liaison_chicane")
            heading = add_arc(segments, points, heading, turn_type, -dir_a)
        else:
            direction = random.choice([-1, 1])
            heading = add_arc(segments, points, heading, turn_type, direction)

        # Intercalage d'une ligne droite aléatoire
        if i < len(turns) - 1:
            straight_len = random.uniform(80, 260)
            add_straight(segments, points, heading, straight_len)

    # Fermeture de la boucle vers le début de la ligne des stands
    x_end, y_end = points[-1]
    x_start, y_start = points[0]
    dx, dy = x_start - x_end, y_start - y_end
    closure_len = math.hypot(dx, dy)

    if closure_len > 1:
        heading_to_start = math.degrees(math.atan2(dy, dx))
        add_straight(segments, points, heading_to_start, closure_len, category="retour_stands")

    return segments, points


def export_image(points: List[Tuple[float, float]], output: Path) -> None:
    xs, ys = zip(*points)
    plt.figure(figsize=(10, 8))
    plt.plot(xs, ys, linewidth=7, color="#222")
    plt.plot(xs, ys, linewidth=4, color="#bdbdbd")
    plt.scatter([xs[0]], [ys[0]], s=120, marker="s", color="red", label="Ligne des stands")
    plt.axis("equal")
    plt.axis("off")
    plt.title("Circuit généré automatiquement")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()


def update_excel(segments: List[Segment], excel_path: Path) -> None:
    if excel_path.exists():
        wb = load_workbook(excel_path)
    else:
        wb = Workbook()

    if "Circuit" in wb.sheetnames:
        ws = wb["Circuit"]
        ws.delete_rows(1, ws.max_row)
    else:
        ws = wb.create_sheet("Circuit")

    headers = [
        "Index",
        "Type",
        "Categorie",
        "Longueur_m",
        "Angle_deg",
        "Debut_X",
        "Debut_Y",
        "Fin_X",
        "Fin_Y",
    ]
    ws.append(headers)

    for seg in segments:
        ws.append(
            [
                seg.index,
                seg.type_segment,
                seg.categorie,
                seg.longueur_m,
                seg.angle_deg,
                seg.debut_x,
                seg.debut_y,
                seg.fin_x,
                seg.fin_y,
            ]
        )

    wb.save(excel_path)


def main() -> None:
    print("=== Générateur de circuit style Formule 1 ===")
    random.seed()

    counts = {
        "virage_rapide": ask_int("Nombre de virages rapides : "),
        "virage_lent": ask_int("Nombre de virages lents : "),
        "chicane": ask_int("Nombre de chicanes : "),
        "epingle": ask_int("Nombre d'épingles : "),
    }

    if sum(counts.values()) == 0:
        print("Vous devez demander au moins un virage pour générer un circuit.")
        return

    segments, points = build_track(counts)

    image_path = Path("circuit.png")
    excel_path = Path("circuit.xlsx")

    export_image(points, image_path)
    update_excel(segments, excel_path)

    print(f"Image créée : {image_path.resolve()}")
    print(f"Tableau Excel mis à jour : {excel_path.resolve()}")
    print(f"Nombre total de segments : {len(segments)}")


if __name__ == "__main__":
    main()
