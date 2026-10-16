# -*- coding: utf-8 -*-
"""
ĐÀO VÀNG - Sinh viên sinh tồn (Python + pygame)
Cài đặt:  pip install pygame
Chạy:     python dao_vang.py

Nếu chữ tiếng Việt bị lỗi font: chép 1 file font hỗ trợ tiếng Việt (vd Arial, Roboto)
vào cùng thư mục với file này và đặt tên là  font.ttf  (bản đậm: font_bold.ttf).
"""
import os, sys, json, math, random, re, colorsys, unicodedata
import pygame

W, H = 800, 500          # toạ độ logic của game (luôn là 800x500)
SC = 1.0                 # hệ số phóng to khi vẽ ra cửa sổ thật (giữ nét, không bị mờ)
OX, OY = W // 2, 70
TIME = 50
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dao_vang_save.json")

BIG = [
    ("Đầu tháng", ["Căn tin", "Hội trường", "Thư viện", "Cổng trường", "Lớp học"]),
    ("Deadline", ["Thư viện 2", "Lớp học 2", "Phòng thực hành", "Quán cà phê"]),
    ("Cuối tháng", ["Thư viện 3", "Lớp học 3", "Căn tin 2", "Quán cơm tấm", "Nhà trọ"]),
    ("Mùa thi", ["Thư viện 4", "Lớp học 4", "Căn tin 3", "Phòng thực hành 2", "Nhà trọ 2", "Phòng thi"]),
]
LV = []
for _bi, (_bn, _maps) in enumerate(BIG):
    for _mi, _name in enumerate(_maps):
        LV.append({"name": _name, "bi": _bi, "mi": _mi, "hue": (len(LV) * 47) % 360})

UPGRADES = [
    ("rope", "Dây kéo bền", "Thu dây nhanh hơn 10% mỗi cấp", 200, 5),
    ("steel", "Móc thép", "Kéo vật nặng dễ hơn", 350, 3),
    ("bag", "Ba lô sinh viên", "Tăng 15% điểm thưởng mỗi cấp", 400, 3),
    ("coffee", "Cà phê tăng lực", "Tăng tốc kéo 5 giây (phím C), dùng 1 lần", 150, 99),
    ("mag", "Nam châm mini", "Hút vật nhẹ ở gần", 500, 1),
]
# tên, bán kính, giá trị, tốc độ kéo, màu
TYPES = [
    ("gs", 14, 50, 5, (245, 197, 24)),
    ("gl", 28, 200, 2, (224, 168, 0)),
    ("rock", 22, 20, 1.5, (125, 125, 125)),
    ("gem", 9, 300, 6, (79, 214, 255)),
]
PT = [0, 0.3, 0.6, 1.0]   # điểm môn theo số sao (0,1,2,3 sao)


def stars_of(score):
    return 3 if score >= 1000 else 2 if score >= 900 else 1 if score >= 800 else 0


# ======================================================================
#  Lớp vẽ: mọi hàm vẽ nhận toạ độ logic và tự nhân với SC
# ======================================================================
def P(v):
    return int(round(v * SC))


def col(c):
    """Nhận '#rgb', '#rrggbb' hoặc tuple -> tuple số nguyên."""
    if isinstance(c, str):
        c = c.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    return tuple(int(v) for v in c)


def hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def R(s, c, x, y, w, h):
    x0, y0, x1, y1 = P(x), P(y), P(x + w), P(y + h)
    pygame.draw.rect(s, col(c), (x0, y0, max(1, x1 - x0), max(1, y1 - y0)))


def RO(s, c, x, y, w, h, wd=1):
    x0, y0, x1, y1 = P(x), P(y), P(x + w), P(y + h)
    pygame.draw.rect(s, col(c), (x0, y0, max(1, x1 - x0), max(1, y1 - y0)), max(1, P(wd)))


def C(s, c, x, y, r):
    pygame.draw.circle(s, col(c), (P(x), P(y)), max(1, P(r)))


def CO(s, c, x, y, r, wd=1):
    pygame.draw.circle(s, col(c), (P(x), P(y)), max(2, P(r)), max(1, P(wd)))


def L_(s, c, a, b, w=2):
    pygame.draw.line(s, col(c), (P(a[0]), P(a[1])), (P(b[0]), P(b[1])), max(1, P(w)))


def poly(s, c, pts, wd=0):
    pygame.draw.polygon(s, col(c), [(P(x), P(y)) for x, y in pts], wd)


def star(s, cx, cy, r, color, filled=True):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    poly(s, color, pts, 0 if filled else max(1, P(1.5)))


def heart(s, x, y, size, color):
    r = size / 4.0
    C(s, color, x - r, y, r)
    C(s, color, x + r, y, r)
    poly(s, color, [(x - 2 * r, y + 1), (x + 2 * r, y + 1), (x, y + 3 * r)])


# ---------------------------------------------------------------- font
FONT_REG = None
FONT_BOLD = None
VN_OK = False
_fonts = {}


def _has_vn(path):
    try:
        f = pygame.font.Font(path, 20)
        m = f.metrics("ĂăÂâÊêÔôƠơƯưĐđẮệỜữỵ")
        return all(x is not None for x in m)
    except Exception:
        return False


def find_fonts():
    here = os.path.dirname(os.path.abspath(__file__))
    pairs = [(os.path.join(here, "font.ttf"), os.path.join(here, "font_bold.ttf")),
             (os.path.join(here, "fonts", "font.ttf"), os.path.join(here, "fonts", "font_bold.ttf"))]
    win = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    for r, b in (("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf"), ("tahoma.ttf", "tahomabd.ttf"),
                 ("calibri.ttf", "calibrib.ttf"), ("verdana.ttf", "verdanab.ttf")):
        pairs.append((os.path.join(win, r), os.path.join(win, b)))
    for d in ("/System/Library/Fonts/Supplemental/", "/Library/Fonts/"):
        pairs.append((d + "Arial.ttf", d + "Arial Bold.ttf"))
        pairs.append((d + "Tahoma.ttf", d + "Tahoma Bold.ttf"))
    for d in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/TTF/", "/usr/share/fonts/dejavu/"):
        pairs.append((d + "DejaVuSans.ttf", d + "DejaVuSans-Bold.ttf"))
    pairs.append(("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"))
    pairs.append(("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"))
    for name in ("segoeui", "arial", "tahoma", "dejavusans", "notosans", "liberationsans", "freesans"):
        try:
            p = pygame.font.match_font(name)
            pb = pygame.font.match_font(name, bold=True)
        except Exception:
            p = pb = None
        if p:
            pairs.append((p, pb or ""))
    for r, b in pairs:
        if r and os.path.isfile(r) and _has_vn(r):
            return r, (b if b and os.path.isfile(b) else None)
    return None, None


def get_font(size, bold):
    px = max(9, P(size))
    k = (px, bold)
    if k not in _fonts:
        if FONT_REG:
            path = FONT_BOLD if (bold and FONT_BOLD) else FONT_REG
            f = pygame.font.Font(path, px)
            if bold and not FONT_BOLD:
                f.set_bold(True)
        else:
            f = pygame.font.Font(None, px)
        _fonts[k] = f
    return _fonts[k]


def tx(s):
    """Nếu máy không có font tiếng Việt -> bỏ dấu để không bị ô vuông."""
    if VN_OK:
        return s
    s = s.replace("Đ", "D").replace("đ", "d")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def text(s, txt, size, color, pos, anchor="center", bold=True, shadow=False):
    """Vẽ chữ. Trả về (trái, trên, phải, dưới) theo toạ độ logic."""
    f = get_font(size, bold)
    txt = tx(txt)
    px, py = P(pos[0]), P(pos[1])
    if shadow:
        sh = f.render(txt, True, (0, 0, 0))
        d = max(1, P(2))
        s.blit(sh, sh.get_rect(**{anchor: (px + d, py + d)}))
    img = f.render(txt, True, col(color))
    r = img.get_rect(**{anchor: (px, py)})
    s.blit(img, r)
    return (r.left / SC, r.top / SC, r.right / SC, r.bottom / SC)


def mpos():
    mx, my = pygame.mouse.get_pos()
    return mx / SC, my / SC


def draw_item(s, it):
    x, y, r = it["x"], it["y"], it["r"]
    if it["n"] == "gem":
        pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        poly(s, it["c"], pts)
        poly(s, (40, 40, 40), pts, 1)
    else:
        C(s, it["c"], x, y, r)
        CO(s, (40, 40, 40), x, y, r, 1)


# ---------------------------------------------------------------- nhân vật sinh viên
def draw_student(s, cx, dy, wx):
    B, LB, SK = (31, 95, 208), (53, 176, 238), (241, 199, 160)
    hx, hy = wx - 4, OY + dy - 6
    R(s, (34, 48, 74), cx - 13, 102 + dy, 11, 23)
    R(s, (34, 48, 74), cx + 2, 102 + dy, 11, 23)
    R(s, (17, 17, 17), cx - 15, 124 + dy, 14, 6)
    R(s, (17, 17, 17), cx + 1, 124 + dy, 14, 6)
    L_(s, SK, (cx + 18, 68 + dy), (hx, hy), 7)
    C(s, SK, hx, hy, 3.5)
    L_(s, B, (cx + 16, 68 + dy), (cx + 25, 67 + dy), 7)
    R(s, (85, 85, 85), wx - 8, OY + dy - 14, 16, 14)
    R(s, (255, 255, 255), cx - 17, 58 + dy, 34, 46)
    RO(s, (197, 208, 222), cx - 17, 58 + dy, 34, 46, 1)
    R(s, B, cx - 27, 58 + dy, 11, 16)
    R(s, LB, cx - 27, 73 + dy, 11, 3)
    R(s, SK, cx - 25, 76 + dy, 7, 15)
    R(s, B, cx - 17, 85 + dy, 34, 2)
    text(s, "CTU", 9, B, (cx - 15, 73 + dy), "topleft")
    poly(s, LB, [(cx + 9, 69 + dy), (cx + 14, 74 + dy), (cx + 9, 79 + dy), (cx + 4, 74 + dy)])
    poly(s, B, [(cx - 10, 56 + dy), (cx + 10, 56 + dy), (cx, 67 + dy)])
    C(s, SK, cx, 42 + dy, 14)
    hair = [(cx + 14 * math.cos(math.radians(a)), 40 + dy - 14 * math.sin(math.radians(a))) for a in range(0, 181, 15)]
    poly(s, (26, 26, 26), hair)
    C(s, (26, 26, 26), cx - 5, 45 + dy, 1.8)
    C(s, (26, 26, 26), cx + 5, 45 + dy, 1.8)


# ---------------------------------------------------------------- cảnh nền từng map
def scene(s, k, h):
    def r(c, x, y, w, hh): R(s, c, x, y, w, hh)
    def c_(cc, x, y, rr): C(s, cc, x, y, rr)
    def t(txt, x, y, f, cc): text(s, txt, f, cc, (x, y), "midbottom")
    def tri(cc, a, b, d): poly(s, cc, [a, b, d])
    def ln(cc, a, b, w=2): L_(s, cc, a, b, w)

    def table(x):
        r("#c28b4e", x - 30, 92, 60, 6); r("#7a5230", x - 3, 98, 6, 22)
        c_("#7a5230", x - 40, 112, 7); c_("#7a5230", x + 40, 112, 7)

    def shelf(x, y, w, rows):
        r("#6b4220", x, y, w, rows * 26 + 4)
        for rr in range(rows):
            ry = y + 4 + rr * 26
            r("#4a2e14", x, ry + 23, w, 3)
            for i in range(int((w - 6) / 9)):
                r(hsl((i * 53 + rr * 97) % 360, 55, 50), x + 3 + i * 9, ry + (i % 3) * 3, 7, 22 - (i % 3) * 3)

    r(hsl(h, 45, 90), 0, 0, W, 130)
    r("#a9794a", 0, 120, W, 10)
    if k == "Căn tin":
        r("#8a5a2b", 480, 70, 300, 50); r("#6b4220", 480, 66, 300, 6); t("CĂN TIN", 630, 50, 24, "#bb3333")
        for i in range(5): c_("#ffffff", 510 + i * 55, 62, 9)
        table(90); table(230)
    elif k == "Hội trường":
        r("#8e1f1f", 440, 22, 340, 98); r("#bb3333", 464, 30, 292, 65); t("HỘI TRƯỜNG", 610, 72, 22, "#ffd35a")
        r("#6b4220", 440, 95, 340, 25); r("#7a5230", 580, 78, 36, 42); ln("#222222", (598, 78), (598, 64)); c_("#222222", 598, 62, 4)
        for x in (120, 250):
            ln("#555555", (x, 0), (x, 14)); c_("#ffd35a", x, 18, 7)
        for i in range(4):
            x = 40 + i * 62; r("#2f4f94", x, 74, 42, 14); r("#3a5fa8", x, 90, 42, 28)
    elif k == "Thư viện":
        shelf(20, 48, 280, 3); shelf(470, 22, 300, 4)
    elif k == "Cổng trường":
        r("#d9d9d9", 440, 30, 26, 90); r("#d9d9d9", 720, 30, 26, 90); r("#2f6fd0", 430, 16, 326, 26)
        t("ĐẠI HỌC CẦN THƠ", 593, 38, 14, "#ffffff")
        for i in range(13): r("#555555", 470 + i * 20, 58, 3, 62)
        for x in (105, 230):
            r("#6b4220", x - 5, 70, 10, 50); c_("#3c9a4c", x, 55, 28); c_("#3c9a4c", x - 18, 72, 18); c_("#3c9a4c", x + 18, 72, 18)
    elif k == "Lớp học":
        r("#8a5a2b", 446, 18, 268, 88); r("#2f5d3a", 452, 24, 256, 76)
        for y, x2 in ((45, 640), (62, 600), (79, 660)): ln("#dfe9df", (470, y), (x2, y))
        c_("#ffffff", 745, 45, 18); ln("#222222", (745, 45), (745, 33)); ln("#222222", (745, 45), (754, 49))
        for i in range(3):
            r("#c28b4e", 50 + i * 100, 88, 70, 8); r("#7a5230", 80 + i * 100, 96, 6, 24)
    elif k == "Phòng thực hành":
        r("#9aa7b5", 40, 85, 330, 8); r("#6b7785", 50, 93, 310, 27)
        for x, cc in ((80, "#3cc46a"), (140, "#4aa8ff"), (200, "#e8a030")):
            tri(cc, (x, 85), (x - 16, 85), (x - 8, 55)); tri(cc, (x - 8, 85), (x + 12, 85), (x + 2, 55)); r("#cfd8e3", x - 9, 45, 6, 12)
        for x in (480, 570):
            r("#222222", x, 50, 70, 45); r("#55aadd", x + 4, 54, 62, 37); r("#555555", x + 28, 95, 14, 10)
        r("#6b4220", 670, 60, 100, 6)
        for x, cc in ((690, "#dd3333"), (720, "#33aa66"), (750, "#3388cc")): r(cc, x - 6, 38, 12, 22)
    elif k == "Quán cà phê":
        t("CAFÉ", 610, 54, 30, "#6b3e1e"); r("#6b3e1e", 470, 85, 310, 35)
        for i in range(5): r("#ffffff", 500 + i * 50, 72, 16, 13)
        r("#8cc4f0", 40, 30, 150, 70); r("#ffffff", 112, 30, 6, 70); r("#ffffff", 40, 62, 150, 5)
        for x in (260, 520):
            ln("#555555", (x, 0), (x, 28)); c_("#ffd35a", x, 34, 9)
        r("#a0522d", 230, 100, 30, 20); c_("#3c9a4c", 245, 92, 14)
    elif k == "Quán cơm tấm":
        for i in range(9): r("#dd3333" if i % 2 else "#ffffff", 440 + i * 38, 6, 38, 20)
        t("CƠM TẤM", 610, 60, 24, "#bb3333"); r("#333333", 480, 85, 120, 35)
        c_("#999999", 510, 76, 10); c_("#aaaaaa", 520, 62, 13); c_("#999999", 545, 70, 10)
        for x in (660, 710):
            c_("#ffffff", x, 92, 14); c_("#f4e9c8", x, 90, 9)
        table(120); table(250)
    elif k == "Nhà trọ":
        r("#e8c36a", 460, 50, 200, 70); tri("#bb3333", (450, 50), (560, 12), (670, 50))
        r("#8a5a2b", 540, 78, 40, 42); r("#6aa0e0", 475, 68, 36, 26); r("#6aa0e0", 610, 68, 36, 26)
        ln("#555555", (50, 50), (290, 50))
        for cc, x in (("#dd3333", 80), ("#33aa88", 130), ("#eeee55", 180), ("#5588cc", 230)): r(cc, x, 50, 26, 34)
        r("#a0522d", 720, 100, 26, 20); c_("#3c9a4c", 733, 92, 14)
    elif k == "Phòng thi":
        c_("#ffffff", 590, 42, 24); ln("#222222", (590, 42), (590, 26)); ln("#222222", (590, 42), (602, 48))
        t("PHÒNG THI", 720, 52, 20, "#bb3333")
        for i in range(4):
            x = 40 + i * 70; r("#c28b4e", x, 92, 56, 6); r("#ffffff", x + 16, 86, 18, 6); r("#7a5230", x + 26, 98, 5, 22)
        r("#7a5230", 640, 90, 100, 8); r("#7a5230", 650, 98, 6, 22); r("#7a5230", 724, 98, 6, 22)


def draw_menu_scene(s, t):
    for y in range(0, 300, 2):
        f = y / 300.0
        R(s, (int(74 + 131 * f), int(168 + 70 * f), int(240 + 15 * f)), 0, y, W, 2)
    C(s, (255, 224, 102), 690, 70, 34)
    for x0, y, sc, v in ((0, 60, 1, 12), (300, 110, .8, 8), (550, 40, 1.2, 15)):
        x = ((x0 + t * v) % 1000) - 100
        for dx, dy, rr in ((0, 0, 22), (24, -8, 28), (52, 0, 20)):
            C(s, (250, 250, 252), x + dx * sc, y + dy * sc, rr * sc)
    R(s, (242, 242, 242), 540, 170, 240, 130); R(s, (31, 95, 208), 530, 148, 260, 26); R(s, (53, 176, 238), 530, 174, 260, 5)
    text(s, "ĐẠI HỌC CẦN THƠ", 14, (255, 255, 255), (660, 161))
    for rr in range(2):
        for cc in range(6): R(s, (106, 160, 224), 552 + cc * 38, 190 + rr * 40, 26, 24)
    R(s, (31, 95, 208), 645, 262, 30, 38)
    R(s, (76, 175, 80), 0, 292, W, 10)
    R(s, (107, 66, 32), 466, 255, 8, 40)
    C(s, (60, 154, 76), 470, 245, 26); C(s, (60, 154, 76), 452, 262, 16); C(s, (60, 154, 76), 488, 262, 16)
    R(s, (122, 74, 34), 0, 302, W, 198)
    for i in range(70): R(s, (106, 63, 26), (i * 137) % 800, 310 + (i * 59) % 185, 5, 3)
    for x, y, k in ((250, 360, 1), (300, 450, 2), (480, 420, 0), (560, 480, 3), (640, 370, 1),
                    (720, 440, 2), (760, 340, 0), (150, 470, 3), (420, 360, 2), (60, 420, 0)):
        n, r_, v, sp, cc = TYPES[k]
        draw_item(s, {"n": n, "r": r_, "c": cc, "x": x, "y": y})
    a = math.sin(t * 1.5) * .9
    ln_ = 140 + math.sin(t * .7) * 25
    wx, wy = OX - 242, OY + 170
    draw_student(s, OX - 48 - 242, 170, wx)
    ex, ey = wx + math.sin(a) * ln_, wy + math.cos(a) * ln_
    L_(s, (34, 34, 34), (wx, wy), (ex, ey), 3)
    C(s, (34, 34, 34), ex, ey, 6)
    box = pygame.Surface((P(290), P(30)), pygame.SRCALPHA)
    box.fill((0, 0, 0, 115))
    s.blit(box, (P(14), P(12)))
    for i in range(3): heart(s, 32 + i * 24, 22, 16, (230, 50, 60))
    text(s, "Mì gói x2    Cà phê x1", 14, (255, 255, 255), (108, 27), "midleft")


# ======================================================================
#  Game
# ======================================================================
class Game:
    def __init__(self):
        self.S = {"coins": 0, "prog": 0, "up": {}, "stars": [0] * len(LV)}
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.S.update(d)
        except Exception:
            pass
        st = list(self.S.get("stars", []))
        self.S["stars"] = (st + [0] * len(LV))[:len(LV)]
        self.state = "menu"
        self.cur = 0
        self.items = []
        self.score = 0
        self.left = TIME
        self.boost = 0.0
        self.t = 0.0
        self.hook = self.new_hook()
        self.pend = None
        self.msg = ""
        self.click = None
        self.result = (0, False)
        self.run = True

    def save(self):
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.S, f, ensure_ascii=False)
        except Exception:
            pass

    def U(self, k): return self.S["up"].get(k, 0)
    def total(self): return sum(PT[n] for n in self.S["stars"])
    def gpa(self): return self.total() / 5.0
    def new_hook(self): return {"a": 0.0, "len": 40.0, "mode": "swing", "item": None}

    def button(self, s, rect, label, bg=(200, 137, 26), fg=(255, 255, 255), size=20, enabled=True, sub=False):
        x, y, w, h = rect
        mx, my = mpos()
        hover = enabled and x <= mx <= x + w and y <= my <= y + h
        c = bg if enabled else (110, 110, 110)
        if hover:
            c = tuple(min(255, v + 25) for v in c)
        x0, y0, x1, y1 = P(x), P(y), P(x + w), P(y + h)
        try:
            pygame.draw.rect(s, c, (x0, y0, x1 - x0, y1 - y0), border_radius=P(10))
        except TypeError:
            pygame.draw.rect(s, c, (x0, y0, x1 - x0, y1 - y0))
        text(s, label, size, fg, (x + w / 2, y + h / 2 - (8 if sub else 0)))
        if not enabled or self.click is None:
            return False
        cx, cy = self.click
        return x <= cx <= x + w and y <= cy <= y + h

    def overlay(self, s, alpha=225):
        o = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        o.fill((42, 33, 22, alpha))
        s.blit(o, (0, 0))

    # ---- điều khiển
    def start(self, i):
        self.cur, self.score, self.left, self.boost, self.t = i, 0, TIME, 0.0, 0.0
        self.hook = self.new_hook()
        self.spawn()
        self.state = "play"

    def spawn(self):
        self.items = []
        tries = 0
        while len(self.items) < 13 and tries < 500:
            tries += 1
            k = random.random() * 12
            n, r, v, sp, c = TYPES[0 if k < 4 else 1 if k < 7 else 2 if k < 10 else 3]
            it = {"n": n, "r": r, "v": v, "sp": sp, "c": c,
                  "x": r + 20 + random.random() * (W - 2 * r - 40),
                  "y": 170 + r + random.random() * (H - 185 - 2 * r)}
            if all(math.hypot(o["x"] - it["x"], o["y"] - it["y"]) > o["r"] + it["r"] + 8 for o in self.items):
                self.items.append(it)

    def finish(self):
        n = stars_of(self.score)
        ok = n > 0
        if n > self.S["stars"][self.cur]:
            self.S["stars"][self.cur] = n
        self.S["coins"] += self.score if ok else self.score // 2
        if ok and self.cur == self.S["prog"] and self.S["prog"] < len(LV):
            self.S["prog"] += 1
        self.save()
        self.result = (n, ok)
        self.state = "over"

    def drop(self):
        if self.state == "play" and self.hook["mode"] == "swing":
            self.hook["mode"] = "out"

    def coffee(self):
        if self.state == "play" and self.U("coffee") > 0 and self.boost <= 0:
            self.S["up"]["coffee"] = self.U("coffee") - 1
            self.boost = 5.0
            self.save()

    def ask(self, kind):
        if self.state == "play":
            self.pend = kind
            self.state = "confirm"

    def update(self, dt):
        self.left -= dt
        if self.boost > 0:
            self.boost -= dt
        if self.left <= 0:
            self.left = 0
            self.finish()
            return
        spd = (1 + .1 * self.U("rope")) * (1.6 if self.boost > 0 else 1)
        h = self.hook
        if h["mode"] == "swing":
            self.t += dt
            h["a"] = math.sin(self.t * 1.8) * 1.2
            h["len"] = 40
        elif h["mode"] == "out":
            h["len"] += 360 * dt
            x, y = OX + math.sin(h["a"]) * h["len"], OY + math.cos(h["a"]) * h["len"]
            for it in self.items:
                mg = 35 if self.U("mag") and it["sp"] >= 5 else 0
                if math.hypot(it["x"] - x, it["y"] - y) < it["r"] + 6 + mg:
                    h["item"] = it
                    self.items.remove(it)
                    h["mode"] = "in"
                    break
            if x < 5 or x > W - 5 or y > H - 5:
                h["mode"] = "in"
        else:
            it = h["item"]
            hv = 1 + .3 * self.U("steel") if (it and it["sp"] < 3) else 1
            h["len"] -= (it["sp"] * 60 * hv if it else 380) * spd * dt
            if it:
                it["x"] = OX + math.sin(h["a"]) * h["len"]
                it["y"] = OY + math.cos(h["a"]) * h["len"]
            if h["len"] <= 40:
                h["len"] = 40
                if it:
                    self.score += int(round(it["v"] * (1 + .15 * self.U("bag"))))
                h["item"] = None
                h["mode"] = "swing"
                self.t = math.asin(max(-1, min(1, h["a"] / 1.2))) / 1.8

    # ---- vẽ màn chơi
    def draw_play(self, s):
        L = LV[self.cur]
        s.fill(hsl(L["hue"], 55, 82))
        R(s, hsl(L["hue"], 30, 38), 0, 130, W, H - 130)
        scene(s, re.sub(r" \d+$", "", L["name"]), L["hue"])
        h = self.hook
        for it in self.items:
            draw_item(s, it)
        x, y = OX + math.sin(h["a"]) * h["len"], OY + math.cos(h["a"]) * h["len"]
        L_(s, (34, 34, 34), (OX, OY), (x, y), 3)
        C(s, (34, 34, 34), x, y, 6)
        if h["item"]:
            draw_item(s, h["item"])
        draw_student(s, OX - 48, 0, OX)
        nxt = 800 if self.score < 800 else 900 if self.score < 900 else 1000
        right = text(s, "Điểm: %d/%d" % (self.score, nxt), 20, (34, 34, 34), (14, 10), "topleft")[2]
        for i in range(stars_of(self.score)):
            star(s, right + 14 + i * 18, 22, 8, (240, 180, 0))
        text(s, "%ds%s" % (math.ceil(self.left), "  (cà phê)" if self.boost > 0 else ""), 20, (34, 34, 34), (W - 14, 10), "topright")
        text(s, "%s · Màn %d: %s" % (BIG[L["bi"]][0], L["mi"] + 1, L["name"]), 15, (34, 34, 34), (OX, 140))

    def play_ui(self, s):
        used = False
        if self.button(s, (10, H - 44, 130, 34), "Thoát game", (192, 57, 43), size=16):
            self.ask("exit"); used = True
        elif self.button(s, (150, H - 44, 150, 34), "Kết thúc ván", size=16):
            self.ask("end"); used = True
        elif self.button(s, (W - 190, H - 44, 180, 34), "Cà phê (C) x%d" % self.U("coffee"), size=16):
            self.coffee(); used = True
        return used

    # ---- vòng lặp từng khung hình
    def frame(self, s, dt):
        st = self.state
        if st == "menu":
            self.screen_menu(s)
        elif st == "sel":
            self.screen_sel(s)
        elif st == "shop":
            self.screen_shop(s)
        elif st == "play":
            self.update(dt)
            if self.state == "play":
                self.draw_play(s)
                used = self.play_ui(s)
                if self.click is not None and not used and self.state == "play":
                    self.drop()
        elif st == "confirm":
            self.draw_play(s)
            self.overlay(s)
            text(s, "Bạn có chắc không?", 40, (255, 255, 255), (OX, 170))
            msg = "Thoát game? Kết quả ván này sẽ bị bỏ qua." if self.pend == "exit" else "Kết thúc ván và xem kết quả?"
            text(s, msg, 20, (240, 230, 210), (OX, 220), bold=False)
            if self.button(s, (OX - 215, 270, 200, 50), "Đồng ý"):
                if self.pend == "exit":
                    self.state = "menu"
                else:
                    self.finish()
            elif self.button(s, (OX + 15, 270, 200, 50), "Không", (192, 57, 43)):
                self.state = "play"
        elif st == "over":
            self.screen_over(s)

    def screen_menu(self, s):
        draw_menu_scene(s, pygame.time.get_ticks() / 1000.0)
        text(s, "ĐÀO VÀNG", 64, (255, 255, 255), (OX, 120), shadow=True)
        text(s, "Sinh viên sinh tồn: đào xu, qua môn, sống sót đến cuối kỳ!", 18, (255, 255, 255), (OX, 175), shadow=True)
        if self.button(s, (OX - 110, 220, 220, 52), "Chơi game", size=24):
            self.state = "sel"
        elif self.button(s, (OX - 110, 285, 220, 52), "Thoát game", (240, 240, 240), (59, 42, 20), size=24):
            self.run = False

    def screen_sel(self, s):
        s.fill((42, 33, 22))
        text(s, "Chọn màn chơi", 26, (255, 255, 255), (OX, 22))
        text(s, "Xu: %d   |   Điểm tích lũy: %.1f/20   |   GPA: %.2f/4.0" % (self.S["coins"], self.total(), self.gpa()),
             16, (240, 230, 210), (OX, 52), bold=False)
        text(s, "Qua màn: 800 điểm = 1 sao · 900 điểm = 2 sao · 1000 điểm = 3 sao", 13, (200, 190, 170), (OX, 72), bold=False)
        k = 0
        y = 92
        clicked = None
        for bn, maps in BIG:
            text(s, bn, 17, (245, 197, 24), (20, y), "topleft")
            n = len(maps)
            bw, gap = 122, 6
            x0 = (W - (n * bw + (n - 1) * gap)) / 2.0
            for i, m in enumerate(maps):
                locked = k > self.S["prog"]
                rect = (x0 + i * (bw + gap), y + 22, bw, 52)
                done = self.S["stars"][k] > 0
                bg = (46, 158, 79) if done else (200, 137, 26)
                if self.button(s, rect, "%d. %s" % (k + 1, m), bg, size=12, enabled=not locked, sub=True):
                    clicked = k
                if locked:
                    text(s, "khóa", 11, (200, 200, 200), (rect[0] + bw / 2, rect[1] + 38))
                else:
                    for j in range(3):
                        star(s, rect[0] + bw / 2 - 18 + j * 18, rect[1] + 38, 7, (255, 230, 90), filled=j < self.S["stars"][k])
                k += 1
            y += 90
        if self.button(s, (OX - 215, H - 46, 200, 38), "Cửa hàng", size=18):
            self.msg = ""
            self.state = "shop"
        elif self.button(s, (OX + 15, H - 46, 200, 38), "Về menu", (90, 80, 70), size=18):
            self.state = "menu"
        if clicked is not None:
            self.start(clicked)

    def screen_shop(self, s):
        s.fill((42, 33, 22))
        text(s, "Cửa hàng nâng cấp", 26, (255, 255, 255), (OX, 24))
        text(s, "Xu: %d    %s" % (self.S["coins"], self.msg), 17, (245, 197, 24), (OX, 54), bold=False)
        y = 80
        for uid, name, desc, price, mx in UPGRADES:
            n = self.U(uid)
            R(s, (70, 56, 38), 40, y, 720, 60)
            text(s, "%s  (đang có: %d)" % (name, n), 18, (255, 255, 255), (56, y + 8), "topleft")
            text(s, desc, 14, (210, 200, 180), (56, y + 34), "topleft", bold=False)
            full = n >= mx
            can = (not full) and self.S["coins"] >= price
            if self.button(s, (620, y + 10, 128, 40), "Tối đa" if full else "%d xu" % price, size=17, enabled=can):
                self.S["coins"] -= price
                self.S["up"][uid] = n + 1
                self.msg = "Đã mua %s!" % name
                self.save()
            y += 68
        if self.button(s, (OX - 130, H - 52, 260, 40), "Quay lại chọn màn", (90, 80, 70), size=18):
            self.state = "sel"

    def screen_over(self, s):
        self.draw_play(s)
        self.overlay(s, 235)
        n, ok = self.result
        title = ("Tốt nghiệp!" if self.cur == len(LV) - 1 else "Hoàn thành!") if ok else "Chưa đạt!"
        text(s, title, 44, (255, 255, 255), (OX, 70))
        for j in range(3):
            star(s, OX - 50 + j * 50, 135, 22, (255, 220, 60), filled=j < n)
        text(s, "Điểm: %d  (cần ≥ 800 để qua màn)" % self.score, 20, (240, 230, 210), (OX, 190), bold=False)
        text(s, "Điểm môn: +%.1f   |   Tích lũy: %.1f/20" % (PT[n], self.total()), 20, (240, 230, 210), (OX, 220), bold=False)
        text(s, "GPA: %.2f/4.0   |   Xu: %d" % (self.gpa(), self.S["coins"]), 20, (245, 197, 24), (OX, 250))
        y = 285
        go = None
        if ok and self.cur < len(LV) - 1:
            if self.button(s, (OX - 110, y, 220, 44), "Màn tiếp theo"):
                go = ("start", self.cur + 1)
            y += 54
        if self.button(s, (OX - 110, y, 220, 44), "Chơi lại", (90, 80, 70)):
            go = ("start", self.cur)
        if self.button(s, (OX - 110, y + 54, 220, 44), "Chọn màn", (90, 80, 70)):
            go = ("sel", 0)
        if go:
            if go[0] == "start":
                self.start(go[1])
            else:
                self.state = "sel"


def main():
    global SC, FONT_REG, FONT_BOLD, VN_OK
    if sys.platform == "win32":          # tránh Windows tự phóng to cửa sổ làm chữ bị mờ
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    pygame.init()
    try:
        info = pygame.display.Info()
        sw, sh = info.current_w, info.current_h
        if sw > 0 and sh > 0:
            SC = max(1.0, min(sw * 0.92 / W, (sh - 100) / H, 2.5))
    except Exception:
        SC = 1.0
    screen = pygame.display.set_mode((P(W), P(H)))
    pygame.display.set_caption(tx("Đào Vàng - Sinh viên sinh tồn"))
    FONT_REG, FONT_BOLD = find_fonts()
    VN_OK = FONT_REG is not None
    if not VN_OK:
        print("[!] Không tìm thấy font hỗ trợ tiếng Việt -> game sẽ hiển thị không dấu.\n"
              "    Hãy chép một file font (vd Arial) vào cùng thư mục, đặt tên font.ttf để có dấu.")
    clock = pygame.time.Clock()
    g = Game()
    while g.run:
        dt = min(clock.tick(60) / 1000.0, .05)
        g.click = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                g.run = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                g.click = (e.pos[0] / SC, e.pos[1] / SC)
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_DOWN):
                    g.drop()
                elif e.key == pygame.K_c:
                    g.coffee()
                elif e.key == pygame.K_ESCAPE:
                    g.ask("exit")
        g.frame(screen, dt)
        pygame.display.flip()
    g.save()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
