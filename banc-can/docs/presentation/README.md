# Matière pour la présentation technique

Ce dossier rassemble ce qu'il faut pour monter la présentation de ce qui a été fait, partie
technique seulement : pas de planning, de GANTT, de RACI ni de registre des risques. Chaque
section ci-dessous peut donner une ou plusieurs diapositives. Pour chacune : ce qu'il faut
dire, les chiffres clés, et où trouver les images et les sources dans le dépôt.

| Dossier | Contenu |
|---|---|
| `captures/` | captures d'écran de la démonstration du 03/11 sur le banc réel |
| `images/` | rendus 3D, schémas et PCB en PNG 2400 px, prêts à coller dans une diapo |
| `generer_images.py` | régénère `images/` depuis les projets KiCad (KiCad 9 et Edge) |
| `Avancement_Bus_CAN_G69.pptx` | la présentation, 13 diapos |
| `EXPLICATIONS_DIAPOS.md` | ce que montre chaque diapo et comment répondre aux questions : **à lire avant l'oral** |

Les rendus 3D de l'adaptateur ont un fond transparent : ils s'affichent proprement sur une
diapositive claire comme sur une foncée.

---

## 1. Le besoin : un banc de test CAN générique

- Banc **G69-BANC-001** : outil commun pour valider le standard CAN et les ICD produits avec
  les groupes partenaires (Cobot RMD-X, Ecomarathon, Formula Student, MIR1000), tous traités
  au même niveau. Aucun code n'est propre à un partenaire : tout passe par la configuration.
- Paramètres retenus : **500 kbit/s**, CAN 2.0A *classic* (identifiants 11 bits),
  point d'échantillonnage **87,5 %**, tolérance d'oscillateur admissible **0,485 %**.
- Sept tests de validation, de T1 (couche physique) à T7 (isolation galvanique).

Sources : `Banc de Test/Dossier_Banc_Test_CAN_v0.1.pdf` (dossier de définition),
`banc-can/README.md` (§ Paramètres retenus), `banc-can/docs/protocole_validation.md`,
`banc-can/docs/config_logicielle.md`.

## 2. L'ICD : une source unique pour tout le monde

- `banc-can/icd/bench_icd.yaml` décrit tous les identifiants, signaux et encodages.
- Un générateur en tire le C des firmwares, le Python des outils PC, un fichier DBC et les
  tableaux LaTeX : aucune recopie à la main, un test de CI vérifie que le code généré est à
  jour. 248 vecteurs de référence vérifient que les encodeurs donnent tous le même résultat.
- Formulaire ICD distribué aux groupes partenaires : `ICD/icd_bus_can_formulaire.pdf`.
- Exemple d'application à un partenaire : schéma du bus du Cobot, `Cobot/schema_bus_cobot.png`.

Sources : `banc-can/tools/codegen/`, `banc-can/icd/reference_vectors.json`,
`banc-can/docs/latex/icd_encoding_table.tex`.

## 3. Le matériel du banc

- 3 × **NUCLEO-G431KB** (N1, N2, N3), chacune avec un transceiver **Adafruit CAN Pal**
  (TJA1051T/3), sur une paire torsadée CAN_H / CAN_L avec une masse commune.
- Interface PC : **MyActuator USBCAN-Z**, à une extrémité du bus. Les terminaisons de 120 Ω
  sont sur l'USBCAN-Z et sur la CAN Pal de N3, les deux extrémités.
- Firmware prévu aussi pour un 4ᵉ nœud sur **Blue Pill STM32F103** et pour la Nucleo-L476RG.
- Deux modifications sur chaque Nucleo, trouvées en lisant la documentation de ST (UM2397) :
  - **retirer le cavalier HW1**, qui relie PA12 (FDCAN1_TX) à la masse et bloquerait le bus
    en état dominant ;
  - **souder les ponts SB9 et SB10** pour brancher le quartz 24 MHz. L'oscillateur interne
    HSI (±1 %) dépasse la tolérance CAN de 0,485 %. Ponts soudés et vérifiés sur les trois
    cartes : horloge sur le quartz, PLL à 160 MHz.

| Image | Fichier |
|---|---|
| Schéma de câblage complet (KiCad) | `images/cablage_bus_can.png` |
| Emplacement des ponts SB9/SB10 | `banc-can/docs/SB9_SB10_emplacement.png` |
| Broches utilisées sur la Nucleo (D2, D10, 3V3, GND, VIN) | `banc-can/docs/nucleo_broches_banc.png` |
| Schéma fonctionnel du banc | `banc-can/schema/preview.png` |
| Schéma des écrans LCD 16x2 | `banc-can/docs/latex/schema_ecrans_lcd.pdf` |

Sources : `banc-can/hardware/cablage_bus_can/` (projet KiCad, PDF, ERC sans erreur),
`banc-can/docs/pinout.md`, `banc-can/docs/bringup.md`.

## 4. Les firmwares

- Code commun indépendant du microcontrôleur (`firmware/common/`) : tampon circulaire,
  protocole ARM/GO pour le test d'arbitrage, heartbeat, modes de faute commandés à distance
  par `BENCH_CFG` (babbling idiot, débit erroné, DLC incohérent, silencieux, bus-off).
- Une couche par contrôleur : FDCAN pour le G431, bxCAN pour le F103 et le L476.
- Tout le brochage est dans un seul fichier par carte, `firmware/boards/*/board.h`.
- Autotest de mise en route : bouclage interne du contrôleur, puis ping/pong sur le bus.
- Tests unitaires du code commun sur PC, sans matériel (`ctest --preset host`).
- Défauts trouvés et corrigés en cours de route, utiles pour une diapo « difficultés » :
  copie de 64 octets par la HAL dans un tampon de 8 (débordement), nœuds figés au démarrage
  faute de gestionnaire SysTick, compteur DWT figé par STM32CubeProgrammer, écarts du dossier
  v0.1 (PB9 absent du boîtier, PA2 déjà pris par le port COM du ST-LINK). Liste complète
  dans `banc-can/CHANGELOG.md`.

## 5. Les outils PC

- **`canbench`**, en ligne de commande : moniteur, tests d'arbitrage, d'encodage et de
  fautes, charge du bus, enregistrement et rejeu, rapports Markdown et LaTeX datés avec le
  hash git du firmware. Tout tourne aussi sur un bus virtuel avec un simulateur de N1 à N4,
  mais aucun verdict de réussite n'y est prononcé.
- **Interface graphique** dans le navigateur et logiciel Windows **`BancCAN.exe`** : bus en
  direct, état des nœuds, trames décodées, tests T3, T4 et T6, injection de fautes,
  chronogrammes de la couche physique.
- **Moniteur de dialogue** (`banc-can/pc/moniteur_dialogue.py`), utilisé pour la démo du
  §7 avec l'USBCAN-Z.

Sources : `banc-can/pc/canbench/`, `banc-can/lancer_banc.bat`, `banc-can/pc/build_exe.py`.

## 6. La simulation 3D du banc

- Banc complet en 3D dans un navigateur (Three.js), avec les vrais modèles 3D des
  composants exportés de KiCad.
- Moteur CAN 2.0A au bit près : CRC-15, bourrage de bits, arbitrage, ACK, compteurs
  d'erreurs TEC/REC, error-passive, bus-off et reprise. Les trames circulent sur le bus.
- On peut manœuvrer les interrupteurs de faute SW1 à SW3, envoyer des `BENCH_CFG` et lancer
  le test d'arbitrage T3.
- Vérifiée par 248 vecteurs de référence et 7 scénarios rejoués sans navigateur.
- Lancement : `python -m http.server 8765 --directory banc-can/simulation_3d`, puis
  <http://localhost:8765>. Utile pour une démo en direct.

| Image | Fichier |
|---|---|
| Vue d'ensemble de la simulation | `images/simulation_3d.png` |

Sources : `banc-can/simulation_3d/LISEZMOI.md`.

## 7. Démonstration sur le banc réel, 03/11

Dialogue entre deux nœuds et appels depuis le PC, sur le bus réel à 500 kbit/s :

1. N1 envoie à N2 « M'entends tu ? » (ID 0x0A1) ;
2. N2 répond « Oui » (ID 0x0A2) ;
3. N1 conclut « Tres bien » (texte ASCII, sans accent).

N1 relance la question toutes les 5 s, et chaque réponse part 300 ms après le message
reçu. Le PC appelle un nœud, ou tous, sur l'ID 0x0B0, et chaque nœud répond « Ici Nn »
sur 0x0B0 + n. Les messages de plus de 7 caractères sont découpés en plusieurs trames : l'octet 0
porte le numéro de la partie et le nombre de parties, les 7 autres octets le texte.

Constaté sur le bus : heartbeats, arbitrage (0x100 passe avant 0x200), dialogue et appels,
avec des compteurs d'erreurs à 0.

| Capture | Ce qu'elle montre |
|---|---|
| `captures/01_moniteur_dialogue_et_appels.png` | le moniteur en entier : trames émises (TX) et reçues (RX), avec leur transcription |
| `captures/02_gros_plan_dialogue_N1_N2.png` | gros plan sur le dialogue entre N1 et N2 |
| `captures/03_gros_plan_appels_du_PC.png` | gros plan sur les appels du PC et les réponses des nœuds |
| `captures/04_zcanpro_trames_brutes.jpg` | les mêmes trames, brutes, dans ZCANPRO (logiciel du fabricant de l'interface) |

Sources : `banc-can/firmware/entry/dialogue.c` (presets `n1-dialogue`, `n2-dialogue`,
`n3-dialogue`), `banc-can/pc/moniteur_dialogue.py`.

## 8. L'adaptateur USB-CAN conçu par le groupe (KiCad)

- Pourquoi : le CANable 2.0 prévu ne pouvait pas être commandé (ticket GLPI 0015779). On a
  donc conçu une carte équivalente, fabricable à la factory de l'ENSEA.
- Chaîne : USB-B → protection ESD USBLC6-2SC6 → pont USB-série **CH340C** →
  **STM32G431KBT6** (FDCAN) → transceiver **TJA1051T/3** → **bornier à vis** 3 points
  (CAN_H, CAN_L, masse), comme celui de l'USBCAN-Z. Régulateur AMS1117-3.3, quartz 8 MHz, terminaison 120 Ω sur cavalier,
  connecteur SWD, boutons RESET et BOOT0, LED d'alimentation, RX et TX.
- PCB 2 couches de **87,7 × 41 mm**, cuivre nu, aux règles de la factory (piste 0,4 mm,
  isolation 0,3 mm), routé avec Freerouting.
- Vérifications : ERC 0 erreur ; DRC 0 piste non connectée, 0 erreur d'empreinte (7
  avertissements de sérigraphie seulement). Chaque composant vérifié contre sa datasheet,
  avec la page ou le tableau utilisé.
- Dossier de fabrication complet : Gerber, perçages, nomenclature, tableau de commande avec
  les liens fournisseurs, PCB imprimable à l'échelle 1:1.

| Image | Fichier |
|---|---|
| Vue 3D en perspective | `images/adaptateur_3d_iso.png` |
| Vue 3D de dessus et de dessous | `images/adaptateur_3d_dessus.png`, `images/adaptateur_3d_dessous.png` |
| Schéma électrique | `images/adaptateur_schema.png` |
| PCB routé (deux couches de cuivre) | `images/adaptateur_pcb.png` |

Sources : `banc-can/hardware/adaptateur_usb_can/` (projet KiCad, scripts de génération),
`fabrication/` (Gerber, BOM, `schema.pdf`, `implantation.pdf`, `pcb_echelle_1.pdf`,
`adaptateur_usb_can_commande.xlsx`), `SOURCES_COMPOSANTS.md` (vérification composant par
composant), `banc-can/hardware/regles_fabrication/` (règles et guide de la factory).

## 9. Limites connues, pour être honnête à l'oral

- Hors du test d'arbitrage, les nœuds n'émettent leurs trames applicatives qu'après ARM, et
  non toutes les 20 ms comme le prévoit l'ICD. Ils émettent aussi dès ARM, sans attendre GO.
- Le débit n'a pas encore été mesuré contre une référence indépendante (oscilloscope) :
  c'est la phase 3 de `banc-can/docs/bringup.md`.
- L'USBCAN-Z est un clone d'une interface ZLG. Son pilote Windows n'est pas compatible avec
  l'« intégrité de la mémoire » de Windows 11 : il faut la désactiver pendant les essais,
  ou utiliser un PC dédié au banc.
- Le modèle de faute SW1 (terminaison retirée) de la simulation est arbitraire : 4 % de
  trames en erreur, ce n'est pas une mesure.
