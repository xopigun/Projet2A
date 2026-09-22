# Verifie qu'aucun fichier de firmware/common/ n'inclut un en-tete HAL ou CMSIS.
#
# Le code commun doit rester independant du microcontroleur : c'est ce qui permet
# de le tester nativement et de le partager entre le port FDCAN (G431) et le port
# bxCAN (F103). Ce test echoue avec la liste des fichiers fautifs.

file(GLOB_RECURSE sources "${BENCH_COMMON_DIR}/*.c" "${BENCH_COMMON_DIR}/*.h")

set(interdits "")
foreach(source IN LISTS sources)
    file(READ "${source}" contenu)
    if(contenu MATCHES "#[ \t]*include[ \t]*[<\"](stm32|core_cm|cmsis)")
        file(RELATIVE_PATH relatif "${BENCH_COMMON_DIR}" "${source}")
        list(APPEND interdits "${relatif}")
    endif()
endforeach()

list(LENGTH sources total)
if(interdits)
    message(FATAL_ERROR
        "firmware/common/ doit rester independant du materiel, or ces fichiers "
        "incluent un en-tete HAL ou CMSIS :\n  ${interdits}\n"
        "Deplacer l'acces materiel dans firmware/ports/.")
endif()

message(STATUS "${total} fichiers de firmware/common/ verifies : aucun en-tete HAL.")
