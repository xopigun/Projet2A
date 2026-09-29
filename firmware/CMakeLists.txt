# Firmware d'un nœud du banc.
#
# Un seul exécutable par configuration, le rôle venant de BENCH_NODE_ID.
# La carte cible en découle : N1 à N3 sur Nucleo-G431KB, N4 sur Blue Pill F103.

set(VENDOR ${CMAKE_CURRENT_SOURCE_DIR}/vendor)

# ---------------------------------------------------------------------------
#  Choix de la cible d'après le rôle
# ---------------------------------------------------------------------------
if(BENCH_NODE_ID EQUAL 4)
    set(BENCH_BOARD_DIR ${CMAKE_CURRENT_SOURCE_DIR}/boards/bluepill_f103)
    set(BENCH_PORT_DIR  ${CMAKE_CURRENT_SOURCE_DIR}/ports/f103_bxcan)
    set(BENCH_MCU_FAMILY f1)
    # Le STM32F103C8 est un « medium density » : il partage l'en-tete xB.
    set(BENCH_MCU_DEVICE STM32F103xB)
    set(BENCH_CPU_FLAGS -mcpu=cortex-m3 -mthumb -mfloat-abi=soft)
    set(BENCH_STARTUP ${VENDOR}/cmsis_device_f1/Source/Templates/gcc/startup_stm32f103xb.s)
    set(BENCH_LINKER_SCRIPT ${BENCH_PORT_DIR}/STM32F103C8Tx_FLASH.ld)
    set(BENCH_VECTORS SysTick_Handler USB_LP_CAN1_RX0_IRQHandler USB_HP_CAN1_TX_IRQHandler)
    if(BENCH_CLOCK_SOURCE STREQUAL "HSI")
        message(FATAL_ERROR
            "Pas de repli HSI pour N4 : le quartz de la Blue Pill est cable d'origine, "
            "et le HSI du F103 ne permet pas le meme arbre d'horloge. Utiliser HSE.")
    endif()
else()
    set(BENCH_BOARD_DIR ${CMAKE_CURRENT_SOURCE_DIR}/boards/nucleo_g431kb)
    set(BENCH_PORT_DIR  ${CMAKE_CURRENT_SOURCE_DIR}/ports/g431_fdcan)
    set(BENCH_MCU_FAMILY g4)
    set(BENCH_MCU_DEVICE STM32G431xx)
    set(BENCH_CPU_FLAGS -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard)
    set(BENCH_STARTUP ${VENDOR}/cmsis_device_g4/Source/Templates/gcc/startup_stm32g431xx.s)
    set(BENCH_LINKER_SCRIPT ${BENCH_PORT_DIR}/STM32G431KBTx_FLASH.ld)
    set(BENCH_VECTORS SysTick_Handler FDCAN1_IT0_IRQHandler)
endif()

set(BENCH_ELF n${BENCH_NODE_ID})

# ---------------------------------------------------------------------------
#  Bibliothèque HAL — uniquement les modules dont le banc a besoin
# ---------------------------------------------------------------------------
set(HAL_DIR ${VENDOR}/stm32${BENCH_MCU_FAMILY}xx_hal_driver)
set(HAL_PREFIX stm32${BENCH_MCU_FAMILY}xx_hal)

# Modules presents sous le meme nom dans les deux HAL.
set(HAL_MODULES
    ${HAL_DIR}/Src/${HAL_PREFIX}.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_cortex.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_dma.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_exti.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_flash.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_flash_ex.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_gpio.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_i2c.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_pwr.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_rcc.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_rcc_ex.c
    ${HAL_DIR}/Src/${HAL_PREFIX}_uart.c
)
# Modules propres a chaque famille : le controleur CAN en premier lieu.
if(BENCH_MCU_FAMILY STREQUAL "g4")
    list(APPEND HAL_MODULES
        ${HAL_DIR}/Src/${HAL_PREFIX}_dma_ex.c
        ${HAL_DIR}/Src/${HAL_PREFIX}_fdcan.c
        ${HAL_DIR}/Src/${HAL_PREFIX}_i2c_ex.c
        ${HAL_DIR}/Src/${HAL_PREFIX}_pwr_ex.c
        ${HAL_DIR}/Src/${HAL_PREFIX}_uart_ex.c)
else()
    list(APPEND HAL_MODULES
        ${HAL_DIR}/Src/${HAL_PREFIX}_can.c
        ${HAL_DIR}/Src/${HAL_PREFIX}_gpio_ex.c)
endif()

add_library(bench_hal STATIC
    ${HAL_MODULES}
    ${VENDOR}/cmsis_device_${BENCH_MCU_FAMILY}/Source/Templates/system_stm32${BENCH_MCU_FAMILY}xx.c
)
target_include_directories(bench_hal PUBLIC
    ${BENCH_PORT_DIR}                      # stm32<famille>xx_hal_conf.h du projet
    ${HAL_DIR}/Inc
    ${VENDOR}/cmsis_device_${BENCH_MCU_FAMILY}/Include
    ${VENDOR}/cmsis_core/Core/Include
)
target_compile_definitions(bench_hal PUBLIC ${BENCH_MCU_DEVICE} USE_HAL_DRIVER)
target_compile_options(bench_hal PUBLIC ${BENCH_CPU_FLAGS})
# Code fourni par ST : on ne le corrige pas, on n'impose donc pas nos options
# strictes. Nos propres avertissements restent actifs sur le reste du projet.
target_compile_options(bench_hal PRIVATE -w)

# ---------------------------------------------------------------------------
#  Code commun — aucune dépendance HAL (vérifié par un test natif)
# ---------------------------------------------------------------------------
set(COMMON ${CMAKE_CURRENT_SOURCE_DIR}/common)

add_library(bench_app STATIC
    ${COMMON}/icd_gen/icd_gen.c
    ${COMMON}/util/ring_buffer.c
    ${COMMON}/protocol/arbitration.c
    ${COMMON}/protocol/heartbeat.c
    ${COMMON}/app/node.c
    ${COMMON}/app/faults.c
)
target_include_directories(bench_app PUBLIC ${COMMON} ${COMMON}/icd_gen ${BENCH_BOARD_DIR})

# Source d'horloge du noeud. HSE par defaut : c'est la seule reference valable
# pour le CAN. HSI n'est qu'un repli pour travailler avant la soudure de SB9/SB10 ;
# il declenche un avertissement a la compilation et le noeud le signale ensuite
# dans son heartbeat (clock_not_qualified).
set(BENCH_CLOCK_SOURCE "HSE" CACHE STRING "Source d'horloge : HSE (defaut) ou HSI (repli non valide)")
set_property(CACHE BENCH_CLOCK_SOURCE PROPERTY STRINGS HSE HSI)
if(BENCH_CLOCK_SOURCE STREQUAL "HSI")
    target_compile_definitions(bench_app PUBLIC BENCH_CLOCK_SOURCE=2)
    message(WARNING "Horloge HSI : reference NON CONFORME pour le CAN. Le debit ne "
                    "pourra pas etre valide. Souder SB9 et SB10 puis repasser en HSE.")
elseif(NOT BENCH_CLOCK_SOURCE STREQUAL "HSE")
    message(FATAL_ERROR "BENCH_CLOCK_SOURCE doit valoir HSE ou HSI, pas « ${BENCH_CLOCK_SOURCE} ».")
endif()
target_link_libraries(bench_app PUBLIC bench_hal)

# ---------------------------------------------------------------------------
#  Exécutable
# ---------------------------------------------------------------------------
# Programme principal et appels systeme : communs aux deux cartes (entry/).
# Le mode autotest remplace main.c par selftest.c : meme port, meme code commun,
# seul le programme principal change (voir docs/bringup.md).
set(ENTRY ${CMAKE_CURRENT_SOURCE_DIR}/entry)
option(BENCH_SELFTEST "Compiler l'autotest de mise en route au lieu du firmware" OFF)

# Bus direct : deux cartes reliées fil à fil, sans transceiver (essai sur table).
option(BENCH_CAN_DIRECT "TX a drain ouvert pour un bus direct sans transceiver" OFF)
if(BENCH_CAN_DIRECT)
    target_compile_definitions(bench_app PUBLIC BENCH_CAN_DIRECT=1)
    message(WARNING "Bus direct sans transceiver : toutes les cartes reliees doivent porter "
                    "ce firmware, jamais un firmware normal (sortie push-pull).")
endif()
if(BENCH_SELFTEST)
    set(BENCH_MAIN ${ENTRY}/selftest.c)
    message(STATUS "Mode autotest : bouclage interne puis ping/pong")
else()
    set(BENCH_MAIN ${ENTRY}/main.c)
endif()

add_executable(${BENCH_ELF}
    ${BENCH_MAIN}
    ${ENTRY}/syscalls.c
    ${ENTRY}/interrupts.c
    ${BENCH_PORT_DIR}/serial.c
    ${BENCH_PORT_DIR}/clock.c
    ${BENCH_PORT_DIR}/can_port.c
    ${BENCH_STARTUP}
)
target_include_directories(${BENCH_ELF} PRIVATE ${BENCH_PORT_DIR})
target_link_libraries(${BENCH_ELF} PRIVATE bench_app)

target_compile_definitions(${BENCH_ELF} PRIVATE BENCH_NODE_ID=${BENCH_NODE_ID})
target_compile_options(${BENCH_ELF} PRIVATE ${BENCH_CPU_FLAGS})

target_link_options(${BENCH_ELF} PRIVATE
    ${BENCH_CPU_FLAGS}
    -T${BENCH_LINKER_SCRIPT}
    --specs=nano.specs
    # Pas de --specs=nosys.specs : les talons d'appels systeme sont fournis par
    # syscalls.c, ce qui evite un avertissement d'edition de liens par appel.
    -Wl,--gc-sections
    # Le script d'edition de liens produit un segment unique RWX ; l'avertissement
    # des binutils recents ne s'applique pas a une cible sans MMU ni protection
    # memoire configuree.
    -Wl,--no-warn-rwx-segments
    -Wl,-Map=$<TARGET_FILE_DIR:${BENCH_ELF}>/${BENCH_ELF}.map
    -Wl,--print-memory-usage
)
set_target_properties(${BENCH_ELF} PROPERTIES SUFFIX ".elf" LINK_DEPENDS ${BENCH_LINKER_SCRIPT})

# Sections placées séparément pour que --gc-sections puisse faire son travail.
target_compile_options(bench_app PUBLIC -ffunction-sections -fdata-sections)

# ---------------------------------------------------------------------------
#  Sorties et programmation
# ---------------------------------------------------------------------------
add_custom_command(TARGET ${BENCH_ELF} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex   $<TARGET_FILE:${BENCH_ELF}>
            $<TARGET_FILE_DIR:${BENCH_ELF}>/${BENCH_ELF}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${BENCH_ELF}>
            $<TARGET_FILE_DIR:${BENCH_ELF}>/${BENCH_ELF}.bin
    COMMAND ${CMAKE_SIZE} --format=berkeley $<TARGET_FILE:${BENCH_ELF}>
    COMMENT "Tailles flash et RAM de ${BENCH_ELF}"
)

# Garde-fou : un vecteur activé sans gestionnaire retombe sur Default_Handler,
# une boucle infinie, sans erreur ni avertissement. L'édition de liens échoue
# désormais dans ce cas (scripts/check_vectors.py).
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_command(TARGET ${BENCH_ELF} POST_BUILD
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/../scripts/check_vectors.py
            --nm ${CMAKE_NM} $<TARGET_FILE:${BENCH_ELF}> ${BENCH_VECTORS}
    COMMENT "Verification des vecteurs d'interruption de ${BENCH_ELF}"
    VERBATIM
)

bench_add_flash_target(${BENCH_ELF}
    OPENOCD_CFG ${CMAKE_CURRENT_SOURCE_DIR}/../cmake/openocd_${BENCH_MCU_FAMILY}.cfg)
