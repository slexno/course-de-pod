const setupForm = document.getElementById("setup-form");
const setupPanel = document.getElementById("setup-panel");
const racePanel = document.getElementById("race-panel");

const segmentInfo = document.getElementById("segment-info");
const activeInfo = document.getElementById("active-info");
const ranking = document.getElementById("ranking");
const rollResult = document.getElementById("roll-result");

const startBtn = document.getElementById("start-btn");
const rollBtn = document.getElementById("roll-btn");
const successBtn = document.getElementById("success-btn");
const failBtn = document.getElementById("fail-btn");
const nextBtn = document.getElementById("next-btn");

for (let i = 1; i <= 4; i++) {
  const row = document.createElement("div");
  row.className = "player-grid";
  row.innerHTML = `
    <input name="name-${i}" placeholder="Joueur ${i}" value="Joueur ${i}" />
    <input name="engine-${i}" type="number" min="1" max="10" value="6" />
    <input name="downforce-${i}" type="number" min="1" max="10" value="6" />`;
  setupForm.appendChild(row);
}

async function postJSON(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Erreur API");
  return data;
}

function renderState(state) {
  if (!state.started) return;

  setupPanel.classList.add("hidden");
  racePanel.classList.remove("hidden");

  const seg = state.segment;
  segmentInfo.innerHTML = seg
    ? `<strong>Segment ${state.segment_index + 1}/${state.segment_count}</strong> — ${seg.type} (${seg.category}) - ${Math.round(seg.length_m)} m`
    : "Aucun segment trouvé dans circuit.xlsx";

  activeInfo.textContent = state.active_player
    ? `Actif: ${state.active_player.name} ${state.active_has_target ? "(peut tenter un dépassement)" : "(leader, pas de cible)"}`
    : "";

  ranking.innerHTML = "";
  state.players.forEach((player, idx) => {
    const li = document.createElement("li");
    li.textContent = `${idx + 1}. ${player.name} | Engine ${player.engine_power} | Downforce ${player.downforce}`;
    ranking.appendChild(li);
  });

  if (state.last_roll) {
    const r = state.last_roll;
    rollResult.innerHTML = `
      <strong>${r.player}</strong> tente sur <strong>${r.target}</strong><br/>
      d20: ${r.d20} | mod: ${r.modifier >= 0 ? "+" : ""}${r.modifier} | total: <strong>${r.total}</strong><br/>
      <em>${r.note}</em>`;
  } else {
    rollResult.textContent = "Aucun jet en cours.";
  }
}

startBtn.addEventListener("click", async () => {
  const players = [];
  for (let i = 1; i <= 4; i++) {
    players.push({
      name: setupForm.querySelector(`[name='name-${i}']`).value,
      engine_power: Number(setupForm.querySelector(`[name='engine-${i}']`).value),
      downforce: Number(setupForm.querySelector(`[name='downforce-${i}']`).value),
    });
  }

  try {
    const state = await postJSON("/api/start", { players });
    renderState(state);
  } catch (err) {
    alert(err.message);
  }
});

rollBtn.addEventListener("click", async () => {
  try {
    renderState(await postJSON("/api/roll"));
  } catch (err) {
    alert(err.message);
  }
});

successBtn.addEventListener("click", async () => {
  try {
    renderState(await postJSON("/api/resolve", { success: true }));
  } catch (err) {
    alert(err.message);
  }
});

failBtn.addEventListener("click", async () => {
  try {
    renderState(await postJSON("/api/resolve", { success: false }));
  } catch (err) {
    alert(err.message);
  }
});

nextBtn.addEventListener("click", async () => {
  try {
    renderState(await postJSON("/api/next"));
  } catch (err) {
    alert(err.message);
  }
});
