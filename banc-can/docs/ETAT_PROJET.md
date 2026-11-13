# État du projet — banc de test CAN G69

Point fait le **13/11/2026**. Ce document dit où en est le projet, ce qui a été
abandonné en cours de route et pourquoi, et ce qui reste à faire. Il est tenu à jour à
chaque changement de cap ; le détail technique reste dans les documents cités.

---

## En bref

- **Banc** : 4 nœuds **Nucleo-G431KB** identiques (N1 à N4), chacun avec un transceiver
  **TJA1051T/3** soudé sur un adaptateur SOP8, sur une paire torsadée à 500 kbit/s.
  Interface PC : **ZLG USBCAN-UC12** (vendu comme MyActuator USBCAN-Z), piloté sans son
  pilote Windows. Schéma de référence :
  [`hardware/cablage_bus_can/cablage_bus_can.pdf`](../hardware/cablage_bus_can/cablage_bus_can.pdf).
- **Logiciel** : firmwares, ICD unique, outils PC `canbench` (ligne de commande, interface
  graphique, `BancCAN.exe`) et simulation 3D sont écrits et testés. Tout compile et tous les
  tests passent.
- **Sur le banc réel** : la phase 1 de mise en route (29/09) et une démonstration de
  dialogue entre nœuds (03/11) ont réussi avec trois Nucleo. Les tests de validation T1 à T7
  n'ont pas encore été passés.
- **Matériel conçu, pas encore fabriqué** : l'adaptateur USB-CAN v0.2 et son boîtier
  imprimé en 3D.

---

## Fait

| Domaine | Ce qui existe | Vérifié |
|---|---|---|
| Firmware des nœuds | N1 à N4 sur Nucleo-G431KB : port FDCAN, horloge HSE (repli HSI signalé), heartbeat, protocole ARM/GO, modes de faute commandés par `BENCH_CFG`, autotest de mise en route | compilation de n1 à n4 ; N1 à N3 éprouvés sur carte |
| Afficheurs | LCD 16x2 sur N1 et N2 (firmware `scope`) | sur carte |
| Pont CAN-USB | firmware slcan sur Nucleo-L476RG (`bridge`) | compilation |
| Modifications des Nucleo | cavalier HW1 retiré, ponts SB9/SB10 soudés | sur N1, N2, N3 (quartz et PLL à 160 MHz vérifiés) |
| ICD | `icd/bench_icd.yaml`, générateur vers C, Python, DBC et LaTeX, 248 vecteurs de référence | CI |
| Outils PC | `canbench` : `monitor`, `arbitration`, `encoding`, `faults`, `busload`, `record`, `replay`, `report` ; interface graphique, `BancCAN.exe`, panneau Qualité | 121 tests Python |
| Adaptateur ZLG | pilote WinUSB écrit dans le dépôt (`pc/canbench/zlg_usbcan/`), protocole documenté | sur le banc |
| Simulation 3D | banc complet dans le navigateur, moteur CAN au bit près | 248 vecteurs, scénarios rejoués |
| Adaptateur USB-CAN v0.2 | STM32G431KB + CH340C + TJA1051T/3, 60 × 30 mm, fiche USB-A en clé ; dossier factory complet ; corrections du cours PCB appliquées (MPN, classe Puissance, teardrops) | ERC 0, DRC 0 erreur |
| Boîtier de l'adaptateur | deux coques encliquetables, tranchées pour la Bambu Lab X1 Carbon du FabLab | rendus et coupes |
| Documentation | mise en route, brochage, configuration logicielle, protocole de validation, présentation | tests de cohérence avec les `board.h` |

Vérifications du 13/11/2026 : tests natifs 10/10, tests Python 121/121, tests de la
simulation 2/2, compilation de `n1`, `n2`, `n3`, `n4`, `n4-selftest`, `n4-selftest-hsi` et
`bridge`.

---

## Abandonné

| Élément prévu | Remplacé par | Pourquoi | Où c'est tracé |
|---|---|---|---|
| **Blue Pill STM32F103** pour le nœud N4 | une **4ᵉ Nucleo-G431KB** | décision du groupe. Conséquences : une seule carte et un seul firmware à maintenir, programmation et journal par le ST-LINK intégré (plus de ST-Link V2 ni d'adaptateur USB-série), plus de clones de qualité incertaine ni de partage CAN/USB propre au F103 | port, `board.h`, config OpenOCD et sous-modules F1 retirés le 13/11/2026 ; derniers dans `d1a745c` |
| **CANable 2.0** (interface PC du dossier v0.1) | **ZLG USBCAN-UC12** côté PC, et notre **adaptateur USB-CAN** à fabriquer | introuvable chez les fournisseurs acceptés par l'école (ticket GLPI 0015779) | `hardware/adaptateur_usb_can/generate_schematic.py` |
| **Pilote Windows du ZLG** (`usbcan.sys`) | pilote **WinUSB** + bibliothèque du dépôt | refusé par l'intégrité de la mémoire de Windows, qu'on ne désactive pas | `README.md` § Adaptateur ZLG |
| **Adafruit CAN Pal** (3 modules, démonstration du 03/11) | **TJA1051T/3** en SO8 sur adaptateurs SOP8, 4 exemplaires | passage à 4 nœuds avec la commande BC-2026-G69-001 | schéma de câblage, révision 0.2 |
| **Connecteurs DB9** (dossier §4.2) | paire torsadée et borniers ; bornier à vis 3 points sur l'adaptateur | plus simple à câbler, rien à souder | `docs/pinout.md` §7 ; commit `ec7d4f1` |
| **Alimentation 12 V + régulateur LM2596** (schéma fonctionnel v0.1) | chaque Nucleo alimentée par son USB, via le **hub alimenté Velleman HQM121C** | le 5 V de la Nucleo suffit aux transceivers ; VIN n'est pas câblé | schéma de câblage |
| Adaptateur USB-CAN : **STM32 en LQFP48** (clone du CANable) | **LQFP32** + pont USB-série **CH340C** | le pas de 0,5 mm ne respecte pas l'isolation de 0,3 mm de la factory | `generate_schematic.py` de l'adaptateur |
| Adaptateur USB-CAN : **DB9**, carte v0.1, **trous de fixation** | bornier à vis, carte **60 × 30 mm**, fiche **USB-A en clé** ; plus de trous, le boîtier tient la carte par les bords | taille d'une clé USB, branchement direct sur le PC | commits `ec7d4f1`, `d1a745c` |
| **Amazon Business** comme fournisseur | distributeurs professionnels (Farnell, RS, Mouser, DigiKey) | refusé par l'école pour les articles non vendus par Amazon (ticket GLPI 0015779) | `generate_commande.py` |
| **SN65HVD230** (transceiver 3,3 V) | TJA1051T/3 | le dossier retient le TJA1051T/3 (broche VIO) | `docs/PLAN.md` §3.3 |

### À confirmer par le groupe

Ces éléments figurent dans le dossier v0.1, le schéma fonctionnel ou la simulation 3D,
mais pas dans le schéma de câblage actuel. Abandonnés ou seulement pas encore montés ?

- les interrupteurs de faute **SW1, SW2, SW3** et la terminaison commutée `R_T2` (les fautes
  logicielles passent par `BENCH_CFG`) ;
- le **MPU-6050** sur N2 ;
- le **capteur à effet Hall** (N2) et la sonde **DS18B20** (N3), prévus au lot 6 ;
- le **pont slcan sur Nucleo-L476RG**, utile tant que l'adaptateur USB-CAN n'est pas fabriqué ;
- les **LCD 16x2** : conservés à côté des futurs écrans OLED, ou remplacés ?

Le schéma fonctionnel `schema/` reste celui de la phase 0 ; le câblage réel fait foi.

---

## Reste à faire

### Matériel

1. **Monter N4** : retirer HW1, souder SB9/SB10, souder les quatre TJA1051T/3 sur leurs
   adaptateurs SOP8 avec leurs 100 nF, et la résistance de 120 Ω sur celui de N4
   ([bringup.md](bringup.md) étape 8).
2. **Faire fabriquer l'adaptateur USB-CAN** : déposer `fabrication/` à la factory, en faisant
   valider les fentes ovales de 2,5 × 0,9 mm des pattes de blindage de la fiche USB-A ;
   commander les composants (`adaptateur_usb_can_commande.xlsx`).
3. **Imprimer le boîtier** au FabLab sur la X1 Carbon : badge, ticket signé par un
   facilitateur, plateau à vérifier (`hardware/adaptateur_usb_can/boitier/README.md`).
4. **Rendre le banc propre** : plaque modulaire imprimée et carte porteuse par nœud, pour
   supprimer les fils Dupont (en discussion).

### Logiciel

5. **Écrans OLED SSD1306** sur les nœuds (lot 6) : I2C1 sur PA15/PB7 déjà réservé dans
   `board.h`, rafraîchissement par DMA et par pages modifiées (`docs/PLAN.md` §2.3).
6. **Défaut D1, côté PC** : `canbench arbitration` attend encore 2 ms entre ARM et GO, ce qui
   fait échouer T3 sur le banc réel (`docs/PLAN.md` §8 bis). Le firmware est déjà corrigé.

### Validation

7. **Passer T1 à T7** sur le banc réel ([protocole_validation.md](protocole_validation.md)),
   T1 et T2 à l'oscilloscope.
8. **Reporter dans le dossier v0.2** les écarts relevés (`docs/PLAN.md` §9 bis).

### Questions encore ouvertes

| # | Question | État |
|---|---|---|
| Q2 | Soudure de SB9/SB10 | faite sur N1 à N3 ; à faire sur N4 |
| Q5b, Q5c | Terminaisons sur les modules transceiver | **tranché** : adaptateurs SOP8 nus, 120 Ω sur le ZLG et sur N4 seulement |
