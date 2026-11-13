# Simulation 3D du banc CAN

Banc complet en 3D, interactif, dans un navigateur : les trames circulent sur le bus,
on manœuvre SW1 à SW3, on envoie des `BENCH_CFG` et on lance le test d'arbitrage T3.

## Lancer

Les modules JavaScript et les modèles 3D se chargent par HTTP (pas en `file://`) :

```bash
python -m http.server 8765 --directory banc-can/simulation_3d
```

puis ouvrir <http://localhost:8765>. La console du navigateur donne accès au moteur :
`banc.bench.nodes.N1`, `banc.bench.trace`…

## Ce qui est simulé, et comment

| Niveau | Modèle |
|---|---|
| Trame | CAN 2.0A au bit près : SOF, identifiant, DLC, données, CRC-15, bourrage, ACK, EOF, IFS. Durée exacte à 500 kbit/s. |
| Contenu | Signaux encodés selon l'ICD (`icd.json`, exporté de `icd/bench_icd.yaml`), séquences déterministes des capteurs, compteurs et somme de contrôle. `test_can.mjs` vérifie l'encodeur contre les 248 vecteurs de `icd/reference_vectors.json`. |
| Arbitrage | Nœuds qui démarrent ensemble : l'identifiant le plus faible gagne, les perdants réémettent. Rang du bit de perte affiché. |
| ARM / GO | Comme le firmware : les contendants arment leur trame à la réception d'ARM, GO occupe le bus pendant ce temps, heartbeats suspendus. |
| Erreurs | Confinement ISO 11898-1 : TEC +8 / REC +1, décrément sur succès, error-warning, error-passive, bus-off, reprise automatique après 128 × 11 bits récessifs (`BENCH_BUSOFF_AUTO`). |
| SW2 fermé | Bus récessif : erreur de bit sur le SOF (LEC 5) pour chaque émetteur, puis bus-off. |
| SW3 ouvert | N4 seul : erreur d'ACK, TEC plafonné à 128 (règle de l'émetteur error-passive). |
| SW1 ouvert | **Modèle arbitraire** : 4 % des trames en erreur. Ce n'est pas une mesure. |
| Modes BENCH_CFG | babbling idiot, débit erroné (N4 détruit les trames tant qu'il est error-active), DLC incohérent, silencieux, bus-off maintenu. Le nœud répond `BENCH_RESULT` puis applique le mode. |

`test_bus.mjs` rejoue ces scénarios sans navigateur :

```bash
node test_can.mjs
```

```bash
node test_bus.mjs
```

**Limite de l'animation** : les trains de bits qui « voyagent » sont une illustration
ralentie. Sur le vrai bus, le signal parcourt la ligne en quelques dizaines de ns, bien
moins qu'un bit (2 µs) : tous les nœuds voient le même niveau au même instant. C'est ce
que montre l'éclairage du bus (dominant = allumé) aux vitesses lentes.

## Modèles 3D

`modeles/*.glb` est produit par `generate_modeles_3d.py` (Python de KiCad 9) :

- **adaptateur USB-CAN** : exporté du vrai PCB, `hardware/adaptateur_usb_can/` ;
- **Nucleo-G431KB, module TJA1051, GY-521, LM2596, cartes DB9, terminaisons** :
  maquettes reconstituées avec les boîtiers 3D de la bibliothèque KiCad (QFN-32,
  SOIC-8, micro-USB, barrettes, DB9…) sur un contour aux dimensions de la carte. Le format
  et les connecteurs sont respectés, pas l'implantation exacte ;
- **afficheur 16×2** (WC1602A) et **TO-92** : modèles KiCad tels quels.

```bash
"C:\Program Files\KiCad\9.0\bin\python.exe" generate_modeles_3d.py <chemin de gltf-transform>
```

`gltf-transform` (`npm install @gltf-transform/cli`) simplifie et quantifie les maillages.
La table, les câbles, les interrupteurs, l'alimentation et le PC sont dessinés dans `scene.js`.

| Fichier | Rôle |
|---|---|
| `index.html` | page, mise en forme |
| `app.js` | pupitre, trace, oscilloscope, arbitrage, boucle |
| `scene.js` | scène Three.js et animation des trames |
| `bus.js` | moteur du bus (sans navigateur) |
| `can.js` | trame au niveau bit, encodage des signaux |
| `exporter_icd.py` | écrit `icd.json` depuis `pc/canbench/icd_gen.py` |
