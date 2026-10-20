# Cibles de programmation flash_<node>.
#
# Ni STM32_Programmer_CLI ni openocd ne sont necessairement dans le PATH : on les
# cherche d'abord dans le PATH, puis dans les emplacements d'installation usuels sous
# Windows et sous Linux. Le premier trouve est utilise ; l'autre reste selectionnable
# par -DBENCH_FLASH_TOOL=openocd|cubeprog.

set(BENCH_FLASH_TOOL "auto" CACHE STRING "Outil de programmation : auto, cubeprog ou openocd")
set_property(CACHE BENCH_FLASH_TOOL PROPERTY STRINGS auto cubeprog openocd)

# --- STM32_Programmer_CLI -------------------------------------------------------------
file(GLOB _bench_cubeprog_hints
    "C:/ST/STM32CubeIDE_*/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.*/tools/bin"
    "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin"
    "C:/Program Files (x86)/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin"
    "$ENV{HOME}/STM32CubeProgrammer/bin"
    "/opt/st/stm32cubeprog/bin")
find_program(BENCH_CUBEPROG NAMES STM32_Programmer_CLI HINTS ${_bench_cubeprog_hints})

# --- OpenOCD --------------------------------------------------------------------------
file(GLOB _bench_openocd_hints
    "C:/ST/xpack-openocd-*/bin"
    "C:/Program Files/OpenOCD/bin"
    "$ENV{HOME}/.local/xPacks/openocd/*/.content/bin"
    "/usr/bin" "/usr/local/bin")
find_program(BENCH_OPENOCD NAMES openocd HINTS ${_bench_openocd_hints})

if(BENCH_FLASH_TOOL STREQUAL "auto")
    if(BENCH_CUBEPROG)
        set(BENCH_FLASH_TOOL_RESOLVED cubeprog)
    elseif(BENCH_OPENOCD)
        set(BENCH_FLASH_TOOL_RESOLVED openocd)
    else()
        set(BENCH_FLASH_TOOL_RESOLVED none)
    endif()
else()
    set(BENCH_FLASH_TOOL_RESOLVED ${BENCH_FLASH_TOOL})
endif()

# bench_add_flash_target(<cible> OPENOCD_CFG <fichier de configuration openocd>)
#
# Cree la cible flash_<cible>. Si aucun outil n'est disponible, la cible existe quand
# meme mais affiche un message explicite : la CI ne dispose d'aucun des deux et ne doit
# pas echouer a la configuration pour autant.
function(bench_add_flash_target target)
    cmake_parse_arguments(ARG "" "OPENOCD_CFG" "" ${ARGN})

    if(BENCH_FLASH_TOOL_RESOLVED STREQUAL "cubeprog")
        add_custom_target(flash_${target}
            COMMAND ${BENCH_CUBEPROG} -c port=SWD mode=UR -w $<TARGET_FILE_DIR:${target}>/${target}.hex -rst
            DEPENDS ${target}
            COMMENT "Programmation de ${target} via STM32_Programmer_CLI"
            USES_TERMINAL VERBATIM)
    elseif(BENCH_FLASH_TOOL_RESOLVED STREQUAL "openocd")
        add_custom_target(flash_${target}
            COMMAND ${BENCH_OPENOCD} -f ${ARG_OPENOCD_CFG}
                    -c "program $<TARGET_FILE:${target}> verify reset exit"
            DEPENDS ${target}
            COMMENT "Programmation de ${target} via OpenOCD"
            USES_TERMINAL VERBATIM)
    else()
        add_custom_target(flash_${target}
            COMMAND ${CMAKE_COMMAND} -E echo
                "Aucun outil de programmation trouve. Installer STM32CubeProgrammer ou OpenOCD,"
            COMMAND ${CMAKE_COMMAND} -E echo
                "ou indiquer son emplacement : cmake -DBENCH_CUBEPROG=<chemin> ou -DBENCH_OPENOCD=<chemin>."
            COMMAND ${CMAKE_COMMAND} -E false
            COMMENT "Programmation de ${target} : outil indisponible" VERBATIM)
    endif()
endfunction()

function(bench_report_flash_tool)
    if(BENCH_FLASH_TOOL_RESOLVED STREQUAL "cubeprog")
        message(STATUS "Programmation : STM32_Programmer_CLI (${BENCH_CUBEPROG})")
    elseif(BENCH_FLASH_TOOL_RESOLVED STREQUAL "openocd")
        message(STATUS "Programmation : OpenOCD (${BENCH_OPENOCD})")
    else()
        message(STATUS "Programmation : aucun outil trouve, les cibles flash_* seront inactives")
    endif()
endfunction()
