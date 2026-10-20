@echo off
rem Lance l'interface graphique du banc CAN dans le navigateur.
rem
rem   Double-clic         : simulation sur bus virtuel (aucun materiel requis)
rem   lancer_banc.bat gs_usb   : banc reel, via un CANable 2.0 (candleLight)
rem   lancer_banc.bat slcan COM5 : banc reel, CANable en firmware slcan
rem
rem Ne demande aucune installation : seul Python et les dependances de canbench
rem (python-can, cantools, pyyaml) sont necessaires.

setlocal
cd /d "%~dp0pc"
set "IFACE=%~1"
if "%IFACE%"=="" set "IFACE=virtual"
set "CHAN="
if not "%~2"=="" set "CHAN=--channel %~2"

where python >nul 2>nul
if errorlevel 1 (
    echo Python est introuvable. Installer Python 3.11 ou plus recent depuis python.org.
    pause
    exit /b 1
)

python -c "import can, cantools, yaml" 2>nul
if errorlevel 1 (
    echo Il manque des dependances. Depuis le dossier pc, lancer une fois :
    echo     python -m pip install -e .
    pause
    exit /b 1
)

python -m canbench --interface %IFACE% %CHAN% gui
pause
