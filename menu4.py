"""
GAME MAP 3D - menu chay game .exe (pygame)
------------------------------------------
- Luon chay toan man hinh, tu lay do phan giai that cua man hinh (2K -> 2K, 4K -> 4K).
- Moi file .exe nam canh menu la mot "khu vuc" tren ban do 3D (goc nhin cheo xuong).
- Click 1 lan: chon. Click lan 2 / double-click / Enter / nut RUN: chay game.
- Nut IMPORT (hoac keo-tha file .exe vao man hinh): chep game tu noi khac vao thu muc menu.
- Phim: mui ten = di chuyen | Enter = chay | F5 = quet lai | Con lan chuot = zoom | Delete = xoa game | ESC = thoat.
- Panel phai hien thanh tuu cua game dang chon (x/y): >=50% cam, >=80% xanh la, 100% -> loi nhan.
  (Doc achievements.json canh game; tong so thanh tuu lay tu khoa "total" trong file do,
   hoac tu file .py cung ten dat canh .exe neu co.)
- Khi game dang chay menu se thu nho xuong, dong game xong menu tu hien lai.

Cai dat:  pip install pygame
Chay:     python menu.py          (them --windowed neu muon thu o che do cua so)
"""

import ast
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
import time

# Windows: bao Windows khong "phong to ao" man hinh de lay dung do phan giai that
if sys.platform == "win32":
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pygame

if getattr(sys, "frozen", False):      # menu cung duoc dong goi thanh .exe
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    SELF_NAME = os.path.basename(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SELF_NAME = os.path.basename(os.path.abspath(__file__))

GAME_EXTS = (".exe",)                  # loai file duoc coi la game

# ---------- mau ----------
BG = (12, 13, 15)
MAP_BG = (21, 22, 25)
YEL = (238, 220, 66)
YEL_HI = (255, 240, 112)
YEL_DIM = (168, 156, 50)
WHITE = (235, 235, 232)
GRAY_TXT = (130, 133, 140)
PANEL = (58, 60, 64)
PANEL_DARK = (26, 27, 31)
CONTOUR = (58, 60, 68)
CONTOUR_IDX = (92, 95, 104)
CELL_LINE = (42, 44, 49)
ACH_ORANGE = (255, 160, 50)
ACH_GREEN = (90, 230, 140)
ACH_FULL_TEXT = "Hãy chạm cỏ đỏ bro"

FONT_NAMES = "consolas,couriernew,menlo,dejavusansmono,monospace"

# ---------- camera 3D ----------
YAW = math.radians(32)
PITCH = math.radians(52)
COS_Y, SIN_Y = math.cos(YAW), math.sin(YAW)
COS_P, SIN_P = math.cos(PITCH), math.sin(PITCH)
PERSP = 0.022          # do "xa nho gan to"
GAP = 0.06             # khe giua cac o
HATCH_N = 9            # so net gach cheo tren moi o
NORMALS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
LEVELS = [0.07 + 0.075 * i for i in range(12)]   # cac muc duong dong muc
Z_SCALE = 1.0
DOUBLE_CLICK = 0.40


# =====================================================================
#  File / game
# =====================================================================
def list_games():
    out = []
    for f in os.listdir(BASE_DIR):
        p = os.path.join(BASE_DIR, f)
        if (
            f.lower().endswith(GAME_EXTS)
            and f.lower() != SELF_NAME.lower()
            and not f.startswith("_")
            and os.path.isfile(p)
        ):
            out.append(f)
    return sorted(out, key=str.lower)


def import_files(paths):
    ok, skipped = 0, 0
    for src in paths:
        if not os.path.isfile(src) or not src.lower().endswith(GAME_EXTS):
            skipped += 1
            continue
        name = os.path.basename(src)
        dst = os.path.join(BASE_DIR, name)
        if os.path.abspath(src) == os.path.abspath(dst):
            skipped += 1
            continue
        stem, ext = os.path.splitext(name)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(BASE_DIR, "%s_%d%s" % (stem, i, ext))
            i += 1
        try:
            shutil.copy2(src, dst)
            ok += 1
        except OSError:
            skipped += 1
    return ok, skipped


TRASH_DIR = os.path.join(BASE_DIR, "_deleted")


def trash_game(name):
    """Chuyen game vao thu muc _deleted (van khoi phuc duoc). Tra ve True neu thanh cong."""
    src = os.path.join(BASE_DIR, name)
    try:
        os.makedirs(TRASH_DIR, exist_ok=True)
        stem, ext = os.path.splitext(name)
        dst = os.path.join(TRASH_DIR, name)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(TRASH_DIR, "%s_%d%s" % (stem, i, ext))
            i += 1
        shutil.move(src, dst)
        return True
    except OSError:
        return False


PICK_CODE = (
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
    "fs = filedialog.askopenfilenames(title='Chọn file game (.exe)',"
    " filetypes=[('Chương trình', '*.exe')])\n"
    "print('\\n'.join(fs))\n"
)


def _pick_inprocess():
    import tkinter as tk
    from tkinter import filedialog

    r = tk.Tk()
    r.withdraw()
    r.attributes("-topmost", True)
    fs = filedialog.askopenfilenames(
        title="Chọn file game (.exe)", filetypes=[("Chương trình", "*.exe")]
    )
    r.destroy()
    return list(fs)


def pick_files():
    """Mo hop thoai chon file trong 1 process rieng (an toan voi pygame tren moi he dieu hanh)."""
    if getattr(sys, "frozen", False):   # ban .exe khong co python de chay process phu
        try:
            return _pick_inprocess()
        except Exception:
            return []
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        out = subprocess.run(
            [sys.executable, "-c", PICK_CODE],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=900,
        )
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


_ACH_STATIC = {}   # ten game -> (mtime file .py cung ten, (ids, save_file) | None)
_ACH_SAVE = {}     # duong dan file save -> (mtime, set id da mo, tong | None)


def _static_achievements(path):
    """Doc ACHIEVEMENTS va SAVE_FILE tu ma nguon game (ast, khong chay game)."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    ids, save = None, "achievements.json"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            names, value = [node.target.id], node.value
        else:
            continue
        try:
            if "ACHIEVEMENTS" in names:
                data = ast.literal_eval(value)
                found = []
                for a in data:
                    if isinstance(a, dict) and "id" in a:
                        found.append(str(a["id"]))
                    elif isinstance(a, str):
                        found.append(a)
                ids = found
            elif "SAVE_FILE" in names:
                v = ast.literal_eval(value)
                if isinstance(v, str):
                    save = v
        except (ValueError, TypeError, SyntaxError):
            pass
    return (ids, save) if ids else None


def read_achievements(name):
    """Tra ve (da dat, tong) hoac None neu khong biet game co thanh tuu hay khong.

    Tong so thanh tuu lay tu: (1) file .py cung ten dat canh .exe (doc ACHIEVEMENTS + SAVE_FILE
    bang ast), hoac (2) khoa "total" ma game ghi trong file achievements.json.
    """
    src_path = os.path.join(BASE_DIR, os.path.splitext(name)[0] + ".py")
    static = None
    if os.path.isfile(src_path):
        try:
            gm = os.stat(src_path).st_mtime
        except OSError:
            gm = None
        cached = _ACH_STATIC.get(name)
        if cached is None or cached[0] != gm:
            cached = (gm, _static_achievements(src_path))
            _ACH_STATIC[name] = cached
        static = cached[1]
    ids, save = static if static else (None, "achievements.json")
    sp = save if os.path.isabs(save) else os.path.join(BASE_DIR, save)
    try:
        mt = os.stat(sp).st_mtime
    except OSError:
        mt = None
    entry = _ACH_SAVE.get(sp)
    if entry is None or entry[0] != mt:
        unlocked, total = set(), None
        if mt is not None:
            try:
                with open(sp, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                lst = data.get("unlocked", []) if isinstance(data, dict) else data
                unlocked = {str(i) for i in lst}
                if isinstance(data, dict) and isinstance(data.get("total"), int):
                    total = data["total"]
            except (OSError, ValueError, AttributeError, TypeError):
                unlocked, total = set(), None
        entry = (mt, unlocked, total)
        _ACH_SAVE[sp] = entry
    if ids:
        all_ids = set(ids)
        return len(all_ids & entry[1]), len(all_ids)
    if entry[2] and entry[2] > 0:
        return min(len(entry[1]), entry[2]), entry[2]
    return None


def fmt_size(n):
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%.1f MB" % (n / 1024.0 / 1024.0)


def file_info(name):
    try:
        st = os.stat(os.path.join(BASE_DIR, name))
        return fmt_size(st.st_size), time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
    except OSError:
        return "?", "?"


def trunc_mid(text, n):
    if len(text) <= n:
        return text
    n = max(5, n)
    keep = (n - 3) // 2
    return text[:keep] + "..." + text[-(n - 3 - keep):]


def minimize_window():
    try:
        from pygame._sdl2.video import Window

        Window.from_display_module().minimize()
    except Exception:
        try:
            pygame.display.iconify()
        except Exception:
            pass


def restore_window():
    try:
        from pygame._sdl2.video import Window

        w = Window.from_display_module()
        w.restore()
        w.focus()
    except Exception:
        pass


# =====================================================================
#  Dia hinh: duong dong muc (marching squares)
# =====================================================================
_CASES = {
    1: [(3, 2)], 2: [(2, 1)], 3: [(3, 1)], 4: [(0, 1)],
    5: [(0, 3), (2, 1)], 6: [(0, 2)], 7: [(0, 3)], 8: [(0, 3)],
    9: [(0, 2)], 10: [(0, 1), (3, 2)], 11: [(0, 1)], 12: [(3, 1)],
    13: [(2, 1)], 14: [(3, 2)],
}


def _edge(e, px, py, step, a, b, c, d, L):
    if e == 0:                      # canh tren a-b
        t = (L - a) / (b - a)
        return px + t * step, py
    if e == 1:                      # canh phai b-c
        t = (L - b) / (c - b)
        return px + step, py + t * step
    if e == 2:                      # canh duoi d-c
        t = (L - d) / (c - d)
        return px + t * step, py + step
    t = (L - a) / (d - a)           # canh trai a-d
    return px, py + t * step


def build_contours(cols, rows):
    """Tra ve list (muc, x1, y1, x2, y2). Quanh luoi game la mat phang bang (khong co duong)."""
    M, step = 7.0, 0.34
    x0 = y0 = -M
    nx = int((cols + 2 * M) / step) + 2
    ny = int((rows + 2 * M) / step) + 2

    def hgt(x, y):
        v = (
            math.sin(x * 0.52 + 1.3) * math.cos(y * 0.46 - 0.4)
            + 0.6 * math.sin(x * 0.21 + y * 0.29 + 2.0)
            + 0.35 * math.sin(x * 1.05 - y * 0.85 + 0.5)
        )
        h = (v + 1.95) / 3.9
        d = math.hypot(max(-x, 0.0, x - cols), max(-y, 0.0, y - rows))
        t = min(1.0, d / 3.2)
        return h * t * t * (3 - 2 * t)

    g = [[hgt(x0 + i * step, y0 + j * step) for i in range(nx)] for j in range(ny)]
    segs = []
    for j in range(ny - 1):
        r0, r1 = g[j], g[j + 1]
        for i in range(nx - 1):
            a, b, c, d = r0[i], r0[i + 1], r1[i + 1], r1[i]
            lo, hi = min(a, b, c, d), max(a, b, c, d)
            if hi < LEVELS[0] or lo > LEVELS[-1]:
                continue
            px, py = x0 + i * step, y0 + j * step
            for k, L in enumerate(LEVELS):
                if L < lo or L > hi:
                    continue
                code = (a > L) * 8 + (b > L) * 4 + (c > L) * 2 + (d > L)
                for e1, e2 in _CASES.get(code, ()):
                    p1 = _edge(e1, px, py, step, a, b, c, d, L)
                    p2 = _edge(e2, px, py, step, a, b, c, d, L)
                    segs.append((k, p1[0], p1[1], p2[0], p2[1]))
    return segs


# =====================================================================
#  Hinh hoc tien ich
# =====================================================================
def make_proj(origin, zoom, cam):
    """Phep chieu 3D (goc nhin cheo xuong, co phoi canh nhe) -> toa do man hinh."""
    ox, oy = origin
    cx, cy = cam

    def P(x, y, z=0.0):
        dx = x - cx
        dy = y - cy
        xr = dx * COS_Y - dy * SIN_Y
        yr = dx * SIN_Y + dy * COS_Y
        up = yr * SIN_P + z * COS_P
        dep = yr * COS_P - z * SIN_P
        p = 1.0 / (1.0 + PERSP * dep)
        return (ox + xr * p * zoom, oy - up * p * zoom)

    return P


def point_in_poly(pt, poly):
    x, y = pt
    sign = 0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cr = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if cr != 0:
            sg = 1 if cr > 0 else -1
            if sign == 0:
                sign = sg
            elif sign != sg:
                return False
    return True


def skew_poly(x, y, w, h, k):
    return [(x + k, y), (x + w, y), (x + w - k, y + h), (x, y + h)]


def band_poly(c, r_in, r_out, a0, a1, steps=28):
    pts_o = []
    pts_i = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        ca, sa = math.cos(a), -math.sin(a)
        pts_o.append((c[0] + ca * r_out, c[1] + sa * r_out))
        pts_i.append((c[0] + ca * r_in, c[1] + sa * r_in))
    return pts_o + pts_i[::-1]


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# =====================================================================
#  Ung dung
# =====================================================================
class App:
    def __init__(self, windowed=False):
        pygame.init()
        pygame.display.set_caption("BẢN ĐỒ GAME")
        if windowed:
            self.screen = pygame.display.set_mode((1600, 900))
        else:
            # (0, 0) + FULLSCREEN = dung do phan giai that cua man hinh
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.W, self.H = self.screen.get_size()
        self.s = self.H / 1080.0          # he so ti le UI theo do phan giai
        self.clock = pygame.time.Clock()
        self.fonts = {}

        self.R = int(min(self.H * 0.40, self.W * 0.30))
        self.ccx, self.ccy = self.W // 2, int(self.H * 0.46)
        self.map_rect = pygame.Rect(self.ccx - self.R, self.ccy - self.R, 2 * self.R, 2 * self.R)
        self.build_background()
        self.contour_surf = pygame.Surface(self.map_rect.size, pygame.SRCALPHA)
        self.contour_key = None
        self.layout_buttons()
        self.dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 175))
        self.confirm = None
        self.dlg = {}

        self.games = []
        self.selected = None
        self.hover = None
        self.hit = []
        self.hcur = {}
        self.cols = self.rows = 0
        self.segs = []
        self.fit = 100.0
        self.zoom = self.zoom_t = 1.0
        self.cam = self.cam_target = (0.0, 0.0)
        self.proc = None
        self.msg = ""
        self.msg_until = 0.0
        self.last_click_t = 0.0
        self.last_click_idx = None
        self.refresh()
        self.cam = self.cam_target

    # ----- tai nguyen -----
    def font(self, size, bold=False):
        size = max(8, int(size))
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont(FONT_NAMES, size, bold)
        return self.fonts[key]

    def text(self, txt, size, color, pos, anchor="topleft", bold=False):
        img = self.font(size, bold).render(txt, True, color)
        r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        self.screen.blit(img, r)
        return r

    def build_background(self):
        bg = pygame.Surface((self.W, self.H)).convert()
        bg.fill(BG)
        step = max(24, int(48 * self.s))
        for y in range(step // 2, self.H, step):
            for x in range(step // 2, self.W, step):
                bg.set_at((x, y), (30, 31, 35))
        arm = max(3, int(6 * self.s))
        for gy, y in enumerate(range(step // 2, self.H, step)):
            for gx, x in enumerate(range(step // 2, self.W, step)):
                if gx % 4 == 0 and gy % 4 == 0:
                    pygame.draw.line(bg, (46, 48, 53), (x - arm, y), (x + arm, y), 1)
                    pygame.draw.line(bg, (46, 48, 53), (x, y - arm), (x, y + arm), 1)
        self.bg = bg
        ov = bg.subsurface(self.map_rect).copy().convert_alpha()
        pygame.draw.circle(ov, (0, 0, 0, 0), (self.R, self.R), self.R)
        self.overlay = ov

    def layout_buttons(self):
        s, W, H = self.s, self.W, self.H
        bw, bh = int(W * 0.165), int(H * 0.075)
        gap = int(10 * s)
        y = int(H * 0.885)
        x1 = W // 2 - (3 * bw + 2 * gap) // 2
        self.btn = {
            "import": pygame.Rect(x1, y, bw, bh),
            "run": pygame.Rect(x1 + bw + gap, y, bw, bh),
            "delete": pygame.Rect(x1 + 2 * (bw + gap), y, bw, bh),
            "exit": pygame.Rect(W - int(40 * s) - int(150 * s), int(0.04 * H), int(150 * s), int(0.05 * H)),
        }

    # ----- du lieu -----
    def notify(self, msg, dur=4.0):
        self.msg = msg
        self.msg_until = time.time() + dur

    def refresh(self, msg=None):
        keep = self.games[self.selected] if self.selected is not None and self.selected < len(self.games) else None
        self.games = list_games()
        self.selected = self.games.index(keep) if keep in self.games else None
        self.layout_grid()
        if msg:
            self.notify(msg)

    def layout_grid(self):
        n = len(self.games)
        cols = max(5, int(math.ceil(math.sqrt(max(n, 1)) * 1.35)))
        rows = max(4, int(math.ceil(n / float(cols))) + 1)
        if (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self.segs = build_contours(cols, rows)
            P = make_proj((0, 0), 1.0, (cols / 2.0, rows / 2.0))
            maxd = max(
                math.hypot(*P(x, y, 0.0))
                for x, y in [(0, 0), (cols, 0), (cols, rows), (0, rows)]
            )
            self.fit = self.R * 0.82 / maxd
            self.contour_key = None

    def cell_xy(self, idx):
        r, c = divmod(idx, self.cols)
        return c, self.rows - 1 - r        # hang dau tien nam o phia xa (tren cung)

    # ----- hanh dong -----
    def do_import(self, paths=None):
        if paths is None:
            minimize_window()
            paths = pick_files()
            restore_window()
        if not paths:
            return
        ok, skipped = import_files(paths)
        msg = "ĐÃ NHẬP %d FILE" % ok
        if skipped:
            msg += " / BỎ QUA %d" % skipped
        self.refresh(msg)

    def do_run(self):
        if self.proc is not None:
            return
        if self.selected is None or self.selected >= len(self.games):
            self.notify("CHƯA CHỌN KHU VỰC")
            return
        name = self.games[self.selected]
        try:
            self.proc = subprocess.Popen([os.path.join(BASE_DIR, name)], cwd=BASE_DIR)
            self.notify("ĐANG CHẠY: " + name, 3600)
            minimize_window()
        except OSError:
            self.proc = None
            self.notify("KHÔNG CHẠY ĐƯỢC: " + name)

    def ask_delete(self):
        if self.proc is not None:
            return
        if self.selected is None or self.selected >= len(self.games):
            self.notify("CHƯA CHỌN KHU VỰC")
            return
        self.confirm = self.games[self.selected]

    def do_delete(self):
        name, self.confirm = self.confirm, None
        if not name:
            return
        idx = self.games.index(name) if name in self.games else 0
        if trash_game(name):
            self.hcur.pop(name, None)
            self.games = list_games()
            self.selected = min(idx, len(self.games) - 1) if self.games else None
            self.layout_grid()
            self.notify("ĐÃ XÓA: " + name)
        else:
            self.notify("KHÔNG XÓA ĐƯỢC: " + name)

    def pick(self, pos):
        if math.hypot(pos[0] - self.ccx, pos[1] - self.ccy) > self.R:
            return None
        for idx, poly in reversed(self.hit):
            if point_in_poly(pos, poly):
                return idx
        return None

    # ----- su kien -----
    def on_click(self, pos):
        if self.confirm:
            if self.dlg.get("yes") and self.dlg["yes"].collidepoint(pos):
                self.do_delete()
            elif self.dlg.get("no") and self.dlg["no"].collidepoint(pos):
                self.confirm = None
            return
        if self.btn["exit"].collidepoint(pos):
            raise SystemExit
        if self.btn["import"].collidepoint(pos):
            self.do_import()
            return
        if self.btn["run"].collidepoint(pos):
            self.do_run()
            return
        if self.btn["delete"].collidepoint(pos):
            self.ask_delete()
            return
        idx = self.pick(pos)
        if idx is None:
            if math.hypot(pos[0] - self.ccx, pos[1] - self.ccy) <= self.R:
                self.selected = None
            return
        now = time.time()
        if idx == self.selected or (idx == self.last_click_idx and now - self.last_click_t < DOUBLE_CLICK):
            self.selected = idx
            self.do_run()
        else:
            self.selected = idx
        self.last_click_t = now
        self.last_click_idx = idx

    def on_key(self, key):
        if self.confirm:
            if key == pygame.K_y:
                self.do_delete()
            elif key in (pygame.K_ESCAPE, pygame.K_n):
                self.confirm = None
            return
        if key == pygame.K_ESCAPE:
            raise SystemExit
        if key == pygame.K_DELETE:
            self.ask_delete()
            return
        if key == pygame.K_F5:
            self.refresh("ĐÃ QUÉT LẠI: %d GAME" % len(list_games()))
            return
        if not self.games:
            return
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.do_run()
            return
        step = {
            pygame.K_LEFT: -1, pygame.K_RIGHT: 1,
            pygame.K_UP: -self.cols, pygame.K_DOWN: self.cols,
        }.get(key)
        if step is None:
            return
        if self.selected is None:
            self.selected = 0
        else:
            self.selected = max(0, min(len(self.games) - 1, self.selected + step))

    # ----- cap nhat -----
    def update(self, dt):
        k = min(1.0, dt * 8.0)
        self.zoom += (self.zoom_t - self.zoom) * k
        if abs(self.zoom - self.zoom_t) < 1e-3:
            self.zoom = self.zoom_t
        c0 = (self.cols / 2.0, self.rows / 2.0)
        tgt = c0
        if self.selected is not None and self.selected < len(self.games) and self.zoom_t > 1.05:
            tx, ty = self.cell_xy(self.selected)
            w = min(1.0, 0.35 + (self.zoom_t - 1.0) * 0.65)
            tgt = (c0[0] + (tx + 0.5 - c0[0]) * w, c0[1] + (ty + 0.5 - c0[1]) * w)
        self.cam_target = tgt
        cx = self.cam[0] + (tgt[0] - self.cam[0]) * k
        cy = self.cam[1] + (tgt[1] - self.cam[1]) * k
        if abs(cx - tgt[0]) < 1e-3 and abs(cy - tgt[1]) < 1e-3:
            cx, cy = tgt
        self.cam = (cx, cy)

    # ----- ve ban do -----
    def render_contours(self, zoom):
        surf = self.contour_surf
        surf.fill((0, 0, 0, 0))
        R = self.R
        P = make_proj((R, R), zoom, self.cam)
        w1 = max(1, int(self.s * 1.2))
        w2 = max(1, int(self.s * 1.7))
        lim = (R * 1.04) ** 2
        for k, x1, y1, x2, y2 in self.segs:
            z = LEVELS[k] * Z_SCALE
            a = P(x1, y1, z)
            b = P(x2, y2, z)
            if (a[0] - R) ** 2 + (a[1] - R) ** 2 > lim and (b[0] - R) ** 2 + (b[1] - R) ** 2 > lim:
                continue
            if k % 3 == 0:
                pygame.draw.line(surf, CONTOUR_IDX, a, b, w2)
            else:
                pygame.draw.line(surf, CONTOUR, a, b, w1)

    def draw_map(self, dt, t):
        scr, s = self.screen, self.s
        zoom = self.fit * self.zoom
        P = make_proj((self.ccx, self.ccy), zoom, self.cam)

        scr.set_clip(self.map_rect)
        pygame.draw.rect(scr, MAP_BG, self.map_rect)

        key = (round(self.cam[0], 3), round(self.cam[1], 3), round(zoom, 3))
        if key != self.contour_key:
            self.render_contours(zoom)
            self.contour_key = key
        scr.blit(self.contour_surf, self.map_rect.topleft)

        n = len(self.games)
        cx0, cy0 = self.cam
        self.hit = []

        # o trong (mat phang)
        for idx in range(n, self.cols * self.rows):
            x, y = self.cell_xy(idx)
            x0, x1, y0, y1 = x + GAP, x + 1 - GAP, y + GAP, y + 1 - GAP
            poly = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
            pygame.draw.polygon(scr, CELL_LINE, poly, 1)
            c = P(x + 0.5, y + 0.5)
            pygame.draw.circle(scr, CELL_LINE, (int(c[0]), int(c[1])), max(1, int(2 * s)))

        # cac game: ve tu xa den gan
        order = []
        for idx in range(n):
            x, y = self.cell_xy(idx)
            yr = (x + 0.5 - cx0) * SIN_Y + (y + 0.5 - cy0) * COS_Y
            order.append((-yr, idx))
        order.sort()
        for _, idx in order:
            self.draw_tile(P, idx, zoom, dt, t)

        scr.set_clip(None)
        scr.blit(self.overlay, self.map_rect.topleft)

    def draw_tile(self, P, idx, zoom, dt, t):
        scr, s = self.screen, self.s
        name = self.games[idx]
        sel = idx == self.selected
        hov = idx == self.hover and not sel
        target = 0.60 if sel else (0.24 if hov else 0.08)
        h = self.hcur.get(name, 0.0)
        h += (target - h) * min(1.0, dt * 12.0)
        self.hcur[name] = h

        x, y = self.cell_xy(idx)
        x0, x1, y0, y1 = x + GAP, x + 1 - GAP, y + GAP, y + 1 - GAP
        wc = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        top = [P(a, b, h) for a, b in wc]
        bot = [P(a, b, 0.0) for a, b in wc]
        self.hit.append((idx, bot))

        if sel:
            fill, hatch, edge, txt = YEL, YEL_HI, (255, 250, 190), (22, 22, 18)
            side_a, side_b = (176, 160, 44), (132, 120, 32)
        elif hov:
            fill, hatch, edge, txt = (86, 80, 28), (140, 130, 40), YEL, (250, 244, 190)
            side_a, side_b = (60, 56, 22), (44, 41, 16)
        else:
            fill, hatch, edge, txt = (50, 48, 22), (92, 86, 32), YEL_DIM, (226, 218, 150)
            side_a, side_b = (36, 34, 15), (26, 25, 11)

        if sel:  # vong tron xung quanh o dang chon
            r = 0.64 + 0.05 * math.sin(t * 3.2)
            cc = (x + 0.5, y + 0.5)
            ring = [P(cc[0] + r * math.cos(a * math.pi / 14), cc[1] + r * math.sin(a * math.pi / 14), 0.0) for a in range(28)]
            pygame.draw.polygon(scr, YEL_DIM, ring, max(1, int(2 * s)))

        for i, (nx, ny) in enumerate(NORMALS):
            if nx * SIN_Y + ny * COS_Y < 0:      # mat huong ve phia nguoi nhin
                j = (i + 1) % 4
                pygame.draw.polygon(scr, side_a if i % 2 else side_b, [top[i], top[j], bot[j], bot[i]])
        pygame.draw.polygon(scr, fill, top)

        # net gach cheo (hatch) giong vung vang tren ban do
        for k in range(1, HATCH_N):
            c = 2.0 * k / HATCH_N
            if c <= 1.0:
                u1, v1, u2, v2 = c, 0.0, 0.0, c
            else:
                u1, v1, u2, v2 = 1.0, c - 1.0, c - 1.0, 1.0
            pa = P(x0 + u1 * (x1 - x0), y0 + v1 * (y1 - y0), h)
            pb = P(x0 + u2 * (x1 - x0), y0 + v2 * (y1 - y0), h)
            pygame.draw.line(scr, hatch, pa, pb, 1)
        pygame.draw.polygon(scr, edge, top, max(1, int(s * (3 if sel else 2))))

        # ten game (chu nam phang tren o, nhu nhan "THE HUB")
        ctr = P(x + 0.5, y + 0.5, h)
        xs = [p[0] for p in top]
        span = (max(xs) - min(xs)) * 0.60
        fs = max(10 * s, min(zoom * 0.115, 22 * s))
        maxc = max(4, int(span / (0.6 * fs)))
        stem = os.path.splitext(name)[0].upper()
        lines = textwrap.wrap(stem, maxc, break_long_words=True) or [stem]
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] = lines[-1][: max(1, maxc - 2)] + ".."
        lh = self.font(fs, True).get_linesize()
        yy = ctr[1] - lh * len(lines) / 2.0 + (4 * s if sel else 0)
        for ln in lines:
            self.text(ln, fs, txt, (ctr[0], yy), "midtop", True)
            yy += lh

        if sel:  # mui ten + duong ke vang giong con tro tren ban do
            ax, ay = ctr[0], ctr[1] - 30 * s
            pygame.draw.line(scr, YEL, (ax, ay - 12 * s), (ax, ay - self.R * 0.30), max(2, int(2 * s)))
            a = 12 * s
            arrow = [(ax, ay - a), (ax + 0.85 * a, ay + 0.9 * a), (ax, ay + 0.4 * a), (ax - 0.85 * a, ay + 0.9 * a)]
            pygame.draw.polygon(scr, WHITE, arrow)

    # ----- vong tron + HUD -----
    def draw_ring(self, t):
        scr, s, R = self.screen, self.s, self.R
        c = (self.ccx, self.ccy)
        th = int(14 * s)
        pygame.draw.circle(scr, PANEL, c, R + th, th)
        pygame.draw.circle(scr, (12, 12, 14), c, R, max(1, int(2 * s)))
        pygame.draw.circle(scr, (104, 106, 112), c, R + th + int(7 * s), max(1, int(2 * s)))
        # vach chia o 4 huong
        for a in (0, 90, 180, 270):
            r1, r2 = R - int(14 * s), R
            ca, sa = math.cos(math.radians(a)), -math.sin(math.radians(a))
            pygame.draw.line(scr, (140, 142, 148), (c[0] + ca * r1, c[1] + sa * r1), (c[0] + ca * r2, c[1] + sa * r2), max(1, int(2 * s)))
        # cung vang co dinh + cung quay
        pygame.draw.polygon(scr, YEL, band_poly(c, R + int(3 * s), R + th - int(2 * s), math.radians(200), math.radians(236)))
        ang = math.radians((t * 36) % 360)
        pygame.draw.polygon(scr, YEL, band_poly(c, R + int(3 * s), R + th - int(2 * s), ang, ang + math.radians(16)))

    def draw_button(self, key, label, enabled, mouse):
        scr, s = self.screen, self.s
        rect = self.btn[key]
        k = int(22 * s)
        hov = enabled and rect.collidepoint(mouse)
        if key == "delete":
            base = (112, 114, 120) if hov else ((70, 72, 78) if enabled else (36, 37, 41))
        else:
            base = YEL_HI if hov else (YEL if enabled else (86, 82, 40))
        poly = skew_poly(rect.x, rect.y, rect.w, rect.h, k)
        pygame.draw.polygon(scr, base, poly)
        pygame.draw.polygon(scr, (22, 22, 18), poly, max(1, int(2 * s)))
        pygame.draw.line(scr, mix(base, (0, 0, 0), 0.25), (rect.x + 4 * s, rect.bottom - 6 * s), (rect.right - k - 4 * s, rect.bottom - 6 * s), max(1, int(3 * s)))
        ic = (rect.x + k + int(34 * s), rect.centery)
        dark = WHITE if key == "delete" else (22, 22, 18)
        a = int(11 * s)
        if key == "delete":
            wd = max(2, int(4 * s))
            pygame.draw.line(scr, dark, (ic[0] - a, ic[1] - a), (ic[0] + a, ic[1] + a), wd)
            pygame.draw.line(scr, dark, (ic[0] - a, ic[1] + a), (ic[0] + a, ic[1] - a), wd)
        elif key == "import":
            pygame.draw.line(scr, dark, (ic[0] - a, ic[1]), (ic[0] + a, ic[1]), max(2, int(4 * s)))
            pygame.draw.line(scr, dark, (ic[0], ic[1] - a), (ic[0], ic[1] + a), max(2, int(4 * s)))
        else:
            pygame.draw.polygon(scr, dark, [(ic[0] - a * 0.7, ic[1] - a), (ic[0] + a, ic[1]), (ic[0] - a * 0.7, ic[1] + a)])
        self.text(label, 28 * s, dark, (rect.x + k + int(70 * s), rect.centery), "midleft", True)

    def panel(self, x, y, w, h):
        scr, s = self.screen, self.s
        poly = skew_poly(x, y, w, h, int(18 * s))
        pygame.draw.polygon(scr, PANEL_DARK, poly)
        pygame.draw.polygon(scr, (70, 72, 78), poly, max(1, int(s)))
        pygame.draw.line(scr, YEL, (x + 18 * s, y + 2 * s), (x + 18 * s + 70 * s, y + 2 * s), max(2, int(3 * s)))

    def draw_hud(self, mouse):
        scr, s, W, H = self.screen, self.s, self.W, self.H
        m = int(40 * s)
        n = len(self.games)

        # tieu de tren trai
        y0, pw, ph = int(0.04 * H), int(380 * s), int(0.07 * H)
        poly = skew_poly(m, y0, pw, ph, int(18 * s))
        pygame.draw.polygon(scr, PANEL, poly)
        pygame.draw.polygon(scr, (20, 21, 24), poly, max(1, int(2 * s)))
        self.text("BẢN ĐỒ GAME", 32 * s, WHITE, (m + 36 * s, y0 + ph / 2), "midleft", True)
        cur = (self.selected + 1) if self.selected is not None else 0
        self.text("%02d/%02d" % (cur, n), 24 * s, YEL, (m + pw - 44 * s, y0 + ph / 2), "midright", True)

        # nut thoat
        er = self.btn["exit"]
        ep = skew_poly(er.x, er.y, er.w, er.h, int(14 * s))
        pygame.draw.polygon(scr, (90, 92, 98) if er.collidepoint(mouse) else PANEL, ep)
        pygame.draw.polygon(scr, (20, 21, 24), ep, max(1, int(2 * s)))
        self.text("THOÁT [ESC]", 20 * s, WHITE, er.center, "center", True)

        # panel trai / phai (neu man hinh du rong)
        avail = W // 2 - self.R - int(60 * s) - m
        if avail > 220 * s:
            pw2 = int(min(avail, 400 * s))
            py = int(H * 0.22)
            ph2 = int(H * 0.40)
            self.draw_info_panel(W - m - pw2, py, pw2, ph2)
            self.draw_help_panel(m, int(H * 0.22), pw2, ph2)

        # so khu vuc ben duoi trai
        by = int(H * 0.775)
        self.text("KHU VỰC", 18 * s, GRAY_TXT, (m, by), "topleft", True)
        num = "%02d" % (self.selected + 1) if self.selected is not None else "--"
        self.text(num, 66 * s, WHITE, (m, by + 22 * s), "topleft", True)
        pygame.draw.circle(scr, GRAY_TXT, (int(m + 150 * s), int(by + 62 * s)), int(11 * s), max(1, int(2 * s)))
        self.text("i", 16 * s, GRAY_TXT, (m + 150 * s, by + 62 * s), "center", True)

        # thong ke ben duoi phai
        info = "%d GAME  |  LƯỚI %dx%d" % (n, self.cols, self.rows)
        self.text("THƯ MỤC", 18 * s, GRAY_TXT, (W - m, by), "topright", True)
        self.text(info, 24 * s, YEL, (W - m, by + 28 * s), "topright", True)

        # hai nut vang
        self.draw_button("import", "THÊM GAME", True, mouse)
        can = self.selected is not None and self.proc is None
        self.draw_button("run", "CHẠY", can, mouse)
        self.draw_button("delete", "XÓA", can, mouse)

        # thanh trang thai
        txt = self.msg if time.time() < self.msg_until else trunc_mid(BASE_DIR, int(W * 0.5 / (0.6 * 16 * s)))
        col = YEL if time.time() < self.msg_until else GRAY_TXT
        self.text(txt, 16 * s, col, (W // 2, H - int(0.026 * H)), "center", True)

    def draw_info_panel(self, x, y, w, h):
        s = self.s
        self.panel(x, y, w, h)
        pad = int(26 * s)
        yy = y + int(22 * s)
        self.text("// KHU VỰC ĐANG CHỌN", 18 * s, YEL, (x + pad, yy), "topleft", True)
        yy += int(44 * s)
        if self.selected is None or self.selected >= len(self.games):
            self.text("CHƯA CHỌN KHU VỰC", 24 * s, WHITE, (x + pad, yy), "topleft", True)
            self.text("BẤM VÀO MỘT Ô TRÊN BẢN ĐỒ", 16 * s, GRAY_TXT, (x + pad, yy + 40 * s), "topleft", True)
            self.text("HOẶC KÉO-THẢ FILE .EXE VÀO ĐÂY", 16 * s, GRAY_TXT, (x + pad, yy + 64 * s), "topleft", True)
            return
        name = self.games[self.selected]
        maxc = max(8, int((w - 2 * pad) / (0.6 * 28 * s)))
        lines = textwrap.wrap(os.path.splitext(name)[0].upper(), maxc, break_long_words=True)[:3]
        for ln in lines:
            self.text(ln, 28 * s, WHITE, (x + pad, yy), "topleft", True)
            yy += int(36 * s)
        yy += int(14 * s)
        self.text("THÀNH TỰU", 16 * s, GRAY_TXT, (x + pad, yy + 3 * s), "topleft", True)
        ach = read_achievements(name)
        if ach is None:
            self.text("KHÔNG CÓ", 18 * s, GRAY_TXT, (x + pad + 125 * s, yy + 2 * s), "topleft", True)
        else:
            got, total = ach
            pct = got * 100.0 / total
            vx = x + pad + 125 * s
            if got >= total:
                fs = min(22 * s, (w - 2 * pad - 125 * s) / (0.6 * len(ACH_FULL_TEXT)))
                self.text(ACH_FULL_TEXT, fs, ACH_GREEN, (vx, yy), "topleft", True)
            else:
                col = ACH_GREEN if pct >= 80 else (ACH_ORANGE if pct >= 50 else WHITE)
                r = self.text("%d/%d" % (got, total), 24 * s, col, (vx, yy - 2 * s), "topleft", True)
                self.text("%d%%" % int(pct), 16 * s, GRAY_TXT, (r.right + 12 * s, yy + 4 * s), "topleft", True)
        yy += int(38 * s)
        size, mtime = file_info(name)
        cw = 0.6 * 18 * s
        vmax = max(6, int((w - 2 * pad - 125 * s) / cw))
        for label, val in (("TỆP", name), ("DUNG LƯỢNG", size), ("SỬA LÚC", mtime), ("THƯ MỤC", BASE_DIR)):
            self.text(label, 16 * s, GRAY_TXT, (x + pad, yy), "topleft", True)
            self.text(trunc_mid(val, vmax), 18 * s, WHITE, (x + pad + 125 * s, yy - 1 * s), "topleft", True)
            yy += int(34 * s)

    def draw_help_panel(self, x, y, w, h):
        s = self.s
        self.panel(x, y, w, h)
        pad = int(26 * s)
        yy = y + int(22 * s)
        self.text("// ĐIỀU KHIỂN", 18 * s, YEL, (x + pad, yy), "topleft", True)
        yy += int(44 * s)
        rows = [
            ("BẤM CHUỘT", "CHỌN / CHẠY"),
            ("MŨI TÊN", "DI CHUYỂN"),
            ("ENTER", "CHẠY GAME"),
            ("CON LĂN", "ZOOM BẢN ĐỒ"),
            ("F5", "QUÉT LẠI THƯ MỤC"),
            ("KÉO-THẢ .EXE", "THÊM GAME"),
            ("DEL", "XÓA GAME"),
            ("ESC", "THOÁT MENU"),
        ]
        for k, v in rows:
            self.text(k, 17 * s, YEL_DIM, (x + pad, yy), "topleft", True)
            self.text(v, 17 * s, WHITE, (x + pad + 150 * s, yy), "topleft", True)
            yy += int(33 * s)

    def draw_dialog(self, mouse):
        scr, s = self.screen, self.s
        scr.blit(self.dim, (0, 0))
        w, h = int(640 * s), int(300 * s)
        x, y = (self.W - w) // 2, (self.H - h) // 2
        self.panel(x, y, w, h)
        pad = int(34 * s)
        self.text("// XÓA KHU VỰC NÀY?", 20 * s, YEL, (x + pad, y + 30 * s), "topleft", True)
        name = trunc_mid(self.confirm, int((w - 2 * pad) / (0.6 * 30 * s)))
        self.text(name, 30 * s, WHITE, (x + pad, y + 78 * s), "topleft", True)
        self.text("FILE ĐƯỢC CHUYỂN VÀO THƯ MỤC _deleted (KHÔI PHỤC ĐƯỢC)", 16 * s, GRAY_TXT, (x + pad, y + 128 * s), "topleft", True)
        bw, bh = int(250 * s), int(60 * s)
        by = y + h - bh - int(30 * s)
        self.dlg = {
            "yes": pygame.Rect(x + pad, by, bw, bh),
            "no": pygame.Rect(x + w - pad - bw, by, bw, bh),
        }
        for key, label in (("yes", "XÁC NHẬN [Y]"), ("no", "HỦY [N]")):
            rect = self.dlg[key]
            hov = rect.collidepoint(mouse)
            poly = skew_poly(rect.x, rect.y, rect.w, rect.h, int(16 * s))
            if key == "yes":
                base, tc = (YEL_HI if hov else YEL), (22, 22, 18)
            else:
                base, tc = ((110, 112, 118) if hov else PANEL), WHITE
            pygame.draw.polygon(scr, base, poly)
            pygame.draw.polygon(scr, (22, 22, 18), poly, max(1, int(2 * s)))
            self.text(label, 24 * s, tc, rect.center, "center", True)

    def draw(self, dt, t):
        mouse = pygame.mouse.get_pos()
        self.hover = self.pick(mouse)
        self.screen.blit(self.bg, (0, 0))
        self.draw_map(dt, t)
        self.draw_ring(t)
        self.draw_hud(mouse)
        if self.confirm:
            self.draw_dialog(mouse)
        pygame.display.flip()

    # ----- vong lap chinh -----
    def run(self):
        t0 = time.time()
        while True:
            dt = min(0.05, self.clock.tick(60 if self.proc is None else 15) / 1000.0)
            t = time.time() - t0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.on_click(e.pos)
                elif e.type == pygame.MOUSEWHEEL:
                    self.zoom_t = max(0.8, min(2.6, self.zoom_t * (1.12 ** e.y)))
                elif e.type == pygame.KEYDOWN:
                    self.on_key(e.key)
                elif e.type == pygame.DROPFILE:
                    self.do_import([e.file])
            if self.proc is not None and self.proc.poll() is not None:
                code = self.proc.returncode
                self.proc = None
                restore_window()
                self.notify("ĐÃ ĐÓNG GAME (mã thoát %s)" % code)
            self.update(dt)
            self.draw(dt, t)


def main():
    app = App(windowed="--windowed" in sys.argv)
    try:
        app.run()
    except SystemExit:
        pass
    finally:
        if app.proc is not None and app.proc.poll() is None:
            pass  # de game tiep tuc chay neu nguoi dung thoat menu
        pygame.quit()


if __name__ == "__main__":
    main()
