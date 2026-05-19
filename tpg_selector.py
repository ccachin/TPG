#!/usr/bin/env python3
"""
TPG Sélecteur d'arrêt
Carte OSM dessinée directement sur tk.Canvas (pas de dépendance externe)
+ Recherche par nom
"""

import tkinter as tk
from tkinter import ttk
import urllib.request, urllib.parse, json, threading, math, io, os, sys, subprocess
from datetime import datetime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ─── CONFIG ──────────────────────────────────────────────────────────────────
GENEVE_LAT  = 46.2044
GENEVE_LON  = 6.1432
INIT_ZOOM   = 14
API_BASE    = "https://transport.opendata.ch/v1"
TILE_SIZE   = 256

# ─── MATHS TUILES OSM ────────────────────────────────────────────────────────
def lat_lon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) +
             1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y

def tile_to_lat_lon(x, y, zoom):
    n  = 2 ** zoom
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon

def lat_lon_to_pixel(lat, lon, zoom, tile_x0, tile_y0):
    """Pixel dans la vue (tuile tile_x0,tile_y0 en haut-gauche)."""
    n  = 2 ** zoom
    px = (lon + 180) / 360 * n * TILE_SIZE - tile_x0 * TILE_SIZE
    py = (1 - math.log(math.tan(math.radians(lat)) +
          1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * TILE_SIZE - tile_y0 * TILE_SIZE
    return px, py

# ─── API ─────────────────────────────────────────────────────────────────────
def fetch_stops(lat, lon, limit=60):
    """Récupère les arrêts en faisant 5 requêtes (centre + 4 directions)
    pour couvrir une zone plus grande."""
    DELTA = 0.012  # ~1.2km de décalage par direction
    centers = [
        (lat,       lon),        # centre
        (lat+DELTA, lon),        # nord
        (lat-DELTA, lon),        # sud
        (lat,       lon+DELTA),  # est
        (lat,       lon-DELTA),  # ouest
    ]
    seen  = set()
    stops = []
    for clat, clon in centers:
        url = f"{API_BASE}/locations?x={clat:.4f}&y={clon:.4f}&type=station&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            for s in data.get("stations", []):
                name = s.get("name","")
                if name and name not in seen and s.get("coordinate",{}).get("x"):
                    seen.add(name)
                    stops.append({
                        "name": name,
                        "id":   s.get("id",""),
                        "lat":  s["coordinate"]["x"],
                        "lon":  s["coordinate"]["y"],
                    })
        except Exception:
            continue
    return stops

def search_stops(query, limit=10):
    if len(query) < 2:
        return []
    url = f"{API_BASE}/locations?query={urllib.parse.quote(query)}&type=station&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        return [{"name": s["name"], "id": s.get("id", ""),
                 "lat": s["coordinate"]["x"], "lon": s["coordinate"]["y"]}
                for s in data.get("stations", [])
                if s.get("coordinate", {}).get("x")]
    except Exception:
        return []

# ─── CARTE ───────────────────────────────────────────────────────────────────
class MapCanvas(tk.Canvas):
    """Carte OSM optimisée : déplacement fluide par move() sans recréer les items."""

    OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    def __init__(self, master, on_stop_click, **kw):
        super().__init__(master, bg="#2a2a2a",
                         highlightthickness=0, cursor="fleur", **kw)
        self._on_stop_click = on_stop_click
        self._zoom   = INIT_ZOOM
        self._lat    = GENEVE_LAT
        self._lon    = GENEVE_LON

        # Cache tuiles : (z,x,y) → ImageTk
        self._tiles       = {}
        self._tile_items  = {}  # (z,x,y) → canvas item id
        self._fetching    = set()

        self._stops       = []
        self._stop_items     = []
        self._platform_items     = []
        self._platform_stops     = []
        self._platform_screen_pos = []
        self._platform_callback   = None  # canvas item ids des marqueurs

        # Drag
        self._drag_x = None
        self._drag_y = None
        self._drag_lat = GENEVE_LAT
        self._drag_lon = GENEVE_LON

        # Throttle redraw
        self._render_job = None

        self.bind("<Configure>",       self._on_configure)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>",      self._on_wheel)
        self.bind("<Button-4>",        lambda e: self._change_zoom(1))
        self.bind("<Button-5>",        lambda e: self._change_zoom(-1))

    # ── Géométrie ────────────────────────────────────────────────────────────
    def _lat_lon_to_screen(self, lat, lon):
        """Coordonnées écran pour un lat/lon donné."""
        w, h = self.winfo_width(), self.winfo_height()
        n    = 2 ** self._zoom
        # Position pixel absolue dans le monde tuile
        px_world = (lon + 180) / 360 * n * TILE_SIZE
        py_world = (1 - math.log(math.tan(math.radians(lat)) +
                    1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * TILE_SIZE
        # Centre du monde
        cx_world = (self._lon + 180) / 360 * n * TILE_SIZE
        cy_world = (1 - math.log(math.tan(math.radians(self._lat)) +
                    1 / math.cos(math.radians(self._lat))) / math.pi) / 2 * n * TILE_SIZE
        sx = px_world - cx_world + w / 2
        sy = py_world - cy_world + h / 2
        return sx, sy

    def _screen_to_lat_lon(self, sx, sy):
        w, h = self.winfo_width(), self.winfo_height()
        n = 2 ** self._zoom
        cx_world = (self._lon + 180) / 360 * n * TILE_SIZE
        cy_world = (1 - math.log(math.tan(math.radians(self._lat)) +
                    1 / math.cos(math.radians(self._lat))) / math.pi) / 2 * n * TILE_SIZE
        px_world = sx - w / 2 + cx_world
        py_world = sy - h / 2 + cy_world
        lon = px_world / (n * TILE_SIZE) * 360 - 180
        lat = math.degrees(math.atan(math.sinh(
              math.pi * (1 - 2 * py_world / (n * TILE_SIZE)))))
        return lat, lon

    # ── Événements ───────────────────────────────────────────────────────────
    def _on_configure(self, e):
        self._full_render()
        self.after(100, lambda: threading.Thread(
            target=self._load_stops_bg, daemon=True).start())

    def _on_press(self, e):
        # 1. Priorité : clic sur un point de quai (distance euclidienne)
        for sx, sy, R, idx in getattr(self, "_platform_screen_pos", []):
            dist = ((e.x - sx)**2 + (e.y - sy)**2) ** 0.5
            if dist <= R + 6:  # tolérance +6px
                pstops = getattr(self, "_platform_stops", [])
                cb     = getattr(self, "_platform_callback", None)
                if cb and idx < len(pstops):
                    s = pstops[idx]
                    cb(s["name"], s["platform"])
                    self._clear_platform_items()
                return

        # 2. Clic sur un arrêt normal
        radius = max(12, 24 - self._zoom)
        items = self.find_overlapping(e.x-radius, e.y-radius, e.x+radius, e.y+radius)
        for item in items:
            for tag in self.gettags(item):
                if tag.startswith("stop:"):
                    idx = int(tag.split(":")[1])
                    if idx < len(self._stops):
                        self._on_stop_click(self._stops[idx])
                    return

        # 3. Sinon drag
        self._drag_x = e.x
        self._drag_y = e.y
        self._drag_lat = self._lat
        self._drag_lon = self._lon

    def _on_drag(self, e):
        if self._drag_x is None:
            return
        dx = e.x - self._drag_x
        dy = e.y - self._drag_y
        # Convertir le delta pixel en delta lat/lon
        # 1 tuile = TILE_SIZE pixels = 360/2^zoom degrés longitude (à l'équateur)
        n   = 2 ** self._zoom
        # Delta longitude : linéaire
        d_lon = -dx / TILE_SIZE / n * 360
        # Delta latitude : via mercator inverse
        cy_world = (1 - math.log(math.tan(math.radians(self._drag_lat)) +
                    1 / math.cos(math.radians(self._drag_lat))) / math.pi) / 2 * n
        new_cy   = cy_world - dy / TILE_SIZE
        new_lat  = math.degrees(math.atan(
                   math.sinh(math.pi * (1 - 2 * new_cy / n))))
        self._lat = new_lat
        self._lon = self._drag_lon + d_lon
        self._drag_x = e.x
        self._drag_y = e.y
        self._drag_lat = self._lat
        self._drag_lon = self._lon
        # Déplacer tous les items visuellement
        self.move("all", dx, dy)
        # Recharger les tuiles manquantes après un court délai
        if self._render_job:
            self.after_cancel(self._render_job)
        self._render_job = self.after(150, self._full_render)

    def _on_release(self, e):
        self._drag_x = None
        self._full_render()
        threading.Thread(target=self._load_stops_bg, daemon=True).start()

    def _on_wheel(self, e):
        self._change_zoom(1 if e.delta > 0 else -1)

    def _change_zoom(self, delta):
        new_zoom = max(10, min(18, self._zoom + delta))
        if new_zoom == self._zoom:
            return
        self._zoom = new_zoom
        self._tiles.clear()
        self._fetching.clear()
        self._full_render()
        threading.Thread(target=self._load_stops_bg, daemon=True).start()

    def center_on(self, lat, lon):
        self._lat, self._lon = lat, lon
        self._full_render()
        threading.Thread(target=self._load_stops_bg, daemon=True).start()

    # ── Rendu ────────────────────────────────────────────────────────────────
    def _full_render(self):
        """Reconstruction complète (au zoom ou resize). Repositionne tout."""
        if not HAS_PIL:
            self.delete("all")
            self.create_text(self.winfo_width()//2, self.winfo_height()//2,
                text="Installez Pillow:\npip install Pillow",
                fill="#ff8c00", font=("Arial", 14), justify="center")
            return

        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return

        self.delete("all")
        self._tile_items = {}
        self._stop_items = []
        self._offset_x = 0
        self._offset_y = 0

        self._fill_tiles()
        self._draw_stops()
        self._draw_controls()

    def _fill_tiles(self):
        """Ajoute/met à jour les tuiles visibles sans tout supprimer."""
        if not HAS_PIL:
            return
        w, h = self.winfo_width(), self.winfo_height()
        n    = 2 ** self._zoom

        # Tuile du centre
        cx_world = (self._lon + 180) / 360 * n
        cy_world = (1 - math.log(math.tan(math.radians(self._lat)) +
                    1 / math.cos(math.radians(self._lat))) / math.pi) / 2 * n

        # Plage de tuiles à afficher
        tx0 = int(cx_world) - w // (2 * TILE_SIZE) - 1
        ty0 = int(cy_world) - h // (2 * TILE_SIZE) - 1
        tx1 = tx0 + w // TILE_SIZE + 3
        ty1 = ty0 + h // TILE_SIZE + 3

        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                key = (self._zoom, tx % n, ty)
                # Position écran de la tuile
                sx = (tx - cx_world) * TILE_SIZE + w / 2
                sy = (ty - cy_world) * TILE_SIZE + h / 2

                if key in self._tile_items:
                    # Repositionner l'item existant
                    self.coords(self._tile_items[key], int(sx), int(sy))
                elif key in self._tiles:
                    # Créer l'item depuis le cache
                    item = self.create_image(int(sx), int(sy),
                                             image=self._tiles[key],
                                             anchor="nw", tags="tile")
                    self._tile_items[key] = item
                    self.tag_lower("tile")
                else:
                    # Placeholder + téléchargement
                    self.create_rectangle(int(sx), int(sy),
                        int(sx)+TILE_SIZE, int(sy)+TILE_SIZE,
                        fill="#333", outline="#444", tags="tile")
                    self.tag_lower("tile")
                    if key not in self._fetching:
                        self._fetching.add(key)
                        threading.Thread(
                            target=self._fetch_tile,
                            args=(tx % n, ty, self._zoom),
                            daemon=True).start()

    def _fetch_tile(self, tx, ty, zoom):
        key = (zoom, tx, ty)
        url = self.OSM.format(z=zoom, x=tx, y=ty)
        try:
            req = urllib.request.Request(url,
                  headers={"User-Agent": "Mozilla/5.0 (TPG-Display/1.0)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            img   = Image.open(io.BytesIO(data)).convert("RGB")
            photo = ImageTk.PhotoImage(img)
            self._tiles[key] = photo
            self._fetching.discard(key)
            # Redessiner depuis le thread principal
            self.after(0, self._full_render)
        except Exception:
            self._fetching.discard(key)

    def add_platform_stops(self, platform_stops, callback):
        """Affiche les 2 côtés de l'arrêt comme points cliquables."""
        self._clear_platform_items()
        self._platform_stops    = platform_stops
        self._platform_callback = callback
        # Stocker les positions écran pour la détection dans _on_press
        self._platform_screen_pos = []

        R = 16  # rayon des points de quai
        for i, s in enumerate(platform_stops):
            sx, sy = self._lat_lon_to_screen(s["lat"], s["lon"])
            sx, sy = int(sx), int(sy)
            color  = s.get("color", "#ff8c00")
            label  = s.get("label", "")[:35]

            ids = []
            ids.append(self.create_oval(sx-R, sy-R, sx+R, sy+R,
                fill=color, outline="#fff", width=3, tags="pstop"))
            ids.append(self.create_text(sx, sy,
                text=str(i+1), fill="#000",
                font=("Arial", 12, "bold"), tags="pstop"))
            ids.append(self.create_text(sx, sy + R + 10,
                text=label, fill=color,
                font=("Arial", 8, "bold"), tags="pstop"))
            self._platform_items.extend(ids)
            # Position écran pour détection de clic
            self._platform_screen_pos.append((sx, sy, R, i))

        self.tag_raise("pstop")

    def _clear_platform_items(self):
        for item in getattr(self, "_platform_items", []):
            try:
                self.delete(item)
            except Exception:
                pass
        self._platform_items     = []
        self._platform_screen_pos = []

    def _draw_stops(self):
        # Supprimer anciens marqueurs normaux
        for item in self._stop_items:
            self.delete(item)
        self._stop_items = []
        for i, s in enumerate(self._stops):
            sx, sy = self._lat_lon_to_screen(s["lat"], s["lon"])
            w, h = self.winfo_width(), self.winfo_height()
            if -20 < sx < w+20 and -20 < sy < h+20:
                tag = f"stop:{i}"
                a = self.create_oval(sx-9, sy-9, sx+9, sy+9,
                    fill="#ff8c00", outline="#fff", width=2,
                    tags=("stop", tag))
                self._stop_items.append(a)

    def _draw_controls(self):
        w, h = self.winfo_width(), self.winfo_height()
        for item in self.find_withtag("control"):
            self.delete(item)
        self.create_rectangle(10, 10, 36, 36,
            fill="#222", outline="#555", tags="control")
        self.create_text(23, 23, text="+", fill="#ff8c00",
            font=("Arial", 14, "bold"), tags=("control","zoom_in"))
        self.create_rectangle(10, 40, 36, 66,
            fill="#222", outline="#555", tags="control")
        self.create_text(23, 53, text="−", fill="#ff8c00",
            font=("Arial", 14, "bold"), tags=("control","zoom_out"))
        self.tag_bind("zoom_in",  "<Button-1>", lambda e: self._change_zoom(1))
        self.tag_bind("zoom_out", "<Button-1>", lambda e: self._change_zoom(-1))
        self.create_text(w-6, h-6, text=f"z{self._zoom}",
            fill="#888", font=("Arial", 8), anchor="se", tags="control")
        self.tag_raise("control")
        self.tag_raise("stop")

    def _load_stops_bg(self):
        stops = fetch_stops(self._lat, self._lon)
        self.after(0, lambda s=stops: self._set_stops(s))

    def _set_stops(self, stops):
        self._stops = stops
        self._draw_stops()
        self._draw_controls()


# ─── FENÊTRE PRINCIPALE ───────────────────────────────────────────────────────
class TPGSelector(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("TPG – Sélection de l'arrêt")
        self.configure(bg="#111")
        self.geometry("900x650")
        self.minsize(600, 400)
        self._stop_name = None
        self._current_platform = None
        self._build()

    def _build(self):
        # ── Barre du haut ────────────────────────────────────────────────────
        top = tk.Frame(self, bg="#1a1a1a", pady=8, padx=12)
        top.pack(fill="x")

        tk.Label(top, text="🚋 TPG", font=("Arial", 14, "bold"),
                 fg="#ff8c00", bg="#1a1a1a").pack(side="left")

        self._stop_lbl = tk.Label(top,
                 text="Cliquez sur un arrêt ou recherchez par nom",
                 fg="#555", bg="#1a1a1a", font=("Arial", 11))
        self._stop_lbl.pack(side="left", padx=16)

        self._btn = tk.Button(top,
                 text="▶  Lancer l'afficheur",
                 bg="#333", fg="#555", font=("Arial", 11, "bold"),
                 relief="flat", padx=14, pady=5,
                 state="disabled", command=self._launch)
        self._btn.pack(side="right")

        # ── Onglets ──────────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",     background="#111", borderwidth=0)
        style.configure("TNotebook.Tab", background="#222", foreground="#aaa",
                         font=("Arial", 10), padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", "#ff8c00")],
                  foreground=[("selected", "#000")])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # ── Onglet Carte ─────────────────────────────────────────────────────
        tab_map = tk.Frame(nb, bg="#111")
        nb.add(tab_map, text="  🗺  Carte  ")

        if HAS_PIL:
            self._map = MapCanvas(tab_map, self._on_stop_click)
            self._map.pack(fill="both", expand=True)
            # Charger les arrêts initiaux
            self.after(300, lambda: threading.Thread(
                target=lambda: self._map._load_stops_bg(),
                daemon=True).start())
        else:
            tk.Label(tab_map,
                text="Pillow requis pour la carte\npip install Pillow",
                fg="#ff8c00", bg="#111", font=("Arial", 13),
                justify="center").pack(expand=True)

        # ── Onglet Recherche ─────────────────────────────────────────────────
        tab_search = tk.Frame(nb, bg="#111")
        nb.add(tab_search, text="  🔍  Recherche  ")
        self._build_search(tab_search)

    def _build_search(self, parent):
        row = tk.Frame(parent, bg="#111", pady=14, padx=16)
        row.pack(fill="x")

        tk.Label(row, text="Rechercher :",
                 fg="#aaa", bg="#111", font=("Arial", 11)).pack(side="left")

        self._sv = tk.StringVar()
        self._sv.trace("w", self._on_search)
        e = tk.Entry(row, textvariable=self._sv,
                     bg="#222", fg="#ff8c00",
                     insertbackground="#ff8c00",
                     font=("Arial", 13), width=28, relief="flat",
                     highlightthickness=1, highlightcolor="#ff8c00")
        e.pack(side="left", padx=10, ipady=5)
        e.focus()

        self._lb = tk.Listbox(parent,
                bg="#1a1a1a", fg="#ccc",
                selectbackground="#ff8c00", selectforeground="#000",
                font=("Arial", 12), relief="flat",
                highlightthickness=0, activestyle="none", cursor="hand2")
        self._lb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._lb.bind("<ButtonRelease-1>", self._on_list_select)
        self._lb.bind("<Double-Button-1>", self._on_list_double)

        self._results = []
        self._search_job = None

    def _on_search(self, *_):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self._do_search)

    def _do_search(self):
        q = self._sv.get().strip()
        if len(q) < 2:
            self._lb.delete(0, "end")
            self._results = []
            return
        threading.Thread(target=self._fetch_search, args=(q,), daemon=True).start()

    def _fetch_search(self, q):
        r = search_stops(q)
        self.after(0, lambda: self._show(r))

    def _show(self, results):
        self._results = results
        self._lb.delete(0, "end")
        for s in results:
            self._lb.insert("end", f"  {s['name']}")

    def _on_list_select(self, _):
        sel = self._lb.curselection()
        if sel:
            self._on_stop_click(self._results[sel[0]])

    def _on_list_double(self, _):
        sel = self._lb.curselection()
        if sel:
            s = self._results[sel[0]]
            self._on_stop_click(s)
            if HAS_PIL and s.get("lat"):
                self._map.center_on(s["lat"], s["lon"])

    # ── Sélection / Lancement ────────────────────────────────────────────────
    def _on_stop_click(self, stop):
        self._stop_name = stop["name"]
        self._stop_lat  = stop.get("lat")
        self._stop_lon  = stop.get("lon")
        self._stop_lbl.config(text=f"Chargement des quais...", fg="#aaa")
        self._btn.config(state="disabled", bg="#333", fg="#555")
        threading.Thread(target=self._load_platforms,
                         args=(stop,), daemon=True).start()

    def _load_platforms(self, stop):
        """Charge les quais de l'arrêt et les affiche sur la carte."""
        url = ("https://transport.opendata.ch/v1/stationboard"
               "?station=" + urllib.parse.quote(stop["name"]) + "&limit=40")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            from collections import defaultdict, Counter
            platforms = defaultdict(Counter)
            for e in data.get("stationboard", []):
                pf   = e["stop"].get("platform") or "?"
                dest = e.get("to","").replace("Gen\u00e8ve, ","")
                platforms[pf][dest] += 1
            quais = []
            for pf, dests in sorted(platforms.items()):
                top = [d for d, _ in dests.most_common(3)]
                quais.append({"platform": pf, "dests": top})
        except Exception:
            quais = []
        self.after(0, lambda: self._show_platforms(stop, quais))

    def _show_platforms(self, stop, quais):
        """Affiche 2 points (un par côté de la route) sur la carte."""
        if not quais:
            self._select_platform(stop["name"], None)
            return
        if len(quais) == 1:
            self._select_platform(stop["name"], quais[0]["platform"])
            return

        self._stop_lbl.config(
            text="De quel côté êtes-vous ? Cliquez sur votre côté →",
            fg="#ffaa00")

        import math
        lat = stop.get("lat") or 0
        lon = stop.get("lon") or 0

        # Placer les 2 côtés N et S (ou E et O) à ~15m d'écart
        OFFSET = 0.00015   # ~15 mètres
        sides  = [
            {"lat": lat + OFFSET, "lon": lon, "color": "#ff8c00"},
            {"lat": lat - OFFSET, "lon": lon, "color": "#00aaff"},
        ]

        platform_stops = []
        for i, (q, side) in enumerate(zip(quais[:2], sides)):
            lines  = " · ".join(q["dests"][:3])
            platform_stops.append({
                "name":     stop["name"],
                "lat":      side["lat"],
                "lon":      side["lon"],
                "platform": q["platform"],
                "label":    lines,
                "color":    side["color"],
            })

        if HAS_PIL and hasattr(self, "_map"):
            self._map.add_platform_stops(platform_stops, self._select_platform)

    def _select_platform(self, stop_name, platform):
        """Appelé quand l'utilisateur clique sur un quai."""
        self._stop_name = stop_name
        pf_txt = f" (quai {platform})" if platform else ""
        self._stop_lbl.config(text=f"✓  {stop_name}{pf_txt}", fg="#ff8c00")
        self._btn.config(state="normal", bg="#ff8c00", fg="#000",
                         text="▶  Lancer l'afficheur")
        self._current_platform = platform

    def _launch(self):
        if not self._stop_name:
            return
        platform = getattr(self, "_current_platform", None)
        self._do_launch(None, platform)

    def _fetch_directions(self):
        url = ("https://transport.opendata.ch/v1/stationboard"
               "?station=" + urllib.parse.quote(self._stop_name) + "&limit=40")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            # Grouper par platform (quai/côté de la route)
            from collections import defaultdict, Counter
            platforms = defaultdict(Counter)
            for e in data.get("stationboard", []):
                platform = e["stop"].get("platform") or "?"
                dest = e.get("to","").replace("Gen\u00e8ve, ","")
                platforms[platform][dest] += 1
            # Construire la liste des quais avec leurs destinations principales
            quais = []
            for platform, dests in sorted(platforms.items()):
                top_dests = [d for d, _ in dests.most_common(3)]
                quais.append({"platform": platform, "dests": top_dests})
        except Exception:
            quais = []
        self.after(0, lambda: self._ask_direction(quais))

    def _ask_direction(self, quais):
        self._btn.config(state="normal", text="\u25b6  Lancer l'afficheur")
        if not quais:
            self._do_launch(None, None)
            return
        if len(quais) == 1:
            self._do_launch(None, quais[0]["platform"])
            return

        win = tk.Toplevel(self)
        win.title("Choisir le quai")
        win.configure(bg="#1a1a1a")
        win.resizable(False, False)
        win.lift()
        win.focus_force()

        tk.Label(win,
            text="De quel côté de la route êtes-vous ?",
            fg="#ff8c00", bg="#1a1a1a",
            font=("Arial", 12, "bold"), pady=12).pack(padx=20)

        frame = tk.Frame(win, bg="#1a1a1a")
        frame.pack(padx=16, pady=(0, 8), fill="x")

        for q in quais:
            pf   = q["platform"]
            dests = ", ".join(q["dests"][:3])
            label = f"  Quai {pf}  \u2192  {dests}"
            if len(label) > 55:
                label = label[:55] + "..."
            btn = tk.Button(frame,
                text=label,
                bg="#222", fg="#ccc",
                font=("Arial", 11), relief="flat",
                padx=12, pady=10, anchor="w",
                activebackground="#ff8c00", activeforeground="#000",
                cursor="hand2",
                command=lambda p=pf: [win.destroy(), self._do_launch(None, p)])
            btn.pack(fill="x", pady=3)

        tk.Button(win, text="Tous les quais",
            bg="#333", fg="#aaa", font=("Arial", 10),
            relief="flat", pady=6,
            command=lambda: [win.destroy(), self._do_launch(None, None)]).pack(pady=(0,10))
        win.grab_set()

    def _do_launch(self, direction, platform):
        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tpg_led.py")
        if not os.path.exists(script):
            script = "tpg_led.py"
        env = os.environ.copy()
        env["TPG_STATION"] = self._stop_name
        if direction:
            env["TPG_DIRECTION"] = direction
        else:
            env.pop("TPG_DIRECTION", None)
        if platform:
            env["TPG_PLATFORM"] = platform
        else:
            env.pop("TPG_PLATFORM", None)
        env.pop("TPG_LINE", None)
        subprocess.Popen([sys.executable, script], env=env)
        self.after(500, self.destroy)



# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not HAS_PIL:
        print("Pillow requis : pip install Pillow")
    app = TPGSelector()
    app.mainloop()