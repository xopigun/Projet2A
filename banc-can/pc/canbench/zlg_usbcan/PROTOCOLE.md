# Protocole USB de l'adaptateur ZLG USBCAN-UC12

Reconstitué par **analyse statique** de `usbcan.dll` (ZLG, 2017, 32 bits,
`C:\Windows\SysWOW64\usbcan.dll`), à des fins d'interopérabilité (art. L122-6-1 CPI).
Statut de chaque point : **[S]** déduit du code, **[V]** vérifié sur l'adaptateur.

## Pourquoi

Le pilote noyau ZLG (`usbcan.sys` v1.94, 2017) est incompatible avec l'intégrité de la
mémoire de Windows. Or ce pilote ne fait que relayer des octets bruts vers les endpoints :
tout le protocole est dans `usbcan.dll`, en mode utilisateur. On peut donc le remplacer par
WinUSB (pilote générique signé Microsoft) et parler à l'adaptateur via libusb.

## Matériel [V]

- USB 1.1 full speed, `0471:1200`, produit « USBCAN-UC12 », classe constructeur.
- Une interface, quatre endpoints, ouverts par la DLL sous les noms `PIPE00`..`PIPE03` :

| Tuyau | Endpoint | Type | Taille | Rôle |
|---|---|---|---|---|
| PIPE00 | `0x81` IN | interruption | 16 | réponses aux commandes |
| PIPE01 | `0x01` OUT | interruption | 16 | commandes |
| PIPE02 | `0x82` IN | bulk | 64 | trames reçues |
| PIPE03 | `0x02` OUT | bulk | 64 | trames à émettre |

- Contrôleur CAN de type **SJA1000** (mode PeliCAN) : la DLL lit ses registres par numéro.

## Commandes (PIPE01) [S]

Format : `12 <code> <n> <n octets>`. Réponse sur PIPE00, de longueur variable **[V]** :
`12 <code> <0x80 | m> 00 <m-1 octets de charge utile>`. La DLL de 2017 attendait `13`
en tête ; le firmware 1.02 renvoie `12`. Un octet 2 < `0x80` signale un acquittement
d'émission du canal `<code>` (octet 2 = trames acceptées) **[S]**.
`<c>` désigne `canal << 4`. Délai d'attente de la DLL : 1 s.

| Code | Fonction VCI | Corps envoyé | Réponse utile |
|---|---|---|---|
| `01` | ReadBoardInfo | `00` | **[V]** `02 01` = firmware 1.02 (mot LE) |
| `12` | ReadBoardInfo | `00` | **[V]** `06 10` (sens à établir : version matérielle ?) |
| `13` | ReadBoardInfo | `00` | **[V]** `02` (sens à établir) |
| `14` | ReadBoardInfo | `00` | **[V]** n° de série ASCII (`2F436ABA022`) |
| `15` | ReadBoardInfo | `00` | **[V]** type ASCII (`USBCAN`) |
| `03` | InitCAN (débit) | `00 ((mode<<3)\|canal)<<4 Timing0 Timing1` | **[V]** acquittement `12 03 81 00` |
| `04` | InitCAN (filtre) | `00 ((filtre<<2)\|canal)<<4 AccCode[3..0] AccMask[3..0]` | **[V]** acquittement |
| `0E` | StartCAN | `00 <c>` | **[V]** acquittement |
| `0F` | ResetCAN | `00 <c>` — **octet `n` = `0x12`**, pas la longueur | acquittement |
| `0D` | lecture registre SJA1000 | `00 <c> <registre>` | **[V]** valeur à l'octet 4 (EWL lu = `0x60` = 96, valeur d'usine du SJA1000) |
| `06` | statistiques | `00 <c>` | **[V]** octet 4, puis deux `uint32` A et B (octets 5 et 9) ; bus au repos : A = 0, B ≈ 900 ; la DLL affiche `A*100/(A+B)` (taux d'occupation ?) |
| `07` | lecture mémoire | `00 <adresse 16 bits> <long.> <…>` | 8 octets max par bloc |
| `08` | écriture mémoire | `<n> 00 <adresse> <long.> <données> <somme>` | acquittement |

`mode` : 0 normal, 1 écoute seule. Timing0/Timing1 = BTR0/BTR1 du SJA1000 (16 MHz) ;
500 kbit/s = `00 1C`. `VCI_ReadCANStatus` lit les registres `00` (mode), `02` (état),
`0B` (ALC), `0C` (ECC), `0D` (limite d'avertissement), `0E` (REC), `0F` (TEC).

À l'ouverture, la DLL envoie aussi l'IOCTL `0x220004` (sans données) au pilote ZLG :
probablement une réinitialisation des tuyaux, sans équivalent nécessaire sous WinUSB.

## Émission (PIPE03) [S]

Jusqu'à 3 enregistrements de 19 octets par écriture (57 ≤ 64), **même disposition qu'en
réception** **[V]** (le tampon de la DLL commence 5 octets avant le premier champ rempli —
une première lecture l'avait manqué) :

| Octets | Contenu |
|---|---|
| 0–4 | réservés (zéros) |
| 5 | SendType (0 normal, 1 une seule tentative…) |
| 6 | `Ext<<7 \| RTR<<6 \| canal<<4 \| DLC` |
| 7–10 | `uint32` LE : `ID << 5` (standard) ou `ID << 3` (étendu), alignement SJA1000 |
| 11–18 | données |

Firmware ≥ 1.02 : à la fin de l'émission, acquittement **`13 <canal> <n>`** sur PIPE00
(3 octets, commence par `13`, contrairement aux réponses de commande) **[V]**. Sans
acquittement CAN, l'adaptateur réémet ~1,66 s puis abandonne avec `n = 0` **[V]**.

> **Piège [V]** : une trame destinée à un canal non démarré reste dans le tampon de
> l'adaptateur, qui refuse alors toute écriture sur PIPE03 (NAK, délai dépassé). Ni
> ResetCAN ni la réinitialisation USB logicielle ne la purgent : il faut débrancher
> l'adaptateur.

## Réception (PIPE02)

Lectures de 1216 octets (64 enregistrements de 19 octets) **[S]**, enregistrements de
19 octets **[V]** :

| Octets | Contenu |
|---|---|
| 0–3 | horodatage `uint32` LE, **unité 0,1 ms** **[V]** |
| 4 | **état** : `00` trame normale, `E1`–`EF` événement du contrôleur |
| 5 | réservé |
| 6 | `Ext<<7 \| RTR<<6 \| canal<<4 \| DLC` |
| 7–10 | ID décalé comme à l'émission |
| 11–18 | données |

Événements (octet 4) : `E1`/`EF` débordement FIFO, `E2` avertissement d'erreurs **[V]**,
`E3` erreur passive (octets 7–9 = ECC, REC, TEC) **[V]**, `E4` perte d'arbitrage
(octet 7 = ALC), `E5` erreur de bus. Pour les événements, l'octet 6 vaut `05`.

Essai sans aucun nœud sur le bus (trame non acquittée) **[V]** :

```
+7 ms     94 ad 02 00 e3 00 05 c0 00 80 ...   erreur passive, REC=0, TEC=128
+1670 ms  70 ee 02 00 e2 00 05 60 00 00 ...   avertissement d'erreurs
+1670 ms  13 00 00  (PIPE00)                  canal 0 : 0 trame émise
```

## Limites constatées [V]

- **ECC reste à `0xC0`** (type « autre », émission, segment 0), avant comme après une
  erreur d'acquittement — un vrai SJA1000 donnerait `0xD9` (slot ACK). L'adaptateur est
  probablement un microcontrôleur qui *émule* les registres SJA1000 : le type et le champ
  de l'erreur ne sont pas disponibles. REC, TEC, EWL (96) et les événements sont fiables.
- La commande `06` renvoie `A = 0, B = 917` même pendant une émission : sens inconnu.
- Registre d'état (`02`) toujours lu à `00`.

Indicateurs de qualité exploitables : REC/TEC et leur évolution, événements
avertissement / passif / bus-off / perte d'arbitrage / débordement, horodatage à 0,1 ms
(gigue et périodes par identifiant), trames non acquittées (acquittement `n = 0`).
