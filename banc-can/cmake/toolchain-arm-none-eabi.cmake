# Chaine de compilation croisee ARM pour les firmwares du banc.
# Ne fixe que le compilateur : les options propres au coeur (Cortex-M4F ou M3)
# sont portees par chaque cible dans firmware/, via bench_target_cpu().

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# Sans systeme d'exploitation, CMake ne peut pas produire d'executable de test :
# on lui demande de valider le compilateur sur une bibliotheque statique.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(BENCH_ARM_PREFIX arm-none-eabi- CACHE STRING "Prefixe de la chaine de compilation ARM")

find_program(BENCH_ARM_GCC     ${BENCH_ARM_PREFIX}gcc     REQUIRED)
find_program(BENCH_ARM_GXX     ${BENCH_ARM_PREFIX}g++)
find_program(BENCH_ARM_OBJCOPY ${BENCH_ARM_PREFIX}objcopy REQUIRED)
find_program(BENCH_ARM_SIZE    ${BENCH_ARM_PREFIX}size    REQUIRED)

set(CMAKE_C_COMPILER   ${BENCH_ARM_GCC})
set(CMAKE_ASM_COMPILER ${BENCH_ARM_GCC})
if(BENCH_ARM_GXX)
    set(CMAKE_CXX_COMPILER ${BENCH_ARM_GXX})
endif()

set(CMAKE_OBJCOPY ${BENCH_ARM_OBJCOPY} CACHE FILEPATH "objcopy" FORCE)
set(CMAKE_SIZE    ${BENCH_ARM_SIZE}    CACHE FILEPATH "size"    FORCE)

# Ne chercher les programmes que sur l'hote, et les bibliotheques/en-tetes que dans le sysroot.
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM BEFORE)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
