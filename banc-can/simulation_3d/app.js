// Pupitre, instruments et boucle de la simulation : relie le moteur (bus.js) à la scène 3D.
import { Bench, STATE, MODES } from "./bus.js";
import { BenchScene, NODE_COLORS } from "./scene.js";
import { BIT_US, hex } from "./can.js";

const $ = (id) => document.getElementById(id);
const icd = await (await fetch("icd.json")).json();
const NAMES = ["PC", "N1", "N2", "N3", "N4"];
const SPEED_MIN = 2e-5;
const SPEED_MAX = 0.5;

let bench;
let playing = true;
let speed = 0.02;
let selected = "bus";
let lastFrame = null;
let pendingRows = [];
let lastVisual = 0;
let stepping = false;

// --- descriptions de l'inspecteur ------------------------------------------------

const INFO = {
  bus: {
    title: "Bus CAN",
    text: "Paire torsadée principale, CAN 2.0A à 500 kbit/s (bit de 2 µs). Les nœuds sont sur des dérivations courtes (≤ 0,3 m) et les deux terminaisons de 120 Ω sont aux extrémités physiques.",
    note: "Les trains de cubes montrent qui parle à qui, ralentis. Sur le vrai bus le signal parcourt la ligne en quelques dizaines de ns : tous les nœuds voient le même bit au même instant, comme l'éclairage du bus (dominant = allumé).",
    src: "docs/pinout.md §6 et §7, icd/bench_icd.yaml",
  },
  N1: { title: "N1 · Nucleo-G431KB", text: "Émet ENERGY_COMMAND (0x100) toutes les 20 ms, contendant de rang 1 au test d'arbitrage. FDCAN1 sur PA12 (TX) et PA11 (RX), transceiver TJA1051T/3 (VCC 5 V, VIO 3,3 V). Afficheur LCD 16×2 (firmware scope).", src: "docs/pinout.md §2, §5" },
  N2: { title: "N2 · Nucleo-G431KB", text: "Émet IMU_SPEED (0x200) toutes les 20 ms : MPU-6050 en I2C et capteur à effet Hall sur PA4 ; sans capteur, la séquence déterministe de l'ICD. Contendant de rang 2. Afficheur LCD 16×2.", src: "docs/pinout.md §2, icd/bench_icd.yaml" },
  N3: { title: "N3 · Nucleo-G431KB", text: "Émet TEMP_BATTERY (0x300) toutes les 20 ms : sonde DS18B20 en 1-Wire sur PA7 (tirage 4,7 kΩ). Contendant de rang 3.", src: "docs/pinout.md §2" },
  N4: { title: "N4 · Nucleo-G431KB", text: "Nœud fautif : n'émet que son heartbeat, et les modes de faute commandés par BENCH_CFG (babbling idiot, débit erroné, DLC incohérent, silencieux, bus-off maintenu). Même carte et même port FDCAN que N1 à N3.", src: "docs/pinout.md §2, docs/bringup.md" },
  PC: { title: "J5 · Adaptateur USB-CAN G69", text: "Remplace le CANable 2.0. STM32G431KBT6 (FDCAN1 sur PA11/PA12) + pont USB-série CH340C + TJA1051T/3, firmware slcan. Le PC y pilote le banc (BancCAN, canbench).", note: "Modèle 3D exporté du vrai PCB KiCad, celui envoyé à la factory ENSEA (cuivre nu).", src: "hardware/adaptateur_usb_can/" },
  RT1: { title: "RT1 · terminaison fixe", text: "120 Ω entre CAN_H et CAN_L à l'extrémité gauche de la ligne.", src: "docs/pinout.md §6" },
  RT2: { title: "RT2 · terminaison commutée", text: "120 Ω à l'extrémité droite, mise hors circuit par SW1 pour le test de perte de terminaison.", src: "docs/pinout.md §6, §8" },
  SW1: { title: "SW1 · perte de terminaison", text: "Fermé en fonctionnement nominal. Ouvert, il retire RT2 : la ligne n'est plus adaptée d'un côté. La simulation tire alors une erreur sur environ 4 % des trames ; ce taux est un choix de modèle, pas une mesure.", src: "docs/pinout.md §8" },
  SW2: { title: "SW2 · court-circuit CAN_H / CAN_L", text: "Ouvert en nominal. Fermé, la tension différentielle est nulle : le bus reste récessif. Chaque émetteur relit son SOF dominant récessif (erreur de bit, LEC 5), TEC +8 à chaque essai, puis bus-off. À ne fermer que brièvement sur le vrai banc.", src: "docs/pinout.md §8, TJA1051 §6" },
  SW3: { title: "SW3 · retrait à chaud de N4", text: "Fermé en nominal. Ouvert, N4 se retrouve seul : personne n'acquitte ses trames (erreur d'ACK), son TEC monte jusqu'à 128 puis s'arrête (règle de l'émetteur error-passive). Le reste du bus continue.", src: "docs/pinout.md §8, ISO 11898-1" },
  laptop: { title: "PC · BancCAN", text: "Interface graphique du banc : connexion à l'adaptateur en slcan, tests T1 à T6, décodage des trames selon l'ICD. L'écran reproduit la trace de la simulation.", src: "README.md, pc/canbench/" },
  alim: { title: "Alimentation de laboratoire", text: "12 V / 3 A vers le module abaisseur LM2596.", src: "schema/G69_Banc_CAN.pdf §3" },
  buck: { title: "Module LM2596", text: "Abaisseur 12 V → 5 V (≈ 2 A) : rail 5 V commun, VCC des quatre transceivers. Le VIO de chaque TJA1051T/3 vient du 3,3 V local de sa carte.", src: "schema/G69_Banc_CAN.pdf §3" },
};

// --- moteur ----------------------------------------------------------------------

function newBench() {
  bench = new Bench(icd);
  bench.on((type, p) => {
    if (type === "start") {
      if (p.seg === "bus" || !lastFrame || lastFrame.seg !== "bus" || lastFrame.end < bench.t) lastFrame = p;
      const now = performance.now();
      if (p.error || p.arbitration || now - lastVisual > 45) { lastVisual = now; scene?.frameStart(p); }
      if (p.arbitration) renderArbitration();
    }
    if (type === "end") { pendingRows.push(p); if (stepping) stepping = "done"; }
    if (type === "switch") syncSwitches();
  });
  if (scene) scene.bench = bench;
  lastFrame = null;
  pendingRows = [];
  $("trace").innerHTML = "";
  syncSwitches();
  renderArbitration();
}

let scene = null;
newBench();
scene = new BenchScene($("scene"), bench, {
  onSelect: select,
  onSwitch: (sw) => bench.setSwitch(sw, !bench.switches[sw]),
  onReady: () => { $("loading").hidden = true; },
});

// --- vitesse ---------------------------------------------------------------------

const toSlider = (s) => Math.round((Math.log10(s / SPEED_MIN) / Math.log10(SPEED_MAX / SPEED_MIN)) * 1000);
const fromSlider = (v) => SPEED_MIN * (SPEED_MAX / SPEED_MIN) ** (v / 1000);
function fmtDur(us) {
  if (us < 1000) return `${us.toFixed(us < 10 ? 1 : 0)} µs`;
  if (us < 1e6) return `${(us / 1000).toFixed(us < 1e4 ? 2 : 1)} ms`;
  return `${(us / 1e6).toFixed(2)} s`;
}
function setSpeed(s) {
  speed = s;
  $("speed").value = toSlider(s);
  const frameReal = (123 * BIT_US * 1e-6) / s;
  $("speedLabel").textContent = `1 s réelle = ${fmtDur(s * 1e6)} de bus. Une trame de 8 octets (≈ 123 bits) dure ${frameReal < 1 ? (frameReal * 1000).toFixed(0) + " ms" : frameReal.toFixed(1) + " s"} à l'écran.`;
  document.querySelectorAll("[data-speed]").forEach((b) => b.classList.toggle("on", Math.abs(Math.log10(+b.dataset.speed / s)) < 0.05));
}
$("speed").addEventListener("input", (e) => setSpeed(fromSlider(+e.target.value)));
document.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => setSpeed(+b.dataset.speed)));
setSpeed(speed);

$("play").addEventListener("click", () => {
  playing = !playing;
  $("play").textContent = playing ? "Pause" : "Lecture";
  $("play").setAttribute("aria-pressed", playing);
});
$("step").addEventListener("click", () => {
  playing = false;
  $("play").textContent = "Lecture";
  stepping = true;
  for (let i = 0; i < 40000 && stepping !== "done"; i++) bench.advance(25);
  stepping = false;
});

// --- pupitre ---------------------------------------------------------------------

function syncSwitches() {
  for (const sw of ["SW1", "SW2", "SW3"]) {
    const closed = bench.switches[sw];
    const fault = sw === "SW2" ? closed : !closed;
    const el = $(`sw-${sw}`);
    el.classList.toggle("fault", fault);
    el.querySelector("em").textContent = closed ? "fermé" : "ouvert";
    el.setAttribute("aria-pressed", fault);
  }
  const r = bench.switches.SW2 ? "0 Ω : court-circuit" : bench.switches.SW1 ? "60 Ω (2 × 120 Ω, attendu)" : "120 Ω : une seule terminaison";
  $("ohm").textContent = `CAN_H–CAN_L hors tension : ${r}`;
}
document.querySelectorAll("[data-sw]").forEach((b) => b.addEventListener("click", () => { bench.setSwitch(b.dataset.sw, !bench.switches[b.dataset.sw]); select(b.dataset.sw); }));

$("cfgMode").innerHTML = MODES.map((m, i) => `<option value="${i}" ${i === 1 ? "selected" : ""}>${i} · ${m}</option>`).join("");
$("cfgSend").addEventListener("click", () => {
  const param = parseInt($("cfgParam").value, 16) || 0;
  bench.sendCfg(+$("cfgTarget").value, +$("cfgMode").value, Math.max(1, +$("cfgDur").value || 1000), param);
});
$("cfgRevoke").addEventListener("click", () => bench.sendCfg(+$("cfgTarget").value, 0, 0));
$("arbitrage").addEventListener("click", () => {
  bench.runArbitration();
  if (speed > 0.002) setSpeed(0.0004);
  showTab("arb");
  scene.view("bus");
});
$("hsi").addEventListener("change", (e) => { bench.hsi = e.target.checked; });
$("reset").addEventListener("click", () => { newBench(); $("hsi").checked = false; });
document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => { scene.view(b.dataset.view); if (b.dataset.view !== "overview") select(b.dataset.view === "bus" ? "bus" : b.dataset.view); }));

// --- état des nœuds et inspecteur -------------------------------------------------

function nodesTable() {
  $("nodes").innerHTML = NAMES.map((n) => {
    const x = bench.nodes[n];
    return `<tr data-node="${n}" class="${selected === n ? "sel" : ""}"><td><span class="tag" style="--c:${NODE_COLORS[n]}">${n}</span></td>
      <td><span class="pill s${x.state}">${STATE[x.state]}</span></td><td>${Math.min(x.tec, 255)}</td><td>${x.rec}</td><td>${x.sent}</td><td>${x.received}</td></tr>`;
  }).join("");
}
$("nodes").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-node]");
  if (tr) { select(tr.dataset.node); scene.view(tr.dataset.node); }
});

function select(key) {
  selected = key;
  scene?.select(key);
  inspector();
  nodesTable();
}

function inspector() {
  const info = INFO[selected] || INFO.bus;
  const n = bench.nodes[selected];
  const sw = selected.startsWith("SW") ? `<div class="actions"><button class="btn primary" data-toggle="${selected}">Basculer ${selected}</button></div>` : "";
  const actions = n && selected !== "PC"
    ? `<div class="actions"><button class="btn" data-cfg="1">Babbling idiot</button><button class="btn" data-cfg="2">250 kbit/s</button><button class="btn" data-cfg="4">Silencieux</button><button class="btn" data-cfg="5">Bus-off maintenu</button></div><p class="hint">BENCH_CFG envoyé par le PC à ${selected}, pour 1 s.</p>`
    : "";
  $("inspector").innerHTML = `<h2>Inspecteur</h2><h3>${info.title}</h3><p>${info.text}</p>${info.note ? `<p class="hint">${info.note}</p>` : ""}<div id="insLive">${liveHtml()}</div>${sw}${actions}<p class="src">Source : ${info.src}</p>`;
}
$("inspector").addEventListener("click", (e) => {
  const cfg = e.target.closest("[data-cfg]");
  if (cfg) bench.sendCfg(bench.nodes[selected].nodeId, +cfg.dataset.cfg, 1000, 0x400);
  const tg = e.target.closest("[data-toggle]");
  if (tg) bench.setSwitch(tg.dataset.toggle, !bench.switches[tg.dataset.toggle]);
});

function liveHtml() {
  const n = bench.nodes[selected];
  let live = "";
  if (n) {
    const rx = n.lastRx ? `${hex(n.lastRx.id)} ${n.lastRx.name}` : "—";
    live = `<dl class="kv">
      <dt>État</dt><dd class="s${n.state}">${STATE[n.state]}</dd>
      <dt>TEC / REC</dt><dd>${Math.min(n.tec, 255)} / ${n.rec}${n.state === 3 ? ` · reprise ${Math.min(128, n.recovery)}/128 × 11 bits` : ""}</dd>
      <dt>LEC</dt><dd>${["0 aucune", "1 bourrage", "2 forme", "3 acquittement", "4 bit récessif", "5 bit dominant", "6 CRC"][n.lec] || n.lec}</dd>
      <dt>Mode</dt><dd>${MODES[n.mode]}${n.mode ? ` (encore ${fmtDur(Math.max(0, n.modeUntil - bench.t))})` : ""}</dd>
      <dt>Émises / reçues</dt><dd>${n.sent} / ${n.received}</dd>
      <dt>Perdues</dt><dd>${n.lost}</dd>
      <dt>File d'émission</dt><dd>${n.queue.map((f) => hex(f.id)).join(" ") || "vide"}</dd>
      <dt>Dernière reçue</dt><dd>${rx}</dd></dl>`;
  } else if (selected === "bus") {
    live = `<dl class="kv"><dt>Débit</dt><dd>500 kbit/s (bit = 2 µs)</dd><dt>Trames</dt><dd>${bench.stats.ok} correctes, ${bench.stats.err} en erreur</dd><dt>Charge</dt><dd>${(bench.load() * 100).toFixed(1)} %</dd></dl>`;
  } else if (selected.startsWith("SW")) {
    live = `<dl class="kv"><dt>Position</dt><dd>${bench.switches[selected] ? "fermé" : "ouvert"}</dd><dt>Nominal</dt><dd>${selected === "SW2" ? "ouvert" : "fermé"}</dd></dl>`;
  }
  return live;
}

// --- trace ------------------------------------------------------------------------

function fmtVal(v) {
  return Number.isInteger(v) ? String(v) : (Math.round(v * 10000) / 10000).toString();
}
function decodeText(e) {
  if (!e.ok) return e.cause || "erreur";
  if (e.dlc !== 8 && bench.frames[e.id]) return `DLC ${e.dlc} au lieu de 8 (incohérent avec l'ICD)`;
  const d = bench.decode(e.id, e.data);
  if (!d) return e.tag || "";
  const meta = bench.frames[e.id];
  if (meta.name.startsWith("HEARTBEAT")) return `${STATE[d.ctrl_state]} · TEC ${d.tec} · REC ${d.rec} · mode ${d.current_mode}${d.clock_not_qualified ? " · HORLOGE NON QUALIFIÉE" : ""}`;
  if (meta.name === "BENCH_CFG") return `→ ${d.target_node ? "N" + d.target_node : "tous"} · ${MODES[d.mode] ?? d.mode} · ${d.duration_ms} ms${d.mode === 1 ? " · param " + hex(d.param_u16) : ""}`;
  if (meta.name === "BENCH_RESULT") return `N${d.node_id} · mode ${d.mode} · statut ${["succès", "refusé", "interrompu", "non supporté"][d.status]} · émises ${d.frames_sent}`;
  if (!meta.signals.length) return e.tag === "ARM" || e.tag === "GO" ? `${meta.name} (contenu nul)` : "";
  return meta.signals.filter((s) => !/counter|checksum|present/.test(s.name)).map((s) => `${s.name} ${fmtVal(d[s.name])}${s.unit ? " " + s.unit : ""}`).join(" · ");
}
function flushTrace() {
  if (!pendingRows.length) return;
  const rows = pendingRows.slice(-60).reverse().map((e) => {
    const data = e.data.slice(0, 8).map((b) => b.toString(16).toUpperCase().padStart(2, "0")).join(" ");
    return `<tr class="${e.ok ? "" : "err"}"><td>${(e.start / 1000).toFixed(3)}</td><td><span class="tag" style="--c:${NODE_COLORS[e.tx]}">${e.tx}</span></td><td>${hex(e.id)}</td><td>${e.name}</td><td>${e.dlc}</td><td>${data}</td><td>${e.fullBits.length}</td><td class="dec">${decodeText({ ...e, cause: e.error?.cause })}</td></tr>`;
  }).join("");
  pendingRows = [];
  const tb = $("trace");
  tb.insertAdjacentHTML("afterbegin", rows);
  while (tb.rows.length > 200) tb.deleteRow(-1);
}

// --- arbitrage --------------------------------------------------------------------

function renderArbitration() {
  const a = bench.lastArbitration;
  if (!a) {
    $("pane-arb").innerHTML = `<p class="hint">Aucun arbitrage pour l'instant. Lancer <b>T3 · Arbitrage ARM / GO</b> : après GO, N1, N2 et N3 commencent leur trame au même bit.</p>`;
    return;
  }
  const head = `<tr><th class="name">Nœud</th><th>ID</th><th>SOF</th>${[...Array(11)].map((_, i) => `<th>ID${10 - i}</th>`).join("")}</tr>`;
  const row = (name, id, lostAt, color) => {
    const cells = [`<td class="b0">0</td>`];
    for (let i = 0; i < 11; i++) {
      const v = (id >> (10 - i)) & 1;
      const cls = [v === 0 ? "b0" : "", lostAt >= 0 && i > lostAt ? "lost" : "", i === lostAt ? "cut" : ""].join(" ");
      cells.push(`<td class="${cls}">${v}</td>`);
    }
    return `<tr><td class="name"><span class="tag" style="--c:${color}">${name}</span></td><td>${hex(id)}</td>${cells.join("")}</tr>`;
  };
  const rows = a.contenders.map((c) => row(c.node, c.id, c.lostAt, NODE_COLORS[c.node])).join("");
  const losers = a.contenders.filter((c) => c.lostAt >= 0);
  const text = losers.map((c) => `${c.node} émet un 1 récessif au bit ID${10 - c.lostAt} mais relit le 0 dominant de ${a.winner} : il perd l'arbitrage et passe en réception, sans rien détruire.`).join(" ");
  $("pane-arb").innerHTML = `<div class="wrap"><table>${head}${rows}${row("bus (ET câblé)", a.id, -1, "#888")}</table></div>
    <p class="hint">À t = ${(a.t / 1000).toFixed(3)} ms, ${a.contenders.length} nœuds démarrent ensemble. Un 0 (dominant) l'emporte sur un 1 (récessif) : le bus réalise un ET logique. ${text} ${a.winner} gagne avec ${hex(a.id)}, l'identifiant le plus faible ; les perdants réémettent dès que le bus se libère, d'où l'ordre 0x100, 0x200, 0x300 dans la trace.</p>`;
}

// --- oscilloscope : trame bit à bit -------------------------------------------------

const FIELD_COLORS = { SOF: "#8fd", ID: "#ffd166", RTR: "#9ad", IDE: "#9ad", r0: "#9ad", DLC: "#c9a0ff", DATA: "#7fd1ff", CRC: "#ff9fb2", "CRC delim": "#777", ACK: "#5fe08a", "ACK delim": "#777", EOF: "#888" };
function drawScope() {
  const c = $("scopeCanvas");
  const box = c.parentElement.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio, 2);
  if (c.width !== Math.round(box.width * dpr) || c.height !== Math.round(box.height * dpr)) { c.width = Math.round(box.width * dpr); c.height = Math.round(box.height * dpr); }
  const g = c.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = box.width, H = box.height;
  g.fillStyle = "#071113";
  g.fillRect(0, 0, W, H);
  const f = lastFrame;
  g.font = "12px 'IBM Plex Mono', monospace";
  if (!f) { g.fillStyle = "#b8d3cf"; g.fillText("En attente d'une trame…", 16, 24); return; }
  const live = bench.t < f.end;
  const pos = (bench.t - f.start) / BIT_US;
  const shown = f.error ? [...f.bits, ...Array(6).fill({ v: 0, field: "drapeau d'erreur", err: true }), ...Array(8).fill({ v: 1, field: "délimiteur d'erreur", err: true })] : f.fullBits;
  const left = 54, right = 14, top = 46;
  const n = shown.length;
  const bw = (W - left - right) / n;
  const yH = (v) => top + 18 + (v === 0 ? 0 : 1) * ((H - top - 60) / 4);
  const yL = (v) => top + 18 + (v === 0 ? 3 : 2) * ((H - top - 60) / 4) + 6;

  // Titre
  g.fillStyle = "#b8d3cf";
  const crcVal = parseInt(f.fullBits.filter((b) => b.field === "CRC" && !b.stuff).map((b) => b.v).join(""), 2);
  g.fillText(`${f.tx} → ${hex(f.id)} ${f.name} · DLC ${f.dlc} · ${f.fullBits.length} bits dont ${f.fullBits.filter((b) => b.stuff).length} de bourrage · CRC ${hex(crcVal, 4)} · ${fmtDur(f.fullBits.length * BIT_US)}${f.error ? " · ERREUR : " + f.error.cause : live ? " · en cours" : ""}`, 12, 18);

  // Champs
  let i0 = 0;
  for (let i = 1; i <= n; i++) {
    if (i === n || shown[i].field !== shown[i0].field) {
      const fld = shown[i0].field;
      g.fillStyle = shown[i0].err ? "#ff5d63" : FIELD_COLORS[fld] || "#888";
      g.globalAlpha = 0.16;
      g.fillRect(left + i0 * bw, top, (i - i0) * bw, H - top - 22);
      g.globalAlpha = 1;
      const w = (i - i0) * bw;
      if (w > 20) {
        g.fillText(fld === "ID" ? `ID ${hex(f.id)}` : fld === "DATA" ? `DATA ${f.dlc} o` : fld, left + i0 * bw + 2, top + 12, w - 4);
      }
      i0 = i;
    }
  }
  // Grille et étiquettes de tension
  g.strokeStyle = "#15302f";
  g.lineWidth = 1;
  for (let i = 0; i <= n; i += 10) { g.beginPath(); g.moveTo(left + i * bw, top); g.lineTo(left + i * bw, H - 22); g.stroke(); }
  g.fillStyle = "#6f8f8a";
  g.fillText("3,5 V", 6, yH(0) + 4);
  g.fillText("2,5 V", 6, yH(1) + 4);
  g.fillText("1,5 V", 6, yL(0) + 4);
  g.fillText("2,5 V", 6, yL(1) + 4);
  for (let i = 0; i <= n; i += 20) g.fillText(`${i}`, left + i * bw - 4, H - 6);

  // Traces CAN_H et CAN_L
  for (const [yf, color, name] of [[yH, "#ff6a48", "CAN_H"], [yL, "#4aa6ff", "CAN_L"]]) {
    g.strokeStyle = color;
    g.lineWidth = 2;
    g.beginPath();
    for (let i = 0; i < n; i++) {
      const y = yf(shown[i].v);
      if (i === 0) g.moveTo(left, y); else g.lineTo(left + i * bw, y);
      g.lineTo(left + (i + 1) * bw, y);
    }
    g.stroke();
    g.fillStyle = color;
    g.fillText(name, W - right - 44, yf(1) - 6);
  }
  // Bits de bourrage et bit en erreur
  for (let i = 0; i < n; i++) {
    if (shown[i].stuff) { g.fillStyle = "#ffd166"; g.beginPath(); g.moveTo(left + (i + 0.5) * bw, H - 34); g.lineTo(left + (i + 0.5) * bw - 4, H - 26); g.lineTo(left + (i + 0.5) * bw + 4, H - 26); g.fill(); }
  }
  if (f.error) { g.strokeStyle = "#ff5d63"; g.lineWidth = 2; g.strokeRect(left + f.error.bit * bw, top, bw, H - top - 22); }
  // Partie pas encore émise, curseur
  if (live) {
    const x = left + Math.max(0, Math.min(n, pos)) * bw;
    g.fillStyle = "rgba(7,17,19,.72)";
    g.fillRect(x, top, W - right - x, H - top - 22);
    g.strokeStyle = "#e8fff9";
    g.beginPath(); g.moveTo(x, top - 4); g.lineTo(x, H - 22); g.stroke();
  }
  g.fillStyle = "#ffd166";
  g.fillText("▲ bit de bourrage", W - right - 150, top - 10);
}

// --- onglets ----------------------------------------------------------------------

const LEGENDS = {
  trace: "Trames dans l'ordre d'émission, décodées selon l'ICD",
  bits: "Niveaux CAN_H et CAN_L de la trame en cours ou de la dernière",
  arb: "Bits d'identifiant au dernier arbitrage disputé",
};
function showTab(name) {
  document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === name));
  for (const t of ["trace", "bits", "arb"]) $(`pane-${t}`).hidden = t !== name;
  $("legend").textContent = LEGENDS[name];
  try { localStorage.setItem("banc3d.tab", name); } catch {}
}
document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
let firstTab = "trace";
try { firstTab = localStorage.getItem("banc3d.tab") || "trace"; } catch {}
showTab(["trace", "bits", "arb"].includes(firstTab) ? firstTab : "trace");

// --- afficheurs ----------------------------------------------------------------------

function lcdLines(name) {
  const n = bench.nodes[name];
  if (bench.hsi) return ["HSI - NON VALIDE", `${["ACTIF", "WARN", "PASSIF", "BUS-OFF"][n.state]} T${Math.min(n.tec, 255)}`];
  const rx = n.lastRx ? hex(n.lastRx.id) : "-----";
  return [`RX ${rx} n=${n.received}`, `${["ACTIF", "WARN", "PASSIF", "BUS-OFF"][n.state]} T${Math.min(n.tec, 255)} R${n.rec}`];
}
function laptopDraw(g, w, h) {
  g.fillStyle = "#0f1a1e";
  g.fillRect(0, 0, w, h);
  g.fillStyle = "#1b2a30";
  g.fillRect(0, 0, w, 54);
  g.fillStyle = "#e2e9ec";
  g.font = "600 28px 'IBM Plex Sans Condensed', sans-serif";
  g.fillText("BancCAN · slcan · 500 kbit/s", 20, 37);
  NAMES.forEach((name, i) => {
    const s = bench.nodes[name].state;
    g.fillStyle = NODE_COLORS[name];
    g.fillRect(20 + i * 198, 72, 14, 14);
    g.fillStyle = ["#47c07c", "#e2b23f", "#f08a45", "#ff5d63"][s];
    g.font = "500 22px 'IBM Plex Mono', monospace";
    g.fillText(`${name} ${["actif", "warn", "passif", "bus-off"][s]}`, 42, 87);
    g.translate(198, 0);
  });
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.font = "21px 'IBM Plex Mono', monospace";
  bench.trace.slice(-17).reverse().forEach((e, i) => {
    g.fillStyle = e.ok ? "#b8d3cf" : "#ff5d63";
    const data = e.data.slice(0, 8).map((b) => b.toString(16).toUpperCase().padStart(2, "0")).join(" ");
    g.fillText(`${(e.t / 1000).toFixed(2).padStart(9)}  ${e.tx}  ${hex(e.id)}  [${e.dlc}]  ${e.ok ? data : "ERREUR"}`, 20, 130 + i * 29);
  });
}

// --- thème --------------------------------------------------------------------------

const mql = matchMedia("(prefers-color-scheme: dark)");
mql.addEventListener("change", () => scene.applyTheme());
new MutationObserver(() => scene.applyTheme()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

// --- boucle ------------------------------------------------------------------------

let prev = performance.now();
let slow = 0;
function frame(now) {
  const dt = Math.min(0.1, (now - prev) / 1000);
  prev = now;
  if (playing) bench.advance(dt * 1e6 * speed);
  scene.update(dt, playing ? speed : 0);
  if (!$("pane-bits").hidden) drawScope();
  slow += dt;
  if (slow > 0.12) {
    slow = 0;
    $("clock").textContent = `${(bench.t / 1e6).toFixed(3).replace(".", ",")} s`;
    const load = bench.load();
    $("loadVal").textContent = `${(load * 100).toFixed(1)} %`;
    $("loadBar").style.width = `${load * 100}%`;
    nodesTable();
    flushTrace();
    scene.refresh(lcdLines, laptopDraw);
    const live = $("insLive");
    if (live) live.innerHTML = liveHtml();
  }
  requestAnimationFrame(frame);
}
// Accès depuis la console du navigateur, pour explorer : banc.bench.nodes.N1, banc.scene…
window.banc = { get bench() { return bench; }, scene, setSpeed, frame };
select("bus");
requestAnimationFrame(frame);
