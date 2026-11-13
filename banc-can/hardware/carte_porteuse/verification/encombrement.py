"""Contrôle des encombrements de la carte porteuse avec ses modules enfichés (boîtes)."""
import struct, sys, glob, os, itertools
D = sys.argv[1]
def pts(p):
    d = open(p, 'rb').read()
    if d[:5] == b'solid':
        return [tuple(map(float, l.split()[1:4])) for l in d.decode(errors='ignore').splitlines() if l.strip().startswith('vertex')]
    n = struct.unpack('<I', d[80:84])[0]
    out = []
    for i in range(n):
        v = struct.unpack('<12f', d[84 + 50 * i:84 + 50 * i + 48]); out += [v[3:6], v[6:9], v[9:12]]
    return out
# Repère carte : X, Y (mm, KiCad), z vers le haut ; l'export STL donne x = X-100, y = -(Y-100).
boxes = {}
for p in glob.glob(D + '/c_*.stl'):
    q = [v for v in pts(p) if v[2] > 1.65 or v[2] < -0.05]
    if not q: continue
    X = [v[0] + 100 for v in q]; Y = [100 - v[1] for v in q]; Z = [v[2] for v in q]
    boxes[os.path.basename(p)[2:-4]] = (min(X), max(X), min(Y), max(Y), min(Z), max(Z))
MOD = {
    "Nucleo (carte + composants)": (109.8, 128.3, 106.1, 156.4, 10.5, 14.5),
    "Nucleo USB": (115.2, 122.9, 104.9, 110.5, 12.6, 15.6),
    "Fiche USB du câble": (113.5, 124.5, 80.0, 104.8, 11.5, 17.0),
    "Ecran OLED debout": (105.4, 132.7, 159.5, 163.5, 1.0, 29.0),
    "MPU-6050 debout": (91.0, 95.2, 117.3, 138.5, 1.0, 17.6),
    "Fils bornier entrée": (85.0, 98.9, 101.5, 114.6, 1.6, 8.0),
    "Fils bornier sortie": (139.6, 155.0, 101.5, 114.6, 1.6, 8.0),
    "Cavalier TERM": (130.2, 132.8, 117.7, 122.8, 1.6, 10.5),
    "Câble capteurs (Dupont)": (130.2, 132.8, 124.2, 134.4, 1.6, 20.0),
    "Tête de vis H1": (116.3, 121.8, 103.55, 109.05, 1.6, 4.6),
    "Tête de vis H2": (116.3, 121.8, 134.75, 140.25, 1.6, 4.6),
}
def inter(a, b, m=0.0):
    return all(a[2*i] < b[2*i+1] - m and b[2*i] < a[2*i+1] - m for i in range(3))
pb = 0
for (na, a), (nb, b) in itertools.combinations(MOD.items(), 2):
    if inter(a, b) and not {na, nb} <= {"Nucleo (carte + composants)", "Nucleo USB"} and not {na, nb} <= {"Nucleo USB", "Fiche USB du câble"}:
        print("CONFLIT module/module :", na, "<->", nb); pb += 1
for na, a in MOD.items():
    for nc, c in boxes.items():
        # les barrettes de la Nucléo et les borniers sous leurs fils sont des contacts voulus
        if (nc in ("J3", "J4") and na.startswith("Nucleo")) or (nc == "J7" and na == "Cavalier TERM") \
           or (nc == "J8" and na.startswith("Câble capteurs")) or (nc == "J5" and na.startswith("Ecran")) \
           or (nc == "J6" and na.startswith("MPU")) or (nc == "J1" and "entrée" in na) or (nc == "J2" and "sortie" in na):
            continue
        if inter(a, c):
            print(f"CONFLIT {na} <-> {nc} : composant z {c[4]:.1f}..{c[5]:.1f}"); pb += 1
# marge verticale sous la Nucléo
sous = [(n, c[5]) for n, c in boxes.items() if inter(MOD["Nucleo (carte + composants)"][:4] + (-1, 99), c) and n not in ("J3", "J4")]
print("sous la Nucleo :", ", ".join(f"{n} {z:.1f} mm" for n, z in sorted(sous, key=lambda t: -t[1])), "| fond de la Nucleo a 10,5 mm")
for n in ("J1", "J2", "J3", "J5", "J6"):
    print(n, "boîte", tuple(round(v, 1) for v in boxes[n]))
print("conflits :", pb)
