/* ===========================================================================
 *  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN
 *
 *  Produit par tools/codegen à partir de icd/bench_icd.yaml.
 *  Toute modification manuelle sera écrasée, et la CI la rejettera.
 *
 *  Regénérer :  python -m tools.codegen
 * ===========================================================================
 */


#ifndef BENCH_ICD_VECTORS_H
#define BENCH_ICD_VECTORS_H

#include <stddef.h>
#include <stdint.h>

#define BENCH_VECTOR_MAX_SIGNALS 16u

/**
 * Un cas de référence produit par la référence Python.
 *
 * @c values porte les valeurs physiques d'entrée, dans l'ordre de
 * déclaration des signaux de la trame ; @c data porte les octets que la
 * référence Python a obtenus à partir de ces valeurs.
 */
typedef struct {
    const char *frame;   /**< nom de la disposition de trame */
    const char *label;   /**< description lisible du cas */
    uint16_t    can_id;
    uint8_t     dlc;
    uint8_t     signal_count;
    double      values[BENCH_VECTOR_MAX_SIGNALS];
    uint8_t     data[8];
} bench_vector_t;

extern const bench_vector_t bench_vectors[];
extern const size_t        bench_vector_count;

/**
 * @brief Encode un cas de référence avec le code C généré.
 *
 * @param vector cas à encoder
 * @param out    tampon de 8 octets recevant le résultat
 * @return 1 si la trame porte des signaux, 0 sinon (ARM et GO sont vides)
 */
int bench_vector_pack(const bench_vector_t *vector, uint8_t *out);

#endif /* BENCH_ICD_VECTORS_H */
