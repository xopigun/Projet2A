# Plan de travail — Dépôt logiciel du banc de test CAN (G69-BANC-001)

**Phase 0 — lecture des références et plan.** Aucun code écrit à ce stade.
Auteurs (ordre alphabétique) : Samuel GOMRI, Dylan KIATI, Hugo MATHOUX.

---

## 1. État des documents de référence

| Fichier attendu | Présent | Contenu réel | Exploitable |
|---|---|---|---|
| `Dossier_Banc_Test_CAN_v0_1.pdf` | **NON** | — | **Bloquant partiel** |
| `NucleoG431KB Datasheet.pdf` | oui | **UM2397 Rev 2** (manuel utilisateur Nucleo-32 MB1430), 30 p. | **oui, excellent** |
| `BluePill STM32F103.pdf` | oui | Support marketing ST « STM32 development boards portfolio Q1'2022 », 26 p. | **non — hors sujet** |
| `TJA1051.PDF` | oui | NXP TJA1051 Rev 02, 1 juillet 2009, 18 p. | oui |
| `SN65HVD230.PDF` | oui | TI SLOS346G, juin 2002 (HVD230/231/232), 29 p. | oui |
| UM2397 | **fourni sous un autre nom** (voir ci-dessus) | — | oui |
| RM0440 (STM32G4) | NON | — | à récupérer |
| RM0008 (STM32F1) | NON | — | à récupérer |
| DS12589 (datasheet STM32G431) | NON | — | à récupérer |

### 1.1 Point bloquant : le dossier de définition est absent

`docs/references/Dossier_Banc_Test_CAN_v0_1.pdf` n'est pas dans le dépôt. Or c'est la
spécification principale. Tout ce qui en dépend est donc repris **uniquement** depuis
l'énoncé de la mission, sans possibilité de recoupement :

- section 1 — les six fonctions à valider (nommées, jamais énumérées ailleurs) ;
- section 4.6 — protocole ARM/GO (l'énoncé en donne la substance) ;
- tableau 7 — métrique « Perdus » (point §9.6 : **non vérifiable** en l'état) ;
- sections 6 et 7 — dont `config_logicielle.md` et `protocole_validation.md` doivent
  reprendre le contenu ;
- définition de **SW1 / SW2 / SW3** : l'énoncé mentionne que SW2 ne doit être fermé que
  brièvement, ce qui suggère un court-circuit CANH/CANL, mais les trois interrupteurs ne
  sont nulle part définis.

→ **Question 1 (voir §9)** : me fournir le PDF, ou valider les hypothèses que je propose.

### 1.2 Le document « Blue Pill » ne contient aucune information sur la Blue Pill

Le PDF est une présentation commerciale du portfolio cartes ST. Il ne contient ni
brochage STM32F103C8T6, ni schéma de la carte tierce « Blue Pill », ni rien sur bxCAN.
Tout ce qui concerne le nœud N4 devra s'appuyer sur RM0008 + la datasheet F103C8 +
le schéma communautaire de la carte. **Aucun brochage F103 ne sera écrit sans source.**

---

## 2. Vérification des 7 points relevés dans le dossier v0.1 (§9 de la mission)

### 9.1 — PB8 = BOOT0 utilisé en SCL I2C → **CONFIRMÉ (risque réel), et évitable**

Sources : UM2397 Table 12 (« 31 PB8-BOOT0 / BOOT »), §6.6.1 (« LD2 … PB8, si SB7 ON et
SB6 OFF, configuration par défaut »), Table 9.

Deux problèmes cumulés, pas un seul :

1. PB8 est la broche BOOT0 (option byte `nSWBOOT0 = 1` par défaut ⇒ BOOT0 lu sur la
   broche au reset). Une pull-up I2C vers 3,3 V force BOOT0 à 1 au reset ⇒ démarrage
   sur le bootloader système. **Mécanisme à confirmer dans RM0440** — `TODO(verif)`.
2. PB8 porte déjà la LED utilisateur LD2 de la carte (SB7 ON par défaut).

**Solution retenue, entièrement sourcée, sans modification matérielle :**
I2C1 sur **PA15 = SCL** et **PB7 = SDA**, accessibles directement sur **CN4 pin 8
(ARD_D5)** et **CN4 pin 7 (ARD_D4)** — UM2397 Table 11 et Table 12. Aucun pont à souder
n'est requis pour cet usage (SB2/SB3 ne concernent que le report de ces mêmes signaux
vers A4/A5 sur CN3).

Conséquence : PB8 reste libre et **redevient utilisable en LED** (c'est LD2, déjà câblée),
puisque le danger tenait à la pull-up, pas à l'usage en sortie — BOOT0 n'est échantillonné
qu'au reset.

### 9.2 — PA2 en LED alors que c'est le TX du VCP ST-LINK → **CONFIRMÉ**

Sources : UM2397 Table 8 (« SB1, SB12 : ON — USART2 (PA2/PA3) connecté au Virtual COM
port du STLINK-V3E », configuration **par défaut**), Table 9 (SB1 : « T_VCP_TX est
connecté à l'E/S PA2 »), Table 12 (« 7 PA2 T_VCP_TX USART2_Tx »).

PA2 est bien le TX du VCP, câblé par défaut. L'utiliser en LED :

- supprime le journal série (objectif §5.1 de la mission) ;
- met en conflit la sortie du STLINK-V3E et la sortie GPIO.

À noter : PA2 est **aussi** ARD_A7 (CN3 pin 5), donc physiquement accessible — d'où
probablement l'erreur.

**Solution retenue :** PA2/PA3 réservés au VCP (USART2, journal série). Les trois LEDs
passent sur des broches libres (proposition en §4.3).

### 9.3 — Rafraîchissement OLED ≈ 23 ms et non ≈ 10 ms → **CONFIRMÉ**

Calcul : 128×64 / 8 = 1024 octets de GDDRAM. En I2C chaque octet coûte 9 bits (8 + ACK).
1024 × 9 / 400 000 = **23,04 ms**. En ajoutant, pour chacune des 8 pages, START + adresse
+ octet de contrôle + commandes de positionnement colonne/page (≈ 6 octets), soit
8 × 6 × 9 / 400 000 ≈ 1,1 ms, on obtient **≈ 24 ms par trame complète**.

La valeur de ≈ 10 ms du dossier est donc fausse d'un facteur ≈ 2,3 (elle correspondrait à
un comptage de 8 bits/octet **et** à ≈ 800 kHz, hors spécification SSD1306).

Conséquences, qui justifient les deux choix d'architecture :

- à 10 Hz en trame complète, le bus I2C est occupé **24 % du temps**, ce qui entre en
  concurrence directe avec le MPU-6050 sur le même bus → **mise à jour par pages modifiées
  uniquement** ;
- 24 ms de transfert bloquant par rafraîchissement est incompatible avec la boucle
  temps réel → **DMA obligatoire**, l'ISR CAN restant prioritaire.

### 9.4 — Repères PA11/PA12 sur le connecteur Arduino Nano → **CONFIRMÉ**

Source : UM2397 Table 11 — CN4 pin 13 = ARD_D10 = **PA11** ; CN4 pin 5 = ARD_D2 = **PA12**.
Confirmé par Table 12 (« 21 PA11 ARD_D10 », « 22 PA12 ARD_D2 »).

**Réserve importante :** ni Table 11 ni Table 12 ne mentionnent FDCAN. UM2397 liste pour
PA11 « SPI1_CS / TIM1_CH4 » et pour PA12 « IO ». L'affectation **FDCAN1_RX = PA11 /
FDCAN1_TX = PA12 (AF9)** doit être confirmée dans la **datasheet DS12589**, table des
fonctions alternées — `TODO(verif)`. C'est l'affectation usuelle sur G431, mais elle ne
sera pas écrite dans `board.h` sans cette source.

### 9.5 — Blue Pill : PA11/PA12 partagés avec l'USB → **NON VÉRIFIABLE ICI**

Le PDF fourni ne documente pas la carte (voir §1.2). Les points cités dans la mission
(partage USB/bxCAN, pull-up USB sur PA12, clones F103) sont plausibles et connus, mais
**je ne les déclarerai confirmés qu'après lecture de RM0008 + datasheet F103C8 + schéma
de la carte**.

Piste à évaluer alors, qui supprimerait le problème à la racine : **remapper bxCAN sur
PB8/PB9** (`AFIO_MAPR.CAN_REMAP = 10`), broches libres sur la Blue Pill, au lieu de
PA11/PA12 partagées avec l'USB. À trancher au Lot 5 — `TODO(verif)`.

### 9.6 — Métrique « Perdus » du tableau 7 → **NON VÉRIFIABLE** (dossier absent)

Je ne peux pas lire le tableau 7. Sur le principe, l'ambiguïté décrite est réelle :
N3 (0x300) perd l'arbitrage **deux fois par cycle** (contre N1 puis contre N2). « Perdus
1000 » sur 1000 cycles peut donc signifier « 1000 cycles où N3 a perdu » ou « 2000
arbitrages perdus ». Je tranche en **définissant la métrique sans ambiguïté** plutôt qu'en
comptant les pertes (voir §4.4).

### 9.7 — Plage d'identifiants réservés → **À ARRÊTER AVEC TOI** (Question 3)

---

## 3. Points nouveaux relevés pendant la lecture (non listés dans la mission)

### 3.1 — CRITIQUE : cavalier HW1 court-circuite PA12 (FDCAN1_TX) à la masse

UM2397 §6.1 (vue de dessous) : « **HW1 (cavalier 2,54 mm) sur CN4 [4-5]** ».
CN4 pin 4 = GND, CN4 pin 5 = ARD_D2 = **PA12**.
UM2397 §5.1 étape 5 : « Retirer le cavalier placé entre D2 (CN4 pin 5) et GND (CN4 pin 4) ».

**La carte est livrée avec PA12 relié à la masse.** Si PA12 est bien FDCAN1_TX (§9.4),
ne pas retirer HW1 met l'entrée TX du transceiver à 0 ⇒ **état dominant permanent** ⇒ le
bus entier est bloqué, et le symptôme ressemblera à une panne de bus, pas à une erreur de
montage. À écrire en tête de la procédure de montage et du `README.md`.

### 3.2 — CRITIQUE : aucune HSE n'est active par défaut sur la Nucleo-G431KB

UM2397 §6.5 : « **Configuration HSI (par défaut)** : SB9 et SB10 OFF, SB11 et SB8 OFF,
SB13 OFF ». Le quartz X2 **24 MHz / 20 ppm / 6 pF** est bien monté sur la carte (§6.1,
Features p. 2) mais il est **déconnecté**.

Or la mission interdit le HSI comme référence CAN. Trois options :

| Option | Modification | Fréquence | Tolérance |
|---|---|---|---|
| **A (retenue)** | souder **SB9 + SB10** | 24 MHz quartz X2 | 20 ppm = 0,002 % |
| B | souder **SB13** | 25 MHz, MCO du ST-LINK (bypass) | non spécifiée dans UM2397 |
| C | HSI 16 MHz | aucune | ±1 % ⇒ **hors spec** (voir §4.1) |

→ **Une modification matérielle (2 ponts à souder par carte G431) est nécessaire.**
C'est une contrainte de montage à intégrer au dossier. **Question 2.**

### 3.3 — Variante de transceiver : le TJA1051T simple est incompatible 3,3 V

TJA1051 §6, Table 2 : seuls **TJA1051T/3** et **TJA1051TK/3** possèdent la broche VIO
(pin 5) permettant l'interface directe avec un microcontrôleur 3,0–3,6 V. Sur le
**TJA1051T**, pin 5 est n.c. et VIO est relié en interne à VCC, donc **niveaux logiques
5 V** ⇒ incompatible avec les GPIO 3,3 V du STM32 sans adaptation.
Par ailleurs VCC = **4,5 à 5,5 V** dans tous les cas : le TJA1051 doit être alimenté en
5 V (disponible sur CN3 pin 4), avec VIO = 3,3 V.

Le SN65HVD230 est lui intégralement 3,3 V (VCC 3,0–3,6 V). Mixer les deux sur le bus est
acceptable (les niveaux différentiels ISO 11898-2 sont respectés), mais doit être noté.

### 3.4 — Broche S / RS : les deux transceivers n'ont pas la même sémantique

| | TJA1051 (pin 8 « S ») | SN65HVD230 (pin 8 « RS ») |
|---|---|---|
| Niveau bas | Normal | Haute vitesse (pas de contrôle de pente) |
| Niveau haut | **Silent** : émetteur coupé, **récepteur pleinement actif** | **Standby** : émetteur coupé, récepteur actif mais dégradé (temps de réveil) |
| Au repos | pull-down interne ⇒ Normal | à câbler (pull-down externe requis) |

Sources : TJA1051 §6.1.1/6.1.2 et Table 3 ; SN65HVD230 §« pin 8 provides three different
modes » et table « Transceiver modes » (V(Rs) > 0,75 VCC ⇒ Standby).

**Conséquence de conception :** pour le « mode silencieux logiciel » du nœud témoin, il
est préférable d'utiliser le **mode moniteur du contrôleur** (FDCAN bit `CCCR.MON`,
bxCAN bit `BTR.SILM`) plutôt que la broche du transceiver : sémantique identique sur les
deux MCU, pas de dégradation du récepteur, pas de dépendance au modèle de transceiver.
La broche S/RS reste pilotable si `board.h` la définit, en complément.

### 3.5 — Le TJA1051 limite l'injection de faute « dominant permanent »

TJA1051 §6.2.1 : fonction *TXD dominant time-out*. Si TXD reste bas trop longtemps, le
driver est désactivé ; cette temporisation « définit également le débit minimal possible
de 40 kbit/s ». Une faute « dominant collé » sera donc **automatiquement corrigée par le
transceiver** au bout de quelques centaines de µs. Le SN65HVD230 n'a pas cette protection.
À prendre en compte dans la conception de T6 (le mode « babbling idiot » n'est pas affecté,
puisque TXD y bascule normalement).

### 3.6 — Le mode « arrêt d'acquittement » de N4 n'existe pas en tant que tel

Ni bxCAN ni FDCAN n'offrent de « ne pas acquitter » indépendant. Le seul moyen est le
mode moniteur/silencieux, qui n'acquitte pas. Les deux modes de faute demandés
(« passage en mode silencieux » et « arrêt d'acquittement ») sont donc **le même mode**.
Je n'en implémenterai qu'un, nommé `FAULT_SILENT`, documenté comme couvrant les deux.

### 3.7 — Terminaisons : les modules transceiver du commerce embarquent 120 Ω

Les cartes filles SN65HVD230 (« CJMCU-230 ») et TJA1051 courantes ont une résistance de
120 Ω montée à demeure. Avec 4 nœuds : 4 × 120 Ω en parallèle = **30 Ω**, le bus ne
fonctionne pas. Exactement deux terminaisons doivent subsister, aux extrémités.
C'est probablement l'objet de SW1 — à confirmer avec le dossier (Question 1).

### 3.8 — Limite de mesure côté PC pour le critère temporel de l'arbitrage

Le critère « écart temporel entre trames successives mesuré côté PC » (§5.3 de la mission)
se heurte à la latence USB non déterministe du CANable. À 500 kbit/s une trame standard de
8 octets dure ≈ 220 µs ; l'horodatage logiciel côté hôte a une gigue du même ordre, voire
supérieure. Deux parades, à combiner :

1. utiliser l'horodatage **matériel** du firmware candleLight s'il est disponible
   (`TODO(verif)` : dépend de la version de firmware du CANable) ;
2. faire porter le critère chiffré strict par **T2 (mesure oscilloscope)** et par les
   compteurs embarqués des nœuds, et ne garder côté PC qu'un critère large de
   non-régression.

---

## 4. Décisions techniques

### 4.1 Bit timing — valeurs vérifiées par le calcul

Formules (ISO 11898-1 / CiA) :
`df ≤ SJW / (20·NBT)` et `df ≤ min(PS1,PS2) / (2·(13·NBT − PS2))`, tolérance retenue = min.

| Nœud | Horloge noyau | BRP | NBT | SYNC+TSEG1+TSEG2 | SJW | Point d'éch. | df max |
|---|---|---|---|---|---|---|---|
| G431 (retenu) | 80 MHz | 10 | 16 tq | 1 + 13 + 2 | 2 | **87,50 %** | **0,485 %** |
| G431 (variante) | 80 MHz | 5 | 32 tq | 1 + 27 + 4 | 4 | 87,50 % | 0,485 % |
| F103 (retenu) | 36 MHz (APB1) | 9 | 8 tq | 1 + 6 + 1 | 1 | **87,50 %** | **0,485 %** |

**Les trois valeurs proposées dans la mission sont confirmées exactes.** Point
d'échantillonnage identique et rigoureusement égal à 87,5 % sur les deux familles.

**Réponse au « compromis SJW limité » du F103 :** il n'y en a pas. À point d'échantillonnage
égal, la tolérance ne dépend que du **rapport** SJW/NBT, pas de SJW en valeur absolue :
2/16 = 1/8, les deux configurations donnent **exactement 0,485 %**. Les alternatives F103
à plus grand NBT sont d'ailleurs moins bonnes, car bxCAN limite TS1 ≤ 16 tq et TS2 ≤ 8 tq :
le seul autre candidat raisonnable (BRP 4, 18 tq, 1+15+2) donne 88,89 % — donc un point
d'échantillonnage **différent de celui du G431**, ce qui est rédhibitoire ici — pour une
tolérance **inférieure** (0,431 %). La vraie limite de la solution 8 tq est la
**granularité** : un pas de resynchronisation vaut 12,5 % du temps de bit, contre 6,25 %
sur le G431. Sans incidence sur la tolérance, mais à mentionner.

**Justification de l'interdiction du HSI** (demandée en §5.1 de la mission) :
HSI16 est spécifié à **±1 %** sur la plage de température après calibration usine, soit
**plus du double** de la tolérance admissible de 0,485 %. Le quartz X2 (20 ppm = 0,002 %)
laisse une marge de facteur 240. `TODO(verif)` : chiffre ±1 % à confirmer sur DS12589.

### 4.2 Arbre d'horloge G431 proposé

HSE 24 MHz (X2, SB9+SB10 soudés) → PLL : **M = 3** (⇒ 8 MHz, dans la plage 2,66–16 MHz),
**N = 40** (⇒ VCO 320 MHz, dans 96–344 MHz), **R = 2** ⇒ **SYSCLK 160 MHz**,
**Q = 4** ⇒ **horloge noyau FDCAN = 80 MHz**.

Compromis assumé et à documenter : SYSCLK à 160 MHz au lieu du maximum 170 MHz. C'est le
prix d'un point d'échantillonnage **exactement** à 87,5 % partagé avec le F103 — à 170 MHz
sur PCLK1, le meilleur candidat est 88,24 %, qui ne s'aligne pas. 160 MHz est très
largement suffisant pour ce banc. Contraintes PLL à confirmer sur RM0440 — `TODO(verif)`.

### 4.3 Brochage proposé (à figer dans `board.h`, nulle part ailleurs)

**Nucleo-G431KB** — toutes les affectations ci-dessous sont sourcées UM2397 Table 11/12,
sauf la fonction alternée FDCAN, marquée `TODO(verif)` (DS12589) :

| Fonction | Broche | Repère Arduino Nano | Source / remarque |
|---|---|---|---|
| FDCAN1_RX | PA11 | CN4-13 / D10 | AF9 `TODO(verif)` |
| FDCAN1_TX | PA12 | CN4-5 / D2 | AF9 `TODO(verif)` — **retirer HW1** (§3.1) |
| I2C1_SCL | PA15 | CN4-8 / D5 | UM2397 T11 — évite PB8/BOOT0 |
| I2C1_SDA | PB7 | CN4-7 / D4 | UM2397 T11 |
| VCP TX / RX | PA2 / PA3 | CN3-5 / CN3-10 | USART2, SB1+SB12 ON par défaut |
| LED TX | PB8 | (LD2 embarquée) | sortie seule, sans pull-up (§9.1) |
| LED erreur | PB0 | CN4-6 / D3 | libre |
| LED bus-off | PB6 | CN4-9 / D6 | libre |
| Transceiver S | PB5 | CN4-14 / D11 | optionnel (§3.4) |
| HSE | PF0 / PF1 | — | consommées si SB9+SB10 soudés |

**Blue Pill F103** : **aucun brochage proposé à ce stade** — pas de source (§1.2, §9.5).

### 4.4 Métrique d'arbitrage retenue

Je retiens la définition proposée dans la mission, qui lève l'ambiguïté du tableau 7 :

> **rang** = 1 + nombre de trames contendantes reçues entre la fin de GO et la fin de sa
> propre émission.

Attendu : N1 → 1, N2 → 2, N3 → 3, à chaque cycle. On rapporte un **histogramme des rangs
par nœud** plutôt qu'un compteur « perdus », et le verdict est « 1000/1000 cycles au rang
attendu ». Les compteurs de pertes d'arbitrage matériels restent remontés à titre
indicatif dans le heartbeat.

Le raisonnement sur GO est correct et sera documenté : GO (0x011) ayant un identifiant
inférieur à tous les contendants (0x100/0x200/0x300), un nœud armé qui tenterait d'émettre
pendant GO perd l'arbitrage contre GO et retransmet automatiquement à la fin de GO. Le
départ simultané est donc garanti **par l'arbitrage lui-même**, sans hypothèse sur les
latences logicielles — à condition que la retransmission automatique soit active.

### 4.5 Plage d'identifiants réservés (proposition, Question 3)

| ID | Nom | Sens | DLC |
|---|---|---|---|
| 0x010 | `ARM` | PC → nœuds | 8, contenu nul |
| 0x011 | `GO` | PC → nœuds | 8, contenu nul |
| 0x012 | `BENCH_CFG` | PC → nœud | 8 |
| 0x013 | `BENCH_RESULT` | nœud → PC | 8 |
| 0x701..0x704 | `HEARTBEAT_n` | nœud → PC | 8 |

Réserve globale proposée : **0x000–0x01F** et **0x700–0x71F**, à reporter dans les quatre
ICD partenaires. Remarque : 0x000–0x00F reste libre dans la réserve, ce qui laisse une
marge pour un futur identifiant plus prioritaire que ARM si nécessaire.

---

## 5. Arborescence retenue

Conforme à celle de la mission, avec trois ajustements :

```
banc-can/
├── README.md  CHANGELOG.md  LICENSE
├── CMakeLists.txt  CMakePresets.json
├── .gitignore  .gitattributes  .gitmodules  .clang-format  .editorconfig
├── .github/workflows/ci.yml
├── icd/
│   ├── bench_icd.yaml
│   └── schema.json
├── tools/codegen/               # YAML -> C, Python, DBC, LaTeX
├── firmware/
│   ├── common/
│   │   ├── can_if.h
│   │   ├── protocol/           # ARM/GO, trames de service, heartbeat
│   │   ├── icd_gen/            # généré — ne pas éditer
│   │   ├── app/                # rôles N1..N4, modes de test, machine d'états
│   │   ├── ui/                 # SSD1306 + mise en page 3 zones, LEDs
│   │   ├── sensors/            # MPU-6050, DS18B20, Hall + simulateurs
│   │   └── util/               # ring buffer, horodatage, CRC
│   ├── ports/{g431_fdcan,f103_bxcan}/
│   ├── boards/{nucleo_g431kb,bluepill_f103}/board.h
│   ├── vendor/                 # (+) sous-modules ST, isolés du code du projet
│   └── tests_host/
├── pc/canbench/  pc/tests/
├── scripts/                    # bit_timing.py, bus_load.py
└── docs/
    ├── references/
    ├── PLAN.md  architecture.md  pinout.md  bit_timing.md
    ├── config_logicielle.md  protocole_validation.md
    ├── montage.md              # (+) montage, HW1, ponts à souder, terminaisons
    └── latex/
```

Ajustements : (+) `firmware/vendor/` pour cantonner les sous-modules ST ;
(+) `docs/montage.md`, rendu nécessaire par §3.1/§3.2/§3.7 ; `scripts/` inchangé.

---

## 6. Outillage

### 6.1 Sous-modules ST — versions à épingler (dépôts et tags vérifiés ce jour)

| Sous-module | Dernier tag publié |
|---|---|
| `STMicroelectronics/stm32g4xx_hal_driver` | `v1.2.7` |
| `STMicroelectronics/cmsis_device_g4` | `v1.2.6` |
| `STMicroelectronics/stm32f1xx_hal_driver` | `v1.1.10` |
| `STMicroelectronics/cmsis_device_f1` | `v4.3.5` |
| `STMicroelectronics/cmsis_core` | `v5.9.0_20250520` |

Les cinq dépôts existent et sont accessibles (`git ls-remote`). Les tags ci-dessus sont
les plus récents ; **je propose de les épingler tels quels** sauf objection.

### 6.2 État de la machine de développement

| Outil | État |
|---|---|
| git 2.55.0 / cmake 3.29.2 / ninja 1.12.0 | **OK** |
| arm-none-eabi-gcc 13.3.1 (ST 13.3.rel1) | **OK** |
| gcc 13.2.0 (MinGW-w64 UCRT) — tests hôte | **OK** |
| Python 3.13.12 | **OK** (≥ 3.10 requis) |
| `openocd` 0.12.0 | présent mais **hors PATH** : `C:\ST\xpack-openocd-0.12.0-7\bin` |
| `STM32_Programmer_CLI` 2.2.200 | présent mais **hors PATH** (plugin STM32CubeIDE 1.19.0) |
| `ruff`, `clang-format` | **ABSENTS** — à installer (`pip install ruff`) |

⇒ Les cibles `flash_<node>` devront **chercher** les deux exécutables (PATH, puis chemins
d'installation connus sous `C:\ST\`), et non les supposer dans le PATH. La CI Linux
utilisera des chemins différents : la détection sera écrite pour les deux.

### 6.3 Décisions d'outillage

- **Tests hôte C** : CMake + CTest, avec Unity vendorisé (fichier unique, pas de
  sous-module supplémentaire). Le code `common/` ne devra inclure **aucun en-tête HAL**,
  ce qui est vérifié par un test de compilation native.
- **Parité C ↔ Python de l'ICD** : le générateur exporte des **vecteurs de référence JSON**,
  consommés à la fois par le test C et par le test Python. Plus robuste et plus portable
  que `ctypes` en CI multi-plateforme, et ça teste bien la même chose.
- **`.ioc` indicatif** : fourni sous `docs/`, jamais référencé par le build.

---

## 7. Protocole de validation — découpage proposé (T1–T7)

Je retiens le découpage de la mission, avec une réserve sur T1/T2/T7 :

| Test | Objet | Automatisé par | Nature |
|---|---|---|---|
| T1 | Couche physique : niveaux différentiels, terminaisons | — (oscilloscope + multimètre) | manuel |
| T2 | Débit et bit timing : temps de bit, point d'échantillonnage | — (oscilloscope) | manuel |
| T3 | Arbitrage ARM/GO | `canbench arbitration` | automatique |
| T4 | Encodage ICD | `canbench encoding` | automatique |
| T5 | Fautes physiques SW1/SW2/SW3 | `canbench faults` (guidé) | semi-auto |
| T6 | Fautes logicielles N4 | `canbench faults` | automatique |
| T7 | Isolation galvanique | — | **squelette seul** |

Réserves : T1, T2 et T7 ne sont pas automatisables — `canbench` n'y fournira qu'une aide à
la saisie et la mise en forme du rapport. Le critère « six fonctions de la section 1 du
dossier » ne peut pas être tracé tant que le dossier manque (**Question 1**).

---

## 8. Découpage en lots

| Lot | Contenu | Livrable vérifiable |
|---|---|---|
| 1 | Socle : `git init`, ignore/attributes/clang-format, CMake racine, presets, sous-modules épinglés, CI valide | `cmake --preset` configure les 4 nœuds |
| 2 | ICD : `bench_icd.yaml`, `schema.json`, générateur, vecteurs de référence, tests de collision/chevauchement | tests ICD verts, code généré à jour |
| 3 | `firmware/common` + `tests_host` : ring buffer, protocole ARM/GO, heartbeat, machine d'états | CTest vert en natif, zéro include HAL |
| 4 | `ports/g431_fdcan` + `boards/nucleo_g431kb` + horloges + bit timing | N1/N2/N3 compilent sans warning, tailles affichées |
| 5 | `ports/f103_bxcan` + `boards/bluepill_f103` (**après** obtention de RM0008 + schéma) | N4 compile |
| 6 | IHM : SSD1306 DMA + pages partielles, LEDs ; capteurs + simulateurs déterministes | build + test hôte des simulateurs |
| 7 | `pc/canbench` : CLI, simulateur de nœuds, `monitor`/`arbitration`/`encoding` | bout en bout sur bus `virtual` |
| 8 | `faults`, `busload`, `record`/`replay`, `report` | bout en bout sur bus `virtual` |
| 9 | Documentation : `architecture.md`, `pinout.md`, `bit_timing.md`, `config_logicielle.md`, `protocole_validation.md`, `montage.md`, extraits LaTeX, `CHANGELOG.md` | relecture |
| 10 | CI complète, durcissement, récapitulatif matériel | workflow vert |

Le Lot 5 est le seul à dépendre d'un document encore absent ; les autres peuvent démarrer
dès validation de ce plan.

---

## 9. Questions ouvertes — réponses attendues avant le Lot 1

1. **Dossier de définition** : peux-tu déposer `Dossier_Banc_Test_CAN_v0_1.pdf` dans
   `docs/references/` ? À défaut, confirme-moi : (a) la liste des six fonctions de la
   section 1, (b) la définition de SW1/SW2/SW3, (c) le contenu du tableau 7.
2. **Modification matérielle des cartes G431** : acceptes-tu de souder SB9+SB10 sur chaque
   Nucleo (§3.2) ? Sinon je bascule sur SB13 (MCO 25 MHz), ce qui change tout le §4.1/4.2.
3. **Plage d'identifiants réservés** : je valide 0x000–0x01F + 0x700–0x71F (§4.5) ?
4. **Documents manquants** : peux-tu récupérer RM0440, RM0008 et DS12589 ? Le Lot 5 (N4)
   est bloqué sans RM0008 + le schéma de la Blue Pill.
5. **Modèle exact des transceivers achetés** : TJA1051**T/3** ou TJA1051T (§3.3) ?
   SN65HVD230 ou HVD232 ? Et les modules portent-ils un 120 Ω soudé (§3.7) ?
6. **Suivi des PDF dans git** : 25 Mo de références. Je les versionne tels quels, je les
   mets en Git LFS, ou je les laisse hors dépôt (`.gitignore` + note dans le README) ?
7. **Licence** du dépôt (fichier `LICENSE`) ?

---

## 10. Récapitulatif des `TODO(verif)`

| # | Élément | Source à consulter | Bloque |
|---|---|---|---|
| V1 | FDCAN1_RX/TX = PA11/PA12, AF9 | DS12589 (datasheet G431), table des AF | Lot 4 |
| V2 | Mécanisme `nSWBOOT0`/`nBOOT0` sur PB8 | RM0440 § option bytes | doc seule |
| V3 | Contraintes PLL G4 (M, N, Q, R, plages VCO) | RM0440 § RCC | Lot 4 |
| V4 | Précision HSI16 (±1 %) | DS12589 § caractéristiques d'horloge | doc seule |
| V5 | Brochage complet Blue Pill + remap bxCAN PB8/PB9 | RM0008 + DS F103C8 + schéma carte | **Lot 5** |
| V6 | Pull-up USB sur PA12 de la Blue Pill, clones F103 | schéma carte | Lot 5 |
| V7 | Horodatage matériel du firmware candleLight du CANable | doc candleLight / gs_usb | Lot 7 |
| V8 | Tolérance de l'horloge du ST-LINK MCO (option B, §3.2) | UM2448 | si option B |
| V9 | Présence/valeur des terminaisons sur les modules achetés | inspection visuelle | T1 |
