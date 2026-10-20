/**
 * @file bench_test.h
 * @brief Harnais de test minimal pour les tests natifs du code commun.
 *
 * Le dossier de définition laissait le choix entre Unity et « ctest simple » :
 * c'est la seconde option qui est retenue. Le harnais tient en un en-tête, sans
 * dépendance externe à récupérer ni à épingler, et CTest fournit déjà
 * l'orchestration, le parallélisme et le rapport d'échec.
 *
 * Usage :
 * @code
 *   BENCH_TEST(nom_du_cas) {
 *       BENCH_ASSERT_EQ_UINT(attendu, obtenu);
 *   }
 *
 *   BENCH_TEST_MAIN(nom_du_cas, autre_cas)
 * @endcode
 */

#ifndef BENCH_TEST_H
#define BENCH_TEST_H

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/** Compteur d'échecs du cas de test courant. */
extern int bench_test_failures;

/** Nom du cas de test courant, pour les messages d'erreur. */
extern const char *bench_test_current;

#define BENCH_TEST(name) static void name(void)

#define BENCH_FAIL(fmt, ...)                                                                \
    do {                                                                                    \
        bench_test_failures++;                                                              \
        fprintf(stderr, "%s:%d: [%s] " fmt "\n", __FILE__, __LINE__, bench_test_current,    \
                __VA_ARGS__);                                                               \
    } while (0)

#define BENCH_ASSERT(condition)                                                             \
    do {                                                                                    \
        if (!(condition)) {                                                                 \
            BENCH_FAIL("%s est faux", #condition);                                          \
        }                                                                                   \
    } while (0)

#define BENCH_ASSERT_EQ_INT(expected, actual)                                               \
    do {                                                                                    \
        const int64_t _e = (int64_t)(expected);                                             \
        const int64_t _a = (int64_t)(actual);                                               \
        if (_e != _a) {                                                                     \
            BENCH_FAIL("%s : attendu %" PRId64 ", obtenu %" PRId64, #actual, _e, _a);       \
        }                                                                                   \
    } while (0)

#define BENCH_ASSERT_EQ_UINT(expected, actual)                                              \
    do {                                                                                    \
        const uint64_t _e = (uint64_t)(expected);                                           \
        const uint64_t _a = (uint64_t)(actual);                                             \
        if (_e != _a) {                                                                     \
            BENCH_FAIL("%s : attendu %" PRIu64 ", obtenu %" PRIu64, #actual, _e, _a);       \
        }                                                                                   \
    } while (0)

#define BENCH_ASSERT_EQ_PTR(expected, actual)                                               \
    do {                                                                                    \
        if ((const void *)(expected) != (const void *)(actual)) {                           \
            BENCH_FAIL("%s : pointeurs différents", #actual);                               \
        }                                                                                   \
    } while (0)

/** Compare deux zones mémoire et affiche l'octet fautif en cas d'écart. */
#define BENCH_ASSERT_EQ_MEM(expected, actual, length, context)                              \
    do {                                                                                    \
        const uint8_t *_e = (const uint8_t *)(expected);                                    \
        const uint8_t *_a = (const uint8_t *)(actual);                                      \
        for (size_t _i = 0u; _i < (size_t)(length); _i++) {                                 \
            if (_e[_i] != _a[_i]) {                                                         \
                /* %lu plutôt que %zu : le runtime C de MinGW ne gère pas « z ». */         \
                BENCH_FAIL("%s : octet %lu, attendu 0x%02X, obtenu 0x%02X", (context),      \
                           (unsigned long)_i, (unsigned)_e[_i], (unsigned)_a[_i]);          \
                break;                                                                      \
            }                                                                               \
        }                                                                                   \
    } while (0)

#define BENCH_RUN(name)                                                                     \
    do {                                                                                    \
        const int _before = bench_test_failures;                                            \
        bench_test_current = #name;                                                         \
        name();                                                                             \
        printf("  %-46s %s\n", #name,                                                       \
               (bench_test_failures == _before) ? "ok" : "ECHEC");                          \
    } while (0)

/**
 * @brief Déclare le point d'entrée qui exécute les cas donnés.
 *
 * Renvoie un code de sortie non nul si un seul assert a échoué, ce qui suffit à
 * CTest pour marquer le test en échec.
 */
#define BENCH_TEST_MAIN(...)                                                                \
    int bench_test_failures = 0;                                                            \
    const char *bench_test_current = "";                                                    \
    int main(void) {                                                                        \
        printf("%s\n", __FILE__);                                                           \
        BENCH_TEST_FOREACH(__VA_ARGS__)                                                     \
        if (bench_test_failures != 0) {                                                     \
            fprintf(stderr, "%d assertion(s) en échec\n", bench_test_failures);             \
            return EXIT_FAILURE;                                                            \
        }                                                                                   \
        printf("tous les cas passent\n");                                                   \
        return EXIT_SUCCESS;                                                                \
    }

/* Déroulement de la liste variadique : jusqu'à 12 cas par fichier de test. */
#define BENCH_ARG_N(_1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, N, ...) N
#define BENCH_COUNT(...) BENCH_ARG_N(__VA_ARGS__, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1)

#define BENCH_FE_1(x) BENCH_RUN(x);
#define BENCH_FE_2(x, ...) BENCH_RUN(x); BENCH_FE_1(__VA_ARGS__)
#define BENCH_FE_3(x, ...) BENCH_RUN(x); BENCH_FE_2(__VA_ARGS__)
#define BENCH_FE_4(x, ...) BENCH_RUN(x); BENCH_FE_3(__VA_ARGS__)
#define BENCH_FE_5(x, ...) BENCH_RUN(x); BENCH_FE_4(__VA_ARGS__)
#define BENCH_FE_6(x, ...) BENCH_RUN(x); BENCH_FE_5(__VA_ARGS__)
#define BENCH_FE_7(x, ...) BENCH_RUN(x); BENCH_FE_6(__VA_ARGS__)
#define BENCH_FE_8(x, ...) BENCH_RUN(x); BENCH_FE_7(__VA_ARGS__)
#define BENCH_FE_9(x, ...) BENCH_RUN(x); BENCH_FE_8(__VA_ARGS__)
#define BENCH_FE_10(x, ...) BENCH_RUN(x); BENCH_FE_9(__VA_ARGS__)
#define BENCH_FE_11(x, ...) BENCH_RUN(x); BENCH_FE_10(__VA_ARGS__)
#define BENCH_FE_12(x, ...) BENCH_RUN(x); BENCH_FE_11(__VA_ARGS__)

#define BENCH_CONCAT_(a, b) a##b
#define BENCH_CONCAT(a, b) BENCH_CONCAT_(a, b)
#define BENCH_TEST_FOREACH(...) BENCH_CONCAT(BENCH_FE_, BENCH_COUNT(__VA_ARGS__))(__VA_ARGS__)

#endif /* BENCH_TEST_H */
