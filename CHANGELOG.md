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
