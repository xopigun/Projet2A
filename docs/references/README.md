# Documents de référence

Les PDF ne sont **pas versionnés** (`docs/references/*.pdf` est dans `.gitignore`) :
ils pèsent ensemble environ 25 Mo, sont redistribués par leurs éditeurs et évoluent
indépendamment du dépôt. Ce fichier tient lieu d'index : il indique où les retrouver et
ce que l'on en a réellement utilisé.

Placer les fichiers téléchargés dans ce répertoire pour reproduire l'environnement de
travail. Aucun outil du dépôt n'en dépend à la compilation.

## Dossier du projet

| Document | Réf. | Révision | Source |
|---|---|---|---|
| Dossier de définition — Banc de test CAN | G69-BANC-001 | v0.1, 22/09/2026 | interne au groupe 69 |

Nom attendu ici : `Dossier_Banc_Test_CAN_v0_1.pdf`. La source LaTeX est hors dépôt
(`Projet 2A/Banc de Test/Dossier_Banc_Test_CAN_v0.1.tex`) et **fait foi** pour les tableaux.

Sections utilisées : §1 (les six fonctions), §2 (architecture, choix du TJA1051T/3),
§4.1 (schéma d'un nœud), §4.2 (bus, brochage DB9 CiA 303-1), §4.3 (SW1/SW2/SW3),
§4.4 (IHM locale, zones de l'écran), §4.6 (protocole ARM/GO, tableau 7).
Les sections 5, 6 et 7 sont des squelettes `\todo{}` que nos documents ont vocation à remplir.

## Documents constructeurs

| Document | Réf. | Révision | Lien officiel |
|---|---|---|---|
| STM32G4 Nucleo-32 board (MB1430) — manuel utilisateur | **UM2397** | Rev 2, 04/09/2019 | <https://www.st.com/resource/en/user_manual/um2397-stm32g4-nucleo32-board-mb1430-stmicroelectronics.pdf> |
| TJA1051 — High-speed CAN transceiver | TJA1051 | Rev 02, 01/07/2009 | <https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf> |
| SN65HVD230/231/232 — 3.3 V CAN transceivers | SLOS346 | Rev G, 06/2002 | <https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf> |

Sections utilisées :

- **UM2397** — §5.1 (cavalier HW1 à retirer), §6.1 (implantation, HW1 sur CN4 [4-5]),
  §6.5 (sources d'horloge, HSI par défaut), §6.6.1 (LED LD2 sur PB8), §6.6.4 (VCP sur
  USART2/PA2-PA3), §6.7 **Table 9** (ponts de soudure et leur état par défaut, en gras),
  §7.2 **Table 11** (brochage Arduino Nano), §8 **Table 12** (affectation des 32 broches).
  C'est la référence la plus utilisée du projet.
- **TJA1051** — Table 2 (brochage, broche VIO présente seulement sur les versions T/3 et
  TK/3), §6.1.1 et §6.1.2 (modes Normal et Silent via la broche S), Table 3 (table de
  vérité), §6.2.1 (*TXD dominant time-out*, débit minimal 40 kbit/s), Table 6 (VCC, VIO).
- **SN65HVD230** — conservé à titre de comparaison : ce composant **n'est pas dans la BOM
  nominale**, le dossier retenant le TJA1051T/3. Utilisé pour documenter la différence de
  sémantique de la broche 8 (RS = standby/slope control, et non silent).

> Attention : le fichier fourni sous le nom `NucleoG431KB Datasheet.pdf` **n'est pas une
> datasheet** mais le manuel utilisateur UM2397 de la carte. La datasheet du
> microcontrôleur (DS12589) est un document distinct, encore manquant.
>
> Le fichier fourni sous le nom `BluePill STM32F103.pdf` **ne documente pas la carte
> Blue Pill** : c'est une présentation commerciale du portfolio cartes ST (Q1 2022). Il ne
> contient aucune information exploitable sur le STM32F103 ni sur bxCAN.

## Documents encore manquants

Ils bloquent les vérifications listées au §10 de [PLAN.md](../PLAN.md).

| Document | Réf. | Nécessaire pour |
|---|---|---|
| STM32G4 series — reference manual | **RM0440** | Registres RCC/PLL, FDCAN, option bytes `nSWBOOT0` (V2, V3) |
| STM32G431xx — datasheet | **DS12589** | Fonctions alternées (FDCAN1 sur PA11/PA12, V1), précision HSI16 (V4) |
| STM32G431 — errata sheet | ES (G431) | Anomalies FDCAN éventuelles (V10) |
| STM32F10xxx — reference manual | **RM0008** | bxCAN, remap `AFIO_MAPR.CAN_REMAP` (V5) |
| STM32F103x8/xB — datasheet | **DS5319** | Brochage et fonctions alternées du F103C8 (V5) |
| Schéma de la carte « Blue Pill » | — | Pull-up USB sur PA12, clones F103 (V6) |

Tant que RM0008, DS5319 et le schéma de la Blue Pill ne sont pas disponibles, le **lot 5**
(port bxCAN et carte N4) reste bloqué : aucun brochage F103 ne sera écrit sans source.
