# Visualisation 3D du banc

Le banc complet tel qu'on veut l'obtenir, dans une seule page web : 4 nœuds sur leurs cartes
porteuses v0.3, l'adaptateur USB-CAN dans son boîtier, le hub USB, le boîtier de fautes et le
bus en étoile sur trois bornes Wago 221-420 (une par signal).

```bash
python generer.py
```

produit `visualisation_3d_banc_CAN.html` (environ 4,5 Mo, non versionné). La page s'ouvre par
double-clic dans un navigateur récent ; une connexion Internet est nécessaire pour charger
three.js.

| Fichier | Rôle |
|---|---|
| `gabarit.html` | la scène : disposition, câbles, jonction du bus, points de vue |
| `generer.py` | exporte la carte porteuse depuis son PCB et assemble la page |
| `modeles/` | adaptateur USB-CAN simplifié et boîtier, repris de la page envoyée le 13/11/2026 |

La carte porteuse est réexportée à chaque génération : la page suit la carte routée. Le reste
(écrans, MPU-6050, Wago, hub, boîtier de fautes, plaque) est modélisé à ses dimensions dans
`gabarit.html`. À ne pas confondre avec `simulation_3d/`, qui simule le bus au bit près mais
montre encore le banc du dossier v0.1.
