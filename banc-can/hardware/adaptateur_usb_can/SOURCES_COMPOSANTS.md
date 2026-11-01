# Adaptateur USB-CAN G69 : sources et vérifications par composant

Ce document indique, pour chaque composant de l'adaptateur, les informations utilisées dans
le schéma et le PCB, et d'où elles viennent : datasheet (page, figure ou tableau),
bibliothèque KiCad 9.0.7, documentation du banc CAN ou source secondaire.

Statut de chaque information :

- ✅ **vérifiée** dans la datasheet officielle jointe au dossier ;
- ⚠️ **à confirmer** : point qui dépend du composant réellement acheté ou d'un accord de
  la factory ;
- ℹ️ **choix de conception** : valeur choisie, pas tirée d'une datasheet.

Les datasheets jointes sont dans le dossier `datasheets/` du .zip :

| Fichier | Document |
|---|---|
| `STM32G431_DS12589_Rev6.pdf` | ST DS12589 Rev 6, datasheet du STM32G431x6/x8/xB |
| `ST_AN2606_bootloader.pdf` | ST AN2606 Rev 70, chargeur intégré des STM32 (STM32G431 : §52) |
| `WCH_CH340DS1.pdf` | WCH CH340DS1 version 3D, datasheet de la famille CH340 |
| `NXP_TJA1051_Rev02.pdf` | NXP TJA1051 Rev 02, transceiver CAN haute vitesse |
| `AMS_AMS1117.pdf` | Advanced Monolithic Systems AMS1117, régulateur LDO 1 A |
| `ST_USBLC6-2.pdf` | ST DS4260 Rev 7, protection ESD USBLC6-2 |
| `OST_USB-B1HSxx.pdf` | On Shore Technology USB-B1HSxx, embase USB-B |
| `Bourns_MF-NSMF.pdf` | Bourns MF-NSMF, fusibles réarmables 1206 |
| `Omron_B3F.pdf` | Omron B3F, boutons tactiles 6 × 6 mm |

Le registre FLASH_OPTR cité pour le STM32 vient du manuel de référence ST RM0440 Rev 9, présent
dans le dépôt (`banc-can/docs/references/RM0440.pdf`) mais non joint (2 140 pages).

---

## Contexte et choix d'architecture

| Information | Valeur | Source |
|---|---|---|
| Règles de fabrication | 2 couches, piste ≥ 0,4 mm conseillée (0,3 mm minimum), isolation ≥ 0,3 mm, perçages de 0,4 à 2 mm par pas de 0,2 mm, trous de fixation 3,2 mm, cuivre nu | *PCB @ Factory, Design Guidelines* (ENSEA), joint ; fichier DRC `20260112_ENSEA_2_layers_drc.kicad_pro` |
| Le CANable 2.0 (STM32G431 en LQFP48, pas de 0,5 mm) ne passe pas à la factory | écart de 0,20 mm entre pastilles, sous les 0,3 mm d'isolation | empreinte KiCad `LQFP-48_7x7mm_P0.5mm` : pastilles de 0,3 mm au pas de 0,5 mm |
| Choix du LQFP32 (pas de 0,8 mm) | écart de 0,30 mm entre pastilles, pile à la limite factory | DS12589 Fig. 44 p.165 (pastilles de 0,50 mm au pas de 0,80 mm) ✅ |
| En LQFP32, FDCAN1_TX n'existe que sur PA12, qui porte aussi USB_DP : l'USB natif et le CAN ne peuvent pas fonctionner ensemble | d'où le pont USB-série CH340C et le protocole slcan | DS12589 Table 12–13 (FDCAN1_TX sur PA12, PB9 ou PD1) et Fig. 6 p.44 (ni PB9 ni PD1 en boîtier 32) ✅ |
| Brochage du DB9 | 2 = CAN_L, 3 = GND, 7 = CAN_H (CiA 303-1), identique à J1–J5 du banc | `banc-can/docs/pinout.md` §7 (dossier du banc) |

---

## U1 — STM32G431KBT6 (microcontrôleur, LQFP32)

Datasheet : **ST DS12589 Rev 6**, fichier `STM32G431_DS12589_Rev6.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage du LQFP32 | 1 VDD, 2 PF0-OSC_IN, 3 PF1-OSC_OUT, 4 PG10-NRST, 5–12 PA0–PA7, 13 PB0, 14 VSSA, 15 VDDA, 16 VSS, 17 VDD, 18–25 PA8–PA15, 26–30 PB3–PB7, 31 PB8-BOOT0, 32 VSS | Fig. 6 p.44 | ✅ |
| USART2 vers le CH340C | PA2 = USART2_TX (AF7), PA3 = USART2_RX (AF7) | Table 13 p.61 | ✅ |
| FDCAN1 vers le TJA1051 | PA11 = FDCAN1_RX (AF9), PA12 = FDCAN1_TX (AF9) | Table 13 p.61 | ✅ |
| Débogage SWD | PA13 = SWDIO, PA14 = SWCLK (AF0) | Table 13 p.61 | ✅ |
| Tension d'alimentation | VDD de 1,71 à 3,6 V : le 3,3 V convient | Table 17 *General operating conditions* p.71 | ✅ |
| Découplage VDD | n × 100 nF + 1 × 4,7 µF → C5, C6 (100 nF) et C9 (4,7 µF) | Fig. 16 *Power supply scheme* p.68 | ✅ |
| Découplage VDDA | 10 nF + 1 µF → C7 (10 nF) et C8 (1 µF) | Fig. 16 p.68 | ✅ (corrigé : C7 valait 100 nF) |
| Placement des découplages | au plus près des broches, ou sous elles en face arrière | Fig. 16 p.68, *Caution* | ✅ |
| Quartz HSE | 4 à 48 MHz, 8 MHz typique : Y1 = 8 MHz | Table 40 p.100 | ✅ |
| Condensateur sur NRST | 0,1 µF au plus près de la broche → C12 = 100 nF | Fig. 27 p.117 | ✅ |
| Empreinte du LQFP32 | pastilles de 0,50 mm au pas de 0,80 mm (écart 0,30 mm). L'empreinte KiCad `LQFP-32_7x7mm_P0.8mm` a la même largeur et des pastilles plus longues : 1,5 mm contre 1,2 mm, ce qui facilite la soudure à la main | Fig. 44 p.165 | ✅ |
| Chargeur intégré sur USART2 (PA2 = TX, PA3 = RX ; 8 bits, parité paire, 1 stop) | programmation par le CH340 sans sonde | **ST AN2606 Rev 70**, Table 115 p.274 | ✅ |
| Lancement du chargeur | Pattern 15 : BOOT0 (broche) = 1, nBOOT1 = 1, nSWBOOT0 = 1 → bouton SW2 maintenu pendant RESET | AN2606 Table 2 p.34 ; RM0440 Rev 9 Table 5 p.91 | ✅ ; la valeur d'usine des octets d'option n'est pas donnée explicitement (FLASH_OPTR = 0xFXXX XXXX), à lire avec STM32CubeProgrammer au premier branchement |

## U2 — CH340C (pont USB-UART, SOIC-16)

Datasheet : **WCH CH340DS1, version 3D**, fichier `WCH_CH340DS1.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Boîtier | SOP-16 3,9 mm au pas de 1,27 mm → empreinte `SOIC-16_3.9x9.9mm_P1.27mm` | §3 *Package*, p.2 | ✅ |
| Brochage du SOP-16 | 1 GND, 2 TXD, 3 RXD, 4 V3, 5 UD+, 6 UD−, 7 NC, 8 OUT#, 9 CTS#, 10 DSR#, 11 RI#, 12 DCD#, 13 DTR#, 14 RTS#, 15 R232, 16 VCC | §4 *Pin*, p.3–4 (colonne SOP16) | ✅ |
| Broche 7 | CH340C : broche vide, à laisser en l'air → croix de non-connexion | §4 p.3 | ✅ |
| Broche 8 | OUT#, sortie MODEM ; se change en second DTR# si on ajoute une résistance de 4,7 kΩ à la masse → laissée non connectée | §4 p.3 et §5.3 p.7 | ✅ (la bibliothèque KiCad l'appelle « NC ») |
| Broche 15 (R232) | rappel interne au niveau bas → peut rester en l'air | §4 p.4 | ✅ |
| Fonctionnement en 3,3 V | V3 relié à VCC, alimentés en 3,3 V (R2 = 0 Ω). VCC de 3,1 à 3,6 V | §4 p.3 (ligne V3) ; §6.3 p.9 | ✅ |
| Pas de quartz externe | CH340C : horloge interne | §2 *Features*, p.1 | ✅ |
| Pas de résistance série sur UD+/UD− | « Connect directly to the D+/D- data line … without a series resistor » | §4 p.3 | ✅ |
| Découplage de VCC | 0,1 µF obligatoire → C3 = 100 nF. C4 sur V3 est facultatif en mode 3,3 V | §4 p.3 (ligne VCC) | ✅ |
| Débit UART | de 50 bit/s à 2 Mbit/s | §2 p.1 | ✅ |
| Consommation | 12 mA maximum | §6.2–6.3 p.8–9 | ✅ |

## U3 — TJA1051T/3 (transceiver CAN, SOIC-8)

Datasheet : **NXP TJA1051 Rev 02 (1er juillet 2009)**, fichier `NXP_TJA1051_Rev02.pdf`. C'est la version déjà présente
dans le dépôt du banc ; la révision la plus récente chez NXP n'a pas été comparée.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage | 1 TXD, 2 GND, 3 VCC, 4 RXD, 5 VIO (version /3), 6 CANL, 7 CANH, 8 S | Table 2 p.3 | ✅ |
| VCC | 4,5 à 5,5 V : alimenté par le 5 V de l'USB | Table 6 *Static characteristics* p.7 | ✅ |
| VIO | 2,8 à 5,5 V : niveaux logiques en 3,3 V, compatibles avec le STM32 | p.7 | ✅ |
| Broche S | niveau haut = mode silencieux ; rappel interne au niveau bas. R6 (10 kΩ) le double, et PA4 la commande | §6.2.2 p.5 | ✅ |
| Rappel interne de TXD | tiré vers VIO : récessif tant que le MCU ne pilote pas | §6.2.2 p.5 | ✅ |
| Marge sur VCC | USB au pire 4,75 V, moins au plus 0,05 V de chute dans F1 → 4,70 V ≥ 4,5 V | calcul à partir de la Table 6 (TJA1051) et de la fiche Bourns (F1) | ✅ |

## U4 — AMS1117-3.3 (régulateur 3,3 V, SOT-223)

Datasheet : **Advanced Monolithic Systems AMS1117**, fichier `AMS_AMS1117.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage du SOT-223 | 1 GND/ADJ, 2 VOUT, 3 VIN, languette = VOUT → empreinte KiCad `SOT-223-3_TabPin2` | *Pin connections* p.1 | ✅ |
| Tension d'entrée maximale | 15 V (5 V utilisé) | *Absolute maximum ratings* p.2 | ✅ |
| Chute de tension | 1,3 V maximum à 0,8 A ; à environ 50 mA, l'entrée au pire de 4,70 V laisse de la marge | *Electrical characteristics* p.2–3 | ✅ |
| Condensateur de sortie | **22 µF au tantale solide** pour la stabilité → C2 = 22 µF tantale, boîtier A | *Stability*, p.4 | ✅ (corrigé : C2 était en céramique) |
| Courant de charge minimal | 10 mA ; la carte consomme plus (MCU, CH340, LED) | *Minimum load*, p.3 et note 5 | ✅ |

## U5 — USBLC6-2SC6 (protection ESD de l'USB, SOT-23-6)

Datasheet : **ST DS4260 Rev 7 (décembre 2021)**, fichier `ST_USBLC6-2.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage | 1 I/O1, 2 GND, 3 I/O2, 4 I/O2, 5 VBUS, 6 I/O1 (vue de dessus) | *Functional diagram*, p.1 | ✅ |
| Câblage | D+ sur I/O1, D− sur I/O2, VBUS sur le 5 V après le fusible | Fig. 13 *USB 2.0 port application diagram*, p.9 | ✅ |
| Tenue sur VBUS | VRM = 5,25 V (condition de mesure de la fuite) : compatible avec le 5 V de l'USB | Table *Electrical characteristics*, p.2 | ✅ |

## J1 — Embase USB type B, OST USB-B1HSxx (traversante, coudée)

Datasheet : **On Shore Technology USB-B1HSxx** (rév. A, 2012), fichier `OST_USB-B1HSxx.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Implantation conseillée | broches 1 à 4 sur une grille de 2,50 × 2,00 mm, Ø 0,92 ± 0,08 mm ; 2 pattes de blindage Ø 2,33 ± 0,08 mm espacées de 12,04 mm, à 2,71 mm de la rangée de broches | *Recommended P.C. Board Layout* | ✅ identique à l'empreinte KiCad `USB_B_OST_USB-B1HSxx_Horizontal` |
| Valeurs nominales | 1 A, 30 V AC | *Ratings* | ✅ |
| Brochage USB | 1 VBUS, 2 D−, 3 D+, 4 GND | numérotation de la vue de face (plan OST) ; affectation selon la norme USB 2.0 | ✅ |
| Perçages de 2,33 mm | hors de la série factory (0,4 à 2 mm) | guide factory | ⚠️ à valider avec la factory |

## F1 — Fusible réarmable 500 mA, Bourns MF-NSMF050 (1206)

Datasheet : **Bourns MF-NSMF series**, fichier `Bourns_MF-NSMF.pdf`. La nomenclature indique
seulement « PTC 500 mA 1206 » : la référence Bourns sert à justifier les valeurs, toute
référence équivalente du magasin convient.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Courant maintenu et de déclenchement | Ihold 0,50 A, Itrip 1,00 A à 23 °C | tableau p.1, ligne MF-NSMF050 | ✅ |
| Tension maximale | 13,2 V | idem | ✅ |
| Résistance | 0,15 Ω (Rmin) à 0,70 Ω (R1max) → chute ≤ 0,05 V à environ 70 mA | idem | ✅ |
| Boîtier | 1206 standard → empreinte `Fuse_1206_3216Metric_Pad1.42x1.75mm_HandSolder` | p.1 | ✅ |

## SW1, SW2 — Boutons poussoirs 6 × 6 mm traversants (type Omron B3F-1000)

Datasheet : **Omron B3F**, fichier `Omron_B3F.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Implantation | 4 trous Ø 1,0 ± 0,1 mm, entraxe de 6,5 × 4,5 mm → empreinte KiCad `SW_PUSH_6mm` (perçage de 1,1 mm, arrondi à 1,2 mm par la factory) | *PCB Mounting Holes*, p.4 | ✅ |

## Y1 — Quartz 8 MHz HC-49/U, avec C10 et C11 (22 pF)

Aucune référence précise n'est imposée : prendre le quartz 8 MHz HC-49 disponible au magasin.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Fréquence | 8 MHz, dans la plage de 4 à 48 MHz du HSE | DS12589 Table 40 p.100 | ✅ |
| Quartz indépendant des Nucleo (24 MHz) | sert de référence d'horloge à l'étape 6 bis du bring-up | `banc-can/docs/bringup.md` | ℹ️ |
| Empreinte | HC-49/U vertical, entraxe 4,88 mm | bibliothèque KiCad (`Crystal_HC49-U_Vertical`) | ℹ️ |
| C10 = C11 = 22 pF | capacité de charge obtenue ≈ 22/2 + environ 5 pF parasites ≈ 16 pF. À ajuster selon la CL du quartz reçu : C ≈ 2 × (CL − 5 pF) | règle usuelle (ST AN2867, non jointe) | ⚠️ à recalculer avec la CL réelle |

## J2 — Embase SUB-D 9 points mâle coudée, pour CI

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage | 2 CAN_L, 3 GND, 7 CAN_H ; les autres broches non connectées | CiA 303-1, repris dans `banc-can/docs/pinout.md` §7 | ✅ (document du banc) |
| Empreinte | DE-9 standard : pas de 2,77 × 2,84 mm, fixations espacées de 25 mm | bibliothèque KiCad (`DSUB-9_Pins_Horizontal_…`) ; le lien vers la datasheet Tonar de KiCad est mort | ℹ️ à comparer avec l'embase reçue |
| Genre | mâle, côté appareil comme le veut la CiA | CiA 303-1 | ℹ️ à confirmer avec les câbles du banc |

## R7 + JP1 — Terminaison 120 Ω commutable

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| 120 Ω à chaque extrémité du bus | JP1 fermé si l'adaptateur est en bout de bus | ISO 11898-2 ; `banc-can/docs/pinout.md` §7 (« deux terminaisons exactement ») | ✅ (document du banc) |

## Composants passifs génériques (R, C, LED, barrettes)

| Repère | Valeur | Justification | Statut |
|---|---|---|---|
| C1 | 10 µF céramique | réservoir d'entrée du régulateur | ℹ️ |
| C3, C4 | 100 nF | découplage du CH340C | ℹ️ (voir U2) |
| C13, C14 | 100 nF | découplage de VCC et VIO du TJA1051 | ℹ️ pratique courante |
| R1, R4, R5 + D1–D3 | 1 kΩ, LED 1206 | I ≈ (3,3 − 2,0) / 1000 ≈ 1,3 mA, en supposant Vf ≈ 2 V | ℹ️ |
| R3 | 10 kΩ | rappel de BOOT0 à la masse : démarrage sur la flash | ℹ️ |
| R6 | 10 kΩ | S au niveau bas, mode normal (double le rappel interne) | ℹ️ |
| J3 | barrette 1 × 5 au pas de 2,54 mm | SWD : 3V3, SWCLK, GND, SWDIO, NRST | ℹ️ |
| Toutes les empreintes CMS passives | 1206 HandSolder | conseil du guide factory pour la soudure à la main | ✅ guide factory |

---

## Vérifications globales faites sur le projet KiCad

| Vérification | Résultat | Outil |
|---|---|---|
| ERC du schéma | 0 violation | `kicad-cli sch erc` (KiCad 9.0.7), rapport joint |
| DRC avec les règles ENSEA, et cohérence avec le schéma | 0 erreur, 0 liaison manquante ; 7 avertissements de sérigraphie, dus à l'USB-B et au DB9 qui dépassent volontairement du bord | `kicad-cli pcb drc --schematic-parity`, rapport joint |
| Routage | 2 couches, pistes de 0,4 mm, vias de 0,8/0,4 mm, plan de masse en face arrière | Freerouting 2.5.0, rétrécissement des pistes (« neckdown ») désactivé |

## Points restant à confirmer (⚠️ ou ℹ️)

1. **Quartz** : relever la CL du quartz reçu et recalculer C10/C11.
2. **Perçages de 2,33 mm** (USB-B) : à faire accepter par la factory.
3. **Octets d'option du STM32** (nSWBOOT0, nBOOT1) : les lire au premier branchement. Si la
   broche BOOT0 n'est pas prise en compte, programmer par le connecteur SWD J3.
4. **Embase DB9** : comparer les dimensions de l'embase achetée avec l'empreinte (pas de
   2,77 × 2,84 mm, fixations espacées de 25 mm).
