# Observer le bus à l'oscilloscope

Firmware : presets `n1-scope-direct` et `n2-scope-direct`
(`firmware/entry/scope.c`). Bus direct, sans transceiver, horloge HSI :
**essai sur table, ne valide pas le débit**.

## Ce que chaque nœud émet

Les deux nœuds disent **« Test »** en ASCII. C'est l'**identifiant** qui dit qui
parle.

| Nœud | Identifiant | DLC | Données | Cadence |
|---|---|---|---|---|
| N1 | `0x0F0` | 4 | `54 65 73 74` = « Test » | toutes les 20 ms |
| N2 | `0x20F` | 4 | `54 65 73 74` = « Test » | 5 ms après chaque trame de N1 (toutes les 20 ms si N1 se tait) |

- Le contenu est **fixe** (pas de compteur) : l'oscilloscope peut se déclencher
  dessus et superposer les trames.
- N1 a l'identifiant le plus bas : en cas de collision, il gagne l'arbitrage.
- À 500 kbit/s, un bit dure **2 µs**. Un bit à 0 est un niveau bas (0 V), un bit
  à 1 un niveau haut (3,3 V).

## Les quatre lettres, en binaire

| Lettre | Hex | Bits envoyés (MSB d'abord) |
|---|---|---|
| T | `0x54` | `0101 0100` |
| e | `0x65` | `0110 0101` |
| s | `0x73` | `0111 0011` |
| t | `0x74` | `0111 0100` |

Chaque octet dure 16 µs. Aucun bit de bourrage n'apparaît dans ces données.

## Où lire chaque champ sur l'écran

Les temps sont comptés depuis le front descendant du SOF. Bits de bourrage
marqués `*` : un bit inséré après cinq bits identiques.

### N1 — 80 bits, 160 µs

| Temps (µs) | Champ | Bits |
|---|---|---|
| 0 – 2 | SOF | `0` |
| 2 – 24 | Identifiant `0x0F0` | `00011110000` |
| 24 – 28 | RTR | `01*` (RTR puis bit de bourrage) |
| 28 – 32 | IDE, r0 | `0` `0` |
| 32 – 40 | DLC = 4 | `0100` |
| 40 – 56 | `T` | `01010100` |
| 56 – 72 | `e` | `01100101` |
| 72 – 88 | `s` | `01110011` |
| 88 – 104 | `t` | `01110100` |
| 104 – 134 | CRC | `101100001001101` |
| 134 – 136 | DEL CRC | `1` |
| 136 – 138 | ACK | `0` si un autre nœud acquitte, `1` sinon |
| 138 – 160 | DEL ACK, EOF, IFS | `1` `1111111` `111` |

### N2 — 82 bits, 164 µs

| Temps (µs) | Champ | Bits |
|---|---|---|
| 0 – 2 | SOF | `0` |
| 2 – 28 | Identifiant `0x20F` | `01000001*11110*` |
| 28 – 34 | RTR, IDE, r0 | `0` `0` `0` |
| 34 – 44 | DLC = 4 | `01*100` |
| 44 – 60 | `T` | `01010100` |
| 60 – 76 | `e` | `01100101` |
| 76 – 92 | `s` | `01110011` |
| 92 – 108 | `t` | `01110100` |
| 108 – 138 | CRC | `001110001100010` |
| 138 – 140 | DEL CRC | `1` |
| 140 – 142 | ACK | `0` si un autre nœud acquitte, `1` sinon |
| 142 – 164 | DEL ACK, EOF, IFS | `1` `1111111` `111` |

Suites générées par `canbench.physical.build_frame` (CRC-15 et bourrage selon
ISO 11898-1) ; elles n'ont pas encore été comparées à une capture.

## Réglage de l'oscilloscope

| Réglage | Valeur |
|---|---|
| Sonde | pointe sur le fil BUS, pince de masse sur le fil GND |
| Atténuation | celle de la sonde : **10:1** dans le menu de la voie si l'interrupteur est sur ×10 |
| Couplage | DC |
| Échelle verticale | 1 V/div (le bus passe de 0 à 3,3 V) |
| Base de temps | 20 µs/div : une trame de 160 µs tient sur 8 divisions |
| Déclenchement | front **descendant**, niveau 1,6 V, mode Normal, voie du BUS |
| Holdoff | environ 1 ms, pour n'accrocher que le SOF |

À 1 ms/div, on voit une trame de N1 puis, 5 ms plus tard, celle de N2.

## Décoder la capture

### Sur l'oscilloscope, si l'option est présente

Touche **Serial** : si **CAN** figure dans la liste des modes, régler Source =
voie 1, Signal = `Rx`, débit 500 kb/s, point d'échantillonnage 87,5 %, seuil
1,6 V. L'oscilloscope affiche alors `0F0`, la longueur 4 et `54 65 73 74`.
L'option de décodage automobile est payante : si la touche Serial ne propose pas
CAN, elle n'est pas installée.

### Sur le PC, sans option : `canbench.scope`

1. Déclencher une capture complète (bouton **Single**, une trame entière à
   l'écran, 20 µs/div).
2. **Save/Recall** → **Enregistrer** : format **CSV**, source **voie 1**,
   longueur **maximale**, destination la clé USB.
3. Sur le PC, depuis `pc/` :

```bash
python -m canbench.scope capture.csv
```

Exemple de sortie :

```
#1  t=     10.0 µs  id=0x0F0  dlc=4  data=54 65 73 74  « Test »  CRC ok  acquittée : oui  bit=2.000 µs
```

L'outil seuille la courbe au milieu de son excursion (peu importe l'échelle ou
l'atténuation de la sonde), mesure la durée de chaque palier, en déduit le nombre
de bits, retire le bourrage et vérifie le CRC-15. Il est insensible à la dérive
de ±1 % de l'horloge HSI. Il affiche aussi la durée d'un bit **mesurée**, qui doit
être proche de 2 µs. Le code de retour vaut 0 si toutes les trames ont un CRC
correct.

## Ce qu'on doit voir, et ce qui doit alerter

- **Niveaux** : 0 V pour un bit dominant, 3,3 V pour un bit récessif. Ce n'est
  pas la signalisation différentielle d'un vrai bus CAN : il n'y a pas de
  transceiver.
- **Fronts montants arrondis** : en bus direct, le retour à 1 se fait par les
  résistances internes (environ 40 kΩ), donc lentement. Les fronts descendants
  sont nets. Si le front montant ne laisse pas le temps d'atteindre 3,3 V en
  2 µs, ajouter une résistance de 2,2 kΩ entre le BUS et le 3,3 V.
- **Bit ACK** : à 0 si l'autre nœud acquitte. Débrancher N2 : l'ACK de N1 passe
  à 1 et N1 voit des erreurs d'acquittement (TEC qui monte jusqu'à 128).
- **Écart de débit** : les deux cartes sont sur HSI (±1 %), donc la durée d'un bit
  peut différer d'une carte à l'autre de quelques dizaines de ns. Ce n'est pas un
  défaut : la mesure précise du débit demande une référence indépendante.
