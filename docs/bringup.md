# Mise en route du banc — procédure pas à pas

Cette procédure amène trois cartes NUCLEO-G431KB neuves à un bus CAN qui communique.
Elle est conçue pour être exécutée **dans l'ordre**, chaque étape ne dépendant que des
précédentes, et pour que chaque échec désigne une cause unique.

Le principe est de repousser le plus tard possible ce qui peut faire douter : l'étape 3
valide la logique du nœud et l'encodage **sans transceiver ni fil de bus**. Si elle passe,
tout défaut ultérieur vient du câblage.

> **Le débit n'est établi qu'à l'étape 6 bis.** Ni le bouclage interne ni l'échange entre
> deux Nucleo identiques ne le prouvent : dans les deux cas, émetteur et récepteur partagent
> la même horloge ou la même configuration d'horloge, donc une erreur commune est invisible.
> Il faut une référence indépendante — le CANable ou l'oscilloscope.

Prévoir environ 1 h pour trois cartes, fer à souder compris.

---

## Ce qu'il faut sous la main

| Matériel | Quantité | Remarque |
|---|---|---|
| NUCLEO-G431KB | 3 | N1, N2, N3 |
| TJA1051**T/3** (module ou circuit + support) | 3 | la variante importe — voir [pinout.md](pinout.md) §5 |
| Câble USB Type-A vers Micro-B | 1 au moins | alimentation et ST-LINK |
| Résistances 120 Ω | 2 | terminaisons `R_T1` et `R_T2` |
| Condensateurs 100 nF | 6 | découplage `VCC` et `VIO` de chaque transceiver |
| Multimètre | 1 | mesure de continuité et de résistance |
| Fer à souder à panne fine | 1 | ponts SB9/SB10 |
| **Oscilloscope** + sonde différentielle | 1 | **nécessaire à l'étape 6 bis** : c'est lui qui établit le débit |
| CANable 2.0 | 1 | référence d'oscillateur indépendante, étape 6 bis |

Côté logiciel : voir les prérequis du [README](../README.md). Un terminal série est
nécessaire (PuTTY, TeraTerm, `screen`, l'onglet série de VS Code…) réglé sur
**115200 bauds, 8N1, sans contrôle de flux**.

---

## Étape 1 — Les deux modifications matérielles

> Ces deux gestes sont **obligatoires**. Les omettre produit des symptômes qui ressemblent
> à des pannes matérielles et non à des erreurs de montage : c'est ce qui coûte le plus de
> temps à diagnostiquer.

### 1.1 Retirer le cavalier HW1 — sur chaque carte

La carte est livrée avec un cavalier 2,54 mm entre **CN4 broche 5** (`D2`) et **CN4 broche 4**
(`GND`), sur la face inférieure (UM2397 §5.1 étape 5, §6.1).

`D2` est **PA12**, c'est-à-dire `FDCAN1_TX`. Laissé en place, ce cavalier maintient l'entrée
TXD du transceiver à 0, donc le bus en **état dominant permanent** : plus aucun nœud ne peut
communiquer, y compris les autres.

**Contrôle :** multimètre en continuité, entre CN4-4 et CN4-5. Doit être **ouvert**.

### 1.2 Souder SB9 et SB10 — sur chaque carte

En sortie d'usine la carte démarre sur le **HSI** : SB8, SB9, SB10, SB11 et SB13 sont tous
ouverts (UM2397 §6.5 et Table 9). Le quartz 24 MHz X2 est monté sur la carte mais
**déconnecté**.

Le HSI est spécifié à ±1 %, soit plus du double de la tolérance admissible de **0,485 %** à
500 kbit/s (voir [bit_timing.md](bit_timing.md)). Deux nœuds sur HSI peuvent communiquer par
chance, mais aucune mesure n'aurait valeur de preuve.

SB9 et SB10 sont sur la face inférieure, près du quartz X2. Les ponter à l'étain.

**Contrôle :** continuité entre chaque pastille du pont. À défaut, l'étape 3 affichera
`HSE 24MHz` ou `HSI - NON VALIDE`, ce qui tranche sans ambiguïté.

> **Si les encadrants n'ont pas encore validé cette soudure**, il est possible de continuer
> en compilant avec `-DBENCH_CLOCK_SOURCE=2`. Le firmware émet alors un avertissement à la
> compilation, affiche `HSI - NON VALIDE` et lève le bit `clock_not_qualified` dans son
> heartbeat, ce qui empêche `canbench` de prononcer un verdict de réussite. **Les étapes 3
> et 4 restent exécutables** et gardent tout leur intérêt de mise au point.

---

## Étape 2 — Compiler et programmer l'autotest

Rien n'est encore câblé : ni transceiver, ni bus. Seule la carte et son câble USB.

```bash
git clone --recursive <url> banc-can
cd banc-can
cmake --preset n1-selftest
cmake --build --preset n1-selftest
```

Le résumé de taille doit s'afficher en fin de compilation (environ 36 Ko de flash, 28 %).

Programmer la carte :

```bash
cmake --build --preset n1-selftest --target flash_n1
```

`STM32_Programmer_CLI` et `openocd` sont cherchés dans le `PATH` puis dans les emplacements
d'installation usuels. Si aucun n'est trouvé, la cible l'indique et donne la variable à
renseigner.

Répéter avec `n2-selftest` et `n3-selftest` pour les deux autres cartes.

---

## Étape 3 — Phase 1 : bouclage interne, sans transceiver

Ouvrir le terminal série sur le port COM de la carte, puis appuyer sur le bouton **RESET**
(B1). Le FDCAN est configuré en `FDCAN_MODE_INTERNAL_LOOPBACK` : il se reçoit lui-même, rien
n'est émis sur PA12.

### Résultat attendu

```
============================================================
 Autotest du banc CAN — noeud N1 — Nucleo-G431KB
============================================================
  Horloge     : HSE 24MHz
  FDCAN       : 80000000 Hz
  Temps de bit: BRP=10, 1+13+2 tq, SJW=2 -> 500000 bit/s, SP=87,50 %

=== Phase 1 : bouclage interne (aucun transceiver requis) ===
  [ARM           ] ok  id=0x010 dlc=8
  [GO            ] ok  id=0x011 dlc=8
  [BENCH_CFG     ] ok  id=0x012 dlc=8
  [BENCH_RESULT  ] ok  id=0x013 dlc=8
  [HEARTBEAT     ] ok  id=0x781 dlc=8
  [ENERGY_COMMAND] ok  id=0x100 dlc=8
  [IMU_SPEED     ] ok  id=0x200 dlc=8
  [TEMP_BATTERY  ] ok  id=0x300 dlc=8
  apres phase 1  etat=error-active   TEC=  0 REC=  0 LEC=0 pertes_fifo=0 tampon=0
  Resultat : 8/8 trames correctes.
```

**Ce que cette phase démontre :** le PLL verrouille ; les valeurs de temps de bit sont
acceptées par le contrôleur ; l'interruption de réception fonctionne ; le tampon circulaire
transporte les trames sans perte ; l'encodage est correct octet par octet.

**Ce qu'elle ne démontre pas : le débit réel.** En bouclage interne, l'émetteur et le
récepteur sont le même périphérique et partagent l'horloge noyau. Une PLL mal configurée se
boucle sur elle-même sans erreur, et un nœud tournant à 400 kbit/s passerait cette phase
sans broncher. Le débit relève de l'étape 6 bis.

### Diagnostic

| Symptôme | Cause probable | Action |
|---|---|---|
| Rien ne s'affiche | Terminal mal réglé, ou mauvais port COM | 115200 8N1 ; vérifier le port dans le gestionnaire de périphériques |
| Rien ne s'affiche, port COM absent | Pilote ST-LINK, ou carte non alimentée | LED LD4 (5V_PWR) doit être allumée |
| `Horloge : HSI - NON VALIDE` | SB9/SB10 non soudés, ou compilé avec `-DBENCH_CLOCK_SOURCE=2` | Étape 1.2, puis recompiler sans l'option |
| La carte reste muette après la bannière | Échec de `bench_clock_config()` : le quartz ne démarre pas | Reprendre la soudure de SB9/SB10 ; vérifier qu'il n'y a pas de court-circuit |
| `ECHEC : aucune trame recue en 50 ms` | Interruption non déclenchée, ou temps de bit refusé | Le contrôleur n'est pas en cause ici, le bouclage est interne : vérifier que la carte est bien un G431KB |
| `ECHEC : octet N recu 0xXX` | Régression dans le code généré | `python -m tools.codegen --check`, puis `ctest --preset host` |

> **Tant que la phase 1 n'est pas verte, ne pas câbler le bus.** Le message le dit : à ce
> stade, un échec vient de la carte ou de sa configuration, jamais du câblage.

Faire passer l'étape 3 sur les **trois** cartes avant de continuer.

---

## Étape 4 — Câbler un nœud

Pour chaque carte, câbler le transceiver selon [pinout.md](pinout.md) §5 :

| Nucleo | TJA1051T/3 |
|---|---|
| PA12 — CN4-5 (`D2`) | 1 `TXD` |
| PA11 — CN4-13 (`D10`) | 4 `RXD` |
| 3V3 — CN3-14 | 5 `VIO` |
| 5V — CN3-4 | 3 `VCC` |
| GND — CN4-4 | 2 `GND` |
| — | 8 `S` → GND |

Un condensateur de 100 nF entre `VCC` et `GND`, un autre entre `VIO` et `GND`, au plus près
du composant.

### Contrôles avant mise sous tension

1. **`VCC` du transceiver est bien sur 5 V**, pas sur 3,3 V. Le TJA1051T/3 exige 4,5 à 5,5 V
   côté bus ; c'est `VIO` qui est en 3,3 V.
2. **CN4-4 et CN4-5 toujours ouverts** — si HW1 a été remis par mégarde, on le verra ici.
3. Un nœud est alimenté **soit** par le rail 5 V du banc, **soit** par son USB, jamais les
   deux simultanément.

---

## Étape 5 — Câbler le bus et vérifier les terminaisons

Relier les nœuds en ligne, dérivations les plus courtes possible (≤ 0,3 m), avec une
résistance de 120 Ω à **chaque extrémité physique** de la ligne, et **uniquement là**.

### Contrôle décisif, hors tension

Multimètre en ohmmètre entre **CAN_H et CAN_L**, bus entièrement assemblé, SW1 fermé :

| Mesure | Interprétation | Action |
|---|---|---|
| **≈ 60 Ω** | Correct : deux terminaisons de 120 Ω en parallèle | Continuer |
| ≈ 120 Ω | Une seule terminaison | SW1 ouvert, ou `R_T2` absente |
| **< 40 Ω** | Terminaisons surnuméraires | Des modules portent encore leur 120 Ω — voir ci-dessous |
| ≫ 120 Ω | Aucune terminaison, ou ligne coupée | Reprendre le câblage |

> **Si les modules transceiver portent un 120 Ω soudé**, le retirer **sur les quatre nœuds**,
> N1 compris. Dans la topologie du dossier, aucun nœud n'est en bout de ligne : une
> terminaison en bout de dérivation ne termine pas la ligne principale et ajoute des
> réflexions. Avec quatre modules terminés plus les deux résistances discrètes, le bus
> verrait 20 Ω et aucun niveau dominant ne pourrait s'établir.
>
> Ce point dépend des cartes achetées — question **Q5b**, encore ouverte.

Vérifier aussi la **continuité des masses** : le GND de tous les nœuds et celui du bus
(DB9 broche 3) doivent être communs. Un nœud sans masse commune émet des erreurs de bit sans
raison apparente.

---

## Étape 6 — Phase 2 : ping/pong sur le bus réel

Les trois cartes toujours programmées avec l'autotest. Alimenter les trois, ouvrir un
terminal série sur chacune, puis les réinitialiser.

N1 est l'initiateur : il émet `0x100` toutes les 100 ms. N2 et N3 répondent à chacune de ses
trames avec `0x200` et `0x300`.

### Résultat attendu, sur N1

```
=== Phase 2 : ping/pong sur le bus reel ===
  Ce noeud est N1, identifiant 0x100.
  Role : initiateur. Emet toutes les 100 ms.

  t=     1s  emises=10     recues=20     reponses=20
                 etat=error-active   TEC=  0 REC=  0 LEC=0 pertes_fifo=0 tampon=0
  t=     2s  emises=20     recues=40     reponses=40
                 etat=error-active   TEC=  0 REC=  0 LEC=0 pertes_fifo=0 tampon=0
```

Les trois critères d'un bus sain :

1. `reponses` vaut **deux fois** `emises` — N2 et N3 répondent chacun ;
2. `etat=error-active`, avec **TEC = 0 et REC = 0** qui ne bougent pas ;
3. `pertes_fifo=0` et `tampon=0`.

> **Cette phase ne prouve toujours pas le débit.** Les trois Nucleo partagent la même
> configuration d'horloge : si elle est fausse, elles le sont identiquement et communiquent
> parfaitement entre elles. Passer à l'étape 6 bis.

Sur N2 et N3, `emises` doit suivre `recues` à une unité près.

### Diagnostic

| Symptôme | Cause probable |
|---|---|
| `TEC` monte jusqu'à 128 puis `etat=BUS-OFF` sur **tous** les nœuds | Cavalier HW1 non retiré quelque part : dominant permanent |
| `TEC` monte sur **un seul** nœud, les autres sont sains | Ce nœud n'est pas acquitté : son `RXD` ou son `TXD` est mal câblé, ou son transceiver n'est pas alimenté en 5 V |
| `TEC` et `REC` montent partout, sans bus-off immédiat | Terminaisons : reprendre le contrôle des 60 Ω de l'étape 5 |
| `etat=error-active` mais `reponses=0` | N2 et N3 ne reçoivent pas : vérifier leur `RXD` (PA11) |
| Erreurs sporadiques qui augmentent avec la longueur | Dérivations trop longues, ou masse non commune |
| Un nœud affiche `HSI - NON VALIDE` | Il communique peut-être, mais la mesure n'a pas valeur de preuve |
| `pertes_fifo` ou `tampon` non nuls | Le logiciel ne suit pas : à signaler, ce n'est pas normal à cette charge |

> Un `LEC` non nul juste après le démarrage est normal : le premier nœud allumé émet dans le
> vide et compte une erreur d'acquittement tant que les autres ne sont pas prêts. C'est la
> **progression** de `TEC` en régime établi qui compte, pas sa valeur ponctuelle.

---

---

## Étape 6 bis — Phase 3 : le débit, contre une référence indépendante

> **C'est l'étape qui établit le débit.** Les phases 1 et 2 ne le font pas, et
> c'est le piège de cette mise en route.
>
> En **bouclage interne**, l'émetteur et le récepteur d'un même contrôleur partagent
> l'horloge noyau : une PLL mal configurée se boucle sur elle-même sans la moindre
> erreur. Un nœud tournant à 400 kbit/s au lieu de 500 passe la phase 1 sans broncher.
>
> En **phase 2**, les trois Nucleo portent la **même** configuration d'horloge. Si
> elle est fausse, elles le sont toutes de la même façon et se comprennent
> parfaitement entre elles. Une erreur commune est structurellement invisible.
>
> Il faut donc une source dont l'oscillateur n'a **rien à voir** avec le nôtre.

### 6 bis.1 — Échange avec le CANable

Le CANable 2.0 possède son propre quartz, indépendant de celui des Nucleo. S'il
communique sans erreur avec le banc, c'est que les deux débits coïncident
réellement.

Raccorder le CANable sur le connecteur libre (J5), puis :

```bash
canbench --interface gs_usb --bitrate 500000 monitor
```

**Critères, à vérifier des deux côtés :**

| Côté | Attendu |
|---|---|
| PC | Les trames de N1, N2 et N3 apparaissent, décodées, sans trame erronée |
| Nœuds (VCP) | `TEC` et `REC` restent à 0, `etat=error-active` |

Un débit divergent se manifeste par des erreurs de *stuff* ou de *form*, un `REC`
qui grimpe, et des trames tronquées côté PC — pas par un silence.

> Si le CANable est configuré à un débit différent du banc, **aucun des deux ne
> peut acquitter l'autre** : `TEC` monte jusqu'au passage en *error-passive* puis
> en *bus-off*. C'est un résultat exploitable, pas une panne.

### 6 bis.2 — Mesure du temps de bit à l'oscilloscope

Sonde différentielle entre **CAN_H et CAN_L**, ou deux voies en mode
mathématique A−B. Déclencher sur un front descendant du début de trame.

**Valeur attendue : 2,000 µs par bit** (1 / 500 000).

| Bande | Valeur | Origine |
|---|---|---|
| **Tolérance d'acceptation** | **1,990 à 2,010 µs** (± 0,485 %) | Écart maximal admissible par nœud, calculé en [bit_timing.md](bit_timing.md) |
| **Valeur attendue en pratique** | **2,000 µs à quelques ppm près** | Le quartz est à 20 ppm, soit ± 0,04 ns |

Cet écart entre les deux lignes est le cœur du diagnostic. La bande d'acceptation
est large parce qu'elle doit couvrir le pire cas normatif ; mais avec une
configuration **correcte**, on doit mesurer 2,000 µs à la précision de
l'oscilloscope près. Toute valeur qui s'en écarte visiblement signale une erreur
de configuration, même si elle reste dans la bande.

| Mesure | Interprétation |
|---|---|
| 2,000 µs ± quelques ppm | Correct |
| 2,000 µs ± jusqu'à 1 % | Le nœud tourne probablement sur **HSI** (± 1 %) |
| Écart d'un rapport simple (2,5 µs, 1,6 µs…) | `PLLM`/`PLLN`/`PLLQ` ou `BENCH_CAN_PRESCALER` erronés |
| 4,000 µs | 250 kbit/s : mode de faute « débit erroné » resté actif |

**Méthode.** Mesurer un seul bit donne une résolution médiocre. Préférer la
mesure automatique de période de l'oscilloscope avec moyennage, ou mesurer la
durée d'une suite de bits de même niveau, puis diviser. Le champ le plus commode
est le **délimiteur de CRC suivi de l'ACK**, ou une zone de bits identiques
consécutifs repérée à l'œil.

**Précision de l'instrument.** La base de temps d'un oscilloscope numérique
courant est spécifiée autour de ± 50 ppm, soit 0,005 % — cent fois plus fin que
la bande d'acceptation de 0,485 %. L'instrument n'est donc pas le facteur
limitant, à condition de moyenner.

### 6 bis.3 — Cas du repli HSI

Si les cartes tournent encore sur HSI (SB9/SB10 non soudés), le firmware l'affiche
et lève `clock_not_qualified` dans son heartbeat.

Dans cet état, **les phases 1 et 2 gardent tout leur intérêt** : elles valident le
câblage, le transceiver, les terminaisons et toute la logique applicative. Mais
**le débit n'est pas établi** et aucun verdict de réussite ne peut être prononcé
pour T2 ni pour les tests qui en dépendent. `canbench` refuse d'ailleurs de le
faire tant que le bit est levé.

### 6 bis.4 — Lien avec le protocole de validation

Cette étape est la version « mise en route » du test **T2** de
[protocole_validation.md](protocole_validation.md). T2 reprend la même mesure avec
un relevé formel, une photo d'écran d'oscilloscope et un verdict daté. Réussir
6 bis ne dispense pas d'exécuter T2 ; cela garantit seulement que T2 a des chances
de passer.

---

## Étape 7 — Passer au firmware nominal

Une fois la phase 2 verte sur les trois nœuds, reprogrammer avec le firmware réel :

```bash
cmake --preset n1 && cmake --build --preset n1 --target flash_n1
cmake --preset n2 && cmake --build --preset n2 --target flash_n2
cmake --preset n3 && cmake --build --preset n3 --target flash_n3
```

Le banc est alors prêt pour le protocole de validation
([protocole_validation.md](protocole_validation.md)), à commencer par T1 et T2 qui demandent
l'oscilloscope.

---

## Récapitulatif

| Étape | Ce qui est validé | Matériel nécessaire |
|---|---|---|
| 1 | — | Fer à souder, multimètre |
| 2 | Chaîne de compilation et programmation | Carte + USB |
| 3 | PLL, ISR, tampon, encodage — **pas le débit** | Carte + USB **seulement** |
| 4 | Câblage d'un nœud | + transceiver |
| 5 | Topologie et terminaisons | + bus, multimètre |
| 6 | Communication réelle entre trois nœuds — **pas le débit** | Banc complet |
| 6 bis | **Le débit**, contre une référence indépendante | + CANable et oscilloscope |
| 7 | — | Banc complet |
