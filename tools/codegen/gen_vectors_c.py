"""Génération des vecteurs de référence sous forme de tableaux C.

Le test natif doit être confronté aux **mêmes** vecteurs que le test Python.
Plutôt que d'embarquer un analyseur JSON dans le code de test, le générateur
produit directement les tableaux C : le fichier JSON et ce fichier C sont issus
de la même fonction ``vectors.build()``, ils ne peuvent donc pas diverger.

Ce que le test vérifie réellement
---------------------------------

Chaque cas porte les **valeurs physiques** d'entrée, pas seulement les octets
attendus. Le test remplit la structure C avec ces valeurs, appelle ``pack()`` et
compare le résultat aux octets produits par la référence Python.

Un simple aller-retour ``unpack()`` puis ``pack()`` ne suffirait pas : il est
auto-cohérent pour n'importe quel motif d'octets et passerait même si les octets
de référence étaient faux. Il faut partir des valeurs physiques pour que les deux
chaînes d'encodage soient réellement comparées.
"""

from __future__ import annotations

from .gen_c import BANNER, _unique_layouts
from .model import Icd, Message
from .vectors import build

MAX_SIGNALS = 16


def generate_header() -> str:
    return "\n".join(
        [
            BANNER,
            "",
            "#ifndef BENCH_ICD_VECTORS_H",
            "#define BENCH_ICD_VECTORS_H",
            "",
            "#include <stddef.h>",
            "#include <stdint.h>",
            "",
            f"#define BENCH_VECTOR_MAX_SIGNALS {MAX_SIGNALS}u",
            "",
            "/**",
            " * Un cas de référence produit par la référence Python.",
            " *",
            " * @c values porte les valeurs physiques d'entrée, dans l'ordre de",
            " * déclaration des signaux de la trame ; @c data porte les octets que la",
            " * référence Python a obtenus à partir de ces valeurs.",
            " */",
            "typedef struct {",
            "    const char *frame;   /**< nom de la disposition de trame */",
            "    const char *label;   /**< description lisible du cas */",
            "    uint16_t    can_id;",
            "    uint8_t     dlc;",
            "    uint8_t     signal_count;",
            "    double      values[BENCH_VECTOR_MAX_SIGNALS];",
            "    uint8_t     data[8];",
            "} bench_vector_t;",
            "",
            "extern const bench_vector_t bench_vectors[];",
            "extern const size_t        bench_vector_count;",
            "",
            "/**",
            " * @brief Encode un cas de référence avec le code C généré.",
            " *",
            " * @param vector cas à encoder",
            " * @param out    tampon de 8 octets recevant le résultat",
            " * @return 1 si la trame porte des signaux, 0 sinon (ARM et GO sont vides)",
            " */",
            "int bench_vector_pack(const bench_vector_t *vector, uint8_t *out);",
            "",
            "#endif /* BENCH_ICD_VECTORS_H */",
            "",
        ]
    )


def _fill_function(message: Message) -> list[str]:
    """Fonction qui remplit la structure de @p message depuis un tableau de doubles."""
    out = [
        f"static void bench_fill_{message.c_name}({message.struct_name} *frame,",
        f"                                        const double *values) {{",
    ]
    for index, signal in enumerate(message.signals):
        cast = signal.c_phys_type
        out.append(f"    frame->{signal.name} = ({cast})values[{index}];")
    out += ["}", ""]
    return out


def generate_source(icd: Icd) -> str:
    data = build(icd)
    layouts = [m for m in _unique_layouts(icd.default) if m.signals]
    by_name = {m.name: m for m in layouts}

    too_many = [m.name for m in layouts if len(m.signals) > MAX_SIGNALS]
    if too_many:
        raise ValueError(
            f"BENCH_VECTOR_MAX_SIGNALS ({MAX_SIGNALS}) est trop petit pour {too_many}"
        )

    out = [BANNER, "", '#include "icd_vectors.h"', "", '#include "icd_gen.h"', "",
           "#include <string.h>", ""]

    # --- tableau des cas ---------------------------------------------------
    out.append("const bench_vector_t bench_vectors[] = {")
    for frame in data["frames"]:
        message = by_name.get(frame["name"])
        signals = message.signals if message else []
        for case in frame["cases"]:
            payload = list(case["data"]) + [0] * (8 - len(case["data"]))
            bytes_literal = ", ".join(f"0x{b:02X}u" for b in payload)

            # Valeurs physiques dans l'ordre des signaux ; défaut si non fixée.
            physical = [
                float(case["values"].get(s.name, s.default)) for s in signals
            ]
            physical += [0.0] * (MAX_SIGNALS - len(physical))
            values_literal = ", ".join(f"{v:.17g}" for v in physical)

            label = case["label"].replace("\\", "").replace('"', "'")
            out.append(
                f'    {{ "{frame["name"]}", "{label}", 0x{frame["can_id"]:03X}u, '
                f'{frame["dlc"]}u, {len(signals)}u,'
            )
            out.append(f"      {{ {values_literal} }},")
            out.append(f"      {{ {bytes_literal} }} }},")
    out += [
        "};",
        "",
        "const size_t bench_vector_count = sizeof(bench_vectors) / sizeof(bench_vectors[0]);",
        "",
    ]

    # --- fonctions de remplissage -----------------------------------------
    for message in layouts:
        out += _fill_function(message)

    # --- dispatcher --------------------------------------------------------
    out += [
        "int bench_vector_pack(const bench_vector_t *vector, uint8_t *out) {",
        "    memset(out, 0, 8);",
        "",
    ]
    for index, message in enumerate(layouts):
        keyword = "if" if index == 0 else "} else if"
        out += [
            f'    {keyword} (strcmp(vector->frame, "{message.name}") == 0) {{',
            f"        {message.struct_name} frame;",
            f"        memset(&frame, 0, sizeof(frame));",
            f"        bench_fill_{message.c_name}(&frame, vector->values);",
            f"        bench_{message.c_name}_pack(out, &frame);",
            "        return 1;",
        ]
    out += [
        "    }",
        "",
        "    return 0;  /* trame sans signal : ARM et GO */",
        "}",
        "",
    ]
    return "\n".join(out)
