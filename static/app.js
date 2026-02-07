const setupForm = document.getElementById("setup-form");
const setupPanel = document.getElementById("setup-panel");
const racePanel = document.getElementById("race-panel");
const lapsInput = document.getElementById("laps-input");

const raceMeta = document.getElementById("race-meta");
const segmentInfo = document.getElementById("segment-info");
const activeInfo = document.getElementById("active-info");
const ranking = document.getElementById("ranking");
const rollResult = document.getElementById("roll-result");
const errorBox = document.getElementById("error-box");

const startBtn = document.getElementById("start-btn");
const rollBtn = document.getElementById("roll-btn");
const successBtn = document.getElementById("success-btn");
const failBtn = document.getElementById("fail-btn");
const pitBtn = document.getElementById("pit-btn");
const nextBtn = document.getElementById("next-btn");
const weatherSelect = document.getElementById("weather-select");
const weatherBtn = document.getElementById("weather-btn");

for (let i = 1; i <= 4; i++) {
  const row = document.createElement("div");
  row.className = "player-grid";
  row.innerHTML = `
    <input name="name-${i}" placeholder="Joueur ${i}" value="Joueur ${i}" />
    <input name="engine-${i}" type="number" min="1" max="10" value="6" />
    <input name="downforce-${i}" type="number" min="1" max="10" value="6" />
    <input name="skill-${i}" type="number" min="1" max="10" value="6" />
    <input name="reliability-${i}" type="number" min="1" max="10" value="6" />`;
  setupForm.appendChild(row);
}

function showError(message = "") {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return { error: (await response.text()) || "Réponse non JSON reçue." };
}

async function requestJSON(url, method = "GET", body = null) {
  const options = { method, headers: {} };
  if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  const data = await parseResponse(response);
  if (!response.ok) throw new Error(data.error || `Erreur API (${response.status})`);
  return data;
}

function renderState(state) {
  const isStarted = !!state.started;
  setupPanel.classList.toggle("hidden", isStarted);
  racePanel.classList.toggle("hidden", !isStarted);

  if (!isStarted) return;

  weatherSelect.value = state.weather;
  raceMeta.innerHTML = `<strong>Tour ${state.lap}/${state.total_laps}</strong> | Météo: ${state.weather}${state.finished ? " | <span class='warning'>Course terminée</span>" : ""}`;

  const seg = state.segment;
  segmentInfo.innerHTML = seg
    ? `<strong>Segment ${state.segment_index + 1}/${state.segment_count}</strong> — ${seg.type} (${seg.category}) - ${Math.round(seg.length_m)} m`
    : `Aucun segment trouvé. Vérifie: ${state.circuit_file}`;

  activeInfo.textContent = state.active_player
    ? `Actif: ${state.active_player.name} (${state.active_player.status}) ${state.active_has_target ? "- peut tenter un dépassement" : "- leader"}`
    : "";

  ranking.innerHTML = "";
  state.players.forEach((player, idx) => {
    const li = document.createElement("li");
    li.textContent = `${idx + 1}. ${player.name} [${player.status}] | ENG ${player.engine_power} | DF ${player.downforce} | SKILL ${player.driver_skill} | REL ${player.reliability} | Wear ${player.tire_wear}% | Pits ${player.pit_stops}`;
    ranking.appendChild(li);
  });

  const disabledRace = state.finished;
  rollBtn.disabled = disabledRace || !state.active_has_target || state.active_player?.status !== "running";
  pitBtn.disabled = disabledRace || state.active_player?.status !== "running";
  nextBtn.disabled = disabledRace;
  weatherBtn.disabled = disabledRace;
  successBtn.disabled = !state.last_roll;
  failBtn.disabled = !state.last_roll;

  if (state.last_roll) {
    const r = state.last_roll;
    rollResult.innerHTML = `
      <strong>${r.player}</strong> vs <strong>${r.target}</strong><br/>
      d20: ${r.d20} | mod: ${r.modifier >= 0 ? "+" : ""}${r.modifier} | total: <strong>${r.total}</strong><br/>
      <em>${r.note}</em>
      ${r.reliability_note ? `<br/><span class='warning'>${r.reliability_note}</span>` : ""}`;
  } else {
    rollResult.textContent = "Aucun jet en cours.";
  }
}

startBtn.addEventListener("click", async () => {
  showError("");
  const players = [];

  for (let i = 1; i <= 4; i++) {
    players.push({
      name: setupForm.querySelector(`[name='name-${i}']`).value,
      engine_power: Number(setupForm.querySelector(`[name='engine-${i}']`).value),
      downforce: Number(setupForm.querySelector(`[name='downforce-${i}']`).value),
      driver_skill: Number(setupForm.querySelector(`[name='skill-${i}']`).value),
      reliability: Number(setupForm.querySelector(`[name='reliability-${i}']`).value),
    });
  }

  try {
    const laps = Number(lapsInput.value);
    renderState(await requestJSON("/api/start", "POST", { players, total_laps: laps }));
  } catch (err) {
    showError(err.message);
  }
});

weatherBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/weather", "POST", { weather: weatherSelect.value }));
  } catch (err) {
    showError(err.message);
  }
});

rollBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/roll", "POST", {}));
  } catch (err) {
    showError(err.message);
  }
});

successBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/resolve", "POST", { success: true }));
  } catch (err) {
    showError(err.message);
  }
});

failBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/resolve", "POST", { success: false }));
  } catch (err) {
    showError(err.message);
  }
});

pitBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/pit", "POST", {}));
  } catch (err) {
    showError(err.message);
  }
});

nextBtn.addEventListener("click", async () => {
  showError("");
  try {
    renderState(await requestJSON("/api/next", "POST", {}));
  } catch (err) {
    showError(err.message);
  }
});

(async function bootstrap() {
  try {
    renderState(await requestJSON("/api/state"));
  } catch (err) {
    showError(`Impossible de charger l'état initial: ${err.message}`);
  }
})();
