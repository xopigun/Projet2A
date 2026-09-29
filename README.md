# Banc de test CAN — G69-BANC-001

Outil interne du **groupe 69** (ENSEA 2A, projet « Conception d'une Électronique Modulaire
(Bus CAN) ») servant à valider le standard CAN commun et les ICD produits avec les groupes
partenaires.

Le banc est **générique** : aucun code n'est spécifique à un groupe partenaire, les besoins
particuliers passent par de la configuration. Les quatre projets partenaires (Cobot RMD-X,
Ecomarathon, Formula Student, MIR1000) sont traités au même niveau.

Auteurs (ordre alphabétique) : Samuel GOMRI, Dylan KIATI, Hugo MATHOUX.

---

## ⚠ À faire avant la première mise sous tension

Ces deux points sont des **modifications matérielles** sur chaque Nucleo-G431KB. Les ignorer
donne des symptômes qui ressemblent à une panne et non à une erreur de montage.

1. **Retirer le cavalier HW1**, livré fermé entre `CN4` broche 5 (`D2` = PA12) et `CN4`
   broche 4 (`GND`) — UM2397 §5.1 et §6.1. PA12 est `FDCAN1_TX` : laissé à la masse, il
   place le bus en **état dominant permanent** et bloque toute communication.

2. **Souder les ponts SB9 et SB10** pour connecter le quartz 24 MHz. En sortie d'usine la
   carte démarre sur le **HSI** (UM2397 §6.5, Table 9), dont la précision de ±1 % dépasse
   plus du double la tolérance admissible de 0,485 % à 500 kbit/s. Tant que ce n'est pas
   fait, compiler avec `-DBENCH_CLOCK_SOURCE=HSI` : le firmware émet un avertissement à la
   compilation, affiche `HSI - NON VALIDE` sur l'écran et signale le défaut dans son
   heartbeat, et `canbench` refuse alors de prononcer un verdict de réussite.

**Procédure de mise en route pas à pas : [docs/bringup.md](docs/bringup.md).** Elle amène
trois cartes neuves à un bus qui communique, en validant l'horloge, le temps de bit et
l'encodage **avant** tout câblage grâce au bouclage interne du FDCAN.

Brochage, terminaisons et injection de fautes : [docs/pinout.md](docs/pinout.md).

---

## Démarrage rapide

### Prérequis

| Outil | Version | Rôle |
|---|---|---|
| git | ≥ 2.30 | sous-modules |
| CMake | ≥ 3.24 | presets version 6 |
| Ninja | ≥ 1.10 | générateur |
| `arm-none-eabi-gcc` | ≥ 12 | firmwares |
| `gcc` ou `clang` | — | tests unitaires natifs |
| Python | ≥ 3.10 | outils PC et génération depuis l'ICD |
| STM32CubeProgrammer **ou** OpenOCD | — | programmation (facultatif) |

### Cloner

```bash
git clone --recursive <url> banc-can
cd banc-can
```

Si le dépôt a été cloné sans `--recursive` :

```bash
git submodule update --init --recursive
```

### Compiler et exécuter les tests unitaires (aucun matériel)

```bash
cmake --preset host
cmake --build --preset host
ctest --preset host
```

### Compiler un firmware

Un preset par nœud : `n1`, `n2`, `n3` (Nucleo-G431KB) et `n4` (Blue Pill STM32F103).

```bash
cmake --preset n1
cmake --build --preset n1
```

### Programmer un nœud

```bash
cmake --build --preset n1 --target flash_n1
```

`STM32_Programmer_CLI` et `openocd` sont cherchés dans le `PATH` puis dans les emplacements
d'installation usuels ; le premier trouvé est utilisé. Pour forcer :
`cmake --preset n1 -DBENCH_FLASH_TOOL=openocd`.

### Installer les outils PC

```bash
python -m pip install -e "pc[dev]"
```

### Premier test, sans matériel

Toutes les sous-commandes fonctionnent sur le bus `virtual` de python-can, avec un
simulateur qui reproduit N1 à N4 (ARM/GO et heartbeat compris) :

```bash
canbench --interface virtual --simulate arbitration --cycles 100
canbench --interface virtual --simulate encoding
canbench --interface virtual --simulate faults
canbench --interface virtual --simulate busload --measure 2
```

`--simulate` démarre un simulateur reproduisant N1 à N4. **Aucun verdict de réussite n'est
prononcé sur le bus virtuel** : le simulateur reproduit le comportement attendu, il ne le
démontre pas. Les rapports produits portent la mention correspondante.

### Interface graphique

Pour une démonstration, ou simplement pour piloter le banc sans ligne de commande, il
existe un **logiciel Windows**, `BancCAN.exe`. Il s'ouvre dans sa propre fenêtre, se
connecte depuis le bouton « Connexion » (simulation ou CANable), et s'arrête quand on
ferme la fenêtre. Le bouton « Aide » explique chaque indicateur, chaque test et chaque
faute. L'exécutable n'est pas versionné ; il se reconstruit en une minute :

```bash
python -m pip install pyinstaller
```

```bash
python pc/build_exe.py
```

Le fichier produit est `dist/BancCAN.exe`. Pour que le logiciel pilote un CANable réel,
installer le pilote python-can correspondant **avant** de le construire
(`python -m pip install -e "pc[slcan]"` ou `"pc[gs-usb]"`) : il est alors embarqué.
Le firmware candleLight (`gs_usb`) demande en outre la bibliothèque système **libusb**,
absente par défaut sous Windows : le paquet `libusb-package` la fournit. Tant qu'elle
manque, la fenêtre « Connexion » l'indique au lieu de proposer une connexion vouée à
l'échec. Le firmware `slcan` n'en a pas besoin.

Sans construire l'exécutable, **double-cliquer sur `lancer_banc.bat`** donne la même
interface dans le navigateur. Le navigateur s'ouvre sur
<http://127.0.0.1:8765> et affiche le bus en direct, l'état des nœuds tiré de leurs
heartbeats, les trames décodées par l'ICD, les tests T3, T4 et T6 avec leur rapport
téléchargeable, et l'injection de fautes par `BENCH_CFG`.

Sans argument, l'interface tourne en **simulation** : un bandeau le rappelle en permanence
et aucun verdict n'y vaut preuve. Sur le banc réel :

```bash
lancer_banc.bat gs_usb
```

L'équivalent en ligne de commande est `canbench --interface virtual gui`. L'interface
n'ajoute aucune dépendance et n'a aucune logique de test propre : elle appelle les mêmes
fonctions que `canbench`.

### Premier test sur le banc réel

Le CANable 2.0 est supporté en firmware candleLight (`gs_usb`) et en `slcan` :

```bash
canbench --interface gs_usb  monitor
canbench --interface slcan --channel COM7 arbitration --cycles 1000
```

---

## Organisation du dépôt

| Répertoire | Contenu |
|---|---|
| `icd/` | `bench_icd.yaml` — **source unique** des identifiants, signaux et encodages |
| `tools/codegen/` | génération depuis l'ICD : C, Python, DBC, LaTeX |
| `firmware/common/` | code indépendant du microcontrôleur — aucun en-tête HAL |
| `firmware/ports/` | couches matérielles : `g431_fdcan`, `f103_bxcan` |
| `firmware/boards/` | `board.h` — **tout** le brochage, et nulle part ailleurs |
| `firmware/vendor/` | sous-modules ST épinglés (HAL, CMSIS) |
| `firmware/tests_host/` | tests unitaires natifs du code commun |
| `pc/canbench/` | outil en ligne de commande `canbench` |
| `scripts/` | `bit_timing.py`, `bus_load.py` |
| `docs/` | plan, architecture, brochage, bit timing, protocole de validation, extraits LaTeX |

Le code généré depuis l'ICD (`firmware/common/icd_gen/`, `pc/canbench/icd_gen.py`) **ne
doit pas être édité à la main** : un test de CI vérifie qu'il est à jour.

## Sous-modules

Versions épinglées ; licences relevées dans les dépôts aux versions indiquées.

| Sous-module | Tag | Licence |
|---|---|---|
| `cmsis_core` | `v5.9.0_20250520` | Apache-2.0 |
| `cmsis_device_g4` | `v1.2.6` | Apache-2.0 |
| `cmsis_device_f1` | `v4.3.5` | Apache-2.0 |
| `stm32g4xx_hal_driver` | `v1.2.7` | BSD-3-Clause |
| `stm32f1xx_hal_driver` | `v1.1.10` | BSD-3-Clause |

Le projet lui-même est sous licence MIT — voir [LICENSE](LICENSE).

## Paramètres retenus

| Paramètre | Valeur |
|---|---|
| Débit | 500 kbit/s, CAN 2.0A *classic* (identifiants 11 bits) |
| Point d'échantillonnage | 87,50 % exactement, identique sur G431 et F103 |
| Tolérance d'oscillateur | 0,485 % — voir [docs/bit_timing.md](docs/bit_timing.md) |
| G431 | horloge FDCAN 80 MHz, BRP 10, 16 tq (1+13+2), SJW 2 |
| F103 | APB1 36 MHz, BRP 9, 8 tq (1+6+1), SJW 1 |

## Documentation

- [docs/PLAN.md](docs/PLAN.md) — plan de travail, écarts relevés, points à vérifier
- [docs/architecture.md](docs/architecture.md) — couches, flux ISR, machine d'états ARM/GO
- [docs/pinout.md](docs/pinout.md) — brochage, vérifié depuis les `board.h`
- [docs/bit_timing.md](docs/bit_timing.md) — calcul et justification du bit timing
- [docs/config_logicielle.md](docs/config_logicielle.md) — paramètres FDCAN/bxCAN
- [docs/protocole_validation.md](docs/protocole_validation.md) — les sept tests T1 à T7
- [docs/bringup.md](docs/bringup.md) — procédure de mise en route pas à pas
- [docs/references/README.md](docs/references/README.md) — où trouver les documents de référence
