from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from openpyxl import load_workbook

app = Flask(__name__)

CIRCUIT_FILE = Path("circuit.xlsx")


@dataclass
class Player:
    player_id: int
    name: str
    engine_power: int
    downforce: int


class GameState:
    def __init__(self) -> None:
        self.players: list[Player] = []
        self.positions: list[int] = []
        self.segment_index = 0
        self.active_position_index = 0
        self.last_roll: dict[str, Any] | None = None

    @property
    def started(self) -> bool:
        return len(self.players) == 4


game_state = GameState()


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
                "index": int(row[0]),
                "type": row[1],
                "category": row[2],
                "length_m": float(row[3] or 0),
                "angle_deg": float(row[4] or 0),
            }
        )
    return segments


def stat_to_modifier(stat: int) -> int:
    return max(-4, min(5, stat - 5))


def compute_roll_modifier(player: Player, segment: dict[str, Any]) -> tuple[int, str]:
    if segment["type"] == "ligne_droite":
        base = stat_to_modifier(player.engine_power)
        bonus = 0
        if segment["length_m"] >= 180:
            bonus += 1
        if segment["length_m"] >= 260:
            bonus += 1
        modifier = max(-4, min(5, base + bonus))
        note = f"Ligne droite ({int(segment['length_m'])} m): bonus moteur +{bonus}."
        return modifier, note

    requirements = {
        "epingle": 3,
        "virage_lent": 5,
        "chicane": 6,
        "virage_rapide": 8,
    }
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

    modifier = max(-4, min(5, base + context_bonus))
    note = (
        f"{segment['category'].replace('_', ' ')}: besoin downforce {requirement}, "
        f"écart {gap:+d}, bonus contexte {context_bonus:+d}."
    )
    return modifier, note


def serialize_state() -> dict[str, Any]:
    segments = load_circuit_segments()
    by_id = {p.player_id: p for p in game_state.players}
    ranking = [asdict(by_id[pid]) for pid in game_state.positions]

    current_segment = segments[game_state.segment_index] if segments else None
    active_player = ranking[game_state.active_position_index] if ranking else None
    active_has_target = bool(game_state.active_position_index > 0)

    return {
        "started": game_state.started,
        "players": ranking,
        "segment": current_segment,
        "segment_index": game_state.segment_index,
        "segment_count": len(segments),
        "active_player": active_player,
        "active_has_target": active_has_target,
        "last_roll": game_state.last_roll,
    }


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/state")
def get_state() -> Any:
    return jsonify(serialize_state())


@app.post("/api/start")
def start_game() -> Any:
    payload = request.get_json(force=True)
    players_payload = payload.get("players", [])

    if len(players_payload) != 4:
        return jsonify({"error": "Il faut exactement 4 joueurs."}), 400

    players: list[Player] = []
    for idx, row in enumerate(players_payload, start=1):
        name = (row.get("name") or "").strip()
        engine = int(row.get("engine_power", 0))
        downforce = int(row.get("downforce", 0))

        if not name:
            return jsonify({"error": "Chaque joueur doit avoir un nom."}), 400
        if not (1 <= engine <= 10 and 1 <= downforce <= 10):
            return jsonify({"error": "Les stats doivent être entre 1 et 10."}), 400

        players.append(Player(idx, name, engine, downforce))

    game_state.players = players
    game_state.positions = [p.player_id for p in players]
    game_state.segment_index = 0
    game_state.active_position_index = 0
    game_state.last_roll = None

    return jsonify(serialize_state())


@app.post("/api/roll")
def roll_overtake() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400
    if not state["active_has_target"]:
        return jsonify({"error": "Le leader n'a personne à dépasser."}), 400

    active = game_state.positions[game_state.active_position_index]
    player = next(p for p in game_state.players if p.player_id == active)
    segment = state["segment"]
    if segment is None:
        return jsonify({"error": "Aucun segment disponible dans circuit.xlsx."}), 400

    modifier, note = compute_roll_modifier(player, segment)
    roll = random.randint(1, 20)
    total = roll + modifier

    target_id = game_state.positions[game_state.active_position_index - 1]
    target = next(p for p in game_state.players if p.player_id == target_id)

    game_state.last_roll = {
        "player": player.name,
        "target": target.name,
        "d20": roll,
        "modifier": modifier,
        "total": total,
        "note": note,
    }

    return jsonify(serialize_state())


@app.post("/api/resolve")
def resolve_roll() -> Any:
    payload = request.get_json(force=True)
    success = bool(payload.get("success"))

    if game_state.last_roll is None:
        return jsonify({"error": "Lancez un dé avant de résoudre."}), 400

    if success and game_state.active_position_index > 0:
        i = game_state.active_position_index
        game_state.positions[i - 1], game_state.positions[i] = (
            game_state.positions[i],
            game_state.positions[i - 1],
        )
        game_state.active_position_index -= 1

    game_state.last_roll = None
    return jsonify(serialize_state())


@app.post("/api/next")
def next_turn() -> Any:
    state = serialize_state()
    if not state["started"]:
        return jsonify({"error": "La course n'est pas démarrée."}), 400

    game_state.last_roll = None
    game_state.active_position_index += 1

    if game_state.active_position_index >= len(game_state.positions):
        game_state.active_position_index = 0
        segment_count = max(1, state["segment_count"])
        game_state.segment_index = (game_state.segment_index + 1) % segment_count

    return jsonify(serialize_state())


def run_local_server() -> None:
    """Lance le serveur local sans reloader pour compatibilité IDE (Spyder/Jupyter)."""
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)


if __name__ == "__main__":
    run_local_server()
