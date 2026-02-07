#!/usr/bin/env python3
"""Générateur de circuit style Formule 1 avec export image et Excel.

Fonctionnalités:
- Paramètres utilisateur: virages rapides/lents, chicanes, épingles.
- Génération d'un tracé fermé non auto-chevauchant (avec retries).
- Rendu type "carte F1" (fond sombre + 3 secteurs de taille égale).
- Panneau latéral décrivant chaque section (droites/virages, angle, longueur).
- Export Excel détaillé dans `circuit.xlsx` (avec fallback si verrouillé).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

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
    secteur: int = 1


TURN_LIBRARY = {
    "virage_rapide": {"angle": (25, 42), "radius": (95, 155)},
    "virage_lent": {"angle": (50, 88), "radius": (40, 80)},
    "chicane": {"angle": (28, 44), "radius": (32, 58)},
    "epingle": {"angle": (130, 172), "radius": (18, 32)},
}

SECTOR_COLORS = {
    1: "#ff2d2d",  # rouge
    2: "#00b8ff",  # cyan
    3: "#ffd400",  # jaune
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

    cx = x0 - direction * radius * math.sin(math.radians(heading))
    cy = y0 + direction * radius * math.cos(math.radians(heading))

    start_theta = math.degrees(math.atan2(y0 - cy, x0 - cx))

    steps = max(10, int(abs(angle) // 2))
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


def _ccw(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float]
) -> bool:
    return _ccw(p1, p3, p4) != _ccw(p2, p3, p4) and _ccw(p1, p2, p3) != _ccw(p1, p2, p4)


def has_self_intersection(points: List[Tuple[float, float]]) -> bool:
    if len(points) < 5:
        return False

    eps = 1e-6
    for i in range(len(points) - 1):
        a1, a2 = points[i], points[i + 1]
        if math.hypot(a2[0] - a1[0], a2[1] - a1[1]) < eps:
            continue
        for j in range(i + 2, len(points) - 1):
            # Ignore adjacent segments sharing endpoints.
            if j == i or j == i - 1 or j == i + 1:
                continue
            b1, b2 = points[j], points[j + 1]
            if math.hypot(b2[0] - b1[0], b2[1] - b1[1]) < eps:
                continue
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def build_track_once(counts: dict[str, int]) -> Tuple[List[Segment], List[Tuple[float, float]]]:
    turns = generate_turn_segments(counts)
    segments: List[Segment] = []
    points: List[Tuple[float, float]] = [(0.0, 0.0)]

    heading = 0.0
    pit_length = random.uniform(260, 380)
    add_straight(segments, points, heading, pit_length, category="ligne_des_stands")

    for i, turn_type in enumerate(turns):
        if turn_type == "chicane":
            dir_a = random.choice([-1, 1])
            heading = add_arc(segments, points, heading, turn_type, dir_a)
            add_straight(segments, points, heading, random.uniform(40, 85), category="liaison_chicane")
            heading = add_arc(segments, points, heading, turn_type, -dir_a)
        else:
            direction = random.choice([-1, 1])
            heading = add_arc(segments, points, heading, turn_type, direction)

        if i < len(turns) - 1:
            add_straight(segments, points, heading, random.uniform(90, 260))

    x_end, y_end = points[-1]
    x_start, y_start = points[0]
    dx, dy = x_start - x_end, y_start - y_end
    closure_len = math.hypot(dx, dy)

    if closure_len > 1:
        heading_to_start = math.degrees(math.atan2(dy, dx))
        add_straight(segments, points, heading_to_start, closure_len, category="retour_stands")

    return segments, points


def assign_sectors(segments: List[Segment]) -> None:
    total_length = sum(seg.longueur_m for seg in segments)
    if total_length <= 0:
        return

    cut1 = total_length / 3
    cut2 = 2 * total_length / 3
    cumulative = 0.0

    for seg in segments:
        midpoint = cumulative + seg.longueur_m / 2
        if midpoint < cut1:
            seg.secteur = 1
        elif midpoint < cut2:
            seg.secteur = 2
        else:
            seg.secteur = 3
        cumulative += seg.longueur_m


def build_track(counts: dict[str, int], max_tries: int = 250) -> Tuple[List[Segment], List[Tuple[float, float]]]:
    best: Optional[Tuple[List[Segment], List[Tuple[float, float]]]] = None

    for _ in range(max_tries):
        segments, points = build_track_once(counts)

        # Critères de qualité visuelle:
        # 1) Pas d'auto-intersection
        # 2) Boîte englobante pas trop dégénérée
        xs, ys = zip(*points)
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        ratio = max(width, height) / max(min(width, height), 1e-6)

        if not has_self_intersection(points) and ratio < 4.2:
            assign_sectors(segments)
            return segments, points

        if best is None:
            best = (segments, points)

    # Dernier recours: retourne la meilleure tentative même si imparfaite.
    assert best is not None
    segments, points = best
    assign_sectors(segments)
    return segments, points


def _segment_label(seg: Segment) -> str:
    if seg.type_segment == "ligne_droite":
        return f"S{seg.index:02d} | Droite | {seg.longueur_m:.1f} m"
    sens = "G" if seg.angle_deg > 0 else "D"
    return f"S{seg.index:02d} | {seg.categorie} ({sens}) | {abs(seg.angle_deg):.1f}° | {seg.longueur_m:.1f} m"


def export_image(segments: List[Segment], points: List[Tuple[float, float]], output: Path) -> None:
    # Prépare les sous-tracés par segment (pour colorer les secteurs).
    seg_lines = [((seg.debut_x, seg.debut_y), (seg.fin_x, seg.fin_y), seg.secteur) for seg in segments]

    fig = plt.figure(figsize=(14, 8), facecolor="#0b0f1a")
    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1.1])
    ax_track = fig.add_subplot(gs[0, 0])
    ax_info = fig.add_subplot(gs[0, 1])

    ax_track.set_facecolor("#0b0f1a")
    ax_info.set_facecolor("#0b0f1a")

    # Fond de piste
    xs, ys = zip(*points)
    ax_track.plot(xs, ys, linewidth=11, color="#2d3248", solid_capstyle="round", zorder=1)

    # Couche secteurs
    for (x0, y0), (x1, y1), sector in seg_lines:
        color = SECTOR_COLORS.get(sector, "#ffffff")
        ax_track.plot([x0, x1], [y0, y1], linewidth=4.5, color=color, solid_capstyle="round", zorder=2)

    # Ligne des stands (sur la première droite)
    s0 = segments[0]
    midx = (s0.debut_x + s0.fin_x) / 2
    midy = (s0.debut_y + s0.fin_y) / 2
    ax_track.scatter([midx], [midy], s=90, marker="s", color="#ffffff", edgecolor="#000000", zorder=4)
    ax_track.text(midx + 10, midy + 8, "START / PIT", color="white", fontsize=9, weight="bold")

    # Numéros de sections
    for seg in segments:
        px = (seg.debut_x + seg.fin_x) / 2
        py = (seg.debut_y + seg.fin_y) / 2
        ax_track.text(
            px,
            py,
            f"{seg.index:02d}",
            color="#e6eaf8",
            fontsize=8,
            ha="center",
            va="center",
            bbox=dict(boxstyle="circle,pad=0.15", facecolor="#1c2135", edgecolor="#313854"),
            zorder=5,
        )

    ax_track.set_title("Circuit généré - style carte F1", color="white", fontsize=16, weight="bold", pad=12)
    ax_track.axis("equal")
    ax_track.axis("off")

    # Légende secteurs
    y_leg = 0.95
    for sector, name in [(1, "SECTEUR 1"), (2, "SECTEUR 2"), (3, "SECTEUR 3")]:
        ax_info.text(0.02, y_leg, "■", color=SECTOR_COLORS[sector], fontsize=18, va="center")
        ax_info.text(0.09, y_leg, name, color="white", fontsize=11, weight="bold", va="center")
        y_leg -= 0.06

    # Description détaillée des sections
    ax_info.text(0.02, y_leg - 0.02, "Sections", color="white", fontsize=13, weight="bold")
    y = y_leg - 0.07
    for seg in segments:
        color = SECTOR_COLORS.get(seg.secteur, "#ffffff")
        ax_info.text(0.02, y, _segment_label(seg), color=color, fontsize=8.8, family="monospace")
        y -= 0.038
        if y < 0.03:
            break

    total_length = sum(seg.longueur_m for seg in segments)
    ax_info.text(
        0.02,
        0.01,
        f"Longueur estimée: {total_length:.1f} m | Segments: {len(segments)}",
        color="#d2d7e8",
        fontsize=9,
        weight="bold",
    )

    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.axis("off")

    plt.tight_layout()
    plt.savefig(output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def update_excel(segments: List[Segment], excel_path: Path) -> Path:
    if excel_path.exists():
        try:
            wb = load_workbook(excel_path)
        except PermissionError:
            wb = Workbook()
    else:
        wb = Workbook()

    if "Circuit" in wb.sheetnames:
        ws = wb["Circuit"]
        ws.delete_rows(1, ws.max_row)
    else:
        ws = wb.create_sheet("Circuit")

    headers = [
        "Index",
        "Secteur",
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
                seg.secteur,
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

    try:
        wb.save(excel_path)
        return excel_path
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = excel_path.with_name(f"{excel_path.stem}_{timestamp}.xlsx")
        wb.save(fallback_path)
        print(
            "[INFO] Impossible d'écrire dans 'circuit.xlsx' (fichier probablement ouvert). "
            f"Export réalisé dans: {fallback_path}"
        )
        return fallback_path


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

    export_image(segments, points, image_path)
    excel_written_path = update_excel(segments, excel_path)

    print(f"Image créée : {image_path.resolve()}")
    print(f"Tableau Excel mis à jour : {excel_written_path.resolve()}")
    print(f"Nombre total de segments : {len(segments)}")


if __name__ == "__main__":
    main()
