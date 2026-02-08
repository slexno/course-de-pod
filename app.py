from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file

from circuit_generator import build_track

BASE_DIR = Path(__file__).resolve().parent
CIRCUIT_PNG = BASE_DIR / "circuit.png"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))


@dataclass
class Player:
    player_id: int
    name: str
    engine_power: int
    downforce: int
    dexterity: int
    aggressiveness: int
    tire_wear: float = 0.0
    status: str = "running"
    risk_penalty_sections: int = 0
    next_section_bonus: int = 0
    prep_defense_bonus: int = 0
    corner_exit_bonus: int = 0
    successful_overtakes: int = 0
    successful_defenses: int = 0
    malus_count: int = 0
    slow_malus_sections: int = 0
    skip_turns: int = 0
    pit_defense_malus_next: int = 0
    color: str = "#22c55e"


class GameState:
    def __init__(self) -> None:
        self.players: list[Player] = []
        self.positions: list[int] = []
        self.segment_index = 0
        self.active_position_index = 0
        self.last_duel: dict[str, Any] | None = None
        self.weather = "dry"
        self.current_lap = 1
        self.total_laps = 3
        self.circuit_segments: list[dict[str, Any]] = []
        self.circuit_points: list[tuple[float, float]] = []
        self.circuit_counts: dict[str, int] = {
            "virage_rapide": 3,
            "virage_lent": 4,
            "virage_moyen": 2,
            "epingle": 1,
        }

    @property
    def started(self) -> bool:
        return len(self.players) >= 3


game_state = GameState()


PLAYER_COLORS = [
    "#ef4444", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7",
    "#06b6d4", "#f97316", "#84cc16", "#e879f9", "#14b8a6",
]


def color_for_player(idx: int) -> str:
    return PLAYER_COLORS[(idx - 1) % len(PLAYER_COLORS)]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dnd_modifier(stat: int) -> int:
    return max(-5, min(5, math.floor((stat - 10) / 2)))


def weather_dex_penalty() -> int:
    return 0


def load_circuit_segments() -> list[dict[str, Any]]:
    return game_state.circuit_segments


def ensure_circuit() -> None:
    if game_state.circuit_segments:
        return
    game_state.circuit_segments, game_state.circuit_points = generate_circuit(game_state.circuit_counts)


def generate_circuit(counts: dict[str, int]) -> tuple[list[dict[str, Any]], list[tuple[float, float]]]:
    generated_segments, generated_points = build_track(counts)
    segments = [
        {
            "index": seg.index,
            "type": seg.type_segment,
            "category": seg.categorie,
            "length_m": float(seg.longueur_m),
            "start_x": float(seg.debut_x),
            "start_y": float(seg.debut_y),
            "end_x": float(seg.fin_x),
            "end_y": float(seg.fin_y),
        }
        for seg in generated_segments
    ]
    return segments, generated_points


def wear_penalty(player: Player) -> int:
    if game_state.total_laps <= 0:
        return 0
    max_wear = game_state.total_laps * 30.0
    ratio = player.tire_wear / max_wear
    if ratio >= 1.0:
        return -4
    if ratio >= 0.75:
        return -3
    if ratio >= 0.5:
        return -2
    if ratio >= 0.3:
        return -1
    return 0


def current_segment(segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not segments:
        return None
    return segments[game_state.segment_index]


def get_player_by_id(pid: int) -> Player | None:
    return next((p for p in game_state.players if p.player_id == pid), None)


def get_active_player() -> Player | None:
    if not game_state.positions:
        return None
    if game_state.active_position_index >= len(game_state.positions):
        game_state.active_position_index = 0
    return get_player_by_id(game_state.positions[game_state.active_position_index])


def get_target_player() -> Player | None:
    if game_state.active_position_index <= 0:
        return None
    return get_player_by_id(game_state.positions[game_state.active_position_index - 1])


def get_player_behind() -> Player | None:
    if game_state.active_position_index >= len(game_state.positions) - 1:
        return None
    return get_player_by_id(game_state.positions[game_state.active_position_index + 1])


def attack_modifier(attacker: Player, segment: dict[str, Any], dangerous: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    w_pen = weather_dex_penalty()

    if segment["type"] == "ligne_droite":
        seg_mod = dnd_modifier(attacker.engine_power)
        notes.append(f"Ligne droite: engine {seg_mod:+d}")
    else:
        seg_mod = dnd_modifier(attacker.downforce) + dnd_modifier(attacker.aggressiveness)
        notes.append(
            f"Virage: downforce {dnd_modifier(attacker.downforce):+d}, agressivité {dnd_modifier(attacker.aggressiveness):+d}"
        )

    dex_mod = dnd_modifier(attacker.dexterity) + w_pen
    notes.append(f"Dex + météo: {dex_mod:+d}")

    total = seg_mod + dex_mod + attacker.next_section_bonus + wear_penalty(attacker)
    if segment["type"] == "ligne_droite":
        total += attacker.corner_exit_bonus
        if attacker.corner_exit_bonus:
            notes.append(f"Bonus sortie virage: {attacker.corner_exit_bonus:+d}")

    if dangerous:
        total += 2
        notes.append("Dépassement dangereux: +2")

    if attacker.next_section_bonus:
        notes.append(f"Bonus action prochaine section: {attacker.next_section_bonus:+d}")

    wp = wear_penalty(attacker)
    if wp:
        notes.append(f"Usure pneus: {wp:+d}")

    if attacker.risk_penalty_sections > 0:
        total -= 3
        notes.append(f"Malus risque: -3 ({attacker.risk_penalty_sections} sections restantes)")

    if attacker.slow_malus_sections > 0:
        total -= 5
        notes.append(f"Malus ralentissement: -5 ({attacker.slow_malus_sections} sections restantes)")

    return total, notes


def defense_modifier(defender: Player, segment: dict[str, Any]) -> tuple[int, list[str]]:
    notes: list[str] = []
    dex_mod = dnd_modifier(defender.dexterity) + weather_dex_penalty()

    if segment["type"] == "ligne_droite":
        car_mod = dnd_modifier(defender.engine_power)
        notes.append(f"Défense ligne droite: engine {car_mod:+d}")
    else:
        car_mod = dnd_modifier(defender.downforce)
        notes.append(f"Défense virage: downforce {car_mod:+d}")

    total = dex_mod + car_mod + defender.prep_defense_bonus + wear_penalty(defender)
    notes.append(f"Dex + météo: {dex_mod:+d}")

    if defender.prep_defense_bonus:
        notes.append(f"Préparation: {defender.prep_defense_bonus:+d}")

    if defender.pit_defense_malus_next:
        total += defender.pit_defense_malus_next
        notes.append(f"Malus récupération pneus: {defender.pit_defense_malus_next:+d}")

    # Défense agressive aléatoire basée sur agressivité
    aggr_mod = dnd_modifier(defender.aggressiveness)
    if aggr_mod > 0:
        chance = min(0.75, max(0.15, defender.aggressiveness / 25))
        if random.random() < chance:
            total += aggr_mod
            notes.append(f"Défense agressive: {aggr_mod:+d}")

    wp = wear_penalty(defender)
    if wp:
        notes.append(f"Usure pneus: {wp:+d}")

    if defender.risk_penalty_sections > 0:
        total -= 3
        notes.append(f"Malus risque: -3 ({defender.risk_penalty_sections} sections restantes)")

    if defender.slow_malus_sections > 0:
        total -= 5
        notes.append(f"Malus ralentissement: -5 ({defender.slow_malus_sections} sections restantes)")

    return total, notes


def slow_attack_modifier(attacker: Player) -> tuple[int, list[str]]:
    aggr = dnd_modifier(attacker.aggressiveness)
    total = aggr + wear_penalty(attacker)
    notes = [f"Agressivité: {aggr:+d}"]

    wp = wear_penalty(attacker)
    if wp:
        notes.append(f"Usure pneus: {wp:+d}")

    if attacker.slow_malus_sections > 0:
        total -= 5
        notes.append(f"Malus ralentissement: -5 ({attacker.slow_malus_sections} sections restantes)")

    return total, notes


def dangerous_risk_penalty(attacker: Player, dangerous: bool) -> tuple[bool, str]:
    if not dangerous:
        return False, ""
    threshold = attacker.aggressiveness + dnd_modifier(attacker.dexterity)
    roll = random.randint(1, 20)
    if roll < threshold:
        attacker.risk_penalty_sections = max(attacker.risk_penalty_sections, 3)
        attacker.malus_count += 1
        return True, f"Risque pris: malus -3 pendant 3 sections ({roll} < {threshold})."
    return False, f"Risque évité ({roll} >= {threshold})."


def tire_wear_multiplier(player: Player) -> float:
    return 2.0 if game_state.positions and game_state.positions[0] == player.player_id else 1.0


def apply_tire_delta(player: Player, delta: float) -> None:
    if delta > 0:
        player.tire_wear += delta * tire_wear_multiplier(player)
    else:
        player.tire_wear = max(0.0, player.tire_wear + delta)


def consume_turn(player: Player, segment: dict[str, Any], action_wear: float) -> None:
    apply_tire_delta(player, action_wear)
    if player.risk_penalty_sections > 0:
        player.risk_penalty_sections -= 1
    if player.slow_malus_sections > 0:
        player.slow_malus_sections -= 1

    if segment["type"] != "ligne_droite":
        score = dnd_modifier(player.dexterity) + dnd_modifier(player.downforce)
        player.corner_exit_bonus = max(-2, min(3, score // 2))
    player.next_section_bonus = 0


def advance_turn() -> None:
    game_state.active_position_index += 1
    if game_state.active_position_index >= len(game_state.positions):
        game_state.active_position_index = 0

        segments = load_circuit_segments()
        segment_count = max(1, len(segments))
        game_state.segment_index = (game_state.segment_index + 1) % segment_count
        if game_state.segment_index == 0:
            game_state.current_lap += 1

    apply_pending_skip_turns()


def apply_pending_skip_turns() -> None:
    if not game_state.positions:
        return
    safety = 0
    while safety < len(game_state.positions):
        active = get_active_player()
        if active is None or active.skip_turns <= 0:
            return
        active.skip_turns -= 1
        game_state.last_duel = {"info": f"{active.name} passe son tour (bonus de dépassement adverse)."}
        game_state.active_position_index = (game_state.active_position_index + 1) % len(game_state.positions)
        safety += 1


def track_data(segments: list[dict[str, Any]]) -> dict[str, Any]:
    if not segments:
        return {"markers": [], "path": []}

    points = game_state.circuit_points or [(segments[0]["start_x"], segments[0]["start_y"])]
    if not game_state.circuit_points:
        points.extend((s["end_x"], s["end_y"]) for s in segments)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    def normalize(x: float, y: float) -> tuple[float, float]:
        x_pct = 4 + (92 * ((x - min_x) / span_x))
        y_pct = 96 - (92 * ((y - min_y) / span_y))
        return x_pct, y_pct

    path = [{"x": normalize(x, y)[0], "y": normalize(x, y)[1]} for x, y in points]
    cumulative_section_lengths = [0.0]
    for seg in segments:
        cumulative_section_lengths.append(cumulative_section_lengths[-1] + max(1e-6, seg["length_m"]))
    total_section_length = cumulative_section_lengths[-1] or 1.0

    section_idx = 0
    sections = []
    travel = 0.0
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        piece_len = math.hypot(x1 - x0, y1 - y0)
        midpoint = travel + (piece_len / 2)
        section_distance = (midpoint / max(1e-6, sum(math.hypot(points[j][0]-points[j-1][0], points[j][1]-points[j-1][1]) for j in range(1, len(points))))) * total_section_length
        while section_idx < len(segments) - 1 and section_distance > cumulative_section_lengths[section_idx + 1]:
            section_idx += 1
        seg = segments[section_idx]
        sx, sy = normalize(x0, y0)
        ex, ey = normalize(x1, y1)
        sections.append({
            "index": seg["index"],
            "type": seg["type"],
            "category": seg["category"],
            "start": {"x": sx, "y": sy},
            "end": {"x": ex, "y": ey},
        })
        travel += piece_len

    cumulative_lengths = [0.0]
    for i in range(1, len(points)):
        prev_x, prev_y = points[i - 1]
        x, y = points[i]
        cumulative_lengths.append(cumulative_lengths[-1] + math.hypot(x - prev_x, y - prev_y))
    total_length = cumulative_lengths[-1] or 1.0

    def point_from_ratio(ratio: float) -> tuple[float, float]:
        target = (ratio % 1.0) * total_length
        for i in range(1, len(cumulative_lengths)):
            if cumulative_lengths[i] >= target:
                seg_len = max(1e-6, cumulative_lengths[i] - cumulative_lengths[i - 1])
                t = (target - cumulative_lengths[i - 1]) / seg_len
                x0, y0 = points[i - 1]
                x1, y1 = points[i]
                return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
        return points[-1]

    markers = []
    count = max(1, len(game_state.positions))
    for i, pid in enumerate(game_state.positions):
        player = get_player_by_id(pid)
        if player is None:
            continue

        gap = 0.02
        ratio = (game_state.segment_index + 0.85 - (i * gap * len(segments))) / max(1, len(segments))
        x, y = point_from_ratio(ratio)

        mx, my = normalize(x, y)
        markers.append({
            "name": player.name,
            "x": mx,
            "y": my,
            "color": player.color,
            "status": "running",
        })

    return {"markers": markers, "path": path, "sections": sections}


def qualification_order(segments: list[dict[str, Any]]) -> list[int]:
    scores: list[tuple[int, int]] = []
    for p in game_state.players:
        pace = 0
        corner_bonus = 0
        for seg in segments:
            if seg["type"] == "ligne_droite":
                pace += dnd_modifier(p.engine_power) + corner_bonus
            else:
                corner_bonus = max(-2, min(3, (dnd_modifier(p.dexterity) + dnd_modifier(p.downforce)) // 2))
                pace += dnd_modifier(p.downforce) + dnd_modifier(p.dexterity)
            pace += random.randint(1, 4)
        scores.append((pace, p.player_id))
    scores.sort(reverse=True)
    return [pid for _, pid in scores]


def final_stats() -> dict[str, Any]:
    ranked = [get_player_by_id(pid) for pid in game_state.positions]
    ranked = [p for p in ranked if p is not None]
    data = [
        {
            "position": i + 1,
            "name": p.name,
            "successful_overtakes": p.successful_overtakes,
            "successful_defenses": p.successful_defenses,
            "malus_count": p.malus_count,
        }
        for i, p in enumerate(ranked)
    ]
    return {"podium": data[:3], "others": data[3:], "full": data}


def serialize_state() -> dict[str, Any]:
    ensure_circuit()
    segments = load_circuit_segments()
    by_id = {p.player_id: p for p in game_state.players}
    ranking = [asdict(by_id[pid]) for pid in game_state.positions if pid in by_id]
    finished = game_state.current_lap > game_state.total_laps

    return {
        "started": game_state.started,
        "player_count": len(game_state.players),
        "players": ranking,
        "segment": current_segment(segments),
        "segment_index": game_state.segment_index,
        "segment_count": len(segments),
        "active_player": asdict(get_active_player()) if get_active_player() else None,
        "active_has_target": bool(game_state.active_position_index > 0),
        "last_duel": game_state.last_duel,
        "lap": game_state.current_lap,
        "total_laps": game_state.total_laps,
        "finished": finished,
        "track": track_data(segments),
        "circuit_file": "generated_in_memory",
        "circuit_counts": game_state.circuit_counts,
        "final_stats": final_stats() if finished and game_state.started else None,
    }


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/circuit-image")
def circuit_image() -> Any:
    if CIRCUIT_PNG.exists():
        return send_file(CIRCUIT_PNG)
    return ("circuit.png introuvable", 404)


@app.get("/api/state")
def get_state() -> Any:
    return jsonify(serialize_state())


@app.post("/api/restart")
def restart() -> Any:
    global game_state
    game_state = GameState()
    return jsonify(serialize_state())




@app.post("/api/circuit-preview")
def circuit_preview() -> Any:
    payload = request.get_json(silent=True) or {}
    counts = {
        "virage_rapide": max(0, safe_int(payload.get("virage_rapide"), game_state.circuit_counts["virage_rapide"])),
        "virage_lent": max(0, safe_int(payload.get("virage_lent"), game_state.circuit_counts["virage_lent"])),
        "virage_moyen": max(0, safe_int(payload.get("virage_moyen"), game_state.circuit_counts["virage_moyen"])),
        "epingle": max(0, safe_int(payload.get("epingle"), game_state.circuit_counts["epingle"])),
    }
    if sum(counts.values()) <= 0:
        return jsonify({"error": "Le circuit doit contenir au moins un virage."}), 400

    game_state.circuit_counts = counts
    game_state.circuit_segments, game_state.circuit_points = generate_circuit(counts)
    game_state.segment_index = 0
    game_state.last_duel = {"info": "Nouveau circuit généré."}
    return jsonify(serialize_state())


@app.post("/api/start")
def start_game() -> Any:
    payload = request.get_json(silent=True) or {}
    players_payload = payload.get("players", [])
    if not (3 <= len(players_payload) <= 10):
        return jsonify({"error": "Il faut entre 3 et 10 joueurs."}), 400

    total_laps = max(1, min(20, safe_int(payload.get("total_laps"), 5)))
    circuit_payload = payload.get("circuit", {})
    counts = {
        "virage_rapide": max(0, safe_int(circuit_payload.get("virage_rapide"), game_state.circuit_counts["virage_rapide"])),
        "virage_lent": max(0, safe_int(circuit_payload.get("virage_lent"), game_state.circuit_counts["virage_lent"])),
        "virage_moyen": max(0, safe_int(circuit_payload.get("virage_moyen"), game_state.circuit_counts["virage_moyen"])),
        "epingle": max(0, safe_int(circuit_payload.get("epingle"), game_state.circuit_counts["epingle"])),
    }
    if sum(counts.values()) <= 0:
        return jsonify({"error": "Le circuit doit contenir au moins un virage."}), 400

    players: list[Player] = []
    for idx, row in enumerate(players_payload, start=1):
        name = (row.get("name") or "").strip()
        engine = safe_int(row.get("engine_power"), -1)
        downforce = safe_int(row.get("downforce"), -1)
        dex = safe_int(row.get("dexterity"), -1)
        aggr = safe_int(row.get("aggressiveness"), -1)
        if not name:
            return jsonify({"error": "Chaque joueur doit avoir un nom."}), 400
        if not (0 <= engine <= 20 and 0 <= downforce <= 20 and 0 <= dex <= 20 and 0 <= aggr <= 20):
            return jsonify({"error": "Toutes les stats doivent être entre 0 et 20."}), 400
        if engine + downforce + dex + aggr != 50:
            return jsonify({"error": "La somme des 4 stats doit être exactement 50 pour chaque joueur."}), 400
        players.append(Player(player_id=idx, name=name, engine_power=engine, downforce=downforce, dexterity=dex, aggressiveness=aggr, color=color_for_player(idx)))

    game_state.players = players
    game_state.total_laps = total_laps
    game_state.current_lap = 1
    game_state.segment_index = 0
    game_state.active_position_index = 0
    game_state.last_duel = None
    game_state.weather = "dry"
    reuse_preview = game_state.circuit_segments and counts == game_state.circuit_counts
    game_state.circuit_counts = counts
    if not reuse_preview:
        game_state.circuit_segments, game_state.circuit_points = generate_circuit(counts)

    segments = game_state.circuit_segments
    game_state.positions = qualification_order(segments) if segments else [p.player_id for p in players]

    return jsonify(serialize_state())


@app.post("/api/weather")
def set_weather() -> Any:
    return jsonify({"error": "La météo a été retirée du jeu."}), 400


@app.post("/api/next-turn")
def next_turn() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if state["finished"]:
        return jsonify({"error": "Course terminée."}), 400
    active = get_active_player()
    if active is not None:
        game_state.last_duel = {"info": f"{active.name} passe son tour."}
    advance_turn()
    return jsonify(serialize_state())


@app.post("/api/action")
def action() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if state["finished"]:
        return jsonify({"error": "Course terminée."}), 400

    payload = request.get_json(silent=True) or {}
    action_type = payload.get("type")

    segments = load_circuit_segments()
    segment = current_segment(segments)
    if segment is None:
        return jsonify({"error": "Segment introuvable."}), 400

    attacker = get_active_player()
    if attacker is None:
        advance_turn()
        return jsonify(serialize_state())

    if action_type == "prepare":
        attacker.prep_defense_bonus = 2
        consume_turn(attacker, segment, action_wear=1.6)
        game_state.last_duel = {"info": f"{attacker.name} se prépare (+2 défense)."}
        advance_turn()
        return jsonify(serialize_state())

    if action_type == "next_section_bonus":
        attacker.next_section_bonus += 1
        consume_turn(attacker, segment, action_wear=1.6)
        game_state.last_duel = {"info": f"{attacker.name} prépare la prochaine section (+1 attaque)."}
        advance_turn()
        return jsonify(serialize_state())

    if action_type == "slow_behind":
        if game_state.active_position_index >= len(game_state.positions) - 1:
            consume_turn(attacker, segment, action_wear=1.6)
            game_state.last_duel = {"info": f"{attacker.name} est dernier: personne à ralentir."}
            advance_turn()
            return jsonify(serialize_state())

        defender = get_player_behind()
        if defender is None:
            return jsonify({"error": "Défenseur indisponible."}), 400

        atk_mod, atk_notes = slow_attack_modifier(attacker)
        def_mod, def_notes = defense_modifier(defender, segment)
        defender_pit_malus_used = defender.pit_defense_malus_next
        atk_roll = random.randint(1, 20)
        def_roll = random.randint(1, 20)
        atk_total = atk_roll + atk_mod
        def_total = def_roll + def_mod
        success = atk_total > def_total

        overtake_back = (def_total - atk_total) > 10
        if success:
            defender.slow_malus_sections = max(defender.slow_malus_sections, 2)
            attacker.successful_overtakes += 1
            apply_tire_delta(attacker, -0.5)
        else:
            defender.successful_defenses += 1
            apply_tire_delta(attacker, 1.0)
            if overtake_back:
                i = game_state.active_position_index
                game_state.positions[i], game_state.positions[i + 1] = game_state.positions[i + 1], game_state.positions[i]
                game_state.active_position_index += 1

        apply_tire_delta(defender, 0.5)

        defender.prep_defense_bonus = 0
        if defender_pit_malus_used:
            defender.pit_defense_malus_next = 0
        consume_turn(attacker, segment, action_wear=1.8)

        game_state.last_duel = {
            "attacker": attacker.name,
            "defender": defender.name,
            "attack_roll": atk_roll,
            "attack_mod": atk_mod,
            "attack_total": atk_total,
            "attack_notes": atk_notes,
            "defense_roll": def_roll,
            "defense_mod": def_mod,
            "defense_total": def_total,
            "defense_notes": def_notes,
            "dangerous": False,
            "risk_triggered": False,
            "risk_note": "Contre réussi: dépassement défensif (>10)." if overtake_back else "",
            "success": success,
        }

        advance_turn()
        return jsonify(serialize_state())

    if action_type == "pit_recover":
        old_wear = attacker.tire_wear
        apply_tire_delta(attacker, -50.0)
        attacker.pit_defense_malus_next = -11
        info = f"{attacker.name} régénère ses pneus (-{min(50.0, old_wear):.1f}) mais aura -11 à sa prochaine défense."
        consume_turn(attacker, segment, action_wear=1.6)
        game_state.last_duel = {"info": info}
        advance_turn()
        return jsonify(serialize_state())

    if action_type == "pass":
        consume_turn(attacker, segment, action_wear=1.4)
        game_state.last_duel = {"info": f"{attacker.name} passe cette section."}
        advance_turn()
        return jsonify(serialize_state())

    if action_type not in {"overtake", "dangerous_overtake"}:
        return jsonify({"error": "Action inconnue."}), 400

    if game_state.active_position_index == 0:
        consume_turn(attacker, segment, action_wear=1.2)
        game_state.last_duel = {"info": f"{attacker.name} est leader: pas de cible, tour passé."}
        advance_turn()
        return jsonify(serialize_state())

    defender = get_target_player()
    if defender is None:
        return jsonify({"error": "Défenseur indisponible."}), 400

    dangerous = action_type == "dangerous_overtake"

    atk_mod, atk_notes = attack_modifier(attacker, segment, dangerous)
    def_mod, def_notes = defense_modifier(defender, segment)
    defender_pit_malus_used = defender.pit_defense_malus_next
    atk_roll = random.randint(1, 20)
    def_roll = random.randint(1, 20)

    risk_triggered, risk_note = dangerous_risk_penalty(attacker, dangerous)

    atk_total = atk_roll + atk_mod
    def_total = def_roll + def_mod
    success = atk_total > def_total

    if success:
        attacker.successful_overtakes += 1
        i = game_state.active_position_index
        game_state.positions[i - 1], game_state.positions[i] = game_state.positions[i], game_state.positions[i - 1]
        game_state.active_position_index -= 1
        if (atk_total - def_total) >= 10:
            defender.skip_turns += 1
        apply_tire_delta(attacker, -0.5)
    else:
        defender.successful_defenses += 1
        apply_tire_delta(attacker, 1.0)

    apply_tire_delta(defender, 0.5)

    defender.prep_defense_bonus = 0
    if defender_pit_malus_used:
        defender.pit_defense_malus_next = 0
    consume_turn(attacker, segment, action_wear=1.4 if dangerous else 1.0)

    game_state.last_duel = {
        "attacker": attacker.name,
        "defender": defender.name,
        "attack_roll": atk_roll,
        "attack_mod": atk_mod,
        "attack_total": atk_total,
        "attack_notes": atk_notes,
        "defense_roll": def_roll,
        "defense_mod": def_mod,
        "defense_total": def_total,
        "defense_notes": def_notes,
        "dangerous": dangerous,
        "risk_triggered": risk_triggered,
        "risk_note": risk_note,
        "success": success,
    }

    advance_turn()
    return jsonify(serialize_state())


def run_local_server() -> None:
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)


if __name__ == "__main__":
    run_local_server()
