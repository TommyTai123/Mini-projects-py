# -*- coding: utf-8 -*-
"""
SINH TỒN ĐẠI HỌC (Python + pygame)
Cài đặt:  pip install pygame
Chạy:     python dao_vang.py
"""
import os, sys, json, math, random, re, colorsys, time
import pygame

W, H = 800, 500          # tọa độ logic của game (giữ nguyên toàn bộ bố cục)
OX, OY = W // 2, 70
# Độ phân giải thật khi vẽ = (W, H) * UI_SCALE.
#   None -> tự chọn theo màn hình (tối đa 3.2 => 2560x1600, xấp xỉ 2K)
#   Muốn ép cứng: đặt số, ví dụ 3.2 (2560x1600), 2.4 (1920x1200), 2 (1600x1000)
UI_SCALE = None
MAX_SCALE = 3.2
_K = 1.0                 # hệ số phóng hiện tại (được gán trong main)
TIME = 180               # thời gian mỗi ván (giây)
MISS_PENALTY = 5         # kéo hụt (móc không trúng gì) bị trừ bao nhiêu giây
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dao_vang_save.json")

BIG = [
    ("Đầu tháng", ["Căn tin", "Hội trường", "Thư viện", "Cổng trường", "Lớp học"]),
    ("Deadline", ["Thư viện 2", "Lớp học 2", "Phòng thực hành", "Quán cà phê"]),
    ("Cuối tháng", ["Thư viện 3", "Lớp học 3", "Căn tin 2", "Quán cơm tấm", "Nhà trọ"]),
    ("Mùa thi", ["Thư viện 4", "Lớp học 4", "Căn tin 3", "Phòng thực hành 2", "Nhà trọ 2", "Phòng thi"]),
]
LV = []
for bi, (bn, maps) in enumerate(BIG):
    for mi, name in enumerate(maps):
        LV.append({"name": name, "bi": bi, "mi": mi, "hue": (len(LV) * 47) % 360})

UPGRADES = [
    ("rope", "Dây kéo bền", "Thu dây nhanh hơn 10% mỗi cấp · phím 1", 200, 5),
    ("steel", "Móc thép", "Kéo vật nặng dễ hơn · phím 2", 350, 3),
    ("bag", "Ba lô sinh viên", "Tăng 15% điểm thưởng mỗi cấp · phím 3", 400, 3),
    ("coffee", "Cà phê tăng lực", "Tăng tốc kéo 5 giây, dùng 1 lần · phím 4 (hoặc C)", 150, 99),
    ("mag", "Nam châm mini", "Hút vật nhẹ ở gần · phím 5", 500, 1),
]
SHORT = {"rope": "Dây", "steel": "Móc", "bag": "Ba lô", "coffee": "Cà phê", "mag": "Nam châm"}
# r = bán kính, v = điểm, sp = tốc độ kéo (càng nhỏ càng nặng)
# slow = làm chậm móc (giây), lose = mất thời gian (giây), stun = choáng (giây)
TYPES = {
    "coin": {"name": "Xu lẻ", "r": 10, "v": 10, "sp": 5, "c": (245, 197, 24)},
    "wallet": {"name": "Ví tiền", "r": 15, "v": 50, "sp": 4, "c": (139, 90, 43)},
    "laptop": {"name": "Laptop cũ", "r": 17, "v": 200, "sp": 2.5, "c": (150, 160, 175)},
    "homework": {"name": "Bài tập trễ hạn", "r": 19, "v": 0, "sp": 2, "c": (250, 248, 235), "slow": 4},
    "debt": {"name": "Cục nợ môn", "r": 20, "v": 0, "sp": 1.5, "c": (90, 60, 60), "lose": 5},
    "ewaste": {"name": "Rác điện tử", "r": 17, "v": 0, "sp": 2, "c": (50, 130, 80), "slow": 3, "lose": 2},
    "meme": {"name": "Mặt cười meme", "r": 13, "v": -300, "sp": 5, "c": (255, 220, 60)},
    "landlord": {"name": "Chủ trọ khó tính", "r": 32, "v": 0, "sp": 1.2, "c": (235, 190, 150), "stun": 5},
    "scholarship": {"name": "Học bổng", "r": 11, "v": 1000, "sp": 5, "c": (255, 215, 0)},
    "clock": {"name": "Đồng hồ", "r": 15, "v": 0, "sp": 4, "c": (240, 240, 240), "lose": 10},
}
BAD = {"homework", "debt", "ewaste", "meme", "landlord", "clock"}
# vật phẩm xuất hiện (tên, trọng số) theo màn lớn; laptop luôn có đúng 1 cái mỗi màn
POOLS = [
    [("coin", 8), ("wallet", 5)],
    [("coin", 8), ("wallet", 5), ("homework", 2), ("debt", 1.5), ("ewaste", 2)],
    [("coin", 8), ("wallet", 5), ("meme", 2), ("landlord", 1)],
    [("coin", 8), ("wallet", 5), ("clock", 2)],
]
PT = [0, 0.3, 0.6, 1.0]  # điểm môn theo số sao


# ---- vẽ độ phân giải cao ------------------------------------------------------
# Game vẫn viết theo tọa độ 800x500; Canvas + pygame.draw bên dưới tự nhân hệ số
# phóng, nên hình và chữ được vẽ thẳng ở độ phân giải lớn (sắc nét, không bị nhòe).
_real_draw = pygame.draw


def _sw(w, k):
    return 0 if w == 0 else max(1, int(round(w * k)))


class Canvas:
    def __init__(self, surf, k):
        self.surf, self.k = surf, k

    def __getattr__(self, name):
        return getattr(self.surf, name)

    def fill(self, c, *a):
        self.surf.fill(c)

    def blit(self, src, dest=(0, 0), *a, **kw):
        k = self.k
        dx, dy = (dest.x, dest.y) if isinstance(dest, pygame.Rect) else (dest[0], dest[1])
        w, h = src.get_size()
        size = (max(1, int(round(w * k))), max(1, int(round(h * k))))
        img = pygame.transform.smoothscale(src, size) if src.get_bitsize() in (24, 32) else pygame.transform.scale(src, size)
        return self.surf.blit(img, (int(round(dx * k)), int(round(dy * k))))

    def set_clip(self, r=None):
        if r is None:
            self.surf.set_clip(None)
            return
        k = self.k
        x, y, w, h = r
        x0, y0 = int(round(x * k)), int(round(y * k))
        self.surf.set_clip(pygame.Rect(x0, y0, int(round((x + w) * k)) - x0, int(round((y + h) * k)) - y0))

    def alpha_fill(self, rect, color, radius=0):
        """Ô nền trong suốt (có thể bo góc), vẽ thẳng ở độ phân giải cao."""
        k = self.k
        x, y, w, h = rect
        x0, y0 = int(round(x * k)), int(round(y * k))
        pw, ph = max(1, int(round((x + w) * k)) - x0), max(1, int(round((y + h) * k)) - y0)
        img = pygame.Surface((pw, ph), pygame.SRCALPHA)
        _real_draw.rect(img, color, (0, 0, pw, ph), border_radius=int(round(radius * k)))
        self.surf.blit(img, (x0, y0))


class _HiDraw:
    """Thay pygame.draw: nếu vẽ lên Canvas thì nhân tọa độ/độ dày với hệ số phóng."""

    def __getattr__(self, name):
        return getattr(_real_draw, name)

    def rect(self, surf, color, rect, width=0, *a, **kw):
        if not isinstance(surf, Canvas):
            return _real_draw.rect(surf, color, rect, width, *a, **kw)
        k = surf.k
        x, y, w, h = rect
        x0, y0 = int(round(x * k)), int(round(y * k))
        r = pygame.Rect(x0, y0, int(round((x + w) * k)) - x0, int(round((y + h) * k)) - y0)
        for key in list(kw):
            if key.endswith("radius"):
                kw[key] = int(round(kw[key] * k))
        return _real_draw.rect(surf.surf, color, r, _sw(width, k), *a, **kw)

    def circle(self, surf, color, center, radius, width=0, *a, **kw):
        if not isinstance(surf, Canvas):
            return _real_draw.circle(surf, color, center, radius, width, *a, **kw)
        k = surf.k
        return _real_draw.circle(surf.surf, color, (center[0] * k, center[1] * k),
                                 max(1, int(round(radius * k))), _sw(width, k), *a, **kw)

    def line(self, surf, color, a, b, width=1):
        if not isinstance(surf, Canvas):
            return _real_draw.line(surf, color, a, b, width)
        k = surf.k
        return _real_draw.line(surf.surf, color, (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), max(1, int(round(width * k))))

    def polygon(self, surf, color, points, width=0):
        if not isinstance(surf, Canvas):
            return _real_draw.polygon(surf, color, points, width)
        k = surf.k
        return _real_draw.polygon(surf.surf, color, [(p[0] * k, p[1] * k) for p in points], _sw(width, k))


pygame.draw = _HiDraw()


def mpos():
    """Vị trí chuột theo tọa độ logic 800x500."""
    x, y = pygame.mouse.get_pos()
    return (int(x / _K), int(y / _K))


def pick_scale():
    if UI_SCALE:
        return float(UI_SCALE)
    try:
        dw, dh = pygame.display.get_desktop_sizes()[0]
    except Exception:
        try:
            info = pygame.display.Info()
            dw, dh = info.current_w, info.current_h
        except Exception:
            dw, dh = 1920, 1080
    k = min((dw - 60) / W, (dh - 140) / H)
    return max(1.0, min(MAX_SCALE, k))


UNLOCK_LV = sum(len(m) for _, m in BIG[:3])  # màn nhỏ đầu tiên của màn lớn 4
UNLOCK_COST = 14000
UNLOCK_TXT = f"{UNLOCK_COST:,}".replace(",", ".")


def big_th(bi):
    return (800, 900, 1000)


def thresholds(cur):
    return big_th(LV[cur]["bi"])


def stars_of(score, cur):
    t = thresholds(cur)
    return 3 if score >= t[2] else 2 if score >= t[1] else 1 if score >= t[0] else 0



# ---------------------------------------------------------------- helpers
def hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def col(c):
    if isinstance(c, str):
        # pygame.Color không hiểu mã "#RGB" (3 ký tự) -> đây là nguyên nhân lỗi không vào được màn
        if c.startswith("#") and len(c) == 4:
            c = "#" + "".join(ch * 2 for ch in c[1:])
        return pygame.Color(c)
    return c


_fonts = {}
_font_path = None
_font_searched = False
VN_TEST = "ĐàoVàngếặờưởỹ"
FONT_NAMES = ["segoeui", "arial", "tahoma", "calibri", "dejavusans", "notosans",
              "liberationsans", "freesans", "ubuntu", "roboto", "opensans", "verdana"]
FONT_FILES = [
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


def _supports_vn(path, bold=False):
    try:
        f = pygame.font.Font(path, 20)
        m = f.metrics(VN_TEST)
        return all(x is not None for x in m)
    except Exception:
        return False


def find_font():
    """Tìm font hệ thống hiển thị được tiếng Việt có dấu."""
    global _font_path, _font_searched
    if _font_searched:
        return _font_path
    _font_searched = True
    for n in FONT_NAMES:
        p = pygame.font.match_font(n)
        if p and _supports_vn(p):
            _font_path = p
            return p
    for p in FONT_FILES:
        if os.path.exists(p) and _supports_vn(p):
            _font_path = p
            return p
    return None


def font(size, bold=True):
    k = (size, bold)
    if k not in _fonts:
        p = find_font()
        f = pygame.font.Font(p, size) if p else pygame.font.Font(None, size)
        f.set_bold(bold)
        _fonts[k] = f
    return _fonts[k]


def text(s, txt, size, color, pos, anchor="center", bold=True, shadow=False):
    if isinstance(s, Canvas):
        k = s.k
        fh = font(max(1, int(round(size * k))), bold)

        def put(img, p):
            rr = img.get_rect(**{anchor: (int(round(p[0] * k)), int(round(p[1] * k)))})
            s.surf.blit(img, rr)
            return rr
        if shadow:
            put(fh.render(txt, True, (0, 0, 0)), (pos[0] + 2, pos[1] + 2))
        rr = put(fh.render(txt, True, col(color)), pos)
        return pygame.Rect(int(rr.x / k), int(rr.y / k), int(rr.w / k), int(rr.h / k))
    f = font(size, bold)
    if shadow:
        img = f.render(txt, True, (0, 0, 0))
        r = img.get_rect(**{anchor: (pos[0] + 2, pos[1] + 2)})
        s.blit(img, r)
    img = f.render(txt, True, col(color))
    r = img.get_rect(**{anchor: pos})
    s.blit(img, r)
    return r


def R(s, c, x, y, w, h):
    pygame.draw.rect(s, col(c), (x, y, w, h))


def C(s, c, x, y, r):
    pygame.draw.circle(s, col(c), (x, y), r)


def L_(s, c, a, b, w=2):
    pygame.draw.line(s, col(c), a, b, w)


def poly(s, c, pts):
    pygame.draw.polygon(s, col(c), pts)


def star(s, cx, cy, r, color, filled=True):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    if filled:
        pygame.draw.polygon(s, col(color), pts)
    else:
        pygame.draw.polygon(s, col(color), pts, 2)


def heart(s, x, y, size, color):
    r = size // 4
    C(s, color, x - r, y, r)
    C(s, color, x + r, y, r)
    poly(s, color, [(x - 2 * r, y + 1), (x + 2 * r, y + 1), (x, y + 3 * r)])


def draw_item(s, it):
    x, y, r, n = it["x"], it["y"], int(it["r"]), it["n"]
    ix, iy = int(x), int(y)
    ol = (40, 40, 40)
    if n == "coin":
        C(s, (245, 197, 24), ix, iy, r)
        pygame.draw.circle(s, (200, 150, 0), (ix, iy), int(r * 0.62), 2)
        pygame.draw.circle(s, ol, (ix, iy), r, 1)
    elif n == "wallet":
        rc = pygame.Rect(ix - r, iy - int(r * 0.7), 2 * r, int(r * 1.4))
        pygame.draw.rect(s, (139, 90, 43), rc, border_radius=4)
        pygame.draw.rect(s, (95, 58, 25), (rc.x, rc.y, rc.w, rc.h // 3), border_radius=4)
        C(s, (245, 197, 24), rc.right - 5, iy + 3, 3)
        pygame.draw.rect(s, ol, rc, 1, border_radius=4)
    elif n == "laptop":
        sh = int(r * 1.1)
        pygame.draw.rect(s, (60, 64, 72), (ix - r + 3, iy - r + 2, 2 * r - 6, sh), border_radius=2)
        pygame.draw.rect(s, (90, 170, 230), (ix - r + 6, iy - r + 5, 2 * r - 12, sh - 6))
        pygame.draw.rect(s, (170, 175, 185), (ix - r, iy + int(r * 0.2), 2 * r, int(r * 0.5)), border_radius=3)
        pygame.draw.rect(s, ol, (ix - r, iy + int(r * 0.2), 2 * r, int(r * 0.5)), 1, border_radius=3)
    elif n == "homework":
        rc = (ix - r + 3, iy - r, 2 * r - 6, 2 * r)
        pygame.draw.rect(s, (250, 248, 235), rc)
        pygame.draw.rect(s, ol, rc, 1)
        for k in range(4):
            L_(s, (200, 60, 60) if k == 0 else (130, 150, 200), (ix - r + 7, iy - r + 6 + k * 7), (ix + r - 7, iy - r + 6 + k * 7), 1)
        text(s, "!", 16, (220, 30, 30), (ix, iy + 9))
    elif n == "debt":
        C(s, (90, 60, 60), ix, iy, r)
        pygame.draw.circle(s, ol, (ix, iy), r, 1)
        text(s, "F", int(r * 1.3), (255, 90, 90), (ix, iy))
    elif n == "ewaste":
        rc = (ix - r, iy - r + 3, 2 * r, 2 * r - 6)
        pygame.draw.rect(s, (50, 130, 80), rc, border_radius=3)
        R(s, (30, 30, 30), ix - 9, iy - 6, 10, 10)
        R(s, (220, 190, 60), ix + 3, iy + 1, 8, 6)
        L_(s, (200, 220, 200), (ix - r + 3, iy + 8), (ix + r - 3, iy + 8), 1)
        pygame.draw.rect(s, ol, rc, 1, border_radius=3)
    elif n == "meme":
        C(s, (255, 220, 60), ix, iy, r)
        pygame.draw.circle(s, ol, (ix, iy), r, 1)
        C(s, ol, ix - 4, iy - 3, 2)
        C(s, ol, ix + 4, iy - 3, 2)
        R(s, (255, 255, 255), ix - 5, iy + 2, 10, 4)
        C(s, (230, 70, 90), ix, iy + 8, 3)
    elif n == "landlord":
        R(s, (120, 60, 60), ix - 18, iy + 14, 36, 18)
        C(s, (235, 190, 150), ix, iy - 4, 22)
        pygame.draw.circle(s, (170, 170, 170), (ix, iy - 4), 22, 5, draw_top_left=True, draw_top_right=True)
        pygame.draw.circle(s, ol, (ix, iy - 4), 22, 1)
        C(s, ol, ix - 8, iy, 2)
        C(s, ol, ix + 8, iy, 2)
        L_(s, (200, 30, 30), (ix - 12, iy - 7), (ix - 4, iy - 3), 3)
        L_(s, (200, 30, 30), (ix + 12, iy - 7), (ix + 4, iy - 3), 3)
        L_(s, ol, (ix - 7, iy + 12), (ix + 7, iy + 12), 2)
        L_(s, ol, (ix - 7, iy + 12), (ix - 9, iy + 15), 2)
        L_(s, ol, (ix + 7, iy + 12), (ix + 9, iy + 15), 2)
        text(s, "TRỌ", 10, (255, 255, 255), (ix, iy + 23))
    elif n == "scholarship":
        pygame.draw.circle(s, (255, 245, 160), (ix, iy), r + 4, 2)
        C(s, (255, 215, 0), ix, iy, r)
        pygame.draw.circle(s, (170, 110, 0), (ix, iy), r, 2)
        text(s, "HB", 11, (120, 70, 0), (ix, iy))
    elif n == "clock":
        C(s, (240, 240, 240), ix, iy, r)
        pygame.draw.circle(s, ol, (ix, iy), r, 2)
        L_(s, ol, (ix, iy), (ix, iy - 9), 2)
        L_(s, ol, (ix, iy), (ix + 6, iy + 3), 2)
        C(s, (220, 50, 50), ix - r + 2, iy - r + 3, 3)
        C(s, (220, 50, 50), ix + r - 2, iy - r + 3, 3)
    else:
        C(s, it["c"], ix, iy, r)
        pygame.draw.circle(s, ol, (ix, iy), r, 1)




UP_NAME = {u[0]: u[1] for u in UPGRADES}
COLL = [
    ("Có lợi", ["coin", "wallet", "laptop", "rope", "steel", "bag", "coffee", "mag"]),
    ("Có hại", ["homework", "debt", "ewaste", "meme", "landlord", "clock"]),
    ("Huyền thoại", ["diploma", "scholarship"]),
]
DESC = {
    "coin": "+10 điểm", "wallet": "+50 điểm", "laptop": "+200 điểm",
    "homework": "Làm chậm móc 4s", "debt": "Mất 5 giây", "ewaste": "Chậm 3s, mất 2s",
    "meme": "Trừ 300 điểm", "landlord": "Choáng 5 giây", "clock": "Mất 10 giây",
    "rope": "Thu dây nhanh hơn", "steel": "Kéo vật nặng dễ", "bag": "+15% điểm thưởng",
    "coffee": "Tăng tốc 5 giây", "mag": "Hút vật nhẹ ở gần",
    "scholarship": "+1000 điểm", "diploma": "Bấm để xem bằng",
}


def rank_of(g):
    return "Xuất sắc" if g >= 3.6 else "Giỏi" if g >= 3.2 else "Khá" if g >= 2.5 else "Trung bình"


def draw_upgrade(s, k, cx, cy):
    cx, cy = int(cx), int(cy)
    if k == "rope":
        pygame.draw.circle(s, (190, 150, 90), (cx, cy), 20, 4)
        pygame.draw.circle(s, (160, 120, 70), (cx, cy), 11, 3)
        L_(s, (190, 150, 90), (cx + 16, cy + 14), (cx + 26, cy + 24), 3)
    elif k == "steel":
        L_(s, (170, 175, 185), (cx, cy - 24), (cx, cy + 8), 5)
        L_(s, (170, 175, 185), (cx, cy + 8), (cx + 14, cy + 18), 5)
        L_(s, (170, 175, 185), (cx + 14, cy + 18), (cx + 6, cy + 26), 5)
        C(s, (120, 125, 135), cx, cy - 24, 5)
    elif k == "bag":
        pygame.draw.rect(s, (31, 95, 208), (cx - 18, cy - 14, 36, 38), border_radius=8)
        pygame.draw.rect(s, (53, 176, 238), (cx - 12, cy + 6, 24, 14), border_radius=4)
        L_(s, (31, 95, 208), (cx - 8, cy - 14), (cx - 8, cy - 22), 3)
        L_(s, (31, 95, 208), (cx - 8, cy - 22), (cx + 8, cy - 22), 3)
        L_(s, (31, 95, 208), (cx + 8, cy - 22), (cx + 8, cy - 14), 3)
    elif k == "coffee":
        R(s, (245, 245, 245), cx - 14, cy - 8, 28, 28)
        pygame.draw.circle(s, (245, 245, 245), (cx + 17, cy + 5), 8, 3)
        R(s, (110, 70, 35), cx - 14, cy - 8, 28, 8)
        for dx in (-6, 2, 10):
            L_(s, (230, 230, 230), (cx + dx, cy - 12), (cx + dx + 3, cy - 22), 2)
    elif k == "mag":
        R(s, (220, 50, 50), cx - 18, cy - 18, 10, 26)
        R(s, (60, 110, 220), cx + 8, cy - 18, 10, 26)
        R(s, (170, 175, 185), cx - 18, cy + 8, 36, 10)
        R(s, (240, 240, 240), cx - 18, cy - 18, 10, 5)
        R(s, (240, 240, 240), cx + 8, cy - 18, 10, 5)


def draw_diploma_icon(s, cx, cy):
    cx, cy = int(cx), int(cy)
    pygame.draw.rect(s, (250, 240, 205), (cx - 26, cy - 18, 52, 36), border_radius=3)
    pygame.draw.rect(s, (200, 150, 30), (cx - 26, cy - 18, 52, 36), 2, border_radius=3)
    for i in range(3):
        L_(s, (150, 130, 90), (cx - 18, cy - 8 + i * 7), (cx + 8, cy - 8 + i * 7), 1)
    C(s, (200, 40, 40), cx + 14, cy + 8, 7)



# ---------------------------------------------------------------- thành tựu
# (mã, tên, mô tả, gợi ý)
ACHIEVEMENTS = [
    ("three_star", "Ghê vậy", "Đạt 3 sao lần đầu tiên",
     "Đạt từ 1000 điểm trở lên ở bất kỳ màn chơi nào."),
    ("no_help", "Tay không bắt giặc", "Vượt qua màn chơi mà không sử dụng bất kỳ vật phẩm hỗ trợ nào",
     "Mẹo: tắt hết nâng cấp (phím 1-5) trước khi thả móc và đừng uống cà phê."),
    ("clean", "Bàn tay vàng trong làng né", "Hoàn thành 1 màn chơi mà không kéo trúng bất kỳ vật phẩm có hại/rác nào",
     "Mẹo: tránh bài tập, cục nợ, rác điện tử, meme, chủ trọ và đồng hồ."),
]
ACH_INFO = {a[0]: a for a in ACHIEVEMENTS}
ACH_COLOR = {"three_star": ((235, 175, 20), (150, 100, 0)),
             "no_help": ((205, 75, 65), (120, 30, 30)),
             "clean": ((46, 150, 110), (20, 90, 65))}


def draw_badge(s, key, cx, cy, r, ok):
    """Huy hiệu thành tựu (đã mở: có màu + biểu tượng, chưa mở: xám + ổ khóa)."""
    cx, cy = int(cx), int(cy)
    u = r / 30.0
    if not ok:
        C(s, (58, 50, 40), cx, cy, r)
        pygame.draw.circle(s, (105, 95, 80), (cx, cy), r, max(2, int(3 * u)))
        pygame.draw.circle(s, (130, 120, 105), (cx, cy - int(6 * u)), max(2, int(9 * u)), max(2, int(3 * u)))
        pygame.draw.rect(s, (130, 120, 105), (cx - 12 * u, cy - 3 * u, 24 * u, 18 * u), border_radius=3)
        C(s, (58, 50, 40), cx, cy + 5 * u, max(2, int(3 * u)))
        return
    bg, rim = ACH_COLOR[key]
    C(s, rim, cx, cy, r)
    C(s, bg, cx, cy, r - max(2, int(3 * u)))
    pygame.draw.circle(s, tuple(min(255, v + 60) for v in bg), (cx, cy), int(r - 7 * u), max(1, int(2 * u)))
    if key == "three_star":
        star(s, cx, cy - 4 * u, 13 * u, (255, 255, 255))
        star(s, cx - 15 * u, cy + 9 * u, 8 * u, (255, 245, 190))
        star(s, cx + 15 * u, cy + 9 * u, 8 * u, (255, 245, 190))
    elif key == "no_help":
        skin, sk_ol = (255, 224, 189), (140, 90, 60)
        pygame.draw.rect(s, skin, (cx - 12 * u, cy - 3 * u, 24 * u, 18 * u), border_radius=5)
        for i in range(4):
            fx = cx - 9 * u + i * 6 * u
            C(s, skin, fx, cy - 4 * u, 3.6 * u)
            pygame.draw.circle(s, sk_ol, (fx, cy - 4 * u), 3.6 * u, 1)
        C(s, skin, cx - 12 * u, cy + 5 * u, 4.5 * u)
        pygame.draw.rect(s, sk_ol, (cx - 12 * u, cy - 3 * u, 24 * u, 18 * u), 1, border_radius=5)
        R(s, (255, 255, 255), cx - 9 * u, cy + 15 * u, 18 * u, 5 * u)
    elif key == "clean":
        gold, g_ol = (255, 215, 0), (150, 105, 0)
        pygame.draw.rect(s, gold, (cx - 10 * u, cy - 1 * u, 20 * u, 18 * u), border_radius=5)
        for i, hh in enumerate((12, 16, 14, 10)):
            fx = cx - 10 * u + i * 5.5 * u
            pygame.draw.rect(s, gold, (fx, cy - 1 * u - hh * u, 4.4 * u, hh * u + 2 * u), border_radius=2)
            pygame.draw.rect(s, g_ol, (fx, cy - 1 * u - hh * u, 4.4 * u, hh * u + 2 * u), 1, border_radius=2)
        L_(s, gold, (cx - 9 * u, cy + 10 * u), (cx - 17 * u, cy + 2 * u), max(2, int(4 * u)))
        pygame.draw.rect(s, g_ol, (cx - 10 * u, cy - 1 * u, 20 * u, 18 * u), 1, border_radius=5)
        star(s, cx + 17 * u, cy - 15 * u, 6 * u, (255, 255, 255))


# ---------------------------------------------------------------- nhân vật
def draw_student(s, cx, dy, wx):
    B, LB, SK = (31, 95, 208), (53, 176, 238), (241, 199, 160)
    hx, hy = wx - 4, OY + dy - 6
    R(s, (34, 48, 74), cx - 13, 102 + dy, 11, 23)
    R(s, (34, 48, 74), cx + 2, 102 + dy, 11, 23)
    R(s, (17, 17, 17), cx - 15, 124 + dy, 14, 6)
    R(s, (17, 17, 17), cx + 1, 124 + dy, 14, 6)
    pygame.draw.line(s, SK, (cx + 18, 68 + dy), (hx, hy), 7)
    C(s, SK, hx, hy, 4)
    pygame.draw.line(s, B, (cx + 16, 68 + dy), (cx + 25, 67 + dy), 7)
    R(s, (85, 85, 85), wx - 8, OY + dy - 14, 16, 14)
    R(s, (255, 255, 255), cx - 17, 58 + dy, 34, 46)
    pygame.draw.rect(s, (197, 208, 222), (cx - 17, 58 + dy, 34, 46), 1)
    R(s, B, cx - 27, 58 + dy, 11, 16)
    R(s, LB, cx - 27, 73 + dy, 11, 3)
    R(s, SK, cx - 25, 76 + dy, 7, 15)
    R(s, B, cx - 17, 85 + dy, 34, 2)
    text(s, "CTU", 9, B, (cx - 15, 74 + dy), "topleft")
    poly(s, LB, [(cx + 9, 69 + dy), (cx + 14, 74 + dy), (cx + 9, 79 + dy), (cx + 4, 74 + dy)])
    poly(s, B, [(cx - 10, 56 + dy), (cx + 10, 56 + dy), (cx, 67 + dy)])
    C(s, SK, cx, 42 + dy, 14)
    pygame.draw.circle(s, (26, 26, 26), (cx, 40 + dy), 14, draw_top_left=True, draw_top_right=True)
    R(s, (26, 26, 26), cx - 14, 39 + dy, 28, 2)
    C(s, (26, 26, 26), cx - 5, 45 + dy, 2)
    C(s, (26, 26, 26), cx + 5, 45 + dy, 2)


# ---------------------------------------------------------------- cảnh nền các map
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

    r(hsl(h, 55, 80), 0, 0, W, 130)
    r("#a9794a", 0, 120, W, 10)
    if k == "Căn tin":
        r("#8a5a2b", 480, 70, 300, 50); r("#6b4220", 480, 66, 300, 6); t("CĂN TIN", 630, 50, 24, "#b33")
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
        t("CƠM TẤM", 610, 60, 24, "#b33"); r("#333333", 480, 85, 120, 35)
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
        t("PHÒNG THI", 720, 52, 20, "#b33")
        for i in range(4):
            x = 40 + i * 70; r("#c28b4e", x, 92, 56, 6); r("#ffffff", x + 16, 86, 18, 6); r("#7a5230", x + 26, 98, 5, 22)
        r("#7a5230", 640, 90, 100, 8); r("#7a5230", 650, 98, 6, 22); r("#7a5230", 724, 98, 6, 22)


def draw_menu_scene(s, t):
    for y in range(300):
        f = y / 300.0
        pygame.draw.rect(s, (int(74 + 131 * f), int(168 + 70 * f), int(240 + 15 * f)), (0, y, W, 1))
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
    R(s, (107, 66, 32), 466, 255, 8, 40); C(s, (60, 154, 76), 470, 245, 26); C(s, (60, 154, 76), 452, 262, 16); C(s, (60, 154, 76), 488, 262, 16)
    R(s, (122, 74, 34), 0, 302, W, 198)
    for i in range(70): R(s, (106, 63, 26), (i * 137) % 800, 310 + (i * 59) % 185, 5, 3)
    for x, y, nm in ((250, 360, "laptop"), (300, 450, "coin"), (480, 420, "wallet"), (560, 480, "coin"), (640, 370, "wallet"),
                     (720, 440, "coin"), (760, 340, "wallet"), (150, 470, "coin"), (420, 360, "coin"), (60, 420, "wallet")):
        draw_item(s, {"n": nm, "r": TYPES[nm]["r"], "c": TYPES[nm]["c"], "x": x, "y": y})
    a = math.sin(t * 1.5) * .9
    ln_ = 140 + math.sin(t * .7) * 25
    wx, wy = OX - 242, OY + 170
    draw_student(s, OX - 48 - 242, 170, wx)
    ex, ey = wx + math.sin(a) * ln_, wy + math.cos(a) * ln_
    pygame.draw.line(s, (34, 34, 34), (wx, wy), (ex, ey), 3); C(s, (34, 34, 34), ex, ey, 6)
    # thanh trạng thái sinh tồn
    s.alpha_fill((14, 12, 190, 30), (0, 0, 0, 115))
    text(s, "Mì gói x2   Cà phê x1", 14, (255, 255, 255), (28, 27), "midleft")


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        self.S = {"coins": 0, "prog": 0, "up": {}, "stars": [0] * len(LV),
                  "profile": {"name": "", "id": "", "major": ""}, "seen": {}, "bought": [], "diploma": None,
                  "ach": {}}
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.S.update(d)
            self.S["stars"] = (list(self.S.get("stars", [])) + [0] * len(LV))[:len(LV)]
        except Exception:
            pass
        self.state = "menu"
        self.cur = 0
        self.items = []
        self.score = 0
        self.left = TIME
        self.boost = 0
        self.t = 0
        self.hook = self.new_hook()
        self.pend = None
        self.msg = ""
        self.click = None
        self.result = (0, 0)
        self.run = True
        self.eq = {u[0]: True for u in UPGRADES}
        self.stun = 0
        self.slow = 0
        self.flash = ("", 0)
        self.counts = {}
        self.earned = 0
        self.sch_at = 10
        self.sch_done = True
        self.fs = False
        self.pf = 0
        self.tab = 0
        self.scroll = 0
        self.back = "menu"
        self.used_help = False   # ván này đã dùng vật phẩm hỗ trợ chưa
        self.bad_hit = False     # ván này đã kéo trúng vật phẩm có hại chưa
        self.toasts = []         # hàng đợi thông báo thành tựu

    # ---- thành tựu
    def unlock(self, key):
        ach = self.S.setdefault("ach", {})
        if key in ach:
            return
        ach[key] = time.strftime("%d/%m/%Y")
        self.toasts.append({"key": key, "t": 0.0})

    def draw_toast(self, s, dt):
        """Thông báo thành tựu kiểu Steam: trượt lên từ góc phải dưới, giữ vài giây rồi trượt xuống."""
        if not self.toasts:
            return
        tt = self.toasts[0]
        tt["t"] += dt
        DUR, IN = 4.8, 0.45
        t = tt["t"]
        if t >= DUR:
            self.toasts.pop(0)
            return
        ease = lambda x: 1 - (1 - max(0.0, min(1.0, x))) ** 3
        p = ease(t / IN) if t < IN else (1 - ease((t - (DUR - IN)) / IN) if t > DUR - IN else 1.0)
        w, h = 290, 66
        x = W - w - 10
        y = H - 10 - h + (1 - p) * (h + 24)
        name = ACH_INFO[tt["key"]][1]
        s.alpha_fill((x, y, w, h), (24, 28, 38, 240), 8)
        pygame.draw.rect(s, (245, 197, 24), (x, y, w, h), 2, border_radius=8)
        draw_badge(s, tt["key"], x + 37, y + h / 2, 24, True)
        text(s, "Thành tựu đã mở khóa!", 11, (245, 197, 24), (x + 72, y + 10), "topleft")
        sz = 16
        while sz > 10 and font(sz, True).size(name)[0] > w - 84:
            sz -= 1
        text(s, name, sz, (255, 255, 255), (x + 72, y + 31), "topleft")

    # ---- tiện ích
    def toggle_fs(self):
        try:
            pygame.display.toggle_fullscreen()
            self.fs = not self.fs
        except Exception:
            pass

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

    def button(self, s, rect, label, bg=(200, 137, 26), fg=(255, 255, 255), size=20, enabled=True, sub=None):
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(mpos())
        c = bg if enabled else (110, 110, 110)
        if hover: c = tuple(min(255, v + 25) for v in c)
        pygame.draw.rect(s, c, rect, border_radius=10)
        if sub is None:
            text(s, label, size, fg, rect.center)
        else:
            text(s, label, size, fg, (rect.centerx, rect.centery - 8))
        return enabled and self.click is not None and rect.collidepoint(self.click)

    def overlay(self, s, alpha=140):
        s.alpha_fill((0, 0, W, H), (42, 33, 22, alpha))

    # ---- chuyển trạng thái
    def start(self, i):
        self.cur, self.score, self.left, self.boost, self.t = i, 0, TIME, 0, 0
        self.stun = 0
        self.slow = 0
        self.flash = ("", 0)
        self.counts = {}
        self.earned = 0
        self.eq = {u[0]: True for u in UPGRADES}
        self.used_help = False
        self.bad_hit = False
        self.sch_at = random.uniform(TIME * 0.16, TIME * 0.64)
        self.sch_done = i < len(LV) - 2  # học bổng chỉ có ở 2 màn cuối
        self.hook = self.new_hook()
        self.spawn()
        self.state = "play"

    def E(self, k):
        """Cấp nâng cấp đang được trang bị (bật) trong ván này."""
        return self.U(k) if self.eq.get(k, True) else 0

    def pop(self, msg, t=1.6):
        self.flash = (msg, t)

    def place(self, name):
        p = TYPES[name]
        r = p["r"]
        for _ in range(60):
            it = {"n": name, "r": r, "v": p["v"], "sp": p["sp"], "c": p["c"],
                  "x": r + 20 + random.random() * (W - 2 * r - 40),
                  "y": 170 + r + random.random() * (H - 50 - 170 - 2 * r)}
            if all(math.hypot(o["x"] - it["x"], o["y"] - it["y"]) > o["r"] + it["r"] + 8 for o in self.items):
                self.items.append(it)
                return True
        return False

    def pick(self):
        pool = POOLS[LV[self.cur]["bi"]]
        name = random.choices([n for n, _ in pool], [w for _, w in pool])[0]
        if name == "landlord":
            hi = self.hook["item"]
            if any(o["n"] == "landlord" for o in self.items) or (hi and hi["n"] == "landlord"):
                name = "coin"
        return name

    def spawn(self):
        self.items = []
        self.place("laptop")
        tries = 0
        while len(self.items) < 14 and tries < 100:
            tries += 1
            self.place(self.pick())

    def finish(self):
        n = stars_of(self.score, self.cur)
        ok = n > 0
        if n > self.S["stars"][self.cur]:
            self.S["stars"][self.cur] = n
        gain = self.score if ok else self.score // 2
        self.earned = gain
        self.S["coins"] += gain
        if ok and self.cur == self.S["prog"] and self.S["prog"] < len(LV):
            self.S["prog"] += 1
        if ok and self.cur == len(LV) - 1:
            g = self.gpa()
            old = self.S.get("diploma")
            if not old or g >= old.get("gpa", 0):
                self.S["diploma"] = {"rank": rank_of(g), "gpa": round(g, 2), "date": time.strftime("%d/%m/%Y")}
        # ---- thành tựu
        if n == 3:
            self.unlock("three_star")
        if ok and not self.used_help:
            self.unlock("no_help")
        if ok and not self.bad_hit:
            self.unlock("clean")
        self.save()
        self.result = (n, ok)
        self.state = "over"

    def drop(self):
        if self.state == "play" and self.hook["mode"] == "swing" and self.stun <= 0:
            self.hook["mode"] = "out"
            if any(self.E(k) > 0 for k in ("rope", "steel", "bag", "mag")):
                self.used_help = True

    def coffee(self):
        if self.state == "play" and self.U("coffee") > 0 and self.boost <= 0:
            self.S["up"]["coffee"] -= 1
            self.boost = 5
            self.used_help = True
            self.save()

    def slot(self, i):
        """Nút 1-5: trang bị / dùng nâng cấp trong màn chơi."""
        if self.state != "play":
            return
        uid = UPGRADES[i][0]
        if uid == "coffee":
            self.coffee()
        elif self.U(uid) > 0:
            self.eq[uid] = not self.eq.get(uid, True)

    def ask(self, kind):
        if self.state == "play":
            self.pend = kind
            self.state = "confirm"

    def collect(self, it):
        """Vật phẩm được kéo về tới tay sinh viên."""
        n = it["n"]
        p = TYPES[n]
        self.counts[n] = self.counts.get(n, 0) + 1
        seen = self.S.setdefault("seen", {})
        seen[n] = seen.get(n, 0) + 1
        msgs = []
        v = it["v"]
        if v > 0:
            g = round(v * (1 + .15 * self.E("bag")))
            self.score += g
            msgs.append(f"+{g}")
        elif v < 0:
            self.score = max(0, self.score + v)
            msgs.append(f"{v} điểm!")
        if p.get("lose"):
            self.left = max(0, self.left - p["lose"])
            msgs.append(f"-{p['lose']}s")
        if p.get("slow"):
            self.slow = p["slow"]
            msgs.append("móc bị chậm")
        if p.get("stun"):
            self.stun = p["stun"]
            msgs.append(f"choáng {p['stun']}s!")
        if msgs:
            self.pop(f"{p['name']}: " + " · ".join(msgs) if n in BAD else " ".join(msgs), 1.4)
        if n not in ("laptop", "scholarship"):
            self.place(self.pick())

    # ---- cập nhật
    def update(self, dt):
        self.left -= dt
        if self.boost > 0: self.boost -= dt
        if self.slow > 0: self.slow -= dt
        if self.stun > 0: self.stun -= dt
        if self.flash[1] > 0: self.flash = (self.flash[0], self.flash[1] - dt)
        if self.left <= 0:
            self.left = 0
            self.finish()
            return
        # học bổng: chạy ngang qua một lần duy nhất rồi mất
        if not self.sch_done and TIME - self.left >= self.sch_at:
            self.sch_done = True
            self.items.append({"n": "scholarship", "r": 11, "v": 1000, "sp": 5, "c": (255, 215, 0),
                               "x": -15.0, "y": random.uniform(185, 330), "vx": 170.0})
            self.pop("Học bổng xuất hiện!", 2)
        for it in self.items:
            if "vx" in it: it["x"] += it["vx"] * dt
        self.items = [it for it in self.items if "vx" not in it or it["x"] < W + 25]
        spd = (1 + .1 * self.E("rope")) * (1.6 if self.boost > 0 else 1) * (0.5 if self.slow > 0 else 1)
        h = self.hook
        if h["mode"] == "swing":
            if self.stun <= 0: self.t += dt
            h["a"] = math.sin(self.t * 1.8) * 1.2
            h["len"] = 40
        elif h["mode"] == "out":
            h["len"] += 360 * dt
            x, y = OX + math.sin(h["a"]) * h["len"], OY + math.cos(h["a"]) * h["len"]
            for it in self.items:
                mg = 35 if self.E("mag") and it["n"] not in BAD and it["sp"] >= 4 else 0
                if math.hypot(it["x"] - x, it["y"] - y) < it["r"] + 6 + mg:
                    h["item"] = it
                    if it["n"] in BAD:
                        self.bad_hit = True
                    self.items.remove(it)
                    h["mode"] = "in"
                    break
            if x < 5 or x > W - 5 or y > H - 5:
                h["mode"] = "in"
                self.left = max(0, self.left - MISS_PENALTY)
                self.pop(f"Kéo hụt! -{MISS_PENALTY}s", 1.2)
        else:
            it = h["item"]
            hv = 1 + .3 * self.E("steel") if it and it["sp"] < 3 else 1
            h["len"] -= (it["sp"] * 60 * hv if it else 380) * spd * dt
            if it:
                it["x"] = OX + math.sin(h["a"]) * h["len"]
                it["y"] = OY + math.cos(h["a"]) * h["len"]
            if h["len"] <= 40:
                h["len"] = 40
                if it:
                    self.collect(it)
                h["item"] = None
                h["mode"] = "swing"
                self.t = math.asin(max(-1, min(1, h["a"] / 1.2))) / 1.8

    # ---- vẽ màn chơi
    def draw_play(self, s):
        L = LV[self.cur]
        s.fill(hsl(L["hue"], 65, 74))
        R(s, hsl(L["hue"], 38, 32), 0, 130, W, H - 130)
        scene(s, re.sub(r" \d+$", "", L["name"]), L["hue"])
        h = self.hook
        for it in self.items: draw_item(s, it)
        if h["item"]: draw_item(s, h["item"])
        x, y = OX + math.sin(h["a"]) * h["len"], OY + math.cos(h["a"]) * h["len"]
        pygame.draw.line(s, (34, 34, 34), (OX, OY), (x, y), 3)
        C(s, (34, 34, 34), x, y, 6)
        if h["item"]: draw_item(s, h["item"])
        draw_student(s, OX - 48, 0, OX)
        if self.stun > 0 and self.state in ("play", "confirm"):
            for i in range(3):
                ang = pygame.time.get_ticks() / 200.0 + i * 2.09
                star(s, OX - 48 + math.cos(ang) * 18, 22 + math.sin(ang) * 5, 5, (255, 230, 60))
            text(s, f"Choáng {math.ceil(self.stun)}s", 14, (200, 40, 40), (OX - 48, 8))
        t1, t2, t3 = thresholds(self.cur)
        nxt = t1 if self.score < t1 else t2 if self.score < t2 else t3
        r = text(s, f"Điểm: {self.score}/{nxt}", 20, (34, 34, 34), (14, 20), "topleft")
        for i in range(stars_of(self.score, self.cur)): star(s, r.right + 16 + i * 18, 31, 8, (240, 180, 0))
        extra = ("  (cà phê)" if self.boost > 0 else "") + ("  (chậm)" if self.slow > 0 else "")
        text(s, f"{math.ceil(self.left)}s" + extra, 20, (34, 34, 34), (W - 14, 20), "topright")
        text(s, f"{BIG[L['bi']][0]} · Màn {L['mi'] + 1}: {L['name']}", 15, (34, 34, 34), (OX, 140))
        if self.flash[1] > 0:
            text(s, self.flash[0], 24, (255, 255, 255), (OX, 175), shadow=True)

    def play_ui(self, s):
        over = False
        if self.button(s, (10, H - 44, 110, 34), "Thoát", (192, 57, 43), size=16): self.ask("exit"); over = True
        if self.button(s, (124, H - 44, 120, 34), "Kết thúc ván", size=16): self.ask("end"); over = True
        for i, (uid, name, desc, price, mx) in enumerate(UPGRADES):
            n = self.U(uid)
            on = self.eq.get(uid, True)
            rect = (252 + i * 110, H - 44, 106, 34)
            if uid == "coffee":
                bg = (255, 160, 40) if self.boost > 0 else (200, 137, 26)
                sub = f"x{n}"
            else:
                bg = (46, 158, 79) if on else (150, 90, 40)
                sub = f"Lv{n} " + ("BẬT" if on else "TẮT")
            if self.button(s, rect, " ", bg, enabled=n > 0): self.slot(i); over = True
            text(s, f"{i + 1}. {SHORT[uid]}", 14, (255, 255, 255), (rect[0] + 53, rect[1] + 10))
            text(s, sub, 12, (255, 255, 255), (rect[0] + 53, rect[1] + 25), bold=False)
        return over

    # ---- các màn hình
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
                over = self.play_ui(s)
                if self.click and not over: self.drop()
        elif st == "confirm":
            self.draw_play(s)
            self.overlay(s)
            text(s, "Bạn có chắc không?", 40, (255, 255, 255), (OX, 170))
            msg = "Thoát game? Kết quả ván này sẽ bị bỏ qua." if self.pend == "exit" else "Kết thúc ván và xem kết quả?"
            text(s, msg, 20, (240, 230, 210), (OX, 220), bold=False)
            if self.button(s, (OX - 215, 270, 200, 50), "Đồng ý"):
                if self.pend == "exit": self.state = "menu"
                else: self.finish()
            elif self.button(s, (OX + 15, 270, 200, 50), "Không", (192, 57, 43)):
                self.state = "play"
        elif st == "over":
            self.screen_over(s)
        elif st == "profile":
            self.screen_profile(s)
        elif st == "coll":
            self.screen_coll(s)
        elif st == "diploma":
            self.screen_diploma(s)
        elif st == "ach":
            self.screen_ach(s)
        self.draw_toast(s, dt)

    def screen_menu(self, s):
        draw_menu_scene(s, pygame.time.get_ticks() / 1000.0)
        # bảng thông tin trên đầu nhân vật (giống tên người chơi trong Minecraft)
        pr = self.S["profile"]
        lines = [(pr["name"] or "Sinh viên", 18, (255, 255, 255), True),
                 (f"MSSV: {pr['id'] or 'chưa nhập'}", 13, (200, 230, 255), False),
                 (f"Ngành: {pr['major'] or 'chưa nhập'}", 13, (200, 230, 255), False)]
        wmax = max(font(sz, b).size(t)[0] for t, sz, c, b in lines)
        bw_, bh_ = wmax + 24, 74
        cx = OX - 48 - 242
        bx = max(6, min(W - bw_ - 6, cx - bw_ // 2))
        by = 124
        s.alpha_fill((bx, by, bw_, bh_), (0, 0, 0, 150))
        pygame.draw.rect(s, (255, 255, 255), (bx, by, bw_, bh_), 1)
        poly(s, (30, 30, 30), [(cx - 6, by + bh_), (cx + 6, by + bh_), (cx, by + bh_ + 8)])
        yy = by + 6
        for t, sz, c, b in lines:
            text(s, t, sz, c, (bx + bw_ // 2, yy + sz // 2 + 3), bold=b)
            yy += sz + 7
        if self.click and pygame.Rect(bx, by, bw_, bh_).collidepoint(self.click):
            self.pf = 0
            self.state = "profile"
            return
        text(s, "SINH TỒN ĐẠI HỌC", 54, (255, 210, 40), (OX, 56), shadow=True)
        sub_t = "Sinh viên sinh tồn: đào xu, qua môn, sống sót đến cuối kỳ!"
        sw = font(14, True).size(sub_t)[0] + 24
        s.alpha_fill((OX - sw // 2, 98, sw, 26), (255, 255, 255, 235), 13)
        text(s, sub_t, 14, (10, 60, 190), (OX, 111))
        if self.button(s, (OX - 110, 196, 220, 48), "Chơi game", size=24): self.state = "sel"
        elif self.button(s, (OX - 110, 252, 220, 48), "Bộ sưu tập", (46, 120, 180), size=24): self.tab = 0; self.scroll = 0; self.state = "coll"
        elif self.button(s, (OX - 110, 308, 220, 48), "Thành tựu", (140, 80, 190), size=24): self.scroll = 0; self.state = "ach"
        elif self.button(s, (OX - 110, 364, 220, 48), "Thoát game", (240, 240, 240), (59, 42, 20), size=24): self.run = False
        text(s, "Được tạo bởi Cao Thiên Phú và Nguyễn Phát Tài", 13, (255, 255, 255), (W - 10, H - 8), "bottomright", shadow=True)
        if self.button(s, (14, H - 46, 200, 34), "Đặt tên · MSSV · Ngành", (31, 95, 208), size=14):
            self.pf = 0
            self.state = "profile"

    # ---- thông tin sinh viên
    FIELDS = [("Họ và tên", "name", 20), ("MSSV", "id", 12), ("Ngành", "major", 28)]

    def on_text(self, txt):
        if self.state != "profile": return
        lab, key, mx = self.FIELDS[self.pf]
        txt = "".join(ch for ch in txt if ch.isprintable())
        v = self.S["profile"][key]
        self.S["profile"][key] = (v + txt)[:mx]

    def profile_key(self, k, uni=""):
        lab, key, mx = self.FIELDS[self.pf]
        if k == pygame.K_BACKSPACE:
            self.S["profile"][key] = self.S["profile"][key][:-1]
        elif k == pygame.K_TAB:
            self.pf = (self.pf + 1) % len(self.FIELDS)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.save()
            self.state = "menu"
        elif uni and uni not in "\t\r\n":
            self.on_text(uni)  # dự phòng khi hệ thống không gửi sự kiện TEXTINPUT

    def screen_profile(self, s):
        s.fill((42, 33, 22))
        text(s, "Thông tin sinh viên", 28, (255, 255, 255), (OX, 36))
        text(s, "Gõ để nhập · Tab: chuyển ô · Enter: lưu", 14, (200, 190, 170), (OX, 66), bold=False)
        y = 96
        for i, (lab, key, mx) in enumerate(self.FIELDS):
            text(s, lab, 18, (245, 197, 24), (OX - 260, y), "topleft")
            rect = pygame.Rect(OX - 260, y + 26, 520, 44)
            focus = i == self.pf
            pygame.draw.rect(s, (70, 56, 38), rect, border_radius=8)
            pygame.draw.rect(s, (245, 197, 24) if focus else (120, 100, 70), rect, 2, border_radius=8)
            cur = "|" if focus and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            text(s, self.S["profile"][key] + cur, 20, (255, 255, 255), (rect.x + 12, rect.centery), "midleft", bold=False)
            if self.click and rect.collidepoint(self.click): self.pf = i
            y += 88
        if self.button(s, (OX - 110, y + 10, 220, 46), "Lưu", (46, 158, 79), size=22):
            self.save()
            self.state = "menu"

    # ---- bộ sưu tập
    def coll_state(self, k):
        S = self.S
        if k == "diploma":
            d = S.get("diploma")
            return (bool(d), f"Loại {d['rank']}" if d else "Chưa tốt nghiệp")
        if k in UP_NAME:
            ok = k in S.get("bought", []) or self.U(k) > 0
            return (ok, "Đã mua" if ok else "Chưa mua")
        n = S.get("seen", {}).get(k, 0)
        return (n > 0, f"Đã kéo: {n}" if n else "Chưa kéo")

    def on_wheel(self, d):
        if self.state in ("coll", "ach"):
            self.scroll += d

    def on_drag(self, dy):
        if self.state in ("coll", "ach") and mpos()[1] >= 84:
            self.scroll -= dy

    def coll_key(self, k):
        if k == pygame.K_UP: self.scroll -= 40
        elif k == pygame.K_DOWN: self.scroll += 40
        elif k == pygame.K_ESCAPE: self.state = "menu"

    def screen_coll(self, s):
        s.fill((42, 33, 22))
        total = sum(len(v) for _, v in COLL)
        have = sum(1 for _, v in COLL for k in v if self.coll_state(k)[0])
        text(s, "Bộ sưu tập", 28, (255, 255, 255), (OX, 26))
        text(s, f"Đã sưu tầm: {have}/{total}   ·   cuộn chuột hoặc kéo để xem thêm", 14, (240, 230, 210), (OX, 54), bold=False)
        for i, (tn, keys) in enumerate(COLL):
            if self.button(s, (30 + i * 250, 74, 240, 34), tn, (200, 137, 26) if i == self.tab else (90, 80, 70), size=16):
                self.tab = i
                self.scroll = 0
        keys = COLL[self.tab][1]
        cw, ch, gp, cols = 120, 190, 10, 6
        area = pygame.Rect(0, 116, W, H - 116 - 60)
        rows = (len(keys) + cols - 1) // cols
        content = rows * (ch + gp) - gp
        mx = max(0, content - area.h)
        self.scroll = max(0, min(mx, self.scroll))
        s.set_clip(area)
        for i, k in enumerate(keys):
            r_, c_ = divmod(i, cols)
            n_in_row = min(cols, len(keys) - r_ * cols)
            x0 = (W - (n_in_row * cw + (n_in_row - 1) * gp)) // 2
            x, y = x0 + c_ * (cw + gp), 118 + r_ * (ch + gp) - int(self.scroll)
            ok, status = self.coll_state(k)
            card = pygame.Rect(x, y, cw, ch)
            pygame.draw.rect(s, (70, 56, 38) if ok else (52, 44, 34), card, border_radius=10)
            cx = x + cw // 2
            if ok:
                if k in TYPES:
                    draw_item(s, {"n": k, "r": TYPES[k]["r"], "c": TYPES[k]["c"], "x": cx, "y": y + 62})
                elif k in UP_NAME:
                    draw_upgrade(s, k, cx, y + 62)
                else:
                    draw_diploma_icon(s, cx, y + 62)
                name = TYPES[k]["name"] if k in TYPES else UP_NAME.get(k, "Bằng tốt nghiệp")
            else:
                text(s, "?", 44, (120, 110, 95), (cx, y + 62))
                name = "???"
            text(s, name, 13, (255, 255, 255) if ok else (150, 140, 125), (cx, y + 130))
            text(s, status, 13, (245, 197, 24) if ok else (150, 140, 125), (cx, y + 152), bold=False)
            if ok:
                text(s, DESC[k], 11, (210, 200, 180), (cx, y + 174), bold=False)
            if k == "diploma" and ok and self.click and card.collidepoint(self.click) and area.collidepoint(self.click):
                self.back = "coll"
                self.state = "diploma"
        s.set_clip(None)
        if mx > 0:
            pygame.draw.rect(s, (70, 56, 38), (W - 10, area.y, 6, area.h), border_radius=3)
            th = max(30, int(area.h * area.h / content))
            ty = area.y + int((area.h - th) * self.scroll / mx)
            pygame.draw.rect(s, (245, 197, 24), (W - 10, ty, 6, th), border_radius=3)
        if self.button(s, (OX - 110, H - 52, 220, 40), "Về menu", (90, 80, 70), size=18): self.state = "menu"

    # ---- thành tựu
    def screen_ach(self, s):
        s.fill((42, 33, 22))
        got = self.S.get("ach", {})
        have = sum(1 for a in ACHIEVEMENTS if a[0] in got)
        text(s, "Thành tựu", 28, (255, 255, 255), (OX, 26))
        text(s, f"Đã mở khóa: {have}/{len(ACHIEVEMENTS)}", 15, (245, 197, 24), (OX, 56))
        area = pygame.Rect(0, 80, W, H - 80 - 60)
        rh, gp = 96, 10
        content = len(ACHIEVEMENTS) * (rh + gp) - gp
        mx = max(0, content - area.h)
        self.scroll = max(0, min(mx, self.scroll))
        s.set_clip(area)
        for i, (key, name, desc, hint) in enumerate(ACHIEVEMENTS):
            ok = key in got
            y = 84 + i * (rh + gp) - int(self.scroll)
            card = pygame.Rect(40, y, 720, rh)
            pygame.draw.rect(s, (70, 56, 38) if ok else (52, 44, 34), card, border_radius=10)
            if ok:
                pygame.draw.rect(s, (245, 197, 24), card, 2, border_radius=10)
            draw_badge(s, key, card.x + 54, card.centery, 34, ok)
            text(s, name, 20, (255, 255, 255) if ok else (170, 160, 145), (card.x + 108, y + 12), "topleft")
            text(s, desc, 14, (225, 215, 195) if ok else (160, 150, 135), (card.x + 108, y + 42), "topleft", bold=False)
            text(s, hint, 12, (190, 180, 160) if ok else (130, 120, 105), (card.x + 108, y + 66), "topleft", bold=False)
            text(s, f"Đã mở khóa · {got[key]}" if ok else "Chưa mở khóa", 13,
                 (245, 197, 24) if ok else (150, 140, 125), (card.right - 16, y + 14), "topright")
        s.set_clip(None)
        if mx > 0:
            pygame.draw.rect(s, (70, 56, 38), (W - 10, area.y, 6, area.h), border_radius=3)
            th = max(30, int(area.h * area.h / content))
            ty = area.y + int((area.h - th) * self.scroll / mx)
            pygame.draw.rect(s, (245, 197, 24), (W - 10, ty, 6, th), border_radius=3)
        if self.button(s, (OX - 110, H - 52, 220, 40), "Về menu", (90, 80, 70), size=18): self.state = "menu"

    # ---- bằng tốt nghiệp
    def screen_diploma(self, s):
        d = self.S.get("diploma")
        s.fill((42, 33, 22))
        if not d:
            text(s, "Bạn chưa tốt nghiệp. Hãy hoàn thành 20 màn!", 20, (255, 255, 255), (OX, 200))
        else:
            ink = (60, 45, 25)
            card = pygame.Rect(40, 20, 720, 410)
            pygame.draw.rect(s, (250, 240, 205), card, border_radius=8)
            pygame.draw.rect(s, (200, 150, 30), card, 6, border_radius=8)
            pygame.draw.rect(s, (200, 150, 30), card.inflate(-28, -28), 2)
            pr = self.S["profile"]
            text(s, "ĐẠI HỌC CẦN THƠ", 20, (31, 95, 208), (OX, 58))
            text(s, "BẰNG TỐT NGHIỆP", 40, (150, 30, 30), (OX, 102))
            text(s, "Chứng nhận sinh viên", 16, ink, (OX, 144), bold=False)
            text(s, (pr["name"] or "(chưa nhập tên)").upper(), 34, (30, 30, 30), (OX, 188))
            text(s, f"MSSV: {pr['id'] or '—'}", 20, ink, (OX, 232), bold=False)
            text(s, f"Ngành: {pr['major'] or '—'}", 20, ink, (OX, 262), bold=False)
            text(s, "đã hoàn thành 20 màn của chương trình Sinh viên sinh tồn", 15, ink, (OX, 298), bold=False)
            text(s, f"Tốt nghiệp loại  {d['rank'].upper()}", 28, (150, 30, 30), (OX, 340))
            text(s, f"GPA: {d['gpa']:.2f}/4.0   ·   Ngày cấp: {d['date']}", 16, ink, (OX, 382), bold=False)
            C(s, (200, 40, 40), 685, 360, 34)
            C(s, (150, 20, 20), 685, 360, 28)
            star(s, 685, 360, 18, (255, 220, 60))
        if self.button(s, (OX - 110, H - 56, 220, 40), "Quay lại", (90, 80, 70), size=18): self.state = self.back

    def screen_sel(self, s):
        s.fill((42, 33, 22))
        text(s, "Chọn màn chơi", 26, (255, 255, 255), (OX, 22))
        text(s, f"Xu: {self.S['coins']}   |   Điểm tích lũy: {self.total():.1f}/20   |   GPA: {self.gpa():.2f}/4.0", 16, (240, 230, 210), (OX, 52), bold=False)
        text(s, "Qua màn: 800 điểm = 1 sao · 900 điểm = 2 sao · 1000 điểm = 3 sao", 13, (200, 190, 170), (OX, 72), bold=False)
        k = 0
        y = 92
        for bn, maps in BIG:
            text(s, bn, 17, (245, 197, 24), (20, y), "topleft")
            n = len(maps)
            bw, gap = 122, 6
            x0 = (W - (n * bw + (n - 1) * gap)) // 2
            for i, m in enumerate(maps):
                locked = k > self.S["prog"]
                rect = (x0 + i * (bw + gap), y + 22, bw, 52)
                done = self.S["stars"][k] > 0
                bg = (200, 137, 26) if not done else (46, 158, 79)
                need_pay = (k == UNLOCK_LV and not locked and not self.S.get("paid4"))
                if need_pay:
                    if self.button(s, rect, " ", (150, 60, 60), size=11,
                                   enabled=self.S["coins"] >= UNLOCK_COST):
                        self.S["coins"] -= UNLOCK_COST
                        self.S["paid4"] = True
                        self.save()
                    mx_ = rect[0] + bw // 2
                    text(s, "Đóng tiền trọ và", 10, (255, 255, 255), (mx_, rect[1] + 10))
                    text(s, "tiền nợ tín chỉ", 10, (255, 255, 255), (mx_, rect[1] + 23))
                    text(s, f"{UNLOCK_TXT} xu", 11, (255, 230, 150), (mx_, rect[1] + 39))
                    k += 1
                    continue
                if self.button(s, rect, f"{k + 1}. {m}", bg, size=11, enabled=not locked, sub=True):
                    self.start(k)
                if not locked:
                    for j in range(3):
                        star(s, rect[0] + bw // 2 - 18 + j * 18, rect[1] + 38, 7, (255, 230, 90), filled=j < self.S["stars"][k])
                else:
                    text(s, "khóa", 11, (200, 200, 200), (rect[0] + bw // 2, rect[1] + 38))
                k += 1
            y += 90
        if self.button(s, (OX - 215, H - 46, 200, 38), "Cửa hàng", size=18): self.msg = ""; self.state = "shop"
        elif self.button(s, (OX + 15, H - 46, 200, 38), "Về menu", (90, 80, 70), size=18): self.state = "menu"

    def screen_shop(self, s):
        s.fill((42, 33, 22))
        text(s, "Cửa hàng nâng cấp", 26, (255, 255, 255), (OX, 24))
        text(s, f"Xu: {self.S['coins']}   {self.msg}", 17, (245, 197, 24), (OX, 54), bold=False)
        y = 80
        for uid, name, desc, price, mx in UPGRADES:
            n = self.U(uid)
            pygame.draw.rect(s, (70, 56, 38), (40, y, 720, 60), border_radius=10)
            text(s, f"{name}  (đang có: {n})", 18, (255, 255, 255), (56, y + 8), "topleft")
            text(s, desc, 14, (210, 200, 180), (56, y + 34), "topleft", bold=False)
            full = n >= mx
            can = (not full) and self.S["coins"] >= price
            if self.button(s, (620, y + 10, 128, 40), "Tối đa" if full else f"{price} xu", size=17, enabled=can):
                self.S["coins"] -= price
                self.S["up"][uid] = n + 1
                bt = self.S.setdefault("bought", [])
                if uid not in bt: bt.append(uid)
                self.msg = f"Đã mua {name}!"
                self.save()
            y += 68
        if self.button(s, (OX - 130, H - 52, 260, 40), "Quay lại chọn màn", (90, 80, 70), size=18): self.state = "sel"

    def screen_over(self, s):
        self.draw_play(s)
        self.overlay(s, 165)
        n, ok = self.result
        t1 = thresholds(self.cur)[0]
        title = ("Tốt nghiệp!" if self.cur == len(LV) - 1 else "Hoàn thành!") if ok else "Chưa đạt!"
        text(s, title, 44, (255, 255, 255), (OX, 55))
        for j in range(3): star(s, OX - 50 + j * 50, 115, 22, (255, 220, 60), filled=j < n)
        text(s, f"Điểm: {self.score}  (cần ≥ {t1} để qua màn)", 20, (240, 230, 210), (OX, 165), bold=False)
        got = "  ·  ".join(f"{TYPES[k]['name']} x{v}" for k, v in self.counts.items()) or "chưa thu được vật phẩm nào"
        text(s, "Đã thu: " + got, 13, (210, 200, 180), (OX, 192), bold=False)
        text(s, f"Xu nhận được: +{self.earned}", 20, (245, 197, 24), (OX, 220))
        text(s, f"Điểm môn: +{PT[n]}   |   Tích lũy: {self.total():.1f}/20", 18, (240, 230, 210), (OX, 248), bold=False)
        text(s, f"GPA: {self.gpa():.2f}/4.0   |   Tổng xu: {self.S['coins']}", 18, (245, 197, 24), (OX, 273))
        y = 300
        if ok and self.cur == len(LV) - 1:
            if self.button(s, (OX - 110, y, 220, 44), "Xem bằng tốt nghiệp", (46, 120, 180)):
                self.back = "over"
                self.state = "diploma"
            y += 54
        if ok and self.cur + 1 == UNLOCK_LV and not self.S.get("paid4"):
            text(s, f"Cần đóng tiền trọ và tiền nợ tín chỉ {UNLOCK_TXT} xu để mở màn lớn 4 (ở màn chọn màn)", 15, (255, 230, 150), (OX, y + 22))
            y += 54
        elif ok and self.cur < len(LV) - 1:
            if self.button(s, (OX - 110, y, 220, 44), "Màn tiếp theo"): self.start(self.cur + 1)
            y += 54
        if self.button(s, (OX - 110, y, 220, 44), "Chơi lại", (90, 80, 70)): self.start(self.cur)
        elif self.button(s, (OX - 110, y + 54, 220, 44), "Chọn màn", (90, 80, 70)): self.state = "sel"


def main():
    global _K
    pygame.init()
    _K = pick_scale()
    CW, CH = int(round(W * _K)), int(round(H * _K))
    try:
        # SCALED: cửa sổ co giãn được, tỉ lệ luôn đúng; game vẽ thẳng ở CW x CH
        screen = pygame.display.set_mode((CW, CH), pygame.SCALED | pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((CW, CH))
    pygame.display.set_caption("Sinh Tồn Đại Học")
    clock = pygame.time.Clock()
    g = Game()
    TI = getattr(pygame, "TEXTINPUT", None)
    WHEEL = getattr(pygame, "MOUSEWHEEL", None)
    try:
        pygame.key.start_text_input()
    except Exception:
        pass
    ti_seen = False
    repeat_on = False
    while g.run:
        dt = min(clock.tick(60) / 1000.0, .05)
        g.click = None
        want = g.state == "profile"
        if want != repeat_on:
            repeat_on = want
            if want: pygame.key.set_repeat(350, 40)
            else: pygame.key.set_repeat()
        events = pygame.event.get()
        if TI and any(ev.type == TI for ev in events):
            ti_seen = True
        for e in events:
            if e.type == pygame.QUIT:
                g.run = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                g.click = (int(e.pos[0] / _K), int(e.pos[1] / _K))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (4, 5):
                g.on_wheel(-40 if e.button == 4 else 40)
            elif WHEEL and e.type == WHEEL:
                g.on_wheel(-e.y * 40)
            elif e.type == pygame.MOUSEMOTION and e.buttons[0]:
                g.on_drag(e.rel[1] / _K)
            elif TI and e.type == TI:
                g.on_text(e.text)
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                g.toggle_fs()
            elif e.type == pygame.KEYDOWN and g.state == "profile":
                g.profile_key(e.key, "" if ti_seen else e.unicode)
            elif e.type == pygame.KEYDOWN and g.state in ("coll", "ach"):
                g.coll_key(e.key)
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_DOWN): g.drop()
                elif e.key == pygame.K_c: g.coffee()
                elif pygame.K_1 <= e.key <= pygame.K_5: g.slot(e.key - pygame.K_1)
                elif e.key == pygame.K_ESCAPE: g.ask("exit")
        g.frame(Canvas(pygame.display.get_surface() or screen, _K), dt)
        pygame.display.flip()
    g.save()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()