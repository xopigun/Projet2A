# Brochage du banc

Ce document décrit le câblage d'un nœud. **La référence est `board.h`**, pas ce fichier :
un test de la suite Python (`test_pinout_coherent_avec_board_h`) échoue si une broche
déclarée dans `firmware/boards/*/board.h` n'apparaît pas ici, pour éviter que la
documentation ne dérive du code.

Toutes les affectations viennent de **UM2397 Rev 2** (manuel utilisateur de la carte
NUCLEO-G431KB, MB1430), Table 11 (connecteurs Arduino Nano) et Table 12 (affectation des
32 broches du boîtier UFQFPN32), sauf mention contraire.

---

## 1. Avant tout câblage — deux gestes obligatoires

| # | Geste | Pourquoi | Source |
|---|---|---|---|
| 1 | **Retirer le cavalier HW1** entre CN4-5 (`D2` = PA12) et CN4-4 (`GND`) | PA12 est `FDCAN1_TX`. Laissé à la masse, il place le bus en **dominant permanent** et bloque toute communication, avec un symptôme qui ressemble à une panne matérielle. | UM2397 §5.1 étape 5, §6.1 |
| 2 | **Souder SB9 et SB10** | La carte démarre sur le **HSI** en sortie d'usine : SB8, SB9, SB10, SB11 et SB13 sont tous ouverts. Le quartz 24 MHz est monté mais déconnecté. Le HSI (±1 %) dépasse plus du double la tolérance admissible de 0,485 %. | UM2397 §6.5, Table 9 |

Tant que le geste 2 n'est pas fait, compiler avec `-DBENCH_CLOCK_SOURCE=2` : le firmware
émet un avertissement, affiche `HSI - NON VALIDE` et lève `clock_not_qualified` dans son
heartbeat, ce qui interdit tout verdict de réussite.

**Ne pas toucher à SB2 ni SB3**, fermés par défaut — voir §3.

---

## 2. Nucleo-G431KB (nœuds N1, N2, N3)

| Fonction | Broche | Repère Nano | Connecteur | Remarque |
|---|---|---|---|---|
| `FDCAN1_RX` | PA11 | D10 | CN4-13 | AF9 (DS12589 Table 13) |
| `FDCAN1_TX` | PA12 | D2 | CN4-5 | AF9 — **retirer HW1** |
| `I2C1_SCL` | PA15 | D5 (= A5) | CN4-8 (= CN3-7) | SB3 fermé : le signal est sur les deux |
| `I2C1_SDA` | PB7 | D4 (= A4) | CN4-7 (= CN3-8) | SB2 fermé : idem |
| VCP TX | PA2 | A7 | CN3-5 | USART2, SB1 fermé par défaut |
| VCP RX | PA3 | A2 | CN3-10 | USART2, SB12 fermé par défaut |
| LED TX | PB8 | D13 | — | LED LD2 embarquée ; PB8 est aussi BOOT0 |
| LED erreur | PA0 | A0 | CN3-12 | error-passive |
| LED bus-off | PA1 | A1 | CN3-11 | bus-off |
| Broche S transceiver | PB6 | D6 | CN4-9 | optionnelle, voir §5 |
| Capteur Hall (N2) | PA4 | A3 | CN3-9 | entrée à front |
| 1-Wire DS18B20 (N3) | PA7 | A6 | CN3-6 | drain ouvert + 4,7 kΩ |
| HSE | PF0 / PF1 | D7 / D8 | CN4-10 / CN4-11 | **consommées** si SB9+SB10 soudés |

### Écarts par rapport au dossier v0.1

| Le dossier place… | …or | Retenu |
|---|---|---|
| `PB8` = SCL, **`PB9`** = SDA | **PB9 n'existe pas** sur le boîtier UFQFPN32 (UM2397 Table 12 : PA0–PA15, PB0, PB3–PB8, PF0, PF1, PG10) ; et PB8 est BOOT0, qu'une pull-up I2C forcerait à 1 au reset | `PA15` = SCL, `PB7` = SDA |
| une LED sur `PA2` | PA2 est le TX du port COM virtuel du ST-LINK (SB1 fermé par défaut) | LED TX sur `PB8` |

PA0 et PA1 sont conservées telles que le dossier les prévoit.

---

## 3. Contrainte logicielle : PA5 et PA6 en entrée flottante

SB2 et SB3 sont **fermés par défaut** (UM2397 Table 9, état par défaut en gras). Ils
reportent PA15 et PB7 sur A5 et A4, l'emplacement I2C standard d'un Arduino Nano.

Ce n'est pas un problème — notre câblage sur D4/D5 fonctionne sans modification — **mais**
UM2397 précise alors : « PA6 must be configured as floating input » (SB3) et « PA5 must be
configured as floating input » (SB2). Sans cela, PA5 et PA6 entrent en conflit électrique
avec PB7 et PA15 via CN3-8 et CN3-7.

C'est appliqué par `BENCH_FLOATING_PINS` dans `board.h`, configuré au démarrage par
`gpio_init()`. **Ne pas ouvrir SB2 ni SB3** : ce serait utile seulement pour retrouver A4 et
A5 en entrées analogiques, ce dont le banc n'a pas besoin.

---

## 4. Blue Pill STM32F103 (nœud N4)

**Aucun brochage n'est proposé à ce stade.** Le document fourni sous le nom
`BluePill STM32F103.pdf` est une présentation commerciale du portfolio cartes ST et ne
contient aucune information sur la carte, le F103 ni bxCAN.

Le brochage sera écrit au lot 5, une fois disponibles **RM0008**, **DS5319** et le schéma de
la carte. Deux points seront alors tranchés :

- PA11/PA12 sont partagées avec l'USB, et la Blue Pill porte une résistance de tirage sur
  PA12 (valeur souvent erronée sur les clones) — `TODO(verif) V6` ;
- l'alternative est de remapper bxCAN sur PB8/PB9 via `AFIO_MAPR.CAN_REMAP = 10`, broches
  libres sur cette carte — `TODO(verif) V5`.

---

## 5. Transceiver TJA1051T/3

Le dossier (§2.3 et §4.1) retient le **TJA1051T/3** pour les quatre nœuds. La variante
importe : seuls les `TJA1051T/3` et `TJA1051TK/3` possèdent la broche **VIO** permettant
l'interface directe avec un microcontrôleur 3,3 V. Le `TJA1051T` simple a des niveaux
logiques 5 V, incompatibles sans adaptation.

| Broche TJA1051T/3 | Vers | Remarque |
|---|---|---|
| 1 `TXD` | PA12 | niveau 3,3 V |
| 2 `GND` | GND | masse commune avec le GND du bus (DB9-3) |
| 3 `VCC` | **+5 V** | 4,5 à 5,5 V — CN3-4 ou le rail 5 V du banc, **jamais les deux** |
| 4 `RXD` | PA11 | niveau VIO |
| 5 `VIO` | **+3,3 V** | fixe les seuils logiques |
| 6 `CANL` | DB9-2 | |
| 7 `CANH` | DB9-7 | |
| 8 `S` | GND, ou PB6 | bas = normal, haut = silencieux |

Découplage : 100 nF au plus près de `VCC` et de `VIO`.

**La broche S n'est pas le moyen retenu pour le mode silencieux.** Le firmware utilise le
mode moniteur du contrôleur (`FDCAN CCCR.MON`, `bxCAN BTR.SILM`) : même sémantique sur les
deux microcontrôleurs, pas de dégradation du récepteur, et aucune dépendance au modèle de
transceiver. La broche reste pilotable si `board.h` la définit.

À noter pour le test T6 : le TJA1051 possède une temporisation *TXD dominant time-out*
(§6.2.1) qui coupe le driver si TXD reste bas trop longtemps — elle « définit également le
débit minimal possible de 40 kbit/s ». Une faute « dominant collé » sera donc corrigée
d'elle-même après quelques centaines de µs. Le mode *babbling idiot* n'est pas concerné,
TXD y basculant normalement.

---

## 6. Terminaisons — **point à trancher (Q5b)**

Le dossier (§4.2, §4.3) définit **deux terminaisons discrètes de 120 Ω**, aux deux
extrémités physiques de la ligne : `R_T1` fixe, et `R_T2` commutée par SW1. Les quatre
nœuds et le CANable sont sur des dérivations courtes (≤ 0,3 m), **pas** en bout de ligne.

Or les modules transceiver du commerce portent fréquemment une résistance de 120 Ω soudée à
demeure. Les deux cas doivent être traités :

### Cas A — les modules ne portent pas de 120 Ω

Rien à faire. Le montage est celui du dossier : `R_T1` et `R_T2` discrètes aux extrémités,
SW1 fermé en fonctionnement nominal.

### Cas B — les modules portent un 120 Ω soudé

**Le retirer (ou l'ouvrir) sur les quatre nœuds**, N1 compris.

C'est le point important : on pourrait croire qu'il suffit d'en garder un en guise de
`R_T1`. Ce n'est pas le cas, parce que dans la topologie du dossier **N1 n'est pas à une
extrémité de la ligne** — il est sur une dérivation, comme les autres. Une terminaison
placée en bout de stub ne termine pas la ligne principale et introduit des réflexions au
lieu de les supprimer.

Avec les quatre modules terminés et les deux résistances discrètes, le bus verrait
6 × 120 Ω en parallèle, soit **20 Ω**. Le TJA1051 spécifie sa tension différentielle de
sortie `VO(dif)bus` (1,5 à 3 V) **pour une charge RL de 45 à 65 Ω** ; à 20 Ω on est très
au-delà, et le comportement n'est plus garanti. En pratique la tension différentielle
s'effondre et peut approcher le seuil de détection du récepteur, spécifié entre 0,5 et
0,9 V : on obtient alors des **erreurs intermittentes** — trames perdues, `REC` qui grimpe,
comportement dépendant de la température et de la longueur du câble — plutôt qu'un bus
franchement muet. C'est un mode de défaillance bien plus coûteux à diagnostiquer.

*Source : TJA1051, tableau des caractéristiques statiques — `VO(dif)bus` pour
RL = 45 Ω à 65 Ω, et `Vth(RX)dif` de 0,5 à 0,9 V.*

### Contrôle avant mise sous tension

Bus complet assemblé, **hors tension**, SW1 fermé, mesurer entre CAN_H et CAN_L :

| Mesure | Interprétation |
|---|---|
| **≈ 60 Ω** | correct — deux terminaisons de 120 Ω en parallèle |
| ≈ 120 Ω | une seule terminaison : SW1 ouvert, ou `R_T2` absente |
| < 40 Ω | terminaisons surnuméraires — des modules portent encore leur 120 Ω |
| ≫ 120 Ω | aucune terminaison, ou ligne coupée |

Cette mesure est le premier point du test **T1**.

---

## 7. Connecteurs du bus — DB9, CiA 303-1

Tous les connecteurs J1 à J5 utilisent le même brochage, afin qu'un nœud puisse être
raccordé à n'importe quel point sans risque d'erreur (dossier §4.2).

| Broche DB9 | Signal | Couleur préconisée |
|---|---|---|
| 2 | `CAN_L` | bleu |
| 3 | `GND` (référence) | noir |
| 7 | `CAN_H` | rouge (ou blanc) |
| 9 | +5 V (optionnel) | rouge |
| 1, 4, 5, 6, 8 | non connectées | — |

Règles de topologie : deux terminaisons exactement, aux extrémités physiques ; dérivations
les plus courtes possible ; blindage relié à la masse **en un seul point**.

---

## 8. Injection de fautes

| Repère | Faute | Position nominale | Effet attendu |
|---|---|---|---|
| SW1 | Perte d'une terminaison (retire `R_T2`) | **fermé** | Dégradation du signal, hausse du taux d'erreur |
| SW2 | Court-circuit CAN_H / CAN_L | **ouvert** | Erreurs de bit, passage en *bus-off* |
| SW3 | Retrait à chaud de N4 (DPST) | **fermé** | Le reste du bus continue de fonctionner |

> **SW2 ne doit être fermé que brièvement.** Le TJA1051T/3 limite son courant de
> court-circuit mais s'échauffe si l'état se prolonge. `canbench faults` affiche une durée
> maximale et un décompte. Ne jamais actionner SW2 pendant qu'un nœud isolé galvaniquement
> est sous tension côté puissance.
