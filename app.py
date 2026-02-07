from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
CIRCUIT_FILE = BASE_DIR / "circuit.xlsx"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))


@dataclass
class Player:
    player_id: int
    name: str
    engine_power: int
    downforce: int
    driver_skill: int
    reliability: int
    tire_wear: int = 0
    pit_stops: int = 0
    status: str = "running"  # running | dnf


class GameState:
    def __init__(self) -> None:
        self.players: list[Player] = []
        self.positions: list[int] = []
        self.segment_index = 0
        self.active_position_index = 0
        self.last_roll: dict[str, Any] | None = None
        self.weather = "dry"
        self.current_lap = 1
        self.total_laps = 3

    @property
    def started(self) -> bool:
        return len(self.players) == 4


game_state = GameState()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_circuit_segments() -> list[dict[str, Any]]:
    if not CIRCUIT_FILE.exists():
        return []

    wb = load_workbook(CIRCUIT_FILE, data_only=True)
    if "Circuit" not in wb.sheetnames:
        return []

    ws = wb["Circuit"]
    segments: list[dict[str, Any]] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        segments.append(
            {
                "index": safe_int(row[0]),
                "type": row[1] or "inconnu",
                "category": row[2] or "inconnu",
                "length_m": float(row[3] or 0),
                "angle_deg": float(row[4] or 0),
            }
        )

    return segments


def stat_to_modifier(stat: int) -> int:
    return max(-4, min(5, stat - 5))


def weather_modifier(player: Player, segment: dict[str, Any]) -> tuple[int, str]:
    weather = game_state.weather
    is_straight = segment["type"] == "ligne_droite"

    if weather == "dry":
        return 0, "Piste sèche."
    if weather == "cloudy":
        return 0, "Nuageux: pas d'impact."

    if weather == "rain":
        if is_straight:
            return -1, "Pluie: traction réduite en ligne droite (-1)."
        return (1, "Pluie: bonne downforce en virage (+1).") if player.downforce >= 7 else (-1, "Pluie: downforce insuffisante en virage (-1).")

    # storm
    if is_straight:
        return -2, "Orage: gros déficit en ligne droite (-2)."
    return (-1, "Orage: downforce solide limite la casse (-1).") if player.downforce >= 8 else (-2, "Orage: virage très difficile (-2).")


def tire_wear_modifier(player: Player) -> tuple[int, str]:
    if player.tire_wear >= 85:
        return -2, "Pneus très usés (-2)."
    if player.tire_wear >= 60:
        return -1, "Pneus usés (-1)."
    return 0, "Pneus corrects."


def compute_roll_modifier(player: Player, segment: dict[str, Any]) -> tuple[int, str]:
    notes: list[str] = []

    if segment["type"] == "ligne_droite":
        base = stat_to_modifier(player.engine_power)
        bonus = 0
        if segment["length_m"] >= 180:
            bonus += 1
        if segment["length_m"] >= 260:
            bonus += 1
        mod = base + bonus
        notes.append(f"Ligne droite ({int(segment['length_m'])}m): moteur {base:+d}, longueur {bonus:+d}.")
    else:
        requirements = {"epingle": 3, "virage_lent": 5, "chicane": 6, "virage_rapide": 8}
        requirement = requirements.get(segment["category"], 5)
        base = stat_to_modifier(player.downforce)
        gap = player.downforce - requirement
        if gap >= 2:
            context_bonus = 2
        elif gap >= 0:
            context_bonus = 1
        elif gap <= -3:
            context_bonus = -2
        else:
            context_bonus = -1
        mod = base + context_bonus
        notes.append(f"Virage: downforce {base:+d}, contexte {context_bonus:+d}.")

    skill_mod = stat_to_modifier(player.driver_skill)
    mod += skill_mod
    notes.append(f"Talent pilote {skill_mod:+d}.")

    w_mod, w_note = weather_modifier(player, segment)
    mod += w_mod
    notes.append(w_note)

    t_mod, t_note = tire_wear_modifier(player)
    mod += t_mod
    notes.append(t_note)

    mod = max(-4, min(5, mod))
    notes.append(f"Mod final borné: {mod:+d}.")

    return mod, " ".join(notes)


def apply_tire_wear(player: Player, segment: dict[str, Any]) -> None:
    if player.status != "running":
        return

    delta = 2 if segment["type"] == "ligne_droite" else 4
    if game_state.weather == "rain":
        delta += 1
    elif game_state.weather == "storm":
        delta += 2

    player.tire_wear = min(100, player.tire_wear + delta)


def maybe_engine_failure(player: Player, d20_roll: int) -> tuple[bool, str]:
    if d20_roll > 2:
        return False, ""

    threshold = player.reliability * 2
    check = random.randint(1, 20)
    if check > threshold:
        player.status = "dnf"
        return True, f"Casse moteur ! check fiabilité {check}/20 > seuil {threshold}/20."

    return False, f"Moteur sauvé de justesse ({check}/20 <= {threshold}/20)."


def serialize_state() -> dict[str, Any]:
    segments = load_circuit_segments()
    by_id = {p.player_id: p for p in game_state.players}
    ranking = [asdict(by_id[pid]) for pid in game_state.positions]

    current_segment = segments[game_state.segment_index] if segments else None
    active_player = ranking[game_state.active_position_index] if ranking else None

    return {
        "started": game_state.started,
        "players": ranking,
        "segment": current_segment,
        "segment_index": game_state.segment_index,
        "segment_count": len(segments),
        "active_player": active_player,
        "active_has_target": bool(game_state.active_position_index > 0),
        "last_roll": game_state.last_roll,
        "circuit_file": str(CIRCUIT_FILE),
        "weather": game_state.weather,
        "lap": game_state.current_lap,
        "total_laps": game_state.total_laps,
        "finished": game_state.current_lap > game_state.total_laps,
    }


def get_active_player() -> Player | None:
    if not game_state.positions:
        return None
    if game_state.active_position_index >= len(game_state.positions):
        game_state.active_position_index = 0
    pid = game_state.positions[game_state.active_position_index]
    return next((p for p in game_state.players if p.player_id == pid), None)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/state")
def get_state() -> Any:
    return jsonify(serialize_state())


@app.post("/api/start")
def start_game() -> Any:
    payload = request.get_json(silent=True) or {}
    players_payload = payload.get("players", [])

    if len(players_payload) != 4:
        return jsonify({"error": "Il faut exactement 4 joueurs."}), 400

    total_laps = safe_int(payload.get("total_laps"), 3)
    total_laps = max(1, min(10, total_laps))

    players: list[Player] = []
    for idx, row in enumerate(players_payload, start=1):
        name = (row.get("name") or "").strip()
        engine = safe_int(row.get("engine_power"), -1)
        downforce = safe_int(row.get("downforce"), -1)
        skill = safe_int(row.get("driver_skill"), -1)
        reliability = safe_int(row.get("reliability"), -1)

        if not name:
            return jsonify({"error": "Chaque joueur doit avoir un nom."}), 400
        if not (1 <= engine <= 10 and 1 <= downforce <= 10 and 1 <= skill <= 10 and 1 <= reliability <= 10):
            return jsonify({"error": "Toutes les stats doivent être entre 1 et 10."}), 400

        players.append(Player(idx, name, engine, downforce, skill, reliability))

    game_state.players = players
    game_state.positions = [p.player_id for p in players]
    game_state.segment_index = 0
    game_state.active_position_index = 0
    game_state.last_roll = None
    game_state.weather = "dry"
    game_state.current_lap = 1
    game_state.total_laps = total_laps

    return jsonify(serialize_state())


@app.post("/api/weather")
def set_weather() -> Any:
    payload = request.get_json(silent=True) or {}
    weather = payload.get("weather")
    if weather not in {"dry", "cloudy", "rain", "storm"}:
        return jsonify({"error": "Météo invalide."}), 400

    game_state.weather = weather
    return jsonify(serialize_state())


@app.post("/api/roll")
def roll_overtake() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if state["finished"]:
        return jsonify({"error": "La course est terminée."}), 400
    if not state["active_has_target"]:
        return jsonify({"error": "Le leader n'a personne à dépasser."}), 400

    player = get_active_player()
    if player is None or player.status != "running":
        return jsonify({"error": "Pilote actif indisponible."}), 400

    segment = state["segment"]
    if segment is None:
        return jsonify({"error": f"Aucun segment disponible dans {CIRCUIT_FILE}."}), 400

    modifier, note = compute_roll_modifier(player, segment)
    roll = random.randint(1, 20)
    total = roll + modifier

    target_id = game_state.positions[game_state.active_position_index - 1]
    target = next((p for p in game_state.players if p.player_id == target_id), None)
    if target is None:
        return jsonify({"error": "Cible introuvable."}), 400

    failed, reliability_note = maybe_engine_failure(player, roll)

    game_state.last_roll = {
        "player": player.name,
        "target": target.name,
        "d20": roll,
        "modifier": modifier,
        "total": total,
        "note": note,
        "engine_failure": failed,
        "reliability_note": reliability_note,
    }

    return jsonify(serialize_state())


@app.post("/api/resolve")
def resolve_roll() -> Any:
    payload = request.get_json(silent=True) or {}
    success = bool(payload.get("success"))

    if game_state.last_roll is None:
        return jsonify({"error": "Lancez un dé avant de résoudre."}), 400

    active = get_active_player()
    if active is None:
        return jsonify({"error": "Pilote actif introuvable."}), 400

    if game_state.last_roll.get("engine_failure"):
        success = False

    if success and game_state.active_position_index > 0 and active.status == "running":
        i = game_state.active_position_index
        game_state.positions[i - 1], game_state.positions[i] = game_state.positions[i], game_state.positions[i - 1]
        game_state.active_position_index -= 1

    game_state.last_roll = None
    return jsonify(serialize_state())


@app.post("/api/pit")
def pit_stop() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if state["finished"]:
        return jsonify({"error": "La course est terminée."}), 400

    player = get_active_player()
    if player is None or player.status != "running":
        return jsonify({"error": "Pilote actif indisponible."}), 400

    player.tire_wear = max(0, player.tire_wear - 45)
    player.pit_stops += 1
    game_state.last_roll = {
        "player": player.name,
        "target": "stands",
        "d20": "-",
        "modifier": 0,
        "total": "-",
        "note": "Arrêt au stand effectué: pneus rafraîchis.",
        "engine_failure": False,
        "reliability_note": "",
    }

    return jsonify(serialize_state())


@app.post("/api/next")
def next_turn() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if state["finished"]:
        return jsonify({"error": "La course est terminée."}), 400

    segment = state["segment"]
    active = get_active_player()
    if active is not None and segment is not None:
        apply_tire_wear(active, segment)

    game_state.last_roll = None
    game_state.active_position_index += 1

    if game_state.active_position_index >= len(game_state.positions):
        game_state.active_position_index = 0
        segment_count = max(1, state["segment_count"])
        game_state.segment_index = (game_state.segment_index + 1) % segment_count
        if game_state.segment_index == 0:
            game_state.current_lap += 1

    return jsonify(serialize_state())


def run_local_server() -> None:
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)


if __name__ == "__main__":
    run_local_server()
