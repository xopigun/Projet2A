// Boîte imprimée en 3D du banc CAN G69 : 4 nœuds sur carte porteuse v0.3, hub USB,
// adaptateur USB-CAN v0.2 et interrupteurs de faute SW1 à SW3.
// Fermée, elle ne laisse voir que les 4 écrans OLED (façade) et les 3 leviers (dessus).
//
//   openscad -D 'piece="bac"'       -o bac.stl       boitier_banc.scad   // fond sur le plateau
//   openscad -D 'piece="couvercle"' -o couvercle.stl boitier_banc.scad   // déjà retourné : dessus sur le plateau
//   openscad -D 'piece="ensemble"'  boitier_banc.scad                    // vue montée avec le contenu
//   openscad -D 'piece="ouvert"'    boitier_banc.scad                    // sans le couvercle
//
// Repère (mm) : origine au coin intérieur avant gauche du bac, sur le plancher.
// x vers la droite, y vers l'arrière (y = 0 : face intérieure de la façade), z vers le haut.
// Une carte porteuse se place par x = X_kicad - 89,5 + n * pas_noeud + marge_x et
// y = y_facade_kicad - Y_kicad : les cotes viennent de carte_porteuse/generate_pcb.py et de
// carte_porteuse/verification/encombrement.py.
//
// Sans support : le bac s'imprime plancher sur le plateau (les fenêtres des écrans sont des
// ponts de 24 mm), le couvercle s'imprime dessus sur le plateau (gravures côté plateau).

piece = "ensemble";            // "bac", "couvercle", "ensemble", "ouvert", "eclate"
$fn = 48;
eps = 0.01;

// ---- Parois ----
mur = 2.4;                     // 6 passes de buse 0,4
plancher = 2.0;
plafond = 2.4;
rayon = 3.0;                   // arrondi des arêtes verticales extérieures

// ---- Nœuds : carte porteuse v0.3 ----
nb_noeuds = 4;
pas_noeud = 58;                // de X = 89,5 (MPU-6050 debout à 91,0) à 147,5 (fils du bornier)
marge_x = 2;                   // de part et d'autre de la rangée
x0_kicad = 89.5;
y_facade_kicad = 164.0;        // la face de l'écran OLED est à Y = 163,5 : 0,5 mm de jeu
h_entretoise = 6;              // dessous de la carte au-dessus du plancher (soudures : 2 mm)
d_entretoise = 7;
d_vis_carte = 2.8;             // vis M3 autotaraudeuse dans le plastique (M3 taraudé : 2,5)
fixations = [[119.05, 106.3], [119.05, 137.5]];   // H1, H2
appui_bornier = [137.3, 100.2, 2.0, 3.0];         // X, Y, largeur, profondeur : coin arrière droit

// ---- Fenêtre d'un écran OLED 0,96" (module debout, à l'envers) ----
// Module : X 105,4 à 132,7, verre z 6 à 25 au-dessus du dessous de la carte.
// À VÉRIFIER sur un module reçu : position exacte de la zone allumée.
fen_x_kicad = 119.05;          // centre
fen_l = 24;
fen_z0 = 7;                    // au-dessus du dessous de la carte
fen_h = 13;
fen_chanfrein = 1.6;           // évasement vers l'extérieur, pour lire de biais

// ---- Zone arrière : câbles USB des Nucleo, hub, adaptateur ----
y_cartes = 64;                 // arrière des cartes (Y = 100)
y_cables = 100;                // fin de la zone des fiches micro-USB (25 mm) et du rayon des câbles
prof_arriere = 120;            // hub à plat : 28 mm devant (jusqu'aux fiches des Nucleo), 78 mm derrière pour l'adaptateur enfiché
// Hub USB HQ Power HQM121C : barre à ports latéraux orientables, prise d'alimentation sur le
// dessus, câble par un bout (photo du banc). 100 x 30 x 15 mm d'après les revendeurs ;
// la LONGUEUR EST À MESURER : sur la photo le hub paraît plus long.
hub = [100, 30, 15];
hub_pos = [20, 112];
// Adaptateur USB-CAN v0.2 dans son boîtier imprimé (64 x 34,4 x 10,7 mm) : enfiché directement
// dans un port latéral du hub, comme le ZLG aujourd'hui. Pas de berceau : vue seulement.
adapt = [34.4, 64, 10.7];
adapt_pos = [70, 154.9];        // fiche USB (12,9 mm) contre le flanc arrière du hub
jeu_berceau = 0.4;
h_berceau = 6;
ep_berceau = 1.6;

// ---- Hauteur ----
h_int = 42;                    // OLED à 35 mm ; corps des interrupteurs : 14 mm sous le couvercle

// ---- Interrupteurs de faute, sur le couvercle ----
d_inter = 6.2;                 // canon fileté de 6 mm (type MTS-102). À ajuster aux pièces choisies.
inter_y = 208;
inter_x = [156, 186, 216];
inter_nom = ["SW1", "SW2", "SW3"];
inter_role = ["TERM", "H-L", "N4"];

// ---- Sortie des câbles (USB vers le PC, alimentation du hub) ----
sortie_x = 70;
sortie_l = 16;
sortie_h = 12;

// ---- Couvercle ----
jeu_couvercle = 0.25;
h_jupe = 4;
ep_jupe = 1.6;
colonne = 9;                   // colonnes de vis aux 4 coins
d_vis_couv = 2.8;
d_passage = 3.4;
grav = 0.6;

// ---- Cotes dérivées ----
li = nb_noeuds * pas_noeud + 2 * marge_x;          // largeur intérieure
pi_ = y_cables + prof_arriere;                     // profondeur intérieure
le = li + 2 * mur;
pe = pi_ + 2 * mur;
he = plancher + h_int;

function nx(n, X) = X - x0_kicad + n * pas_noeud + marge_x;
function ny(Y) = y_facade_kicad - Y;

module arrondi(l, p, h, r) {
    hull() for (x = [r, l - r], y = [r, p - r]) translate([x, y, 0]) cylinder(r = r, h = h);
}

module colonnes(h, d) {
    for (x = [0, li - colonne], y = [0, pi_ - colonne])
        translate([x, y, 0]) difference() {
            cube([colonne, colonne, h]);
            translate([colonne / 2, colonne / 2, h - 14]) cylinder(d = d, h = 14 + eps);
        }
}

// Butées aux deux bouts du hub, fendues pour son câble : les grands côtés restent libres
// pour les ports latéraux.
module berceau(pos, dim) {
    l = dim[0] + 2 * jeu_berceau; p = dim[1] + 2 * jeu_berceau; fente = 12; retour = 5;
    translate([pos[0] - jeu_berceau, pos[1] - jeu_berceau, 0])
        for (sx = [0, 1]) translate([sx * l, 0, 0]) mirror([sx, 0, 0])
            for (sy = [0, 1]) translate([0, sy * p, 0]) mirror([0, sy, 0]) {
                translate([-ep_berceau, -ep_berceau, 0]) cube([ep_berceau, (p - fente) / 2 + ep_berceau, h_berceau]);
                translate([-ep_berceau, -ep_berceau, 0]) cube([retour + ep_berceau, ep_berceau, h_berceau]);
            }
}

module fenetre(n) {
    x = nx(n, fen_x_kicad); z = h_entretoise + fen_z0;
    hull() {
        translate([x - fen_l / 2, -eps, z]) cube([fen_l, eps, fen_h]);
        translate([x - fen_l / 2 - fen_chanfrein, -mur - eps, z - fen_chanfrein])
            cube([fen_l + 2 * fen_chanfrein, eps, fen_h + 2 * fen_chanfrein]);
    }
    translate([x - fen_l / 2, -mur / 2, z]) cube([fen_l, mur, fen_h]);
}

module bac() {
    difference() {
        translate([-mur, -mur, -plancher]) arrondi(le, pe, he, rayon);
        cube([li, pi_, h_int + eps]);
        for (n = [0 : nb_noeuds - 1]) {
            fenetre(n);
            // repère du nœud gravé au-dessus de sa fenêtre
            translate([nx(n, fen_x_kicad), -mur + grav, h_entretoise + fen_z0 + fen_h + 5])
                rotate([90, 0, 0]) linear_extrude(grav + eps)
                    text(str("N", n + 1), size = 6, halign = "center", font = "Liberation Sans:style=Bold");
        }
        // sortie des câbles, ouverte vers le haut
        translate([sortie_x - sortie_l / 2, pi_ - eps, h_int - sortie_h]) cube([sortie_l, mur + 2 * eps, sortie_h + eps]);
    }
    // entretoises et appui sous le bornier de chaque carte
    for (n = [0 : nb_noeuds - 1]) {
        for (f = fixations) translate([nx(n, f[0]), ny(f[1]), 0]) difference() {
            union() { cylinder(d = d_entretoise, h = h_entretoise); cylinder(d1 = d_entretoise + 4, d2 = d_entretoise, h = 2); }
            translate([0, 0, -eps]) cylinder(d = d_vis_carte, h = h_entretoise + 2 * eps);
        }
        translate([nx(n, appui_bornier[0]), ny(appui_bornier[1]) - appui_bornier[3], 0])
            cube([appui_bornier[2], appui_bornier[3], h_entretoise]);
    }
    berceau(hub_pos, hub);
    colonnes(h_int, d_vis_couv);
}

// Couvercle, dans le repère du bac (dessus à z = h_int + plafond).
module couvercle() {
    difference() {
        union() {
            translate([-mur, -mur, h_int]) arrondi(le, pe, plafond, rayon);
            // jupe de centrage, interrompue aux colonnes et à la sortie des câbles
            difference() {
                translate([jeu_couvercle, jeu_couvercle, h_int - h_jupe])
                    cube([li - 2 * jeu_couvercle, pi_ - 2 * jeu_couvercle, h_jupe]);
                translate([jeu_couvercle + ep_jupe, jeu_couvercle + ep_jupe, h_int - h_jupe - eps])
                    cube([li - 2 * (jeu_couvercle + ep_jupe), pi_ - 2 * (jeu_couvercle + ep_jupe), h_jupe + 2 * eps]);
                for (x = [-eps, li - colonne - 0.5], y = [-eps, pi_ - colonne - 0.5])
                    translate([x, y, h_int - h_jupe - eps]) cube([colonne + 0.5 + eps, colonne + 0.5 + eps, h_jupe + 2 * eps]);
                translate([sortie_x - sortie_l / 2 - 1, pi_ - 6, h_int - h_jupe - eps]) cube([sortie_l + 2, 6, h_jupe + 2 * eps]);
            }
        }
        for (x = [colonne / 2, li - colonne / 2], y = [colonne / 2, pi_ - colonne / 2])
            translate([x, y, h_int - eps]) cylinder(d = d_passage, h = plafond + 2 * eps);
        for (i = [0 : len(inter_x) - 1]) {
            translate([inter_x[i], inter_y, h_int - eps]) cylinder(d = d_inter, h = plafond + 2 * eps);
            translate([inter_x[i], inter_y - 13, h_int + plafond - grav]) linear_extrude(grav + eps)
                text(inter_nom[i], size = 5, halign = "center", font = "Liberation Sans:style=Bold");
            translate([inter_x[i], inter_y - 20, h_int + plafond - grav]) linear_extrude(grav + eps)
                text(inter_role[i], size = 3.6, halign = "center", font = "Liberation Sans");
        }
        translate([li / 2, 30, h_int + plafond - grav]) linear_extrude(grav + eps)
            text("BANC CAN G69", size = 9, halign = "center", font = "Liberation Sans:style=Bold");
    }
}

// ---- Contenu, pour les vues seulement ----
module boite_k(n, x0, x1, y0, y1, z0, z1) {
    translate([nx(n, x0), ny(y1), h_entretoise + z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}
module contenu() {
    contour = [[106.8, 100.0], [139.5, 100.0], [139.5, 116.7], [137.0, 116.7], [137.0, 145.0],
               [129.0, 145.0], [129.0, 157.6], [109.4, 157.6], [109.4, 138.8], [97.7, 138.8],
               [97.7, 116.7], [106.8, 116.7]];
    for (n = [0 : nb_noeuds - 1]) {
        color("darkgreen") translate([0, 0, h_entretoise]) linear_extrude(1.6)
            polygon([for (p = contour) [nx(n, p[0]), ny(p[1])]]);
        color("steelblue") { boite_k(n, 109.8, 128.3, 106.1, 156.4, 10.5, 14.5); boite_k(n, 115.2, 122.9, 104.9, 110.5, 12.6, 15.6); }
        color("dimgray") boite_k(n, 113.5, 124.5, 80.0, 104.8, 11.5, 17.0);          // fiche du câble USB
        color("white") boite_k(n, 105.4, 132.7, 159.5, 161.1, 1.0, 29.0);            // OLED
        color("black") boite_k(n, 106.0, 132.0, 161.1, 162.5, 6.0, 25.0);
        color("green") boite_k(n, 131.0, 138.6, 105.5, 120.9, 1.6, 12.0);            // bornier
        if (n == 1) color("royalblue") boite_k(n, 93.6, 95.2, 117.3, 138.5, 1.0, 17.6);   // MPU-6050 (N2)
    }
    color("silver") translate([hub_pos[0], hub_pos[1], 0]) cube(hub);
    color("orange") translate([adapt_pos[0], adapt_pos[1], 0]) cube(adapt);
    color("silver") translate([adapt_pos[0] + adapt[0] / 2 - 6, adapt_pos[1] - 12.9, 3]) cube([12, 12.9, 4.5]);
    for (x = inter_x) {
        color("red") translate([x - 6.5, inter_y - 4, h_int - 14]) cube([13, 8, 14]);
        color("silver") translate([x, inter_y, h_int]) { cylinder(d = 6, h = 9); rotate([12, 0, 0]) cylinder(d = 3, h = 19); }
    }
}

if (piece == "bac") bac();
else if (piece == "couvercle") translate([0, 0, h_int + plafond]) rotate([180, 0, 0]) couvercle();
else if (piece == "ouvert") { color("gainsboro") bac(); contenu(); }
else if (piece == "eclate") { color("gainsboro") bac(); contenu(); color("lightsteelblue", 0.9) translate([0, 0, 45]) couvercle(); }
else { color("gainsboro") bac(); contenu(); color("lightsteelblue") couvercle(); }

echo(str("Boite : ", le, " x ", pe, " x ", he + plafond, " mm"));
