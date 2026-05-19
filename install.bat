@echo off
chcp 65001 >nul
echo.
echo  TPG Display — Installation Windows
echo  ────────────────────────────────────
echo.

:: 1. Vérifier Python
echo [ ] Vérification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python non trouvé.
    echo     Téléchargez Python sur https://www.python.org/downloads/
    echo     Cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo [v] %%i

:: 2. Pillow
echo.
echo [ ] Vérification de Pillow...
python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo     Installation de Pillow...
    pip install Pillow
    if errorlevel 1 (
        echo [!] Erreur installation Pillow
        pause
        exit /b 1
    )
)
echo [v] Pillow OK

:: 3. Vérifier tkinter
echo.
echo [ ] Vérification de tkinter...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [!] tkinter non disponible.
    echo     Réinstallez Python en cochant "tcl/tk and IDLE".
    pause
    exit /b 1
)
echo [v] tkinter OK

:: 4. Créer start.bat
echo.
echo [ ] Création du raccourci start.bat...
set SCRIPT_DIR=%~dp0
echo @echo off > "%SCRIPT_DIR%start.bat"
echo cd /d "%SCRIPT_DIR%" >> "%SCRIPT_DIR%start.bat"
echo python tpg_selector.py >> "%SCRIPT_DIR%start.bat"
echo [v] start.bat créé

:: 5. Raccourci bureau
echo.
set SHORTCUT=%USERPROFILE%\Desktop\TPG Display.bat
echo @echo off > "%SHORTCUT%"
echo cd /d "%SCRIPT_DIR%" >> "%SHORTCUT%"
echo pythonw tpg_selector.py >> "%SHORTCUT%"
echo [v] Raccourci bureau créé

:: 6. Résumé
echo.
echo  ✅ Installation terminée !
echo.
echo  Pour lancer l'application :
echo    double-cliquer sur "TPG Display" sur le bureau
echo    ou exécuter : start.bat
echo.
echo  Raccourcis clavier dans l'afficheur :
echo    F11 / F   → plein écran
echo    S         → retour au sélecteur d'arrêt
echo    Echap     → quitter le plein écran
echo.
pause
