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
| `OST_USB-B1HSxx.pdf` | On Shore Technology USB-B1HSxx, embase USB-B (version 0.1 ; la version 0.2 passe à une fiche USB-A mâle CNCTech, datasheet non jointe) |
| `Bourns_MF-NSMF.pdf` | Bourns MF-NSMF, fusibles réarmables 1206 |
| `Omron_B3F.pdf` | Omron B3F, boutons tactiles 6 × 6 mm (version 0.1 ; la version 0.2 passe aux boutons CMS Omron B3U, datasheet non jointe) |

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
| Connecteur de bus : bornier à vis plutôt que DB9 | le bus du banc est câblé en fils nus, vissés sur les borniers de l'USBCAN-Z et des CAN Pal ; même ordre H, L, G que l'USBCAN-Z | marquage du boîtier de l'USBCAN-Z ; `banc-can/hardware/cablage_bus_can/` |

---

## U1 — STM32G431KBT6 (microcontrôleur, LQFP32)

Datasheet : **ST DS12589 Rev 6**, fichier `STM32G431_DS12589_Rev6.pdf`.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage du LQFP32 | 1 VDD, 2 PF0-OSC_IN, 3 PF1-OSC_OUT, 4 PG10-NRST, 5–12 PA0–PA7, 13 PB0, 14 VSSA, 15 VDDA, 16 VSS, 17 VDD, 18–25 PA8–PA15, 26–30 PB3–PB7, 31 PB8-BOOT0, 32 VSS | Fig. 6 p.44 | ✅ |
| USART2 vers le CH340C | PA2 = USART2_TX (AF7), PA3 = USART2_RX (AF7) | Table 13 p.61 | ✅ |
| FDCAN1 vers le TJA1051 | PA11 = FDCAN1_RX (AF9), PA12 = FDCAN1_TX (AF9) | Table 13 p.61 | ✅ |
| Débogage SWD | PA13 = SWDIO, PA14 = SWCLK (AF0) | Table 13 p.61 | ✅ |
| LED d'erreur | PA8 (broche 18) en sortie GPIO vers R8 et D4 : broche libre, ni broche de démarrage (BOOT0 = PB8) ni broche SWD/JTAG (PA13 à PA15, PB3, PB4) | Fig. 6 p.44 | ✅ pour le brochage ; ℹ️ choix de la broche |
| Tension d'alimentation | VDD de 1,71 à 3,6 V : le 3,3 V convient | Table 17 *General operating conditions* p.71 | ✅ |
| Découplage VDD | n × 100 nF + 1 × 4,7 µF → C5, C6 (100 nF) et C9 (4,7 µF) | Fig. 16 *Power supply scheme* p.68 | ✅ |
| Découplage VDDA | 10 nF + 1 µF → C7 (10 nF) et C8 (1 µF) | Fig. 16 p.68 | ✅ (corrigé : C7 valait 100 nF) |
| Placement des découplages | au plus près des broches, ou sous elles en face arrière : C5 sous la broche 1 (1,1 mm), C6 à 2,6 mm de la broche 17, C7 à 2,7 mm de la broche 15, chacun avec un via de masse à moins de 1,5 mm de sa pastille GND. Le LQFP32 n'a ni VREF+ ni VBAT : rien d'autre à découpler | Fig. 16 p.68, *Caution* ; Fig. 6 p.44 ; mesures de `verifier_criteres.py` | ✅ |
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
| Câblage | D+ sur I/O1 (broches 1 et 6), D− sur I/O2 (3 et 4), VBUS (5) sur le VBUS de la fiche, avant le fusible | Fig. 13 *USB 2.0 port application diagram*, p.9 | ✅ |
| Tenue sur VBUS | VRM = 5,25 V (condition de mesure de la fuite) : compatible avec le 5 V de l'USB | Table *Electrical characteristics*, p.2 | ✅ |
| Implantation | en face arrière, sous les pastilles de J1, traversée en ligne : rangée D+ au nord, rangée D− au sud, masse (2) à l'est reliée au plan sous l'axe de la paire, VBUS (5) à l'ouest. Un via dans chaque pastille de données (J1.3 / U5.1 et J1.2 / U5.3), symétriques ; aucun via ni cuivre sous le corps de la fiche, aucune piste de la face arrière sous la paire | `generate_pcb.py`, `router_manuel.py` | ℹ️ |

## J1 — Fiche USB type A mâle, CNCTech 1001-011-01101 (coudée, format clé)

L'adaptateur se branche directement sur un port USB du PC, sans câble. Une embase A femelle
n'est pas possible sur un périphérique : elle obligerait à un câble A-A, hors norme, qui relie
deux sorties 5 V.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Empreinte | 4 pastilles CMS de 2,5 × 1,1 mm (pas de 2,5 et 2,0 mm), 2 trous de centrage, 2 pattes de blindage traversantes ; repère « PCB Edge » sur le bord de la carte, la fiche dépasse de 14,7 mm | bibliothèque KiCad (`Connector_USB:USB_A_CNCTech_1001-011-01101_Horizontal`), copiée dans la bibliothèque locale `adaptateur_usb_can.pretty` avec les perçages ci-dessous | ℹ️ à comparer avec la datasheet CNCTech (non jointe) |
| Brochage USB | 1 VBUS, 2 D−, 3 D+, 4 GND | norme USB 2.0 | ✅ |
| Perçages | trous de centrage : 1,2 mm (1,1 mm dans la bibliothèque) ; fentes des pattes de blindage : 2,5 × 1,0 mm (2,5 × 0,9 mm dans la bibliothèque), à faire avec l'outil de 1,0 mm | guide factory (perçages de 0,4 à 2,0 mm par pas de 0,2 mm, arrondis à la taille supérieure) | ⚠️ le guide ne cite que des perçages ronds : faire accepter les deux fentes par la factory (sinon trous ronds et pattes repliées) |

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

## SW1, SW2 — Boutons poussoirs CMS 3 × 2,5 mm (Omron B3U-1000P)

Les boutons traversants 6 × 6 mm de la version 0.1 ne tenaient pas sur la carte 60 × 30 mm.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Empreinte | 2 pastilles de 0,9 × 1,7 mm à 3,4 mm d'entraxe, boîtier 3 × 2,5 mm | bibliothèque KiCad (`Button_Switch_SMD:SW_SPST_B3U-1000P`) | ℹ️ à comparer avec la datasheet Omron B3U (non jointe) et avec le bouton acheté |

## Y1 — Quartz 8 MHz CMS 5 × 3,2 mm, avec C10 et C11 (22 pF)

Aucune référence précise n'est imposée : prendre un quartz 8 MHz en boîtier 5032 à deux
pastilles. Le HC-49 de la version 0.1 (12 mm de long) ne tenait pas sur la carte.

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Fréquence | 8 MHz, dans la plage de 4 à 48 MHz du HSE | DS12589 Table 40 p.100 | ✅ |
| Quartz indépendant des Nucleo (24 MHz) | sert de référence d'horloge à l'étape 6 bis du bring-up | `banc-can/docs/bringup.md` | ℹ️ |
| Empreinte | boîtier 5 × 3,2 mm, 2 pastilles allongées de 0,6 mm vers l'extérieur (2,6 × 2,4 mm) : 0,95 mm de pastille visible à chaque bout du boîtier au lieu de 0,35 mm, pour le fer | bibliothèque KiCad (`Crystal_SMD_5032-2Pin_5.0x3.2mm`), retouchée dans la bibliothèque locale `adaptateur_usb_can.pretty` (la variante « HandSoldering » de KiCad, 1,85 mm visible, ne tient pas entre C10 et C11) | ℹ️ |
| Implantation | quartz vertical en face des broches 2 et 3 (PF0, PF1), C10 au-dessus, C11 en dessous ; pistes OSC_IN 4,2 mm et OSC_OUT 3,8 mm, sans via (de centre à centre, broche → pastille du quartz → condensateur : 6,7 et 6,2 mm) ; aucune piste ni composant sous le quartz en face arrière (plan de masse plein) ; anneau de garde : côté ouest il réunit les masses de C10 et C11, côté est il sépare le quartz du tronc +3V3 puis, par un pavé de masse, C11 de NRST ; il rejoint le plan par un seul via, à 2,85 mm de la broche 32 (VSS). Retour de masse par l'anneau jusqu'à ce via : 6,5 mm pour C10, 22,6 mm pour C11 | règles de ST AN2867 §5.1 (non jointe) ; mesures de `verifier_criteres.py` | ℹ️ NRST (broche 4, voisine de PF1) longe la pastille sud du quartz à 0,40 mm sur 3,6 mm, sans place pour une garde (1,5 mm entre cette pastille et les broches de U1) : ligne statique, filtrée par C12 (100 nF). UART_TX reste à 1,3 mm |
| C10 = C11 = 22 pF | capacité de charge obtenue ≈ 22/2 + environ 5 pF parasites ≈ 16 pF. À ajuster selon la CL du quartz reçu : C ≈ 2 × (CL − 5 pF) | règle usuelle (ST AN2867, non jointe) | ⚠️ à recalculer avec la CL réelle |

## J2 — Bornier à vis 3 points, pas de 5,08 mm, pour CI

| Information utilisée | Valeur | Source | Statut |
|---|---|---|---|
| Brochage | 1 GND, 2 CAN_L, 3 CAN_H ; sur la carte, de haut en bas : H, L, G, repérés en sérigraphie | schéma de l'adaptateur ; ordre du bornier de l'USBCAN-Z | ✅ |
| Empreinte | Phoenix MKDS 1,5/3-5,08 : 3 broches au pas de 5,08 mm, boîtier 15,2 × 9,8 mm, entrée des fils côté bord de carte ; perçages de 1,4 mm (1,3 mm dans la bibliothèque, hors du pas de la factory) | bibliothèque KiCad (`TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal`), copiée dans la bibliothèque locale `adaptateur_usb_can.pretty` | ℹ️ |
| Courant | quelques dizaines de mA sur le bus, négligeable pour un bornier de puissance | — | ✅ |

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
| R1, R4, R5 + D1–D3 | 1 kΩ, LED 0805 | I ≈ (3,3 − 2,0) / 1000 ≈ 1,3 mA, en supposant Vf ≈ 2 V. LED RX sur PA7 (broche 12), LED TX sur PB0 (broche 13) : des broches du bas du STM32, à côté des LED | ℹ️ |
| R8 + D4 | 1 kΩ, LED rouge 0805 (Würth 150080RS75000 ou équivalente) | LED d'erreur, même montage que D2 et D3 (sortie du MCU, résistance, LED, masse) sur PA8 (broche 18). Placée dans la rangée des LED, à 4,8 mm de D3. Le capot du boîtier v0.2 n'a pas de trou au-dessus d'elle | ℹ️ |
| R3 | 10 kΩ | rappel de BOOT0 à la masse : démarrage sur la flash | ℹ️ |
| R6 | 10 kΩ | S au niveau bas, mode normal (double le rappel interne) | ℹ️ |
| J3 | barrette 1 × 4 au pas de 2,54 mm | SWD : 1 SWCLK, 2 SWDIO, 3 GND, 4 3V3, dans l'ordre des broches du STM32. NRST n'y est pas : la programmation SWD normale s'en passe, et le bouton RESET reste disponible | ℹ️ |
| Toutes les empreintes CMS passives | 0805 HandSolder (fusible F1 en 1206) | le guide factory conseille « 0805 ou 1206 » avec l'option HandSolder | ✅ guide factory |

---

## Vérifications globales faites sur le projet KiCad

| Vérification | Résultat | Outil |
|---|---|---|
| ERC du schéma | 0 violation | `kicad-cli sch erc` (KiCad 9.0.7), rapport joint |
| DRC avec les règles ENSEA, et cohérence avec le schéma | 0 erreur, 0 avertissement, 0 liaison manquante, parité 0 | `kicad-cli pcb drc --schematic-parity --severity-all`, rapport joint |
| Carte | 60 × 30 mm, sans trou de fixation ; composants sur les deux faces : connecteurs, STM32, CH340C, quartz, boutons, LED et leurs résistances dessus ; régulateur, protection USB, transceiver et découplages dessous | `generate_pcb.py`, contrôlé par `verif_placement.py` |
| Empreintes retouchées | bibliothèque locale `adaptateur_usb_can.pretty` (+ `fp-lib-table`), recréée par `generate_pcb.py` : quartz à pastilles allongées, fiche USB et bornier aux perçages de la factory, sérigraphie coupée au bord de carte | `generate_pcb.py` (`EMPREINTES_LOCALES`) |
| Version | 0.3 : cartouches du schéma et de la carte, texte « G69 v0.3 » en sérigraphie. Le boîtier imprimé porte encore « v0.2 » (`boitier/`, non modifié) | `generate_schematic.py`, `generate_pcb.py` (`VERSION`) |
| Routage | 2 couches, pistes de 0,4 à 0,6 mm, vias de 0,8/0,4 mm. Routage en face avant (455 mm) ; la face arrière ne porte que des ponts courts (114 mm, le plus long segment 4,8 mm) et son plan de masse est d'un seul tenant. 53 vias de masse : un contre chaque découplage, un de chaque côté de la paire CAN, puis une couture sur une grille de 8 mm (`../poser_vias_couture.py`). Perçages : 0,4 mm (vias), 1,0 mm (fentes de J1), 1,2 mm (pions de J1), 1,4 mm (bornier), tous au pas de la factory | `router_manuel.py` : pistes, vias et repères de sérigraphie posés par tables et par calcul, résultat identique à chaque exécution. `route_freerouting.py` et `../elaguer_vias.py` (version 0.2) ne servent plus |

## Reprise après les remarques d'électronique

Mesures faites par `verifier_criteres.py` sur la carte routée (il les refait à chaque exécution :
30 critères, tous tenus).

| Remarque | Ce qui a été fait | Mesure |
|---|---|---|
| R1 — vias de masse | un via contre la pastille GND de chaque condensateur de découplage, un de chaque côté de la paire CAN, puis couture sur une grille de 8 mm | 53 vias GND ; point le plus éloigné d'un via : 6,7 mm ; via à 1,41 mm au pire du centre de la pastille GND d'un découplage (C3 et C13 : via dans la pastille) |
| R2 — découplage du STM32 | C5, C6, C7 contre leur broche, en face arrière ; via de masse à côté de chacun | C5 → broche 1 : 1,11 mm ; C6 → broche 17 : 2,55 mm ; C7 → broche 15 : 2,73 mm (centre à centre). Le LQFP32 n'a ni VREF+ ni VBAT ; VDDA garde 10 nF + 1 µF (DS12589 Fig. 16) |
| R3 — quartz (ST AN2867) | Y1, C10 et C11 en face des broches 2 et 3 ; anneau de garde prolongé entre C11 et NRST ; face arrière dégagée | OSC_IN 4,22 mm, OSC_OUT 3,78 mm, sans via ; aucune piste dessous ni autre signal dans la cellule gardée ; plan B.Cu plein à 97 % sous le quartz ; îlot relié au plan par un seul via, à 2,85 mm de la broche 32. Reste : NRST à 0,40 mm de la pastille sud du quartz sur 3,6 mm ; retour de masse de C11 de 22,6 mm par l'anneau (point de liaison unique, côté broche 32) |
| R4 — plan de masse du dessous | routage ramené en face avant ; UART sans via par le canal sous le CH340C ; C3 alimenté en face avant ; protection USB sous les pastilles de la fiche | 114 mm de pistes sur B.Cu (388 mm avant), plus long segment 4,8 mm ; zone GND B.Cu en 1 morceau (13 avant) ; plan plein à 93 % sous U1, à 87 % sous la paire USB et, en face avant, à 94 % en face de la paire CAN (hors pastilles d'extrémité). Trois grappes de composants gardent un trou de plus de 12 mm dans le plan : fiche USB (6,9 × 12,6 mm), régulateur et V3 du CH340C (13,7 × 14,1 mm), transceiver et bornier (12,5 × 19,2 mm) |
| R5 — paires | CANH/CANL côte à côte (0,7 mm d'entraxe) de U3 jusqu'entre les bornes H et L ; USB D+/D− resserrées à 0,7 mm dès la sortie des pastilles de J1 jusqu'aux broches de U2 ; CAN_S contourne le bornier pour ne pas couper le plan en face de la paire CAN | écart de longueur : CAN 0,51 mm, USB 0,24 mm. Part de la longueur à 1,0 mm d'entraxe ou moins, hors pastilles d'extrémité : CAN 84 %, USB 92 % (64 % et 64 % pastilles comprises : les broches de U3 sont au pas de 1,27 mm, les bornes de J2 à 5,08 mm, les pastilles de J1 à 2,0 mm) |
| R6 — LED d'erreur | D4 rouge 0805 + R8 1 kΩ sur PA8 (broche 18) | au schéma, sur la carte, dans la nomenclature |
| R7 — TJA1051 près du bornier | U3 reste sous le bornier, décalé de 1 mm vers l'ouest | pastilles de U3 à 2,01 mm de celles de J2 (1,0 mm avant) |

**Ce qui n'a pas pu être corrigé** :

- Trous du plan de masse de la face arrière : la grappe du régulateur (U4, C1, C2, puis R2 et C4 par la
  liaison V3 du CH340C) et celle du transceiver (U3, ses découplages, R7, bornes H et L) restent d'un
  seul tenant. Les séparer demande de passer le régulateur en face avant ou de sortir U3 de sous le
  bornier, donc de refaire le placement et le boîtier.
- Le pont +3V3 de la face arrière entre J3 et C6 (3,6 mm) reste : en face avant, CAN_RX, CAN_TX et
  LED_ERR passent entre J3 et le STM32 et barrent le chemin.
- NRST à côté du quartz et retour de masse long de C11 : voir la ligne R3.

**Ordre de soudure** : face arrière d'abord (U3, U4, U5, F1, condensateurs et résistances), puis
la face avant en CMS, et en dernier les traversants J2, J3 et JP1. Dans cet ordre :

1. U3, R7 et C13 avant le bornier J2 : une fois J2 soudé, ses broches dépassent à 2 mm des broches 1
   et 8 de U3. Contrôler U3 à l'ohmmètre (continuité de CANH et CANL jusqu'aux pastilles de J2, pas
   de court-circuit entre broches voisines) avant de souder J2.
2. Y1 avant C10 et C11 : étamer ses deux pastilles, poser le quartz, chauffer le bout de pastille qui
   dépasse (0,95 mm). C10 et C11 sont à 0,6 mm de ces bouts.
3. R1 avant JP1 : 1,2 mm entre la pastille de R1 et l'embase.

Vias dans une pastille (la factory métallise les vias ; à la main ils se remplissent d'étain) :
C2 (+3V3), C3 (les deux pastilles), C5 (+3V3), C8 (GND), C13 (GND), R3 (BOOT0), et les deux vias de la
protection USB, chacun dans une pastille de J1 en face avant et de U5 en face arrière (J1.3 / U5.1 pour
D+, J1.2 / U5.3 pour D−). `verifier_criteres.py` en donne la liste.

**Plan d'implantation** (`fabrication/implantation.pdf`) : une page par face, avec le repère et la
valeur dans chaque composant ; la face arrière y est dessinée carte retournée. C'est la référence
pour souder si la factory ne sérigraphie pas la carte.

## Points restant à confirmer (⚠️ ou ℹ️)

1. **Quartz** : relever la CL du quartz reçu et recalculer C10/C11.
2. **Fentes de 2,5 × 1,0 mm** (pattes de la fiche USB-A) : à faire accepter par la factory, dont le
   guide ne cite que des perçages ronds.
3. **Vias dans des pastilles** (liste ci-dessus) : le guide annonce des vias métallisés ; le faire
   confirmer pour ceux-là.
4. **Octets d'option du STM32** (nSWBOOT0, nBOOT1) : les lire au premier branchement. Si la
   broche BOOT0 n'est pas prise en compte, programmer par le connecteur SWD J3.
5. **Bornier J2** : vérifier que le bornier acheté est au pas de 5,08 mm (et non 5,00 mm) ; les
   perçages sont de 1,4 mm.
6. **LED d'erreur D4** : le capot imprimé (v0.2) n'a pas de trou au-dessus d'elle, en
   (139,2 ; 126,4) sur la carte. Percer le capot à 2,2 mm ou ajouter `[9.2, -11.4]` à `leds`
   dans `boitier/boitier.scad`, puis refaire le STL, le 3MF et le G-code, et réimprimer le capot.
   Les gravures du boîtier disent « v0.2 ».
7. **Sérigraphie** : tous les repères sont visibles, placés hors des pastilles et des vias par
   `router_manuel.py` ; celui de J2 est sous le bornier (les lettres H, L, G occupent la place à
   côté). À vérifier : la factory sérigraphie-t-elle les cartes en cuivre nu ?
8. **Trous de fixation** : la carte n'en a pas, le boîtier la tient par son rebord et ses nervures.
