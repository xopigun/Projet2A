# Configuration logicielle du contrôleur CAN

Destiné à remplir la **section 6 du dossier de définition**, laissée en `\todo{}` dans la
v0.1. L'extrait LaTeX correspondant est [latex/config_logicielle.tex](latex/config_logicielle.tex),
à inclure par `\input{}`.

Toutes les valeurs numériques citées ici sont celles inscrites dans
`firmware/boards/nucleo_g431kb/board.h`, qui fait autorité. Un test de la suite Python
échoue si ce document diverge du code.

---

## 1. Arbre d'horloge

### 1.1 Pourquoi pas le HSI

La tolérance d'écart d'horloge admissible à 500 kbit/s avec le temps de bit retenu est de
**0,485 %** (calcul en §3.3). Les deux sources disponibles sur la carte donnent :

| Source | Précision | Verdict |
|---|---|---|
| Quartz X2, 24 MHz | 20 ppm = **0,002 %** | marge d'un facteur 240 |
| HSI16 | **±1 %** de dérive thermique (0–85 °C), plus −0,75 / +0,5 % d'étalonnage d'usine | **plus du double de ce qui est admissible** |

Le HSI est donc exclu comme référence CAN. Ce n'est pas une marge de confort : deux nœuds
sur HSI peuvent dériver l'un de l'autre de 2 % dans le pire cas, soit quatre fois la
tolérance, et les erreurs de trame deviennent aléatoires — c'est-à-dire indiscernables d'un
défaut du bus, ce qui ruine la valeur de preuve du banc.

> Source : **DS12589** Rev 6, Table 42. L'étalonnage d'usine (15,88 à 16,08 MHz à 30 °C)
> et la dérive thermique se cumulent : ±1 % est donc un minimum, pas un pire cas.

### 1.2 Contrainte matérielle

La NUCLEO-G431KB démarre sur le **HSI** en sortie d'usine : SB8, SB9, SB10, SB11 et SB13
sont tous ouverts (UM2397 §6.5 et Table 9). Le quartz est monté mais déconnecté.
**Souder SB9 et SB10** est donc une étape obligatoire du montage, décrite dans
[bringup.md](bringup.md) §1.2.

Un repli sur HSI reste compilable (`-DBENCH_CLOCK_SOURCE=2`) pour travailler avant cette
soudure. Il se signale de trois façons — avertissement à la compilation, bandeau
`HSI - NON VALIDE` sur l'écran, bit `clock_not_qualified` dans le heartbeat — et interdit à
`canbench` de prononcer un verdict de réussite.

### 1.3 Configuration retenue

| Étage | Valeur | Résultat |
|---|---|---|
| Source | HSE, quartz X2 | 24 MHz |
| `PLLM` | ÷ 3 | 8 MHz (entrée PLL, plage 2,66–16 MHz) |
| `PLLN` | × 40 | VCO 320 MHz (plage 96–344 MHz) |
| `PLLR` | ÷ 2 | **SYSCLK = 160 MHz** |
| `PLLQ` | ÷ 4 | **horloge noyau FDCAN = 80 MHz** |
| `AHB`, `APB1`, `APB2` | ÷ 1 | 160 MHz |
| Échelle de tension | `SCALE1_BOOST` | requise au-delà de 150 MHz |
| Latence flash | 4 états d'attente | |

L'horloge du FDCAN est prise sur **`PLLQ`** et non sur `PCLK1` : c'est ce qui permet
d'obtenir 80 MHz tout en gardant 160 MHz pour le cœur.

**SYSCLK est volontairement à 160 MHz et non au maximum de 170 MHz.** C'est le prix d'un
point d'échantillonnage exactement à 87,5 %, partagé avec le F103 : à 170 MHz sur `PCLK1`,
le meilleur candidat tombe à 88,24 %, qui ne s'aligne pas. 160 MHz reste très largement
suffisant pour ce banc, dont la charge de calcul est négligeable.

> Plages vérifiées : **DS12589** Rev 6, Table 45 (entrée PLL, VCO, sorties jusqu'à
> 170 MHz en Range 1 Boost) et **RM0440** Rev 9, §7.4.4 (`8 ≤ PLLN ≤ 127`,
> `1 ≤ PLLM ≤ 16`). Latence flash : RM0440 Table 9, 4 états d'attente jusqu'à 170 MHz.

---

## 2. Protocole : CAN 2.0A classic

> **« FDCAN » désigne le périphérique, pas le protocole.** Le contrôleur du STM32G431
> s'appelle FDCAN parce qu'il *sait* faire du CAN FD. Le protocole effectivement utilisé par
> le banc, et par le standard commun aux groupes partenaires, est **CAN 2.0A classic** :
> identifiants 11 bits, charge utile de 8 octets au plus, pas de commutation de débit.
> Cette distinction doit apparaître telle quelle dans le dossier, sans quoi un lecteur peut
> croire que le bus est en CAN FD.

### 2.1 Configuration

| Paramètre | Valeur | Justification |
|---|---|---|
| `Init.FrameFormat` | `FDCAN_FRAME_CLASSIC` | CAN 2.0A |
| En-tête TX : `FDFormat` | `FDCAN_CLASSIC_CAN` | aucune trame FD émise |
| En-tête TX : `BitRateSwitch` | `FDCAN_BRS_OFF` | pas de commutation de débit |
| En-tête TX : `IdType` | `FDCAN_STANDARD_ID` | identifiants 11 bits |
| DLC | ≤ 8 | limite du CAN 2.0 |
| Débit | 500 kbit/s | |
| `ProtocolException` | désactivée | comportement CAN 2.0 strict |
| `TransmitPause` | désactivée | insérerait deux temps de bit entre trames et fausserait le test d'arbitrage |
| Mode d'émission | `FDCAN_TX_QUEUE_OPERATION` | la file trie par priorité d'identifiant |

### 2.2 Verrouillage, à trois niveaux

Une dérive vers du CAN FD ou des identifiants 29 bits ne doit pas pouvoir se découvrir sur
le banc. Trois garde-fous interviennent à trois moments différents :

| Niveau | Quand | Mécanisme |
|---|---|---|
| **1** | à la génération | Le validateur de l'ICD refuse un identifiant hors 11 bits ou un DLC supérieur à 8 |
| **2** | à la compilation | `icd_gen.h` émet un `_Static_assert` par trame : le build casse si une constante générée s'en écarte |
| **3** | à l'exécution | `tx_common()` refuse d'émettre une trame non conforme ; `port_open()` refuse d'ouvrir si `FrameFormat` a dérivé |

Le niveau 2 couvre les constantes de l'ICD, le niveau 3 les trames construites
dynamiquement — notamment celles issues d'une commande `BENCH_CFG`.

### 2.3 Détection en réception

Deux compteurs, remontés dans le heartbeat et saturant à 255 :

| Compteur | Ce qu'il compte |
|---|---|
| `non_classic_rx` | Trames que le contrôleur signale au format CAN FD |
| `ext_id_rx` | Trames reçues avec un identifiant 29 bits |

Les trames à identifiant étendu sont **comptées mais non transmises** à la couche
applicative : ce sont des trames CAN 2.0B parfaitement valides électriquement, mais elles
n'appartiennent pas à l'ICD.

> **Nuance sur `non_classic_rx`.** Une trame CAN FD circulant sur un bus configuré en
> classic est le plus souvent rejetée au niveau protocole — le bit FDF, réservé dominant en
> CAN 2.0, provoque une erreur de forme — et n'atteint jamais la couche de réception. Elle
> se manifeste alors par un `LEC` en erreur de forme et un `REC` qui grimpe, pas par ce
> compteur. `non_classic_rx` ne capte que ce que le contrôleur accepte de présenter ; il est
> conservé par précaution, mais **le signal principal d'une trame FD sur le bus reste
> l'erreur de forme**. À retenir pour le dépouillement de T6.

Côté PC, `canbench` ouvre l'interface en classic (`fd=False`) et signale toute trame FD ou
étendue reçue.

---

## 3. Temps de bit

### 3.1 Valeurs retenues

| Nœud | Horloge noyau | Prescaler | Durée du bit | Segments | SJW | Point d'éch. |
|---|---|---|---|---|---|---|
| **G431** (N1–N3) | 80 MHz | **10** | **16 tq** | 1 + 13 + 2 | **2** | **87,50 %** |
| **F103** (N4) | 36 MHz (APB1) | **9** | **8 tq** | 1 + 6 + 1 | **1** | **87,50 %** |

Vérification : 80 000 000 / (10 × 16) = 500 000 bit/s, et (16 − 2) / 16 = 0,875 exactement.
Le point d'échantillonnage à 87,5 % est la recommandation CiA.

Ces valeurs ne sont pas recopiées : elles sont **relues depuis les `board.h` et vérifiées**
par `scripts/bit_timing.py --check`, qui échoue si un nœud dévie ou si les nœuds ne
partagent pas le même point d'échantillonnage. La CI l'exécute à chaque compilation.

### 3.2 Correspondance avec les registres

| Grandeur | FDCAN (G431) | bxCAN (F103) |
|---|---|---|
| Prescaler | `NBTP.NBRP` = 10 | `BTR.BRP` = 9 |
| Segment 1 | `NBTP.NTSEG1` = 13 | `BTR.TS1` = 6 |
| Segment 2 | `NBTP.NTSEG2` = 2 | `BTR.TS2` = 1 |
| Saut de resynchronisation | `NBTP.NSJW` = 2 | `BTR.SJW` = 1 |

Attention à la convention d'écriture : les champs de registre valent souvent la valeur
moins un. La HAL s'en charge ; les valeurs ci-dessus sont celles passées à la HAL, en
quanta de temps.

### 3.3 Tolérance d'oscillateur

Deux conditions d'ISO 11898-1, la plus contraignante étant retenue :

```
df ≤ SJW / (20 · NBT)
df ≤ min(PS1, PS2) / (2 · (13 · NBT − PS2))
```

| Nœud | Condition 1 | Condition 2 | **Retenu** |
|---|---|---|---|
| G431 | 2 / (20 × 16) = 0,625 % | 2 / (2 × (208 − 2)) = 0,485 % | **0,485 %** |
| F103 | 1 / (20 × 8) = 0,625 % | 1 / (2 × (104 − 1)) = 0,485 % | **0,485 %** |

### 3.4 Le SJW de 1 du F103 n'est pas un handicap

C'est le point le plus contre-intuitif de cette configuration, et il mérite d'être explicité
dans le dossier.

À point d'échantillonnage égal, la tolérance ne dépend que du **rapport** SJW/NBT, pas de
SJW en valeur absolue. Ici 1/8 = 2/16, et les deux nœuds obtiennent **exactement la même
tolérance de 0,485 %**.

Les alternatives à plus grand nombre de quanta sont d'ailleurs **moins bonnes**, parce que
bxCAN limite `TS1` à 16 tq et `TS2` à 8 tq. Le seul autre candidat raisonnable à 36 MHz est
`BRP = 4`, 18 tq, segments 1 + 15 + 2 : il donne 88,89 %, donc un point d'échantillonnage
**différent de celui du G431** — rédhibitoire — pour une tolérance **inférieure** (0,431 %).

La seule conséquence réelle du SJW de 1 est la **granularité** de la resynchronisation : un
pas vaut 12,5 % du temps de bit sur le F103 contre 6,25 % sur le G431. Cela joue sur la
finesse de rattrapage d'un déphasage, pas sur l'écart d'horloge tolérable.

---

## 4. Filtres d'acceptation

**Aucun filtre n'est configuré** : toutes les trames sont acceptées dans `RX FIFO 0`.

| Paramètre | Valeur |
|---|---|
| `StdFiltersNbr`, `ExtFiltersNbr` | 0 |
| Trames standard non filtrées | `FDCAN_ACCEPT_IN_RX_FIFO0` |
| Trames étendues non filtrées | `FDCAN_ACCEPT_IN_RX_FIFO0` |
| Trames distantes | `FDCAN_FILTER_REMOTE` |

C'est un choix, pas un oubli. Un banc de test doit voir **tout** le trafic, y compris les
trames qu'il n'attend pas : c'est ce qui permet de détecter un *babbling idiot*, un
identifiant inattendu émis par un partenaire, ou une trame au DLC incohérent. Un filtre
masquerait précisément ce que le banc doit mettre en évidence.

Le tri est fait en logiciel, à partir de la table de trames générée depuis l'ICD
(`bench_frame_by_id()`).

---

## 5. Retransmission automatique

**Activée**, sur les deux ports.

C'est une condition de validité du test d'arbitrage, pas une option de confort : sans
retransmission automatique, un nœud qui perd l'arbitrage **abandonne sa trame**. N2 et N3
n'émettraient jamais après avoir perdu contre N1, le classement serait vide et le test ne
démontrerait rien.

| Contrôleur | Réglage |
|---|---|
| FDCAN | `Init.AutoRetransmission = ENABLE` (soit `CCCR.DAR = 0`) |
| bxCAN | `NART = 0` |

Le champ est exposé dans `bench_can_config_t.auto_retransmit` afin de pouvoir le désactiver
volontairement lors d'un test de robustesse, jamais en fonctionnement nominal.

---

## 6. Politique de bus-off

Deux politiques, identiques dans leur effet sur les deux ports, choisies par
`bench_can_config_t.busoff_policy` et reconfigurables en marche par `BENCH_CFG` :

| Politique | Comportement |
|---|---|
| `BENCH_BUSOFF_AUTO` (défaut) | Reprise dès les 128 × 11 bits récessifs écoulés |
| `BENCH_BUSOFF_MANUAL` | Maintien en bus-off jusqu'à commande explicite |

Le mode manuel existe pour les tests de fautes : il laisse le temps d'observer et de
photographier l'état `bus-off` sur l'écran et les LEDs avant que le nœud ne reparte.

### Différence de mise en œuvre entre les deux contrôleurs

C'est le point où les deux ports divergent réellement, et il mérite d'être noté dans le
dossier :

- **bxCAN** dispose du bit matériel `ABOM` (*automatic bus-off management*) : la reprise est
  entièrement gérée par le périphérique.
- **FDCAN n'a pas d'équivalent.** La reprise est **logicielle** : il faut remettre à zéro le
  bit `CCCR.INIT` pour lancer la séquence de reprise. C'est fait par
  `bench_g431_can_poll()`, appelée depuis la boucle principale.

Le comportement observable est identique ; seule l'implémentation diffère.

---

## 7. Mode silencieux

Le mode silencieux — écoute sans acquittement — utilise le **mode moniteur du contrôleur**,
et non la broche `S` du transceiver.

| Contrôleur | Réglage |
|---|---|
| FDCAN | `CCCR.MON` (`FDCAN_MODE_BUS_MONITORING`) |
| bxCAN | `BTR.SILM` |

Trois raisons à ce choix :

1. **Sémantique identique** sur les deux microcontrôleurs, alors que la broche 8 des deux
   transceivers envisagés ne fait pas la même chose : `S` du TJA1051 coupe l'émetteur en
   gardant le récepteur pleinement actif, tandis que `RS` du SN65HVD230 place le composant en
   *standby*, où le récepteur est dégradé.
2. **Aucune broche supplémentaire** n'est nécessaire.
3. Il couvre aussi le mode de faute « **arrêt d'acquittement** » de N4, qui n'existe pas
   séparément : ni bxCAN ni FDCAN n'offrent de « ne pas acquitter » indépendant, et le mode
   moniteur est le seul moyen de ne pas acquitter.

La broche `S` reste pilotable si `board.h` la définit, en complément.

---

## 8. Mode bouclage interne

`FDCAN_MODE_INTERNAL_LOOPBACK`, exposé par `bench_can_config_t.loopback`. Le contrôleur se
reçoit lui-même sans rien émettre sur les broches : **ni transceiver ni bus câblé ne sont
nécessaires**.

C'est la base de la phase 1 de l'autotest de mise en route ([bringup.md](bringup.md) §3).

### Ce que le bouclage valide, et ce qu'il ne valide pas

| Validé | Non validé |
|---|---|
| Le PLL verrouille | **Le débit réel** |
| Les valeurs de temps de bit sont acceptées par le contrôleur | La fréquence absolue de l'horloge |
| L'interruption de réception et le tampon circulaire | |
| L'encodage de l'ICD, octet par octet | |

**Le bouclage interne ne peut pas établir le débit**, et c'est structurel : l'émetteur et le
récepteur sont le même périphérique, cadencés par la même horloge noyau. Une PLL mal
configurée se boucle sur elle-même sans la moindre erreur. Un nœud réglé à 400 kbit/s au
lieu de 500 passe le bouclage sans broncher.

Le même raisonnement s'applique à un échange entre **deux nœuds de configuration
identique** : s'ils sont faux, ils le sont de la même façon et se comprennent parfaitement.
Une erreur d'horloge commune est invisible entre pairs identiques.

Établir le débit demande donc une **référence indépendante** :

1. le **CANable**, dont le quartz n'a aucun rapport avec celui des Nucleo — s'il échange
   sans erreur, les deux débits coïncident réellement ;
2. une **mesure à l'oscilloscope** du temps de bit sur CAN_H − CAN_L : 2,000 µs attendus,
   bande d'acceptation 1,990 à 2,010 µs (± 0,485 %, cf. §3.3), mais **2,000 µs à quelques
   ppm près** avec une configuration correcte, puisque le quartz est à 20 ppm.

C'est l'objet de l'étape 6 bis de la mise en route et du test **T2** du protocole de
validation.

---

## 9. Architecture temps réel

| Élément | Choix |
|---|---|
| Interruption de réception | Recopie la trame horodatée dans le tampon circulaire, **et rien d'autre** |
| Priorité NVIC | 1 (au-dessus des traitements applicatifs) |
| Tampon circulaire | 64 trames, producteur et consommateur uniques, sans section critique |
| Saturation | La trame est **rejetée**, jamais écrasée |
| Horodatage | Compteur de cycles DWT, résolution de l'ordre de la microseconde |
| Boucle principale | Coopérative : décodage, écran, capteurs, heartbeat |

Deux points appellent une justification.

**L'ISR ne fait que recopier.** Le rafraîchissement complet de l'écran demande ≈ 23 ms, soit
la durée d'environ 105 trames. Effectué dans l'ISR, il ferait déborder la file de réception,
et le banc mesurerait ses propres retards logiciels au lieu du comportement du bus.

**En saturation, on rejette sans écraser.** Écraser la trame la plus ancienne fausserait
l'ordre de réception, dont se déduit le rang d'arbitrage. Mieux vaut perdre une trame en le
sachant que mesurer un classement faux.

Le compteur de millisecondes de la HAL est insuffisant pour l'horodatage : une trame de
8 octets dure ≈ 220 µs, donc l'ordre des trames d'un cycle d'arbitrage ne serait pas
discernable. D'où le recours au compteur de cycles DWT.

---

## 10. Distinction des pertes

Le heartbeat remonte **deux** compteurs de perte distincts, et cette distinction est
délibérée :

| Signal | Origine | Ce qu'il signale |
|---|---|---|
| `rx_fifo_lost` | FIFO matérielle du contrôleur (`RF0L`) | Le logiciel n'a pas vidé la FIFO assez vite |
| `ring_overflow` | Tampon circulaire logiciel | La boucle principale n'a pas suivi |

Les confondre reviendrait à ne plus pouvoir distinguer une surcharge du bus d'un défaut de
notre propre logiciel. Aucun des deux ne doit être non nul en fonctionnement nominal ; s'ils
le sont, le résultat du test est suspect et doit être signalé comme tel.

De la même manière, **aucun compteur d'erreur n'est réimplémenté en logiciel**. `TEC`, `REC`,
l'état du contrôleur et le dernier code d'erreur sont lus directement dans les registres
`PSR` et `ECR` (FDCAN) ou `ESR` (bxCAN). Un compteur logiciel refléterait notre
interprétation du protocole, pas le comportement réel du matériel.

---

## 11. Résumé pour la nomenclature logicielle

| Paramètre | G431 (N1–N3) | F103 (N4) |
|---|---|---|
| Périphérique | FDCAN1 en mode Classic | bxCAN |
| Référence d'horloge | HSE 24 MHz (quartz X2, 20 ppm) | HSE 8 MHz |
| Horloge noyau CAN | 80 MHz (PLLQ) | 36 MHz (APB1) |
| Prescaler | 10 | 9 |
| Durée du bit | 16 tq | 8 tq |
| Segments (sync + 1 + 2) | 1 + 13 + 2 | 1 + 6 + 1 |
| SJW | 2 | 1 |
| Point d'échantillonnage | 87,50 % | 87,50 % |
| Tolérance d'oscillateur | 0,485 % | 0,485 % |
| Débit | 500 kbit/s | 500 kbit/s |
| Filtres | aucun | aucun |
| Retransmission automatique | activée | activée |
| Bus-off | reprise logicielle (`CCCR.INIT`) | `ABOM` matériel |
| Mode silencieux | `CCCR.MON` | `BTR.SILM` |

> Les valeurs de la colonne F103 sont **calculées et vérifiées** par
> `scripts/bit_timing.py`, mais le port n'est pas encore écrit : il attend RM0008, DS5319 et
> le schéma de la carte (lot 5).
