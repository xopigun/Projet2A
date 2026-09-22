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

### Corrigé (dans nos propres documents)

- **Portée du bouclage interne** : il ne valide ni l'horloge ni le débit, émetteur et
  récepteur partageant la même horloge noyau. Un échange entre deux nœuds de configuration
  identique ne le prouve pas davantage. Le débit n'est établi qu'à la phase 3 de la mise en
  route, contre une référence indépendante (CANable ou oscilloscope).
- **Effet d'un excès de terminaisons** : à 20 Ω on sort de la plage de charge
  `RL = 45 à 65 Ω` du TJA1051 ; le symptôme attendu est une dégradation de la tension
  différentielle et des erreurs intermittentes, non un bus muet.
