// node test_bus.mjs : scénarios du banc sur le moteur de bus.js, sans navigateur.
import { readFileSync } from "node:fs";
import { Bench, STATE } from "./bus.js";
import { hex } from "./can.js";

const icd = JSON.parse(readFileSync(new URL("./icd.json", import.meta.url), "utf8"));
let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? "ok   " : "ÉCHEC"} ${msg}`); if (!ok) fails++; };
const st = (b) => Object.values(b.nodes).map((n) => `${n.name}:${STATE[n.state]} T${n.tec}/R${n.rec}`).join("  ");

// 1. Trafic nominal : 1 s de bus
let b = new Bench(icd);
b.advance(1e6);
const ok = b.trace.filter((e) => e.ok);
check(ok.filter((e) => e.id === 0x100).length >= 49, `nominal : ${ok.filter((e) => e.id === 0x100).length} trames 0x100 en 1 s (période 20 ms)`);
check(ok.filter((e) => e.id >= 0x781).length === 8, `nominal : ${ok.filter((e) => e.id >= 0x781).length} heartbeats en 1 s (4 nœuds × 2)`);
check(b.trace.every((e) => e.ok), "nominal : aucune erreur");
console.log(`      charge du bus ${(b.load() * 100).toFixed(1)} %`);

// 2. Arbitrage ARM/GO : ordre 0x100, 0x200, 0x300 après GO
b.runArbitration();
b.advance(5000);
const after = b.trace.slice(b.trace.findIndex((e) => e.id === 0x011) + 1).slice(0, 3).map((e) => hex(e.id));
check(after.join() === "0x100,0x200,0x300", `arbitrage : après GO ${after.join(" ")}`);
check(b.lastArbitration && b.lastArbitration.contenders.length === 3, `arbitrage : ${JSON.stringify(b.lastArbitration?.contenders)}`);

// 3. SW2 fermé : les émetteurs passent bus-off
b.setSwitch("SW2", true);
b.advance(20000);
check(["N1", "N2", "N3"].every((n) => b.nodes[n].state === 3 || b.nodes[n].tec > 127), `SW2 fermé : ${st(b)}`);
b.setSwitch("SW2", false);
b.advance(300000);
check(Object.values(b.nodes).every((n) => n.state < 3) && b.trace.slice(-20).every((e) => e.ok), `SW2 rouvert, reprise : ${st(b)}`);

// 4. SW3 ouvert : N4 seul, erreurs d'ACK, plafonne en error-passive
b.setSwitch("SW3", false);
b.advance(30e6);
check(b.nodes.N4.state === 2 && b.nodes.N4.tec >= 128 && b.nodes.N4.tec < 256, `SW3 ouvert : ${st(b)}`);
check(b.nodes.N1.state === 0, "SW3 ouvert : le reste du bus continue");
b.setSwitch("SW3", true);
b.advance(3e6);

// 5. Débit erroné sur N4 : N4 détruit des trames tant qu'il est error-active, puis error-passive
b = new Bench(icd);
let n4BusOff = 0;
b.on((type, p) => { if (type === "state" && p.node === "N4" && p.state === 3) n4BusOff++; });
b.sendCfg(4, 2, 2000);
b.advance(1000);
check(b.trace.some((e) => e.tx === "N4" && e.tag === "accusé BENCH_CFG" && e.ok), "débit erroné : N4 accuse réception au débit nominal");
b.advance(1.5e6);
check(Object.keys(b.stats.errBy).some((n) => n !== "N4"), `débit erroné : N4 détruit aussi des trames des autres nœuds ${JSON.stringify(b.stats.errBy)}`);
check(n4BusOff > 0, `débit erroné : N4 passé ${n4BusOff} fois en bus-off, puis reprise automatique (BENCH_BUSOFF_AUTO)`);
check(b.nodes.N1.state < 3, "débit erroné : N1 n'est pas bus-off");
b.advance(2e6);
check(b.nodes.N4.mode === 0, "débit erroné : mode révoqué après 2 s");

// 6. Babbling idiot 0x400 : charge proche de 100 %
b = new Bench(icd);
b.sendCfg(4, 1, 500, 0x400);
b.advance(200000);
check(b.load() > 0.9, `babbling idiot : charge ${(b.load() * 100).toFixed(0)} %`);
check(b.trace.slice(-200).some((e) => e.id === 0x100 && e.ok), "babbling 0x400 : 0x100, plus prioritaire, passe encore");

// 7. SW1 ouvert : quelques erreurs, pas de bus-off
b = new Bench(icd);
b.setSwitch("SW1", false);
b.advance(2e6);
const errs = b.trace.filter((e) => !e.ok).length;
check(errs > 0 && Object.values(b.nodes).every((n) => n.state < 3), `SW1 ouvert : ${errs} erreurs sur ${b.trace.length} trames, ${st(b)}`);

console.log(fails ? `${fails} échec(s)` : "tous les scénarios passent");
process.exit(fails ? 1 : 0);
