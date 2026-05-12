#!/usr/bin/env python3
"""
Afficheur TPG – Tram 15 direction Nations
Grille 128×96 dots.
- Icône tram quand < 1 minute
- Plein écran avec mise à l'échelle (F11/F/Echap)
- Jour, mois, heure mis à jour automatiquement chaque seconde
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

# ─── CONFIG GRILLE ───────────────────────────────────────────────────────────
COLS = 128
ROWS = 96
DOT_NORMAL = 5   # taille LED en mode normal
GAP_NORMAL = 2

# ─── COULEURS ────────────────────────────────────────────────────────────────
BG_SCREEN = "#0b0b06"
BG_FRAME  = "#111111"
LED_ON    = "#ff8c00"
LED_RED   = "#ff2200"

JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MOIS_FR  = ["Janvier","Fevrier","Mars","Avril","Mai","Juin",
            "Juillet","Aout","Septembre","Octobre","Novembre","Decembre"]

# ─── GRILLE STATIQUE (15 + Nations×2, cols 0-59) ─────────────────────────────
STATIC_DATA = {
    2:  [19, 22, 30, 34],
    3:  [19, 22, 30],
    4:  [19, 20, 22, 25, 26, 29, 30, 31, 32, 34, 37, 38, 41, 42, 43, 47, 48, 49],
    5:  [5, 6, 8, 9, 10, 11, 12, 13, 14, 19, 21, 22, 27, 30, 34, 36, 39, 41, 44, 46],
    6:  [4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 19, 22, 25, 26, 27, 30, 34, 36, 39, 41, 44, 47, 48],
    7:  [3, 4, 5, 6, 8, 9, 19, 22, 24, 27, 30, 34, 36, 39, 41, 44, 49],
    8:  [2, 3, 4, 5, 6, 8, 9, 19, 22, 25, 26, 27, 31, 32, 34, 37, 38, 41, 44, 46, 47, 48],
    9:  [1, 2, 3, 5, 6, 8, 9],
    10: [5, 6, 8, 9, 10, 11, 12, 13],
    11: [5, 6, 8, 9, 10, 11, 12, 13, 14],
    12: [5, 6, 13, 14],
    13: [5, 6, 13, 14],
    14: [5, 6, 13, 14, 19, 22, 30, 34],
    15: [5, 6, 8, 9, 13, 14, 19, 22, 30],
    16: [5, 6, 8, 9, 10, 11, 12, 13, 14, 19, 20, 22, 25, 26, 29, 30, 31, 32, 34, 37, 38, 41, 42, 43, 47, 48, 49],
    17: [5, 6, 9, 10, 11, 12, 13, 19, 21, 22, 27, 30, 34, 36, 39, 41, 44, 46],
    18: [19, 22, 25, 26, 27, 30, 34, 36, 39, 41, 44, 47, 48],
    19: [19, 22, 24, 27, 30, 34, 36, 39, 41, 44, 49],
    20: [19, 22, 25, 26, 27, 31, 32, 34, 37, 38, 41, 44, 46, 47, 48],
}
STATIC_GRID = {(c, r) for r, cols in STATIC_DATA.items() for c in cols}

# ─── ICÔNE TRAM (6×7 dots, extraite de l'image Excel) ────────────────────────
TRAM_ICON = [
    [0,0,1,1,1,1,0],  # toit
    [0,1,0,0,0,0,1],  # carrosserie
    [0,1,0,0,0,0,1],  # fenêtres
    [0,1,0,0,0,0,1],  # carrosserie
    [0,1,1,1,1,1,1],  # bas
    [0,1,1,1,1,1,1],  # bas
    [0,1,1,0,0,1,1],  # roues
]
TRAM_W = 7
TRAM_H = 7

# ─── ICÔNE FAUTEUIL ROULANT (5×7 dots, extraite de l'image Excel) ────────────
# Affiché à gauche des minutes quand le véhicule est accessible PMR.
# L'API TPG ne fournit pas ce champ directement → configurable via SHOW_WHEELCHAIR.
# Mettre à False pour masquer, True pour toujours afficher.
WHEELCHAIR_ICON = [
    [1,1,0,0,0,0],  # épaules
    [0,1,0,0,0,0],  # corps
    [0,1,0,0,0,0],  # corps
    [0,1,1,1,0,0],  # bras + siège
    [1,0,0,1,0,0],  # jambe + repose-pied
    [1,0,0,1,1,0],  # jambe + roue
    [0,1,1,0,0,0],  # bas roue
]
WHEELCHAIR_W = 6
WHEELCHAIR_H = 7

# ─── CONFIG ACCESSIBILITÉ ─────────────────────────────────────────────────────
# True  = icône fauteuil toujours affichée (trams TPG tous accessibles)
# False = icône masquée
SHOW_WHEELCHAIR = True

# ─── FONTE PROPORTIONNELLE ────────────────────────────────────────────────────
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
    ':': ([0,0,0,0b1,0,0b1,0], 1),
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


# ─── CANVAS LED ──────────────────────────────────────────────────────────────
class LEDCanvas(tk.Canvas):
    """Canvas dot-matrix LED avec STEP recalculable pour le plein écran."""

    def __init__(self, master, step, **kw):
        self._step = step
        self._dot  = max(1, step - 2)
        super().__init__(master,
                         width=COLS * step,
                         height=ROWS * step,
                         bg=BG_SCREEN,
                         highlightthickness=0, **kw)
        self._build(step)

    def _build(self, step):
        """(Re)construit toute la grille de dots pour un STEP donné."""
        self._step = step
        self._dot  = max(1, step - 2)
        self.delete("all")
        self._items = {}
        r = self._dot // 2
        dot_off = self._make_dot_off()
        for row in range(ROWS):
            for col in range(COLS):
                x = col * step + step // 2
                y = row * step + step // 2
                item = self.create_oval(x-r, y-r, x+r, y+r,
                                        fill=dot_off, outline="")
                self._items[(col, row)] = item
        # Fond statique
        for (col, row) in STATIC_GRID:
            if (col, row) in self._items:
                self.itemconfig(self._items[(col, row)], fill=LED_ON)
        self._dyn = set()

    def _make_dot_off(self):
        """Couleur DOT_OFF légèrement visible."""
        return "#1e1c07"

    def resize(self, step):
        """Redimensionne le canvas et reconstruit la grille."""
        self.config(width=COLS * step, height=ROWS * step)
        self._build(step)

    def clear_dynamic(self):
        for key in self._dyn:
            color = LED_ON if key in STATIC_GRID else self._make_dot_off()
            self.itemconfig(self._items[key], fill=color)
        self._dyn.clear()

    def dyn(self, col, row, color):
        if 0 <= col < COLS and 0 <= row < ROWS:
            key = (col, row)
            self._dyn.add(key)
            self.itemconfig(self._items[key], fill=color)

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

    def draw_tram(self, col_right, row_start, color):
        """Dessine l'icône tram (6×7) alignée à droite."""
        cx = col_right - TRAM_W + 1
        for r, row in enumerate(TRAM_ICON):
            for c, v in enumerate(row):
                if v:
                    self.dyn(cx + c, row_start + r, color)

    def draw_wheelchair(self, col_left, row_start, color):
        """Dessine l'icône fauteuil roulant (5×7) à une position donnée."""
        for r, row in enumerate(WHEELCHAIR_ICON):
            for c, v in enumerate(row):
                if v:
                    self.dyn(col_left + c, row_start + r, color)


# ─── FETCH API ───────────────────────────────────────────────────────────────
def fetch_departures():
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
        self._step = DOT_NORMAL + GAP_NORMAL  # 7

        self._frame = tk.Frame(self, bg=BG_FRAME)
        self._frame.pack(expand=True, fill="both")

        self.cv = LEDCanvas(self._frame, self._step)
        self.cv.pack(expand=True)

        self.bind("<F11>",    lambda e: self._toggle_fs())
        self.bind("<f>",      lambda e: self._toggle_fs())
        self.bind("<F>",      lambda e: self._toggle_fs())
        self.bind("<Escape>", lambda e: self._exit_fs())

        self._deps  = []
        self._error = None
        self._tick()
        self._refresh()

    def _toggle_fs(self):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        self.after(50, self._apply_scale)  # attendre que la fenêtre se redimensionne

    def _exit_fs(self):
        self._fullscreen = False
        self.attributes("-fullscreen", False)
        self.after(50, self._apply_scale)

    def _apply_scale(self):
        """Calcule le STEP optimal pour remplir la fenêtre."""
        if self._fullscreen:
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
        else:
            w = COLS * (DOT_NORMAL + GAP_NORMAL) + 24
            h = ROWS * (DOT_NORMAL + GAP_NORMAL) + 24
            self.geometry(f"{w}x{h}")

        step = min(w // COLS, h // ROWS)
        step = max(2, step)
        if step != self._step:
            self._step = step
            self.cv.resize(step)
            self._draw()  # redessiner immédiatement

    def _tick(self):
        self._draw()
        self.after(1000, self._tick)

    def _refresh(self):
        def worker():
            deps, err = fetch_departures()
            self._deps, self._error = deps, err
        threading.Thread(target=worker, daemon=True).start()
        self.after(REFRESH_S * 1000, self._refresh)

    def _draw_dep(self, dep_idx, row_start):
        """Dessine les minutes ou l'icône tram + fauteuil roulant si accessible."""
        cv = self.cv
        now = datetime.now()
        if dep_idx >= len(self._deps):
            return
        d     = self._deps[dep_idx]
        mins  = int((d["real"] - now).total_seconds() / 60)
        color = LED_RED if d["delay"] > 0 else LED_ON

        # Icône fauteuil roulant à gauche des minutes (col 60)
        if SHOW_WHEELCHAIR:
            cv.draw_wheelchair(99, row_start, color)

        if mins <= 0:
            # Icône tram à droite quand le tram est imminent
            cv.draw_tram(126, row_start, color)
        else:
            cv.draw_text_right(str(mins), 126, row_start, color)

    def _draw(self):
        cv  = self.cv
        now = datetime.now()
        cv.clear_dynamic()

        # ── Minutes / Tram départ 1 (rows 2-8) ───────────────────────────
        self._draw_dep(0, 2)

        # ── Minutes / Tram départ 2 (rows 14-20) ─────────────────────────
        self._draw_dep(1, 14)

        # ── Date (rows 76-82) ─────────────────────────────────────────────
        jour = JOURS_FR[now.weekday()]
        mois = MOIS_FR[now.month - 1]
        cv.draw_text_center(f"{jour} {now.day} {mois}", 63, 76, LED_ON)

        # ── Heure (rows 86-92) ────────────────────────────────────────────
        sep = ":" if now.second % 2 == 0 else "\x00"
        cv.draw_text_center(now.strftime("%H") + sep + now.strftime("%M"),
                            63, 86, LED_ON)


# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = TPGWindow()
    app.mainloop()