# Protocole de validation

Destiné à remplir la **section 7 du dossier de définition**, laissée en `\todo{}` dans la
v0.1. Sept tests couvrent les six fonctions énoncées en section 1 du dossier.

Chaque test suit le format demandé : **objectif / montage / procédure / critère de réussite
chiffré / résultat mesuré / verdict**. Les colonnes « résultat » et « verdict » sont
remplies à l'exécution, `canbench report` produisant le bloc Markdown et l'extrait LaTeX
datés, avec le hash git du firmware testé.

---

## Couverture des six fonctions du dossier

| # | Fonction (§1 du dossier) | Tests |
|---|---|---|
| 1 | Couche physique (niveaux différentiels, terminaisons, débit 500 kbit/s) | **T1**, **T2** |
| 2 | Arbitrage entre au moins trois nœuds émetteurs simultanés | **T3** |
| 3 | Encodage des messages définis dans l'ICD | **T4** |
| 4 | Robustesse par injection de fautes | **T5**, **T6** |
| 5 | Démonstration pédagogique, tous groupes confondus | **T3**, **T4** (IHM locale) |
| 6 | Isolation galvanique | **T7** (squelette) |

| Test | Objet | Automatisation | Nature |
|---|---|---|---|
| T1 | Couche physique : terminaisons, niveaux différentiels | — | manuel |
| T2 | Débit et point d'échantillonnage | — | manuel (oscilloscope) |
| T3 | Arbitrage ARM/GO | `canbench arbitration` | automatique |
| T4 | Encodage ICD | `canbench encoding` | automatique |
| T5 | Fautes physiques SW1/SW2/SW3 | `canbench faults` (guidé) | semi-auto |
| T6 | Fautes logicielles de N4 | `canbench faults` | automatique |
| T7 | Isolation galvanique | — | squelette |

> **Préalable commun à tous les tests.** Aucun nœud ne doit signaler
> `clock_not_qualified` dans son heartbeat. Ce bit indique que le nœud tourne sur HSI, dont
> la précision de ±1 % dépasse plus du double la tolérance admissible : les mesures restent
> exploitables pour la mise au point, mais **aucun verdict de réussite ne peut être
> prononcé**. `canbench` refuse de le faire tant que le bit est levé.

---

## T1 — Couche physique

**Objectif.** Vérifier que la ligne est correctement terminée et que les niveaux
différentiels sont conformes à ISO 11898-2.

**Montage.** Banc complet assemblé, SW1 fermé, SW2 ouvert, SW3 fermé. Multimètre, puis
oscilloscope avec sonde différentielle sur CAN_H − CAN_L.

**Procédure.**

1. **Hors tension**, mesurer la résistance entre CAN_H et CAN_L.
2. Vérifier la continuité des masses entre tous les nœuds et le GND du bus (DB9-3).
3. Mettre sous tension, bus au repos : mesurer les tensions de mode commun CAN_H et CAN_L.
4. Faire émettre un nœud, relever la tension différentielle à l'état dominant et récessif.

**Critères de réussite.**

| Grandeur | Attendu | Source |
|---|---|---|
| Résistance CAN_H–CAN_L, hors tension | **60 Ω ± 5 %** (soit 57 à 63 Ω) | Deux terminaisons de 120 Ω en parallèle |
| Récessif, différentiel | **−50 à +50 mV** | TJA1051, `VO(dif)bus` récessif |
| Dominant, différentiel | **1,5 à 3,0 V** | TJA1051, `VO(dif)bus` pour RL = 45 à 65 Ω |
| Dominant, CAN_H | 2,75 à 4,5 V | TJA1051, `VO(dom)` |
| Dominant, CAN_L | 0,5 à 2,25 V | TJA1051, `VO(dom)` |

> Une résistance nettement inférieure à 57 Ω signale des terminaisons surnuméraires — le cas
> typique étant des modules transceiver portant un 120 Ω soudé. À 20 Ω, on sort de la plage
> de charge pour laquelle le TJA1051 garantit sa tension différentielle : le symptôme n'est
> pas un bus muet mais des **erreurs intermittentes**, la tension différentielle pouvant
> approcher le seuil du récepteur (0,5 à 0,9 V). Voir [pinout.md](pinout.md) §6.

---

## T2 — Débit et point d'échantillonnage

**Objectif.** Établir que le débit réel est bien de 500 kbit/s, et que le point
d'échantillonnage est conforme.

> **C'est le seul test qui établit le débit.** Il ne peut pas être remplacé par un échange
> entre nœuds du banc. En bouclage interne, l'émetteur et le récepteur partagent l'horloge
> noyau : une PLL fausse se boucle sur elle-même sans erreur. Entre deux Nucleo de
> configuration identique, une erreur d'horloge commune est tout aussi invisible — elles se
> comprennent parfaitement en étant fausses ensemble. Il faut une **référence indépendante**.

**Montage.** Banc en fonctionnement nominal. Oscilloscope avec sonde différentielle sur
CAN_H − CAN_L, déclenché sur front descendant du début de trame. CANable raccordé sur J5.

**Procédure.**

1. Lancer un trafic périodique (`canbench --interface gs_usb monitor`, nœuds en
   fonctionnement nominal).
2. **Mesure du temps de bit.** Relever la durée d'un bit. Privilégier la mesure automatique
   de période avec moyennage, ou mesurer une suite de bits de même niveau puis diviser : un
   bit isolé donne une résolution médiocre.
3. **Mesure du point d'échantillonnage.** Relever la position du point d'échantillonnage
   dans le bit, à partir des segments configurés, ou vérifier la cohérence du rapport
   TSEG1/TSEG2 déclaré en confrontant la durée totale du bit à la configuration.
4. **Référence indépendante.** Vérifier que le CANable, dont le quartz n'a aucun rapport
   avec celui des Nucleo, échange sans erreur : trames décodées côté PC, `TEC` et `REC`
   restant à 0 sur chaque nœud.

**Critères de réussite.**

| Grandeur | Attendu | Origine |
|---|---|---|
| Temps de bit | **2,000 µs**, bande d'acceptation **1,990 à 2,010 µs** | 1/500 000, ± 0,485 % (cf. [bit_timing.md](bit_timing.md)) |
| Temps de bit, valeur typique attendue | **2,000 µs à quelques ppm près** | Quartz à 20 ppm, soit ± 0,04 ns |
| Point d'échantillonnage | **87,5 %** | Recommandation CiA, identique sur les deux familles |
| Échange avec le CANable | Aucune trame erronée, dans les deux sens | Oscillateur indépendant |
| `TEC`, `REC` de chaque nœud | **0**, stables | Heartbeat |

> **La bande d'acceptation et la valeur attendue ne se confondent pas.** La bande de
> ± 0,485 % est la limite normative, qui doit couvrir le pire cas. Avec une configuration
> correcte, la mesure doit tomber sur 2,000 µs à la précision de l'instrument près. Une
> valeur qui s'en écarte visiblement — disons de plus de 0,1 % — signale une erreur de
> configuration **même si elle reste dans la bande**, et doit être investiguée.

**Diagnostic.**

| Mesure | Interprétation |
|---|---|
| 2,000 µs ± jusqu'à 1 % | Le nœud tourne probablement sur HSI (à recouper avec `clock_not_qualified`) |
| Écart d'un rapport simple (2,5 µs, 1,6 µs…) | `PLLM`/`PLLN`/`PLLQ` ou `BENCH_CAN_PRESCALER` erronés |
| 4,000 µs | 250 kbit/s : mode de faute « débit erroné » resté actif sur un nœud |

**Précision de l'instrument.** La base de temps d'un oscilloscope numérique courant est
spécifiée autour de ± 50 ppm, soit 0,005 % — cent fois plus fin que la bande d'acceptation.
L'instrument n'est pas le facteur limitant, à condition de moyenner.

> L'étape **6 bis** de [bringup.md](bringup.md) est la version « mise en route » de ce test :
> mêmes mesures, sans le relevé formel. La réussir ne dispense pas d'exécuter T2 ; elle
> garantit seulement que T2 a des chances de passer.

---

## T3 — Arbitrage ARM/GO

**Objectif.** Démontrer que trois nœuds émettant **réellement** au même instant sont
départagés par l'arbitrage dans l'ordre des identifiants.

**Montage.** Banc complet, N1, N2 et N3 en fonctionnement nominal, CANable sur J5.

**Procédure.**

```bash
canbench arbitration --cycles 1000
```

Le PC émet `ARM` puis `GO`. Les contendants arment leur émission pendant que `GO` occupe le
bus ; l'arbitrage qui suit est réel, et non le fruit d'un ordonnancement logiciel.

**Critères de réussite.**

| Grandeur | Attendu |
|---|---|
| Rang de N1 | **1** sur les 1000 cycles |
| Rang de N2 | **2** sur les 1000 cycles |
| Rang de N3 | **3** sur les 1000 cycles |
| `ARM reçus` | **identique** sur les trois nœuds |
| Cycles invalides | **0** |
| `TEC`, `REC` | 0 |

Le **rang** vaut 1 + le nombre de trames contendantes reçues entre la fin de `GO` et la fin
de sa propre émission. C'est la métrique qui porte le verdict, parce qu'elle est sans
ambiguïté. Les colonnes `gagnés` / `perdus` du tableau 7 du dossier sont également produites
pour compatibilité, `perdus` étant défini comme le nombre de cycles où le nœud a perdu au
moins un arbitrage.

> **Contrôle de validité.** Si les `ARM reçus` diffèrent entre contendants, un nœud a raté
> la fenêtre d'armement : il émettrait seul et apparaîtrait vainqueur sans avoir affronté
> personne. Le cycle est alors invalide et le test doit être rejoué.

---

## T4 — Encodage ICD

**Objectif.** Vérifier que l'encodage des signaux est correct de bout en bout, du capteur
simulé jusqu'au décodage PC.

**Montage.** Banc complet. Capteurs réels débranchés, pour que les nœuds émettent leurs
séquences déterministes déclarées dans l'ICD.

**Procédure.**

```bash
canbench encoding
```

Pour chaque trame applicative, l'outil compare les valeurs reçues aux séquences attendues et
produit un rapport des écarts **octet par octet**.

**Critères de réussite.**

| Grandeur | Attendu |
|---|---|
| Écarts octet par octet | **0** sur toutes les trames de l'ICD |
| Valeurs aux bornes (min, max, zéro, ±1 pas) | conformes |
| Signaux signés à valeur négative | correctement étendus en signe |
| Affichage local de la zone « Dernier reçu » | cohérent avec le décodage PC |

La zone « Dernier reçu » de l'écran de chaque nœud fait partie du critère : c'est elle qui
prouve qu'un nœud **donné** a reçu et décodé le message, là où l'IHM PC ne démontre que le
passage de la trame sur le bus.

---

## T5 — Fautes physiques

**Objectif.** Vérifier le comportement du bus face aux trois défauts physiques les plus
courants.

**Montage.** Banc complet, boîtier d'injection de fautes accessible.

**Procédure.** `canbench faults --physical` guide l'opérateur pas à pas, relève les
compteurs avant et après chaque manipulation, et rappelle les précautions.

| Repère | Faute | Position nominale | Critère de réussite |
|---|---|---|---|
| SW1 | Perte de la terminaison `R_T2` | fermé | Hausse mesurable du taux d'erreur ; `REC` progresse ; retour à 0 après refermeture |
| SW2 | Court-circuit CAN_H / CAN_L | ouvert | Passage en `bus-off` des nœuds émetteurs ; reprise automatique après ouverture |
| SW3 | Retrait à chaud de N4 | fermé | **Le reste du bus continue de fonctionner** ; aucune erreur sur N1–N3 |

> **SW2 ne doit être fermé que brièvement.** Le TJA1051T/3 limite son courant de
> court-circuit mais s'échauffe si l'état se prolonge. `canbench faults` affiche une durée
> maximale et un décompte. Ne jamais actionner SW2 pendant qu'un nœud isolé galvaniquement
> est sous tension côté puissance.

---

## T6 — Fautes logicielles

**Objectif.** Vérifier que le bus et les nœuds sains résistent aux comportements fautifs
d'un nœud, et que ces comportements sont détectés.

**Montage.** Banc complet, N4 en place.

**Procédure.** `canbench faults --logical` pilote les modes de faute de N4 par `BENCH_CFG`.
Chaque mode est **borné dans le temps et révocable**.

| Mode | Comportement | Critère de réussite |
|---|---|---|
| 1 — *babbling idiot* | Inonde le bus d'un identifiant configurable | Charge bus mesurée cohérente ; les trames prioritaires passent toujours ; retour à la normale à l'échéance |
| 2 — débit erroné | Se reconfigure à 250 kbit/s | Erreurs détectées ; `TEC` de N4 progresse jusqu'au `bus-off` ; les autres nœuds restent sains |
| 3 — DLC incohérent | Émet un DLC ne correspondant pas à l'ICD | Signalé par `canbench` ; les nœuds ne décodent pas la trame |
| 4 — silencieux | Mode moniteur du contrôleur | N4 n'acquitte plus ; observable sur les compteurs des autres nœuds |
| 5 — bus-off maintenu | Reste en `bus-off` jusqu'à révocation | État visible sur l'écran et la LED ; reprise sur commande |

Le mode 4 couvre à lui seul « passage en mode silencieux » et « arrêt d'acquittement » : ni
bxCAN ni FDCAN n'offrent de « ne pas acquitter » indépendant du mode moniteur.

> **Limite à connaître.** Le TJA1051 possède une temporisation *TXD dominant time-out* qui
> coupe le driver si TXD reste bas trop longtemps — elle « définit également le débit minimal
> possible de 40 kbit/s ». Une faute « dominant collé » serait donc **corrigée d'elle-même**
> par le transceiver après quelques centaines de µs. Ce n'est pas un défaut du banc, mais
> cela borne ce que ce test peut démontrer, et doit être mentionné au dépouillement.

> **Trames CAN FD.** Une trame FD sur un bus configuré en classic est rejetée au niveau
> protocole — le bit FDF est réservé dominant en CAN 2.0 — et se manifeste par une **erreur
> de forme** (`LEC`) et un `REC` qui progresse, et non par le compteur `non_classic_rx`. Ce
> dernier ne capte que ce que le contrôleur accepte de présenter. Les identifiants 29 bits,
> eux, sont bien comptés par `ext_id_rx`.

---

## T7 — Isolation galvanique

**Squelette.** Cette fonction concerne une variante matérielle qui n'existe pas encore : un
nœud doté d'un transceiver isolé (ISO1050 ou ADM3053) avec alimentation séparée, annoncée
pour la version v0.2 du dossier.

**Objectif.** Vérifier qu'un nœud placé à proximité d'électronique de puissance ne dégrade
pas le bus, et que la barrière d'isolation tient la tension annoncée.

**Procédure prévue.** Mesure de rigidité diélectrique entre les deux masses, puis
reconduction de T1, T2 et T3 avec le nœud isolé en place.

**Critères à fixer** lors de la conception de la variante : tension d'isolement, courant de
fuite, dégradation admissible du taux d'erreur.

> Ne jamais actionner SW2 pendant que le nœud isolé est sous tension côté puissance.

---

## Production du rapport

```bash
canbench report --test T3 --output docs/resultats/
```

Pour chaque test exécuté, `canbench report` produit un bloc Markdown et un extrait LaTeX au
format objectif / montage / procédure / critère / résultat / verdict, **daté** et portant le
**hash git du firmware testé**, afin qu'un résultat puisse toujours être rattaché à une
version précise du code.

Un verdict de réussite est refusé si un nœud signale `clock_not_qualified`, si un compteur
de perte (`rx_fifo_lost`, `ring_overflow`) est non nul, ou si les `ARM reçus` divergent lors
d'un test d'arbitrage.
