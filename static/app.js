const setupForm = document.getElementById("setup-form");
const setupPanel = document.getElementById("setup-panel");
const racePanel = document.getElementById("race-panel");
const endPanel = document.getElementById("end-panel");
const playerCountInput = document.getElementById("player-count-input");
const lapsInput = document.getElementById("laps-input");
const errorBox = document.getElementById("error-box");

const raceMeta = document.getElementById("race-meta");
const segmentInfo = document.getElementById("segment-info");
const activeInfo = document.getElementById("active-info");
const ranking = document.getElementById("ranking");
const attackBox = document.getElementById("attack-box");
const defenseBox = document.getElementById("defense-box");
const trackSvg = document.getElementById("track-svg");
const trackPath = document.getElementById("track-path");
const setupTrackSvg = document.getElementById("setup-track-svg");
const setupTrackPath = document.getElementById("setup-track-path");
const podium = document.getElementById("podium");
const others = document.getElementById("others");

const startBtn = document.getElementById("start-btn");
const restartBtn = document.getElementById("restart-btn");
const restartBtn2 = document.getElementById("restart-btn-2");
const weatherBtn = document.getElementById("weather-btn");
const weatherSelect = document.getElementById("weather-select");

const overtakeBtn = document.getElementById("overtake-btn");
const dangerBtn = document.getElementById("danger-btn");
const prepBtn = document.getElementById("prep-btn");
const nextSectionBtn = document.getElementById("next-section-btn");
const passBtn = document.getElementById("pass-btn");
const nextTurnBtn = document.getElementById("next-turn-btn");
const generateTrackBtn = document.getElementById("generate-track-btn");
const turnFastInput = document.getElementById("turn-fast-input");
const turnSlowInput = document.getElementById("turn-slow-input");
const chicaneInput = document.getElementById("chicane-input");
const hairpinInput = document.getElementById("hairpin-input");

function buildPlayerRows(count) {
  setupForm.innerHTML = "";
  for (let i = 1; i <= count; i++) {
    const row = document.createElement("div");
    row.className = "player-grid";
    row.innerHTML = `
      <input name="name-${i}" placeholder="Pilote ${i}" value="Pilote ${i}" />
      <input name="engine-${i}" type="number" min="0" max="20" value="10" />
      <input name="downforce-${i}" type="number" min="0" max="20" value="10" />
      <input name="dex-${i}" type="number" min="0" max="20" value="10" />
      <input name="aggr-${i}" type="number" min="0" max="20" value="10" />`;
    setupForm.appendChild(row);
  }
}

buildPlayerRows(4);

playerCountInput.addEventListener("change", () => {
  const count = Math.max(3, Math.min(10, Number(playerCountInput.value || 4)));
  playerCountInput.value = String(count);
  buildPlayerRows(count);
});

function showError(message = "") {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

async function parseResponse(response) {
  const c = response.headers.get("content-type") || "";
  if (c.includes("application/json")) return response.json();
  return { error: (await response.text()) || "Réponse non JSON." };
}

async function api(url, method = "GET", body = null) {
  const init = { method, headers: {} };
  if (body) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  const data = await parseResponse(res);
  if (!res.ok) throw new Error(data.error || `Erreur API ${res.status}`);
  return data;
}


function sectionColor(sectionType, sectionCategory) {
  if (sectionCategory === "ligne_des_stands") return "#f59e0b";
  if (sectionCategory === "retour_stands") return "#eab308";
  if (sectionCategory === "chicane") return "#a855f7";
  if (sectionCategory === "epingle") return "#ef4444";
  if (sectionCategory === "virage_lent") return "#f97316";
  if (sectionCategory === "virage_rapide") return "#22c55e";
  if (sectionType === "ligne_droite") return "#60a5fa";
  return "#cbd5e1";
}

function hexToRgba(hex, alpha) {
  const clean = String(hex || "").replace("#", "").trim();
  if (clean.length !== 6) return `rgba(15,23,42,${alpha})`;
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function renderTrack(track, svgElement, pathElement, showMarkers) {
  const markers = (track && track.markers) || [];
  const path = (track && track.path) || [];
  const sections = (track && track.sections) || [];
  const svgNs = "http://www.w3.org/2000/svg";

  pathElement.setAttribute("points", path.map((p) => `${p.x},${p.y}`).join(" "));

  const existingSections = svgElement.querySelector(".track-sections-layer");
  if (existingSections) existingSections.remove();
  const existingLayer = svgElement.querySelector(".track-markers-layer");
  if (existingLayer) existingLayer.remove();

  const sectionLayer = document.createElementNS(svgNs, "g");
  sectionLayer.setAttribute("class", "track-sections-layer");
  sections.forEach((section) => {
    const line = document.createElementNS(svgNs, "line");
    line.setAttribute("x1", String(section.start.x));
    line.setAttribute("y1", String(section.start.y));
    line.setAttribute("x2", String(section.end.x));
    line.setAttribute("y2", String(section.end.y));
    line.setAttribute("stroke", sectionColor(section.type, section.category));
    line.setAttribute("class", "track-section-segment");
    sectionLayer.appendChild(line);
  });
  svgElement.insertBefore(sectionLayer, pathElement);

  if (!showMarkers) return;

  const layer = document.createElementNS(svgNs, "g");
  layer.setAttribute("class", "track-markers-layer");

  markers.forEach((m) => {
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", String(m.x));
    circle.setAttribute("cy", String(m.y));
    circle.setAttribute("r", "1.9");
    circle.setAttribute("fill", m.color || "#22c55e");
    circle.setAttribute("class", "track-marker");

    const label = document.createElementNS(svgNs, "text");
    label.setAttribute("x", String(m.x));
    label.setAttribute("y", String(m.y));
    label.setAttribute("class", "track-marker-label");
    label.textContent = (m.name && m.name[0] ? m.name[0] : "?").toUpperCase();

    layer.appendChild(circle);
    layer.appendChild(label);
  });

  svgElement.appendChild(layer);
}

function renderLastDuel(lastDuel) {
  attackBox.className = "duel-box";
  defenseBox.className = "duel-box";

  if (!lastDuel) {
    attackBox.textContent = "-";
    defenseBox.textContent = "-";
    return;
  }

  if (lastDuel.info) {
    attackBox.textContent = lastDuel.info;
    defenseBox.textContent = "-";
    return;
  }

  const attackSuccess = !!lastDuel.success;
  const defenseSuccess = !lastDuel.success;
  attackBox.classList.add(attackSuccess ? "result-success" : "result-fail");
  defenseBox.classList.add(defenseSuccess ? "result-success" : "result-fail");

  attackBox.innerHTML = `
    <strong>${lastDuel.attacker}</strong><br/>
    d20: ${lastDuel.attack_roll} | mod: ${lastDuel.attack_mod >= 0 ? "+" : ""}${lastDuel.attack_mod}
    <div class="duel-total">Total Attaque: ${lastDuel.attack_total}</div>
    ${lastDuel.attack_notes.join("<br/>")}
    ${lastDuel.dangerous ? "<br/><em>Dépassement dangereux</em>" : ""}
    ${lastDuel.risk_note ? `<br/><span class='warning'>${lastDuel.risk_note}</span>` : ""}`;

  defenseBox.innerHTML = `
    <strong>${lastDuel.defender}</strong><br/>
    d20: ${lastDuel.defense_roll} | mod: ${lastDuel.defense_mod >= 0 ? "+" : ""}${lastDuel.defense_mod}
    <div class="duel-total">Total Défense: ${lastDuel.defense_total}</div>
    ${lastDuel.defense_notes.join("<br/>")}<br/>
    <strong>${lastDuel.success ? "Dépassement réussi" : "Défense réussie"}</strong>`;
}

function renderRanking(players, activePlayerId) {
  ranking.innerHTML = "";
  players.forEach((p, idx) => {
    const card = document.createElement("div");
    card.className = `rank-card ${p.player_id === activePlayerId ? "active" : ""}`;
    card.style.background = hexToRgba(p.color || "#0f172a", 0.30);
    card.style.borderColor = p.color || "#334155";
    const isActive = p.player_id === activePlayerId;
    card.innerHTML = `
      <div class="rank-num">${isActive ? "🎯 " : ""}#${idx + 1}</div>
      <div>
        <strong>${p.name}</strong><br/>
        ENG ${p.engine_power} | DF ${p.downforce} | DEX ${p.dexterity} | AGR ${p.aggressiveness}<br/>
        Usure pneus: ${p.tire_wear.toFixed(1)}
      </div>`;
    ranking.appendChild(card);
  });
}

function renderEndStats(finalStats) {
  podium.innerHTML = "";
  others.innerHTML = "";
  if (!finalStats) return;

  finalStats.podium.forEach((p) => {
    const card = document.createElement("div");
    card.className = "rank-card podium-card";
    card.innerHTML = `<div class='rank-num'>#${p.position}</div><div><strong>${p.name}</strong><br/>Dépassements: ${p.successful_overtakes} | Défenses: ${p.successful_defenses} | Malus: ${p.malus_count}</div>`;
    podium.appendChild(card);
  });

  finalStats.others.forEach((p) => {
    const card = document.createElement("div");
    card.className = "rank-card";
    card.innerHTML = `<div class='rank-num'>#${p.position}</div><div><strong>${p.name}</strong><br/>Dépassements: ${p.successful_overtakes} | Défenses: ${p.successful_defenses} | Malus: ${p.malus_count}</div>`;
    others.appendChild(card);
  });
}

function renderState(state) {
  const started = !!state.started;
  setupPanel.classList.toggle("hidden", started);
  racePanel.classList.toggle("hidden", !started);

  const counts = state.circuit_counts || {};
  turnFastInput.value = counts.virage_rapide ?? turnFastInput.value;
  turnSlowInput.value = counts.virage_lent ?? turnSlowInput.value;
  chicaneInput.value = counts.chicane ?? chicaneInput.value;
  hairpinInput.value = counts.epingle ?? hairpinInput.value;
  renderTrack(state.track || {markers: [], path: []}, setupTrackSvg, setupTrackPath, false);

  if (!started) {
    endPanel.classList.add("hidden");
    return;
  }

  weatherSelect.value = state.weather;
  raceMeta.innerHTML = `<strong>Tour ${state.lap}/${state.total_laps}</strong> | Joueurs: ${state.player_count} | Météo: ${state.weather} (malus dextérité ${state.weather_dex_penalty})${state.finished ? " | <span class='warning'>Course terminée</span>" : ""}`;
  segmentInfo.textContent = state.segment
    ? `Section ${state.segment_index + 1}/${state.segment_count}: ${state.segment.type} (${state.segment.category})`
    : `Aucun segment trouvé dans ${state.circuit_file}`;
  activeInfo.textContent = state.active_player ? `🎯 TOUR EN COURS: ${state.active_player.name.toUpperCase()}` : "";

  renderLastDuel(state.last_duel);
  renderRanking(state.players || [], state.active_player ? state.active_player.player_id : null);
  renderTrack(state.track || {markers: [], path: []}, trackSvg, trackPath, true);

  const disabled = state.finished;
  [overtakeBtn, dangerBtn, prepBtn, nextSectionBtn, passBtn, nextTurnBtn, weatherBtn].forEach((b) => {
    b.disabled = disabled;
  });

  endPanel.classList.toggle("hidden", !state.finished);
  if (state.finished) renderEndStats(state.final_stats);
}

async function runAction(type) {
  showError("");
  try {
    renderState(await api("/api/action", "POST", { type }));
  } catch (err) {
    showError(err.message);
  }
}

startBtn.addEventListener("click", async () => {
  showError("");
  const count = Math.max(3, Math.min(10, Number(playerCountInput.value || 4)));
  const players = [];
  for (let i = 1; i <= count; i++) {
    players.push({
      name: setupForm.querySelector(`[name='name-${i}']`).value,
      engine_power: Number(setupForm.querySelector(`[name='engine-${i}']`).value),
      downforce: Number(setupForm.querySelector(`[name='downforce-${i}']`).value),
      dexterity: Number(setupForm.querySelector(`[name='dex-${i}']`).value),
      aggressiveness: Number(setupForm.querySelector(`[name='aggr-${i}']`).value),
    });
  }

  try {
    renderState(await api("/api/start", "POST", {
      players,
      total_laps: Number(lapsInput.value),
      circuit: {
        virage_rapide: Number(turnFastInput.value),
        virage_lent: Number(turnSlowInput.value),
        chicane: Number(chicaneInput.value),
        epingle: Number(hairpinInput.value),
      },
    }));
  } catch (err) {
    showError(err.message);
  }
});

const restart = async () => {
  showError("");
  try {
    renderState(await api("/api/restart", "POST", {}));
  } catch (err) {
    showError(err.message);
  }
};

restartBtn.addEventListener("click", restart);
restartBtn2.addEventListener("click", restart);

weatherBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await api("/api/weather", "POST", { weather: weatherSelect.value }));
  } catch (err) {
    showError(err.message);
  }
});

overtakeBtn.addEventListener("click", () => runAction("overtake"));
dangerBtn.addEventListener("click", () => runAction("dangerous_overtake"));
prepBtn.addEventListener("click", () => runAction("prepare"));
nextSectionBtn.addEventListener("click", () => runAction("next_section_bonus"));
passBtn.addEventListener("click", () => runAction("pass"));
nextTurnBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await api("/api/next-turn", "POST", {}));
  } catch (err) {
    showError(err.message);
  }
});


generateTrackBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await api("/api/circuit-preview", "POST", {
      virage_rapide: Number(turnFastInput.value),
      virage_lent: Number(turnSlowInput.value),
      chicane: Number(chicaneInput.value),
      epingle: Number(hairpinInput.value),
    }));
  } catch (err) {
    showError(err.message);
  }
});

(async function boot() {
  try {
    renderState(await api("/api/state"));
  } catch (err) {
    showError(err.message);
  }
})();
