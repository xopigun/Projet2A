"""Prévisualisation de la boîte du banc avec les modèles 3D réels, rendue par Blender.

    blender --background --python previsualisation.py -- <dossier de travail>

Le dossier de travail doit contenir :
- carte_porteuse.glb : kicad-cli pcb export glb --subst-models --user-origin 100x100mm
  ../carte_porteuse/carte_porteuse.kicad_pcb
- couvercle_pose.stl : openscad -D 'piece="couvercle_pose"' boitier_banc.scad

Modèles réels : carte porteuse v0.3 (export du PCB), Nucleo-G431KB (simulation_3d/modeles),
adaptateur USB-CAN et son boîtier (visualisation_banc/modeles), bac et couvercle (STL).
Sans fichier 3D, donc en volumes simples aux dimensions connues : écrans OLED, MPU-6050,
hub USB, bornes Wago, interrupteurs, fiches micro-USB.

Repère : celui de boitier_banc.scad (mm, origine au coin intérieur avant gauche, z vers le haut).
"""
import math
import sys
from pathlib import Path

import bpy

ICI = Path(__file__).parent
BANC = ICI.parent.parent
TRAVAIL = Path(sys.argv[sys.argv.index("--") + 1])

# Cotes reprises de boitier_banc.scad
PAS, MARGE, H_ENT, H_INT = 58, 2, 6, 42
HUB, HUB_POS = (100, 30, 15), (20, 112)
ADAPT_CENTRE = (87.2, 186.9)
WAGO_POS = (160, 150)
INTER_X, INTER_Y = (156, 186, 216), 208


def nx(n, X):
    return X - 89.5 + n * PAS + MARGE


def ny(Y):
    return 164.0 - Y


def matiere(nom, rgb, rugosite=0.6, alpha=1.0, emission=0.0, metal=0.0):
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rugosite
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    if emission:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emission
    return m


def boite(x0, y0, z0, dx, dy, dz, mat, nom="volume"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    o = bpy.context.object
    o.scale = (dx, dy, dz)
    o.name = nom
    o.data.materials.append(mat)
    return o


def cylindre(x, y, z0, d, h, mat, incl=0.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=d / 2, depth=h, location=(x, y, z0 + h / 2), rotation=(incl, 0, 0))
    bpy.context.object.data.materials.append(mat)
    return bpy.context.object


def cable(points, d, mat, nom="câble"):
    c = bpy.data.curves.new(nom, "CURVE")
    c.dimensions = "3D"
    c.bevel_depth = d / 2
    c.bevel_resolution = 6
    sp = c.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for pt, co in zip(sp.points, points):
        pt.co = (*co, 1)
    sp.use_endpoint_u = True
    sp.order_u = 3
    o = bpy.data.objects.new(nom, c)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    return o


def importe(chemin, position, rot_z=0.0, echelle=1.0, mat=None):
    """Importe un GLB ou un STL sous un objet vide placé à `position`."""
    avant = set(bpy.data.objects)
    if chemin.suffix == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(chemin))
    else:
        bpy.ops.wm.stl_import(filepath=str(chemin))
    nouveaux = [o for o in bpy.data.objects if o not in avant]
    bpy.ops.object.empty_add(location=(0, 0, 0))
    racine = bpy.context.object
    racine.name = chemin.stem
    for o in nouveaux:
        if o.parent is None:
            o.parent = racine
        if mat is not None and o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat)
    racine.scale = (echelle,) * 3
    racine.rotation_euler = (0, 0, rot_z)
    racine.location = position
    return racine


def scene_vide():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = 48
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 1800, 1150
    s.view_settings.view_transform = "Standard"
    monde = bpy.data.worlds.new("monde")
    monde.use_nodes = True
    monde.node_tree.nodes["Background"].inputs[0].default_value = (0.93, 0.94, 0.95, 1)
    monde.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    s.world = monde
    bpy.ops.object.light_add(type="AREA", location=(60, -160, 320))
    lum = bpy.context.object
    lum.data.energy = 3.5e5
    lum.data.size = 300
    lum.rotation_euler = (math.radians(25), 0, 0)
    bpy.ops.mesh.primitive_plane_add(size=3000, location=(120, 110, -2.05))
    bpy.context.object.data.materials.append(matiere("table", (0.86, 0.87, 0.88), 0.9))
    return s


def camera(s, position, cible, focale=50):
    bpy.ops.object.camera_add(location=position)
    cam = bpy.context.object
    cam.data.lens = focale
    cam.data.clip_end = 5000
    bpy.ops.object.empty_add(location=cible)
    c = cam.constraints.new("TRACK_TO")
    c.target = bpy.context.object
    s.camera = cam


def contenu(M):
    for n in range(4):
        # Carte porteuse : export KiCad, origine en (100, 100), dessous de la carte à z = 0
        importe(TRAVAIL / "carte_porteuse.glb", (nx(n, 100), ny(100), H_ENT), echelle=1000)
        # Nucleo : USB vers l'arrière, carte à 12,6 mm au-dessus du dessous de la porteuse
        importe(BANC / "simulation_3d/modeles/nucleo_g431kb.glb",
                (nx(n, 119.05), ny(132.78), H_ENT + 12.6), rot_z=-math.pi / 2, echelle=1000)
        # Fiche micro-USB du câble de la Nucleo
        boite(nx(n, 113.5), ny(104.8), H_ENT + 11.5, 11, 24.8, 5.5, M["noir"], "fiche USB")
        # Écran OLED debout, à l'envers : circuit, verre, zone allumée
        boite(nx(n, 105.4), ny(161.1), H_ENT + 1.0, 27.3, 1.6, 27.8, M["pcb_bleu"], "OLED")
        boite(nx(n, 106.0), ny(162.5), H_ENT + 6.0, 26.0, 1.4, 19.0, M["noir"], "OLED verre")
        boite(nx(n, 119.05) - 10.85, ny(162.5) - 0.05, H_ENT + 7.6, 21.7, 0.1, 10.9, M["ecran"], "OLED image")
        if n == 1:   # MPU-6050 (GY-521) debout, sur N2
            boite(nx(n, 93.6), ny(138.5), H_ENT + 1.0, 1.6, 21.2, 16.6, M["pcb_bleu"], "MPU-6050")
    # Hub USB : volume aux cotes du modèle (non mesuré)
    boite(HUB_POS[0], HUB_POS[1], 0, *HUB, M["blanc"], "hub USB")
    # Câble USB du hub vers le PC : sort du bout gauche du hub, passe par l'encoche arrière
    cable([(20, 127, 8), (8, 127, 8), (6, 150, 10), (20, 200, 22), (50, 212, 34), (70, 217, 36),
           (70, 232, 36), (72, 250, 20), (80, 275, 2), (120, 330, 2)], 4.0, M["blanc"], "câble USB vers le PC")
    boite(132, 322, 0, 40, 16, 8, M["blanc"], "fiche USB-A vers le PC")
    boite(172, 324, 1.75, 12, 12, 4.5, M["metal"], "fiche USB-A")
    cable([(120, 330, 2), (126, 331, 3), (132, 330, 4)], 4.0, M["blanc"])
    # Adaptateur USB-CAN v0.2 dans son boîtier, fiche USB vers le hub
    for f, mat in ((BANC / "hardware/visualisation_banc/modeles/boitier.stl", M["coque"]),
                   (BANC / "hardware/visualisation_banc/modeles/adaptateur_min.glb", None)):
        importe(f, (*ADAPT_CENTRE, 3.9), rot_z=math.pi / 2, echelle=1 if f.suffix == ".stl" else 1000, mat=mat)
    # Trois bornes Wago 221-420 debout
    for i in range(3):
        boite(WAGO_POS[0] + i * 17 + 0.6, WAGO_POS[1], 0, 15.8, 18.3, 29.8, M["wago"], "Wago 221-420")
        boite(WAGO_POS[0] + i * 17 + 2.6, WAGO_POS[1] + 4, 29.8, 11.8, 12, 1.5, M["orange"], "levier Wago")
    # Interrupteurs de faute : corps sous le couvercle, canon et levier au-dessus
    for x in INTER_X:
        boite(x - 6.5, INTER_Y - 4, H_INT - 14, 13, 8, 14, M["rouge"], "interrupteur")
        cylindre(x, INTER_Y, H_INT, 6, 9, M["metal"])
        cylindre(x, INTER_Y - 1.5, H_INT + 8, 3, 11, M["metal"], incl=math.radians(14))


def construit(couvercle):
    s = scene_vide()
    M = {
        "pla": matiere("PLA", (0.80, 0.82, 0.84), 0.55),
        "couvercle": matiere("couvercle", (0.36, 0.50, 0.68), 0.5, alpha=1.0 if couvercle == "plein" else 0.28),
        "noir": matiere("noir", (0.03, 0.03, 0.03), 0.4),
        "pcb_bleu": matiere("pcb bleu", (0.05, 0.16, 0.45), 0.5),
        "ecran": matiere("ecran", (0.45, 0.80, 1.0), 0.2, emission=4.0),
        "blanc": matiere("blanc", (0.92, 0.92, 0.90), 0.35),
        "coque": matiere("coque", (0.10, 0.11, 0.11), 0.7),
        "wago": matiere("wago", (0.85, 0.88, 0.86), 0.25, alpha=0.75),
        "orange": matiere("orange", (0.90, 0.38, 0.05), 0.45),
        "rouge": matiere("rouge", (0.65, 0.06, 0.05), 0.5),
        "metal": matiere("metal", (0.75, 0.76, 0.78), 0.25, metal=1.0),
    }
    importe(ICI / "bac.stl", (0, 0, 0), mat=M["pla"])
    contenu(M)
    if couvercle:
        importe(TRAVAIL / "couvercle_pose.stl", (0, 0, 0), mat=M["couvercle"])
    return s


def rendu(nom, couvercle, position, cible, focale=50):
    s = construit(couvercle)
    camera(s, position, cible, focale)
    s.render.filepath = str(ICI / nom)
    bpy.ops.render.render(write_still=True)


rendu("preview_ouverte.png", None, (118, -250, 470), (118, 125, 10), 50)
rendu("preview_arriere.png", "plein", (330, 520, 260), (110, 150, 15), 50)
rendu("preview_fermee.png", "plein", (-120, -330, 260), (118, 95, 15), 50)
rendu("preview_transparente.png", "verre", (380, -280, 320), (118, 105, 12), 50)
