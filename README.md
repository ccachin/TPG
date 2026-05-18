# 🚋 Afficheur TPG – Panneau LED dot-matrix

Simulation fidèle d'un panneau d'arrêt TPG (Transports Publics Genevois) en Python, avec données en temps réel, rendu dot-matrix authentique et affichage plein écran adaptatif.

---

## ✨ Fonctionnalités

- **Rendu dot-matrix authentique** — grille de 128×96 LEDs simulées, pixels ronds, espacement adaptatif
- **Données en temps réel** — horaires du tram 15 (ZIPLO → Nations) via l'API [transport.opendata.ch](https://transport.opendata.ch)
- **Retard affiché** — "Retard" s'affiche à la place de la destination en rouge quand le tram est en retard
- **Icône tram** — remplace les minutes quand l'arrivée est imminente (< 1 min), avec clignotement
- **Icône accessibilité PMR** — fauteuil roulant affiché (configurable)
- **Plein écran adaptatif** — remplit exactement la fenêtre quelle que soit la résolution ou le ratio d'écran (16:9, 4:3, carré…)
- **Horloge temps réel** — date et heure mises à jour chaque seconde, deux-points clignotants
- **Mode simulation** — pour tester les différents états (retard, arrivée imminente) sans réseau
- **Optimisé Raspberry Pi** — rendu différentiel (seuls les pixels modifiés sont redessinés)

---

## 📸 États de l'afficheur

| État | Description |
|------|-------------|
| Chiffre orange | Minutes restantes avant l'arrivée |
| Chiffre rouge | Minutes restantes, tram en retard |
| "Retard" rouge | Destination remplacée quand le tram est en retard |
| Icône tram clignotante | Arrivée imminente (< 1 minute) |

---

## 🛠 Installation

### Prérequis

- Python 3.7+
- `tkinter` (inclus dans Python standard sur Windows et macOS ; sur Linux/Raspberry Pi OS : `sudo apt install python3-tk`)
- Connexion internet (pour les données en temps réel)

### Lancement

```bash
git clone https://github.com/votre-utilisateur/tpg-afficheur.git
cd tpg-afficheur
python3 tpg_led.py
```

Aucune dépendance externe — uniquement la bibliothèque standard Python.

---

## ⌨️ Raccourcis clavier

| Touche | Action |
|--------|--------|
| `F11` ou `F` | Basculer plein écran |
| `Échap` | Quitter le plein écran |

---

## ⚙️ Configuration

Toutes les options se trouvent en haut du fichier `tpg_led.py` :

```python
# Station et ligne
STATION   = "Plan-les-Ouates,ZIPLO"   # Nom de la station
LINE      = "15"                        # Numéro de ligne
DIRECTION = "Nations"                   # Destination filtrée
REFRESH_S = 30                          # Intervalle de rafraîchissement API (secondes)

# Accessibilité
SHOW_WHEELCHAIR = True   # Afficher l'icône fauteuil roulant

# Apparence
DOT_RATIO = 0.72   # Taille des LEDs (ratio par rapport à l'espacement)
```

### Mode simulation

Pour tester sans réseau ou simuler un retard :

```python
SIMULATE = True
SIM_DEP1 = {"mins": 0, "delay": 0}   # Tram imminent → icône clignotante
SIM_DEP2 = {"mins": 8, "delay": 3}   # 8 min, retard 3 min → rouge + "Retard"
```

---

## 🔌 API utilisée

[transport.opendata.ch](https://transport.opendata.ch) — API open source des transports publics suisses, gratuite et sans clé d'authentification.

Exemple de requête :
```
https://transport.opendata.ch/v1/stationboard?station=Plan-les-Ouates,ZIPLO&limit=20
```

---

## 🖥 Testé sur

- Windows 11
- Raspberry Pi 400 (Raspberry Pi OS)

---

## 🏗 Architecture technique

```
tpg_led.py
├── STATIC_DATA     — Pixels permanents du "15" (extraits d'une grille Excel pixel par pixel)
├── NATIONS_DEP     — Pixels de la destination (dynamiques pour afficher "Retard")
├── FONT_TPG        — Fonte 4×7 extraite fidèlement des panneaux TPG réels
├── FONT            — Fonte 5×7 pour la date et l'heure
├── LEDCanvas       — Canvas tkinter avec rendu différentiel (diff frame-to-frame)
├── fetch_departures— Appel API avec parsing des données temps réel
└── TPGWindow       — Fenêtre principale, gestion plein écran et boucle de rendu
```

**Rendu différentiel** : à chaque frame, seuls les pixels dont la couleur a changé sont mis à jour via `itemconfig()`, réduisant les appels de ~12 000 à ~50 par frame — essentiel pour la fluidité sur Raspberry Pi.

---

## 📄 Licence

MIT — libre d'utilisation, de modification et de distribution.

---

*Projet personnel inspiré des vrais panneaux d'arrêt TPG de Genève.*
