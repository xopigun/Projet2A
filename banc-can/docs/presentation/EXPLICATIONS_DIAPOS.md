# Explications des diapos

Ce document accompagne [Avancement_Bus_CAN_G69.pptx](Avancement_Bus_CAN_G69.pptx), dans sa
version à 13 diapos. Il explique ce que montre chaque diapo et comment répondre aux
questions qu'on risque de nous poser. Les numéros sont ceux de la présentation actuelle.

## Ce qui a changé par rapport à la première version

- Retirées : « Où en est le projet », « Planning » et « Limites connues et prochaines
  étapes ».
- Diapo 2 : l'encadré « Paramètres retenus » est retiré ; T2 devient « Débit et temps de
  bit », car « échantillonnage » était coupé en fin de ligne.
- Diapo 4 : la ligne sur les 120 Ω précise que les résistances sont intégrées et activées
  par interrupteur.
- Diapo 9 : « Heartbeats » et « Arbitrage » remplacés par deux constats visibles dans le
  tableau : messages découpés, réponse en 300 ms.
- Diapo 13 : la phrase sur les démonstrations est retirée.
- Diapo 3 : deux flèches avaient une hauteur négative, ce qui empêchait PowerPoint
  d'ouvrir le fichier. Elles sont corrigées, avec le même tracé.

---

## Diapo 2 : le besoin et les sept tests de validation

Les sept tests sont les essais que le banc doit faire passer à un bus CAN. Ils viennent de
notre dossier de définition (détail dans `banc-can/docs/protocole_validation.md`) :

| Test | Ce qu'on vérifie |
|---|---|
| **T1, couche physique** | les tensions CAN_H / CAN_L et les terminaisons sont correctes |
| **T2, débit** | le bit dure bien 2 µs (±0,485 %), mesuré à l'oscilloscope |
| **T3, arbitrage** | trois nœuds émettent en même temps, le plus petit identifiant doit passer |
| **T4, encodage** | le contenu des trames respecte l'ICD |
| **T5, fautes physiques** | terminaison retirée, CAN_H / CAN_L en court-circuit, nœud débranché : on regarde la réaction |
| **T6, fautes logicielles** | un nœud bavard, au mauvais débit ou qui envoie une longueur incohérente |
| **T7, isolation galvanique** | un nœud à transceiver isolé, placé près d'électronique de puissance, ne dégrade pas le bus. Variante matérielle pas encore conçue : test seulement esquissé |

On les garde parce que c'est la raison d'être du banc. **Attention** : aucun n'a encore été
déroulé en entier. Si on nous demande où on en est, la réponse honnête est « prévus, pas
encore passés ».

## Diapo 3 : l'ICD, une seule source pour tout le monde

L'ICD (*Interface Control Document*) définit chaque message du bus : son identifiant, le
nœud qui l'envoie, et la façon dont chaque valeur est rangée dans les 8 octets (position,
échelle, unité).

- Tout est dans **un seul fichier**, `banc-can/icd/bench_icd.yaml`.
- Un **générateur** (`banc-can/tools/codegen/`) en tire automatiquement :
  - le **code C** des firmwares ;
  - le **Python** des outils PC ;
  - un **fichier DBC**, le format standard que lisent les logiciels CAN (ZCANPRO et
    d'autres) pour décoder les trames ;
  - les **tableaux LaTeX** du dossier.
- **Intérêt** : on change un identifiant à un seul endroit et tout suit. Un test
  automatique vérifie que le code généré est à jour.
- **Les 248 vecteurs de référence** sont des exemples « valeurs → octets attendus ». Le C,
  le Python et la simulation 3D doivent tous donner exactement les mêmes octets.
- Le **formulaire ICD** (`ICD/icd_bus_can_formulaire.pdf`) est ce qu'on donne aux groupes
  partenaires pour qu'ils décrivent leurs messages.

## Diapo 4 : le matériel du banc, et les 120 Ω

Un bus CAN doit être fermé par **120 Ω à chacune de ses deux extrémités**, soit 60 Ω vus
entre CAN_H et CAN_L. Ces résistances absorbent les réflexions du signal.

Ce ne sont pas des résistances à souder : les deux modules les ont intégrées, activables
par un interrupteur.

- l'**USBCAN-Z** a son interrupteur 120 Ω, marqué sur le boîtier ;
- la **CAN Pal** a aussi une terminaison commutable.

Sur notre schéma, N3 est au bout de la ligne : sa CAN Pal est sur **ON**, celles de N1 et
N2 sur **OFF**, et l'USBCAN-Z sur **ON**.

Pour vérifier sur le banc réel, bus **hors tension**, mesurer au multimètre entre CAN_H et
CAN_L :

| Mesure | Signification |
|---|---|
| **60 Ω** | correct |
| **120 Ω** | il manque une terminaison |
| **environ 40 Ω** | il y en a une de trop |

## Diapo 5 : deux modifications sur chaque Nucleo

- **Cavalier HW1** : livré fermé, il relie PA12 (FDCAN1_TX) à la masse. Le bus reste alors
  bloqué en état dominant et rien ne passe. Il faut le retirer.
- **Ponts SB9 et SB10** : à souder pour brancher le quartz 24 MHz (voir aussi le problème 5
  de la diapo 12). Fait et vérifié sur les trois cartes : l'horloge tourne sur le quartz,
  PLL à 160 MHz.

## Diapo 7 : les firmwares, une architecture en couches

On la lit de bas en haut :

1. **`board.h`** : tout le brochage d'une carte, dans un seul fichier par carte.
2. **Pilotes FDCAN / bxCAN** : un pilote par type de contrôleur CAN. FDCAN pour le
   STM32G431 de nos Nucleo, bxCAN pour la Blue Pill (F103) et la L476.
3. **Interface CAN abstraite (`can_if.h`)** : les mêmes fonctions (ouvrir, émettre,
   recevoir, lire l'état d'erreur) quel que soit le microcontrôleur.
4. **Application commune**, identique sur toutes les cartes :
   - le **heartbeat** : chaque nœud annonce régulièrement son état ;
   - l'**arbitrage ARM/GO** : le PC arme les nœuds, puis leur dit d'émettre en même temps ;
   - les **fautes commandées à distance** (`BENCH_CFG`) ;
   - l'**écran LCD**.

L'intérêt : le même code applicatif tourne sur trois microcontrôleurs, et on peut le tester
sur PC sans carte.

À droite de la diapo :

- **autotest** : la carte se parle d'abord à elle-même (bouclage interne), puis échange avec
  une autre carte ;
- **tests unitaires sur PC** : le code commun est testé sans matériel ;
- **presets CMake** : une commande pour compiler le bon firmware selon le nœud et le mode
  (`n1`, `n1-selftest`, `n1-dialogue`…) ;
- **afficheurs LCD 16×2** : dernière trame reçue et état du contrôleur.

## Diapo 9 : la démonstration du 03/11

Les quatre constats du bas :

- **Messages découpés** : une trame CAN ne porte que 8 octets. On garde 1 octet pour le
  numéro du morceau, il reste 7 caractères de texte par trame. « M'entends tu ? » part donc
  en deux trames : ce sont les lignes « morceau 1/2 » du tableau.
- **Réponse en 300 ms** : chaque nœud répond 300 ms après avoir reçu le message, ce qu'on
  lit dans la colonne Temps (4,280 s → 4,580 s → 4,879 s).
- **Appels du PC** : le PC envoie un appel sur l'identifiant 0x0B0, le nœud appelé répond
  « Ici Nn » sur 0x0B0 + n. On le voit dans `captures/03_gros_plan_appels_du_PC.png`, pas
  dans le tableau de cette diapo.
- **0 erreur** : les compteurs d'erreurs des contrôleurs (TEC et REC) sont restés à 0. Ce
  n'est pas non plus visible dans ce tableau.

Les heartbeats et l'arbitrage (0x100 passe avant 0x200) ont bien été observés sur le bus,
mais ils ne se voient pas sur la capture : c'est pour ça qu'ils ont été retirés de la diapo.

## Diapo 11 : les composants de notre adaptateur USB-CAN

| Composant | Rôle |
|---|---|
| **Fiche USB-A** | se branche directement sur le PC, comme une clé USB : alimentation 5 V et données |
| **ESD USBLC6** | protège les lignes USB contre les décharges électrostatiques |
| **CH340C** | convertisseur USB ↔ série : le PC voit un port COM. Il permet aussi de programmer le STM32 sans sonde, avec le bouton BOOT0 |
| **STM32G431** | le microcontrôleur, avec son contrôleur CAN. Il traduit les commandes série du PC en trames CAN, et inversement. Même famille que nos Nucleo |
| **TJA1051T/3** | le transceiver : transforme les signaux logiques TX/RX (0 / 3,3 V) du microcontrôleur en signal différentiel CAN_H / CAN_L. La version /3 accepte une logique en 3,3 V |
| **Bornier à vis** (J2) | prise vers le bus CAN : 3 bornes H (CAN_H), L (CAN_L) et G (masse), dans le même ordre que l'USBCAN-Z. On y visse directement les fils du bus. Il remplace le connecteur DB9 de la première version |

Autour, il y a :

- un régulateur 5 V → 3,3 V (AMS1117) ;
- un quartz 8 MHz, pour une horloge assez précise pour le CAN ;
- une terminaison 120 Ω sur cavalier ;
- les LED alimentation, RX et TX ;
- les boutons RESET et BOOT0 ;
- un connecteur de programmation SWD.

**À savoir si on nous pose la question** : la carte n'est pas encore fabriquée, et son
firmware reste à écrire. On pourra adapter le pont série-CAN qui existe déjà pour la L476.

Sources : `banc-can/hardware/adaptateur_usb_can/` et sa vérification composant par
composant, `SOURCES_COMPOSANTS.md`.

## Diapo 12 : les difficultés, une par une

1. **Débordement de tampon.** Quand la bibliothèque HAL de ST reçoit certaines trames
   (longueur annoncée de 9 à 15, légale en CAN 2.0), elle recopie jusqu'à 64 octets. Notre
   tampon n'en faisait que 8 : de la mémoire voisine était écrasée. Correction : tampon de
   64 octets, longueur ramenée à 8.
2. **Nœuds figés au démarrage.** Il manquait la fonction d'interruption SysTick. Le
   compteur de millisecondes ne bougeait jamais, et la première attente durait à l'infini,
   environ 1 ms après le démarrage. Correction : fonction ajoutée, avec une vérification à
   la compilation qu'elle existe bien.
3. **Horodatages figés.** Les trames sont datées par un compteur de cycles du processeur
   (DWT). En se déconnectant, STM32CubeProgrammer arrête ce compteur : toutes les dates
   restaient bloquées. Correction : le compteur est relancé à chaque lecture.
4. **Écarts du dossier v0.1.** Notre premier dossier utilisait la broche PB9, qui n'existe
   pas sur le boîtier 32 broches du STM32G431, et plaçait une LED sur PA2, déjà prise par
   le port COM du ST-LINK. Correction : brochage revu, I2C sur PA15 / PB7 et LED sur PB8.
5. **Horloge trop imprécise.** De base, la Nucleo tourne sur son oscillateur interne
   (HSI) à ±1 %, alors que notre réglage CAN tolère 0,485 %. Ça peut marcher par chance,
   mais aucune mesure n'aurait valeur de preuve. Correction : souder SB9 et SB10 pour
   brancher le quartz 24 MHz, fait et vérifié sur les trois cartes.
6. **CANable non commandable.** L'interface USB-CAN prévue (CANable 2.0) ne pouvait pas
   être commandée. En attendant, on a utilisé l'USBCAN-Z trouvée sur place, et on a conçu
   notre propre adaptateur (diapo 11).
