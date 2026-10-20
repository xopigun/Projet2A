# Banc de test CAN - G69-BANC-001
#
# Deux modes de compilation :
#   * natif (hote)  : tests unitaires du code commun, aucun en-tete HAL.
#   * croise (ARM)  : firmware d'un noeud, choisi par BENCH_NODE_ID.
# Le mode est deduit du fichier de chaine de compilation (voir CMakePresets.json).

cmake_minimum_required(VERSION 3.24)

project(banc_can
    VERSION     0.1.0
    DESCRIPTION "Banc de test CAN du groupe 69 - firmwares, outils PC et ICD"
    LANGUAGES   C ASM)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Options communes aux deux modes. -Wall -Wextra est exige par la definition de « termine ».
add_compile_options(-Wall -Wextra -Wshadow -Wundef -Wconversion -Wsign-conversion)

set(BENCH_NODE_ID 0 CACHE STRING "Role du noeud a compiler : 1 a 4, 5 pour le pont CAN-USB (L476), ou 0 pour la compilation hote")

if(CMAKE_CROSSCOMPILING)
    # ---------------------------------------------------------------- firmware
    if(NOT BENCH_NODE_ID MATCHES "^[1-5]$")
        message(FATAL_ERROR
            "BENCH_NODE_ID doit valoir 1 a 4 (noeuds) ou 5 (pont CAN-USB) pour une "
            "compilation croisee (valeur recue : « ${BENCH_NODE_ID} »). Utiliser un "
            "preset n1 a n4, bridge ou bridge-direct.")
    endif()

    if(NOT EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/firmware/vendor/cmsis_core/Core/Include)
        message(FATAL_ERROR
            "Les sous-modules ST sont absents. Lancer :\n"
            "    git submodule update --init --recursive")
    endif()

    include(BenchFlash)
    bench_report_flash_tool()

    if(BENCH_NODE_ID EQUAL 5)
        message(STATUS "Cible : pont CAN-USB (Nucleo-L476RG, slcan)")
    else()
        message(STATUS "Cible : firmware du noeud N${BENCH_NODE_ID}")
    endif()
    add_subdirectory(firmware)
else()
    # -------------------------------------------------------------- tests hote
    message(STATUS "Cible : tests unitaires natifs du code commun")
    enable_testing()
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/firmware/tests_host/CMakeLists.txt)
        add_subdirectory(firmware/tests_host)
    else()
        message(STATUS "firmware/tests_host absent : aucun test a construire (lot 3)")
    endif()
endif()
