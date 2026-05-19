#!/bin/bash
# ─── Script d'installation TPG Display ───────────────────────────────────────
# Usage : bash install.sh
# Testé sur : Raspberry Pi OS, Ubuntu, Debian

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${GREEN}🚋 TPG Display — Installation${NC}"
echo "───────────────────────────────"

# Détecter le système
IS_PI=false
IS_LINUX=false
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    IS_PI=true
    IS_LINUX=true
    echo -e "  Système détecté : ${YELLOW}Raspberry Pi${NC}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    IS_LINUX=true
    echo -e "  Système détecté : ${YELLOW}Linux${NC}"
fi

# 1. Python 3
echo ""
echo "▶ Vérification de Python 3..."
if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}Python 3 non trouvé.${NC} Installation..."
    sudo apt update && sudo apt install -y python3
fi
PYTHON_VER=$(python3 --version)
echo -e "  ✓ ${PYTHON_VER}"

# 2. tkinter
echo ""
echo "▶ Vérification de tkinter..."
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "  Installation de tkinter..."
    sudo apt install -y python3-tk
fi
echo -e "  ✓ tkinter OK"

# 3. Pillow (pour la carte dans tpg_selector.py)
echo ""
echo "▶ Vérification de Pillow..."
if ! python3 -c "from PIL import Image" 2>/dev/null; then
    echo "  Installation de Pillow..."
    # Sur Pi/Debian, apt est plus fiable que pip pour Pillow+ImageTk
    if $IS_LINUX; then
        sudo apt install -y python3-pil python3-pil.imagetk 2>/dev/null || \
        pip3 install Pillow --break-system-packages 2>/dev/null || \
        pip3 install Pillow
    else
        pip3 install Pillow
    fi
fi
echo -e "  ✓ Pillow OK"

# 4. Vérifier la connexion internet
echo ""
echo "▶ Vérification de la connexion internet..."
if python3 -c "import urllib.request; urllib.request.urlopen('https://transport.opendata.ch', timeout=5)" 2>/dev/null; then
    echo -e "  ✓ API transport.opendata.ch accessible"
else
    echo -e "  ${YELLOW}⚠ API non accessible — mode simulation disponible${NC}"
fi

# 5. Créer le script de lancement
echo ""
echo "▶ Création du raccourci de lancement..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat > "$SCRIPT_DIR/start.sh" << LAUNCH
#!/bin/bash
cd "$SCRIPT_DIR"
python3 tpg_selector.py
LAUNCH
chmod +x "$SCRIPT_DIR/start.sh"
echo -e "  ✓ start.sh créé"

# 6. Sur Pi : créer entrée dans le menu applications
if $IS_PI; then
    echo ""
    echo "▶ Création du raccourci bureau (Raspberry Pi)..."
    DESKTOP_FILE="$HOME/Desktop/TPG-Display.desktop"
    cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Name=TPG Display
Comment=Panneau d'arrêt TPG
Exec=bash $SCRIPT_DIR/start.sh
Icon=applications-internet
Terminal=false
Type=Application
Categories=Utility;
DESKTOP
    chmod +x "$DESKTOP_FILE"
    echo -e "  ✓ Icône créée sur le bureau"

    # Option démarrage automatique
    echo ""
    read -p "  Lancer automatiquement au démarrage du Pi ? [o/N] " AUTO
    if [[ "$AUTO" =~ ^[Oo]$ ]]; then
        AUTOSTART_DIR="$HOME/.config/autostart"
        mkdir -p "$AUTOSTART_DIR"
        cat > "$AUTOSTART_DIR/tpg-display.desktop" << AUTOSTART
[Desktop Entry]
Name=TPG Display
Exec=bash -c "sleep 5 && python3 $SCRIPT_DIR/tpg_selector.py"
Type=Application
X-GNOME-Autostart-enabled=true
AUTOSTART
        echo -e "  ✓ Démarrage automatique activé (délai 5s)"
    fi
fi

# 7. Résumé
echo ""
echo -e "${GREEN}✅ Installation terminée !${NC}"
echo ""
echo "  Pour lancer l'application :"
echo -e "    ${YELLOW}python3 $SCRIPT_DIR/tpg_selector.py${NC}"
echo "  ou :"
echo -e "    ${YELLOW}bash $SCRIPT_DIR/start.sh${NC}"
if $IS_PI; then
    echo "  ou double-cliquer sur l'icône 'TPG Display' du bureau"
fi
echo ""
echo "  Raccourcis clavier dans l'afficheur :"
echo "    F11 / F  → plein écran"
echo "    S        → retour au sélecteur d'arrêt"
echo "    Échap    → quitter le plein écran"
echo ""
