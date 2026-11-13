# Carte porteuse d'un nœud du banc CAN (v0.1)

Une Nucleo-G431KB s'enfiche dessus (broche 1 de CN3 et CN4 côté USB, flèche « <- USB »).
La carte porte le TJA1051T/3 soudé (SO8) et ses deux 100 nF, deux borniers H-L-G (entrée,
sortie) pour chaîner le bus, la terminaison 120 Ω sur cavalier TERM (sur N4 : vers SW1), les
barrettes de l'écran OLED (J5) et du MPU-6050 (J6, N2 seulement), et les LED ERR et BUS-OFF.
65 × 50 mm, 2 couches, règles factory ENSEA. À fabriquer en 4 exemplaires.

Non montés (prévus) : R8 (S sur PB6), R11/R12 (OLED en VCC/GND), R4/R5 (tirages I2C),
J8/J9/R6 (capteurs Hall et 1-Wire, reportés).

**Avant de souder R9/R10 : vérifier l'ordre GND/VCC du module OLED reçu.** L'écran se
monte à l'envers dans sa barrette : le firmware retournera l'affichage.

Chaîne : `generate_schematic.py` → `generate_pcb.py` → `route_freerouting.py <jar>` →
`generate_fabrication.py` (depuis PowerShell) → `generate_commande.py`.
État : ERC 0 ; DRC 0 erreur, 0 non connecté (avertissements de sérigraphie seulement).
105 teardrops (éditeur de PCB, Éditer > Éditer Teardrops). Reste : relecture sur les pièces reçues.
