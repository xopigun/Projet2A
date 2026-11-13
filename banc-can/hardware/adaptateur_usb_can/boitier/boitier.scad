// Boîtier imprimé en 3D de l'adaptateur USB-CAN G69 v0.2 (carte 60 x 30 mm, fiche USB-A en clé).
//
//   openscad -D 'piece="fond"'   -o fond.stl   boitier.scad   // à imprimer tel quel, fond sur le plateau
//   openscad -D 'piece="capot"'  -o capot.stl  boitier.scad   // déjà retourné : dessus sur le plateau
//   openscad -D 'piece="ensemble"' boitier.scad               // vue montée, avec la carte si carte.stl existe
//
// Repère (mm) : celui de l'export STL de KiCad avec l'origine au centre de la carte (130, 115) :
// x = X_kicad - 130 (fiche USB à gauche, bornier à droite), y = 115 - Y_kicad, z = 0 sous la carte.
// Les positions et hauteurs viennent du PCB et des modèles 3D KiCad (voir README.md).
//
// Deux coques emboîtées au plan z = 0 (dessous de la carte) :
// - le fond porte la carte sur un rebord et monte une lèvre qui entre dans le capot ;
// - le capot plaque la carte par des nervures, laisse sortir la fiche USB, le bornier,
//   les barrettes SWD et TERM, et porte deux poussoirs souples pour RESET et BOOT0.
// Règles du cours d'impression 3D (ENSEA, Option Maker) : aucune pièce ne demande de supports
// (surplombs à 45° au plus, pas de pont), murs de 1,6 à 2 mm (4 à 5 passes de buse 0,4),
// jeux de 0,2 mm entre la carte et le boîtier, de 0,15 mm entre les coques.

piece = "ensemble";            // "fond", "capot", "ensemble", "eclate", "coupe"
carte_stl = "";
coupe_y = 0;                   // plan de la vue en coupe                // carte exportée par KiCad (voir README.md), pour les vues seulement
$fn = 48;
eps = 0.01;

// ---- Carte ----
carte_x = 60;
carte_y = 30;
carte_ep = 1.6;
jeu_carte = 0.2;               // par côté, entre le chant de la carte et le boîtier

// ---- Boîtier ----
mur = 2.0;                     // côtés et arrière
mur_avant = 1.6;               // côté fiche : laisse 12,9 mm de fiche dépasser (prise USB : ~12 mm)
plancher = 1.6;
plafond = 1.6;
rayon = 2.0;                   // arrondi des arêtes verticales extérieures
z_fond_int = -2.3;             // dessous : composants jusqu'à z = -1,91 (broches du bornier)
z_plafond_int = 5.2;           // dessus : fiche USB jusqu'à z = 4,84, CH340C 3,35, boutons 3,19
rebord = 1.0;                  // appui de la carte sur le fond (bande sans composant au dos)

// ---- Emboîtement ----
levre_ep = 0.85;               // lèvre du fond, côté intérieur du mur
levre_h = 1.4;                 // reste sous le dessus de la carte (z = 1,6)
jeu_coques = 0.15;             // par côté, entre la lèvre et la jupe du capot
clip_saillie = 0.35;           // bossages d'encliquetage sur la lèvre (serrage 0,2 mm)
clip_long = 12;
serrage = 0.05;                // les nervures du capot appuient sur la carte

// ---- Composants (repère ci-dessus) ----
usb_y = 6.03;                  // fiche USB-A : demi-largeur du blindage
usb_z0 = 0.34;                 // hors carte, le blindage descend sous le dessus de la carte
usb_z1 = 4.84;
jeu_usb = 0.2;
bornier = [21.1, 30.9, -8.36, 7.62];      // x0, x1, y0, y1 du bornier J2 (13,8 mm de haut)
jeu_bornier = 0.4;
j3 = [8.73, 11.27, -3.81, 6.35];          // embase plastique de la barrette SWD
jp1 = [12.73, 15.27, 6.19, 11.27];        // embase de la barrette TERM (cavalier)
jeu_barrette = 0.4;            // laisse entrer un connecteur Dupont jusqu'à l'embase
leds = [[7.0, 10.5], [-0.4, -11.4], [4.4, -11.4]];   // D1 PWR, D2 RX, D3 TX
led_d = 2.2;
boutons = [[-8.2, -11.0], [3.0, 11.0]];  // SW1 RESET, SW2 BOOT0 (Omron B3U, dessus à z = 3,19)
bouton_z = 3.19;

// ---- Poussoirs souples (languette découpée dans le capot) ----
lang_l = 9;                    // longueur libre
lang_w = 4.5;
lang_ep = 1.0;                 // amincie par l'intérieur pour fléchir
fente = 0.6;
lang_bout = 1.2;               // du centre du bouton au bout libre
doigt_d = 1.6;
jeu_doigt = 0.15;              // entre le doigt et le bouton au repos

// ---- Gravures ----
police = "Liberation Sans:style=Bold";
grav = 0.4;

// ---- Cotes dérivées ----
cx = carte_x / 2 + jeu_carte;  // demi-cavité
cy = carte_y / 2 + jeu_carte;
x0 = -cx - mur_avant;
x1 = cx + mur;
y1 = cy + mur;
z_bas = z_fond_int - plancher;
z_haut = z_plafond_int + plafond;

echo(str("Boîtier ", x1 - x0, " x ", 2 * y1, " x ", z_haut - z_bas, " mm ; fiche USB dépassant de ",
         44.7 + x0, " mm"));
assert(z_fond_int < -1.91 - 0.3, "plancher trop haut pour les broches du bornier");
assert(z_plafond_int > usb_z1 + 0.3, "plafond trop bas pour la fiche USB");
assert(levre_h < carte_ep - 0.1, "la lèvre doit rester sous le dessus de la carte");
assert(mur - levre_ep - jeu_coques >= 0.8, "jupe du capot trop fine");

module rect(r) { translate([r[0], r[2]]) square([r[1] - r[0], r[3] - r[2]]); }
module grossi(r, j) { rect([r[0] - j, r[1] + j, r[2] - j, r[3] + j]); }

// Contour extérieur : arêtes verticales arrondies.
module contour() {
    translate([x0 + rayon, -y1 + rayon]) offset(r = rayon) square([x1 - x0 - 2 * rayon, 2 * y1 - 2 * rayon]);
}
module cavite() { translate([-cx, -cy]) square([2 * cx, 2 * cy]); }
// Anneau de la lèvre (côtés et arrière ; pas à l'avant, où passe la fiche).
module anneau(e, debut) {
    intersection() {
        difference() { offset(r = e) cavite(); cavite(); }
        translate([debut, -50]) square([100, 100]);
    }
}
// Bossage (ou rainure) triangulaire le long de x, sur la face y = s*yf, entre za et zb.
// Flancs à 41° de la verticale : imprimable sans support dans les deux coques.
module clip(s, xc, yf, saillie, za, zb, long) {
    translate([xc - long / 2, 0, 0]) rotate([90, 0, 90]) linear_extrude(long)
        polygon([[s * yf, za], [s * (yf + saillie), (za + zb) / 2], [s * yf, zb]]);
}
module texte(t, taille, pos, rot = 0) {
    translate(pos) rotate(rot) text(t, size = taille, font = police, halign = "center", valign = "center");
}

// ---------------------------------------------------------------------------------------------
module fond() {
    difference() {
        union() {
            // Coque : plancher et murs jusqu'au plan de joint z = 0.
            difference() {
                translate([0, 0, z_bas]) linear_extrude(-z_bas) contour();
                translate([0, 0, z_fond_int]) linear_extrude(-z_fond_int + eps) cavite();
            }
            // Rebord d'appui sous le pourtour de la carte.
            translate([0, 0, z_fond_int - eps]) linear_extrude(-z_fond_int + eps)
                difference() { cavite(); offset(delta = -(jeu_carte + rebord)) cavite(); }
            // Lèvre d'emboîtement.
            translate([0, 0, -eps]) linear_extrude(levre_h + eps) anneau(levre_ep, -cx + jeu_coques);
            // Bossages d'encliquetage sur les grands côtés (profil triangulaire, 40° au plus).
            for (s = [-1, 1], xc = [-14, 14]) clip(s, xc, cy + levre_ep - eps, clip_saillie, 0.45, 1.25, clip_long);
        }
        // Gravure sous le fond, lisible par en dessous.
        translate([0, 0, z_bas - eps]) linear_extrude(grav + eps) mirror([0, 1, 0]) {
            texte("G69  USB-CAN", 4.2, [0, 3.2]);
            texte("v0.2  ENSEA", 3, [0, -3.2]);
        }
    }
}

// ---------------------------------------------------------------------------------------------
module languette(b) {
    // Poussoir : languette ancrée côté -x, bout libre au-delà du bouton.
    bout = b[0] + lang_bout;
    translate([bout - lang_l, b[1] - lang_w / 2]) square([lang_l, lang_w]);
}
module fente_languette(b) {
    difference() {
        offset(delta = fente) languette(b);
        languette(b);
        // laisse la racine attachée
        translate([b[0] + lang_bout - lang_l - fente - eps, b[1] - lang_w / 2 - fente - eps])
            square([fente + 2 * eps, lang_w + 2 * fente + 2 * eps]);
    }
}

module capot() {
    // Doigts des poussoirs, sous les languettes (ajoutés après l'amincissement).
    for (b = boutons)
        translate([b[0], b[1], bouton_z + jeu_doigt])
            cylinder(d = doigt_d, h = z_haut - lang_ep - bouton_z - jeu_doigt + eps);
    difference() {
        union() {
            difference() {
                linear_extrude(z_haut) contour();
                translate([0, 0, -eps]) linear_extrude(z_plafond_int + eps) cavite();
                // Rainure de la jupe qui reçoit la lèvre.
                translate([0, 0, -eps]) linear_extrude(levre_h + 0.1 + eps)
                    anneau(levre_ep + jeu_coques, -cx - eps);
                for (s = [-1, 1], xc = [-14, 14])
                    clip(s, xc, cy + levre_ep + jeu_coques - eps, clip_saillie + 0.1, 0.35, 1.35, clip_long + 1);
            }
            // Nervures qui plaquent la carte sur le rebord du fond : grands côtés et avant.
            for (s = [-1, 1]) {
                translate([-cx, s > 0 ? cy - 0.8 : -cy, carte_ep - serrage])
                    cube([2 * cx, 0.8, z_plafond_int - carte_ep + serrage + eps]);
                translate([-cx, s > 0 ? usb_y + 0.6 : -cy, carte_ep - serrage])
                    cube([0.8, cy - usb_y - 0.6, z_plafond_int - carte_ep + serrage + eps]);
            }
        }
        // Fiche USB : encoche ouverte vers le plan de joint.
        translate([x0 - eps, -usb_y - jeu_usb, -eps])
            cube([mur_avant + 2 * eps, 2 * (usb_y + jeu_usb), usb_z1 + jeu_usb + eps]);
        // Bornier : fenêtre dans le dessus et encoche dans le mur arrière (il dépasse du capot).
        translate([0, 0, -eps]) linear_extrude(z_haut + 2 * eps)
            union() {
                grossi([bornier[0], 50, bornier[2], bornier[3]], jeu_bornier);
            }
        // Barrettes SWD et TERM : l'embase reste sous le capot, les broches sortent.
        translate([0, 0, z_plafond_int - eps]) linear_extrude(plafond + 2 * eps) {
            grossi(j3, jeu_barrette);
            grossi(jp1, jeu_barrette);
            rect([j3[1] + jeu_barrette - eps, jp1[0] - jeu_barrette + eps,
                  jp1[2] - jeu_barrette, j3[3] + jeu_barrette]);
        }
        // LED.
        for (l = leds) translate([l[0], l[1], z_plafond_int - eps]) cylinder(d = led_d, h = plafond + 2 * eps);
        // Poussoirs : fente en U et amincissement par l'intérieur.
        for (b = boutons) {
            translate([0, 0, z_plafond_int - eps]) linear_extrude(plafond + 2 * eps) fente_languette(b);
            translate([0, 0, z_plafond_int - eps]) linear_extrude(plafond - lang_ep + eps)
                offset(delta = fente) languette(b);
        }
        // Gravures sur le dessus.
        translate([0, 0, z_haut - grav]) linear_extrude(grav + eps) {
            texte("USB-CAN", 4.4, [-14, 0.6]);
            texte("G69", 3, [-14, -4.4]);
            texte("RST", 2.4, [-20.5, -11]);
            texte("BOOT", 2.4, [-10.4, 11]);
            texte("PWR", 2.2, [6.0, 13.8]);
            texte("RX", 2.2, [-0.4, -14.2]);
            texte("TX", 2.2, [4.4, -14.2]);
            texte("SWD", 2.2, [10.0, -6.6]);
            texte("TERM", 2.2, [15.8, 13.8]);
            for (p = [["H", 5.08], ["L", 0], ["G", -5.08]]) texte(p[0], 2.6, [18.6, p[1]]);
        }
    }
}

// ---------------------------------------------------------------------------------------------
module carte() {
    if (carte_stl != "") color("darkgreen") import(carte_stl);
}

if (piece == "fond") fond();
else if (piece == "capot") translate([0, 0, z_haut]) rotate([180, 0, 0]) capot();  // dessus sur le plateau
else if (piece == "eclate") {
    color("gainsboro") fond();
    translate([0, 0, 22]) color("gainsboro", 0.9) capot();
    translate([0, 0, 11]) carte();
}
else if (piece == "coupe") {
    intersection() {
        union() { color("gainsboro") fond(); color("lightsteelblue") capot(); carte(); }
        translate([-50, -50, -10]) cube([100, 50 + coupe_y, 40]);
    }
}
else {
    color("gainsboro") fond();
    color("gainsboro", 0.6) capot();
    carte();
}
