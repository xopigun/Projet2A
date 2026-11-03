// Moteur de simulation du banc : nœuds, contrôleurs CAN et bus, en temps simulé (µs).
//
// Ce qui est modélisé au niveau bit : arbitrage sur l'identifiant, bourrage, CRC, durée
// exacte de chaque trame, acquittement. Ce qui l'est au niveau trame : les erreurs (instant
// de détection tiré dans la trame), le confinement d'erreurs ISO 11898-1 (TEC/REC, états
// error-active, error-passive, bus-off, reprise après 128 × 11 bits récessifs).
// Le taux d'erreur sans terminaison (SW1 ouvert) est un choix de modèle, pas une mesure.

import { BIT_US, IFS_BITS, ERROR_FRAME_BITS, frameBits, packSignals, unpackSignals, arbitrationLoss, hex } from "./can.js";

export const STATE = ["error-active", "error-warning", "error-passive", "bus-off"];
export const MODES = ["normal", "babbling idiot", "débit erroné (250 kbit/s)", "DLC incohérent", "silencieux", "bus-off maintenu"];
const LEC = { STUFF: 1, FORM: 2, ACK: 3, BIT1: 4, BIT0: 5, CRC: 6 };
const TX_BUFFERS = 3; // FDCAN : 3 tampons d'émission
const P_ERR_SANS_TERMINAISON = 0.04;

function rng(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class Bench {
  constructor(icd, seed = 69) {
    this.icd = icd;
    this.rand = rng(seed);
    this.t = 0;
    this.frames = Object.fromEntries(Object.entries(icd.frames).map(([k, f]) => [parseInt(k, 16), f]));
    this.ids = icd.ids;
    this.switches = { SW1: true, SW2: false, SW3: true }; // positions nominales
    this.hsi = false; // SB9/SB10 non soudés : horloge non qualifiée sur N1 à N3
    this.listeners = new Set();
    this.trace = [];
    this.busyLog = []; // [début, fin] des occupations, pour la charge du bus
    this.lastArbitration = null;
    this.stats = { ok: 0, err: 0, errBy: {} };
    this.arbitrationWindow = false;

    const node = (name, extra) => ({
      name, tec: 0, rec: 0, state: 0, lec: 0, mode: 0, modeUntil: 0, param: 0,
      queue: [], sent: 0, received: 0, lost: 0, armRx: 0, step: 0, counter: 0,
      busOffAt: null, recovery: 0, lastRx: null, ledTx: -1e9, ...extra,
    });
    this.nodes = {
      PC: node("PC", { app: null }),
      N1: node("N1", { nodeId: 1, app: 0x100, appPhase: 0 }),
      N2: node("N2", { nodeId: 2, app: 0x200, appPhase: 6500 }),
      N3: node("N3", { nodeId: 3, app: 0x300, appPhase: 13000 }),
      N4: node("N4", { nodeId: 4, app: null }),
    };
    for (const n of Object.values(this.nodes)) {
      if (n.nodeId) n.nextHb = 100000 + 125000 * (n.nodeId - 1);
      if (n.app) n.nextApp = n.appPhase;
    }
    this.hbPeriod = 500000;
    this.appPeriod = 20000;
    this.segments = [];
    this.layout();
  }

  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(type, payload) { for (const fn of this.listeners) fn(type, payload); }

  // Segments électriques : le bus principal, et N4 seul quand SW3 l'isole.
  layout() {
    const all = Object.keys(this.nodes);
    const main = this.switches.SW3 ? all : all.filter((n) => n !== "N4");
    const old = this.segments;
    this.segments = [{ name: "bus", members: main, current: null, freeAt: this.t, idleSince: this.t }];
    if (!this.switches.SW3) this.segments.push({ name: "N4 isolé", members: ["N4"], current: null, freeAt: this.t, idleSince: this.t });
    for (const seg of old) if (seg.current) this.abort(seg, "trame interrompue par la manœuvre de SW3");
  }

  setSwitch(sw, closed) {
    if (this.switches[sw] === closed) return;
    this.switches[sw] = closed;
    if (sw === "SW3") this.layout();
    this.emit("switch", { sw, closed });
  }

  segmentOf(name) { return this.segments.find((s) => s.members.includes(name)); }

  // --- Émission ------------------------------------------------------------------

  enqueue(name, id, data, opts = {}) {
    const n = this.nodes[name];
    const pending = n.queue.findIndex((f) => f.id === id);
    const frame = { id, data, dlc: opts.dlc ?? data.length, queuedAt: this.t, tag: opts.tag };
    if (pending >= 0) { n.queue[pending] = frame; n.lost++; return; } // écrasée avant d'être partie
    if (n.queue.length >= TX_BUFFERS) { n.lost++; return; }
    n.queue.push(frame);
  }

  payload(id, values) {
    const meta = this.frames[id];
    return packSignals(meta.signals, values, meta.dlc);
  }

  appPayload(n) {
    const meta = this.frames[n.app];
    const steps = this.icd.simulations[meta.layout].steps;
    const values = { ...steps[n.step % steps.length] };
    n.step++;
    n.counter = (n.counter + 1) & 0xff;
    if (meta.name === "ENERGY_COMMAND") {
      values.command_counter = n.counter;
      const d = packSignals(meta.signals, values, 8);
      d[7] = d.slice(0, 7).reduce((a, b) => a ^ b, 0);
      return d;
    }
    values.frame_counter = meta.name === "IMU_SPEED" ? n.counter & 7 : n.counter;
    values.sensor_present = 0; // séquence simulée, pas de capteur réel
    return packSignals(meta.signals, values, 8);
  }

  heartbeat(n) {
    return this.payload(this.icd.heartbeat_base + n.nodeId, {
      ctrl_state: n.state, last_error_code: n.lec,
      clock_not_qualified: this.hsi && n.nodeId <= 3 ? 1 : 0,
      fault_mode_active: n.mode ? 1 : 0, silent_mode: n.mode === 4 ? 1 : 0,
      tec: Math.min(n.tec, 255), rec: Math.min(n.rec, 255), current_mode: n.mode,
    });
  }

  /** PC : test d'arbitrage, ARM puis GO à la suite. */
  runArbitration() {
    this.enqueue("PC", this.ids.ARM, new Array(8).fill(0), { tag: "ARM" });
    this.enqueue("PC", this.ids.GO, new Array(8).fill(0), { tag: "GO" });
  }

  /** PC : BENCH_CFG vers un nœud (0 = tous). */
  sendCfg(target, mode, durationMs, param = 0x400) {
    this.enqueue("PC", this.ids.BENCH_CFG, this.payload(this.ids.BENCH_CFG, {
      target_node: target, mode, param_u16: param, duration_ms: durationMs, heartbeat_period_ms: 0,
    }));
  }

  // --- Boucle de temps -----------------------------------------------------------

  advance(dt) {
    const end = this.t + dt;
    let stalled = 0;
    while (this.t < end) {
      const next = Math.min(end, this.nextEvent());
      stalled = next <= this.t ? stalled + 1 : 0;
      this.t = stalled > 50 ? this.t + 1 : Math.max(this.t, next); // garde-fou : jamais figé
      this.tick();
    }
    const horizon = this.t - 100000;
    while (this.busyLog.length && this.busyLog[0][1] < horizon) this.busyLog.shift();
  }

  nextEvent() {
    let t = Infinity;
    for (const n of Object.values(this.nodes)) {
      if (n.nextHb !== undefined) t = Math.min(t, n.nextHb);
      if (n.nextApp !== undefined) t = Math.min(t, n.nextApp);
      if (n.mode && n.modeUntil) t = Math.min(t, n.modeUntil);
      if (n.armAt) t = Math.min(t, n.armAt);
      if (n.mode === 3 && n.nextFault !== undefined) t = Math.min(t, n.nextFault);
    }
    for (const s of this.segments) {
      if (s.current) { t = Math.min(t, s.current.end); continue; }
      if (s.freeAt > this.t) t = Math.min(t, s.freeAt);
      for (const m of s.members) {
        const n = this.nodes[m];
        if (n.state === 3 && n.mode !== 5) t = Math.min(t, this.recoveryAt(n, s));
      }
    }
    return Math.max(t, this.t);
  }

  tick() {
    const now = this.t;
    for (const n of Object.values(this.nodes)) {
      if (n.mode && n.modeUntil && now >= n.modeUntil) this.endMode(n);
      if (n.armAt && now >= n.armAt) {
        n.armAt = null;
        this.enqueue(n.name, n.app, this.appPayload(n), { tag: "contendant" });
      }
      if (n.nextHb !== undefined && now >= n.nextHb) {
        n.nextHb += this.hbPeriod;
        if (!this.arbitrationWindow && n.mode !== 4) this.enqueue(n.name, this.icd.heartbeat_base + n.nodeId, this.heartbeat(n));
      }
      if (n.nextApp !== undefined && now >= n.nextApp) {
        n.nextApp += this.appPeriod;
        if (!this.arbitrationWindow && n.mode !== 4) this.enqueue(n.name, n.app, this.appPayload(n));
      }
      // Modes de faute qui émettent : N4 n'a pas de trame propre, il prend param_u16.
      if (n.mode === 1 && n.queue.length < TX_BUFFERS) this.enqueue(n.name, n.param || n.app || 0x400, new Array(8).fill(0), { tag: "babbling" });
      if (n.mode === 3 && n.nextFault !== undefined && now >= n.nextFault) {
        n.nextFault += this.appPeriod;
        this.enqueue(n.name, n.param || n.app || 0x400, [0, 0, 0, 0], { tag: "DLC 4 au lieu de 8" });
      }
    }
    for (const seg of this.segments) {
      if (seg.current && now >= seg.current.end) this.finish(seg);
      if (!seg.current && now >= seg.freeAt) this.start(seg);
    }
  }

  canTransmit(n) { return n.state !== 3 && n.mode !== 4 && n.queue.length > 0; }
  canAck(n) { return n.state !== 3 && n.mode !== 4 && n.mode !== 2 && n.mode !== 5; }

  // Reprise après bus-off : 128 séquences de 11 bits récessifs. Chaque fin de trame en
  // fournit une ; un bus au repos (ou court-circuité, donc récessif) en fournit en continu.
  idleSequences(n, seg) {
    const from = Math.max(seg.idleSince, n.busOffAt ?? 0);
    return Math.max(0, Math.floor((this.t - from) / (11 * BIT_US) + 1e-6));
  }

  recoveryAt(n, seg) {
    return Math.max(seg.idleSince, n.busOffAt ?? 0) + Math.max(0, 128 - n.recovery) * 11 * BIT_US;
  }

  start(seg) {
    for (const name of seg.members) {
      const n = this.nodes[name];
      if (n.state === 3 && n.mode !== 5 && n.recovery + this.idleSequences(n, seg) >= 128) this.recover(n);
    }
    const contenders = seg.members.map((m) => this.nodes[m]).filter((n) => this.canTransmit(n));
    if (!contenders.length) return;
    for (const name of seg.members) {
      const n = this.nodes[name];
      if (n.state === 3) n.recovery += this.idleSequences(n, seg);
    }
    const heads = contenders.map((n) => ({ node: n, frame: n.queue.reduce((a, b) => (b.id < a.id ? b : a)) }));
    heads.sort((a, b) => a.frame.id - b.frame.id);
    const win = heads[0];
    const tx = win.node;
    const receivers = seg.members.filter((m) => m !== tx.name).map((m) => this.nodes[m]);
    const ackers = receivers.filter((n) => this.canAck(n));
    const fullBits = frameBits(win.frame.id, win.frame.data, { dlc: win.frame.dlc, acked: ackers.length > 0 });

    const arbitration = heads.length > 1 ? {
      t: this.t, winner: tx.name, id: win.frame.id,
      contenders: heads.map((h) => ({ node: h.node.name, id: h.frame.id, lostAt: arbitrationLoss(h.frame.id, win.frame.id) })),
    } : null;
    // On garde l'arbitrage le plus disputé d'une rafale (après GO : 3, puis 2 contendants).
    const prev = this.lastArbitration;
    if (arbitration && (!prev || this.t - prev.t > 2000 || heads.length >= prev.contenders.length)) this.lastArbitration = arbitration;

    // Issue de la trame, décidée au départ ; l'erreur est détectée au bit `errorBit`.
    let error = null;
    const ackIndex = fullBits.findIndex((b) => b.field === "ACK");
    const shorted = this.switches.SW2 && seg.name === "bus";
    const n4 = this.nodes.N4;
    const n4Disturbs = seg.members.includes("N4") && n4 !== tx && n4.mode === 2 && n4.state === 0;
    if (shorted) {
      // Tous les émetteurs partent ensemble et relisent tous un SOF récessif.
      error = { bit: 0, lec: LEC.BIT0, cause: "court-circuit CAN_H/CAN_L (SW2) : le SOF dominant est relu récessif", detector: tx.name, visible: false, all: heads.map((h) => h.node.name) };
    } else if (tx.mode === 2) {
      error = { bit: 3 + Math.floor(this.rand() * 10), lec: LEC.BIT1, cause: "N4 émet à 250 kbit/s : les autres nœuds voient des erreurs de bourrage", detector: receivers[0]?.name, visible: true };
    } else if (n4Disturbs) {
      error = { bit: 4 + Math.floor(this.rand() * 14), lec: LEC.BIT0, cause: "N4 (250 kbit/s) échantillonne mal et détruit la trame par un drapeau d'erreur actif", detector: "N4", visible: true };
    } else if (!this.switches.SW1 && seg.name === "bus" && this.rand() < P_ERR_SANS_TERMINAISON) {
      const r = receivers[Math.floor(this.rand() * receivers.length)];
      error = { bit: 1 + Math.floor(this.rand() * (ackIndex - 2)), lec: LEC.STUFF, cause: "une seule terminaison (SW1 ouvert) : réflexions, bit mal échantillonné", detector: r?.name, visible: true };
    } else if (!ackers.length) {
      error = { bit: ackIndex, lec: LEC.ACK, cause: "aucun nœud n'acquitte : erreur d'acquittement", detector: tx.name, visible: true, ack: true };
    }

    const bits = error ? fullBits.slice(0, error.bit + 1) : fullBits;
    const nbits = error ? error.bit + 1 + ERROR_FRAME_BITS : fullBits.length;
    const cur = {
      seg: seg.name, tx: tx.name, id: win.frame.id, dlc: win.frame.dlc, data: win.frame.data, tag: win.frame.tag,
      name: this.name(win.frame.id), bits, fullBits, start: this.t, end: this.t + nbits * BIT_US,
      receivers: receivers.map((n) => n.name), ackers: ackers.map((n) => n.name), error, arbitration,
    };
    seg.current = cur;
    tx.ledTx = this.t;
    this.busyLog.push([cur.start, cur.end]);
    this.emit("start", cur);
  }

  finish(seg) {
    const cur = seg.current;
    seg.current = null;
    seg.freeAt = this.t + IFS_BITS * BIT_US;
    seg.idleSince = seg.freeAt;
    // Une fin de trame (ACK delim + EOF + IFS) compte pour la reprise d'un nœud en bus-off.
    for (const m of seg.members) if (this.nodes[m].state === 3) this.nodes[m].recovery++;
    const tx = this.nodes[cur.tx];
    const frame = tx.queue.find((f) => f.id === cur.id);
    const entry = { t: cur.start, tx: cur.tx, id: cur.id, name: cur.name, dlc: cur.dlc, data: cur.data, seg: cur.seg, tag: cur.tag, bits: cur.fullBits.length };

    if (!cur.error) {
      tx.queue.splice(tx.queue.indexOf(frame), 1);
      tx.sent++;
      this.count(tx, "tec", -1);
      tx.lec = 0;
      for (const name of cur.receivers) this.deliver(this.nodes[name], cur);
      if (cur.tag === "accusé BENCH_CFG" && tx.pendingCfg) this.startMode(tx);
      entry.ok = true;
    } else {
      const e = cur.error;
      tx.lec = e.lec;
      // ISO 11898-1 : pas d'incrément pour un émetteur error-passive sur erreur d'ACK.
      if (!(e.ack && tx.state === 2)) this.count(tx, "tec", 8);
      for (const name of e.all || []) {
        const other = this.nodes[name];
        if (other !== tx) { other.lec = e.lec; this.count(other, "tec", 8); }
      }
      if (e.visible) {
        for (const name of cur.receivers) {
          const r = this.nodes[name];
          if (r.state === 3 || r.mode === 4) continue;
          this.count(r, "rec", name === e.detector && name === "N4" ? 9 : 1);
        }
      }
      entry.ok = false;
      entry.cause = e.cause;
      entry.errorBit = e.bit;
    }
    this.trace.push(entry);
    if (this.trace.length > 400) this.trace.shift();
    this.stats[entry.ok ? "ok" : "err"]++;
    if (!entry.ok) this.stats.errBy[cur.tx] = (this.stats.errBy[cur.tx] || 0) + 1;
    this.emit("end", { ...cur, ok: entry.ok });
  }

  abort(seg, cause) {
    const cur = seg.current;
    seg.current = null;
    this.trace.push({ t: cur.start, tx: cur.tx, id: cur.id, name: cur.name, dlc: cur.dlc, data: cur.data, ok: false, cause, seg: cur.seg });
    this.emit("end", { ...cur, ok: false });
  }

  deliver(n, cur) {
    if (n.state === 3) return;
    n.received++;
    n.lastRx = { id: cur.id, name: cur.name, t: this.t };
    this.count(n, "rec", -1);
    if (n.name === "PC") return;
    const id = cur.id;
    if (id === this.ids.ARM) {
      n.armRx++;
      this.arbitrationWindow = true;
      // Le contendant arme sa trame de test après un court délai logiciel ; GO, d'identifiant
      // plus faible, occupe le bus pendant ce temps.
      if (n.app) n.armAt = this.t + 20 + this.rand() * 120;
    } else if (id === this.ids.GO) {
      this.arbitrationWindow = false;
    } else if (id === this.ids.BENCH_CFG) {
      const cfg = unpackSignals(this.frames[id].signals, cur.data);
      if (cfg.target_node === 0 || cfg.target_node === n.nodeId) this.applyCfg(n, cfg);
    }
  }

  // Le nœud répond par BENCH_RESULT au débit nominal, puis applique le mode demandé.
  applyCfg(n, cfg) {
    if (cfg.duration_ms === 0) { this.endMode(n, true); this.result(n, 0); return; }
    n.pendingCfg = cfg;
    this.result(n, 0, cfg.mode, "accusé BENCH_CFG");
  }

  startMode(n) {
    const cfg = n.pendingCfg;
    n.pendingCfg = null;
    n.mode = cfg.mode;
    n.param = cfg.param_u16;
    n.modeUntil = this.t + cfg.duration_ms * 1000;
    if (n.mode === 3) n.nextFault = this.t;
    if (n.mode === 5) this.busOff(n);
    this.emit("mode", { node: n.name, mode: n.mode });
  }

  endMode(n, silent) {
    const was = n.mode;
    n.mode = 0;
    n.modeUntil = 0;
    n.queue = n.queue.filter((f) => f.tag !== "babbling" && !String(f.tag || "").startsWith("DLC"));
    if (was === 5) this.recover(n);
    if (!silent) this.result(n, 0, was);
    this.emit("mode", { node: n.name, mode: 0 });
  }

  result(n, status, mode = n.mode, tag = "BENCH_RESULT") {
    this.enqueue(n.name, this.ids.BENCH_RESULT, this.payload(this.ids.BENCH_RESULT, {
      node_id: n.nodeId, mode, status, arm_rx: Math.min(n.armRx, 255),
      frames_sent: Math.min(n.sent, 65535), frames_lost: Math.min(n.lost, 65535),
    }), { tag });
  }

  // --- Confinement d'erreurs -----------------------------------------------------

  count(n, which, delta) {
    if (n.state === 3) return;
    if (which === "rec" && delta < 0 && n.rec > 127) n.rec = 120;
    else n[which] = Math.max(0, n[which] + delta);
    if (n.rec > 255) n.rec = 255;
    if (n.tec > 255) return this.busOff(n);
    const s = n.tec > 127 || n.rec > 127 ? 2 : n.tec >= 96 || n.rec >= 96 ? 1 : 0;
    if (s !== n.state) { n.state = s; this.emit("state", { node: n.name, state: s }); }
  }

  busOff(n) {
    n.state = 3;
    n.tec = 256;
    n.recovery = 0;
    n.busOffAt = this.t;
    this.emit("state", { node: n.name, state: 3 });
  }

  recover(n) {
    n.state = 0; n.tec = 0; n.rec = 0; n.recovery = 0; n.busOffAt = null;
    this.emit("state", { node: n.name, state: 0 });
  }

  // --- Mesures -------------------------------------------------------------------

  load(windowUs = 100000) {
    const from = this.t - windowUs;
    let busy = 0;
    for (const [a, b] of this.busyLog) busy += Math.max(0, Math.min(b, this.t) - Math.max(a, from));
    return Math.min(1, busy / windowUs);
  }

  name(id) {
    const f = this.frames[id];
    return f ? f.name : id === 0x400 ? "inondation (babbling)" : hex(id);
  }

  decode(id, data) {
    const f = this.frames[id];
    return f ? unpackSignals(f.signals, data) : null;
  }
}
