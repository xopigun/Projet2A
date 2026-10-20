# Mise en route — phase 1 sur matériel, 29/09/2026

Premier essai du firmware sur cartes réelles.

| Élément | Valeur |
|---|---|
| Cartes | 2 × NUCLEO-G431KB, cavalier HW1 retiré, SB9/SB10 **non soudés** |
| Firmware | presets `n1-selftest-hsi` et `n2-selftest-hsi`, commit `a636afc` |
| Liaison | USB → ST-LINK intégré : SWD pour la programmation, USART2 → port COM virtuel à 115200 bauds pour le journal |
| Montage | aucun : ni transceiver, ni bus |

## Résultats

| Nœud | Phase 1 (bouclage interne) | Phase 2 (bus réel) | Journal |
|---|---|---|---|
| N1 | **8/8 trames correctes**, error-active, TEC = REC = 0 | BUS-OFF, TEC = 248, LEC = 5 | [2026-09-29_autotest_N1.log](2026-09-29_autotest_N1.log) |
| N2 | **8/8 trames correctes**, error-active, TEC = REC = 0 | en attente de N1 | [2026-09-29_autotest_N2.log](2026-09-29_autotest_N2.log) |

## Ce que ces résultats établissent

- La chaîne de programmation, le démarrage (correctif D4, gestionnaire SysTick), le PLL
  sur HSI, l'horloge noyau FDCAN à 80 MHz, l'acceptation du temps de bit, les
  interruptions de réception, le tampon et l'encodage des 8 trames de l'ICD.
- Le passage en BUS-OFF de N1 en phase 2 est **attendu** : sans transceiver ni autre
  nœud, PA11 ne relit pas ce que PA12 émet. `LEC = 5` (erreur de bit dominant : un 0
  émis est relu 1) et la montée de TEC par pas de 8 jusqu'au BUS-OFF montrent que la
  détection et le confinement d'erreurs du contrôleur fonctionnent.

## Ce qu'ils n'établissent pas

- **Le débit** : horloge HSI non qualifiée, et le bouclage interne partage la même
  horloge (voir `docs/config_logicielle.md` §8).
- La communication entre nœuds : à faire avec transceivers, ou par un bus à diodes.
