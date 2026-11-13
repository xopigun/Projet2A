// Scène 3D du banc : table, cartes (modèles GLB issus de KiCad), câblage, et animation des
// trames. Unités : centimètres, y vers le haut ; le bus court selon x à z = BUS_Z.
//
// L'animation des trames qui « voyagent » est une illustration ralentie : sur le vrai bus,
// le signal parcourt les 5 m de ligne en 25 ns environ, bien moins qu'un bit (2 µs), si bien
// que tous les nœuds voient le même niveau au même instant. C'est ce que montre l'éclairage
// du bus (dominant = allumé), tandis que les « trains » de bits montrent qui parle à qui.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { BIT_US, hex } from "./can.js";
import { STATE } from "./bus.js";

export const NODE_COLORS = { PC: "#7cc35b", N1: "#f2a33a", N2: "#36b5c9", N3: "#a77bf3", N4: "#ef5d8f" };
const CAN_H = 0xd8432c;
const CAN_L = 0x2f7fd6;
const BUS_Z = -20;
const BUS_X0 = -56;
const BUS_X1 = 56;
const WIRE_Y = 0.45;
const NODE_X = { N1: -40, N2: -16, N3: 8, N4: 32 };
const NODE_Z = 6;
const PC_X = 47;
const SW2_X = -3;
const MODELS = ["nucleo_g431kb", "tja1051", "gy521", "lm2596", "carte_db9", "terminaison", "lcd1602", "to92", "adaptateur_usb_can"];
const STUB_T = 0.4; // s réelles pour parcourir une dérivation
const BUS_SPEED = 85; // cm/s réelles le long du bus

const VIEWS = {
  overview: [[4, 92, 112], [6, 0, -4]],
  bus: [[0, 44, 30], [0, 0, -14]],
  PC: [[PC_X + 4, 18, 30], [PC_X, 1, 8]],
};
for (const [n, x] of Object.entries(NODE_X)) VIEWS[n] = [[x + 3, 13, 21], [x, 1.5, 1]];

// --- petits constructeurs --------------------------------------------------------

const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.05, ...extra });

function tube(points, radius, material, segments = 64) {
  const curve = points.length === 2 ? new THREE.LineCurve3(points[0], points[1]) : new THREE.CatmullRomCurve3(points);
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, segments, radius, 8, false), material);
  mesh.castShadow = true;
  return mesh;
}

/** Paire torsadée le long d'une courbe : deux hélices décalées d'un demi-tour. */
function twistedPair(curve, matH, matL, { pitch = 1.3, r = 0.13, gap = 0.17 } = {}) {
  const group = new THREE.Group();
  const len = curve.getLength();
  const n = Math.max(24, Math.ceil(len / pitch) * 12);
  const up = new THREE.Vector3(0, 1, 0);
  for (const [phase, material] of [[0, matH], [Math.PI, matL]]) {
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const u = i / n;
      const p = curve.getPointAt(u);
      const t = curve.getTangentAt(u);
      const side = new THREE.Vector3().crossVectors(t, up);
      if (side.lengthSq() < 1e-4) side.set(1, 0, 0);
      side.normalize();
      const nrm = new THREE.Vector3().crossVectors(side, t).normalize();
      const a = (u * len / pitch) * Math.PI * 2 + phase;
      pts.push(p.clone().addScaledVector(side, Math.cos(a) * gap).addScaledVector(nrm, Math.sin(a) * gap));
    }
    group.add(tube(pts, r, material, n));
  }
  return group;
}

function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const redraw = (...a) => { draw(c.getContext("2d"), w, h, ...a); tex.needsUpdate = true; };
  redraw();
  return { tex, redraw };
}

function breadboardTexture(cols, rows) {
  return canvasTexture(cols * 16, rows * 16, (g, w, h) => {
    g.fillStyle = "#f2f1ec";
    g.fillRect(0, 0, w, h);
    g.fillStyle = "#3a3a3a";
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        if (j === Math.floor(rows / 2) || j === 2 || j === rows - 3) continue; // rainure et séparations
        g.fillRect(i * 16 + 6, j * 16 + 6, 4, 4);
      }
    }
    g.fillStyle = "#d9d7cf";
    g.fillRect(0, Math.floor(rows / 2) * 16 + 2, w, 12);
    g.fillStyle = "#d33";
    g.fillRect(0, 2 * 16 + 7, w, 2);
    g.fillStyle = "#36c";
    g.fillRect(0, (rows - 3) * 16 + 7, w, 2);
  }).tex;
}

function toggleSwitch(label) {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.9, 1.1), mat(0x24292c, { roughness: 0.5 }));
  base.position.y = 0.45;
  base.castShadow = true;
  const nut = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.35, 6), mat(0xb9bec2, { metalness: 0.8, roughness: 0.3 }));
  nut.position.y = 1.07;
  const pivot = new THREE.Group();
  pivot.position.y = 1.2;
  const lever = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.14, 1.5, 12), mat(0xd7dbde, { metalness: 0.9, roughness: 0.25 }));
  lever.position.y = 0.75;
  lever.castShadow = true;
  pivot.add(lever);
  const plate = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.12, 2.2), mat(0x1d4d3f));
  plate.position.y = 0.06;
  plate.receiveShadow = true;
  g.add(plate, base, nut, pivot);
  g.userData.lever = pivot;
  g.userData.label = label;
  return g;
}

function db9Plug(color = 0x2b2f33) {
  const g = new THREE.Group();
  const hood = new THREE.Mesh(new THREE.BoxGeometry(3.3, 1.5, 2.6), mat(color, { roughness: 0.7 }));
  hood.position.set(0, 0, -1.3);
  const shell = new THREE.Mesh(new THREE.BoxGeometry(2.1, 0.95, 0.7), mat(0xc9cdd0, { metalness: 0.85, roughness: 0.3 }));
  shell.position.set(0, 0, 0.3);
  const screws = [-1.25, 1.25].map((x) => {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.9, 12), mat(0x9aa0a4, { metalness: 0.9, roughness: 0.3 }));
    s.rotation.x = Math.PI / 2;
    s.position.set(x, 0, 0.1);
    return s;
  });
  for (const m of [hood, shell]) m.castShadow = true;
  g.add(hood, shell, ...screws);
  return g;
}

function led(color) {
  const g = new THREE.Group();
  const m = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.05, roughness: 0.3, transparent: true, opacity: 0.9 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.5, 16), m);
  body.position.y = 0.25;
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.25, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), m);
  dome.position.y = 0.5;
  const glow = new THREE.PointLight(color, 0, 4, 2);
  glow.position.y = 0.8;
  g.add(body, dome, glow);
  g.userData.set = (on) => { m.emissiveIntensity = on ? 2.4 : 0.05; glow.intensity = on ? 1.6 : 0; };
  return g;
}

function label(html, color, near = 0) {
  const el = document.createElement("div");
  el.className = "lbl";
  el.style.setProperty("--c", color);
  el.innerHTML = html;
  const obj = new CSS2DObject(el);
  obj.userData.near = near; // distance de caméra au-delà de laquelle l'étiquette se masque
  return obj;
}

// --- scène -----------------------------------------------------------------------

export class BenchScene {
  constructor(container, bench, { onSelect, onSwitch, onReady }) {
    this.container = container;
    this.bench = bench;
    this.onSelect = onSelect;
    this.onSwitch = onSwitch;
    this.pickables = [];
    this.nodes3d = {};
    this.switches3d = {};
    this.endpoints = {};
    this.pulses = [];
    this.flashes = [];
    this.selected = null;

    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: true }));
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.05;
    r.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(r.domElement);
    r.domElement.style.display = "block";

    this.labels = new CSS2DRenderer();
    Object.assign(this.labels.domElement.style, { position: "absolute", inset: "0", pointerEvents: "none" });
    container.appendChild(this.labels.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.5, 1200);
    this.camera.position.set(...VIEWS.overview[0]);
    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.target.set(...VIEWS.overview[1]);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = 1.48;
    this.controls.minDistance = 6;
    this.controls.maxDistance = 320;

    const pmrem = new THREE.PMREMGenerator(r);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.5));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-40, 90, 50);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -90, right: 90, top: 60, bottom: -60, near: 10, far: 250 });
    sun.shadow.bias = -0.0005;
    this.scene.add(sun);

    this.applyTheme();
    this.buildStatic();

    this.poolMax = 2400;
    this.pool = this.makePulsePool(this.poolMax);
    this.selBox = new THREE.Box3Helper(new THREE.Box3(), 0x36bfb2);
    this.selBox.visible = false;
    this.scene.add(this.selBox);

    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.bindPointer();

    this.loadModels().then(() => {
      this.buildBench();
      onReady?.();
    });
  }

  applyTheme() {
    const css = getComputedStyle(document.documentElement);
    const bg = css.getPropertyValue("--scene-bg").trim() || "#d9e1e4";
    this.scene.background = new THREE.Color(bg);
    this.scene.fog = new THREE.Fog(bg, 260, 520);
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.labels.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // --- chargement -----------------------------------------------------------------

  async loadModels() {
    const loader = new GLTFLoader();
    this.models = {};
    await Promise.all(MODELS.map(async (name) => {
      // GLB transporté en base64 dans un .json (voir generate_modeles_3d.py)
      const { glb } = await (await fetch(`modeles/${name}.json`)).json();
      const bin = Uint8Array.from(atob(glb), (c) => c.charCodeAt(0));
      const gltf = await loader.parseAsync(bin.buffer, "");
      const root = gltf.scene;
      root.scale.setScalar(100); // m → cm
      root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      this.models[name] = root;
    }));
  }

  /** Copie d'un modèle, recentrée en x/z, posée par sa face inférieure de carte à y = 0. */
  instance(name, { center = true } = {}) {
    const obj = this.models[name].clone(true);
    obj.traverse((o) => { if (o.isMesh) o.material = o.material.clone(); });
    const holder = new THREE.Group();
    holder.add(obj);
    if (center) {
      const box = new THREE.Box3().setFromObject(obj);
      obj.position.x -= (box.min.x + box.max.x) / 2;
      obj.position.z -= (box.min.z + box.max.z) / 2;
    }
    return holder;
  }

  pickable(obj, key) {
    obj.userData.key = key;
    this.pickables.push(obj);
    return obj;
  }

  // --- décor fixe -----------------------------------------------------------------

  buildStatic() {
    const S = this.scene;
    // Tapis antistatique sur le plan de travail
    const mat0 = canvasTexture(512, 512, (g, w, h) => {
      g.fillStyle = "#4f6f80";
      g.fillRect(0, 0, w, h);
      g.strokeStyle = "rgba(255,255,255,.07)";
      g.lineWidth = 1;
      for (let i = 0; i <= w; i += 32) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, h); g.stroke(); g.beginPath(); g.moveTo(0, i); g.lineTo(w, i); g.stroke(); }
    }).tex;
    mat0.wrapS = mat0.wrapT = THREE.RepeatWrapping;
    mat0.repeat.set(5, 3);
    const mat1 = new THREE.Mesh(new THREE.BoxGeometry(150, 0.3, 86), mat(0xffffff, { map: mat0, roughness: 0.9 }));
    mat1.position.set(0, -0.15, -4);
    mat1.receiveShadow = true;
    const table = new THREE.Mesh(new THREE.BoxGeometry(176, 4, 104), mat(0xb59a77, { roughness: 0.8 }));
    table.position.set(0, -2.3, -4);
    table.receiveShadow = true;
    S.add(table, mat1);
  }

  // --- banc -----------------------------------------------------------------------

  buildBench() {
    const S = this.scene;
    const mH = mat(CAN_H, { roughness: 0.45 });
    const mL = mat(CAN_L, { roughness: 0.45 });
    this.busMats = [mH, mL];

    // Ligne principale : paire torsadée entre les deux terminaisons
    const busCurve = new THREE.LineCurve3(new THREE.Vector3(BUS_X0, WIRE_Y, BUS_Z), new THREE.Vector3(BUS_X1, WIRE_Y, BUS_Z));
    const bus = this.pickable(twistedPair(busCurve, mH, mL), "bus");
    S.add(bus);
    const busLbl = label("BUS CAN · CAN_H <span style='color:#ff8a6a'>■</span> CAN_L <span style='color:#6ab0ff'>■</span>", "#888");
    busLbl.position.set(-8, 3.5, BUS_Z - 3);
    S.add(busLbl);

    // Terminaisons : RT1 fixe à gauche, RT2 derrière SW1 à droite
    const rt1 = this.pickable(this.instance("terminaison"), "RT1");
    rt1.position.set(BUS_X0 - 4, 0.4, BUS_Z);
    rt1.rotation.y = Math.PI;
    const rt2 = this.pickable(this.instance("terminaison"), "RT2");
    rt2.position.set(BUS_X1 + 9, 0.4, BUS_Z);
    S.add(rt1, rt2);
    this.addSwitch("SW1", new THREE.Vector3(BUS_X1 + 3.2, 0, BUS_Z), "SW1 · R<sub>T2</sub>");
    S.add(twistedPair(new THREE.LineCurve3(new THREE.Vector3(BUS_X1 + 4.2, WIRE_Y, BUS_Z), new THREE.Vector3(BUS_X1 + 6.4, WIRE_Y, BUS_Z)), mH, mL));
    for (const [txt, obj] of [["R<sub>T1</sub> 120 Ω", rt1], ["R<sub>T2</sub> 120 Ω", rt2]]) {
      const l = label(txt, "#9aa", 70);
      l.position.set(0, 2.6, 0);
      obj.add(l);
    }

    // SW2 : court-circuit entre CAN_H et CAN_L
    const sw2pos = new THREE.Vector3(SW2_X, 0, BUS_Z - 7);
    this.addSwitch("SW2", sw2pos, "SW2 · court-circuit H/L");
    S.add(tube([new THREE.Vector3(SW2_X - 0.3, WIRE_Y, BUS_Z), new THREE.Vector3(SW2_X - 0.5, 1.6, BUS_Z - 3.5), new THREE.Vector3(SW2_X - 0.4, 1.0, BUS_Z - 6.5)], 0.11, mH, 24));
    S.add(tube([new THREE.Vector3(SW2_X + 0.3, WIRE_Y, BUS_Z), new THREE.Vector3(SW2_X + 0.5, 1.6, BUS_Z - 3.5), new THREE.Vector3(SW2_X + 0.4, 1.0, BUS_Z - 6.5)], 0.11, mL, 24));

    // Nœuds N1 à N4
    for (const name of ["N1", "N2", "N3", "N4"]) this.buildNode(name);
    this.buildAdapter();
    this.buildPower();
    this.setSwitchLevers();
  }

  addSwitch(sw, pos, txt) {
    const g = toggleSwitch(sw);
    g.position.copy(pos);
    this.pickable(g, sw);
    const l = label(`${txt} <small id="lbl-${sw}"></small>`, "#c33");
    l.position.set(0, 3.4, 0);
    g.add(l);
    this.scene.add(g);
    this.switches3d[sw] = g;
  }

  setSwitchLevers() {
    for (const [sw, g] of Object.entries(this.switches3d)) {
      const closed = this.bench.switches[sw];
      g.userData.target = closed ? 0.42 : -0.42;
      const nominal = sw === "SW2" ? !closed : closed;
      const el = document.getElementById(`lbl-${sw}`);
      if (el) el.textContent = closed ? "fermé" : "ouvert";
      g.children[0].material.color.set(nominal ? 0x1d4d3f : 0x6a1f22);
    }
  }

  buildNode(name) {
    const S = this.scene;
    const x = NODE_X[name];
    const color = NODE_COLORS[name];
    const g = new THREE.Group();
    g.position.set(x, 0, NODE_Z);
    this.pickable(g, name);
    S.add(g);

    // Plaque d'essai
    const bbW = 12, bbD = 5.6, bbH = 0.85;
    const top = new THREE.MeshStandardMaterial({ map: breadboardTexture(47, 14), roughness: 0.85 });
    const side = mat(0xe9e7df, { roughness: 0.85 });
    const bb = new THREE.Mesh(new THREE.BoxGeometry(bbW, bbH, bbD), [side, side, top, side, side, side]);
    bb.position.y = bbH / 2;
    bb.castShadow = bb.receiveShadow = true;
    g.add(bb);

    const mcu = this.instance("nucleo_g431kb");
    mcu.position.set(-2.4, bbH + 0.26, 0);
    g.add(mcu);
    const tja = this.instance("tja1051");
    tja.position.set(4.3, bbH + 0.26, -0.3);
    tja.rotation.y = Math.PI / 2;
    g.add(tja);

    // Fils entre la carte et le transceiver : TXD, RXD, 5 V, GND
    const wires = [[0xf28c28, -0.9], [0xf2d028, -0.3], [0xd8322c, 0.3], [0x222222, 0.9]];
    for (const [c, dz] of wires) {
      g.add(tube([new THREE.Vector3(0.2, bbH + 0.05, dz * 1.6 - 0.5), new THREE.Vector3(1.6, bbH + 1.4, dz * 1.2), new THREE.Vector3(3.1, bbH + 0.05, dz * 1.1)], 0.06, mat(c), 20));
    }

    // LED externes : erreur (error-passive) et bus-off ; LED TX = LED de la carte
    const ledErr = led(0xffb020);
    ledErr.position.set(3.2, bbH, 2.25);
    const ledOff = led(0xff2a2a);
    ledOff.position.set(4.5, bbH, 2.25);
    const ledTx = led(0x34ff6a);
    ledTx.position.set(name === "N4" ? -0.4 : -1.0, bbH + 0.55, 0.35);
    ledTx.scale.setScalar(0.5);
    g.add(ledErr, ledOff, ledTx);

    // Carte de raccordement DB9 (J1 à J4), tournée vers le bus
    const j = this.instance("carte_db9");
    j.position.set(0, 0.6, -8.5);
    j.rotation.y = Math.PI;
    g.add(j);
    for (const [dx, c] of [[-0.25, CAN_H], [0.25, CAN_L]]) {
      g.add(tube([new THREE.Vector3(5.0, bbH + 0.9, -1.0), new THREE.Vector3(3.0 + dx, 3.2, -4.0), new THREE.Vector3(0.6 + dx * 4, 1.6, -6.4)], 0.09, mat(c), 24));
    }
    g.updateMatrixWorld(true);
    const jb = new THREE.Box3().setFromObject(j);
    const plug = db9Plug();
    plug.rotation.y = Math.PI;
    plug.position.set((jb.min.x + jb.max.x) / 2, 1.45, jb.min.z - 0.2);
    S.add(plug);
    const cableStart = plug.position.clone().add(new THREE.Vector3(0, 0, -2.4));

    // Dérivation (stub) jusqu'au bus, SW3 en série pour N4
    const junction = new THREE.Vector3(x, WIRE_Y, BUS_Z);
    const stub = new THREE.CatmullRomCurve3([cableStart, cableStart.clone().add(new THREE.Vector3(0, 0.6, -2.5)), new THREE.Vector3(x, 1.2, BUS_Z + 2.5), junction]);
    S.add(twistedPair(stub, this.busMats[0], this.busMats[1], { pitch: 1.1, r: 0.1, gap: 0.14 }));
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 12), mat(0xb5b9bc, { metalness: 0.9, roughness: 0.35 }));
    dot.position.copy(junction);
    S.add(dot);
    if (name === "N4") {
      const p = stub.getPointAt(0.45);
      this.addSwitch("SW3", new THREE.Vector3(p.x + 3.2, 0, p.z), "SW3 · N4");
      S.add(tube([p.clone().setY(0.6), new THREE.Vector3(p.x + 1.6, 1.6, p.z), new THREE.Vector3(p.x + 2.6, 1.0, p.z)], 0.08, mat(0x333333), 16));
    }
    this.endpoints[name] = { plug: cableStart, junction, stub, x };

    // Capteurs et afficheurs propres à chaque nœud
    if (name === "N1" || name === "N2") this.addLcd(g, name);
    if (name === "N2") {
      const imu = this.instance("gy521");
      imu.position.set(-8.6, 0.9, 1.0);
      imu.rotation.y = -Math.PI / 2;
      g.add(imu, this.post(-8.6, 1.0, 0.9));
      const hall = this.instance("to92");
      hall.position.set(-8.6, 0.2, 4.4);
      g.add(hall);
      this.tag(g, "MPU-6050 · Hall", -8.6, 3.2, 2.5);
    }
    if (name === "N3") {
      const ds = this.instance("to92");
      ds.position.set(-7.6, 0.2, 2.0);
      g.add(ds);
      this.tag(g, "DS18B20", -7.6, 2.6, 2.0);
    }
    if (name === "N4") {
      const stlink = new THREE.Mesh(new THREE.BoxGeometry(5.3, 0.9, 1.9), mat(0x2b5aa8, { roughness: 0.4, metalness: 0.4 }));
      stlink.position.set(-9.8, 0.45, 2.6);
      stlink.castShadow = true;
      g.add(stlink);
      this.tag(g, "ST-Link V2", -9.8, 2.0, 2.6);
    }

    const role = { N1: "energy_command", N2: "imu_speed", N3: "temp_battery", N4: "nœud fautif" }[name];
    const board = "Nucleo-G431KB";
    const lbl = label(`${name} <small>${role}</small><br><span class="st" id="st-${name}">error-active</span>`, color);
    lbl.position.set(0, 5.2, 0);
    g.add(lbl);
    this.nodes3d[name] = { group: g, ledErr, ledOff, ledTx, label: lbl, flash: 0 };
  }

  post(x, y, z) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, y, 8), mat(0xc8a24a, { metalness: 0.8 }));
    m.position.set(x, y / 2, z);
    return m;
  }

  tag(group, text, x, y, z) {
    const l = label(`<small>${text}</small>`, "#666", 45);
    l.position.set(x, y, z);
    group.add(l);
  }

  addLcd(g, name) {
    const lcd = this.instance("lcd1602");
    const holder = new THREE.Group();
    holder.add(lcd);
    // Afficheur incliné vers l'avant, posé sur un pupitre
    holder.position.set(0, 2.2, 9.2);
    holder.rotation.x = 0.95;
    g.add(holder);
    const stand = new THREE.Mesh(new THREE.BoxGeometry(7.6, 2.6, 0.4), mat(0x30363a));
    stand.position.set(0, 1.3, 7.9);
    stand.rotation.x = 0.35;
    stand.castShadow = true;
    g.add(stand);
    holder.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(lcd);
    const inv = new THREE.Matrix4().copy(holder.matrixWorld).invert();
    box.applyMatrix4(inv);
    const screen = canvasTexture(320, 80, (c, w, h, lines = ["", ""]) => {
      c.fillStyle = "#9fd13c";
      c.fillRect(0, 0, w, h);
      c.fillStyle = "rgba(20,40,0,.88)";
      c.font = "600 30px 'IBM Plex Mono', monospace";
      c.textBaseline = "top";
      c.fillText(lines[0].padEnd(16).slice(0, 16), 8, 6);
      c.fillText(lines[1].padEnd(16).slice(0, 16), 8, 42);
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(6.6, 1.65), new THREE.MeshBasicMaterial({ map: screen.tex, toneMapped: false }));
    plane.rotation.x = -Math.PI / 2;
    plane.position.set((box.min.x + box.max.x) / 2, box.max.y + 0.02, (box.min.z + box.max.z) / 2);
    holder.add(plane);
    this.lcds = this.lcds || {};
    this.lcds[name] = screen;
  }

  buildAdapter() {
    const S = this.scene;
    const ad = this.pickable(this.instance("adaptateur_usb_can"), "PC");
    ad.position.set(PC_X, 0.7, 8);
    ad.rotation.y = Math.PI / 2;
    S.add(ad);
    for (const [dx, dz] of [[-1.6, -3.6], [1.6, -3.6], [-1.6, 3.6], [1.6, 3.6]]) S.add(this.post(PC_X + dx, 0.7, 8 + dz));
    ad.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(ad);
    const plug = db9Plug();
    plug.rotation.y = Math.PI;
    plug.position.set((box.min.x + box.max.x) / 2, 1.6, box.min.z - 0.3);
    S.add(plug);
    const cableStart = plug.position.clone().add(new THREE.Vector3(0, 0, -2.4));
    const junction = new THREE.Vector3(PC_X, WIRE_Y, BUS_Z);
    const stub = new THREE.CatmullRomCurve3([cableStart, cableStart.clone().add(new THREE.Vector3(0, 0.6, -2.5)), new THREE.Vector3(PC_X, 1.2, BUS_Z + 2.5), junction]);
    S.add(twistedPair(stub, this.busMats[0], this.busMats[1], { pitch: 1.1, r: 0.1, gap: 0.14 }));
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 12), mat(0xb5b9bc, { metalness: 0.9, roughness: 0.35 }));
    dot.position.copy(junction);
    S.add(dot);
    this.endpoints.PC = { plug: cableStart, junction, stub, x: PC_X };
    const l = label("J5 · adaptateur <small>USB-CAN G69</small><br><span class='st' id='st-PC'>error-active</span>", NODE_COLORS.PC);
    l.position.set(PC_X, 5, 8);
    S.add(l);

    // Câble USB vers le PC portable
    const usb = new THREE.Vector3((box.min.x + box.max.x) / 2, 1.2, box.max.z + 1);
    S.add(tube([usb, usb.clone().add(new THREE.Vector3(0, 0.4, 4)), new THREE.Vector3(PC_X + 3, 0.5, 20), new THREE.Vector3(PC_X + 6, 0.6, 24)], 0.22, mat(0x1b1b1b), 40));

    // PC portable : l'écran affiche une trace façon BancCAN
    const laptop = this.pickable(new THREE.Group(), "laptop");
    laptop.position.set(PC_X + 15, 0, 30);
    laptop.rotation.y = -0.55;
    const base = new THREE.Mesh(new THREE.BoxGeometry(30, 1.6, 21), mat(0x3a3f44, { metalness: 0.5, roughness: 0.4 }));
    base.position.y = 0.8;
    base.castShadow = true;
    const keys = new THREE.Mesh(new THREE.PlaneGeometry(26, 9), mat(0x1c1f22));
    keys.rotation.x = -Math.PI / 2;
    keys.position.set(0, 1.61, -2.5);
    const hinge = new THREE.Group();
    hinge.position.set(0, 1.6, -10.5);
    hinge.rotation.x = -0.32;
    const lid = new THREE.Mesh(new THREE.BoxGeometry(30, 19.5, 0.7), mat(0x3a3f44, { metalness: 0.5, roughness: 0.4 }));
    lid.position.set(0, 9.75, -0.35);
    lid.castShadow = true;
    this.laptopScreen = canvasTexture(1024, 640, (g, w, h, draw) => draw && draw(g, w, h));
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(28, 17.5), new THREE.MeshBasicMaterial({ map: this.laptopScreen.tex, toneMapped: false }));
    screen.position.set(0, 9.75, 0.02);
    hinge.add(lid, screen);
    laptop.add(base, keys, hinge);
    S.add(laptop);
  }

  buildPower() {
    const S = this.scene;
    // Alimentation de laboratoire 12 V et module abaisseur LM2596 → rail 5 V
    const psu = this.pickable(new THREE.Group(), "alim");
    psu.position.set(-58, 0, -38);
    const body = new THREE.Mesh(new THREE.BoxGeometry(15, 9, 18), mat(0xd9dcdf, { roughness: 0.5 }));
    body.position.y = 4.5;
    body.castShadow = true;
    const face = canvasTexture(300, 180, (g, w, h) => {
      g.fillStyle = "#2b3034";
      g.fillRect(0, 0, w, h);
      g.fillStyle = "#0c0f10";
      g.fillRect(16, 16, 268, 70);
      g.fillStyle = "#ff3b2f";
      g.font = "600 46px 'IBM Plex Mono', monospace";
      g.fillText("12.00V", 30, 68);
      g.fillStyle = "#cfd4d8";
      g.font = "500 20px 'IBM Plex Sans Condensed', sans-serif";
      g.fillText("ALIMENTATION 12 V / 3 A", 18, 120);
      for (const [x, c] of [[200, "#d33"], [250, "#222"]]) { g.fillStyle = c; g.beginPath(); g.arc(x, 152, 13, 0, 7); g.fill(); }
    }).tex;
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(15, 9), new THREE.MeshStandardMaterial({ map: face, roughness: 0.6 }));
    panel.position.set(0, 4.5, 9.01);
    psu.add(body, panel);
    S.add(psu);

    const buck = this.pickable(this.instance("lm2596"), "buck");
    buck.position.set(-38, 0.6, -33);
    S.add(buck, this.post(-38, 0.6, -33));
    const red = mat(0xd8322c);
    const black = mat(0x1e1e1e);
    S.add(tube([new THREE.Vector3(-53, 1.2, -29), new THREE.Vector3(-48, 1.5, -29), new THREE.Vector3(-41, 1.0, -31)], 0.14, red, 30));
    S.add(tube([new THREE.Vector3(-52, 1.2, -29), new THREE.Vector3(-47, 1.2, -30), new THREE.Vector3(-41, 1.0, -34)], 0.14, black, 30));
    const l = label("<small>12 V → LM2596 → rail 5 V</small>", "#c33", 70);
    l.position.set(-38, 4, -33);
    S.add(l);

    // Rail 5 V le long du fond, une descente par nœud vers le VCC du transceiver
    const railZ = -29;
    S.add(tube([new THREE.Vector3(-34, 1.0, railZ + 0.4), new THREE.Vector3(NODE_X.N4 + 4, 1.0, railZ + 0.4)], 0.12, red, 80));
    S.add(tube([new THREE.Vector3(-34, 1.0, railZ - 0.4), new THREE.Vector3(NODE_X.N4 + 4, 1.0, railZ - 0.4)], 0.12, black, 80));
    for (const x of Object.values(NODE_X)) {
      for (const [dx, m] of [[3.4, red], [4.0, black]]) {
        S.add(tube([new THREE.Vector3(x + dx, 1.0, railZ), new THREE.Vector3(x + dx, 9, -18), new THREE.Vector3(x + dx, 6, -2), new THREE.Vector3(x + dx + 0.6, 1.0, NODE_Z - 2.6)], 0.07, m, 48));
      }
    }
  }

  // --- interaction ----------------------------------------------------------------

  bindPointer() {
    const el = this.renderer.domElement;
    const ray = new THREE.Raycaster();
    const ptr = new THREE.Vector2();
    let down = null;
    const pick = (ev) => {
      const r = el.getBoundingClientRect();
      ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ptr, this.camera);
      const hit = ray.intersectObjects(this.pickables, true)[0];
      if (!hit) return null;
      let o = hit.object;
      while (o && !o.userData.key) o = o.parent;
      return o?.userData.key ?? null;
    };
    el.addEventListener("pointerdown", (ev) => { down = [ev.clientX, ev.clientY]; });
    el.addEventListener("pointerup", (ev) => {
      if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
      const key = pick(ev);
      if (!key) return;
      if (key.startsWith("SW")) this.onSwitch(key);
      this.onSelect(key);
    });
    let last = 0;
    el.addEventListener("pointermove", (ev) => {
      if (ev.buttons || performance.now() - last < 60) return;
      last = performance.now();
      el.style.cursor = pick(ev) ? "pointer" : "";
    });
  }

  select(key) {
    this.selected = key;
    const obj = this.pickables.find((o) => o.userData.key === key);
    this.selBox.visible = !!obj;
    if (obj) this.selBox.box.setFromObject(obj).expandByScalar(0.4);
  }

  view(name) {
    const v = VIEWS[name] || VIEWS.overview;
    this.camAnim = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(), p1: new THREE.Vector3(...v[0]), t1: new THREE.Vector3(...v[1]) };
  }

  // --- trames ---------------------------------------------------------------------

  makePulsePool(max) {
    const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(0.6, 0.6, 0.6), new THREE.MeshBasicMaterial({ toneMapped: false }), max);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3);
    mesh.count = 0;
    mesh.frustumCulled = false;
    this.scene.add(mesh);
    return mesh;
  }

  /** Une trame démarre : un train de bits part de l'émetteur, suit la dérivation puis le bus. */
  frameStart(cur) {
    const from = this.endpoints[cur.tx];
    if (!from) return;
    const color = new THREE.Color(NODE_COLORS[cur.tx] || "#ffffff");
    const isolated = cur.seg !== "bus";
    const el = document.createElement("div");
    el.className = "pkt";
    el.style.setProperty("--c", NODE_COLORS[cur.tx]);
    el.textContent = `${hex(cur.id)} ${cur.name}`;
    const tag = new CSS2DObject(el);
    this.scene.add(tag);
    const pulse = { cur, color, runners: [], age: 0, tag, el, dead: false, error: cur.error, receivers: new Set(cur.receivers) };
    const stubLen = isolated ? 0.45 : 1;
    pulse.runners.push({ kind: "stub", curve: from.stub, u0: 0, u1: stubLen, dur: STUB_T * stubLen, t: 0, done: false, lead: true });
    // Instant où l'erreur est détectée, rapporté à la durée de l'animation
    const farthest = Math.max(Math.abs(from.x - BUS_X0), Math.abs(BUS_X1 - from.x));
    const total = STUB_T + (isolated ? 0 : farthest / BUS_SPEED + STUB_T);
    if (cur.error) pulse.stopAt = Math.max(0.12, total * (cur.error.bit / cur.fullBits.length));
    this.pulses.push(pulse);
    while (this.pulses.length > 28) this.killPulse(this.pulses.shift());
    const n = this.nodes3d[cur.tx];
    if (n) n.flash = performance.now();
  }

  frameEnd() {}

  killPulse(p) {
    p.dead = true;
    this.scene.remove(p.tag);
  }

  stepPulses(dt) {
    let k = 0;
    const tmp = new THREE.Object3D();
    const col = new THREE.Color();
    const red = new THREE.Color("#ff3b3b");
    for (const p of this.pulses) {
      p.age += dt;
      const frozen = p.stopAt !== undefined && p.age >= p.stopAt;
      if (frozen && !p.flagged) {
        p.flagged = true;
        p.el.classList.add("bad");
        p.el.textContent = `${hex(p.cur.id)} ✕ ${p.cur.error.ack ? "pas d'ACK" : "erreur"}`;
        const det = this.endpoints[p.cur.error.detector] || this.endpoints[p.cur.tx];
        this.flash(det.junction, 0xff3b3b, 3.5);
      }
      if (frozen && p.age > p.stopAt + 0.9) { this.killPulse(p); continue; }
      let leadPos = null;
      for (const r of p.runners) {
        if (!frozen) r.t += dt;
        const f = Math.min(1, r.t / r.dur);
        const u = r.u0 + (r.u1 - r.u0) * f;
        const pos = r.curve.getPointAt(Math.min(1, Math.max(0, u)));
        if (r.lead) leadPos = pos;
        // Train : SOF en tête, puis l'identifiant, bit par bit
        const len = r.curve.getLength();
        const dir = Math.sign(r.u1 - r.u0) || 1;
        const bits = p.cur.fullBits;
        const nb = Math.min(16, bits.length);
        const visible = !r.done || frozen;
        for (let i = 0; i < nb && visible && k < this.poolMax; i++) {
          const ub = u - (dir * i * 0.85) / len;
          if (ub < Math.min(r.u0, r.u1) - 1e-6 || ub > Math.max(r.u0, r.u1) + 1e-6) break;
          const q = r.curve.getPointAt(Math.min(1, Math.max(0, ub)));
          tmp.position.set(q.x, q.y + 0.6, q.z);
          tmp.updateMatrix();
          this.pool.setMatrixAt(k, tmp.matrix);
          col.copy(frozen ? red : p.color).multiplyScalar(bits[i].v === 0 ? 1.25 : 0.22);
          this.pool.setColorAt(k, col);
          k++;
        }
        if (!r.done && !frozen && r.kind === "bus") this.spawnReceivers(p, r, pos.x);
        if (!r.done && f >= 1 && !frozen) {
          r.done = true;
          this.onRunnerDone(p, r);
        }
      }
      if (leadPos) p.tag.position.set(leadPos.x, leadPos.y + 1.8, leadPos.z);
      if (!frozen && p.runners.every((r) => r.done)) { p.finished = (p.finished || 0) + dt; if (p.finished > 0.5) this.killPulse(p); }
    }
    this.pulses = this.pulses.filter((p) => !p.dead);
    this.pool.count = k;
    this.pool.instanceMatrix.needsUpdate = true;
    if (this.pool.instanceColor) this.pool.instanceColor.needsUpdate = true;
  }

  onRunnerDone(p, r) {
    if (r.kind === "stub") {
      if (p.cur.seg !== "bus") return; // N4 isolé par SW3 : la trame s'arrête à l'interrupteur
      const x = this.endpoints[p.cur.tx].x;
      const busCurveL = new THREE.LineCurve3(new THREE.Vector3(x, WIRE_Y, BUS_Z), new THREE.Vector3(BUS_X0, WIRE_Y, BUS_Z));
      const busCurveR = new THREE.LineCurve3(new THREE.Vector3(x, WIRE_Y, BUS_Z), new THREE.Vector3(BUS_X1, WIRE_Y, BUS_Z));
      const bus = [];
      for (const [c, end] of [[busCurveL, BUS_X0], [busCurveR, BUS_X1]]) {
        const d = Math.abs(end - x);
        if (d >= 0.5) bus.push({ kind: "bus", curve: c, u0: 0, u1: 1, dur: d / BUS_SPEED, t: 0, done: false, x0: x, x1: end });
      }
      // L'étiquette suit le train qui a le plus long chemin à faire
      r.lead = false;
      bus.reduce((a, b) => (b.dur > a.dur ? b : a)).lead = true;
      p.runners.push(...bus);
    } else if (r.kind === "rx") {
      const n = this.nodes3d[r.node];
      this.flash(this.endpoints[r.node].plug, 0x45e07a, 2.2);
      if (n) n.rx = performance.now();
    }
  }

  spawnReceivers(p, r, xNow) {
    for (const name of p.receivers) {
      const ep = this.endpoints[name];
      if (!ep) continue;
      const passed = r.x1 > r.x0 ? ep.x > r.x0 && ep.x <= xNow : ep.x < r.x0 && ep.x >= xNow;
      if (!passed) continue;
      p.receivers.delete(name);
      const reach = name === "N4" && !this.bench.switches.SW3 ? 0.55 : 0;
      p.runners.push({ kind: "rx", node: name, curve: ep.stub, u0: 1, u1: reach, dur: STUB_T * (1 - reach), t: 0, done: false });
    }
  }

  flash(pos, color, size) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.55, 32), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95, side: THREE.DoubleSide, toneMapped: false }));
    m.rotation.x = -Math.PI / 2;
    m.position.copy(pos).setY(pos.y + 0.3);
    this.scene.add(m);
    this.flashes.push({ m, age: 0, size });
  }

  // --- boucle ---------------------------------------------------------------------

  update(dt, speed) {
    if (this.camAnim) {
      const a = this.camAnim;
      a.t = Math.min(1, a.t + dt / 0.8);
      const e = a.t < 0.5 ? 2 * a.t * a.t : 1 - (-2 * a.t + 2) ** 2 / 2;
      this.camera.position.lerpVectors(a.p0, a.p1, e);
      this.controls.target.lerpVectors(a.t0, a.t1, e);
      if (a.t >= 1) this.camAnim = null;
    }
    this.controls.update();

    if (this.busMats) {
      // Niveau du bus : tous les nœuds voient le même bit au même instant
      const seg = this.bench.segments[0];
      const cur = seg.current;
      let glow = 0;
      let color = 0xffffff;
      if (cur) {
        const idx = Math.floor((this.bench.t - cur.start) / BIT_US);
        const realBit = BIT_US * 1e-6 / Math.max(speed, 1e-9);
        let v = 1;
        if (idx < cur.bits.length) v = cur.bits[idx].v;
        else if (cur.error && idx < cur.bits.length + 6) v = 0; // drapeau d'erreur actif
        glow = realBit > 0.03 ? (v === 0 ? 1.4 : 0.08) : 0.55;
        color = cur.error && idx >= cur.bits.length ? 0xff2020 : new THREE.Color(NODE_COLORS[cur.tx]).getHex();
      }
      for (const m of this.busMats) { m.emissive.setHex(color); m.emissiveIntensity = glow; }
    }

    for (const [sw, g] of Object.entries(this.switches3d)) {
      const lev = g.userData.lever;
      lev.rotation.z += ((g.userData.target ?? 0) - lev.rotation.z) * Math.min(1, dt * 12);
    }

    const now = performance.now();
    for (const [name, n] of Object.entries(this.nodes3d)) {
      const node = this.bench.nodes[name];
      if (!node || !n.ledErr) continue;
      n.ledErr.userData.set(node.state === 2);
      n.ledOff.userData.set(node.state === 3);
      n.ledTx.userData.set(now - n.flash < 140);
    }

    this.stepPulses(dt);
    for (const f of this.flashes) {
      f.age += dt;
      f.m.scale.setScalar(1 + f.age * f.size * 3);
      f.m.material.opacity = Math.max(0, 0.95 - f.age * 1.6);
      if (f.age > 0.6) { this.scene.remove(f.m); f.m.geometry.dispose(); f.m.material.dispose(); }
    }
    this.flashes = this.flashes.filter((f) => f.age <= 0.6);

    if (!this.labelList || this.labelList.length === 0) {
      this.labelList = [];
      this.scene.traverse((o) => { if (o.isCSS2DObject && o.userData.near) this.labelList.push(o); });
    }
    const wp = new THREE.Vector3();
    for (const l of this.labelList) l.visible = this.camera.position.distanceTo(l.getWorldPosition(wp)) < l.userData.near;
    this.renderer.render(this.scene, this.camera);
    this.labels.render(this.scene, this.camera);
  }

  /** Rafraîchissements lents : étiquettes, afficheurs LCD, écran du PC. */
  refresh(lcdLines, screenDraw) {
    for (const name of [...Object.keys(NODE_X), "PC"]) {
      const node = this.bench.nodes[name];
      const el = document.getElementById(`st-${name}`);
      if (el && node) {
        el.textContent = `${["actif", "warning", "passif", "BUS-OFF"][node.state]} · T${Math.min(node.tec, 255)} R${node.rec}${node.mode ? " · " + ["", "babbling", "250 kbit/s", "DLC", "silencieux", "bus-off maintenu"][node.mode] : ""}`;
        el.className = `st s${node.state}`;
      }
    }
    if (this.lcds) for (const [name, lcd] of Object.entries(this.lcds)) lcd.redraw(lcdLines(name));
    if (this.laptopScreen) this.laptopScreen.redraw(screenDraw);
    this.setSwitchLevers();
  }
}
