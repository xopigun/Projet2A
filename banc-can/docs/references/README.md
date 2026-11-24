# Documents de référence

Les PDF sont **versionnés dans ce répertoire** depuis le 06/10/2026, pour que toute
l'équipe dispose des mêmes révisions sans avoir à les retrouver (environ 63 Mo). Ce
fichier reste l'index : il donne pour chacun la révision, le lien officiel et ce que
l'on en a réellement utilisé. Aucun outil du dépôt n'en dépend à la compilation.

> **Droits.** Les documents ST, NXP et TI appartiennent à leurs éditeurs, qui les
> diffusent librement sur leurs sites. Les garder dans un dépôt **privé** pour l'équipe
> ne pose pas de difficulté ; si le dépôt devenait public, mieux vaudrait les retirer
> et ne garder que les liens officiels ci-dessous.

## Dossier du projet

| Document | Réf. | Révision | Source |
|---|---|---|---|
| Dossier de définition — Banc de test CAN | G69-BANC-001 | v0.1, 22/09/2026 | interne au groupe 69 |

Nom attendu ici : `Dossier_Banc_Test_CAN_v0_1.pdf`.

> **Le dossier a son propre cycle de vie.** Seul son PDF v0.1 est conservé ici, comme
> référence figée ; il n'est jamais modifié depuis `banc-can/` : sa source LaTeX est dans
> le dossier `Banc de Test/` à la racine du dépôt, et c'est elle qui fait foi pour les tableaux. Le dépôt ne fait que **référencer une version**, ici la **v0.1**.
> Les écarts relevés par rapport à cette version sont consignés dans
> [PLAN.md](../PLAN.md), section « Corrections à reporter dans le dossier v0.2 », à charge
> pour le rédacteur du dossier de les y intégrer.

Sections utilisées : §1 (les six fonctions), §2 (architecture, choix du TJA1051T/3),
§4.1 (schéma d'un nœud), §4.2 (bus, brochage DB9 CiA 303-1), §4.3 (SW1/SW2/SW3),
§4.4 (IHM locale, zones de l'écran), §4.6 (protocole ARM/GO, tableau 7).
Les sections 5, 6 et 7 sont des squelettes `\todo{}` que nos documents ont vocation à remplir.

## Documents constructeurs

| Document | Réf. | Révision | Lien officiel |
|---|---|---|---|
| STM32G4 Nucleo-32 board (MB1430) — manuel utilisateur | **UM2397** | Rev 2, 04/09/2019 | <https://www.st.com/resource/en/user_manual/um2397-stm32g4-nucleo32-board-mb1430-stmicroelectronics.pdf> |
| TJA1051 — High-speed CAN transceiver | TJA1051 | Rev 02, 01/07/2009 | <https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf> |

Sections utilisées :

- **UM2397** — §5.1 (cavalier HW1 à retirer), §6.1 (implantation, HW1 sur CN4 [4-5]),
  §6.5 (sources d'horloge, HSI par défaut), §6.6.1 (LED LD2 sur PB8), §6.6.4 (VCP sur
  USART2/PA2-PA3), §6.7 **Table 9** (ponts de soudure et leur état par défaut, en gras),
  §7.2 **Table 11** (brochage Arduino Nano), §8 **Table 12** (affectation des 32 broches).
  C'est la référence la plus utilisée du projet.
- **TJA1051** — Table 2 (brochage, broche VIO présente seulement sur les versions T/3 et
  TK/3), §6.1.1 et §6.1.2 (modes Normal et Silent via la broche S), Table 3 (table de
  vérité), §6.2.1 (*TXD dominant time-out*, débit minimal 40 kbit/s), Table 6 (VCC, VIO).

> Attention : le fichier fourni sous le nom `NucleoG431KB Datasheet.pdf` **n'est pas une
> datasheet** mais le manuel utilisateur UM2397 de la carte. La datasheet du
> microcontrôleur (DS12589) est un document distinct, encore manquant.

## Documents microcontrôleurs, reçus le 29/09/2026

| Document | Réf. | Révision | Nom attendu ici | Utilisé pour |
|---|---|---|---|---|
| STM32G4 series — reference manual | **RM0440** | Rev 9, 03/2025 | `RM0440.pdf` | §2.4 mémoire (V11), §2.6 démarrage et `FLASH_OPTR` (V2), §7.4.4 PLL (V3), Table 9 latence flash, §44.4.6 `FDCAN_CCCR` |
| STM32G431x6/x8/xB — datasheet | **DS12589** | Rev 6, 10/2021 | `DS12589.pdf` | Table 13 fonctions alternées (V1), Table 42 HSI16 (V4), Table 45 PLL (V3) |
| STM32G431/441 — errata sheet | **ES0431** | Rev 9, 06/2024 | `ES0431.pdf` | §2.15 FDCAN (V10) |

Tous sont disponibles sur <https://www.st.com>, page produit du microcontrôleur, onglet
« Documentation ».

## Retirés du dépôt le 24/11/2026

Documents des choix abandonnés : la Blue Pill STM32F103 pour N4, remplacée par une
Nucleo-G431KB, et le transceiver SN65HVD230, écarté au profit du TJA1051T/3. Ils restent
dans l'historique git (`git log --diff-filter=D -- banc-can/docs/references/`) et sur les
sites des éditeurs.

| Fichier retiré | Réf. | Révision | Avait servi pour |
|---|---|---|---|
| `RM0008.pdf` — STM32F10xxx reference manual | **RM0008** | Rev 21, 02/2021 | §9.3.4 Table 34 remap CAN (V5), § bxCAN (SRAM partagée avec l'USB, modes de test), `FLASH_ACR` |
| `DS5319.pdf` — STM32F103x8/xB datasheet | **DS5319** | Rev 20, 07/2025 | Table 5 broches du LQFP48 et remap (V5), note 5 sur PC13 (V13) |
| `SN65HVD230.PDF` — 3.3 V CAN transceivers, <https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf> | SLOS346 | Rev G, 06/2002 | comparaison : broche 8 = RS (standby/slope control), et non silent comme sur le TJA1051 |
| `BluePill STM32F103.pdf` | — | Q1 2022 | rien : présentation commerciale du portfolio cartes ST, qui ne documente ni la Blue Pill ni bxCAN |

## Documents inexistants ou manquants

Aucun document manquant ne bloque le projet. Les documents propres à la Blue Pill (schéma de la carte, errata STM32F103) ne sont plus
nécessaires : N4 est une Nucleo-G431KB depuis l'abandon de cette carte.
