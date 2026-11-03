// Couche protocole CAN 2.0A de la simulation : encodage des signaux de l'ICD et
// construction bit à bit d'une trame (CRC-15, bourrage), sans dépendance au navigateur.
// Testé contre icd/reference_vectors.json par test_can.mjs.

export const BIT_US = 2; // 500 kbit/s

// --- Signaux (Intel, little-endian) --------------------------------------------

export function packSignals(signals, values, dlc = 8) {
  const data = new Array(dlc).fill(0);
  for (const s of signals) {
    const v = values[s.name] ?? s.default ?? 0;
    let raw = Math.round((v - (s.offset || 0)) / (s.factor || 1));
    const max = s.signed ? 2 ** (s.length - 1) - 1 : 2 ** s.length - 1;
    const min = s.signed ? -(2 ** (s.length - 1)) : 0;
    raw = Math.max(min, Math.min(max, raw));
    if (raw < 0) raw += 2 ** s.length; // complément à deux
    const start = s.start_byte * 8 + s.start_bit;
    for (let i = 0; i < s.length; i++) {
      if (Math.floor(raw / 2 ** i) % 2) {
        const bit = start + i;
        data[bit >> 3] |= 1 << (bit & 7);
      }
    }
  }
  return data;
}

export function unpackSignals(signals, data) {
  const out = {};
  for (const s of signals) {
    const start = s.start_byte * 8 + s.start_bit;
    let raw = 0;
    for (let i = 0; i < s.length; i++) {
      const bit = start + i;
      if ((bit >> 3) < data.length && (data[bit >> 3] >> (bit & 7)) & 1) raw += 2 ** i;
    }
    if (s.signed && raw >= 2 ** (s.length - 1)) raw -= 2 ** s.length;
    out[s.name] = raw * (s.factor || 1) + (s.offset || 0);
  }
  return out;
}

// --- Trame au niveau bit ---------------------------------------------------------

export function crc15(bits) {
  let crc = 0;
  for (const b of bits) {
    const next = b ^ ((crc >> 14) & 1);
    crc = (crc << 1) & 0x7fff;
    if (next) crc ^= 0x4599;
  }
  return crc;
}

function pushBits(arr, value, n, field) {
  for (let i = n - 1; i >= 0; i--) arr.push({ v: (value >> i) & 1, field });
}

/**
 * Trame de données standard, telle qu'elle passe sur le bus.
 * Chaque bit : { v: 0 dominant | 1 récessif, field, stuff? }.
 * Le bit d'ACK est émis récessif par l'émetteur ; `acked` le montre forcé dominant.
 */
export function frameBits(id, data, { acked = true, dlc = data.length } = {}) {
  const raw = [];
  raw.push({ v: 0, field: "SOF" });
  pushBits(raw, id, 11, "ID");
  raw.push({ v: 0, field: "RTR" }, { v: 0, field: "IDE" }, { v: 0, field: "r0" });
  pushBits(raw, dlc & 0xf, 4, "DLC");
  for (const byte of data.slice(0, 8)) pushBits(raw, byte, 8, "DATA");
  pushBits(raw, crc15(raw.map((b) => b.v)), 15, "CRC");

  const out = [];
  let run = 0;
  let last = -1;
  for (const b of raw) {
    out.push(b);
    run = b.v === last ? run + 1 : 1;
    last = b.v;
    if (run === 5) {
      const s = { v: 1 - b.v, field: b.field, stuff: true };
      out.push(s);
      last = s.v;
      run = 1;
    }
  }
  out.push({ v: 1, field: "CRC delim" });
  out.push({ v: acked ? 0 : 1, field: "ACK" });
  out.push({ v: 1, field: "ACK delim" });
  for (let i = 0; i < 7; i++) out.push({ v: 1, field: "EOF" });
  return out;
}

export const IFS_BITS = 3;
// Trame d'erreur : drapeau (6) + superposition éventuelle des autres drapeaux (jusqu'à 6) + délimiteur (8)
export const ERROR_FRAME_BITS = 6 + 6 + 8;

/** Rang du bit d'identifiant où @p id perd l'arbitrage face à @p winner (-1 s'il gagne). */
export function arbitrationLoss(id, winner) {
  for (let i = 10; i >= 0; i--) {
    const a = (id >> i) & 1;
    const w = (winner >> i) & 1;
    if (a !== w) return a === 1 ? 10 - i : -1;
  }
  return -1;
}

export const hex = (n, w = 3) => "0x" + n.toString(16).toUpperCase().padStart(w, "0");
