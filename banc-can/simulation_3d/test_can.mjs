// node test_can.mjs : vérifie l'encodeur de can.js contre icd/reference_vectors.json,
// les octets de référence partagés par le firmware C et l'outil Python.
import { readFileSync } from "node:fs";
import { packSignals, unpackSignals, frameBits, crc15, arbitrationLoss } from "./can.js";

const ref = JSON.parse(readFileSync(new URL("../icd/reference_vectors.json", import.meta.url), "utf8"));
const icd = JSON.parse(readFileSync(new URL("./icd.json", import.meta.url), "utf8"));
const byId = Object.fromEntries(Object.entries(icd.frames).map(([k, f]) => [parseInt(k, 16), f]));

let cases = 0;
let fails = 0;
for (const frame of ref.frames) {
  const meta = byId[frame.can_id];
  for (const c of frame.cases) {
    cases++;
    const values = { ...c.raw };
    for (const s of meta.signals) if (s.name in values) values[s.name] = values[s.name] * (s.factor || 1) + (s.offset || 0);
    const data = packSignals(meta.signals, values, frame.dlc);
    if (data.join() !== c.data.join()) {
      fails++;
      console.log(`ÉCHEC ${frame.name} « ${c.label} » : ${data} au lieu de ${c.data}`);
    }
    const back = unpackSignals(meta.signals, c.data);
    for (const s of meta.signals) {
      if (s.name in c.raw && Math.abs(back[s.name] - values[s.name]) > 1e-9) {
        fails++;
        console.log(`ÉCHEC décodage ${frame.name}.${s.name}`);
      }
    }
  }
}

// CRC-15 : le reste du message suivi de son propre CRC est nul.
const bits = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0];
const crc = crc15(bits);
const withCrc = bits.concat([...Array(15)].map((_, i) => (crc >> (14 - i)) & 1));
if (crc15(withCrc) !== 0) { fails++; console.log("ÉCHEC CRC-15"); }

// Bourrage : jamais six bits identiques avant le délimiteur de CRC.
const f = frameBits(0x100, [0, 0, 0, 0, 0, 0, 0, 0]);
const body = f.slice(0, f.findIndex((b) => b.field === "CRC delim")).map((b) => b.v).join("");
if (/000000|111111/.test(body)) { fails++; console.log("ÉCHEC bourrage"); }

// Arbitrage : 0x100 = 001…, 0x200 = 010…, 0x300 = 011… ; 0x200 et 0x300 perdent au bit 1.
if (arbitrationLoss(0x200, 0x100) !== 1 || arbitrationLoss(0x300, 0x100) !== 1 || arbitrationLoss(0x100, 0x100) !== -1) {
  fails++; console.log("ÉCHEC arbitrage");
}

console.log(`${cases} vecteurs de référence, trame 0x100 nulle : ${f.length} bits dont ${f.filter((b) => b.stuff).length} de bourrage`);
console.log(fails ? `${fails} échec(s)` : "tout est conforme");
process.exit(fails ? 1 : 0);
