import pygame
import sys
import os
import math
import struct
import random
import json
import io
import wave
import array
import subprocess
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
from collections import deque

# Tk after pygame/SDL on macOS crashes. Use Tk only in a child process there.
if sys.platform != "darwin":
    import tkinter as tk
    from tkinter import filedialog


# -------------------------
# DIALOG FILE HELPERS (cross‑platform)
# -------------------------
def _open_level_filetypes():
    return [
        ("SMBX level (.lvl)", "*.lvl"),
        ("LunaLua (.38a)", "*.38a"),
        ("Moondust / PGE (.lvlx)", "*.lvlx"),
        ("All files", "*.*"),
    ]


def _save_level_filetypes():
    return [
        ("SMBX 1.3 binary (.lvl)", "*.lvl"),
        ("LunaLua archive (.38a)", "*.38a"),
        ("Moondust LVLX (.lvlx)", "*.lvlx"),
        ("All files", "*.*"),
    ]


def _save_dialog_initial(suggested_name, initial_dir):
    base = suggested_name or ""
    initialfile = os.path.basename(base) if base else ""
    start = initial_dir
    if not start and base:
        d = os.path.dirname(os.path.abspath(base))
        if d and os.path.isdir(d):
            start = d
    if not start:
        start = os.path.expanduser("~")
    if not os.path.isdir(start):
        start = os.path.expanduser("~")
    return start, initialfile


def _tk_subprocess_open(initialdir, title, filetypes):
    code = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "root = tk.Tk()\n"
        "root.withdraw()\n"
        "root.attributes('-topmost', True)\n"
        "root.update_idletasks()\n"
        "try:\n"
        " p = filedialog.askopenfilename(\n"
        f"  title={title!r},\n"
        f"  filetypes={filetypes!r},\n"
        f"  initialdir={initialdir!r},\n"
        " )\n"
        " print(p or '', end='')\n"
        "finally:\n"
        " root.destroy()\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return (r.stdout or "").strip() or None


def _tk_subprocess_save(initialdir, initialfile, title, defaultextension, filetypes):
    code = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "root = tk.Tk()\n"
        "root.withdraw()\n"
        "root.attributes('-topmost', True)\n"
        "root.update_idletasks()\n"
        "try:\n"
        " p = filedialog.asksaveasfilename(\n"
        f"  title={title!r},\n"
        f"  defaultextension={defaultextension!r},\n"
        f"  filetypes={filetypes!r},\n"
        f"  initialfile={initialfile!r},\n"
        f"  initialdir={initialdir!r},\n"
        " )\n"
        " print(p or '', end='')\n"
        "finally:\n"
        " root.destroy()\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return (r.stdout or "").strip() or None


def ask_open_level_path(initial_dir=None):
    start = initial_dir or os.path.expanduser("~")
    if not os.path.isdir(start):
        start = os.path.expanduser("~")
    fts = _open_level_filetypes()
    if sys.platform == "darwin":
        path = _tk_subprocess_open(start, "Open Level", fts)
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()
        try:
            path = filedialog.askopenfilename(
                parent=root,
                title="Open Level",
                filetypes=fts,
                initialdir=start,
            )
        finally:
            root.destroy()
        path = path if path else None
    return path if path else None


def ask_save_level_path(suggested_name="level.lvl", initial_dir=None):
    base = suggested_name or "level.lvl"
    start, initialfile = _save_dialog_initial(base, initial_dir)
    ext = os.path.splitext(initialfile)[1].lower()
    defaultext = ext if ext in (".lvl", ".38a", ".lvlx") else ".lvl"
    fts = _save_level_filetypes()
    if sys.platform == "darwin":
        path = _tk_subprocess_save(
            start, initialfile, "Save Level As", defaultext, fts
        )
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()
        try:
            path = filedialog.asksaveasfilename(
                parent=root,
                title="Save Level As",
                defaultextension=defaultext,
                filetypes=fts,
                initialfile=initialfile,
                initialdir=start,
            )
        finally:
            root.destroy()
    if not path:
        return None
    if not os.path.splitext(path)[1]:
        path += defaultext
    return path


def ask_save_json_path(suggested_name="level.json", initial_dir=None):
    base = suggested_name or "level.json"
    start, initialfile = _save_dialog_initial(base, initial_dir)
    json_types = [
        ("JSON (*.json)", "*.json"),
        ("All files", "*.*"),
    ]
    if sys.platform == "darwin":
        path = _tk_subprocess_save(
            start, initialfile, "Export Level as JSON", ".json", json_types
        )
    else:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()
        try:
            path = filedialog.asksaveasfilename(
                parent=root,
                title="Export Level as JSON",
                defaultextension=".json",
                filetypes=json_types,
                initialfile=initialfile,
                initialdir=start,
            )
        finally:
            root.destroy()
    if not path:
        return None
    if not path.lower().endswith(".json"):
        path += ".json"
    return path


# -------------------------
# CONSTANTS & CONFIG
# -------------------------
WINDOW_WIDTH, WINDOW_HEIGHT = 1024, 700
SIDEBAR_WIDTH = 200
MENU_HEIGHT = 22
TOOLBAR_HEIGHT = 28
STATUSBAR_HEIGHT = 24
CANVAS_X = SIDEBAR_WIDTH
CANVAS_Y = MENU_HEIGHT + TOOLBAR_HEIGHT
CANVAS_WIDTH = WINDOW_WIDTH - SIDEBAR_WIDTH
CANVAS_HEIGHT = WINDOW_HEIGHT - CANVAS_Y - STATUSBAR_HEIGHT

APP_TITLE = "AC'S Mario fan builder"
APP_VER = "0.1"

GRID_SIZE = 32
FPS = 60
ZOOM_MIN, ZOOM_MAX = 0.25, 4.0
ZOOM_STEP = 0.25

# Dark fusion-style UI (dock panels, orange accent)
SYS_BG         = (40, 40, 40)
SYS_BTN_FACE   = (56, 58, 60)
SYS_BTN_LIGHT  = (86, 88, 91)
SYS_BTN_DARK   = (36, 37, 38)
SYS_BTN_DK_SHD = (22, 22, 23)
SYS_WINDOW     = (69, 72, 74)
SYS_HIGHLIGHT  = (200, 118, 42)
SYS_HIGHLIGHT2 = (236, 168, 72)
SYS_TEXT       = (210, 210, 210)
WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
RED    = (255, 0,   0)
GREEN  = (0,   200, 0)
BLUE   = (0,   0,   255)
YELLOW = (255, 255, 0)
GRAY   = (128, 128, 128)
SMBX_GRID = (72, 74, 78)

GRAVITY           = 0.5
JUMP_STRENGTH     = -10
MOVE_SPEED        = 4
TERMINAL_VELOCITY = 10

pygame.init()
pygame.display.set_caption(f"{APP_TITLE}")
_MIXER_READY = False
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    _MIXER_READY = True
except pygame.error:
    pass
FONT       = pygame.font.Font(None, 20)
FONT_MENU  = pygame.font.Font(None, 20)
FONT_SMALL = pygame.font.Font(None, 16)
FONT_TITLE = pygame.font.Font(None, 28)


# -------------------------
# SMBX ID MAPPINGS (EXTENDED)
# -------------------------
TILE_SMBX_IDS = {
    'ground':1, 'grass':2, 'sand':3, 'dirt':4,
    'brick':45, 'question':34, 'pipe_vertical':112, 'pipe_horizontal':113,
    'platform':159, 'coin':10, 'bridge':47,
    'stone':48, 'ice':55, 'mushroom_platform':91, 'pswitch':60,
    'slope_left':182, 'slope_right':183, 'water':196, 'lava':197,
    'conveyor_left':188, 'conveyor_right':189, 'semisolid':190,
}
BGO_SMBX_IDS  = {'cloud':5, 'bush':6, 'hill':7, 'fence':8, 'bush_3':9, 'tree':10,
                 'castle':11, 'waterfall':12, 'sign':13, 'fence2':14, 'fence3':15}
NPC_SMBX_IDS  = {
    'goomba':1, 'koopa_green':2, 'koopa_red':3, 'paratroopa_green':4,
    'paratroopa_red':5, 'piranha':6, 'hammer_bro':7, 'lakitu':8,
    'mushroom':9, 'flower':10, 'star':11, '1up':12,
    'buzzy':13, 'spiny':14, 'cheep':15, 'blooper':16, 'thwomp':17, 'bowser':18, 'boo':19,
    'podoboo':20, 'piranha_fire':21, 'sledge_bro':22, 'rotodisc':23,
    'burner':24, 'cannon':25, 'bullet_bill':26, 'bowser_statue':27,
    'grinder':28, 'fishbone':29, 'dry_bones':30, 'boo_ring':31,
    'bomber_bill':32, 'bony_beetle':33, 'skull_platform':34,
}
TILE_ID_TO_NAME = {v:k for k,v in TILE_SMBX_IDS.items()}
BGO_ID_TO_NAME  = {v:k for k,v in BGO_SMBX_IDS.items()}
NPC_ID_TO_NAME  = {v:k for k,v in NPC_SMBX_IDS.items()}


# -------------------------
# THEMES (for fallback colors)
# -------------------------
themes = {
    'SMB1': {
        'background':(92,148,252), 'ground':(0,128,0), 'brick':(180,80,40),
        'question':(255,200,0), 'coin':(255,255,0), 'pipe_vertical':(0,200,0),
        'pipe_horizontal':(0,180,0), 'platform':(139,69,19), 'goomba':(200,100,0),
        'koopa_green':(0,200,50), 'koopa_red':(200,50,50), 'mushroom':(255,0,200),
        'flower':(255,140,0), 'star':(255,230,0), 'bgo_cloud':(220,220,220),
        'bgo_bush':(0,160,0), 'bgo_hill':(100,200,100), 'bgo_tree':(0,120,0),
        'grass':(60,180,60), 'sand':(220,200,100), 'dirt':(150,100,60),
        'stone':(140,140,140), 'ice':(160,220,255), 'bridge':(160,100,40),
        'mushroom_platform':(200,100,200), 'pswitch':(80,80,200),
        'slope_left':(180,180,0), 'slope_right':(180,180,0), 'water':(0,100,255),
        'lava':(255,80,0), 'conveyor_left':(100,100,100), 'conveyor_right':(100,100,100),
        'semisolid':(150,150,200),
    },
    'SMB3': {
        'background':(0,0,0), 'ground':(160,120,80), 'brick':(180,100,60),
        'question':(255,210,0), 'coin':(255,255,100), 'pipe_vertical':(0,180,0),
        'pipe_horizontal':(0,160,0), 'platform':(100,100,100), 'goomba':(255,50,50),
        'koopa_green':(0,200,0), 'koopa_red':(200,0,0), 'mushroom':(255,100,200),
        'flower':(255,150,0), 'star':(255,255,0), 'bgo_cloud':(150,150,150),
        'bgo_bush':(0,100,0), 'bgo_hill':(80,160,80), 'bgo_tree':(0,80,0),
        'grass':(130,100,60), 'sand':(200,170,80), 'dirt':(120,80,40),
        'stone':(110,110,110), 'ice':(130,190,230), 'bridge':(130,80,30),
        'mushroom_platform':(170,80,170), 'pswitch':(60,60,170),
        'slope_left':(180,180,0), 'slope_right':(180,180,0), 'water':(0,100,255),
        'lava':(255,80,0), 'conveyor_left':(100,100,100), 'conveyor_right':(100,100,100),
        'semisolid':(150,150,200),
    },
    'SMW': {
        'background':(110,200,255), 'ground':(200,160,100), 'brick':(210,120,70),
        'question':(255,220,0), 'coin':(255,240,0), 'pipe_vertical':(0,220,80),
        'pipe_horizontal':(0,200,70), 'platform':(180,130,70), 'goomba':(210,120,0),
        'koopa_green':(0,220,80), 'koopa_red':(220,60,60), 'mushroom':(255,50,200),
        'flower':(255,160,0), 'star':(255,240,0), 'bgo_cloud':(240,240,240),
        'bgo_bush':(0,200,80), 'bgo_hill':(120,220,120), 'bgo_tree':(0,160,60),
        'grass':(80,200,80), 'sand':(230,210,120), 'dirt':(170,120,70),
        'stone':(160,160,160), 'ice':(180,230,255), 'bridge':(180,120,50),
        'mushroom_platform':(220,120,220), 'pswitch':(100,100,220),
        'slope_left':(180,180,0), 'slope_right':(180,180,0), 'water':(0,100,255),
        'lava':(255,80,0), 'conveyor_left':(100,100,100), 'conveyor_right':(100,100,100),
        'semisolid':(150,150,200),
    }
}
current_theme = 'SMB1'


# -------------------------
# PROCEDURAL SFX (no external sound files; engine presets)
# -------------------------
class ProceduralSfxEngine:
    """NES-ish square / noise bursts; presets tweak pitch, length, and brightness."""

    SR = 22050
    PRESETS = ("off", "smb1", "smb3", "smw", "mm")

    def __init__(self):
        self.preset = "off"
        self._sound_cache = {}

    def set_preset(self, name):
        n = (name or "off").lower()
        if n == "mario_maker":
            n = "mm"
        if n not in self.PRESETS:
            n = "off"
        if n != self.preset:
            self._sound_cache.clear()
        self.preset = n

    def _shape(self, preset, kind):
        """(f0, f1, seconds, duty, noise_mix) — linear freq sweep f0→f1."""
        p = preset
        k = kind
        if p == "smb1":
            if k == "jump":
                return 320, 120, 0.11, 0.5, 0.0
            if k == "coin":
                return 988, 1319, 0.06, 0.5, 0.02
            if k == "stomp":
                return 180, 60, 0.08, 0.45, 0.15
            if k == "hurt":
                return 200, 80, 0.18, 0.5, 0.1
            if k == "die":
                return 400, 60, 0.55, 0.5, 0.08
            if k == "powerup":
                return 220, 880, 0.35, 0.5, 0.0
        if p == "smb3":
            if k == "jump":
                return 360, 140, 0.10, 0.48, 0.0
            if k == "coin":
                return 1100, 1480, 0.055, 0.48, 0.03
            if k == "stomp":
                return 200, 70, 0.075, 0.42, 0.18
            if k == "hurt":
                return 240, 90, 0.16, 0.48, 0.12
            if k == "die":
                return 480, 80, 0.48, 0.48, 0.1
            if k == "powerup":
                return 260, 960, 0.32, 0.48, 0.0
        if p == "smw":
            if k == "jump":
                return 420, 180, 0.09, 0.42, 0.0
            if k == "coin":
                return 1200, 1600, 0.05, 0.42, 0.04
            if k == "stomp":
                return 240, 100, 0.065, 0.38, 0.12
            if k == "hurt":
                return 300, 120, 0.14, 0.42, 0.1
            if k == "die":
                return 560, 100, 0.42, 0.42, 0.08
            if k == "powerup":
                return 300, 1020, 0.28, 0.42, 0.0
        if p == "mm":
            if k == "jump":
                return 520, 260, 0.065, 0.4, 0.0
            if k == "coin":
                return 1400, 1800, 0.038, 0.4, 0.05
            if k == "stomp":
                return 300, 140, 0.045, 0.35, 0.1
            if k == "hurt":
                return 380, 160, 0.1, 0.4, 0.08
            if k == "die":
                return 700, 120, 0.32, 0.4, 0.06
            if k == "powerup":
                return 400, 1100, 0.22, 0.4, 0.0
        return 440, 440, 0.08, 0.5, 0.0

    def _synth(self, kind):
        if self.preset == "off" or not _MIXER_READY:
            return None
        f0, f1, dur, duty, nmix = self._shape(self.preset, kind)
        n = int(self.SR * dur)
        if n < 1:
            return None
        out = array.array("h")
        phase = 0.0
        rng = random.Random(hash((self.preset, kind)) & 0xFFFFFFFF)
        for i in range(n):
            t = i / self.SR
            alpha = i / max(1, n - 1)
            f = f0 + (f1 - f0) * alpha
            phase += 2.0 * math.pi * max(30.0, f) / self.SR
            sq = 30000.0 if (phase % (2 * math.pi)) < (2 * math.pi * duty) else -30000.0
            nz = (rng.random() * 2.0 - 1.0) * 28000.0 * nmix
            env = min(1.0, i / (self.SR * 0.004)) * (1.0 - alpha) ** 0.35
            v = (sq * (1.0 - nmix) + nz) * env
            out.append(int(max(-32767, min(32767, v))))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SR)
            w.writeframes(out.tobytes())
        buf.seek(0)
        return pygame.mixer.Sound(file=buf)

    def _get_sound(self, kind):
        key = (self.preset, kind)
        if key not in self._sound_cache:
            s = self._synth(kind)
            self._sound_cache[key] = s
        return self._sound_cache[key]

    def play(self, kind):
        if self.preset == "off" or not _MIXER_READY:
            return
        snd = self._get_sound(kind)
        if snd is not None:
            snd.play()


# -------------------------
# HELPERS
# -------------------------
def draw_edge(surf, rect, raised=True):
    r = pygame.Rect(rect)
    tl  = SYS_BTN_LIGHT  if raised else SYS_BTN_DK_SHD
    br  = SYS_BTN_DK_SHD if raised else SYS_BTN_LIGHT
    tli = SYS_BTN_FACE    if raised else SYS_BTN_DARK
    bri = SYS_BTN_DARK    if raised else SYS_BTN_FACE
    pygame.draw.line(surf, tl,  r.topleft,    r.topright)
    pygame.draw.line(surf, tl,  r.topleft,    r.bottomleft)
    pygame.draw.line(surf, br,  r.bottomleft, r.bottomright)
    pygame.draw.line(surf, br,  r.topright,   r.bottomright)
    pygame.draw.line(surf, tli, (r.left+1,r.top+1),    (r.right-1,r.top+1))
    pygame.draw.line(surf, tli, (r.left+1,r.top+1),    (r.left+1,r.bottom-1))
    pygame.draw.line(surf, bri, (r.left+1,r.bottom-1), (r.right-1,r.bottom-1))
    pygame.draw.line(surf, bri, (r.right-1,r.top+1),   (r.right-1,r.bottom-1))


def draw_text(surf, text, pos, color=SYS_TEXT, font=FONT, center=False):
    t = font.render(str(text), True, color)
    r = t.get_rect(center=pos) if center else t.get_rect(topleft=pos)
    surf.blit(t, r)


def get_theme_color(name):
    return themes[current_theme].get(name, (128,128,128))


# -------------------------
# ICON DRAWING
# -------------------------
def draw_icon_select(surf, rect, color=SYS_TEXT):
    r = rect.inflate(-6,-6)
    for i in range(0, r.width, 4):
        if (i//4)%2==0:
            pygame.draw.line(surf,color,(r.x+i,r.y),(min(r.x+i+3,r.right),r.y))
            pygame.draw.line(surf,color,(r.x+i,r.bottom),(min(r.x+i+3,r.right),r.bottom))
    for i in range(0, r.height, 4):
        if (i//4)%2==0:
            pygame.draw.line(surf,color,(r.x,r.y+i),(r.x,min(r.y+i+3,r.bottom)))
            pygame.draw.line(surf,color,(r.right,r.y+i),(r.right,min(r.y+i+3,r.bottom)))


def draw_icon_pencil(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pts=[(cx-1,cy+6),(cx+5,cy-3),(cx+3,cy-5),(cx-3,cy+4)]
    pygame.draw.polygon(surf,color,pts,1)
    pygame.draw.line(surf,color,(cx-1,cy+6),(cx-4,cy+8))
    pygame.draw.line(surf,color,(cx-4,cy+8),(cx-2,cy+5))


def draw_icon_eraser(surf, rect, color=SYS_TEXT):
    r=rect.inflate(-8,-8)
    pygame.draw.rect(surf,color,(r.x,r.centery-3,r.width,7),1)
    pygame.draw.line(surf,color,(r.x+r.width//2,r.centery-3),(r.x+r.width//2,r.centery+4))


def draw_icon_fill(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.rect(surf,color,(cx-5,cy-4,8,8),1)
    pygame.draw.rect(surf,color,(cx-4,cy-3,6,6))
    pygame.draw.circle(surf,color,(cx+5,cy+4),2)


def draw_icon_new(surf, rect, color=SYS_TEXT):
    r=rect.inflate(-8,-6); fold=5
    pts=[(r.x,r.y),(r.right-fold,r.y),(r.right,r.y+fold),(r.right,r.bottom),(r.x,r.bottom)]
    pygame.draw.polygon(surf,color,pts,1)
    pygame.draw.line(surf,color,(r.right-fold,r.y),(r.right-fold,r.y+fold))
    pygame.draw.line(surf,color,(r.right-fold,r.y+fold),(r.right,r.y+fold))


def draw_icon_open(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.rect(surf,color,(cx-7,cy-2,14,9),1)
    pygame.draw.rect(surf,color,(cx-7,cy-5,6,4),1)


def draw_icon_save(surf, rect, color=SYS_TEXT):
    r=rect.inflate(-8,-6)
    pygame.draw.rect(surf,color,r,1)
    pygame.draw.rect(surf,SYS_BTN_FACE,(r.x+2,r.y+2,r.width-4,r.height//2-2))
    pygame.draw.rect(surf,color,(r.x+5,r.y+2,r.width-10,r.height//2-2),1)
    pygame.draw.rect(surf,color,(r.x+r.width//3,r.bottom-5,r.width//3,5))


def draw_icon_undo(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.arc(surf,color,(cx-6,cy-4,12,10),math.pi*0.3,math.pi*1.1,2)
    pygame.draw.polygon(surf,color,[(cx-6,cy-4),(cx-9,cy),(cx-3,cy-1)])


def draw_icon_redo(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.arc(surf,color,(cx-6,cy-4,12,10),math.pi*1.9,math.pi*0.7+math.pi*2,2)
    pygame.draw.polygon(surf,color,[(cx+6,cy-4),(cx+9,cy),(cx+3,cy-1)])


def draw_icon_play(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.polygon(surf,color,[(cx-4,cy-6),(cx-4,cy+6),(cx+6,cy)])


def draw_icon_props(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    draw_text(surf,"i",(cx,cy),color,FONT_SMALL,True)
    pygame.draw.circle(surf,color,(cx,cy-5),2)


def draw_icon_grid(surf, rect, color=SYS_TEXT):
    r=rect.inflate(-6,-6)
    for i in range(0,r.width+1,r.width//2):
        pygame.draw.line(surf,color,(r.x+i,r.y),(r.x+i,r.bottom))
    for i in range(0,r.height+1,r.height//2):
        pygame.draw.line(surf,color,(r.x,r.y+i),(r.right,r.y+i))


def draw_icon_zoom_in(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.circle(surf,color,(cx-2,cy-2),5,1)
    pygame.draw.line(surf,color,(cx+2,cy+2),(cx+6,cy+6),2)
    pygame.draw.line(surf,color,(cx-4,cy-2),(cx,cy-2),1)
    pygame.draw.line(surf,color,(cx-2,cy-4),(cx-2,cy),1)


def draw_icon_zoom_out(surf, rect, color=SYS_TEXT):
    cx,cy=rect.center
    pygame.draw.circle(surf,color,(cx-2,cy-2),5,1)
    pygame.draw.line(surf,color,(cx+2,cy+2),(cx+6,cy+6),2)
    pygame.draw.line(surf,color,(cx-4,cy-2),(cx,cy-2),1)


def draw_icon_layer(surf, rect, color=SYS_TEXT):
    r=rect.inflate(-6,-6)
    for i in range(3):
        y=r.y+i*4
        pygame.draw.rect(surf,color,(r.x,y,r.width,4),1)


def draw_icon_event(surf, rect, color=SYS_TEXT):
    cx,cy = rect.center
    pygame.draw.circle(surf,color,(cx-4,cy-4),2)
    pygame.draw.circle(surf,color,(cx+4,cy-4),2)
    pygame.draw.arc(surf,color,(cx-6,cy,12,8),0,math.pi,2)


ICON_FNS = {
    'select':draw_icon_select, 'pencil':draw_icon_pencil, 'eraser':draw_icon_eraser,
    'fill':draw_icon_fill, 'new':draw_icon_new, 'open':draw_icon_open, 'save':draw_icon_save,
    'undo':draw_icon_undo, 'redo':draw_icon_redo, 'play':draw_icon_play, 'props':draw_icon_props,
    'grid':draw_icon_grid, 'zoom_in':draw_icon_zoom_in, 'zoom_out':draw_icon_zoom_out,
    'layer':draw_icon_layer, 'event':draw_icon_event,
}


# -------------------------
# DIALOG CLASSES (advanced)
# -------------------------
class Dialog:
    def __init__(self, screen, title, w, h):
        self.screen = screen
        self.title  = title
        self.w, self.h = w, h
        self.x = (WINDOW_WIDTH - w) // 2
        self.y = (WINDOW_HEIGHT - h) // 2
        self.rect = pygame.Rect(self.x, self.y, w, h)
        self.done = False
        self.result = None
        self._overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 150))

    def _draw_frame(self):
        self.screen.blit(self._overlay,(0,0))
        pygame.draw.rect(self.screen, SYS_BTN_FACE, self.rect)
        draw_edge(self.screen, self.rect, raised=True)
        title_r = pygame.Rect(self.x+2, self.y+2, self.w-4, 20)
        pygame.draw.rect(self.screen, SYS_HIGHLIGHT, title_r)
        draw_text(self.screen, self.title, (title_r.x+4, title_r.y+3), WHITE, FONT_SMALL)
        xr = pygame.Rect(title_r.right-18, title_r.y+1, 16, 16)
        pygame.draw.rect(self.screen, SYS_BTN_FACE, xr)
        draw_edge(self.screen, xr, raised=True)
        draw_text(self.screen, "X", xr.center, SYS_TEXT, FONT_SMALL, True)
        return title_r, xr

    def run(self):
        clock = pygame.time.Clock()
        while not self.done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.done=True; self.result=None
                self.handle_event(event)
            self.draw()
            pygame.display.flip()
            clock.tick(60)
        return self.result

    def handle_event(self, event):
        pass

    def draw(self):
        self._draw_frame()


class MessageBox(Dialog):
    def __init__(self, screen, title, message, buttons=("OK",)):
        lines = message.split('\n')
        w = max(300, max(FONT_SMALL.size(l)[0] for l in lines)+60)
        h = 80 + len(lines)*18 + 40
        super().__init__(screen, title, w, h)
        self.message = message
        self.buttons = buttons

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button==1:
            by = self.h - 40
            bw = 70; gap = 10
            total = len(self.buttons)*(bw+gap)-gap
            bstart = (self.w - total)//2
            for i,b in enumerate(self.buttons):
                r = pygame.Rect(self.x+bstart+i*(bw+gap), self.y+by, bw, 24)
                if r.collidepoint(event.pos):
                    self.result=b; self.done=True

    def draw(self):
        self._draw_frame()
        lines = self.message.split('\n')
        for i,l in enumerate(lines):
            draw_text(self.screen, l, (self.x+20, self.y+34+i*18), SYS_TEXT, FONT_SMALL)
        by=self.h-40; bw=70; gap=10
        total=len(self.buttons)*(bw+gap)-gap
        bstart=(self.w-total)//2
        for i,b in enumerate(self.buttons):
            r=pygame.Rect(self.x+bstart+i*(bw+gap),self.y+by,bw,24)
            pygame.draw.rect(self.screen,SYS_BTN_FACE,r)
            draw_edge(self.screen,r,raised=True)
            draw_text(self.screen,b,r.center,SYS_TEXT,FONT_SMALL,True)


class InputDialog(Dialog):
    def __init__(self, screen, title, prompt, default=""):
        super().__init__(screen, title, 340, 120)
        self.prompt  = prompt
        self.value   = default
        self.cursor  = len(default)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.result=self.value; self.done=True
            elif event.key == pygame.K_ESCAPE:
                self.done=True
            elif event.key == pygame.K_BACKSPACE and self.cursor>0:
                self.value=self.value[:self.cursor-1]+self.value[self.cursor:]
                self.cursor-=1
            elif event.key == pygame.K_LEFT:
                self.cursor=max(0,self.cursor-1)
            elif event.key == pygame.K_RIGHT:
                self.cursor=min(len(self.value),self.cursor+1)
            elif event.unicode and event.unicode.isprintable():
                self.value=self.value[:self.cursor]+event.unicode+self.value[self.cursor:]
                self.cursor+=1
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            ok=pygame.Rect(self.x+self.w-170,self.y+86,70,24)
            cn=pygame.Rect(self.x+self.w-90, self.y+86,70,24)
            if ok.collidepoint(event.pos): self.result=self.value; self.done=True
            if cn.collidepoint(event.pos): self.done=True

    def draw(self):
        self._draw_frame()
        draw_text(self.screen, self.prompt, (self.x+14,self.y+34), SYS_TEXT, FONT_SMALL)
        ir=pygame.Rect(self.x+14,self.y+52,self.w-28,22)
        pygame.draw.rect(self.screen,SYS_WINDOW,ir)
        draw_edge(self.screen,ir,raised=False)
        draw_text(self.screen,self.value,(ir.x+4,ir.y+4),SYS_TEXT,FONT_SMALL)
        if pygame.time.get_ticks()%1000<500:
            cx=ir.x+4+FONT_SMALL.size(self.value[:self.cursor])[0]
            pygame.draw.line(self.screen,BLACK,(cx,ir.y+3),(cx,ir.y+18),1)
        for i,(lbl,bx) in enumerate([("OK",self.w-170),("Cancel",self.w-90)]):
            r=pygame.Rect(self.x+bx,self.y+86,70,24)
            pygame.draw.rect(self.screen,SYS_BTN_FACE,r)
            draw_edge(self.screen,r,raised=True)
            draw_text(self.screen,lbl,r.center,SYS_TEXT,FONT_SMALL,True)


class PropertiesDialog(Dialog):
    def __init__(self, screen, level):
        super().__init__(screen, "Level Properties", 420, 380)
        self.level = level
        self.section = level.current_section()
        self.fields = {
            'name': level.name, 'author': level.author, 'descr': level.description,
            'width': str(self.section.width // GRID_SIZE),
            'height': str(self.section.height // GRID_SIZE),
            'time_limit': str(level.time_limit),
            'lives': str(level.initial_lives), 'coins': str(level.initial_coins),
            'max_coins': str(level.max_coins),
        }
        self.active_field = None
        self.cursors = {k: len(v) for k, v in self.fields.items()}
        self.theme_sel = current_theme

    def _field_rect(self, fy):
        return pygame.Rect(self.x + 150, self.y + fy, 250, 18)

    def handle_event(self, event):
        labels = [('name', 'Level Name:', 50), ('author', 'Author:', 72), ('descr', 'Description:', 94),
                  ('width', 'Width (tiles):', 122), ('height', 'Height (tiles):', 142),
                  ('time_limit', 'Time Limit:', 162), ('lives', 'Lives:', 182),
                  ('coins', 'Start Coins:', 202), ('max_coins', 'Max Coins:', 222)]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active_field = None
            for key, _, fy in labels:
                if self._field_rect(fy).collidepoint(event.pos):
                    self.active_field = key
            bgs = [(92, 148, 252), (0, 0, 40), (0, 0, 0), (255, 140, 60), (30, 20, 10), (0, 80, 160)]
            for i, col in enumerate(bgs):
                r = pygame.Rect(self.x + 10 + i * 65, self.y + 262, 62, 18)
                if r.collidepoint(event.pos):
                    self.section.bg_color = col
            for i, tn in enumerate(themes.keys()):
                r = pygame.Rect(self.x + 10 + i * 90, self.y + 308, 84, 20)
                if r.collidepoint(event.pos):
                    self.theme_sel = tn
            ok = pygame.Rect(self.x + self.w - 170, self.y + self.h - 40, 70, 26)
            cn = pygame.Rect(self.x + self.w - 90, self.y + self.h - 40, 70, 26)
            if ok.collidepoint(event.pos):
                self._apply()
                self.result = 'ok'
                self.done = True
            if cn.collidepoint(event.pos):
                self.done = True
        if event.type == pygame.KEYDOWN and self.active_field:
            k = self.active_field
            v = self.fields[k]
            c = self.cursors[k]
            if event.key == pygame.K_RETURN:
                self.active_field = None
            elif event.key == pygame.K_BACKSPACE and c > 0:
                self.fields[k] = v[:c-1] + v[c:]
                self.cursors[k] = c - 1
            elif event.key == pygame.K_LEFT:
                self.cursors[k] = max(0, c - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursors[k] = min(len(v), c + 1)
            elif event.unicode and event.unicode.isprintable():
                self.fields[k] = v[:c] + event.unicode + v[c:]
                self.cursors[k] = c + 1

    def _apply(self):
        global current_theme
        self.level.name = self.fields['name']
        self.level.author = self.fields['author']
        self.level.description = self.fields['descr']
        try:
            nw = max(20, int(self.fields['width']))
            nh = max(10, int(self.fields['height']))
            self.section.width = nw * GRID_SIZE
            self.section.height = nh * GRID_SIZE
        except:
            pass
        try:
            self.level.time_limit = max(0, int(self.fields['time_limit']))
            self.level.initial_lives = max(0, int(self.fields['lives']))
            self.level.initial_coins = max(0, int(self.fields['coins']))
            self.level.max_coins = max(0, int(self.fields['max_coins']))
        except:
            pass
        current_theme = self.theme_sel

    def draw(self):
        self._draw_frame()
        labels = [('name', 'Level Name:', 50), ('author', 'Author:', 72), ('descr', 'Description:', 94),
                  ('width', 'Width (tiles):', 122), ('height', 'Height (tiles):', 142),
                  ('time_limit', 'Time Limit:', 162), ('lives', 'Lives:', 182),
                  ('coins', 'Start Coins:', 202), ('max_coins', 'Max Coins:', 222)]
        for key, lbl, fy in labels:
            draw_text(self.screen, lbl, (self.x + 10, self.y + fy + 1), SYS_TEXT, FONT_SMALL)
            ir = self._field_rect(fy)
            pygame.draw.rect(self.screen, SYS_WINDOW, ir)
            draw_edge(self.screen, ir, raised=False)
            v = self.fields[key]
            draw_text(self.screen, v, (ir.x + 3, ir.y + 2), SYS_TEXT, FONT_SMALL)
            if self.active_field == key and pygame.time.get_ticks() % 1000 < 500:
                cx = ir.x + 3 + FONT_SMALL.size(v[:self.cursors[key]])[0]
                pygame.draw.line(self.screen, BLACK, (cx, ir.y + 1), (cx, ir.y + 16))
        draw_text(self.screen, "Background:", (self.x + 10, self.y + 246), SYS_TEXT, FONT_SMALL)
        bgs = [(92, 148, 252), (0, 0, 40), (0, 0, 0), (255, 140, 60), (30, 20, 10), (0, 80, 160)]
        names = ['Sky', 'Night', 'Black', 'Sunset', 'Cave', 'Water']
        for i, col in enumerate(bgs):
            r = pygame.Rect(self.x + 10 + i * 65, self.y + 262, 62, 18)
            pygame.draw.rect(self.screen, col, r)
            draw_edge(self.screen, r, raised=self.section.bg_color != col)
            draw_text(self.screen, names[i][:7], (r.x + 2, r.y + 2),
                      (255, 255, 255) if sum(col) < 300 else BLACK, FONT_SMALL)
        draw_text(self.screen, "Theme:", (self.x + 10, self.y + 292), SYS_TEXT, FONT_SMALL)
        for i, tn in enumerate(themes.keys()):
            r = pygame.Rect(self.x + 10 + i * 90, self.y + 308, 84, 20)
            sel = (tn == self.theme_sel)
            pygame.draw.rect(self.screen, SYS_HIGHLIGHT if sel else SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=not sel)
            draw_text(self.screen, tn, r.center, WHITE if sel else SYS_TEXT, FONT_SMALL, True)
        for lbl, bx in [("OK", self.w - 170), ("Cancel", self.w - 90)]:
            r = pygame.Rect(self.x + bx, self.y + self.h - 40, 70, 26)
            pygame.draw.rect(self.screen, SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=True)
            draw_text(self.screen, lbl, r.center, SYS_TEXT, FONT_SMALL, True)


class LayerDialog(Dialog):
    def __init__(self, screen, section):
        super().__init__(screen, "Layer Manager", 340, 320)
        self.section = section
        self.sel = section.current_layer_idx
        self.new_name = section.layers[self.sel].name if section.layers else ""
        self.cursor = len(self.new_name)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, layer in enumerate(self.section.layers):
                r = pygame.Rect(self.x + 10, self.y + 36 + i * 22, self.w - 20, 20)
                if r.collidepoint(event.pos):
                    self.sel = i
                    self.new_name = layer.name
                    self.cursor = len(self.new_name)
                eye_r = pygame.Rect(r.right - 18, r.y + 2, 14, 16)
                if eye_r.collidepoint(event.pos):
                    layer.visible = not layer.visible
            add_r = pygame.Rect(self.x + 10, self.y + self.h - 82, 90, 24)
            del_r = pygame.Rect(self.x + 110, self.y + self.h - 82, 90, 24)
            ren_r = pygame.Rect(self.x + 210, self.y + self.h - 82, 100, 24)
            ok_r = pygame.Rect(self.x + self.w - 170, self.y + self.h - 46, 70, 26)
            cl_r = pygame.Rect(self.x + self.w - 90, self.y + self.h - 46, 70, 26)
            if add_r.collidepoint(event.pos):
                name = InputDialog(self.screen, "New Layer", "Layer name:", f"Layer {len(self.section.layers) + 1}").run()
                if name:
                    self.section.layers.append(Layer(name))
            if del_r.collidepoint(event.pos) and len(self.section.layers) > 1:
                self.section.layers.pop(self.sel)
                self.sel = max(0, self.sel - 1)
                self.section.current_layer_idx = self.sel
            if ren_r.collidepoint(event.pos) and self.section.layers:
                self.section.layers[self.sel].name = self.new_name
            if ok_r.collidepoint(event.pos):
                self.section.current_layer_idx = self.sel
                self.result = 'ok'
                self.done = True
            if cl_r.collidepoint(event.pos):
                self.done = True
        if event.type == pygame.KEYDOWN:
            v = self.new_name
            c = self.cursor
            if event.key == pygame.K_BACKSPACE and c > 0:
                self.new_name = v[:c-1] + v[c:]
                self.cursor = c - 1
            elif event.key == pygame.K_LEFT:
                self.cursor = max(0, c - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor = min(len(v), c + 1)
            elif event.unicode and event.unicode.isprintable():
                self.new_name = v[:c] + event.unicode + v[c:]
                self.cursor = c + 1

    def draw(self):
        self._draw_frame()
        draw_text(self.screen, "Layers:", (self.x + 14, self.y + 24), SYS_TEXT, FONT_SMALL)
        for i, layer in enumerate(self.section.layers):
            r = pygame.Rect(self.x + 10, self.y + 36 + i * 22, self.w - 20, 20)
            bg = SYS_HIGHLIGHT if i == self.sel else SYS_WINDOW
            pygame.draw.rect(self.screen, bg, r)
            draw_edge(self.screen, r, raised=False)
            draw_text(self.screen, layer.name, (r.x + 4, r.y + 3), WHITE if i == self.sel else SYS_TEXT, FONT_SMALL)
            eye = GREEN if layer.visible else RED
            eye_r = pygame.Rect(r.right - 18, r.y + 2, 14, 16)
            pygame.draw.rect(self.screen, eye, eye_r)
            lock = GRAY if layer.locked else SYS_BTN_FACE
            pygame.draw.rect(self.screen, lock, (r.right - 34, r.y + 2, 12, 16))
            draw_text(self.screen, "L" if layer.locked else "", (r.right - 32, r.y + 4), WHITE, FONT_SMALL)
        draw_text(self.screen, "Name:", (self.x + 10, self.y + self.h - 110), SYS_TEXT, FONT_SMALL)
        ir = pygame.Rect(self.x + 56, self.y + self.h - 112, self.w - 70, 20)
        pygame.draw.rect(self.screen, SYS_WINDOW, ir)
        draw_edge(self.screen, ir, raised=False)
        draw_text(self.screen, self.new_name, (ir.x + 4, ir.y + 3), SYS_TEXT, FONT_SMALL)
        if pygame.time.get_ticks() % 1000 < 500:
            cx = ir.x + 4 + FONT_SMALL.size(self.new_name[:self.cursor])[0]
            pygame.draw.line(self.screen, BLACK, (cx, ir.y + 2), (cx, ir.y + 16))
        for lbl, bx, bw in [("Add", 10, 90), ("Delete", 110, 90), ("Rename", 210, 100)]:
            r = pygame.Rect(self.x + bx, self.y + self.h - 82, bw, 24)
            pygame.draw.rect(self.screen, SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=True)
            draw_text(self.screen, lbl, r.center, SYS_TEXT, FONT_SMALL, True)
        for lbl, bx in [("OK", self.w - 170), ("Close", self.w - 90)]:
            r = pygame.Rect(self.x + bx, self.y + self.h - 46, 70, 26)
            pygame.draw.rect(self.screen, SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=True)
            draw_text(self.screen, lbl, r.center, SYS_TEXT, FONT_SMALL, True)


EVENT_ACTION_TYPES = [
    ("Trigger Event", "trigger"),
    ("Show Text", "text"),
    ("Play Sound", "sound"),
    ("End Level", "endlevel"),
    ("Move Layer", "movelayer"),
    ("Toggle Layer", "toggle"),
    ("Set Background", "setbg"),
    ("Set Music", "setmusic"),
    ("Teleport Player", "teleport"),
    ("Kill All NPCs", "killallnpcs"),
    ("Remove Layer", "removelayer"),
    ("Change Section", "changesection"),
]


class EventDialog(Dialog):
    def __init__(self, screen, level):
        super().__init__(screen, "Event Editor", 640, 460)
        self.level = level
        self.section = level.current_section()
        self.events = self.section.events
        self.sel = 0 if self.events else -1
        self.scroll = 0
        self.action_scroll = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
            for i, ev in enumerate(self.events):
                r = pygame.Rect(list_area.x, list_area.y + (i - self.scroll) * 20, 196, 18)
                if r.collidepoint(event.pos) and list_area.y <= r.y < list_area.bottom:
                    self.sel = i
            add_r = pygame.Rect(self.x + 10, self.y + self.h - 42, 70, 26)
            del_r = pygame.Rect(self.x + 86, self.y + self.h - 42, 70, 26)
            addact_r = pygame.Rect(self.x + 220, self.y + self.h - 42, 100, 26)
            delact_r = pygame.Rect(self.x + 326, self.y + self.h - 42, 100, 26)
            ok_r = pygame.Rect(self.x + self.w - 90, self.y + self.h - 42, 70, 26)
            if add_r.collidepoint(event.pos):
                nid = max((e.id for e in self.events), default=-1) + 1
                self.events.append(Event(f"Event {nid}", str(nid)))
                self.sel = len(self.events) - 1
            if del_r.collidepoint(event.pos) and 0 <= self.sel < len(self.events):
                self.events.pop(self.sel)
                self.sel = min(self.sel, len(self.events) - 1)
            if addact_r.collidepoint(event.pos) and 0 <= self.sel < len(self.events):
                ev = self.events[self.sel]
                idx = min(self.action_scroll, len(EVENT_ACTION_TYPES) - 1)
                atype = EVENT_ACTION_TYPES[idx][1]
                action = {"type": atype}
                if atype == "trigger":
                    action["event"] = "0"
                    action["delay"] = "0"
                elif atype == "text":
                    action["text"] = "Message"
                elif atype == "sound":
                    action["id"] = "0"
                elif atype == "endlevel":
                    action["exit"] = "0"
                elif atype == "movelayer":
                    action["layer"] = "Default"
                    action["speed"] = "1"
                    action["targetX"] = "0"
                    action["targetY"] = "0"
                elif atype == "toggle":
                    action["layer"] = "Default"
                    action["show"] = "1"
                elif atype == "setbg":
                    action["type"] = "0"
                    action["img"] = ""
                elif atype == "setmusic":
                    action["id"] = "0"
                    action["file"] = ""
                elif atype == "teleport":
                    action["x"] = "0"
                    action["y"] = "0"
                    action["type"] = "0"
                elif atype == "removelayer":
                    action["layer"] = "Default"
                elif atype == "changesection":
                    action["id"] = "0"
                ev.actions.append(action)
            if delact_r.collidepoint(event.pos) and 0 <= self.sel < len(self.events):
                ev = self.events[self.sel]
                if ev.actions:
                    ev.actions.pop()
            if ok_r.collidepoint(event.pos):
                self.done = True
            # Field editing
            if 0 <= self.sel < len(self.events):
                ev = self.events[self.sel]
                name_r = pygame.Rect(self.x + 220, self.y + 36, 390, 18)
                msg_r = pygame.Rect(self.x + 220, self.y + 58, 390, 18)
                if name_r.collidepoint(event.pos):
                    res = InputDialog(self.screen, "Event Name", "Name:", ev.name).run()
                    if res is not None:
                        ev.name = res
                if msg_r.collidepoint(event.pos):
                    res = InputDialog(self.screen, "Event Message", "Message:", ev.msg).run()
                    if res is not None:
                        ev.msg = res
                # Action parameter editing - click on action value fields
                ay = 90
                for ai, act in enumerate(ev.actions):
                    if ay > self.y + self.h - 60:
                        break
                    ar = pygame.Rect(self.x + 220, ay, 390, 16)
                    if ar.collidepoint(event.pos):
                        self._edit_action(ev, ai)
                    ay += 18
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
            if list_area.collidepoint(mx, my):
                self.scroll = max(0, min(self.scroll - event.y, max(0, len(self.events) - 16)))
            type_area = pygame.Rect(self.x + 220, self.y + self.h - 42, 100, 26)
            if type_area.inflate(200, 0).collidepoint(mx, my):
                self.action_scroll = max(0, min(self.action_scroll - event.y, len(EVENT_ACTION_TYPES) - 1))

    def _edit_action(self, ev, ai):
        act = ev.actions[ai]
        atype = act["type"]
        if atype == "trigger":
            res = InputDialog(self.screen, "Trigger Event", "Event ID:", act.get("event", "0")).run()
            if res is not None:
                act["event"] = res
        elif atype == "text":
            res = InputDialog(self.screen, "Show Text", "Text:", act.get("text", "")).run()
            if res is not None:
                act["text"] = res
        elif atype == "sound":
            res = InputDialog(self.screen, "Play Sound", "Sound ID:", act.get("id", "0")).run()
            if res is not None:
                act["id"] = res
        elif atype == "endlevel":
            res = InputDialog(self.screen, "End Level", "Exit code:", act.get("exit", "0")).run()
            if res is not None:
                act["exit"] = res
        elif atype == "movelayer":
            res = InputDialog(self.screen, "Move Layer", "Layer name:", act.get("layer", "Default")).run()
            if res is not None:
                act["layer"] = res
        elif atype == "toggle":
            res = InputDialog(self.screen, "Toggle Layer", "Layer name:", act.get("layer", "Default")).run()
            if res is not None:
                act["layer"] = res
        elif atype == "teleport":
            res = InputDialog(self.screen, "Teleport", "X,Y:", f"{act.get('x', '0')},{act.get('y', '0')}").run()
            if res is not None:
                parts = res.split(',')
                if len(parts) >= 2:
                    act["x"] = parts[0].strip()
                    act["y"] = parts[1].strip()
        elif atype == "removelayer":
            res = InputDialog(self.screen, "Remove Layer", "Layer name:", act.get("layer", "Default")).run()
            if res is not None:
                act["layer"] = res
        elif atype == "changesection":
            res = InputDialog(self.screen, "Change Section", "Section ID:", act.get("id", "0")).run()
            if res is not None:
                act["id"] = res

    def draw(self):
        self._draw_frame()
        draw_text(self.screen, "Events:", (self.x + 14, self.y + 26), SYS_TEXT, FONT_SMALL)
        list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
        pygame.draw.rect(self.screen, SYS_WINDOW, list_area)
        draw_edge(self.screen, list_area, raised=False)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(list_area)
        for i, ev in enumerate(self.events):
            r = pygame.Rect(list_area.x, list_area.y + (i - self.scroll) * 20, 196, 18)
            if r.bottom < list_area.top or r.top > list_area.bottom:
                continue
            bg = SYS_HIGHLIGHT if i == self.sel else SYS_WINDOW
            pygame.draw.rect(self.screen, bg, r)
            col = WHITE if i == self.sel else SYS_TEXT
            draw_text(self.screen, f"[{ev.id}] {ev.name}", (r.x + 3, r.y + 2), col, FONT_SMALL)
        self.screen.set_clip(old_clip)
        if 0 <= self.sel < len(self.events):
            ev = self.events[self.sel]
            draw_text(self.screen, "Name:", (self.x + 220, self.y + 38), SYS_TEXT, FONT_SMALL)
            name_r = pygame.Rect(self.x + 268, self.y + 36, 342, 18)
            pygame.draw.rect(self.screen, SYS_WINDOW, name_r)
            draw_edge(self.screen, name_r, raised=False)
            draw_text(self.screen, ev.name, (name_r.x + 3, name_r.y + 2), SYS_TEXT, FONT_SMALL)
            draw_text(self.screen, "Msg:", (self.x + 220, self.y + 60), SYS_TEXT, FONT_SMALL)
            msg_r = pygame.Rect(self.x + 254, self.y + 58, 356, 18)
            pygame.draw.rect(self.screen, SYS_WINDOW, msg_r)
            draw_edge(self.screen, msg_r, raised=False)
            msg_display = ev.msg[:50] + "..." if len(ev.msg) > 50 else ev.msg
            draw_text(self.screen, msg_display, (msg_r.x + 3, msg_r.y + 2), SYS_TEXT, FONT_SMALL)
            draw_text(self.screen, "Actions:", (self.x + 220, self.y + 80), SYS_TEXT, FONT_SMALL)
            ay = 96
            for ai, act in enumerate(ev.actions):
                if ay > self.y + self.h - 60:
                    draw_text(self.screen, "...", (self.x + 220, ay), GRAY, FONT_SMALL)
                    break
                desc = self._describe_action(act)
                draw_text(self.screen, f"{ai + 1}. {desc}", (self.x + 224, ay), SYS_TEXT, FONT_SMALL)
                ay += 18
        for lbl, bx, bw in [("Add Event", 10, 70), ("Del Event", 86, 70),
                             (f"+ {EVENT_ACTION_TYPES[self.action_scroll][0]}", 220, 100),
                             ("- Action", 326, 100)]:
            r = pygame.Rect(self.x + bx, self.y + self.h - 42, bw, 26)
            pygame.draw.rect(self.screen, SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=True)
            draw_text(self.screen, lbl, r.center, SYS_TEXT, FONT_SMALL, True)
        ok_r = pygame.Rect(self.x + self.w - 90, self.y + self.h - 42, 70, 26)
        pygame.draw.rect(self.screen, SYS_BTN_FACE, ok_r)
        draw_edge(self.screen, ok_r, raised=True)
        draw_text(self.screen, "Close", ok_r.center, SYS_TEXT, FONT_SMALL, True)

    def _describe_action(self, act):
        t = act.get("type", "?")
        if t == "trigger":
            return f"Trigger event {act.get('event', '?')} delay={act.get('delay', '0')}"
        if t == "text":
            return f"Text: {act.get('text', '')[:30]}"
        if t == "sound":
            return f"Sound ID {act.get('id', '?')}"
        if t == "endlevel":
            return f"End level exit={act.get('exit', '?')}"
        if t == "movelayer":
            return f"Move layer '{act.get('layer', '?')}'"
        if t == "toggle":
            return f"Toggle layer '{act.get('layer', '?')}' show={act.get('show', '?')}"
        if t == "setbg":
            return f"Set BG type={act.get('type', '?')}"
        if t == "setmusic":
            return f"Set music ID {act.get('id', '?')}"
        if t == "teleport":
            return f"Teleport to ({act.get('x', '?')},{act.get('y', '?')})"
        if t == "killallnpcs":
            return "Kill all NPCs"
        if t == "removelayer":
            return f"Remove layer '{act.get('layer', '?')}'"
        if t == "changesection":
            return f"Change to section {act.get('id', '?')}"
        return t


WARP_STYLES = ["Pipe", "Door", "Portal"]
WARP_TYPES = ["Instant", "Pipe", "Door"]
WARP_DIRS = ["Up", "Down", "Left", "Right"]


class WarpDialog(Dialog):
    def __init__(self, screen, level):
        super().__init__(screen, "Warp Editor", 640, 440)
        self.level = level
        self.section = level.current_section()
        self.warps = self.section.warps
        self.sel = 0 if self.warps else -1
        self.scroll = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
            for i, w in enumerate(self.warps):
                r = pygame.Rect(list_area.x, list_area.y + (i - self.scroll) * 20, 196, 18)
                if r.collidepoint(event.pos) and list_area.y <= r.y < list_area.bottom:
                    self.sel = i
            add_r = pygame.Rect(self.x + 10, self.y + self.h - 42, 70, 26)
            del_r = pygame.Rect(self.x + 86, self.y + self.h - 42, 70, 26)
            ok_r = pygame.Rect(self.x + self.w - 90, self.y + self.h - 42, 70, 26)
            if add_r.collidepoint(event.pos):
                nid = max((w.id for w in self.warps), default=-1) + 1
                self.warps.append(Warp(id=nid))
                self.sel = len(self.warps) - 1
            if del_r.collidepoint(event.pos) and 0 <= self.sel < len(self.warps):
                self.warps.pop(self.sel)
                self.sel = min(self.sel, len(self.warps) - 1)
            if ok_r.collidepoint(event.pos):
                self.done = True
            if 0 <= self.sel < len(self.warps):
                w = self.warps[self.sel]
                fields = [
                    (self.y + 36, "Entrance X:", "ix"), (self.y + 58, "Entrance Y:", "iy"),
                    (self.y + 80, "Exit X:", "ox"), (self.y + 102, "Exit Y:", "oy"),
                    (self.y + 124, "Exit W:", "ow"), (self.y + 146, "Exit H:", "oh"),
                    (self.y + 168, "Type:", "warp_type"), (self.y + 190, "In Dir:", "idirect"),
                    (self.y + 212, "Out Dir:", "odirect"), (self.y + 234, "Style:", "style"),
                    (self.y + 256, "Layer:", "layer"), (self.y + 278, "In Layer:", "in_layer"),
                    (self.y + 300, "Out Layer:", "out_layer"),
                ]
                for fy, label, key in fields:
                    val_r = pygame.Rect(self.x + 320, self.y + fy - 2, 300, 18)
                    if val_r.collidepoint(event.pos):
                        cur = str(getattr(w, key, ""))
                        res = InputDialog(self.screen, label, label, cur).run()
                        if res is not None:
                            try:
                                setattr(w, key, int(res))
                            except ValueError:
                                setattr(w, key, res)
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
            if list_area.collidepoint(mx, my):
                self.scroll = max(0, min(self.scroll - event.y, max(0, len(self.warps) - 16)))

    def draw(self):
        self._draw_frame()
        draw_text(self.screen, "Warps:", (self.x + 14, self.y + 26), SYS_TEXT, FONT_SMALL)
        list_area = pygame.Rect(self.x + 10, self.y + 32, 200, 340)
        pygame.draw.rect(self.screen, SYS_WINDOW, list_area)
        draw_edge(self.screen, list_area, raised=False)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(list_area)
        for i, w in enumerate(self.warps):
            r = pygame.Rect(list_area.x, list_area.y + (i - self.scroll) * 20, 196, 18)
            if r.bottom < list_area.top or r.top > list_area.bottom:
                continue
            bg = SYS_HIGHLIGHT if i == self.sel else SYS_WINDOW
            pygame.draw.rect(self.screen, bg, r)
            col = WHITE if i == self.sel else SYS_TEXT
            draw_text(self.screen, f"[{w.id}] ({w.ix},{w.iy})->({w.ox},{w.oy})", (r.x + 3, r.y + 2), col, FONT_SMALL)
        self.screen.set_clip(old_clip)
        if 0 <= self.sel < len(self.warps):
            w = self.warps[self.sel]
            fields = [
                (36, "Entrance X:", "ix"), (58, "Entrance Y:", "iy"),
                (80, "Exit X:", "ox"), (102, "Exit Y:", "oy"),
                (124, "Exit W:", "ow"), (146, "Exit H:", "oh"),
                (168, "Type (0=Inst,1=Pipe,2=Door):", "warp_type"),
                (190, "In Dir (0=Up,1=Dn,2=L,3=R):", "idirect"),
                (212, "Out Dir:", "odirect"), (234, "Style:", "style"),
                (256, "Layer:", "layer"), (278, "In Layer:", "in_layer"),
                (300, "Out Layer:", "out_layer"),
            ]
            for fy, label, key in fields:
                draw_text(self.screen, label, (self.x + 220, self.y + fy), SYS_TEXT, FONT_SMALL)
                val_r = pygame.Rect(self.x + 320, self.y + fy - 2, 300, 18)
                pygame.draw.rect(self.screen, SYS_WINDOW, val_r)
                draw_edge(self.screen, val_r, raised=False)
                draw_text(self.screen, str(getattr(w, key, "")), (val_r.x + 3, val_r.y + 2), SYS_TEXT, FONT_SMALL)
        for lbl, bx, bw in [("Add Warp", 10, 70), ("Del Warp", 86, 70)]:
            r = pygame.Rect(self.x + bx, self.y + self.h - 42, bw, 26)
            pygame.draw.rect(self.screen, SYS_BTN_FACE, r)
            draw_edge(self.screen, r, raised=True)
            draw_text(self.screen, lbl, r.center, SYS_TEXT, FONT_SMALL, True)
        ok_r = pygame.Rect(self.x + self.w - 90, self.y + self.h - 42, 70, 26)
        pygame.draw.rect(self.screen, SYS_BTN_FACE, ok_r)
        draw_edge(self.screen, ok_r, raised=True)
        draw_text(self.screen, "Close", ok_r.center, SYS_TEXT, FONT_SMALL, True)


# -------------------------
# DATA STRUCTURES (SMBX / LVLX level model)
# -------------------------
class Event:
    def __init__(self, name="New Event", trigger="0", actions=None, eid=0, msg=""):
        self.name = name
        self.trigger = trigger
        self.actions = actions or []
        self.id = eid
        self.msg = msg


class PhysEnvZone:
    def __init__(self, x=0, y=0, w=800, h=100, env_type=0, zid=0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.env_type = env_type  # 0=water, 1=quicksand, 2=custom
        self.id = zid


class Warp:
    def __init__(self, id=0, ix=0, iy=0, ox=0, oy=0, ow=GRID_SIZE, oh=GRID_SIZE,
                 warp_type=0, idirect=0, odirect=0, style=0,
                 layer="Default", in_layer="Default", out_layer="Default",
                 event_enter="-1", event_exit="-1",
                 origin_section=0, dest_section=0):
        self.id = id
        self.ix = ix
        self.iy = iy
        self.ox = ox
        self.oy = oy
        self.ow = ow
        self.oh = oh
        self.warp_type = warp_type
        self.idirect = idirect
        self.odirect = odirect
        self.style = style
        self.layer = layer
        self.in_layer = in_layer
        self.out_layer = out_layer
        self.event_enter = event_enter
        self.event_exit = event_exit
        self.origin_section = origin_section
        self.dest_section = dest_section


class CharacterStart:
    def __init__(self, cid=0, state=0, x=0, y=0, w=0, h=0, cx=0, cy=0):
        self.id = cid
        self.state = state
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.cx = cx
        self.cy = cy


class GameObject(pygame.sprite.Sprite):
    def __init__(self, x, y, obj_type, layer=0, event_id=-1, flags=0):
        super().__init__()
        self.rect = pygame.Rect(x, y, GRID_SIZE, GRID_SIZE)
        self.layer = layer
        self.obj_type = obj_type
        self.event_id = event_id
        self.flags = flags


class Tile(GameObject):
    def __init__(self, x, y, tile_type, layer=0, event_id=-1, flags=0,
                 event_hit=-1, event_layer_empty=-1, contents=0,
                 contained_npc_id=0, special_data=0, width=GRID_SIZE, height=GRID_SIZE):
        super().__init__(x, y, tile_type, layer, event_id, flags)
        self.tile_type = tile_type
        self.is_solid = self._is_solid()
        self.width = width
        self.height = height
        self.event_hit = event_hit
        self.event_layer_empty = event_layer_empty
        self.contents = contents
        self.contained_npc_id = contained_npc_id
        self.special_data = special_data
        self.update_image()

    def _is_solid(self):
        return self.tile_type not in ['coin', 'water', 'lava']

    def update_image(self):
        w = GRID_SIZE
        h = GRID_SIZE
        color = get_theme_color(self.tile_type)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if self.tile_type == 'ground':
            surf.fill(color)
            pygame.draw.rect(surf, (0, 100, 0), (0, 0, w, 4))
            pygame.draw.rect(surf, (0, 80, 0), (0, 2, w, 2))
            for _ in range(12):
                pygame.draw.circle(surf, (80, 60, 30), (random.randint(4, w - 4), random.randint(8, h - 4)), 1)
        elif self.tile_type == 'grass':
            surf.fill(color)
            for i in range(0, w, 4):
                pygame.draw.line(surf, (0, 120, 0), (i + 2, 0), (i, 8), 2)
        elif self.tile_type == 'brick':
            surf.fill(color)
            for i in range(0, w, 8):
                for row in range(4):
                    pygame.draw.rect(surf, (130, 60, 20), (i + 2, 2 + row * 8, 4, 6))
            for row in range(1, 4):
                pygame.draw.line(surf, (100, 50, 20), (0, row * 8), (w, row * 8))
            for x in range(8, w, 16):
                pygame.draw.line(surf, (100, 50, 20), (x, 0), (x, h))
        elif self.tile_type == 'question':
            surf.fill((255, 200, 0))
            pygame.draw.rect(surf, (180, 120, 0), (2, 2, w - 4, h - 4), 2)
            draw_text(surf, "?", (w // 2, h // 2), BLACK, FONT_SMALL, True)
        elif self.tile_type == 'pipe_vertical':
            surf.fill((0, 160, 0))
            pygame.draw.rect(surf, (0, 200, 0), (4, 0, w - 8, h))
            pygame.draw.rect(surf, (0, 220, 0), (0, 0, w, 8))
        elif self.tile_type == 'pipe_horizontal':
            surf.fill((0, 160, 0))
            pygame.draw.rect(surf, (0, 200, 0), (0, 4, w, h - 8))
            pygame.draw.rect(surf, (0, 220, 0), (0, 0, 8, h))
        elif self.tile_type == 'coin':
            surf.fill((0, 0, 0, 0))
            pygame.draw.circle(surf, YELLOW, (w // 2, h // 2), w // 3)
            pygame.draw.circle(surf, (255, 200, 0), (w // 2, h // 2), w // 3 - 2)
        elif self.tile_type == 'slope_left':
            pts = [(0, 0), (w, 0), (0, h)]
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, BLACK, pts, 1)
        elif self.tile_type == 'slope_right':
            pts = [(0, 0), (w, 0), (w, h)]
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, BLACK, pts, 1)
        elif self.tile_type == 'water':
            surf.fill((0, 100, 255, 128))
            for i in range(0, w, 4):
                pygame.draw.arc(surf, (100, 150, 255), (i, h // 2, 6, 4), 0, math.pi, 1)
        elif self.tile_type == 'lava':
            surf.fill((255, 80, 0, 128))
            for i in range(0, w, 8):
                pygame.draw.line(surf, (255, 200, 0), (i, h - 4), (i + 4, h - 8), 2)
        elif self.tile_type == 'semisolid':
            surf.fill(color)
            for yy in range(0, h, 4):
                for xx in range(0, w, 8):
                    pygame.draw.rect(surf, (255, 255, 200, 100), (xx, yy, 4, 2))
        else:
            surf.fill(color)
        pygame.draw.rect(surf, (0, 0, 0, 60), surf.get_rect(), 1)
        self.image = surf


class BGO(GameObject):
    def __init__(self, x, y, bgo_type, layer=0, event_id=-1, flags=0,
                 z_layer="Default", sx=64, sy=64):
        super().__init__(x, y, bgo_type, layer, event_id, flags)
        self.bgo_type = bgo_type
        self.z_layer = z_layer
        self.sx = sx
        self.sy = sy
        self.update_image()

    def update_image(self):
        w = GRID_SIZE
        h = GRID_SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        color = get_theme_color('bgo_' + self.bgo_type) if not self.bgo_type.startswith('bgo_') else get_theme_color(self.bgo_type)
        if self.bgo_type == 'cloud':
            pygame.draw.ellipse(surf, color, (4, 8, w - 8, h - 12))
            pygame.draw.ellipse(surf, color, (0, 12, 16, 16))
            pygame.draw.ellipse(surf, color, (w - 16, 12, 16, 16))
        elif self.bgo_type == 'bush':
            pygame.draw.ellipse(surf, color, (4, 8, w - 8, h - 12))
        elif self.bgo_type == 'hill':
            pygame.draw.polygon(surf, color, [(0, h - 4), (w // 2, 4), (w, h - 4)])
        elif self.bgo_type == 'tree':
            pygame.draw.rect(surf, (100, 60, 20), (w // 2 - 4, h - 8, 8, 8))
            pygame.draw.circle(surf, color, (w // 2, h - 12), 12)
        else:
            pygame.draw.rect(surf, color, (4, 4, w - 8, h - 8))
        self.image = surf


class NPC(GameObject):
    def __init__(self, x, y, npc_type, layer=0, event_id=-1, flags=0,
                 direction=1, special_data=0, npc_type_mode=0,
                 generic_animation=0, face_direction=1,
                 no_fireball_kill=0, no_iceball_kill=0, no_yoshi_eat=0,
                 is_star=0, is_throwable=0, is_grabable=0, is_bombable=0,
                 is_shell_surfer=0, is_not_moving=0, is_stuck_debris=0,
                 speed=1.0, can_be_eaten_by_plant=0, enable_particle_effect=0,
                 is_base_plate=0, is_tangible=1, attach_surface=0,
                 auto_destroy_timer=-1, event_die=-1, event_talk=-1,
                 event_empty_layer=-1):
        super().__init__(x, y, npc_type, layer, event_id, flags)
        self.npc_type = npc_type
        self.direction = direction
        self.special_data = special_data
        self.npc_type_mode = npc_type_mode
        self.generic_animation = generic_animation
        self.face_direction = face_direction
        self.no_fireball_kill = no_fireball_kill
        self.no_iceball_kill = no_iceball_kill
        self.no_yoshi_eat = no_yoshi_eat
        self.is_star = is_star
        self.is_throwable = is_throwable
        self.is_grabable = is_grabable
        self.is_bombable = is_bombable
        self.is_shell_surfer = is_shell_surfer
        self.is_not_moving = is_not_moving
        self.is_stuck_debris = is_stuck_debris
        self.speed = speed
        self.can_be_eaten_by_plant = can_be_eaten_by_plant
        self.enable_particle_effect = enable_particle_effect
        self.is_base_plate = is_base_plate
        self.is_tangible = is_tangible
        self.attach_surface = attach_surface
        self.auto_destroy_timer = auto_destroy_timer
        self.event_die = event_die
        self.event_talk = event_talk
        self.event_empty_layer = event_empty_layer
        self.velocity = pygame.Vector2(direction * (0 if is_not_moving else 1), 0)
        self.state = 'normal'
        self.frame = 0
        self.update_image()

    def update_image(self):
        w = GRID_SIZE
        h = GRID_SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        color = get_theme_color(self.npc_type)
        if self.npc_type == 'goomba':
            pygame.draw.ellipse(surf, color, (4, 4, w - 8, h - 6))
            pygame.draw.rect(surf, (100, 50, 0), (4, h - 8, w - 8, 4))
            pygame.draw.circle(surf, WHITE, (w // 3, h // 3), 4)
            pygame.draw.circle(surf, WHITE, (w - w // 3, h // 3), 4)
            pygame.draw.circle(surf, BLACK, (w // 3, h // 3), 2)
            pygame.draw.circle(surf, BLACK, (w - w // 3, h // 3), 2)
        elif self.npc_type.startswith('koopa'):
            pygame.draw.rect(surf, color, (4, 4, w - 8, h - 12))
            pygame.draw.circle(surf, color, (w // 2, 8), 8)
            pygame.draw.circle(surf, BLACK, (w // 3, 10), 2)
            pygame.draw.circle(surf, BLACK, (w - w // 3, 10), 2)
        elif self.npc_type == 'mushroom':
            pygame.draw.circle(surf, (255, 0, 0), (w // 2, h // 3), w // 3)
            pygame.draw.rect(surf, (200, 150, 100), (w // 2 - 4, h // 2, 8, h // 2))
        elif self.npc_type == 'flower':
            pygame.draw.circle(surf, (255, 0, 0), (w // 2, h // 2), 10)
            pygame.draw.circle(surf, (255, 255, 0), (w // 2, h // 2 - 2), 4)
            pygame.draw.polygon(surf, GREEN, [(w // 2 - 8, h // 2 + 4), (w // 2, h - 8), (w // 2 + 8, h // 2 + 4)])
        elif self.npc_type == 'star':
            points = []
            for i in range(10):
                angle = i * math.pi * 2 / 10 - math.pi / 2
                r = w // 2 if i % 2 == 0 else w // 3
                points.append((w // 2 + r * math.cos(angle), h // 2 + r * math.sin(angle)))
            pygame.draw.polygon(surf, YELLOW, points)
        else:
            pygame.draw.rect(surf, color, (4, 4, w - 8, h - 8))
            pygame.draw.circle(surf, BLACK, (w // 2, 8), 2)
        self.image = surf

    def update(self, solid_tiles, player, events):
        if not self._is_flying():
            self.velocity.y += GRAVITY
            self.velocity.y = min(self.velocity.y, TERMINAL_VELOCITY)
        self.rect.x += self.velocity.x
        self._collide(solid_tiles, 'x', events)
        self.rect.y += self.velocity.y
        self._collide(solid_tiles, 'y', events)

    def _is_flying(self):
        return self.npc_type in ['lakitu', 'podoboo', 'piranha_fire']

    def _collide(self, tiles, axis, events):
        for t in tiles:
            if self.rect.colliderect(t.rect):
                if axis == 'x':
                    if self.velocity.x > 0:
                        self.rect.right = t.rect.left
                    else:
                        self.rect.left = t.rect.right
                    self.velocity.x *= -1
                elif axis == 'y':
                    if self.velocity.y > 0:
                        self.rect.bottom = t.rect.top
                    else:
                        self.rect.top = t.rect.bottom
                    self.velocity.y = 0
                if t.tile_type == 'lava':
                    self.kill()
                elif t.tile_type == 'water':
                    self.velocity.y *= 0.5


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.rect = pygame.Rect(x, y, GRID_SIZE, GRID_SIZE)
        self.direction = 1
        self.velocity = pygame.Vector2(0, 0)
        self.on_ground = False
        self.powerup_state = 0
        self.invincible = 0
        self.coins = 0
        self.score = 0
        self.jump_held = False
        self.variable_jump_timer = 0
        self.level_start = (x, y)
        self.update_image()

    def update_image(self):
        w = GRID_SIZE
        h = GRID_SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        skin = (248, 184, 120)
        red = (229, 37, 37)
        blue = (44, 44, 140)
        brown = (140, 90, 44)
        black = (0, 0, 0)
        white = (255, 255, 255)
        pygame.draw.rect(surf, blue, (10, 16, 12, 12))
        pygame.draw.rect(surf, red, (10, 12, 12, 4))
        pygame.draw.ellipse(surf, skin, (10, 4, 12, 12))
        pygame.draw.rect(surf, red, (8, 2, 16, 6))
        pygame.draw.line(surf, black, (8, 8), (24, 8), 1)
        pygame.draw.circle(surf, white, (14, 10), 2)
        pygame.draw.circle(surf, white, (18, 10), 2)
        pygame.draw.circle(surf, black, (14, 10), 1)
        pygame.draw.circle(surf, black, (18, 10), 1)
        pygame.draw.line(surf, brown, (12, 12), (20, 12), 2)
        pygame.draw.rect(surf, brown, (10, 28, 5, 4))
        pygame.draw.rect(surf, brown, (17, 28, 5, 4))
        pygame.draw.line(surf, blue, (12, 12), (12, 16), 2)
        pygame.draw.line(surf, blue, (20, 12), (20, 16), 2)
        if self.direction < 0:
            surf = pygame.transform.flip(surf, True, False)
        self.image = surf

    def update(self, solid_tiles, npc_group, events, coin_tiles=None, sfx_cb=None):
        keys = pygame.key.get_pressed()
        self.velocity.x = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.velocity.x = -MOVE_SPEED
            self.direction = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.velocity.x = MOVE_SPEED
            self.direction = 1
        if keys[pygame.K_SPACE]:
            if self.on_ground and not self.jump_held:
                self.velocity.y = JUMP_STRENGTH
                self.on_ground = False
                self.jump_held = True
                self.variable_jump_timer = 8
                if sfx_cb:
                    sfx_cb("jump")
            elif self.variable_jump_timer > 0 and self.velocity.y < 0:
                self.velocity.y -= 0.5
                self.variable_jump_timer -= 1
        else:
            self.jump_held = False
            self.variable_jump_timer = 0
        self.velocity.y = min(self.velocity.y + GRAVITY, TERMINAL_VELOCITY)
        self.rect.x += self.velocity.x
        self._collide(solid_tiles, 'x', events, sfx_cb)
        self.rect.y += self.velocity.y
        self.on_ground = False
        self._collide(solid_tiles, 'y', events, sfx_cb)
        if coin_tiles:
            for t in coin_tiles:
                if t.alive() and self.rect.colliderect(t.rect):
                    t.kill()
                    self.coins += 1
                    self.score += 10
                    if sfx_cb:
                        sfx_cb("coin")
        for npc in pygame.sprite.spritecollide(self, npc_group, False):
            if not npc.is_tangible:
                continue
            if self.velocity.y > 0 and self.rect.bottom <= npc.rect.centery:
                npc.kill()
                self.velocity.y = JUMP_STRENGTH * 0.7
                self.score += 100
                if sfx_cb:
                    sfx_cb("stomp")
            elif self.invincible <= 0:
                if self.powerup_state > 0:
                    self.powerup_state = 0
                    self.invincible = 120
                    self.update_image()
                    if sfx_cb:
                        sfx_cb("hurt")
                else:
                    self.rect.topleft = self.level_start
                    self.score = max(0, self.score - 50)
                    self.coins = 0
                    self.invincible = 60
                    if sfx_cb:
                        sfx_cb("die")
        if self.invincible > 0:
            self.invincible -= 1

    def _collide(self, tiles, axis, events, sfx_cb=None):
        for t in tiles:
            if self.rect.colliderect(t.rect):
                if t.tile_type == 'lava':
                    self.rect.topleft = self.level_start
                    self.score = max(0, self.score - 50)
                    self.coins = 0
                    self.invincible = 60
                    if sfx_cb:
                        sfx_cb("die")
                    return
                if t.tile_type == 'water':
                    self.velocity.y *= 0.5
                if t.tile_type == 'pswitch':
                    t.kill()
                if t.tile_type == 'slope_left' and axis == 'y' and self.velocity.y >= 0:
                    self.rect.bottom = t.rect.top + (self.rect.right - t.rect.left)
                    self.on_ground = True
                    self.velocity.y = 0
                    continue
                if t.tile_type == 'slope_right' and axis == 'y' and self.velocity.y >= 0:
                    self.rect.bottom = t.rect.top + (t.rect.right - self.rect.left)
                    self.on_ground = True
                    self.velocity.y = 0
                    continue
                if axis == 'x':
                    if self.velocity.x > 0:
                        self.rect.right = t.rect.left
                    else:
                        self.rect.left = t.rect.right
                    self.velocity.x = 0
                elif axis == 'y':
                    if self.velocity.y > 0:
                        self.rect.bottom = t.rect.top
                        self.on_ground = True
                    else:
                        self.rect.top = t.rect.bottom
                    self.velocity.y = 0

    def draw(self, surf, camera_offset):
        if self.invincible > 0 and (self.invincible // 5) % 2 == 0:
            return
        surf.blit(self.image, self.rect.move(camera_offset))


class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width, self.height = width, height
        self.zoom = 1.0

    def update(self, target):
        x = min(0, max(-(self.width - CANVAS_WIDTH / self.zoom),
                        -target.rect.centerx + (CANVAS_WIDTH // 2) / self.zoom))
        y = min(0, max(-(self.height - CANVAS_HEIGHT / self.zoom),
                        -target.rect.centery + (CANVAS_HEIGHT // 2) / self.zoom))
        self.camera = pygame.Rect(x, y, self.width, self.height)

    def move(self, dx, dy):
        self.camera.x = max(-(self.width - CANVAS_WIDTH / self.zoom), min(0, self.camera.x + dx / self.zoom))
        self.camera.y = max(-(self.height - CANVAS_HEIGHT / self.zoom), min(0, self.camera.y + dy / self.zoom))


class Layer:
    def __init__(self, name="Default", visible=True, locked=False, hidden=0):
        self.name = name
        self.visible = visible
        self.locked = locked
        self.hidden = hidden
        self.tiles = pygame.sprite.Group()
        self.bgos = pygame.sprite.Group()
        self.npcs = pygame.sprite.Group()
        self.tile_map = {}

    def add_tile(self, tile):
        self.tiles.add(tile)
        self.tile_map[(tile.rect.x, tile.rect.y)] = tile

    def remove_tile(self, tile):
        self.tiles.remove(tile)
        self.tile_map.pop((tile.rect.x, tile.rect.y), None)


class Section:
    def __init__(self, width=100, height=30):
        self.width = width * GRID_SIZE
        self.height = height * GRID_SIZE
        self.size_left = 0
        self.size_top = 0
        self.layers = [Layer("Default"), Layer("Destroyed Blocks"), Layer("Spawned NPCs")]
        self.current_layer_idx = 0
        self.bg_color = (92, 148, 252)
        self.bg_type = 0
        self.music = 1
        self.music_file = ""
        self.events = []
        self.warps = []
        self.phys_env_zones = []
        self.background_image = None
        self.start_x = 100
        self.start_y = 500
        self.player_direction = 0
        self.player_effect = 0
        self.rewarp_x = -1
        self.rewarp_y = -1
        self.warp_entrance = 0
        self.warp_exit = 0
        self.locked = False
        self.z_layers = [
            {"name": "Background", "priority": 0},
            {"name": "Default", "priority": 100},
            {"name": "Foreground", "priority": 200},
        ]

    def current_layer(self):
        return self.layers[self.current_layer_idx]

    def layer_by_name(self, name):
        for l in self.layers:
            if l.name == name:
                return l
        return self.layers[0]

    def get_solid_tiles(self):
        return [t for layer in self.layers if layer.visible for t in layer.tiles if t.is_solid]


class Level:
    def __init__(self):
        self.sections = [Section()]
        self.current_section_idx = 0
        self.name = "Untitled"
        self.author = "Unknown"
        self.description = ""
        self.license = ""
        self.website = ""
        self.version = "1.0"
        self.no_background = False
        self.time_limit = 400
        self.level_id = 0
        self.stars = 0
        self.initial_lives = 3
        self.initial_coins = 0
        self.max_coins = 0
        self.max_stars_total = 0
        self.max_stars_world = 0
        self.max_stars_level = 0
        self.no_credit = False
        self.restart_level = False
        self.system_id = 0
        self.hub_world_x = 0
        self.hub_world_y = 0
        self.hub_world_level = ""
        self.hub_world_episode = ""
        self.character_starts = [CharacterStart(i) for i in range(5)]
        self.stars_list = []
        self.generator_must_haves = []
        self.physics = {}
        self.luna_config = {}

    def current_section(self):
        return self.sections[self.current_section_idx]

    def current_layer(self):
        return self.current_section().current_layer()

    def collect_all_layer_names(self):
        names = set()
        for sec in self.sections:
            for layer in sec.layers:
                names.add(layer.name)
        return sorted(names)


# -------------------------
# FILE I/O (SMBX .lvl, .38a, .lvlx)
# -------------------------
def read_lvl(filename):
    level = Level()
    try:
        with open(filename, 'rb') as f:
            magic = f.read(4)
            if magic != b'LVL\x1a':
                print("Not a valid SMBX level file")
                return level
            version = struct.unpack('<I', f.read(4))[0]
            level.name = f.read(32).decode('utf-8', errors='ignore').strip('\x00')
            level.author = f.read(32).decode('utf-8', errors='ignore').strip('\x00')
            level.time_limit = struct.unpack('<I', f.read(4))[0]
            level.stars = struct.unpack('<I', f.read(4))[0]
            flags = struct.unpack('<I', f.read(4))[0]
            level.no_background = bool(flags & 1)
            f.read(128 - 4 - 4 - 32 - 32 - 4 - 4 - 4)

            num_sections = struct.unpack('<I', f.read(4))[0]
            level.sections = []
            for s in range(num_sections):
                section = Section()
                section.width = struct.unpack('<I', f.read(4))[0]
                section.height = struct.unpack('<I', f.read(4))[0]
                bg_r, bg_g, bg_b = struct.unpack('<BBB', f.read(3))
                section.bg_color = (bg_r, bg_g, bg_b)
                f.read(1)  # padding
                section.start_x = struct.unpack('<I', f.read(4))[0]
                section.start_y = struct.unpack('<I', f.read(4))[0]
                section.music = struct.unpack('<I', f.read(4))[0]

                num_blocks = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_blocks):
                    x, y, type_id, layer, event_id, flags = struct.unpack('<IIIIII', f.read(24))
                    if type_id in TILE_ID_TO_NAME:
                        tile = Tile(x, y, TILE_ID_TO_NAME[type_id], layer, event_id, flags)
                        while len(section.layers) <= layer:
                            section.layers.append(Layer(f"Layer {len(section.layers)+1}"))
                        section.layers[layer].add_tile(tile)

                num_bgos = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_bgos):
                    x, y, type_id, layer, flags = struct.unpack('<IIIII', f.read(20))
                    if type_id in BGO_ID_TO_NAME:
                        bgo = BGO(x, y, BGO_ID_TO_NAME[type_id], layer, flags=flags)
                        while len(section.layers) <= layer:
                            section.layers.append(Layer(f"Layer {len(section.layers)+1}"))
                        section.layers[layer].bgos.add(bgo)

                num_npcs = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_npcs):
                    x, y, type_id, layer, event_id, flags, direction, special = struct.unpack('<IIIIIIII', f.read(32))
                    if type_id in NPC_ID_TO_NAME:
                        npc = NPC(x, y, NPC_ID_TO_NAME[type_id], layer, event_id, flags,
                                  direction=1 if direction else -1, special_data=special)
                        while len(section.layers) <= layer:
                            section.layers.append(Layer(f"Layer {len(section.layers)+1}"))
                        section.layers[layer].npcs.add(npc)

                num_warps = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_warps):
                    # Read warp data (64 bytes) - we skip for now
                    f.read(64)

                num_events = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_events):
                    name_len = struct.unpack('<B', f.read(1))[0]
                    name = f.read(name_len).decode('utf-8')
                    trigger = struct.unpack('<I', f.read(4))[0]
                    action_count = struct.unpack('<I', f.read(4))[0]
                    for _ in range(action_count):
                        f.read(12)
                    section.events.append(Event(name, str(trigger), [], eid=len(section.events)))

                level.sections.append(section)
    except Exception as e:
        print("Load error:", e)
    return level


def write_lvl(filename, level):
    with open(filename, 'wb') as f:
        f.write(b'LVL\x1a')
        f.write(struct.pack('<I', 1))
        name_bytes = level.name.encode('utf-8')[:31] + b'\x00'
        f.write(name_bytes.ljust(32, b'\x00'))
        author_bytes = level.author.encode('utf-8')[:31] + b'\x00'
        f.write(author_bytes.ljust(32, b'\x00'))
        f.write(struct.pack('<I', level.time_limit))
        f.write(struct.pack('<I', level.stars))
        flags = (1 if level.no_background else 0)
        f.write(struct.pack('<I', flags))
        f.write(b'\x00' * (128 - f.tell()))

        f.write(struct.pack('<I', len(level.sections)))
        for section in level.sections:
            f.write(struct.pack('<I', section.width))
            f.write(struct.pack('<I', section.height))
            f.write(struct.pack('<BBB', *section.bg_color[:3]))
            f.write(b'\x00')
            f.write(struct.pack('<I', section.start_x))
            f.write(struct.pack('<I', section.start_y))
            f.write(struct.pack('<I', section.music))

            blocks = []
            for li, layer in enumerate(section.layers):
                for t in layer.tiles:
                    type_id = TILE_SMBX_IDS.get(t.tile_type, 1)
                    event_id = t.event_id if hasattr(t, 'event_id') else -1
                    flags = t.flags if hasattr(t, 'flags') else 0
                    blocks.append((t.rect.x, t.rect.y, type_id, li, event_id, flags))
            f.write(struct.pack('<I', len(blocks)))
            for b in blocks:
                f.write(struct.pack('<IIIIII', *b))

            bgos = []
            for li, layer in enumerate(section.layers):
                for b in layer.bgos:
                    type_id = BGO_SMBX_IDS.get(b.bgo_type, 5)
                    flags = b.flags if hasattr(b, 'flags') else 0
                    bgos.append((b.rect.x, b.rect.y, type_id, li, flags))
            f.write(struct.pack('<I', len(bgos)))
            for bg in bgos:
                f.write(struct.pack('<IIIII', *bg))

            npcs = []
            for li, layer in enumerate(section.layers):
                for n in layer.npcs:
                    type_id = NPC_SMBX_IDS.get(n.npc_type, 1)
                    event_id = n.event_id if hasattr(n, 'event_id') else -1
                    flags = n.flags if hasattr(n, 'flags') else 0
                    direction = 1 if n.direction > 0 else 0
                    special = n.special_data if hasattr(n, 'special_data') else 0
                    npcs.append((n.rect.x, n.rect.y, type_id, li, event_id, flags, direction, special))
            f.write(struct.pack('<I', len(npcs)))
            for n in npcs:
                f.write(struct.pack('<IIIIIIII', *n))

            f.write(struct.pack('<I', len(section.warps)))
            for warp in section.warps:
                f.write(b'\x00' * 64)

            f.write(struct.pack('<I', len(section.events)))
            for event in section.events:
                name_bytes = event.name.encode('utf-8')
                f.write(struct.pack('<B', len(name_bytes)))
                f.write(name_bytes)
                f.write(struct.pack('<I', 0))
                f.write(struct.pack('<I', 0))


def read_38a(filename):
    temp_dir = tempfile.mkdtemp(prefix="smbx38a_")
    try:
        with zipfile.ZipFile(filename, "r") as zf:
            zf.extractall(temp_dir)

        level_path = os.path.join(temp_dir, "level.lvl")
        if not os.path.exists(level_path):
            for root, _dirs, files in os.walk(temp_dir):
                if "level.lvl" in files:
                    level_path = os.path.join(root, "level.lvl")
                    break
            else:
                raise FileNotFoundError("No level.lvl found inside .38a archive")

        level = read_lvl(level_path)
        level.luna_config = {}
        base = os.path.dirname(level_path)

        for key, fname in [
            ("layers", "layers.txt"),
            ("events", "events.txt"),
            ("lunadll", "lunadll.txt"),
            ("warps", "warp.txt"),
            ("sounds", "sound.txt"),
            ("settings", "settings.txt"),
        ]:
            p = os.path.join(base, fname)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="replace") as fp:
                    level.luna_config[key] = fp.read()

        known = {
            "level.lvl",
            "layers.txt",
            "events.txt",
            "lunadll.txt",
            "warp.txt",
            "sound.txt",
            "settings.txt",
        }
        other = {}
        for walk_root, _dirs, files in os.walk(temp_dir):
            for fn in files:
                if fn in known:
                    continue
                full = os.path.join(walk_root, fn)
                arcname = os.path.relpath(full, temp_dir).replace("\\", "/")
                with open(full, "rb") as fp:
                    other[arcname] = fp.read()
        level.luna_config["other_files"] = other
        return level
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def write_38a(filename, level):
    temp_dir = tempfile.mkdtemp(prefix="smbx38a_")
    try:
        write_lvl(os.path.join(temp_dir, "level.lvl"), level)
        cfg = getattr(level, "luna_config", {}) or {}
        for key, fname in [
            ("layers", "layers.txt"),
            ("events", "events.txt"),
            ("lunadll", "lunadll.txt"),
            ("warps", "warp.txt"),
            ("sounds", "sound.txt"),
            ("settings", "settings.txt"),
        ]:
            if key in cfg:
                with open(os.path.join(temp_dir, fname), "w", encoding="utf-8") as fp:
                    fp.write(cfg[key])

        for relpath, content in cfg.get("other_files", {}).items():
            full = os.path.join(temp_dir, relpath.replace("\\", "/"))
            parent = os.path.dirname(full)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(full, "wb") as fp:
                fp.write(content)

        with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as zf:
            for walk_root, _dirs, files in os.walk(temp_dir):
                for fn in files:
                    full = os.path.join(walk_root, fn)
                    zf.write(full, os.path.relpath(full, temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _lvlx_int(el, attr, default=0):
    try:
        return int(el.get(attr, default))
    except (TypeError, ValueError):
        return default


def read_lvlx(filename):
    level = Level()
    try:
        tree = ET.parse(filename)
        root = tree.getroot()

        head = root.find("head")
        if head is not None:
            t = head.findtext("title")
            if t is not None:
                level.name = t
            a = head.findtext("author")
            if a is not None:
                level.author = a
            timer_el = head.find("timer")
            level.time_limit = _lvlx_int(timer_el or ET.Element("x"), "value", 300)
            stars_el = head.find("stars")
            level.stars = _lvlx_int(stars_el or ET.Element("x"), "value", 0)

        level.sections = []
        for sec_el in root.findall("section"):
            sec = Section()
            sec.width = _lvlx_int(sec_el, "size_right", 3200)
            sec.height = _lvlx_int(sec_el, "size_bottom", 960)
            sec.music = _lvlx_int(sec_el, "music_id", 1)
            sec.bg_color = (
                _lvlx_int(sec_el, "bgcolor_r", 92),
                _lvlx_int(sec_el, "bgcolor_g", 148),
                _lvlx_int(sec_el, "bgcolor_b", 252),
            )

            for bl in sec_el.findall("block"):
                tid = _lvlx_int(bl, "id")
                x = (_lvlx_int(bl, "x") // GRID_SIZE) * GRID_SIZE
                y = (_lvlx_int(bl, "y") // GRID_SIZE) * GRID_SIZE
                li = _lvlx_int(bl, "layer", 0)
                eid = _lvlx_int(bl, "event_destroy", -1)
                fl = _lvlx_int(bl, "invisible", 0)
                if tid in TILE_ID_TO_NAME:
                    while len(sec.layers) <= li:
                        sec.layers.append(Layer(f"Layer {len(sec.layers)+1}"))
                    sec.layers[li].add_tile(
                        Tile(x, y, TILE_ID_TO_NAME[tid], layer=li, event_id=eid, flags=fl)
                    )

            for bg in sec_el.findall("bgo"):
                tid = _lvlx_int(bg, "id")
                x = (_lvlx_int(bg, "x") // GRID_SIZE) * GRID_SIZE
                y = (_lvlx_int(bg, "y") // GRID_SIZE) * GRID_SIZE
                li = _lvlx_int(bg, "layer", 0)
                if tid in BGO_ID_TO_NAME:
                    while len(sec.layers) <= li:
                        sec.layers.append(Layer(f"Layer {len(sec.layers)+1}"))
                    sec.layers[li].bgos.add(
                        BGO(x, y, BGO_ID_TO_NAME[tid], layer=li, flags=0)
                    )

            for npc_el in sec_el.findall("npc"):
                tid = _lvlx_int(npc_el, "id")
                x = (_lvlx_int(npc_el, "x") // GRID_SIZE) * GRID_SIZE
                y = (_lvlx_int(npc_el, "y") // GRID_SIZE) * GRID_SIZE
                li = _lvlx_int(npc_el, "layer", 0)
                dr = _lvlx_int(npc_el, "direction", 1)
                sp = _lvlx_int(npc_el, "special_data", 0)
                eid = _lvlx_int(npc_el, "event_activate", -1)
                if tid in NPC_ID_TO_NAME:
                    while len(sec.layers) <= li:
                        sec.layers.append(Layer(f"Layer {len(sec.layers)+1}"))
                    face = 1 if dr > 0 else -1
                    sec.layers[li].npcs.add(
                        NPC(
                            x,
                            y,
                            NPC_ID_TO_NAME[tid],
                            layer=li,
                            event_id=eid,
                            flags=0,
                            direction=face,
                            special_data=sp,
                        )
                    )

            for _door in sec_el.findall("door"):
                sec.warps.append(Warp())

            for ev_el in sec_el.findall("event"):
                name = ev_el.get("name", "")
                trig = _lvlx_int(ev_el, "trigger", 0)
                sec.events.append(Event(name, str(trig), [], eid=len(sec.events)))

            level.sections.append(sec)

        if not level.sections:
            level.sections = [Section()]

        sp_el = root.find(".//player_point")
        if sp_el is not None and level.sections:
            level.sections[0].start_x = _lvlx_int(sp_el, "x", level.sections[0].start_x)
            level.sections[0].start_y = _lvlx_int(sp_el, "y", level.sections[0].start_y)
    except Exception as e:
        print("LVLX load error:", e)
    return level


def write_lvlx(filename, level):
    sx, sy = 100, 500
    if level.sections:
        sx = level.sections[0].start_x
        sy = level.sections[0].start_y

    xml_root = ET.Element("root")
    xml_root.set("type", "LevelFile")
    xml_root.set("fileformat", "LVLX")
    xml_root.set("format_version", "67")

    head = ET.SubElement(xml_root, "head")
    ET.SubElement(head, "title").text = level.name
    ET.SubElement(head, "author").text = level.author
    timer = ET.SubElement(head, "timer")
    timer.set("value", str(level.time_limit))
    stars = ET.SubElement(head, "stars")
    stars.set("value", str(level.stars))

    sp = ET.SubElement(xml_root, "player_point")
    sp.set("x", str(sx))
    sp.set("y", str(sy))

    for si, sec in enumerate(level.sections):
        sec_el = ET.SubElement(xml_root, "section")
        sec_el.set("id", str(si))
        sec_el.set("size_right", str(sec.width))
        sec_el.set("size_bottom", str(sec.height))
        sec_el.set("music_id", str(sec.music))
        sec_el.set("bgcolor_r", str(sec.bg_color[0]))
        sec_el.set("bgcolor_g", str(sec.bg_color[1]))
        sec_el.set("bgcolor_b", str(sec.bg_color[2]))

        for li, layer in enumerate(sec.layers):
            for tile in layer.tiles:
                bl = ET.SubElement(sec_el, "block")
                bl.set("id", str(TILE_SMBX_IDS.get(tile.tile_type, 1)))
                bl.set("x", str(tile.rect.x))
                bl.set("y", str(tile.rect.y))
                bl.set("layer", str(li))
                bl.set("event_destroy", str(tile.event_id))
                bl.set("invisible", str(tile.flags))

            for bgo in layer.bgos:
                bg = ET.SubElement(sec_el, "bgo")
                bg.set("id", str(BGO_SMBX_IDS.get(bgo.bgo_type, 5)))
                bg.set("x", str(bgo.rect.x))
                bg.set("y", str(bgo.rect.y))
                bg.set("layer", str(li))

            for npc in layer.npcs:
                ne = ET.SubElement(sec_el, "npc")
                ne.set("id", str(NPC_SMBX_IDS.get(npc.npc_type, 1)))
                ne.set("x", str(npc.rect.x))
                ne.set("y", str(npc.rect.y))
                ne.set("layer", str(li))
                ne.set("direction", str(npc.direction))
                ne.set("special_data", str(npc.special_data))
                ne.set("event_activate", str(npc.event_id))

        for _warp in sec.warps:
            ET.SubElement(sec_el, "door")

        for ev in sec.events:
            ev_el = ET.SubElement(sec_el, "event")
            ev_el.set("name", ev.name)
            ev_el.set("trigger", str(ev.trigger))

    tree = ET.ElementTree(xml_root)
    ET.indent(tree, space="  ")
    tree.write(filename, encoding="utf-8", xml_declaration=True)


def detect_format(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".38a":
        return "38a"
    if ext == ".lvlx":
        return "lvlx"
    try:
        with open(filename, "rb") as f:
            magic = f.read(4)
            if magic == b"LVL\x1a":
                return "lvl"
            f.seek(0)
            if f.read(2) == b"PK":
                return "38a"
            f.seek(0)
            chunk = f.read(256).lstrip()
            if chunk.startswith(b"<?xml") or chunk.startswith(b"<"):
                return "lvlx"
    except OSError:
        pass
    return "unknown"


def smart_read(filename):
    fmt = detect_format(filename)
    try:
        if fmt == "38a":
            return read_38a(filename)
        if fmt == "lvlx":
            return read_lvlx(filename)
        if fmt == "lvl":
            return read_lvl(filename)
        with open(filename, "rb") as f:
            if f.read(2) == b"PK":
                return read_38a(filename)
    except Exception as e:
        print("Load error:", e)
    return read_lvl(filename)


def smart_write(filename, level):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".lvlx":
        write_lvlx(filename, level)
    elif ext == ".38a":
        write_38a(filename, level)
    else:
        write_lvl(filename, level)


# -------------------------
# MENU SYSTEM
# -------------------------
class MenuItem:
    def __init__(self, label, callback=None, shortcut="", checkable=False, checked=False, separator=False):
        self.label = label
        self.callback = callback
        self.shortcut = shortcut
        self.checkable = checkable
        self.checked = checked
        self.separator = separator
        self.enabled = True


class DropMenu:
    ITEM_H = 18
    PAD = 6
    def __init__(self, items):
        self.items = items
        self.hovered = -1
        w = max((FONT_SMALL.size(i.label+("  "+i.shortcut if i.shortcut else ""))[0]+30)
                for i in items if not i.separator)
        self.w = max(140, w)
        self.h = sum(6 if i.separator else self.ITEM_H for i in items) + self.PAD*2

    def draw(self, surf, x, y):
        r = pygame.Rect(x, y, self.w, self.h)
        pygame.draw.rect(surf, SYS_BTN_FACE, r)
        draw_edge(surf, r, raised=True)
        cy = y + self.PAD
        for i, item in enumerate(self.items):
            if item.separator:
                pygame.draw.line(surf, SYS_BTN_DARK, (x+4, cy+3), (x+self.w-4, cy+3))
                cy += 6
                continue
            ir = pygame.Rect(x+2, cy, self.w-4, self.ITEM_H)
            if i == self.hovered and item.enabled:
                pygame.draw.rect(surf, SYS_HIGHLIGHT, ir)
            col = WHITE if i==self.hovered and item.enabled else (GRAY if not item.enabled else SYS_TEXT)
            if item.checkable:
                ch_col = col
                draw_text(surf, "✓" if item.checked else " ", (x+8, cy+2), ch_col, FONT_SMALL)
            draw_text(surf, item.label, (x+22, cy+2), col, FONT_SMALL)
            if item.shortcut:
                sw = FONT_SMALL.size(item.shortcut)[0]
                draw_text(surf, item.shortcut, (x+self.w-sw-6, cy+2), col, FONT_SMALL)
            cy += self.ITEM_H

    def hit_item(self, pos, ox, oy):
        cy = oy + self.PAD
        for i, item in enumerate(self.items):
            if item.separator:
                cy += 6
                continue
            ir = pygame.Rect(ox+2, cy, self.w-4, self.ITEM_H)
            if ir.collidepoint(pos):
                return i
            cy += self.ITEM_H
        return -1

    def update_hover(self, pos, ox, oy):
        self.hovered = self.hit_item(pos, ox, oy)


class MenuBar:
    BAR_H = MENU_HEIGHT
    def __init__(self, menus_def):
        self.menus = []
        self.open_idx = -1
        x = 4
        for label, items in menus_def:
            w = FONT_MENU.size(label)[0] + 14
            dm = DropMenu(items)
            self.menus.append([label, x, w, dm])
            x += w

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if my < self.BAR_H:
                for i, (lbl, bx, bw, dm) in enumerate(self.menus):
                    if bx <= mx < bx+bw:
                        self.open_idx = -1 if self.open_idx == i else i
                        return True
            elif self.open_idx >= 0:
                lbl, bx, bw, dm = self.menus[self.open_idx]
                idx = dm.hit_item(event.pos, bx, self.BAR_H)
                if idx >= 0:
                    item = dm.items[idx]
                    if item.enabled and item.callback:
                        item.callback()
                        if item.checkable:
                            item.checked = not item.checked
                self.open_idx = -1
                return True
            else:
                self.open_idx = -1
        if event.type == pygame.MOUSEMOTION and self.open_idx >= 0:
            lbl, bx, bw, dm = self.menus[self.open_idx]
            dm.update_hover(event.pos, bx, self.BAR_H)
            for i, (l2, bx2, bw2, dm2) in enumerate(self.menus):
                if bx2 <= event.pos[0] < bx2+bw2 and event.pos[1] < self.BAR_H:
                    self.open_idx = i
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.open_idx = -1
        return False

    def draw(self, surf):
        pygame.draw.rect(surf, SYS_BTN_FACE, (0, 0, WINDOW_WIDTH, self.BAR_H))
        pygame.draw.line(surf, SYS_HIGHLIGHT, (0, self.BAR_H - 2), (WINDOW_WIDTH, self.BAR_H - 2), 2)
        pygame.draw.line(surf, SYS_BTN_DK_SHD, (0, self.BAR_H - 1), (WINDOW_WIDTH, self.BAR_H - 1))
        for i, (lbl, bx, bw, dm) in enumerate(self.menus):
            r = pygame.Rect(bx, 1, bw, self.BAR_H-2)
            if i == self.open_idx:
                pygame.draw.rect(surf, SYS_HIGHLIGHT, r)
                draw_text(surf, lbl, (bx+7, 3), WHITE, FONT_MENU)
            else:
                draw_text(surf, lbl, (bx+7, 3), SYS_TEXT, FONT_MENU)
        if self.open_idx >= 0:
            lbl, bx, bw, dm = self.menus[self.open_idx]
            dm.draw(surf, bx, self.BAR_H)


# -------------------------
# TOOLBAR BUTTON
# -------------------------
class ToolbarButton:
    def __init__(self, rect, icon_key, callback=None, tooltip="", toggle=False):
        self.rect = pygame.Rect(rect)
        self.icon_key = icon_key
        self.callback = callback
        self.tooltip = tooltip
        self.hovered = False
        self.pressed = False
        self.toggle = toggle
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.pressed and self.rect.collidepoint(event.pos) and self.callback:
                if self.toggle:
                    self.active = not self.active
                self.callback()
            self.pressed = False
        return False

    def draw(self, surf):
        sunken = self.pressed or (self.toggle and self.active)
        if sunken:
            pygame.draw.rect(surf, SYS_BTN_FACE, self.rect)
            pygame.draw.line(surf, SYS_BTN_DARK, self.rect.topleft, self.rect.topright)
            pygame.draw.line(surf, SYS_BTN_DARK, self.rect.topleft, self.rect.bottomleft)
        elif self.hovered:
            pygame.draw.rect(surf, SYS_BTN_FACE, self.rect)
            pygame.draw.line(surf, SYS_BTN_LIGHT, self.rect.topleft, self.rect.topright)
            pygame.draw.line(surf, SYS_BTN_LIGHT, self.rect.topleft, self.rect.bottomleft)
            pygame.draw.line(surf, SYS_BTN_DARK, self.rect.bottomleft, self.rect.bottomright)
            pygame.draw.line(surf, SYS_BTN_DARK, self.rect.topright, self.rect.bottomright)
        else:
            pygame.draw.rect(surf, SYS_BTN_FACE, self.rect)
        fn = ICON_FNS.get(self.icon_key)
        if fn:
            off = (1,1) if sunken else (0,0)
            fn(surf, self.rect.move(off[0], off[1]))


# -------------------------
# SIDEBAR
# -------------------------
class Sidebar:
    def __init__(self):
        self.rect = pygame.Rect(0, CANVAS_Y, SIDEBAR_WIDTH, CANVAS_HEIGHT)
        self.categories = ["Tiles", "BGOs", "NPCs", "Layers"]
        self.current_category = "Tiles"
        self.items = {"Tiles": list(TILE_SMBX_IDS.keys()),
                      "BGOs": list(BGO_SMBX_IDS.keys()),
                      "NPCs": list(NPC_SMBX_IDS.keys()),
                      "Layers": []}
        self.selected_item = 'ground'
        self.tab_h = 20
        self.title_h = 18

    def draw(self, surf, level):
        pygame.draw.rect(surf, SYS_BTN_FACE, self.rect)
        draw_edge(surf, self.rect, raised=False)
        tr = pygame.Rect(self.rect.x+2, self.rect.y+2, self.rect.width-4, self.title_h)
        pygame.draw.rect(surf, SYS_HIGHLIGHT, tr)
        draw_text(surf, "Item toolbox", (tr.x+4, tr.y+3), WHITE, FONT_SMALL)
        tab_y = self.rect.y + self.title_h + 2
        tab_w = self.rect.width // len(self.categories)
        for i, cat in enumerate(self.categories):
            r = pygame.Rect(self.rect.x+2+i*tab_w, tab_y, tab_w-2, self.tab_h)
            sel = (cat == self.current_category)
            pygame.draw.rect(surf, SYS_WINDOW if sel else SYS_BTN_FACE, r)
            draw_edge(surf, r, raised=not sel)
            draw_text(surf, cat, r.center, SYS_TEXT, FONT_SMALL, True)
        content = pygame.Rect(self.rect.x+2, tab_y+self.tab_h, self.rect.width-4,
                              self.rect.height-self.title_h-self.tab_h-4)
        pygame.draw.rect(surf, SYS_WINDOW, content)
        if self.current_category == "Layers":
            self._draw_layers(surf, content, level)
        else:
            self._draw_items(surf, content)

    def _draw_items(self, surf, area):
        items = self.items[self.current_category]
        for i, item in enumerate(items):
            r = pygame.Rect(area.x+4+(i%5)*36, area.y+4+(i//5)*36, 32, 32)
            if not area.contains(r):
                continue
            if item == self.selected_item:
                pygame.draw.rect(surf, SYS_HIGHLIGHT2, r.inflate(4,4))
            preview = pygame.Surface((32,32), pygame.SRCALPHA)
            if self.current_category == "Tiles":
                obj = Tile(0, 0, item)
            elif self.current_category == "BGOs":
                obj = BGO(0, 0, item)
            else:  # NPCs
                obj = NPC(0, 0, item)
            preview.blit(obj.image, (0,0))
            surf.blit(preview, r)

    def _draw_layers(self, surf, area, level):
        y = area.y+5
        section = level.current_section()
        for i, layer in enumerate(section.layers):
            r = pygame.Rect(area.x+2, y, area.width-4, 18)
            pygame.draw.rect(surf, SYS_HIGHLIGHT if i==section.current_layer_idx else SYS_WINDOW, r)
            col = WHITE if i==section.current_layer_idx else SYS_TEXT
            draw_text(surf, layer.name, (r.x+5, r.y+1), col, FONT_SMALL)
            pygame.draw.circle(surf, GREEN if layer.visible else RED, (r.right-8, r.centery), 4)
            pygame.draw.rect(surf, GRAY if layer.locked else SYS_BTN_FACE, (r.right-20, r.y+2, 8, 8))
            y += 22

    def handle_click(self, pos, level):
        tab_y = self.rect.y + self.title_h + 2
        tab_w = self.rect.width // len(self.categories)
        for i, cat in enumerate(self.categories):
            r = pygame.Rect(self.rect.x+2+i*tab_w, tab_y, tab_w-2, self.tab_h)
            if r.collidepoint(pos):
                self.current_category = cat
                return True
        content = pygame.Rect(self.rect.x+2, tab_y+self.tab_h, self.rect.width-4,
                              self.rect.height-self.title_h-self.tab_h-4)
        if self.current_category == "Layers":
            y = content.y+5
            section = level.current_section()
            for i, layer in enumerate(section.layers):
                r = pygame.Rect(content.x+2, y, content.width-4, 18)
                if r.collidepoint(pos):
                    if pos[0] > r.right-20:
                        layer.locked = not layer.locked
                    elif pos[0] > r.right-35:
                        layer.visible = not layer.visible
                    else:
                        section.current_layer_idx = i
                    return True
                y += 22
        else:
            items = self.items[self.current_category]
            for i, item in enumerate(items):
                r = pygame.Rect(content.x+4+(i%5)*36, content.y+4+(i//5)*36, 32, 32)
                if r.collidepoint(pos):
                    self.selected_item = item
                    return True
        return False


# -------------------------
# EDITOR
# -------------------------
class Editor:
    def __init__(self, level, screen, initial_path=None):
        self.screen = screen
        self.level = level
        self.camera = Camera(level.current_section().width, level.current_section().height)
        self.playtest_mode = False
        self.player = None
        self.undo_stack = []
        self.redo_stack = []
        self.sidebar = Sidebar()
        self.drag_draw = False
        self.drag_erase = False
        self.current_file = initial_path if initial_path else None
        self.selection = []
        self.clipboard = []
        self.tool = 'pencil'
        self.grid_enabled = True
        self.mouse_pos = (0,0)
        self.tooltip_text = ""
        self.status_msg = ""
        self.sfx = ProceduralSfxEngine()
        self.sfx_engine_preset = "off"
        self._build_menu()
        self._build_toolbar()

    def _build_menu(self):
        MI = MenuItem
        file_items = [
            MI("New Level",      self.cmd_new,        "Ctrl+N"),
            MI("Open Level...",  self.cmd_open,       "Ctrl+O"),
            MI("Save",           self.cmd_save,       "Ctrl+S"),
            MI("Save As...",     self.cmd_save_as,    "Ctrl+Shift+S"),
            MI("", separator=True),
            MI("Export as JSON", self.cmd_export_json,""),
            MI("", separator=True),
            MI("Exit",           self.cmd_exit,       "Alt+F4"),
        ]
        edit_items = [
            MI("Undo",           self.undo,            "Ctrl+Z"),
            MI("Redo",           self.redo,            "Ctrl+Y"),
            MI("", separator=True),
            MI("Cut",            self.cut_selection,   "Ctrl+X"),
            MI("Copy",           self.copy_selection,  "Ctrl+C"),
            MI("Paste",          self.paste_clipboard, "Ctrl+V"),
            MI("Delete",         self.delete_selected, "Del"),
            MI("", separator=True),
            MI("Select All",     self.select_all,      "Ctrl+A"),
            MI("Deselect All",   self.deselect_all,    "Esc"),
        ]
        view_items = [
            MI("Zoom In",        self.cmd_zoom_in,     "Ctrl+="),
            MI("Zoom Out",       self.cmd_zoom_out,    "Ctrl+-"),
            MI("Reset Zoom",     self.cmd_zoom_reset,  "Ctrl+0"),
            MI("", separator=True),
            MI("Toggle Grid",    self.cmd_toggle_grid, "G", checkable=True, checked=True),
            MI("", separator=True),
            MI("Theme: SMB1",    lambda: self.cmd_set_theme('SMB1')),
            MI("Theme: SMB3",    lambda: self.cmd_set_theme('SMB3')),
            MI("Theme: SMW",     lambda: self.cmd_set_theme('SMW')),
            MI("", separator=True),
            MI("Playtest SFX: Off",           lambda: self.cmd_set_sfx_engine("off")),
            MI("Playtest SFX: SMB1",          lambda: self.cmd_set_sfx_engine("smb1")),
            MI("Playtest SFX: SMB3",          lambda: self.cmd_set_sfx_engine("smb3")),
            MI("Playtest SFX: SMW",           lambda: self.cmd_set_sfx_engine("smw")),
            MI("Playtest SFX: Mario Maker",   lambda: self.cmd_set_sfx_engine("mm")),
        ]
        level_items = [
            MI("Level Properties...", self.cmd_properties, "F4"),
            MI("", separator=True),
            MI("Add Layer",      self.cmd_add_layer,   ""),
            MI("Layer Manager...",self.cmd_layer_manager,""),
            MI("", separator=True),
            MI("Event Editor...", self.cmd_event_editor, "F6"),
            MI("Warp Editor...",  self.cmd_warp_editor, "F7"),
            MI("", separator=True),
            MI("Set Start Pos",  self.cmd_set_start,   ""),
            MI("Fill BG",        self.cmd_fill_bg,     ""),
            MI("Clear All",      self.cmd_clear_all,   ""),
        ]
        tool_items = [
            MI("Select",  self.set_tool_select, "S"),
            MI("Pencil",  self.set_tool_pencil, "P"),
            MI("Eraser / Paint",  self.set_tool_erase,  "E"),
            MI("Fill",    self.set_tool_fill,   "F"),
            MI("", separator=True),
            MI("Event Trigger", self.set_tool_event, "T"),
        ]
        test_items = [
            MI("Playtest",       self.toggle_playtest, "F5"),
            MI("", separator=True),
            MI("Reset Player",   self.cmd_reset_player,""),
        ]
        help_items = [
            MI("Controls...",    self.cmd_help,        "F1"),
            MI("About...",       self.cmd_about,       ""),
        ]
        self.menubar = MenuBar([
            ("File",  file_items),
            ("Edit",  edit_items),
            ("View",  view_items),
            ("Level", level_items),
            ("Tools", tool_items),
            ("Test",  test_items),
            ("Help",  help_items),
        ])

    def _build_toolbar(self):
        items = [
            ("new",     self.cmd_new,       "New Level (Ctrl+N)"),
            ("open",    self.cmd_open,      "Open Level (Ctrl+O)"),
            ("save",    self.cmd_save,      "Save (Ctrl+S)"),
            None,
            ("undo",    self.undo,          "Undo (Ctrl+Z)"),
            ("redo",    self.redo,          "Redo (Ctrl+Y)"),
            None,
            ("select",  self.set_tool_select,"Select Tool [S]"),
            ("pencil",  self.set_tool_pencil,"Pencil Tool [P]"),
            ("eraser",  self.set_tool_erase, "Paint tool [E] — left: place, right: erase"),
            ("fill",    self.set_tool_fill,  "Fill Tool [F]"),
            None,
            ("grid",    self.cmd_toggle_grid,"Toggle Grid [G]", True),
            ("zoom_in", self.cmd_zoom_in,   "Zoom In (Ctrl+=)"),
            ("zoom_out",self.cmd_zoom_out,  "Zoom Out (Ctrl+-)"),
            None,
            ("layer",   self.cmd_layer_manager,"Layer Manager"),
            ("event",   self.cmd_event_editor,"Event Editor [F6]"),
            ("props",   self.cmd_properties,"Level Properties [F4]"),
            None,
            ("play",    self.toggle_playtest,"Playtest [F5]", True),
        ]
        self.toolbar_btns = []
        tb_sz = 24
        tb_y = MENU_HEIGHT + (TOOLBAR_HEIGHT - tb_sz) // 2
        x = SIDEBAR_WIDTH + 4
        for item in items:
            if item is None:
                x += 8
                continue
            if len(item) == 4:
                ik, cb, tip, tog = item
                self.toolbar_btns.append(ToolbarButton((x, tb_y, tb_sz, tb_sz), ik, cb, tip, toggle=tog))
            else:
                ik, cb, tip = item
                self.toolbar_btns.append(ToolbarButton((x, tb_y, tb_sz, tb_sz), ik, cb, tip))
            x += tb_sz + 4

    # ---- MENU COMMANDS ----
    def cmd_new(self):
        res = MessageBox(self.screen, "New Level", "Discard current level and start new?", ("Yes","No")).run()
        if res == "Yes":
            self.level = Level()
            self.current_file = None
            self.camera = Camera(self.level.current_section().width, self.level.current_section().height)
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.selection.clear()
            self.status("New level created.")

    def cmd_open(self):
        start = os.path.dirname(self.current_file) if self.current_file else None
        fn = ask_open_level_path(initial_dir=start)
        if fn:
            if os.path.exists(fn):
                self.level = smart_read(fn)
                self.current_file = fn
                self.camera = Camera(self.level.current_section().width, self.level.current_section().height)
                self.status(f"Opened: {fn}")
            else:
                MessageBox(self.screen, "Error", f"File not found:\n{fn}").run()

    def cmd_save(self):
        if not self.current_file:
            self.cmd_save_as()
            return
        smart_write(self.current_file, self.level)
        self.status(f"Saved: {self.current_file}")

    def cmd_save_as(self):
        fn = ask_save_level_path(suggested_name=self.current_file or "level.lvl")
        if fn:
            self.current_file = fn
            smart_write(fn, self.level)
            self.status(f"Saved as: {fn}")

    def cmd_export_json(self):
        base = self.current_file or "level"
        for ext in (".lvl", ".LVL", ".38a", ".lvlx", ".LVLX"):
            base = base.replace(ext, "")
        default_json = base + ".json"
        start = os.path.dirname(self.current_file) if self.current_file else None
        fn = ask_save_json_path(suggested_name=os.path.basename(default_json), initial_dir=start)
        if not fn:
            return
        section = self.level.current_section()
        data = {"name":self.level.name,"author":self.level.author,"tiles":[],"bgos":[],"npcs":[]}
        for li,layer in enumerate(section.layers):
            for t in layer.tiles:
                data["tiles"].append({"x":t.rect.x,"y":t.rect.y,"type":t.tile_type,"layer":li})
            for b in layer.bgos:
                data["bgos"].append({"x":b.rect.x,"y":b.rect.y,"type":b.bgo_type,"layer":li})
            for n in layer.npcs:
                data["npcs"].append({"x":n.rect.x,"y":n.rect.y,"type":n.npc_type,"layer":li})
        with open(fn,'w') as f:
            json.dump(data,f,indent=2)
        MessageBox(self.screen,"Export","Exported to:\n"+fn).run()

    def cmd_exit(self):
        res = MessageBox(self.screen, "Exit", f"Exit {APP_TITLE}?", ("Yes", "No")).run()
        if res=="Yes":
            pygame.quit()
            sys.exit()

    def cmd_zoom_in(self):
        self.camera.zoom = min(ZOOM_MAX, round(self.camera.zoom+ZOOM_STEP,2))
        self.status(f"Zoom: {int(self.camera.zoom*100)}%")

    def cmd_zoom_out(self):
        self.camera.zoom = max(ZOOM_MIN, round(self.camera.zoom-ZOOM_STEP,2))
        self.status(f"Zoom: {int(self.camera.zoom*100)}%")

    def cmd_zoom_reset(self):
        self.camera.zoom = 1.0
        self.status("Zoom: 100%")

    def cmd_toggle_grid(self):
        self.grid_enabled = not self.grid_enabled
        self.status("Grid: "+("ON" if self.grid_enabled else "OFF"))
        for lbl,bx,bw,dm in self.menubar.menus:
            if lbl=="View":
                for item in dm.items:
                    if item.label=="Toggle Grid":
                        item.checked = self.grid_enabled
        for btn in self.toolbar_btns:
            if btn.icon_key=='grid':
                btn.active = self.grid_enabled

    def cmd_set_theme(self,theme):
        global current_theme
        current_theme = theme
        section = self.level.current_section()
        for layer in section.layers:
            for t in layer.tiles:
                t.update_image()
            for b in layer.bgos:
                b.update_image()
            for n in layer.npcs:
                n.update_image()
        self.status(f"Theme: {theme}")

    def cmd_set_sfx_engine(self, preset):
        self.sfx_engine_preset = preset
        self.sfx.set_preset(preset)
        lab = {"off": "Off", "smb1": "SMB1", "smb3": "SMB3", "smw": "SMW", "mm": "Mario Maker"}.get(preset, preset)
        self.status(f"Playtest SFX: {lab} (procedural, no sound files)")

    def cmd_properties(self):
        PropertiesDialog(self.screen, self.level).run()
        self.camera = Camera(self.level.current_section().width, self.level.current_section().height)
        section = self.level.current_section()
        for layer in section.layers:
            for t in layer.tiles:
                t.update_image()

    def cmd_add_layer(self):
        section = self.level.current_section()
        section.layers.append(Layer(f"Layer {len(section.layers)+1}"))
        self.status(f"Added layer {len(section.layers)}")

    def cmd_layer_manager(self):
        LayerDialog(self.screen, self.level.current_section()).run()

    def cmd_set_start(self):
        wx, wy = self.get_mouse_world()
        gx, gy = self.world_to_grid(wx, wy)
        section = self.level.current_section()
        section.start_x = gx
        section.start_y = gy
        if self.player:
            self.player.level_start = (gx, gy)
        self.status(f"Start pos set: {gx},{gy}")

    def cmd_fill_bg(self):
        dlg = MessageBox(self.screen, "Background", "Choose background color index (1-6):", ("1","2","3","4","5","6","Cancel"))
        res = dlg.run()
        if res and res != "Cancel":
            idx = int(res)-1
            colors = [(92,148,252), (0,0,40), (0,0,0), (255,140,60), (30,20,10), (0,80,160)]
            if 0 <= idx < len(colors):
                self.level.current_section().bg_color = colors[idx]

    def cmd_clear_all(self):
        res = MessageBox(self.screen, "Clear All", "Clear ALL objects from level?\nThis cannot be undone!", ("Yes","No")).run()
        if res == "Yes":
            section = self.level.current_section()
            for layer in section.layers:
                layer.tiles.empty()
                layer.bgos.empty()
                layer.npcs.empty()
                layer.tile_map.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.selection.clear()
            self.status("Level cleared.")

    def cmd_reset_player(self):
        if self.player:
            section = self.level.current_section()
            self.player.rect.topleft = (section.start_x, section.start_y)
            self.player.velocity.update(0,0)
            self.status("Player reset.")

    def cmd_help(self):
        MessageBox(self.screen, "Controls",
            f"{APP_TITLE}\n\n"
            "EDITOR:\n"
            "  Left Click - Place tile/BGO/NPC (Pencil & Eraser) or Select/Fill/Event\n"
            "  Right Click - Delete asset under cursor (any canvas tool; drag to strip)\n"
            "    Hit order: NPC, then BGO, then tile\n"
            "  Arrow Keys - Scroll\n"
            "  Ctrl+Z/Y - Undo/Redo\n"
            "  Ctrl+C/V/X - Copy/Paste/Cut\n"
            "  Ctrl+A - Select All\n"
            "  G - Toggle Grid\n"
            "  Ctrl+=/-  Zoom In/Out\n"
            "  F5 - Playtest\n\n"
            "PLAYTEST:\n"
            "  Arrow/WASD - Move\n"
            "  Space - Jump\n"
            "  Escape - Back to editor"
        ).run()

    def cmd_about(self):
        MessageBox(self.screen, "About",
            f"{APP_TITLE}\n"
            f"Version {APP_VER}\n\n"
            "(C) 1985-2026 Nintendo\n"
            "(C) Redigit 2007-2026\n"
            "(C) A.C Holdings 1999-2026"
        ).run()

    def cmd_event_editor(self):
        EventDialog(self.screen, self.level).run()

    def cmd_warp_editor(self):
        WarpDialog(self.screen, self.level).run()

    def select_all(self):
        self.selection.clear()
        layer = self.level.current_layer()
        self.selection.extend(layer.tiles.sprites())
        self.selection.extend(layer.bgos.sprites())
        self.selection.extend(layer.npcs.sprites())
        self.status(f"Selected {len(self.selection)} objects")

    def deselect_all(self):
        self.selection.clear()

    def delete_selected(self):
        for obj in self.selection:
            self._delete_object(obj)
        self.selection.clear()
        self.status("Deleted selected objects")

    # ---- TOOLS ----
    def set_tool_select(self):
        self.tool = 'select'
        self.status("Tool: Select")

    def set_tool_pencil(self):
        self.tool = 'pencil'
        self.status("Tool: Pencil — left: place, right: erase")

    def set_tool_erase(self):
        self.tool = 'erase'
        self.status("Tool: Eraser — left: place, right: erase (same as Pencil)")

    def set_tool_fill(self):
        self.tool = 'fill'
        self.status("Tool: Fill")

    def set_tool_event(self):
        self.tool = 'event'
        self.status("Tool: Event Picker (click object to assign event)")

    def toggle_playtest(self):
        if self.menubar.open_idx >= 0:
            self.menubar.open_idx = -1
        self.playtest_mode = not self.playtest_mode
        if self.playtest_mode:
            section = self.level.current_section()
            self.player = Player(section.start_x, section.start_y)
            self.player.level_start = (section.start_x, section.start_y)
            self.camera.update(self.player)
            self.sfx.set_preset(self.sfx_engine_preset)
            self.status("PLAYTEST - Esc to return")
        else:
            self.player = None
            self.status("Editor mode")
        for btn in self.toolbar_btns:
            if btn.icon_key=='play':
                btn.active = self.playtest_mode

    def status(self, msg):
        self.status_msg = msg

    # ---- UNDO/REDO ----
    def push_undo(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.status("Nothing to undo")
            return
        action = self.undo_stack.pop()
        action['undo']()
        self.redo_stack.append(action)
        self.status("Undo")

    def redo(self):
        if not self.redo_stack:
            self.status("Nothing to redo")
            return
        action = self.redo_stack.pop()
        action['redo']()
        self.undo_stack.append(action)
        self.status("Redo")

    # ---- COORD HELPERS ----
    def world_to_grid(self, wx, wy):
        return (int(wx)//GRID_SIZE)*GRID_SIZE, (int(wy)//GRID_SIZE)*GRID_SIZE

    def get_mouse_world(self):
        mx, my = self.mouse_pos
        return ((mx - SIDEBAR_WIDTH)/self.camera.zoom - self.camera.camera.x,
                (my - CANVAS_Y)/self.camera.zoom - self.camera.camera.y)

    def canvas_to_world(self, sx, sy):
        return (sx - SIDEBAR_WIDTH)/self.camera.zoom - self.camera.camera.x, \
               (sy - CANVAS_Y)/self.camera.zoom - self.camera.camera.y

    # ---- OBJECT PLACEMENT ----
    def place_object(self, gx, gy):
        layer = self.level.current_layer()
        if layer.locked:
            return
        key = (gx, gy)
        if self.sidebar.current_category == "NPCs":
            npc = NPC(gx, gy, self.sidebar.selected_item, layer=layer)
            layer.npcs.add(npc)
            self.push_undo({'undo': lambda l=layer, n=npc: l.npcs.remove(n),
                            'redo': lambda l=layer, n=npc: l.npcs.add(n)})
        elif self.sidebar.current_category == "BGOs":
            bgo = BGO(gx, gy, self.sidebar.selected_item, layer=layer)
            layer.bgos.add(bgo)
            self.push_undo({'undo': lambda l=layer, b=bgo: l.bgos.remove(b),
                            'redo': lambda l=layer, b=bgo: l.bgos.add(b)})
        else:
            if key in layer.tile_map:
                return
            tile = Tile(gx, gy, self.sidebar.selected_item, layer=layer)
            layer.add_tile(tile)
            self.push_undo({'undo': lambda l=layer, t=tile: l.remove_tile(t),
                            'redo': lambda l=layer, t=tile: l.add_tile(t)})

    def erase_object(self, gx, gy, wx=None, wy=None):
        """Remove one object on the current layer. Prefer pixel hit (wx, wy) so zoom lines up."""
        layer = self.level.current_layer()
        if layer.locked:
            return
        key = (gx, gy)
        use_pt = wx is not None and wy is not None

        if use_pt:
            pt = (float(wx), float(wy))
            for obj in list(layer.npcs):
                if obj.rect.collidepoint(pt):
                    layer.npcs.remove(obj)
                    self.push_undo({'undo': lambda g=layer.npcs, o=obj: g.add(o),
                                    'redo': lambda g=layer.npcs, o=obj: g.remove(o)})
                    self.status_msg = "Removed NPC (right-click)"
                    return
            for obj in list(layer.bgos):
                if obj.rect.collidepoint(pt):
                    layer.bgos.remove(obj)
                    self.push_undo({'undo': lambda g=layer.bgos, o=obj: g.add(o),
                                    'redo': lambda g=layer.bgos, o=obj: g.remove(o)})
                    self.status_msg = "Removed BGO (right-click)"
                    return
            for tkey, tile in list(layer.tile_map.items()):
                if tile.rect.collidepoint(pt):
                    layer.remove_tile(tile)
                    self.push_undo({'undo': lambda l=layer, t=tile: l.add_tile(t),
                                    'redo': lambda l=layer, k=tkey: l.remove_tile(l.tile_map[k]) if k in l.tile_map else None})
                    self.status_msg = "Removed tile (right-click)"
                    return
            return

        if key in layer.tile_map:
            tile = layer.tile_map[key]
            layer.remove_tile(tile)
            self.push_undo({'undo': lambda l=layer, t=tile: l.add_tile(t),
                            'redo': lambda l=layer, k=key: l.remove_tile(l.tile_map[k]) if k in l.tile_map else None})
            self.status_msg = "Removed tile"
            return
        for group in (layer.npcs, layer.bgos):
            for obj in list(group):
                if obj.rect.x == gx and obj.rect.y == gy:
                    group.remove(obj)
                    self.push_undo({'undo': lambda g=group, o=obj: g.add(o),
                                    'redo': lambda g=group, o=obj: g.remove(o)})
                    self.status_msg = "Removed object"
                    return

    def fill_area(self, sx, sy):
        layer = self.level.current_layer()
        if layer.locked:
            return
        target = self.sidebar.selected_item
        start = (sx, sy)
        old_type = layer.tile_map[start].tile_type if start in layer.tile_map else None
        if old_type == target:
            return
        queue = deque([start])
        visited = set()
        new_tiles = []
        while queue:
            x, y = queue.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            if old_type is None:
                if (x, y) in layer.tile_map:
                    continue
            else:
                if (x, y) not in layer.tile_map or layer.tile_map[(x, y)].tile_type != old_type:
                    continue
            if (x, y) in layer.tile_map:
                layer.remove_tile(layer.tile_map[(x, y)])
            t = Tile(x, y, target, layer=layer)
            layer.add_tile(t)
            new_tiles.append(t)
            sec = self.level.current_section()
            for dx, dy in [(GRID_SIZE,0), (-GRID_SIZE,0), (0,GRID_SIZE), (0,-GRID_SIZE)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < sec.width and 0 <= ny < sec.height:
                    queue.append((nx, ny))
        if new_tiles:
            self.push_undo({'undo': lambda l=layer, nt=new_tiles: [l.remove_tile(t) for t in nt],
                            'redo': lambda l=layer, nt=new_tiles: [l.add_tile(t) for t in nt]})

    def handle_select(self, gx, gy, event):
        layer = self.level.current_layer()
        obj = None
        if (gx, gy) in layer.tile_map:
            obj = layer.tile_map[(gx, gy)]
        else:
            for n in layer.npcs:
                if n.rect.x == gx and n.rect.y == gy:
                    obj = n
                    break
            if not obj:
                for b in layer.bgos:
                    if b.rect.x == gx and b.rect.y == gy:
                        obj = b
                        break
        if obj:
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_SHIFT:
                if obj in self.selection:
                    self.selection.remove(obj)
                else:
                    self.selection.append(obj)
            else:
                self.selection = [obj]

    def handle_event_pick(self, gx, gy):
        layer = self.level.current_layer()
        obj = None
        if (gx, gy) in layer.tile_map:
            obj = layer.tile_map[(gx, gy)]
        else:
            for n in layer.npcs:
                if n.rect.x == gx and n.rect.y == gy:
                    obj = n
                    break
            if not obj:
                for b in layer.bgos:
                    if b.rect.x == gx and b.rect.y == gy:
                        obj = b
                        break
        if obj:
            dlg = InputDialog(self.screen, "Assign Event", "Event ID (or -1 for none):", str(obj.event_id))
            res = dlg.run()
            if res is not None:
                try:
                    obj.event_id = int(res)
                except:
                    pass

    def copy_selection(self):
        self.clipboard = [(o.rect.x, o.rect.y, o.obj_type, o.layer) for o in self.selection]
        self.status(f"Copied {len(self.clipboard)} object(s)")

    def cut_selection(self):
        self.copy_selection()
        for o in self.selection:
            self._delete_object(o)
        self.selection.clear()

    def paste_clipboard(self):
        if not self.clipboard:
            return
        wx, wy = self.get_mouse_world()
        bx, by = self.world_to_grid(wx, wy)
        ox, oy = self.clipboard[0][0], self.clipboard[0][1]
        for x, y, otype, li in self.clipboard:
            nx, ny = bx + (x-ox), by + (y-oy)
            if otype in TILE_SMBX_IDS:
                self.level.current_section().layers[li].add_tile(Tile(nx, ny, otype, li))
            elif otype in BGO_SMBX_IDS:
                self.level.current_section().layers[li].bgos.add(BGO(nx, ny, otype, li))
            elif otype in NPC_SMBX_IDS:
                self.level.current_section().layers[li].npcs.add(NPC(nx, ny, otype, li))
        self.status(f"Pasted {len(self.clipboard)} object(s)")

    def _delete_object(self, obj):
        layer = self.level.current_section().layers[obj.layer if isinstance(obj.layer, int) else 0]
        if isinstance(obj, Tile):
            layer.remove_tile(obj)
        elif isinstance(obj, BGO):
            layer.bgos.remove(obj)
        elif isinstance(obj, NPC):
            layer.npcs.remove(obj)

    # ---- EVENT HANDLING ----
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False

        if self.menubar.handle_event(event):
            return True

        for btn in self.toolbar_btns:
            btn.handle_event(event)

        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.tooltip_text = ""
            for btn in self.toolbar_btns:
                if btn.rect.collidepoint(event.pos):
                    self.tooltip_text = btn.tooltip

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL
            if event.key == pygame.K_ESCAPE:
                if self.playtest_mode:
                    self.toggle_playtest()
                elif self.menubar.open_idx >= 0:
                    self.menubar.open_idx = -1
                else:
                    self.deselect_all()
            if not self.playtest_mode and not ctrl:
                if event.key == pygame.K_s:
                    self.set_tool_select()
                if event.key == pygame.K_p:
                    self.set_tool_pencil()
                if event.key == pygame.K_e:
                    self.set_tool_erase()
                if event.key == pygame.K_f:
                    self.set_tool_fill()
                if event.key == pygame.K_t:
                    self.set_tool_event()
                if event.key == pygame.K_g:
                    self.cmd_toggle_grid()
                if event.key == pygame.K_LEFT:
                    self.camera.move(GRID_SIZE, 0)
                if event.key == pygame.K_RIGHT:
                    self.camera.move(-GRID_SIZE, 0)
                if event.key == pygame.K_UP:
                    self.camera.move(0, GRID_SIZE)
                if event.key == pygame.K_DOWN:
                    self.camera.move(0, -GRID_SIZE)
                if event.key == pygame.K_F4:
                    self.cmd_properties()
                if event.key == pygame.K_F5:
                    self.toggle_playtest()
                if event.key == pygame.K_F6:
                    self.cmd_event_editor()
                if event.key == pygame.K_F7:
                    self.cmd_warp_editor()
                if event.key == pygame.K_F1:
                    self.cmd_help()
                if event.key == pygame.K_DELETE:
                    self.delete_selected()
            if ctrl:
                if event.key == pygame.K_n:
                    self.cmd_new()
                if event.key == pygame.K_o:
                    self.cmd_open()
                if event.key == pygame.K_s:
                    self.cmd_save()
                if event.key == pygame.K_z:
                    self.undo()
                if event.key == pygame.K_y:
                    self.redo()
                if event.key == pygame.K_c:
                    self.copy_selection()
                if event.key == pygame.K_v:
                    self.paste_clipboard()
                if event.key == pygame.K_x:
                    self.cut_selection()
                if event.key == pygame.K_a:
                    self.select_all()
                if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    self.cmd_zoom_in()
                if event.key == pygame.K_MINUS:
                    self.cmd_zoom_out()
                if event.key == pygame.K_0:
                    self.cmd_zoom_reset()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.sidebar.rect.collidepoint(event.pos) and event.button == 1:
                self.sidebar.handle_click(event.pos, self.level)
            elif (event.pos[1] > CANVAS_Y and event.pos[0] > SIDEBAR_WIDTH
                  and not self.playtest_mode and self.menubar.open_idx < 0):
                wx, wy = self.canvas_to_world(event.pos[0], event.pos[1])
                gx, gy = self.world_to_grid(wx, wy)
                if event.button == 1:
                    if self.tool in ('pencil', 'erase'):
                        self.drag_draw = True
                        self.place_object(gx, gy)
                    elif self.tool == 'select':
                        self.handle_select(gx, gy, event)
                    elif self.tool == 'fill':
                        self.fill_area(gx, gy)
                    elif self.tool == 'event':
                        self.handle_event_pick(gx, gy)
                elif event.button == 3:
                    self.drag_erase = True
                    self.erase_object(gx, gy, wx, wy)
                elif event.button == 4:
                    self.cmd_zoom_in()
                elif event.button == 5:
                    self.cmd_zoom_out()

        if event.type == pygame.MOUSEMOTION and not self.playtest_mode:
            if self.drag_draw or self.drag_erase:
                wx, wy = self.canvas_to_world(event.pos[0], event.pos[1])
                gx, gy = self.world_to_grid(wx, wy)
                if self.drag_draw:
                    self.place_object(gx, gy)
                elif self.drag_erase:
                    self.erase_object(gx, gy, wx, wy)

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.drag_draw = False
            elif event.button == 3:
                self.drag_erase = False

        return True

    # ---- UPDATE ----
    def update(self):
        if self.playtest_mode and self.player:
            section = self.level.current_section()
            solid = section.get_solid_tiles()
            npcs = pygame.sprite.Group()
            coin_tiles = []
            for layer in section.layers:
                if layer.visible:
                    npcs.add(layer.npcs.sprites())
                    coin_tiles.extend(t for t in layer.tiles if t.tile_type == "coin")
            self.player.update(
                solid, npcs, section.events,
                coin_tiles=coin_tiles,
                sfx_cb=self.sfx.play,
            )
            for npc in npcs:
                npc.update(solid, self.player, section.events)
            self.camera.update(self.player)

    # ---- DRAW ----
    def draw(self, surf):
        surf.fill(SYS_BG)

        # Toolbar dock strip
        pygame.draw.rect(surf, SYS_BTN_FACE, (0, MENU_HEIGHT, WINDOW_WIDTH, TOOLBAR_HEIGHT))
        pygame.draw.line(surf, SYS_BTN_DK_SHD, (0, MENU_HEIGHT), (WINDOW_WIDTH, MENU_HEIGHT))
        pygame.draw.line(surf, SYS_BTN_DARK, (0, MENU_HEIGHT + TOOLBAR_HEIGHT - 1), (WINDOW_WIDTH, MENU_HEIGHT + TOOLBAR_HEIGHT - 1))

        # Draw toolbar buttons
        for btn in self.toolbar_btns:
            btn.draw(surf)

        # Sidebar
        self.sidebar.draw(surf, self.level)

        # Canvas
        canvas_rect = pygame.Rect(SIDEBAR_WIDTH, CANVAS_Y, CANVAS_WIDTH, CANVAS_HEIGHT)
        surf.set_clip(canvas_rect)
        surf.fill(self.level.current_section().bg_color)

        # Grid
        if self.grid_enabled:
            zoom = self.camera.zoom
            cam = self.camera.camera
            sc = int(-cam.x // GRID_SIZE)
            ec = sc + int(CANVAS_WIDTH/(GRID_SIZE*zoom)) + 2
            sr = int(-cam.y // GRID_SIZE)
            er = sr + int(CANVAS_HEIGHT/(GRID_SIZE*zoom)) + 2
            for c in range(sc, ec):
                px = c*GRID_SIZE + cam.x + SIDEBAR_WIDTH
                if canvas_rect.left < px < canvas_rect.right:
                    pygame.draw.line(surf, SMBX_GRID, (px, canvas_rect.y), (px, canvas_rect.bottom))
            for r in range(sr, er):
                py = r*GRID_SIZE + cam.y + CANVAS_Y
                if canvas_rect.top < py < canvas_rect.bottom:
                    pygame.draw.line(surf, SMBX_GRID, (canvas_rect.x, py), (canvas_rect.right, py))

        # Sprites
        section = self.level.current_section()
        for layer in section.layers:
            if not layer.visible:
                continue
            for bgo in layer.bgos:
                p = bgo.rect.move(self.camera.camera.x + SIDEBAR_WIDTH, self.camera.camera.y + CANVAS_Y)
                surf.blit(bgo.image, p)
            for tile in layer.tiles:
                p = tile.rect.move(self.camera.camera.x + SIDEBAR_WIDTH, self.camera.camera.y + CANVAS_Y)
                surf.blit(tile.image, p)
            for npc in layer.npcs:
                p = npc.rect.move(self.camera.camera.x + SIDEBAR_WIDTH, self.camera.camera.y + CANVAS_Y)
                surf.blit(npc.image, p)

        # Selection outlines
        if not self.playtest_mode:
            for obj in self.selection:
                p = obj.rect.move(self.camera.camera.x + SIDEBAR_WIDTH, self.camera.camera.y + CANVAS_Y)
                pygame.draw.rect(surf, SYS_HIGHLIGHT, p, 2)
                pygame.draw.rect(surf, SYS_HIGHLIGHT2, p.inflate(2, 2), 1)

        # Start position marker
        sp = pygame.Rect(section.start_x + self.camera.camera.x + SIDEBAR_WIDTH,
                         section.start_y + self.camera.camera.y + CANVAS_Y,
                         GRID_SIZE, GRID_SIZE)
        if not self.playtest_mode:
            pygame.draw.rect(surf, GREEN, sp, 2)
            draw_text(surf, "S", (sp.x+2, sp.y+2), GREEN, FONT_SMALL)

        # Player
        if self.playtest_mode and self.player:
            self.player.draw(surf, (self.camera.camera.x + SIDEBAR_WIDTH, self.camera.camera.y + CANVAS_Y))

        surf.set_clip(None)

        # Canvas border
        draw_edge(surf, canvas_rect, raised=False)

        # Status Bar
        sb_y = WINDOW_HEIGHT - STATUSBAR_HEIGHT
        pygame.draw.rect(surf, SYS_BG, (0, sb_y, WINDOW_WIDTH, STATUSBAR_HEIGHT))
        pygame.draw.line(surf, SYS_BTN_DK_SHD, (0, sb_y), (WINDOW_WIDTH, sb_y))

        def panel(px, pw, text):
            pr = pygame.Rect(px, sb_y+2, pw, STATUSBAR_HEIGHT-4)
            pygame.draw.rect(surf, SYS_BTN_FACE, pr)
            draw_edge(surf, pr, raised=False)
            draw_text(surf, text, (pr.x + 4, pr.y + 3), SYS_TEXT, FONT_SMALL)

        mode = "PLAYTEST" if self.playtest_mode else f"{self.tool.upper()}"
        panel(2, 120, f"Mode: {mode}")
        panel(126, 160, f"Layer: {self.level.current_layer().name}")
        wx, wy = self.get_mouse_world()
        gx, gy = self.world_to_grid(wx, wy)
        panel(290, 140, f"X:{int(gx//GRID_SIZE)} Y:{int(gy//GRID_SIZE)}")
        panel(434, 100, f"Zoom: {int(self.camera.zoom*100)}%")
        if self.playtest_mode and self.player:
            panel(538, 200, f"Coins:{self.player.coins}  Score:{self.player.score}")
        elif self.status_msg:
            panel(538, WINDOW_WIDTH-542, self.status_msg)

        # Tooltip
        if self.tooltip_text:
            tx, ty = self.mouse_pos
            ty -= 20
            tw = FONT_SMALL.size(self.tooltip_text)[0] + 10
            tr = pygame.Rect(tx, max(CANVAS_Y, ty), tw, 17)
            pygame.draw.rect(surf, SYS_WINDOW, tr)
            draw_edge(surf, tr, raised=True)
            draw_text(surf, self.tooltip_text, (tr.x + 5, tr.y + 3), SYS_TEXT, FONT_SMALL)

        # Menubar drawn last
        self.menubar.draw(surf)


# -------------------------
# MAIN MENU SCREEN
# -------------------------
def main_menu(screen):
    clock = pygame.time.Clock()
    btns = [
        pygame.Rect(WINDOW_WIDTH//2-100, 300, 200, 32),
        pygame.Rect(WINDOW_WIDTH//2-100, 340, 200, 32),
        pygame.Rect(WINDOW_WIDTH//2-100, 380, 200, 32),
    ]
    labels = ["New Level", "Open Level", "Quit"]
    hovered = -1

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.MOUSEMOTION:
                hovered = -1
                for i, r in enumerate(btns):
                    if r.collidepoint(event.pos):
                        hovered = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(btns):
                    if r.collidepoint(event.pos):
                        return ["NEW", "LOAD", "QUIT"][i]

        screen.fill(SYS_BTN_FACE)
        wr = pygame.Rect(WINDOW_WIDTH//2-220, 80, 440, 360)
        pygame.draw.rect(screen, SYS_BTN_FACE, wr)
        draw_edge(screen, wr, raised=True)
        tr = pygame.Rect(wr.x, wr.y, wr.w, 22)
        pygame.draw.rect(screen, SYS_HIGHLIGHT, tr)
        draw_text(screen, APP_TITLE, (tr.x + 4, tr.y + 4), WHITE, FONT_SMALL)

        cr = pygame.Rect(wr.x+6, tr.bottom+6, wr.w-12, wr.h-tr.h-12)
        pygame.draw.rect(screen, SYS_WINDOW, cr)
        draw_edge(screen, cr, raised=False)

        draw_text(screen, APP_TITLE, (cr.centerx, cr.y + 44), SYS_HIGHLIGHT, FONT_TITLE, True)
        draw_text(screen, f"Version {APP_VER}", (cr.centerx, cr.y + 82), SYS_TEXT, FONT_SMALL, True)

        for i, (r, lbl) in enumerate(zip(btns, labels)):
            sel = (i == hovered)
            pygame.draw.rect(screen, SYS_HIGHLIGHT if sel else SYS_BTN_FACE, r)
            draw_edge(screen, r, raised=not sel)
            draw_text(screen, lbl, r.center, WHITE if sel else SYS_TEXT, FONT, True)

        pygame.display.flip()
        clock.tick(60)


# -------------------------
# MAIN
# -------------------------
def main():
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    while True:
        result = main_menu(screen)
        if result == "QUIT":
            pygame.quit()
            sys.exit()
        level = Level()
        loaded_from = None
        if result == "LOAD":
            fn = ask_open_level_path()
            if fn and os.path.exists(fn):
                level = smart_read(fn)
                loaded_from = fn
        editor = Editor(level, screen, initial_path=loaded_from)
        running = True
        while running:
            for event in pygame.event.get():
                res = editor.handle_event(event)
                if res is False:
                    pygame.quit()
                    sys.exit()
                if res == "MENU":
                    running = False
            editor.update()
            editor.draw(screen)
            pygame.display.flip()
            clock.tick(FPS)


if __name__ == "__main__":
    main()
