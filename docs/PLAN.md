# Plan de travail — Dépôt logiciel du banc de test CAN (G69-BANC-001)

**Phase 0 — validée.** Ce document est tenu à jour au fil des lots.
Auteurs (ordre alphabétique) : Samuel GOMRI, Dylan KIATI, Hugo MATHOUX.

Révisions de ce plan :

| Rév. | Objet |
|---|---|
| r1 | Phase 0 initiale, dossier de définition absent |
| r2 | Dossier de définition lu ; réponses Q1–Q7 intégrées ; vérification SB2/SB3 |

---

## 1. État des documents de référence

| Document | Présent | Contenu réel | Exploitable |
|---|---|---|---|
| `Dossier_Banc_Test_CAN_v0_1.pdf` | **oui** (r2) | G69-BANC-001 v0.1, 22/09/2026 | **oui** — source LaTeX également disponible |
| `NucleoG431KB Datasheet.pdf` | oui | **UM2397 Rev 2** (manuel Nucleo-32 MB1430) | **oui** |
| `BluePill STM32F103.pdf` | oui | Support marketing ST « portfolio cartes Q1'2022 » | **non — hors sujet** |
| `TJA1051.PDF` | oui | NXP TJA1051 Rev 02 | oui |
| `SN65HVD230.PDF` | oui | TI SLOS346G | oui (hors BOM nominale, voir §3.3) |
| RM0440, RM0008, DS12589, DS5319, ES G431, schéma Blue Pill | **en cours** (Q4) | — | Lot 5 en attente |

Le fichier PDF du dossier a été recopié depuis `Downloads` vers `docs/references/` sous le
nom `Dossier_Banc_Test_CAN_v0_1.pdf`. La source LaTeX se trouve hors dépôt, dans
`Projet 2A/Banc de Test/` : c'est elle qui fait foi pour les tableaux.

> Le PDF « BluePill STM32F103 » ne documente pas la carte (voir §2.5). Il est conservé
> pour mémoire mais n'est pas une source.

---

## 2. Vérification des 7 points relevés dans le dossier v0.1

### 2.1 — PB8 = BOOT0 utilisé en SCL I2C → **CONFIRMÉ**, et le problème est plus grave

Le dossier (§4.4, figure « IHM locale ») affecte `PB8 -- SCL` et **`PB9 -- SDA`**.

1. **PB9 n'existe pas.** UM2397 Table 12 énumère les 32 broches du boîtier UFQFPN32 :
   PA0–PA15, PB0, PB3, PB4, PB5, PB6, PB7, PB8, PF0, PF1, PG10. **Il n'y a pas de PB9.**
   Le schéma IHM du dossier n'est donc pas réalisable tel quel.
2. **PB8 est BOOT0** (UM2397 Table 12 : « 31 PB8-BOOT0 / BOOT »). Une pull-up I2C vers
   3,3 V force BOOT0 à 1 au reset ⇒ démarrage sur le bootloader système. Mécanisme à
   confirmer dans RM0440 — `TODO(verif) V2`.
3. **PB8 porte déjà LD2** (UM2397 §6.6.1 et Table 9, SB7 **ON** par défaut — gras vérifié).

**Solution retenue :** I2C1 sur **PA15 = SCL** et **PB7 = SDA** (voir §2.8 pour la
vérification SB2/SB3 demandée). PB8 redevient utilisable **en sortie** pour la LED TX :
le danger tenait à la pull-up, pas à l'usage en sortie, BOOT0 n'étant échantillonné qu'au
reset.

### 2.2 — PA2 en LED alors que c'est le TX du VCP → **CONFIRMÉ**

Le dossier affecte les LEDs à `PA0`, `PA1`, `PA2`.

UM2397 Table 9, état par défaut **en gras vérifié par extraction de police** :
**SB1 = ON** (« T_VCP_TX is connected to STM32G4 I/O PA2 ») et **SB12 = ON**. Table 8 et
Table 12 (« 7 PA2 T_VCP_TX USART2_Tx ») concordent.

PA0 et PA1 sont libres et conservés. Seule la LED sur PA2 est déplacée.

### 2.3 — Rafraîchissement OLED ≈ 23 ms et non ≈ 10 ms → **CONFIRMÉ**

Le dossier (§4.4, « Contrainte de temps d'exécution ») annonce « environ 10 ms, soit
l'équivalent d'une vingtaine de trames ».

Calcul : 1024 octets de GDDRAM, 9 bits par octet en I2C (8 + ACK) :
1024 × 9 / 400 000 = **23,04 ms**, plus ≈ 1,1 ms d'adressage des 8 pages ⇒ **≈ 24 ms**.

À 500 kbit/s une trame standard de 8 octets occupe le bus ≈ 220 µs, donc 24 ms
correspondent à **≈ 105 trames** et non à une vingtaine. Les deux chiffres du dossier sont
à corriger (le second ne découle d'ailleurs pas du premier : 10 ms feraient déjà ≈ 45 trames).

La conclusion du dossier — ne jamais rafraîchir dans l'ISR — reste **juste et même
renforcée**. S'y ajoutent les deux choix d'architecture : DMA non bloquant, et mise à jour
par pages modifiées uniquement (à 10 Hz en trame complète le bus I2C serait occupé 24 % du
temps, en concurrence directe avec le MPU-6050 qui le partage).

### 2.4 — Repères PA11/PA12 sur le connecteur Arduino Nano → **CONFIRMÉ**

UM2397 Table 11 : CN4 pin 13 = ARD_D10 = **PA11** ; CN4 pin 5 = ARD_D2 = **PA12**.
Confirmé par Table 12. Le dossier demandait précisément cette vérification.

**Réserve :** UM2397 ne mentionne pas FDCAN (il liste « SPI1_CS / TIM1_CH4 » pour PA11 et
« IO » pour PA12). L'affectation **FDCAN1_RX = PA11 / FDCAN1_TX = PA12 en AF9** reste à
confirmer sur DS12589 — `TODO(verif) V1`. Le `board.h` la porte derrière une constante
unique, signalée.

### 2.5 — Blue Pill : PA11/PA12 partagés avec l'USB → **NON VÉRIFIABLE**

Le PDF fourni est un support marketing sans aucune information sur la carte, le F103 ou
bxCAN. En attente de RM0008 + DS5319 + schéma (Q4). Piste à évaluer alors : remapper bxCAN
sur PB8/PB9 (`AFIO_MAPR.CAN_REMAP = 10`) pour éviter le partage avec l'USB —
`TODO(verif) V5`. **Lot 5 bloqué.**

### 2.6 — Métrique « Perdus » du tableau 7 → **AMBIGUÏTÉ CONFIRMÉE**

Tableau 7 du dossier, lu dans la source :

| Nœud | Identifiant | Gagnés | Perdus | ARM reçus |
|---|---|---|---|---|
| N1 | 0x100 | 1000 | 0 | 1000 |
| N2 | 0x200 | 0 | 1000 | 1000 |
| N3 | 0x300 | 0 | 1000 | 1000 |

L'ambiguïté est réelle et démontrée : sur un cycle, après la fin de GO les trois nœuds
émettent ensemble ; N1 gagne, N2 et N3 perdent ; puis N2 et N3 retransmettent et **N3 perd
une seconde fois**. N3 subit donc **2000 pertes d'arbitrage** sur 1000 cycles, alors que le
tableau affiche 1000. La colonne compte donc des **cycles**, pas des arbitrages.

**Décision :** on conserve les colonnes du tableau 7 pour la compatibilité avec le dossier,
en définissant explicitement `perdus` = *nombre de cycles où le nœud a perdu au moins un
arbitrage*, et on ajoute la métrique non ambiguë du §4.4 (rang), qui est celle sur laquelle
porte le critère de réussite chiffré.

### 2.7 — Plage d'identifiants réservés → **résolu par Q3**, voir §4.5

### 2.8 — Vérification demandée : D4/D5 (PB7/PA15) reliés à A4/A5 ?

**Réponse : oui, SB2 et SB3 sont fermés (ON) par défaut.** Vérifié par extraction des
polices de UM2397 Table 9 : dans les deux cas, c'est la ligne `ON` qui est en gras, et la
note 1 du tableau précise « The default SB state is in bold ».

| Pont | Défaut | Effet |
|---|---|---|
| **SB3** | **ON** | PA15 relié à CN3 pin 7 (A5) — « PA15 does not support ARDUINO Nano D5 **and PA6 must be configured as floating input** » |
| **SB2** | **ON** | PB7 relié à CN3 pin 8 (A4) — « PB7 does not support ARDUINO Nano D4 **and PA5 must be configured as floating input** » |

**Mais il ne faut pas les ouvrir.** PA15 et PB7 sont câblés en dur sur CN4 pin 8 et CN4
pin 7 (Table 11/12) ; SB2/SB3 les reportent **en plus** sur A4/A5, qui est l'emplacement
I2C standard d'un Arduino Nano. Notre câblage (OLED + MPU-6050 sur D4/D5, ou
indifféremment sur A4/A5 — c'est le même net) fonctionne donc **sans aucune modification
matérielle**.

La contrainte réelle est **logicielle** et sera portée par `board.h` :
**PA5 et PA6 doivent être configurées en entrée flottante**, faute de quoi elles entrent en
conflit avec PB7 et PA15 via CN3 pins 7 et 8. C'est le seul point à respecter.

Si une séparation stricte D4/D5 ↔ A4/A5 devenait nécessaire (ce n'est pas le cas ici), il
faudrait ouvrir **SB2** et **SB3** — et alors A4/A5 redeviendraient des entrées analogiques
sur PA5/PA6.

---

## 3. Points relevés pendant la lecture, non listés dans le dossier

### 3.1 — CRITIQUE : cavalier HW1 court-circuite PA12 (FDCAN1_TX) à la masse

UM2397 §6.1 : « **HW1 (cavalier 2,54 mm) sur CN4 [4-5]** ». CN4 pin 4 = GND,
CN4 pin 5 = ARD_D2 = **PA12**. UM2397 §5.1 étape 5 : « Retirer le cavalier placé entre D2
(CN4 pin 5) et GND (CN4 pin 4) ».

**La carte est livrée avec PA12 relié à la masse.** PA12 étant FDCAN1_TX, ne pas retirer
HW1 met TXD du transceiver à 0 ⇒ **dominant permanent** ⇒ bus entier bloqué, avec un
symptôme qui ressemble à une panne matérielle et non à une erreur de montage.
→ En tête de `README.md` et de `docs/montage.md` (Q2).

### 3.2 — CRITIQUE : aucune HSE active par défaut sur la Nucleo-G431KB

UM2397 §6.5 : « **HSI configuration (default)** ». Vérifié sur Table 9 : **SB9, SB10, SB8,
SB11 et SB13 sont tous OFF en gras**. Le quartz X2 (24 MHz, 20 ppm, 6 pF) est monté mais
**déconnecté**.

| Option | Modification | Fréquence | Tolérance |
|---|---|---|---|
| **A (cible)** | souder **SB9 + SB10** | 24 MHz quartz X2 | 20 ppm = 0,002 % |
| B | souder **SB13** | 25 MHz, MCO ST-LINK | non spécifiée — `TODO(verif) V8` |
| C (repli) | HSI 16 MHz | aucune | ±1 % ⇒ **hors spec** (§4.1) |

**Décision (Q2, accord encadrants en attente) :** la source d'horloge est **sélectionnable
dans `board.h`**, HSE par défaut. Le repli HSI est explicite et bruyant :

- `#warning` à la compilation ;
- bandeau **« HSI - NON VALIDE »** en zone Identité de l'OLED ;
- bit `clock_not_qualified` dans le heartbeat, remonté par `canbench monitor` ;
- `canbench report` refuse d'émettre un verdict de réussite pour T2/T3 si un nœud le signale.

### 3.3 — Transceivers : le dossier tranche pour le TJA1051T/3

Le dossier (§2.3 et §4.1) retient **TJA1051T/3** pour les quatre nœuds, avec
VCC = 5 V et VIO = 3,3 V. C'est le bon choix : seuls les TJA1051**T/3** et **TK/3** ont la
broche VIO (TJA1051 Table 2) ; le TJA1051T simple a des niveaux logiques 5 V, incompatibles
avec le STM32 sans adaptation.

⇒ **Q5 première question répondue par le document.** Le SN65HVD230 (3,3 V intégral) n'est
donc pas dans la BOM nominale ; le support reste possible via `board.h` mais n'est pas
implémenté.

**Q5 deuxième question — toujours ouverte :** la présence d'une résistance de 120 Ω soudée
sur les modules transceiver n'est pas renseignée (champ resté entre crochets). Voir §3.7.

### 3.4 — Broche S : sémantique et choix du mode silencieux

Le dossier câble S à la masse (mode normal) et note qu'une GPIO permettrait le mode
silencieux. TJA1051 §6.1.2 : niveau haut sur S ⇒ émetteur coupé, **récepteur pleinement
actif**, avec pull-down interne (donc mode normal si la broche flotte).

**Décision :** le mode silencieux logiciel utilise le **mode moniteur du contrôleur**
(FDCAN `CCCR.MON`, bxCAN `BTR.SILM`) : sémantique identique sur les deux MCU, aucune
dépendance au modèle de transceiver, et pas de broche supplémentaire. La broche S reste
pilotable si `board.h` la définit.

### 3.5 — Le TJA1051 limite l'injection de faute « dominant permanent »

TJA1051 §6.2.1 : *TXD dominant time-out*, qui « définit également le débit minimal possible
de 40 kbit/s ». Une faute « dominant collé » sera **automatiquement corrigée par le
transceiver** après quelques centaines de µs. Sans effet sur le mode *babbling idiot*
(TXD y bascule normalement), mais à documenter dans T6.

### 3.6 — Le mode « arrêt d'acquittement » de N4 n'existe pas séparément

Ni bxCAN ni FDCAN n'offrent de « ne pas acquitter » indépendant : le seul moyen est le mode
moniteur, qui n'acquitte pas. Les deux modes demandés (« mode silencieux » et « arrêt
d'acquittement ») sont **le même mode**, implémenté une seule fois sous le nom
`FAULT_SILENT` et documenté comme couvrant les deux.

### 3.7 — Terminaisons : conflit potentiel entre le dossier et les modules du commerce

Le dossier (§4.2, §4.3) définit **deux terminaisons discrètes** : R_T1 fixe à une extrémité,
R_T2 commutée par SW1 à l'autre. Les nœuds sont sur des dérivations courtes, **pas** aux
extrémités de la ligne.

Or les modules transceiver du commerce portent fréquemment un 120 Ω soudé à demeure. Si
c'est le cas ici, il faut le retirer sur **les quatre nœuds** — et non sur N2/N3/N4
seulement comme l'indiquait la réponse Q5 : d'après le dossier, N1 n'est pas en bout de
ligne et ne tient pas lieu de R_T1.

⇒ **À trancher (Q5 bis)** : soit on retire le 120 Ω des quatre modules et on garde R_T1/R_T2
discrètes conformément au dossier, soit on assume une topologie différente, qu'il faudra
alors corriger dans le dossier. En attendant, `docs/pinout.md` documentera l'option
« quatre modules dépeuplés », conforme au dossier.

### 3.8 — Limite de mesure côté PC pour le critère temporel de l'arbitrage

À 500 kbit/s une trame standard de 8 octets dure ≈ 220 µs, du même ordre que la gigue USB
du CANable. Parades combinées : horodatage matériel candleLight s'il est disponible
(`TODO(verif) V7`) ; critère chiffré strict porté par T2 (oscilloscope) et par les compteurs
embarqués ; côté PC, un critère large de non-régression seulement.

### 3.9 — Le protocole ARM/GO du dossier et celui de l'énoncé sont complémentaires

Le dossier (§4.6) justifie le départ simultané par la **durée de GO** : 8 octets ≈ 250 µs,
« deux ordres de grandeur » au-dessus de la latence d'interruption, donc tous les contendants
sont armés avant la libération du bus. Vérification : trame standard 8 octets = 108 bits,
soit 216 µs, jusqu'à ≈ 246 µs avec bit stuffing au pire cas. **Le chiffre du dossier est
correct.**

L'énoncé avance un second argument : GO (0x011) ayant un identifiant inférieur à tous les
contendants, un nœud armé **avant même le début de GO** perd l'arbitrage contre GO et
attend sa fin.

Les deux arguments couvrent des cas différents et sont donc **complémentaires** — le
premier traite l'armement pendant GO, le second l'armement trop précoce. Ensemble, ils
ferment la démonstration. `docs/architecture.md` les présentera comme tels. La contrainte
d'ordre qui en découle (`ID(GO) < min(ID contendants)`) est vérifiée par le générateur (§4.5).

---

## 4. Décisions techniques

### 4.1 Bit timing — valeurs vérifiées par le calcul

Formules (ISO 11898-1 / CiA) : `df ≤ SJW/(20·NBT)` et
`df ≤ min(PS1,PS2)/(2·(13·NBT − PS2))`, tolérance retenue = min des deux.

| Nœud | Horloge noyau | BRP | NBT | SYNC+TSEG1+TSEG2 | SJW | Point d'éch. | df max |
|---|---|---|---|---|---|---|---|
| G431 (retenu) | 80 MHz | 10 | 16 tq | 1 + 13 + 2 | 2 | **87,50 %** | **0,485 %** |
| G431 (variante) | 80 MHz | 5 | 32 tq | 1 + 27 + 4 | 4 | 87,50 % | 0,485 % |
| F103 (retenu) | 36 MHz (APB1) | 9 | 8 tq | 1 + 6 + 1 | 1 | **87,50 %** | **0,485 %** |

Les trois configurations proposées sont **confirmées exactes**, avec un point
d'échantillonnage rigoureusement égal à 87,5 % sur les deux familles.

**Le « compromis SJW limité » du F103 n'en est pas un.** À point d'échantillonnage égal, la
tolérance ne dépend que du **rapport** SJW/NBT : 1/8 = 2/16, d'où exactement 0,485 % dans
les deux cas. Les alternatives à plus grand NBT sont moins bonnes : bxCAN limite TS1 ≤ 16 tq
et TS2 ≤ 8 tq, et le seul autre candidat raisonnable (BRP 4, 18 tq, 1+15+2) donne 88,89 % —
donc un point d'échantillonnage **désaligné du G431**, rédhibitoire — pour une tolérance
**inférieure** (0,431 %). La vraie limite de la solution 8 tq est la **granularité** : un pas
de resynchronisation vaut 12,5 % du temps de bit contre 6,25 % sur le G431.

**Justification de l'interdiction du HSI :** HSI16 est spécifié à **±1 %**, soit plus du
double de la tolérance admissible de 0,485 %. Le quartz X2 (20 ppm) laisse une marge de
facteur 240. `TODO(verif) V4` : ±1 % à confirmer sur DS12589.

### 4.2 Arbre d'horloge G431

HSE 24 MHz → PLL **M = 3** (⇒ 8 MHz, plage 2,66–16 MHz), **N = 40** (⇒ VCO 320 MHz, plage
96–344 MHz), **R = 2** ⇒ **SYSCLK 160 MHz**, **Q = 4** ⇒ **horloge noyau FDCAN = 80 MHz**.

Compromis assumé : SYSCLK à 160 MHz au lieu du maximum 170 MHz, prix d'un point
d'échantillonnage **exactement** à 87,5 % partagé avec le F103 (à 170 MHz sur PCLK1 le
meilleur candidat est 88,24 %, désaligné). 160 MHz est très largement suffisant ici.
Contraintes PLL à confirmer sur RM0440 — `TODO(verif) V3`.

### 4.3 Brochage proposé (à figer dans `board.h`, nulle part ailleurs)

**Nucleo-G431KB** — sources UM2397 Tables 11/12, sauf mention contraire :

| Fonction | Broche | Repère Nano | Source / remarque |
|---|---|---|---|
| FDCAN1_RX | PA11 | CN4-13 / D10 | AF9 `TODO(verif) V1` |
| FDCAN1_TX | PA12 | CN4-5 / D2 | AF9 `TODO(verif) V1` — **retirer HW1** (§3.1) |
| I2C1_SCL | PA15 | CN4-8 / D5 (= CN3-7 / A5) | SB3 ON — **PA6 en entrée flottante** (§2.8) |
| I2C1_SDA | PB7 | CN4-7 / D4 (= CN3-8 / A4) | SB2 ON — **PA5 en entrée flottante** (§2.8) |
| VCP TX / RX | PA2 / PA3 | CN3-5 / CN3-10 | USART2, SB1+SB12 ON |
| LED TX | PB8 | LD2 embarquée | sortie seule, sans pull-up (§2.1) |
| LED erreur | PA0 | CN3-12 / A0 | conservée du dossier |
| LED bus-off | PA1 | CN3-11 / A1 | conservée du dossier |
| Transceiver S | PB6 | CN4-9 / D6 | optionnel (§3.4) |
| HSE | PF0 / PF1 | — | consommées si SB9+SB10 soudés |

Par rapport au dossier : SCL/SDA déplacés de PB8/PB9 (PB9 inexistant) vers PA15/PB7 ; LED TX
déplacée de PA2 (VCP) vers PB8 ; PA0 et PA1 conservées.

**Blue Pill F103** : aucun brochage proposé — pas de source (§2.5). Lot 5.

### 4.4 Métrique d'arbitrage

Métrique principale, non ambiguë :

> **rang** = 1 + nombre de trames contendantes reçues entre la fin de GO et la fin de sa
> propre émission.

Attendu : N1 → 1, N2 → 2, N3 → 3 à chaque cycle. Le verdict porte sur l'histogramme des
rangs (« 1000/1000 cycles au rang attendu »).

Sont également produites, pour rester compatible avec le tableau 7 du dossier : `gagnés`,
`perdus` (= cycles où le nœud a perdu **au moins un** arbitrage) et `ARM reçus`. Le contrôle
de validité du dossier est conservé : **un cycle est invalide si les `ARM reçus` diffèrent
entre contendants**, ou si l'écart temporel dépasse durée de trame + intermission + tolérance.

### 4.5 Identifiants : profils réseau (Q3)

Les identifiants de service **ne sont jamais en dur** : ils sont définis par un *profil
réseau* dans `icd/bench_icd.yaml`. Les ICD partenaires les déclareront « réservés banc,
reconfigurables », et non imposés.

Profil `bench` par défaut :

| ID | Nom | Sens |
|---|---|---|
| 0x010 | `ARM` | PC → nœuds |
| 0x011 | `GO` | PC → nœuds |
| 0x012 | `BENCH_CFG` | PC → nœud |
| 0x013 | `BENCH_RESULT` | nœud → PC |
| **0x781–0x784** | `HEARTBEAT_n` (0x780 + node_id) | nœud → PC |

**Justification de 0x780 + node_id**, hors 0x700–0x77F comme demandé. En CiA 301, les
identifiants prédéfinis occupent 0x000 (NMT), 0x080 (SYNC), 0x081–0x0FF (EMCY),
0x100 (TIME), 0x181–0x57F (PDO), 0x581–0x67F (SDO), **0x701–0x77F (NMT error control,
c'est-à-dire le heartbeat CANopen)**, puis 0x7E4/0x7E5 (LSS). La plage **0x780–0x7DF est
non attribuée**. Elle offre en outre la **priorité la plus basse** du bus, ce qui est
exactement ce qu'on veut d'un heartbeat : il ne doit jamais retarder une trame applicative.
Les identifiants de service (0x010–0x013) tombent dans 0x001–0x07F, également non attribuée.

> À signaler aux groupes partenaires : les identifiants d'exemple de l'énoncé — 0x100, 0x200,
> 0x300 — correspondent respectivement à TIME, PDO1-rx et PDO2-rx en CANopen. Sans incidence
> ici (ce sont des vecteurs de test, reconfigurables par profil), mais à ne pas reprendre tels
> quels dans un ICD partenaire qui utiliserait CANopen.

Contrôles effectués par le générateur, pour **chaque** profil :

1. aucune collision d'identifiant, y compris entre trames applicatives et plage de service ;
2. aucun chevauchement de signaux à l'intérieur d'une trame ;
3. **contrainte d'ordre ARM/GO** : `ID(GO) < ID(ARM)` est faux ici — la contrainte exacte
   retenue est `ID(GO) < min(ID des contendants)` **et** `ID(ARM) < min(ID des contendants)`,
   qui garantit les deux arguments du §3.9 ;
4. tout identifiant de service hors des plages CANopen libres déclenche un avertissement.

### 4.6 Les six fonctions du dossier (§1) et leur couverture

| # | Fonction (texte du dossier) | Test |
|---|---|---|
| 1 | Validation de la couche physique (niveaux différentiels, terminaisons, débit 500 kbit/s) | T1, T2 |
| 2 | Démonstration de l'arbitrage entre au moins trois nœuds émetteurs simultanés | T3 |
| 3 | Validation de l'encodage des messages définis dans l'ICD | T4 |
| 4 | Tests de robustesse par injection de fautes | T5, T6 |
| 5 | Démonstration pédagogique à destination de l'ensemble des groupes partenaires | T3, T4 (IHM locale) |
| 6 | Validation de l'isolation galvanique | T7 (squelette) |

### 4.7 Injection de fautes : SW1 / SW2 / SW3 (dossier §4.3)

| Rep. | Faute simulée | Position nominale | Effet attendu |
|---|---|---|---|
| SW1 | Perte d'une terminaison (retire R_T2) | **fermé** | Dégradation du signal, hausse du taux d'erreur |
| SW2 | Court-circuit CAN_H / CAN_L | **ouvert** | Erreurs de bit, passage en *bus-off* |
| SW3 | Retrait à chaud du nœud N4 (DPST) | **fermé** | Le reste du bus continue de fonctionner |

Précaution reprise du dossier et à afficher par `canbench faults` : **SW2 ne doit être fermé
que brièvement** — le TJA1051T/3 limite le courant mais s'échauffe en court-circuit
prolongé. Ne jamais actionner SW2 pendant qu'un nœud isolé galvaniquement est sous tension
côté puissance.

---

## 5. Arborescence retenue

```
banc-can/
├── README.md  CHANGELOG.md  LICENSE
├── CMakeLists.txt  CMakePresets.json
├── .gitignore  .gitattributes  .gitmodules  .clang-format  .editorconfig
├── .github/workflows/ci.yml
├── icd/bench_icd.yaml  icd/schema.json
├── tools/codegen/               # YAML -> C, Python, DBC, LaTeX
├── firmware/
│   ├── common/{can_if.h,protocol,icd_gen,app,ui,sensors,util}
│   ├── ports/{g431_fdcan,f103_bxcan}/
│   ├── boards/{nucleo_g431kb,bluepill_f103}/board.h
│   ├── vendor/                  # sous-modules ST, isolés du code du projet
│   └── tests_host/
├── pc/canbench/  pc/tests/
├── scripts/                     # bit_timing.py, bus_load.py
└── docs/
    ├── references/              # PDF hors dépôt + README.md descriptif
    ├── PLAN.md  architecture.md  pinout.md  bit_timing.md
    ├── config_logicielle.md     # remplit la section 6 du dossier (\todo)
    ├── protocole_validation.md  # remplit la section 7 du dossier (\todo)
    ├── montage.md               # HW1, SB9/SB10, terminaisons, PA5/PA6 flottantes
    └── latex/
```

Les sections 5 (tableau de câblage), 6 (configuration logicielle) et 7 (protocole de
validation) du dossier sont des `\todo{}` : nos documents ont vocation à les **remplir**,
via les extraits `\input{}` de `docs/latex/`.

---

## 6. Outillage

### 6.1 Sous-modules ST — versions épinglées

| Sous-module | Tag |
|---|---|
| `STMicroelectronics/stm32g4xx_hal_driver` | `v1.2.7` |
| `STMicroelectronics/cmsis_device_g4` | `v1.2.6` |
| `STMicroelectronics/stm32f1xx_hal_driver` | `v1.1.10` |
| `STMicroelectronics/cmsis_device_f1` | `v4.3.5` |
| `STMicroelectronics/cmsis_core` | `v5.9.0_20250520` |

### 6.2 État de la machine de développement

| Outil | État |
|---|---|
| git 2.55.0 / cmake 3.29.2 / ninja 1.12.0 | OK |
| arm-none-eabi-gcc 13.3.1 / gcc 13.2.0 (MinGW-w64) | OK |
| Python 3.13.12 | OK (≥ 3.10) |
| `openocd` 0.12.0 | présent, **hors PATH** : `C:\ST\xpack-openocd-0.12.0-7\bin` |
| `STM32_Programmer_CLI` 2.2.200 | présent, **hors PATH** (plugin STM32CubeIDE 1.19.0) |
| `ruff`, `clang-format` | **absents** — `pip install ruff` |

Les cibles `flash_<node>` **cherchent** les deux exécutables (PATH puis chemins connus sous
`C:\ST\`) au lieu de les supposer dans le PATH.

### 6.3 Décisions d'outillage

- **Tests hôte C** : CMake + CTest, Unity vendorisé. Un test vérifie que `common/` ne tire
  **aucun en-tête HAL**.
- **Parité C ↔ Python de l'ICD** : le générateur exporte des **vecteurs de référence JSON**
  consommés par le test C et par le test Python — plus portable en CI que `ctypes`.
- **`.ioc` indicatif** sous `docs/`, jamais référencé par le build.
- **Licence MIT** (Q7), avec mention des licences BSD-3-Clause des sous-modules ST.
- **PDF hors dépôt** (Q6) : `docs/references/*.pdf` dans `.gitignore`, remplacés par
  `docs/references/README.md` (référence, révision, lien officiel, sections utilisées).

---

## 7. Protocole de validation — T1 à T7

| Test | Objet | Automatisé par | Nature |
|---|---|---|---|
| T1 | Couche physique : niveaux différentiels, terminaisons | — | manuel (oscillo + multimètre) |
| T2 | Débit et bit timing : temps de bit, point d'échantillonnage | — | manuel (oscilloscope) |
| T3 | Arbitrage ARM/GO | `canbench arbitration` | automatique |
| T4 | Encodage ICD | `canbench encoding` | automatique |
| T5 | Fautes physiques SW1/SW2/SW3 | `canbench faults` (guidé) | semi-auto |
| T6 | Fautes logicielles N4 | `canbench faults` | automatique |
| T7 | Isolation galvanique | — | squelette |

T1, T2 et T7 ne sont pas automatisables : `canbench` n'y fournit qu'une aide à la saisie et
la mise en forme du rapport.

---

## 8. Découpage en lots

| Lot | Contenu | État |
|---|---|---|
| 1 | Socle : ignore/attributes/clang-format, CMake racine, presets, sous-modules, CI, LICENSE, README, `docs/references/README.md` | **en cours** |
| 2 | ICD : YAML, schéma, générateur, vecteurs de référence, tests de collision/chevauchement/ordre ARM-GO | à faire |
| 3 | `firmware/common` + `tests_host` | à faire |
| 4 | `ports/g431_fdcan` + `boards/nucleo_g431kb` + horloges (HSE/HSI sélectionnable) | à faire |
| 5 | `ports/f103_bxcan` + `boards/bluepill_f103` | **bloqué** (Q4 : RM0008, DS5319, schéma) |
| 6 | IHM SSD1306 DMA + pages partielles, LEDs, capteurs + simulateurs | à faire |
| 7 | `pc/canbench` : CLI, simulateur de nœuds, `monitor`/`arbitration`/`encoding` | à faire |
| 8 | `faults`, `busload`, `record`/`replay`, `report` | à faire |
| 9 | Documentation et extraits LaTeX | à faire |
| 10 | CI complète, durcissement, récapitulatif matériel | à faire |

---

## 9. Questions ouvertes

| # | Question | État |
|---|---|---|
| Q1 | Dossier de définition | **résolu** (r2) |
| Q2 | Soudure SB9/SB10 | **en attente encadrants** — repli HSI implémenté et signalé |
| Q3 | Identifiants réservés | **résolu** — profils réseau, heartbeat 0x780+n (§4.5) |
| Q4 | RM0440, RM0008, DS12589, DS5319, ES G431, schéma Blue Pill | **en cours** — bloque le Lot 5 |
| Q5a | Modèle de transceiver | **résolu par le dossier** : TJA1051T/3 (§3.3) |
| Q5b | 120 Ω soudé sur les modules ? | **ouvert** — champ resté entre crochets (§3.7) |
| Q5c | Retrait du 120 Ω : sur 4 nœuds et non 3 ? | **ouvert** — voir §3.7 |
| Q6 | PDF hors dépôt | **résolu** |
| Q7 | Licence MIT | **résolu** (sous réserve encadrants) |

---

## 10. Récapitulatif des `TODO(verif)`

| # | Élément | Source à consulter | Bloque |
|---|---|---|---|
| V1 | FDCAN1_RX/TX = PA11/PA12, AF9 | DS12589, table des fonctions alternées | Lot 4 |
| V2 | Mécanisme `nSWBOOT0`/`nBOOT0` sur PB8 | RM0440 § option bytes | doc |
| V3 | Contraintes PLL G4 (M, N, Q, R, plages VCO) | RM0440 § RCC | Lot 4 |
| V4 | Précision HSI16 (±1 %) | DS12589 § caractéristiques d'horloge | doc |
| V5 | Brochage Blue Pill + remap bxCAN PB8/PB9 | RM0008 + DS5319 + schéma carte | **Lot 5** |
| V6 | Pull-up USB sur PA12 de la Blue Pill, clones F103 | schéma carte | Lot 5 |
| V7 | Horodatage matériel du firmware candleLight | doc candleLight / gs_usb | Lot 7 |
| V8 | Tolérance du MCO ST-LINK (option B, §3.2) | UM2448 | si option B |
| V9 | Présence/valeur des terminaisons sur les modules | inspection visuelle | T1, Q5b |
| V10 | Errata G431 (ES) : anomalies FDCAN éventuelles | ES G431 | Lot 4 |
