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
STATION   = "Plan-les-Ouates,ZIPLO"
LINE      = "15"
DIRECTION = "Nations"
LIMIT     = 20
REFRESH_S = 30
API_URL   = ("https://transport.opendata.ch/v1/stationboard"
             f"?station={urllib.parse.quote(STATION)}&limit={LIMIT}")

# ─── SIMULATION (pour tests sans réseau) ────────────────────────────────────
# Mettre SIMULATE = True pour activer les données fictives
# DEP1 et DEP2 : minutes restantes (0 = tram imminent), delay = retard en minutes
SIMULATE = False
SIM_DEP1 = {"mins": 1,  "delay": 0}   # ex: 1 min, à l'heure
SIM_DEP2 = {"mins": 6,  "delay": 3}   # ex: 6 min, 3 min de retard

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
# Pixels permanents : uniquement le "15" (cols 0-18)
# "Nations" est maintenant dynamique pour pouvoir afficher "En retard"
STATIC_DATA = {
    5:  [5, 6, 8, 9, 10, 11, 12, 13, 14],
    6:  [4, 5, 6, 8, 9, 10, 11, 12, 13, 14],
    7:  [3, 4, 5, 6, 8, 9],
    8:  [2, 3, 4, 5, 6, 8, 9],
    9:  [1, 2, 3, 5, 6, 8, 9],
    10: [5, 6, 8, 9, 10, 11, 12, 13],
    11: [5, 6, 8, 9, 10, 11, 12, 13, 14],
    12: [5, 6, 13, 14],
    13: [5, 6, 13, 14],
    14: [5, 6, 13, 14],
    15: [5, 6, 8, 9, 13, 14],
    16: [5, 6, 8, 9, 10, 11, 12, 13, 14],
    17: [5, 6, 9, 10, 11, 12, 13],
}

# Pixels "Nations" pour chaque départ (col 19-59, dynamiques)
NATIONS_DEP = {
    1: {(c,r) for r,cols in {
        2:[19,22,30,34], 3:[19,22,30],
        4:[19,20,22,25,26,29,30,31,32,34,37,38,41,42,43,47,48,49],
        5:[19,21,22,27,30,34,36,39,41,44,46],
        6:[19,22,25,26,27,30,34,36,39,41,44,47,48],
        7:[19,22,24,27,30,34,36,39,41,44,49],
        8:[19,22,25,26,27,31,32,34,37,38,41,44,46,47,48],
    }.items() for c in cols},
    2: {(c,r) for r,cols in {
        14:[19,22,30,34], 15:[19,22,30],
        16:[19,20,22,25,26,29,30,31,32,34,37,38,41,42,43,47,48,49],
        17:[19,21,22,27,30,34,36,39,41,44,46],
        18:[19,22,25,26,27,30,34,36,39,41,44,47,48],
        19:[19,22,24,27,30,34,36,39,41,44,49],
        20:[19,22,25,26,27,31,32,34,37,38,41,44,46,47,48],
    }.items() for c in cols},
}
STATIC_GRID = {(c, r) for r, cols in STATIC_DATA.items() for c in cols}

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
    'N': ([0b1001,0b1001,0b1101,0b1011,0b1001,0b1001,0b1001], 4),
    'a': ([0b0000,0b0000,0b0110,0b0001,0b0111,0b1001,0b0111], 4),
    't': ([0b0100,0b0100,0b1111,0b0100,0b0100,0b0100,0b0011], 4),
    'i': ([0b1,0b0,0b1,0b1,0b1,0b1,0b1], 1),
    'o': ([0b0000,0b0000,0b0110,0b1001,0b1001,0b1001,0b0110], 4),
    'n': ([0b0000,0b0000,0b1110,0b1001,0b1001,0b1001,0b1001], 4),
    's': ([0b0000,0b0000,0b0111,0b1000,0b0110,0b0001,0b1110], 4),
    'R': ([0b1110,0b1001,0b1001,0b1110,0b1010,0b1001,0b1001], 4),
    'e': ([0b0000,0b0000,0b0110,0b1001,0b1111,0b1000,0b0110], 4),
    'r': ([0b0000,0b0000,0b1011,0b1100,0b1000,0b1000,0b1000], 4),
    'd': ([0b0001,0b0001,0b0111,0b1001,0b1001,0b1001,0b0111], 4),
    ' ': ([0b0000]*7, 3),
}

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

    def draw_text_tpg(self, text, cx, cy, color):
        """Dessine avec la fonte TPG 4×7 (même style que Nations)."""
        x = cx
        for ch in text:
            bm, w = FONT_TPG.get(ch, ([0]*7, 4))
            for r, bits in enumerate(bm):
                for c in range(w):
                    if bits & (1 << (w - 1 - c)):
                        self.dyn(x + c, cy + r, color)
            x += w + 1

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
def fetch_departures():
    if SIMULATE:
        now = datetime.now()
        deps = []
        for sim in [SIM_DEP1, SIM_DEP2]:
            real = now + timedelta(minutes=sim["mins"])
            deps.append({"real": real, "delay": sim["delay"],
                         "mins": sim["mins"]})
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
        if entry.get("number") != LINE: continue
        if DIRECTION.lower() not in entry.get("to","").lower(): continue
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
        deps.append({"real": real, "delay": delay, "mins": mins})
    deps.sort(key=lambda x: x["real"])
    return [d for d in deps if d["mins"] >= -1][:2], None


# ─── FENÊTRE ─────────────────────────────────────────────────────────────────
class TPGWindow(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("TPG – ZIPLO")
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

        self._deps      = []
        self._error     = None
        self._blink_phase = 0   # 0,1=allumé 2=éteint (cycle 333ms×3=1s)
        self._tick()
        self._blink_tick()
        self._refresh()

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

    def _draw_dep(self, dep_idx, row_start, blink_on):
        cv  = self.cv
        now = datetime.now()
        if dep_idx >= len(self._deps):
            # Pas de départ : afficher Nations en dim
            for (c, r) in NATIONS_DEP[dep_idx + 1]:
                cv.dyn(c, r, DOT_OFF)
            return
        d     = self._deps[dep_idx]
        mins  = int((d["real"] - now).total_seconds() / 60)
        color = LED_RED if d["delay"] > 0 else LED_ON

        # Destination : même fonte pour "Nations" et "Retard"
        # On efface toujours les pixels CSV de Nations (ils sont dans NATIONS_DEP)
        # et on redessine via draw_text pour garantir une fonte uniforme
        for (c, r) in NATIONS_DEP[dep_idx + 1]:
            cv.dyn(c, r, DOT_OFF)
        if d["delay"] > 0:
            cv.draw_text_tpg("Retard", 19, row_start, LED_RED)
        else:
            cv.draw_text_tpg("Nations", 19, row_start, LED_ON)

        if SHOW_WHEELCHAIR:
            cv.draw_wheelchair(99, row_start, color)
        if mins <= 0:
            if blink_on:
                cv.draw_tram(126, row_start, color)
        else:
            cv.draw_text_right(str(mins), 126, row_start, color)

    def _draw(self):
        cv  = self.cv
        now = datetime.now()
        blink_on = self._blink_phase < 2  # phases 0,1=allumé / phase 2=éteint
        cv.begin_frame()
        self._draw_dep(0, 2, blink_on)
        self._draw_dep(1, 14, blink_on)
        jour = JOURS_FR[now.weekday()]
        mois = MOIS_FR[now.month - 1]
        cv.draw_text_center(f"{jour} {now.day} {mois}", 63, 76, LED_ON)
        # ':' clignote à 4Hz avec le même état que le tram
        sep = ":" if now.second % 2 == 0 else "\x00"
        cv.draw_text_center(now.strftime("%H") + sep + now.strftime("%M"),
                            63, 86, LED_ON)
        cv.commit_frame()


if __name__ == "__main__":
    app = TPGWindow()
    app.mainloop()
