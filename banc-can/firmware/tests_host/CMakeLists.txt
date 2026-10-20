# Tests unitaires natifs du code commun.
#
# Le code de firmware/common/ doit compiler sans le moindre en-tête HAL : c'est
# ce qui permet de le tester sur l'hôte et ce qui garantit qu'il reste portable
# entre le G431 (FDCAN) et le F103 (bxCAN). La cible bench_common ci-dessous ne
# reçoit donc aucun chemin d'inclusion vers firmware/vendor/.

set(BENCH_COMMON_DIR ${CMAKE_SOURCE_DIR}/firmware/common)

# --- code commun, compilé nativement ---------------------------------------
add_library(bench_common STATIC
    ${BENCH_COMMON_DIR}/icd_gen/icd_gen.c
    ${BENCH_COMMON_DIR}/util/ring_buffer.c
    ${BENCH_COMMON_DIR}/protocol/arbitration.c
    ${BENCH_COMMON_DIR}/protocol/heartbeat.c
    ${BENCH_COMMON_DIR}/app/node.c
    ${BENCH_COMMON_DIR}/app/faults.c
    ${BENCH_COMMON_DIR}/app/slcan.c
)
target_include_directories(bench_common PUBLIC
    ${BENCH_COMMON_DIR}
    ${BENCH_COMMON_DIR}/icd_gen
)
# libm : le code généré utilise llround().
find_library(BENCH_LIBM m)
if(BENCH_LIBM)
    target_link_libraries(bench_common PUBLIC ${BENCH_LIBM})
endif()

# --- vecteurs de référence générés ------------------------------------------
# Le fichier généré appelle les fonctions pack() du code commun : il a besoin de
# icd_gen.h, d'où la dépendance sur bench_common.
add_library(bench_vectors STATIC generated/icd_vectors.c)
target_include_directories(bench_vectors PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/generated)
target_link_libraries(bench_vectors PUBLIC bench_common)

# --- déclaration des cas de test --------------------------------------------
# bench_add_test(<nom> [sources...]) : un exécutable et une entrée CTest.
function(bench_add_test name)
    add_executable(${name} ${name}.c ${ARGN})
    target_include_directories(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    target_link_libraries(${name} PRIVATE bench_common bench_vectors)
    add_test(NAME ${name} COMMAND ${name})
    set_tests_properties(${name} PROPERTIES TIMEOUT 60)
endfunction()

bench_add_test(test_icd_vectors)
bench_add_test(test_ring_buffer)
bench_add_test(test_arbitration)
bench_add_test(test_heartbeat)
bench_add_test(test_classic_can)
bench_add_test(test_faults)
bench_add_test(test_node)
bench_add_test(test_slcan)

# --- garde-fou : aucun en-tête HAL dans firmware/common ---------------------
#
# Une inclusion de stm32*_hal.h dans common/ casserait la portabilité et ne se
# verrait qu'au moment du portage sur l'autre microcontrôleur. On le détecte ici.
add_test(
    NAME common_sans_hal
    COMMAND ${CMAKE_COMMAND}
            -DBENCH_COMMON_DIR=${BENCH_COMMON_DIR}
            -P ${CMAKE_CURRENT_SOURCE_DIR}/check_no_hal.cmake
)
