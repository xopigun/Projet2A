# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Les versions suivent l'historique du dossier de définition G69-BANC-001 : la version `0.1`
du dépôt correspond au dossier `v0.1`.

## [Non publié]

### Ajouté

- Plan de travail de phase 0 (`docs/PLAN.md`) : lecture des références, vérification des
  sept points relevés dans le dossier v0.1, calcul des bit timings, découpage en lots.
- Socle du dépôt : configuration git, style de code, licence MIT, index des références.
- Sous-modules ST épinglés (`firmware/vendor/`) : CMSIS core, CMSIS device G4 et F1,
  pilotes HAL G4 et F1.
- ICD unique (`icd/bench_icd.yaml`) avec profils réseau, générateur vers C, Python, DBC et
  LaTeX, et parité d'encodage vérifiée entre quatre implémentations.
- Code commun testable nativement : tampon circulaire, protocole ARM/GO, heartbeat.
- Firmware des nœuds N1 à N3 (port FDCAN, horloges HSE/HSI sélectionnables).
- ~~Firmware du nœud N4 sur Blue Pill STM32F103~~ (retiré depuis, voir *Retiré*).
  Programme principal commun à toutes les cartes (`firmware/entry/`).
- **Exécution des modes de faute** commandés par `BENCH_CFG` sur les nœuds réels
  (babbling idiot, débit erroné, DLC incohérent, silencieux, bus-off maintenu), avec le
  même comportement que le simulateur.
- **Verrouillage CAN 2.0A classic** à trois niveaux : validateur de l'ICD, `_Static_assert`
  générés, contrôle à l'émission et à l'ouverture. Les trames CAN FD ou à identifiant
  29 bits reçues sont comptées et remontées dans le heartbeat.
- **Autotest de mise en route** (`presets n1-selftest` à `n3-selftest`) : bouclage interne
  FDCAN sans transceiver, puis ping/pong sur le bus réel, avec état `PSR`/`ECR` sur le VCP.
- Documentation : `docs/bringup.md` (mise en route pas à pas), `docs/pinout.md`,
  `docs/config_logicielle.md` et son extrait LaTeX généré depuis les `board.h`,
  `docs/protocole_validation.md` (les sept tests T1 à T7).
- **Outils PC `canbench`** : `monitor`, `arbitration`, `encoding`, `faults`, `busload`,
  `record`, `replay` et `report`. Toutes les sous-commandes tournent sur le bus `virtual`
  avec `--simulate`, qui reproduit N1 à N4 (ARM/GO, heartbeat, modes de faute).
  L'interface est ouverte en CAN 2.0A classic ; toute trame FD ou étendue reçue est
  signalée. Les rapports Markdown et LaTeX portent la date et le hash git du firmware,
  et refusent de conclure à une réussite sur bus virtuel ou avec une horloge non conforme.

- **Interface graphique** (`canbench gui`, `lancer_banc.bat`) : bus en direct, état des
  nœuds, trames décodées, tests T3, T4 et T6 avec rapport, injection de fautes. Sans
  dépendance supplémentaire ; simulation signalée en permanence.
- **Logiciel Windows `BancCAN.exe`** (`pc/build_exe.py`, PyInstaller) : fenêtre
  d'application dédiée, connexion choisie depuis l'interface avec repli en simulation,
  aide intégrée (TEC/REC, états CAN, tests T1 à T7, fautes), arrêt à la fermeture, perte
  de connexion signalée au lieu d'une page figée.
- ~~Afficheurs LCD 16x2 de N1 et N2~~ (retirés depuis au profit des écrans OLED, voir
  *Retiré*).
- **`BENCH_STLINK_SN`** : choix de la sonde à programmer quand plusieurs cartes sont
  branchées ; sans lui, `flash_<noeud>` prend la première trouvée.

- **Adaptateur ZLG USBCAN-UC12 sans son pilote noyau** (`canbench --interface zlg`) : le
  pilote ZLG est refusé par l'intégrité de la mémoire de Windows ; `pc/canbench/zlg_usbcan/`
  parle à l'adaptateur par WinUSB (protocole décrit dans `PROTOCOLE.md`).
- **Panneau Qualité** de l'interface (`pc/canbench/quality.py`) : état du contrôleur de
  l'adaptateur, trames non acquittées, période, gigue et trames manquées par identifiant.
- **Adaptateur USB-CAN v0.2** fabricable à la factory ENSEA (`hardware/adaptateur_usb_can/`) :
  carte 60 × 30 mm, fiche USB-A en clé, bornier à vis ; champs fabricant et MPN dans le
  schéma, classe de nets « Puissance », teardrops ; boîtier imprimé en 3D (`boitier/`) tranché
  pour la Bambu Lab X1 Carbon du FabLab.
- **Point d'état du projet** (`docs/ETAT_PROJET.md`) : ce qui est fait, en cours, et la liste
  des choix abandonnés avec leur raison.

### Modifié

- **Nœud N4 sur Nucleo-G431KB** : les quatre nœuds sont identiques. Presets `n4`,
  `n4-selftest` et nouveau `n4-selftest-hsi` ; ICD, simulation 3D, schéma fonctionnel,
  extrait LaTeX de configuration et documentation mis à jour.
- **Schéma de câblage du bus** (`hardware/cablage_bus_can/`) : 4 Nucleo-G431KB et 4
  TJA1051T/3 sur adaptateurs SOP8 au lieu de 3 Adafruit CAN Pal ; terminaisons sur le ZLG et
  sur l'adaptateur de N4.

### Retiré

- **Blue Pill STM32F103** (nœud N4) : port `firmware/ports/f103_bxcan`, carte
  `firmware/boards/bluepill_f103`, `cmake/openocd_f1.cfg`, sous-modules ST
  `cmsis_device_f1` et `stm32f1xx_hal_driver`, modèle 3D de la simulation. Récupérables dans
  l'historique git (commit `d1a745c` et antérieurs).
- **Pont slcan sur Nucleo-L476RG** (`bridge`, `bridge-direct`) : `entry/slcan_bridge.c`,
  `firmware/boards/nucleo_l476rg`, port `firmware/ports/l476_bxcan`, `cmake/openocd_l4.cfg`,
  sous-modules `cmsis_device_l4` et `stm32l4xx_hal_driver`. Il dépannait tant que le CANable
  était introuvable ; le ZLG et l'adaptateur USB-CAN le remplacent. Le module de protocole
  `common/app/slcan.c` et son test sont **conservés** pour le firmware de l'adaptateur.
- **Afficheurs LCD 16x2** de N1 et N2 : pilote HD44780 (`ports/g431_fdcan/lcd.c`), mise en
  forme `common/app/lcd_text.c` et son test, broches dans `board.h`, schéma
  `docs/latex/schema_ecrans_lcd.tex`. Les écrans OLED SSD1306 les remplacent ; les firmwares
  `scope` et `dialogue` gardent leur journal série.

### Corrigé (écarts relevés par rapport au dossier v0.1)

- **PB9 n'existe pas** sur le boîtier UFQFPN32 du STM32G431KB. Le schéma de l'IHM locale du
  dossier (§4.4) l'utilise comme SDA : I2C1 est déplacé sur `PA15` (SCL) et `PB7` (SDA).
- **PA2 est le TX du port COM virtuel** du ST-LINK (UM2397 Table 8 et Table 9, SB1 fermé par
  défaut). La LED que le dossier y plaçait est déplacée sur `PB8`.
- **Rafraîchissement OLED ≈ 23 ms** et non ≈ 10 ms : 1024 octets à 9 bits par octet en I2C
  à 400 kHz, soit ≈ 105 trames CAN de 8 octets et non « une vingtaine ».
- **Aucune HSE n'est active par défaut** sur la Nucleo-G431KB (SB9/SB10 ouverts) : la source
  d'horloge devient sélectionnable, avec repli HSI explicitement signalé comme non valide.
- **Cavalier HW1** livré fermé entre `D2` (PA12, FDCAN1_TX) et la masse : à retirer avant
  toute mise sous tension du bus.
- **Métrique « Perdus »** du tableau 7 : définie sans ambiguïté comme le nombre de cycles où
  le nœud a perdu au moins un arbitrage, complétée par la métrique de rang.

### Corrigé (firmware)

- **Horodatages figés après une déconnexion du débogueur** (ports G431, F103 alors présent, et L476) :
  après une programmation suivie d'un reset ou une connexion HOTPLUG, STM32CubeProgrammer
  remet `DEMCR` à `0x00000001` en se déconnectant. `TRCENA` effacé fige `DWT->CYCCNT`, que
  le port n'activait qu'une fois : `now_us()` et le `timestamp_us` des trames restaient
  constants jusqu'à la mise hors tension suivante. `now_us()` relance désormais le compteur
  à chaque lecture, sans jamais le remettre à zéro. Aucun rapport PC n'était faussé :
  `timestamp_us` ne quitte pas les nœuds, le pont slcan n'envoie pas d'horodatage et
  `canbench` date les trames à leur réception sur le PC.
- **Débordement de tampon en réception sur le G431** : la HAL G4 recopie jusqu'à 64
  octets pour une trame classique de DLC 9 à 15, légale en CAN 2.0. Réception dans un
  tampon de 64 octets, DLC ramené à 8.
- **Codage du DLC** à l'émission et à la réception sur le G431, qui dépend de la version
  de la HAL ; verrouillé par des assertions statiques.
- **Nœud figé après programmation** (relevé sur carte avec le pilote LCD) : en se
  déconnectant, STM32CubeProgrammer efface `DEMCR.TRCENA`, ce qui fige le compteur de
  cycles DWT ; une attente active fondée sur lui ne se terminait jamais. Le pilote relance
  le compteur à chaque lecture.

### Corrigé (dans nos propres documents)

- **D13 n'est pas PB8** : `docs/pinout.md` donnait D13 comme repère de la LED TX. D13 est
  PB3 (UM2397 Table 11) ; PB8 et LD2 ne sont pas sur le connecteur.

- **Portée du bouclage interne** : il ne valide ni l'horloge ni le débit, émetteur et
  récepteur partageant la même horloge noyau. Un échange entre deux nœuds de configuration
  identique ne le prouve pas davantage. Le débit n'est établi qu'à la phase 3 de la mise en
  route, contre une référence indépendante (CANable ou oscilloscope).
- **Effet d'un excès de terminaisons** : à 20 Ω on sort de la plage de charge
  `RL = 45 à 65 Ω` du TJA1051 ; le symptôme attendu est une dégradation de la tension
  différentielle et des erreurs intermittentes, non un bus muet.
