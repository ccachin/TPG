#!/usr/bin/env python3
"""
Afficheur TPG – Tram 15 direction Nations
Grille 128×96 dots.
Plein écran adaptatif : step_x et step_y calculés indépendamment
pour remplir exactement la fenêtre sans bandes noires.
"""

import tkinter as tk
import urllib.request, urllib.parse, json, threading
from datetime import datetime, timedelta

# ─── CONFIG API ──────────────────────────────────────────────────────────────
# Les paramètres peuvent être surchargés par tpg_selector.py via variables d'env
import os as _os
STATION   = _os.environ.get("TPG_STATION",   "Plan-les-Ouates,ZIPLO")
LINE      = _os.environ.get("TPG_LINE",      "")   # vide = toutes les lignes
DIRECTION = _os.environ.get("TPG_DIRECTION", "")   # vide = toutes directions
PLATFORM  = _os.environ.get("TPG_PLATFORM",  "")   # vide = tous quais
LIMIT     = 40
REFRESH_S = 30
API_URL   = ("https://transport.opendata.ch/v1/stationboard"
             f"?station={urllib.parse.quote(STATION)}&limit={LIMIT}")

# ─── SIMULATION (pour tests sans réseau) ────────────────────────────────────
# Mettre SIMULATE = True pour activer les données fictives
# DEP1 et DEP2 : minutes restantes (0 = tram imminent), delay = retard en minutes
SIMULATE = False
SIM_DEPS = [
    {"mins": 17, "delay": 0, "line": "14", "dest": "Bernex-Vailly"},
    {"mins": 35, "delay": 0, "line": "14", "dest": "Bernex-Vailly"},
    {"mins": 29, "delay": 0, "line": "18", "dest": "Palettes"},
    {"mins": 39, "delay": 0, "line": "18", "dest": "Palettes"},
]

# ─── CONFIG GRILLE ───────────────────────────────────────────────────────────
COLS = 128
ROWS = 96
DOT_RATIO = 0.72   # taille du dot = DOT_RATIO × min(step_x, step_y)

# ─── COULEURS ────────────────────────────────────────────────────────────────
BG_SCREEN = "#0b0b06"
BG_FRAME  = "#000000"
LED_ON    = "#ffaa00"
LED_RED   = "#ff4400"
DOT_OFF   = "#2a2608"

JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MOIS_FR  = ["Janvier","Fevrier","Mars","Avril","Mai","Juin",
            "Juillet","Aout","Septembre","Octobre","Novembre","Decembre"]

# ─── GRILLE STATIQUE ─────────────────────────────────────────────────────────
# Plus de statique : numéro de ligne et destination sont 100% dynamiques
STATIC_GRID = set()  # tout est dynamique

# ─── ICÔNES ──────────────────────────────────────────────────────────────────
TRAM_ICON = [
    [0,0,1,1,1,1,0],
    [0,1,0,0,0,0,1],
    [0,1,0,0,0,0,1],
    [0,1,0,0,0,0,1],
    [0,1,1,1,1,1,1],
    [0,1,1,1,1,1,1],
    [0,1,1,0,0,1,1],
]
TRAM_W, TRAM_H = 7, 7

WHEELCHAIR_ICON = [
    [1,1,0,0,0,0],
    [0,1,0,0,0,0],
    [0,1,0,0,0,0],
    [0,1,1,1,0,0],
    [1,0,0,1,0,0],
    [1,0,0,1,1,0],
    [0,1,1,0,0,0],
]
WHEELCHAIR_W, WHEELCHAIR_H = 6, 7
SHOW_WHEELCHAIR = True

# ─── FONTE ───────────────────────────────────────────────────────────────────
FONT = {
    '0': ([0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110], 5),
    '1': ([0b001,0b011,0b101,0b001,0b001,0b001,0b001], 3),
    '2': ([0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111], 5),
    '3': ([0b11110,0b00001,0b00001,0b01110,0b00001,0b00001,0b11110], 5),
    '4': ([0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010], 5),
    '5': ([0b11111,0b10000,0b11110,0b00001,0b00001,0b10001,0b01110], 5),
    '6': ([0b01110,0b10000,0b10000,0b11110,0b10001,0b10001,0b01110], 5),
    '7': ([0b11111,0b00001,0b00001,0b00010,0b00100,0b01000,0b01000], 5),
    '8': ([0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110], 5),
    '9': ([0b01110,0b10001,0b10001,0b01111,0b00001,0b10001,0b01110], 5),
    ':': ([0,0,0,1,0,1,0], 1),
    '\x00':([0]*7, 1),
    ' ': ([0]*7, 4),
    'A': ([0b01110,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001], 5),
    'B': ([0b11110,0b10001,0b10001,0b11110,0b10001,0b10001,0b11110], 5),
    'C': ([0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01111], 5),
    'D': ([0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110], 5),
    'E': ([0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b11111], 5),
    'F': ([0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b10000], 5),
    'G': ([0b01110,0b10001,0b10000,0b10111,0b10001,0b10001,0b01110], 5),
    'H': ([0b10001,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001], 5),
    'I': ([0b111,0b010,0b010,0b010,0b010,0b010,0b111], 3),
    'J': ([0b00001,0b00001,0b00001,0b00001,0b00001,0b10001,0b01110], 5),
    'K': ([0b10001,0b10010,0b10100,0b11000,0b10100,0b10010,0b10001], 5),
    'L': ([0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b11111], 5),
    'M': ([0b10001,0b11011,0b10101,0b10101,0b10001,0b10001,0b10001], 5),
    'N': ([0b10001,0b11001,0b10101,0b10011,0b10001,0b10001,0b10001], 5),
    'O': ([0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110], 5),
    'P': ([0b11110,0b10001,0b10001,0b11110,0b10000,0b10000,0b10000], 5),
    'Q': ([0b01110,0b10001,0b10001,0b10001,0b10101,0b10010,0b01101], 5),
    'R': ([0b11110,0b10001,0b10001,0b11110,0b10100,0b10010,0b10001], 5),
    'S': ([0b01110,0b10001,0b10000,0b01110,0b00001,0b10001,0b01110], 5),
    'T': ([0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100], 5),
    'U': ([0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110], 5),
    'V': ([0b10001,0b10001,0b10001,0b10001,0b10001,0b01010,0b00100], 5),
    'W': ([0b10001,0b10001,0b10001,0b10101,0b10101,0b11011,0b10001], 5),
    'X': ([0b10001,0b10001,0b01010,0b00100,0b01010,0b10001,0b10001], 5),
    'Y': ([0b10001,0b10001,0b01010,0b00100,0b00100,0b00100,0b00100], 5),
    'Z': ([0b11111,0b00001,0b00010,0b00100,0b01000,0b10000,0b11111], 5),
    'a': ([0b00000,0b00000,0b01110,0b00001,0b01111,0b10001,0b01111], 5),
    'b': ([0b10000,0b10000,0b11110,0b10001,0b10001,0b10001,0b11110], 5),
    'c': ([0b00000,0b00000,0b01110,0b10000,0b10000,0b10001,0b01110], 5),
    'd': ([0b00001,0b00001,0b01111,0b10001,0b10001,0b10001,0b01111], 5),
    'e': ([0b00000,0b00000,0b01110,0b10001,0b11111,0b10000,0b01110], 5),
    'f': ([0b00110,0b01001,0b01000,0b11100,0b01000,0b01000,0b01000], 5),
    'g': ([0b00000,0b01111,0b10001,0b10001,0b01111,0b00001,0b01110], 5),
    'h': ([0b10000,0b10000,0b11110,0b10001,0b10001,0b10001,0b10001], 5),
    'i': ([0b1,0b0,0b1,0b1,0b1,0b1,0b1], 1),
    'j': ([0b00010,0b00000,0b00110,0b00010,0b00010,0b10010,0b01100], 5),
    'k': ([0b10000,0b10000,0b10010,0b10100,0b11000,0b10100,0b10010], 5),
    'l': ([0b11000,0b01000,0b01000,0b01000,0b01000,0b01000,0b11111], 5),
    'm': ([0b00000,0b00000,0b10101,0b11111,0b10101,0b10001,0b10001], 5),
    'n': ([0b00000,0b00000,0b11110,0b10001,0b10001,0b10001,0b10001], 5),
    'o': ([0b00000,0b00000,0b01110,0b10001,0b10001,0b10001,0b01110], 5),
    'p': ([0b00000,0b11110,0b10001,0b10001,0b11110,0b10000,0b10000], 5),
    'q': ([0b00000,0b01111,0b10001,0b10001,0b01111,0b00001,0b00001], 5),
    'r': ([0b0000,0b0000,0b1110,0b1001,0b1000,0b1000,0b1000], 4),
    's': ([0b00000,0b00000,0b01110,0b10000,0b01110,0b00001,0b11110], 5),
    't': ([0b00100,0b00100,0b11111,0b00100,0b00100,0b00100,0b00011], 5),
    'u': ([0b00000,0b00000,0b10001,0b10001,0b10001,0b10001,0b01111], 5),
    'v': ([0b00000,0b00000,0b10001,0b10001,0b10001,0b01010,0b00100], 5),
    'w': ([0b00000,0b00000,0b10001,0b10001,0b10101,0b11011,0b10001], 5),
    'x': ([0b00000,0b00000,0b10001,0b01010,0b00100,0b01010,0b10001], 5),
    'y': ([0b00000,0b10001,0b10001,0b01111,0b00001,0b10001,0b01110], 5),
    'z': ([0b00000,0b00000,0b11111,0b00010,0b00100,0b01000,0b11111], 5),
}


# ─── FONTE TPG 4×7 (extraite des pixels CSV, même style que "Nations") ──────────
# Utilisée pour "Nations" et "Retard" afin d'avoir une typo uniforme
FONT_TPG = {
    # ── Majuscules ──────────────────────────────────────────────────────────
    'A': ([0b0110,0b1001,0b1001,0b1111,0b1001,0b1001,0b1001], 4),
    'B': ([0b1110,0b1001,0b1001,0b1110,0b1001,0b1001,0b1110], 4),
    'C': ([0b0111,0b1000,0b1000,0b1000,0b1000,0b1000,0b0111], 4),
    'D': ([0b1110,0b1001,0b1001,0b1001,0b1001,0b1001,0b1110], 4),
    'E': ([0b1111,0b1000,0b1000,0b1110,0b1000,0b1000,0b1111], 4),
    'F': ([0b1111,0b1000,0b1000,0b1110,0b1000,0b1000,0b1000], 4),
    'G': ([0b0111,0b1000,0b1000,0b1011,0b1001,0b1001,0b0111], 4),
    'H': ([0b1001,0b1001,0b1001,0b1111,0b1001,0b1001,0b1001], 4),
    'I': ([0b111,0b010,0b010,0b010,0b010,0b010,0b111], 3),
    'J': ([0b0001,0b0001,0b0001,0b0001,0b0001,0b1001,0b0110], 4),
    'K': ([0b1001,0b1010,0b1100,0b1010,0b1001,0b1001,0b1001], 4),
    'L': ([0b1000,0b1000,0b1000,0b1000,0b1000,0b1000,0b1111], 4),
    'M': ([0b1001,0b1111,0b1111,0b1001,0b1001,0b1001,0b1001], 4),
    'N': ([0b1001,0b1001,0b1101,0b1011,0b1001,0b1001,0b1001], 4),
    'O': ([0b0110,0b1001,0b1001,0b1001,0b1001,0b1001,0b0110], 4),
    'P': ([0b1110,0b1001,0b1001,0b1110,0b1000,0b1000,0b1000], 4),
    'Q': ([0b0110,0b1001,0b1001,0b1001,0b1011,0b0101,0b0011], 4),
    'R': ([0b1110,0b1001,0b1001,0b1110,0b1010,0b1001,0b1001], 4),
    'S': ([0b0111,0b1000,0b1000,0b0110,0b0001,0b0001,0b1110], 4),
    'T': ([0b1111,0b0010,0b0010,0b0010,0b0010,0b0010,0b0010], 4),
    'U': ([0b1001,0b1001,0b1001,0b1001,0b1001,0b1001,0b0110], 4),
    'V': ([0b1001,0b1001,0b1001,0b1001,0b1001,0b0110,0b0110], 4),
    'W': ([0b1001,0b1001,0b1001,0b1111,0b1111,0b1001,0b1001], 4),
    'X': ([0b1001,0b1001,0b0110,0b0110,0b1001,0b1001,0b1001], 4),
    'Y': ([0b1001,0b1001,0b0110,0b0110,0b0010,0b0010,0b0010], 4),
    'Z': ([0b1111,0b0001,0b0010,0b0110,0b1000,0b1000,0b1111], 4),
    # ── Minuscules ──────────────────────────────────────────────────────────
    'a': ([0b0000,0b0000,0b0110,0b0001,0b0111,0b1001,0b0111], 4),
    'b': ([0b1000,0b1000,0b1110,0b1001,0b1001,0b1001,0b1110], 4),
    'c': ([0b0000,0b0000,0b0111,0b1000,0b1000,0b1000,0b0111], 4),
    'd': ([0b0001,0b0001,0b0111,0b1001,0b1001,0b1001,0b0111], 4),
    'e': ([0b0000,0b0000,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'f': ([0b0011,0b0100,0b0100,0b1110,0b0100,0b0100,0b0100], 4),
    'g': ([0b0000,0b0111,0b1001,0b1001,0b0111,0b0001,0b0110], 4),
    'h': ([0b1000,0b1000,0b1110,0b1001,0b1001,0b1001,0b1001], 4),
    'i': ([0b1,0b0,0b1,0b1,0b1,0b1,0b1], 1),
    'j': ([0b0001,0b0000,0b0001,0b0001,0b0001,0b1001,0b0110], 4),
    'k': ([0b1000,0b1001,0b1010,0b1100,0b1010,0b1001,0b1001], 4),
    'l': ([0b1100,0b0100,0b0100,0b0100,0b0100,0b0100,0b1110], 4),
    'm': ([0b0000,0b0000,0b1001,0b1111,0b1111,0b1001,0b1001], 4),
    'n': ([0b0000,0b0000,0b1110,0b1001,0b1001,0b1001,0b1001], 4),
    'o': ([0b0000,0b0000,0b0110,0b1001,0b1001,0b1001,0b0110], 4),
    'p': ([0b0000,0b1110,0b1001,0b1001,0b1110,0b1000,0b1000], 4),
    'q': ([0b0000,0b0111,0b1001,0b1001,0b0111,0b0001,0b0001], 4),
    'r': ([0b0000,0b0000,0b1011,0b1100,0b1000,0b1000,0b1000], 4),
    's': ([0b0000,0b0000,0b0111,0b1000,0b0110,0b0001,0b1110], 4),
    't': ([0b0100,0b0100,0b1111,0b0100,0b0100,0b0100,0b0011], 4),
    'u': ([0b0000,0b0000,0b1001,0b1001,0b1001,0b1001,0b0111], 4),
    'v': ([0b0000,0b0000,0b1001,0b1001,0b1001,0b0110,0b0110], 4),
    'w': ([0b0000,0b0000,0b1001,0b1001,0b1111,0b1111,0b1001], 4),
    'x': ([0b0000,0b0000,0b1001,0b0110,0b0110,0b1001,0b1001], 4),
    'y': ([0b0000,0b1001,0b1001,0b0111,0b0001,0b1001,0b0110], 4),
    'z': ([0b0000,0b0000,0b1111,0b0001,0b0110,0b1000,0b1111], 4),
    # ── Symboles ────────────────────────────────────────────────────────────
    ' ': ([0b0000]*7, 3),
    '-': ([0b0000,0b0000,0b0000,0b1111,0b0000,0b0000,0b0000], 4),
    '.': ([0b0000,0b0000,0b0000,0b0000,0b0000,0b0110,0b0110], 2),
    ',': ([0b0000,0b0000,0b0000,0b0000,0b0110,0b0100,0b1000], 2),
    "'": ([0b0110,0b0100,0b1000,0b0000,0b0000,0b0000,0b0000], 2),
    '?': ([0b0110,0b1001,0b0001,0b0010,0b0100,0b0000,0b0100], 4),
    '!': ([0b0010,0b0010,0b0010,0b0010,0b0000,0b0000,0b0010], 2),
    '/': ([0b0001,0b0001,0b0010,0b0100,0b1000,0b0000,0b0000], 4),
    # ── Accents français ────────────────────────────────────────────────────
    'é': ([0b0010,0b0100,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'è': ([0b0100,0b0010,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'ê': ([0b0110,0b1001,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'ë': ([0b1010,0b0000,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'à': ([0b0100,0b0010,0b0110,0b0001,0b0111,0b1001,0b0111], 4),
    'â': ([0b0110,0b1001,0b0110,0b0001,0b0111,0b1001,0b0111], 4),
    'î': ([0b0110,0b0000,0b0110,0b0010,0b0010,0b0010,0b0110], 3),
    'ï': ([0b0101,0b0000,0b0110,0b0010,0b0010,0b0010,0b0110], 3),
    'ô': ([0b0110,0b1001,0b0110,0b1001,0b1001,0b1001,0b0110], 4),
    'ù': ([0b0100,0b0010,0b1001,0b1001,0b1001,0b1001,0b0111], 4),
    'û': ([0b0110,0b1001,0b0000,0b1001,0b1001,0b1001,0b0111], 4),
    'ü': ([0b1010,0b0000,0b1001,0b1001,0b1001,0b1001,0b0111], 4),
    'ç': ([0b0000,0b0000,0b0111,0b1000,0b1000,0b1000,0b0111], 4),  # c cédille simplifié
    'œ': ([0b0000,0b0000,0b0111,0b1101,0b1110,0b1000,0b0111], 4),
}

# ─── FONTE ÉPAISSE 7×13 (numéros de ligne) ───────────────────────────────────
# Fonte TPG extraite pixel par pixel des grilles CSV de l'utilisateur
# Largeurs variables : '1'=6, '2'/'5'=7, reste=8 — hauteur 13
THICK = {
    '0': [0b01111110,0b11111111,0b11000011,0b11000011,0b11000011,0b11000011,
          0b11000011,0b11000011,0b11000011,0b11000011,0b11000011,0b11111111,0b01111110],
    '1': [0b000011,0b000111,0b001111,0b011111,0b111011,0b000011,0b000011,
          0b000011,0b000011,0b000011,0b000011,0b000011,0b000011],
    '2': [0b0111110,0b1111111,0b1100011,0b0000011,0b0000011,0b0000111,0b0001110,
          0b0011100,0b0111000,0b1110000,0b1100000,0b1111111,0b1111111],
    '3': [0b01111110,0b11111111,0b11000011,0b00000011,0b00000011,0b00111110,
          0b01111111,0b00000011,0b00000011,0b00000011,0b11000011,0b11111111,0b01111110],
    '4': [0b00001110,0b00011110,0b00111110,0b01110110,0b11100110,0b11000110,
          0b11000110,0b11111111,0b11111111,0b00000110,0b00000110,0b00000110,0b00000110],
    '5': [0b1111111,0b1111111,0b1100000,0b1100000,0b1100000,0b1111110,0b1111111,
          0b0000011,0b0000011,0b0000011,0b1100011,0b1111111,0b0111110],
    '6': [0b01111110,0b11111111,0b11000000,0b11000000,0b11000000,0b11111110,
          0b11111111,0b11000011,0b11000011,0b11000011,0b11000011,0b11111111,0b01111110],
    '7': [0b11111111,0b11111111,0b00000111,0b00000111,0b00000111,0b00001111,
          0b00001110,0b00011110,0b00011100,0b00111100,0b00111000,0b00111000,0b00111000],
    '8': [0b01111110,0b11111111,0b11000011,0b11000011,0b11000011,0b01111110,
          0b11111111,0b11000011,0b11000011,0b11000011,0b11000011,0b11111111,0b01111110],
    '9': [0b01111110,0b11111111,0b11000011,0b11000011,0b11000011,0b11111111,
          0b01111111,0b00000011,0b00000011,0b00000011,0b11000011,0b11111111,0b01111110],
}
THICK_WIDTHS = {'0':8,'1':6,'2':7,'3':8,'4':8,'5':7,'6':8,'7':8,'8':8,'9':8}
THICK_W   = 8
THICK_H   = 13
THICK_GAP = 2


# ─── CANVAS LED ──────────────────────────────────────────────────────────────
class LEDCanvas(tk.Canvas):
    """
    Canvas LED dont les step_x et step_y sont indépendants :
    la grille remplit exactement la zone disponible sans bandes noires.
    Les dots restent ronds (diamètre = DOT_RATIO × min(step_x, step_y)).
    """

    def __init__(self, master, w, h, **kw):
        super().__init__(master, width=w, height=h,
                         bg=BG_SCREEN, highlightthickness=0, **kw)
        self._items = {}
        self._dyn   = set()
        self._sx = 1.0
        self._sy = 1.0
        self._dot = 1
        self._build(w, h)

    def _build(self, w, h):
        """Construit ou reconstruit toute la grille pour une taille w×h."""
        self._sx  = w / COLS
        self._sy  = h / ROWS
        self._dot = max(1, int(min(self._sx, self._sy) * DOT_RATIO))
        r = self._dot // 2

        self.delete("all")
        self._items = {}
        self._dyn   = set()

        for row in range(ROWS):
            for col in range(COLS):
                cx = int((col + 0.5) * self._sx)
                cy = int((row + 0.5) * self._sy)
                item = self.create_oval(cx-r, cy-r, cx+r, cy+r,
                                        fill=DOT_OFF, outline="")
                self._items[(col, row)] = item

        for (col, row) in STATIC_GRID:
            if (col, row) in self._items:
                self.itemconfig(self._items[(col, row)], fill=LED_ON)
        self._cur_state = {k: LED_ON for k in STATIC_GRID if k in self._items}
        self._new_state = {}

    def resize(self, w, h):
        self.config(width=w, height=h)
        self._build(w, h)

    def begin_frame(self):
        self._new_state = {}

    def commit_frame(self):
        new = self._new_state
        cur = self._cur_state
        cfg = self.itemconfig
        items = self._items
        for key, color in new.items():
            if cur.get(key) != color:
                cfg(items[key], fill=color)
                cur[key] = color
        for key in list(cur):
            if key not in new:
                color = LED_ON if key in STATIC_GRID else DOT_OFF
                if cur[key] != color:
                    cfg(items[key], fill=color)
                cur[key] = color
        self._new_state = {}

    def clear_dynamic(self): pass

    def dyn(self, col, row, color):
        if 0 <= col < COLS and 0 <= row < ROWS:
            self._new_state[(col, row)] = color

    # ── Fonte ──────────────────────────────────────────────────────────────
    def _tw(self, text):
        total = 0
        for i, ch in enumerate(text):
            _, w = FONT.get(ch, (None, 5))
            total += w + (1 if i < len(text)-1 else 0)
        return total

    def _draw_char(self, ch, cx, cy, color):
        bm, w = FONT.get(ch, ([0]*7, 5))
        for r, bits in enumerate(bm):
            for c in range(w):
                if bits & (1 << (w - 1 - c)):
                    self.dyn(cx + c, cy + r, color)
        return w

    def draw_text(self, text, cx, cy, color):
        x = cx
        for ch in text:
            w = self._draw_char(ch, x, cy, color)
            x += w + 1

    def draw_text_right(self, text, cx_end, cy, color):
        self.draw_text(text, cx_end - self._tw(text) + 1, cy, color)

    def draw_text_center(self, text, cx, cy, color):
        self.draw_text(text, cx - self._tw(text) // 2, cy, color)

    def _tpg_text_width(self, text):
        """Calcule la largeur en dots d'un texte FONT_TPG."""
        w = 0
        for i, ch in enumerate(text):
            if ch not in FONT_TPG:
                continue  # ignorer les chars inconnus dans le calcul
            _, cw = FONT_TPG[ch]
            w += cw + (1 if i < len(text)-1 else 0)
        return w

    def fit_text_tpg(self, text, max_cols):
        """Tronque le texte pour qu'il tienne dans max_cols dots."""
        if self._tpg_text_width(text) <= max_cols:
            return text
        # Tronquer progressivement et ajouter "."
        for n in range(len(text)-1, 0, -1):
            candidate = text[:n] + "."
            if self._tpg_text_width(candidate) <= max_cols:
                return candidate
        return ""

    def draw_text_tpg(self, text, cx, cy, color):
        """Dessine avec la fonte TPG 4×7 (même style que Nations)."""
        x = cx
        for ch in text:
            if ch not in FONT_TPG:
                continue  # ignorer les chars inconnus silencieusement
            bm, w = FONT_TPG[ch]
            for r, bits in enumerate(bm):
                for c in range(w):
                    if bits & (1 << (w - 1 - c)):
                        self.dyn(x + c, cy + r, color)
            x += w + 1

    def draw_text_big(self, text, cx, cy, color):
        """Dessine avec la fonte FONT en scale=2 (numéro de ligne)."""
        x = cx
        for ch in text:
            bm, w = FONT.get(ch, ([0]*7, 5))
            for r, bits in enumerate(bm):
                for c in range(w):
                    if bits & (1 << (w - 1 - c)):
                        for sr in range(2):
                            for sc in range(2):
                                self.dyn(x + c*2 + sc, cy + r*2 + sr, color)
            x += w*2 + 2

    def draw_thick(self, text, cx, cy, color):
        """Dessine avec la fonte épaisse THICK (numéros de ligne TPG)."""
        x = cx
        for ch in text:
            bm = THICK.get(ch)
            if not bm:
                continue
            w = THICK_WIDTHS.get(ch, THICK_W)
            for r, bits in enumerate(bm):
                for c in range(w):
                    if bits & (1 << (w - 1 - c)):
                        self.dyn(x + c, cy + r, color)
            x += w + THICK_GAP

    def thick_text_width(self, text):
        if not text: return 0
        return sum(THICK_WIDTHS.get(ch, THICK_W) + THICK_GAP for ch in text) - THICK_GAP

    def draw_tram(self, col_right, row_start, color):
        cx = col_right - TRAM_W + 1
        for r, row in enumerate(TRAM_ICON):
            for c, v in enumerate(row):
                if v: self.dyn(cx + c, row_start + r, color)

    def draw_wheelchair(self, col_left, row_start, color):
        for r, row in enumerate(WHEELCHAIR_ICON):
            for c, v in enumerate(row):
                if v: self.dyn(col_left + c, row_start + r, color)


# ─── FETCH API ───────────────────────────────────────────────────────────────
DEBUG = False   # Mettre True pour voir les données brutes dans la console

def fetch_departures():
    if SIMULATE:
        now = datetime.now()
        deps = []
        for sim in SIM_DEPS:
            real = now + timedelta(minutes=sim["mins"])
            deps.append({"real": real, "delay": sim["delay"],
                         "mins": sim["mins"],
                         "line": sim["line"],
                         "dest": sim["dest"]})
        return deps, None
    try:
        req = urllib.request.Request(
            API_URL, headers={"User-Agent": "Mozilla/5.0 (TPG-Display/1.0)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [], str(e)
    deps = []
    for entry in data.get("stationboard", []):
        # Filtrer par ligne/direction seulement si défini
        if LINE and entry.get("number") != LINE: continue
        if PLATFORM:
            entry_platform = entry["stop"].get("platform") or ""
            if entry_platform != PLATFORM:
                continue
        if DIRECTION:
            dest_api = entry.get("to","").lower()
            dirs = [d.strip().lower() for d in DIRECTION.split("|") if d.strip()]
            if not any(d in dest_api for d in dirs):
                continue
        stop     = entry["stop"]
        dep_ts   = stop.get("departureTimestamp")
        prog_dep = stop.get("prognosis", {}).get("departure")
        delay    = stop.get("delay") or 0
        if dep_ts is None: continue
        planned = datetime.fromtimestamp(dep_ts)
        if prog_dep:
            if len(prog_dep) >= 5 and prog_dep[-5] in ('+','-') and ':' not in prog_dep[-5:]:
                prog_dep = prog_dep[:-2] + ':' + prog_dep[-2:]
            real = datetime.fromisoformat(prog_dep).replace(tzinfo=None)
        else:
            real = planned + timedelta(minutes=delay)
        mins = int((real - datetime.now()).total_seconds() / 60)
        dest = entry.get("to", "")
        dest = dest.replace("Genève, ","").replace("Gen\u00e8ve, ","")
        dest = dest.replace("&", "-")
        # Nettoyer espaces insécables et autres caractères spéciaux
        dest = dest.replace("\xa0", " ").replace("\u202f", " ")
        # Supprimer le préfixe "Genève," ou "Geneve," restant
        dest = dest.replace("Gen\u00e8ve,","").replace("Geneve,","").strip()
        # Retard réel = différence entre heure pronostiquée et heure planifiée
        real_delay = int((real - planned).total_seconds() / 60)
        if DEBUG:
            print(f"  L{entry.get('number')} → {dest[:20]:<20} | planned={planned.strftime('%H:%M')} real={real.strftime('%H:%M')} delay_api={delay!r:>5} delay_calc={real_delay:+d}min")
        deps.append({
            "real":     real,
            "planned":  planned,
            "delay":    real_delay,
            "mins":     mins,
            "line":     entry.get("number", "?"),
            "dest":     dest,
        })
    deps.sort(key=lambda x: x["real"])
    return [d for d in deps if d["mins"] >= -1][:8], None


# ─── FENÊTRE ─────────────────────────────────────────────────────────────────
class TPGWindow(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"TPG – {STATION} | Ligne {LINE} → {DIRECTION}")
        self.configure(bg=BG_FRAME)
        self.resizable(True, True)
        self._fullscreen = False
        self._resize_job = None

        # Taille initiale : grille carrée avec step=7
        iw = COLS * 7
        ih = ROWS * 7
        self.geometry(f"{iw}x{ih}")

        self.cv = LEDCanvas(self, iw, ih)
        self.cv.place(x=0, y=0)   # plaqué en haut-gauche, redimensionné dynamiquement

        self.bind("<F11>",       lambda e: self._toggle_fs())
        self.bind("<f>",         lambda e: self._toggle_fs())
        self.bind("<F>",         lambda e: self._toggle_fs())
        self.bind("<Escape>",    lambda e: self._exit_fs())
        self.bind("<Configure>", lambda e: self._on_resize(e))
        self.bind("<s>",         lambda e: self._open_selector())
        self.bind("<S>",         lambda e: self._open_selector())

        self._deps      = []
        self._error     = None
        self._blink_phase = 0   # 0,1=allumé 2=éteint (cycle 333ms×3=1s)
        self._tick()
        self._blink_tick()
        self._refresh()

    def _open_selector(self):
        """Relance le sélecteur d'arrêt (touche S)."""
        import subprocess, sys, os
        # Chercher tpg_selector.py dans le même dossier que ce script
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            here = os.getcwd()
        script = os.path.join(here, "tpg_selector.py")
        if not os.path.exists(script):
            # Fallback : même dossier que le CWD
            script = os.path.join(os.getcwd(), "tpg_selector.py")
        if not os.path.exists(script):
            return  # introuvable, on ne fait rien
        # Lancer dans un nouveau processus indépendant
        subprocess.Popen(
            [sys.executable, script],
            cwd=os.path.dirname(script),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0
        )
        self.after(200, self.destroy)

    def _toggle_fs(self):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)

    def _exit_fs(self):
        self._fullscreen = False
        self.attributes("-fullscreen", False)

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._apply_scale)

    def _apply_scale(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return
        # Le canvas prend toute la fenêtre — step_x et step_y indépendants
        self.cv.place(x=0, y=0, width=w, height=h)
        self.cv.resize(w, h)
        self._draw()

    def _tick(self):
        self._draw()
        self.after(1000, self._tick)

    def _blink_tick(self):
        """Clignotement tram : allumé 2/3 du temps, éteint 1/3."""
        self._blink_phase = (self._blink_phase + 1) % 3
        self._draw()
        self.after(333, self._blink_tick)

    def _refresh(self):
        def worker():
            deps, err = fetch_departures()
            self._deps, self._error = deps, err
        threading.Thread(target=worker, daemon=True).start()
        self.after(REFRESH_S * 1000, self._refresh)

    def _draw_line_group(self, line_num, deps, row_start, blink_on):
        """
        Dessine un groupe de 1 ou 2 départs pour la même ligne.
        Proportions calquées sur le vrai panneau TPG :
        - 1 destination = 14 rows (7px fonte + 7px marge)
        - gap entre 2 destinations de la même ligne = 2 rows
        - numéro centré verticalement sur la hauteur totale du groupe
        """
        cv  = self.cv
        now = datetime.now()

        ROW_H     = 9    # hauteur d'une destination (fonte 7px + marge 2px)
        INTRA_GAP = 0    # pas de gap entre 2 destinations de la même ligne

        NUM_COL_RIGHT = 17   # numéro aligné à droite ici
        DEST_COL      = 20   # destination
        WHEEL_COL     = 107  # fauteuil roulant
        MIN_COL_RIGHT = 126  # minutes

        n = len(deps)

        # Hauteur totale du groupe
        total_h = n * ROW_H + (n - 1) * INTRA_GAP

        # Numéro centré verticalement, justifié à droite
        thick_row = row_start + (total_h - THICK_H) // 2
        num_w     = cv.thick_text_width(line_num)
        num_col   = NUM_COL_RIGHT - num_w + 1
        cv.draw_thick(line_num, num_col, thick_row, LED_ON)

        # Espace dispo pour destination
        dest_max_cols = WHEEL_COL - DEST_COL - 2

        for i, d in enumerate(deps):
            dest_row = row_start + i * (ROW_H + INTRA_GAP)
            mins     = int((d["real"] - now).total_seconds() / 60)

            dest = cv.fit_text_tpg(d["dest"], dest_max_cols)
            cv.draw_text_tpg(dest, DEST_COL, dest_row, LED_ON)

            if SHOW_WHEELCHAIR:
                cv.draw_wheelchair(WHEEL_COL, dest_row, LED_ON)

            if mins <= 0:
                if blink_on:
                    cv.draw_tram(MIN_COL_RIGHT, dest_row, LED_ON)
            else:
                cv.draw_text_right(str(mins), MIN_COL_RIGHT, dest_row, LED_ON)

    def _draw(self):
        cv  = self.cv
        now = datetime.now()
        blink_on = self._blink_phase < 2
        cv.begin_frame()

        # Grouper les départs par ligne (max 2 par ligne)
        from collections import OrderedDict
        groups = OrderedDict()
        for d in self._deps:
            line = d["line"]
            if line not in groups:
                groups[line] = []
            if len(groups[line]) < 2:
                groups[line].append(d)

        # Layout : ROW_H=9, INTRA_GAP=0, INTER_GAP=5
        ROW_H      = 9
        INTRA_GAP  = 0
        INTER_GAP  = 4
        row        = 2

        for line_num, deps in groups.items():
            # Vérifier qu'on a encore de la place avant la date (row 72)
            n = len(deps)
            group_h = n * ROW_H + (n - 1) * INTRA_GAP
            if row + group_h > 72:
                break
            self._draw_line_group(line_num, deps, row, blink_on)
            row += group_h + INTER_GAP

        # Date et heure
        jour = JOURS_FR[now.weekday()]
        mois = MOIS_FR[now.month - 1]
        cv.draw_text_center(f"{jour} {now.day} {mois}", 63, 76, LED_ON)
        sep = ":" if now.second % 2 == 0 else "\x00"
        cv.draw_text_center(now.strftime("%H") + sep + now.strftime("%M"),
                            63, 86, LED_ON)
        cv.commit_frame()


if __name__ == "__main__":
    app = TPGWindow()
    app.mainloop()