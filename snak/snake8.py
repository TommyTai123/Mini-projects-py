import json
import math
import os
import random
import threading
import time
from array import array

# --- Bật chế độ DPI-aware trên Windows: nguyên nhân chính khiến cửa sổ bị mờ khi màn hình
#     đặt tỉ lệ 125%/150% (Windows phóng to cửa sổ lên làm hình bị nhòe) ---
if os.name == "nt":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pygame

try:
    pygame.mixer.pre_init(22050, -16, 1, 512)      # âm thanh mono 16-bit, độ trễ thấp
except Exception:
    pass
pygame.init()

# ====================== CẤU HÌNH ======================
N = 20                                          # lưới 20x20
_info = pygame.display.Info()
DESK_H = _info.current_h if _info.current_h > 0 else 900
CELL = max(18, min(30, (DESK_H - 380) // N))    # tự chọn cỡ ô theo chiều cao màn hình
BW = CELL * N                                   # cạnh bảng chơi
W = max(480, BW + 40)
BX, BY = (W - BW) // 2, 188                     # vị trí bảng chơi
DP_Y = BY + BW + 14                             # vị trí hàng nút mũi tên đầu
H = DP_Y + 40 + 4 + 40 + 14
SPEED = 6                                       # số bước di chuyển/giây
FPS = 60
STEP_MS = 1000 / SPEED                         # thời gian của 1 bước logic (ms)
MAX_DRL = 100                                   # đạt 100 điểm rèn luyện là thắng
SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kyluc.json")

BG = (244, 246, 251)
WHITE = (255, 255, 255)
TEXT = (26, 32, 44)
GRAY = (107, 114, 128)
TRACK = (230, 235, 245)
GRID = (238, 241, 248)
BOARD = (252, 252, 254)
BODY = (62, 171, 120)
HEAD = (34, 160, 100)
GREEN = (46, 170, 115)
GREEN_D = (34, 150, 100)
LINE = (225, 230, 240)

# Toàn màn hình KHÔNG phóng ảnh (sẽ bị mờ/răng cưa). Thay vào đó mọi thứ được VẼ LẠI ở độ phân giải thật:
# S = hệ số tỉ lệ (1.0 ở cửa sổ thường), toạ độ thiết kế (W x H) được nhân S khi vẽ.
window = pygame.display.set_mode((W, H))
fullscreen = False
S = 1.0
WS, HS = W, H                                      # kích thước canvas thật = (W*S, H*S)
screen = pygame.Surface((WS, HS)).convert()
view_off = (0, 0)                                  # canvas nằm ở đâu trong cửa sổ (để căn giữa + chuột chính xác)
pygame.display.set_caption("Rắn Săn Điểm Rèn Luyện")
clock = pygame.time.Clock()


def set_fullscreen(on):
    global window, fullscreen
    fullscreen = on
    try:
        window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if on else pygame.display.set_mode((W, H))
    except Exception:
        fullscreen = False
        window = pygame.display.set_mode((W, H))
    apply_scale()


def apply_scale():
    """Tính lại tỉ lệ theo cửa sổ hiện tại rồi dựng lại toàn bộ hình ảnh ở độ phân giải mới."""
    global S, WS, HS, screen, view_off
    ww, wh = window.get_size()
    S = min(ww / W, wh / H) if fullscreen else 1.0
    WS, HS = max(1, I(W * S)), max(1, I(H * S))
    screen = pygame.Surface((WS, HS)).convert()
    view_off = ((ww - WS) // 2, (wh - HS) // 2)
    rebuild_assets()


def sp(p):
    """Toạ độ thiết kế -> toạ độ pixel thật."""
    return (I(p[0] * S), I(p[1] * S))


def to_canvas(pos):
    """Toạ độ chuột trên cửa sổ -> toạ độ thiết kế (để bấm nút đúng ở mọi độ phân giải)."""
    return (I((pos[0] - view_off[0]) / S), I((pos[1] - view_off[1]) / S))


def mouse_pos():
    return to_canvas(pygame.mouse.get_pos())


def present():
    if window.get_size() != (WS, HS):                  # viền hai bên nếu màn hình khác tỉ lệ
        window.fill((6, 12, 26) if scene in ("menu", "records") else T["bg"])
    window.blit(screen, view_off)
    pygame.display.flip()


FONT_NAMES = ["segoeui", "arial", "tahoma", "dejavusans"]   # font có hỗ trợ tiếng Việt


def F(size, bold=False):
    return pygame.font.SysFont(FONT_NAMES, max(8, int(round(size * S))), bold=bold)


f_title, f_logo, f_num, f_rank = F(28, True), F(32, True), F(30, True), F(21, True)
f_btn, f_head, f_txt, f_lbl, f_huge = F(20, True), F(24, True), F(15), F(14), F(72, True)

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
KEYS = {
    pygame.K_UP: UP, pygame.K_DOWN: DOWN, pygame.K_LEFT: LEFT, pygame.K_RIGHT: RIGHT,
    pygame.K_w: UP, pygame.K_s: DOWN, pygame.K_a: LEFT, pygame.K_d: RIGHT,
}


# ====================== VẼ SẮC NÉT (SUPERSAMPLING) ======================
# pygame.draw không khử răng cưa nên hình bị lởm chởm/mờ. Ở đây mỗi hình được vẽ
# ở độ phân giải lớn gấp SS lần rồi thu nhỏ mượt (smoothscale) -> viền mịn, nét.
SS = 4
_cache = {}


def I(v):
    return int(round(v))


def aa(w, h, draw, base=WHITE, ss=SS):
    """Vẽ hình kích thước thiết kế (w, h) ở ĐỘ PHÂN GIẢI THẬT (nhân S) với siêu lấy mẫu ss -> nét, không răng cưa."""
    ow, oh = max(1, I(w * S)), max(1, I(h * S))
    s = pygame.Surface((ow * ss, oh * ss), pygame.SRCALPHA)
    s.fill((*base[:3], 0))                  # tránh viền đen khi thu nhỏ
    draw(s, ss * ow / w)                    # k = số pixel trên mỗi đơn vị thiết kế
    return pygame.transform.smoothscale(s, (ow, oh))


def rrect(rect, color, radius, border=None, bw=2):
    if rect.w <= 0 or rect.h <= 0:
        return
    key = ("rr", rect.w, rect.h, color, radius, border, bw)
    spr = _cache.get(key)
    if spr is None:
        def d(s, k):
            box = (0, 0, rect.w * k, rect.h * k)
            pygame.draw.rect(s, color, box, border_radius=I(radius * k))
            if border:
                pygame.draw.rect(s, border, box, max(1, I(bw * k)), border_radius=I(radius * k))
        spr = aa(rect.w, rect.h, d, base=color, ss=4 if rect.w * rect.h * S * S < 120000 else 2)
        _cache[key] = spr
    screen.blit(spr, sp(rect.topleft))


def sprite(key, w, h, draw, base=WHITE):
    spr = _cache.get(key)
    if spr is None:
        spr = aa(w, h, draw, base)
        _cache[key] = spr
    return spr


# ====================== ICON SỰ KIỆN / CLB ======================
def _p(k, dx, dy):
    return (14 * k + dx * k, 14 * k + dy * k)


def icon_broom(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    pygame.draw.line(s, (120, 80, 50), p(9, -11), p(-1, 2), I(3 * k))
    pygame.draw.polygon(s, (235, 140, 60), [p(-1, 2), p(-11, 8), p(-5, 13), p(5, 5)])


def icon_blood(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    pygame.draw.circle(s, (220, 50, 50), p(0, 3), I(8 * k))
    pygame.draw.polygon(s, (220, 50, 50), [p(0, -10), p(-7, 2), p(7, 2)])


def icon_blood_club(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    pygame.draw.circle(s, (200, 30, 50), p(0, 3), I(9.5 * k))
    pygame.draw.polygon(s, (200, 30, 50), [p(0, -12), p(-8, 1), p(8, 1)])
    pygame.draw.line(s, WHITE, p(-4, 4), p(4, 4), I(2.4 * k))     # dấu cộng (y tế)
    pygame.draw.line(s, WHITE, p(0, 0), p(0, 8), I(2.4 * k))


def icon_book(s, k):
    pygame.draw.rect(s, (60, 120, 220), (I(4 * k), I(6 * k), I(20 * k), I(16 * k)), border_radius=I(3 * k))
    pygame.draw.line(s, WHITE, _p(k, 0, -8), _p(k, 0, 8), I(2 * k))


def icon_ball(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    pygame.draw.circle(s, (240, 140, 30), p(0, 0), I(10 * k))
    pygame.draw.circle(s, (120, 60, 0), p(0, 0), I(10 * k), I(2 * k))
    pygame.draw.line(s, (120, 60, 0), p(-10, 0), p(10, 0), I(2 * k))


def icon_music(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    col = (150, 60, 200)
    pygame.draw.circle(s, col, p(-3, 6), I(5 * k))
    pygame.draw.line(s, col, p(1, 6), p(1, -9), I(3 * k))
    pygame.draw.line(s, col, p(1, -9), p(8, -5), I(3 * k))


def icon_heart(s, k):
    p = lambda dx, dy: _p(k, dx, dy)
    col = (235, 70, 130)
    pygame.draw.circle(s, col, p(-5, -3), I(6 * k))
    pygame.draw.circle(s, col, p(5, -3), I(6 * k))
    pygame.draw.polygon(s, col, [p(-10, 0), p(10, 0), p(0, 11)])


def icon_star(s, k):
    pts = []
    for i in range(10):
        r = 11 if i % 2 == 0 else 5
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(_p(k, r * math.cos(a), r * math.sin(a)))
    pygame.draw.polygon(s, (240, 190, 20), pts)


def make_icon(fn):
    size = I((CELL + 2) * S)
    big = size * 8
    s = pygame.Surface((big, big), pygame.SRCALPHA)
    s.fill((255, 255, 255, 0))
    fn(s, big / 28)
    return pygame.transform.smoothscale(s, (size, size))


# (tên sự kiện, điểm rèn luyện, icon) - mỗi sự kiện cộng 2 hoặc 3 điểm
EVENTS = [
    ("Tổng vệ sinh", 2, make_icon(icon_broom)),
    ("CLB Hiến máu", 3, make_icon(icon_blood_club)),
    ("CLB Học thuật", 2, make_icon(icon_book)),
    ("Giải thể thao", 2, make_icon(icon_ball)),
    ("Văn nghệ", 2, make_icon(icon_music)),
    ("Tình nguyện", 3, make_icon(icon_heart)),
    ("Hội thảo", 2, make_icon(icon_star)),
]


_EVENT_FNS = {"Tổng vệ sinh": icon_broom, "CLB Hiến máu": icon_blood_club, "CLB Học thuật": icon_book,
              "Giải thể thao": icon_ball, "Văn nghệ": icon_music, "Tình nguyện": icon_heart, "Hội thảo": icon_star}
ICON_BY_NAME = {}                                  # icon sự kiện ở độ phân giải hiện tại (dựng lại khi đổi S)


# ====================== KỶ LỤC & XẾP LOẠI ======================
def load_best():
    try:
        with open(SAVE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("best", 0))
    except Exception:
        return 0


def save_best(v):
    try:
        with open(SAVE, "w", encoding="utf-8") as f:
            json.dump({"best": v}, f)
    except Exception:
        pass


def rank(score):
    if score >= 90:
        return "Xuất sắc"
    if score >= 80:
        return "Tốt"
    if score >= 65:
        return "Khá"
    if score >= 50:
        return "Trung bình"
    return "Yếu"


# ====================== ÂM THANH (tự tổng hợp bằng code, không cần file ngoài) ======================
AUDIO, RATE, ACH = False, 22050, 1
music_ch = None
try:
    _fmt = pygame.mixer.get_init()
    if _fmt and _fmt[1] == -16:
        AUDIO, RATE, ACH = True, _fmt[0], _fmt[2]
        pygame.mixer.set_num_channels(12)
        pygame.mixer.set_reserved(1)               # kênh 0 dành riêng cho nhạc nền
        music_ch = pygame.mixer.Channel(0)
except Exception:
    AUDIO = False

SOUNDS = {}
muted = False                                      # bấm phím N để tắt/bật âm thanh
music_playing = False

TIMBRE = {                                         # (bội số tần số, biên độ)
    "sine": [(1, 1.0)],
    "tri": [(1, 1.0), (3, -0.11), (5, 0.04)],
    "bright": [(1, 1.0), (2, 0.5), (3, 0.25)],
    "brass": [(1, 1.0), (2, 0.7), (3, 0.5), (4, 0.35)],
    "bell": [(1, 1.0), (2.76, 0.6), (5.4, 0.35)],
}


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _grow(buf, n):
    if len(buf) < n:
        buf.extend([0.0] * (n - len(buf)))


def add_note(buf, t0, midi, dur, vol=0.3, timbre="sine", att=0.012, rel=0.08, decay=0.0):
    s0, n = int(t0 * RATE), int(dur * RATE)
    _grow(buf, s0 + n)
    pairs = TIMBRE[timbre]
    norm = vol / sum(abs(a) for _, a in pairs)
    w = 2 * math.pi * _hz(midi) / RATE
    an, rn = max(1, int(att * RATE)), max(1, int(rel * RATE))
    sin, exp = math.sin, math.exp
    for i in range(n):
        ph = w * i
        v = 0.0
        for m, a in pairs:
            v += a * sin(m * ph)
        g = min(1.0, i / an, (n - i) / rn)
        if decay:
            g *= exp(-decay * i / RATE)
        buf[s0 + i] += v * norm * g


def add_noise(buf, t0, dur, vol=0.3, hp=0.0, lp=0.0, att=0.01, rel=0.05, decay=0.0, trem=None):
    s0, n = int(t0 * RATE), int(dur * RATE)
    _grow(buf, s0 + n)
    an, rn = max(1, int(att * RATE)), max(1, int(rel * RATE))
    prev = z = 0.0
    rnd, exp, sin = random.random, math.exp, math.sin
    for i in range(n):
        x = rnd() * 2 - 1
        y = x - hp * prev
        prev = x
        if lp:
            z = lp * z + (1 - lp) * y
            y = z
        g = min(1.0, i / an, (n - i) / rn)
        if decay:
            g *= exp(-decay * i / RATE)
        if trem:
            g *= 1 - trem[1] + trem[1] * (0.5 + 0.5 * sin(2 * math.pi * trem[0] * i / RATE))
        buf[s0 + i] += y * vol * g


def add_echo(buf, taps=((0.17, 0.35), (0.34, 0.2))):
    out, n = buf[:], len(buf)
    for d, g in taps:
        off = int(d * RATE)
        _grow(out, n + off)
        for i in range(n):
            out[i + off] += buf[i] * g
    return out


def to_sound(buf, vol=1.0):
    peak = max(1e-9, max(abs(x) for x in buf))
    k = 0.85 / peak
    arr = array("h")
    for x in buf:
        v = int(max(-1.0, min(1.0, x * k)) * 32767)
        arr.append(v)
        if ACH == 2:
            arr.append(v)
    snd = pygame.mixer.Sound(buffer=arr.tobytes())
    snd.set_volume(vol)
    return snd


def make_eat():                                    # "ting" nhỏ khi ăn điểm
    b = []
    add_note(b, 0.0, 79, 0.10, 0.35, "bright", rel=0.04)
    add_note(b, 0.07, 86, 0.35, 0.35, "bell", decay=7)
    return to_sound(b, 0.7)


def make_slither(variant):                         # tiếng rắn rít + sột soạt
    b = []
    add_noise(b, 0.0, 0.9, 0.5, hp=0.93, att=0.2, rel=0.5, trem=(11 + 3 * variant, 0.35))
    add_noise(b, 0.05, 0.8, 0.9, lp=0.85, att=0.3, rel=0.4, trem=(5, 0.5))
    return to_sound(b, 0.5)


def make_lose():                                   # đi xuống buồn khi hết lượt
    b = []
    for k, m in enumerate((67, 66, 65, 64)):
        add_note(b, k * 0.32, m, 0.34, 0.22, "tri", att=0.03, rel=0.1)
    add_note(b, 1.3, 40, 1.0, 0.3, "tri", decay=2.5)
    add_note(b, 1.3, 52, 1.0, 0.12, "tri", decay=2.5)
    return to_sound(b, 0.85)


def make_fanfare(lv):                              # lv 1..4 = Trung bình / Khá / Tốt / Xuất sắc
    b = []
    if lv == 1:
        for m, t in ((67, 0.0), (71, 0.11), (74, 0.22)):
            add_note(b, t, m, 0.14, 0.22, "brass", rel=0.05)
        for m in (67, 71, 74, 79):
            add_note(b, 0.36, m, 0.55, 0.14, "brass", decay=2)
    elif lv == 2:
        for k, m in enumerate((60, 64, 67, 72)):
            add_note(b, k * 0.1, m, 0.14, 0.22, "brass", rel=0.05)
        for m in (48, 60, 64, 67, 72):
            add_note(b, 0.42, m, 0.8, 0.13, "brass", decay=1.6)
        add_note(b, 0.42, 84, 0.7, 0.12, "bell", decay=4)
        b = add_echo(b, ((0.15, 0.25),))
    elif lv == 3:
        for k, m in enumerate((60, 64, 67, 72, 76)):
            add_note(b, k * 0.09, m, 0.13, 0.22, "brass", rel=0.05)
        for m in (36, 48, 60, 64, 67, 72, 76):
            add_note(b, 0.46, m, 1.1, 0.12, "brass", decay=1.3)
        for k, m in enumerate((88, 91, 95)):
            add_note(b, 0.5 + k * 0.12, m, 0.5, 0.1, "bell", decay=5)
        b = add_echo(b)
    else:
        for t in (0.0, 0.14, 0.28):
            add_note(b, t, 67, 0.11, 0.22, "brass", rel=0.03)
        for k, m in enumerate((60, 64, 67, 72, 76, 79, 84)):
            add_note(b, 0.44 + k * 0.075, m, 0.12, 0.2, "brass", rel=0.04)
        t0 = 0.44 + 7 * 0.075
        add_note(b, t0, 33, 0.5, 0.5, "sine", decay=6)                  # trống
        add_noise(b, t0, 1.2, 0.12, hp=0.97, decay=3)                   # chũm chọe
        for m in (36, 48, 60, 64, 67, 72, 79):
            add_note(b, t0, m, 1.9, 0.1, "brass", decay=1.0, rel=0.4)
        for _ in range(12):
            add_note(b, t0 + random.uniform(0, 1.5), random.choice((88, 91, 95, 98, 100)),
                     0.45, 0.08, "bell", decay=5)
        b = add_echo(b, ((0.2, 0.35), (0.4, 0.22), (0.6, 0.12)))
    return to_sound(b, 0.9)


def make_win():                                    # chiến thắng đạt 100 điểm
    b = []
    for t in (0.0, 0.15, 0.3):
        add_note(b, t, 72, 0.12, 0.22, "brass", rel=0.03)
    for t, m, d in ((0.45, 72, 0.35), (0.85, 68, 0.35), (1.25, 70, 0.35), (1.65, 72, 0.2), (1.9, 70, 0.14)):
        add_note(b, t, m, d, 0.22, "brass", rel=0.05)
    t0 = 2.1
    add_note(b, t0, 33, 0.5, 0.5, "sine", decay=6)
    add_noise(b, t0, 1.6, 0.12, hp=0.97, decay=2.5)
    for m in (36, 48, 60, 64, 67, 72, 76):
        add_note(b, t0, m, 2.4, 0.1, "brass", decay=0.8, rel=0.5)
    for _ in range(16):
        add_note(b, t0 + random.uniform(0, 2.0), random.choice((88, 91, 95, 98, 100)), 0.5, 0.08, "bell", decay=5)
    return to_sound(add_echo(b, ((0.2, 0.35), (0.4, 0.22), (0.6, 0.12))), 0.95)


def make_music():                                  # nhạc nền menu: vui nhộn, lặp liền mạch (~19 giây)
    beat = 60 / 100
    chords = [(36, (60, 64, 67)), (33, (57, 60, 64)), (29, (57, 60, 65)), (31, (55, 59, 62))] * 2
    melody = [(76, 79, 76, 74), (72, 76, 81, 79), (81, 79, 77, 76), (74, 79, 83, 79),
              (76, 79, 84, 83), (81, 79, 76, 72), (77, 81, 84, 81), (74, 79, 83, 79)]
    b = []
    for bar, ((root, tri), mel) in enumerate(zip(chords, melody)):
        t = bar * 4 * beat
        for k in range(8):                                              # arpeggio
            add_note(b, t + k * beat / 2, tri[(0, 1, 2, 1, 0, 1, 2, 1)[k]], beat * 0.5, 0.07, "tri", rel=0.05)
        for k in (0, 2):                                                # bass + trống nhẹ
            add_note(b, t + k * beat, root, beat * 1.8, 0.2, "tri", rel=0.1)
            add_note(b, t + k * beat, 33, 0.18, 0.2, "sine", att=0.002, rel=0.05, decay=18)
        for k in range(4):                                              # giai điệu
            add_note(b, t + k * beat, mel[k], beat * 0.92, 0.12, "bright", rel=0.12)
            add_noise(b, t + k * beat + beat / 2, 0.05, 0.03, hp=0.9, decay=40)
    n = len(b)
    out = add_echo(b, ((0.3, 0.25),))
    for i in range(n, len(out)):                                        # gập đuôi vang về đầu -> lặp mượt
        out[i - n] += out[i]
    del out[n:]
    return to_sound(out, 1.0)


def _build_audio():                                # chạy nền để game mở lên ngay
    try:
        SOUNDS["eat"] = make_eat()
        SOUNDS["slither0"], SOUNDS["slither1"] = make_slither(0), make_slither(1)
        SOUNDS["lose"] = make_lose()
        for lv in (1, 2, 3):
            SOUNDS["fan%d" % lv] = make_fanfare(lv)
        SOUNDS["music"] = make_music()
        SOUNDS["fan4"] = make_fanfare(4)
        SOUNDS["win"] = make_win()
    except Exception:
        pass


def sfx(name):
    if AUDIO and not muted:
        snd = SOUNDS.get(name)
        if snd:
            snd.play()


def rank_level(score):
    return 4 if score >= 90 else 3 if score >= 80 else 2 if score >= 65 else 1 if score >= 50 else 0


if AUDIO:
    threading.Thread(target=_build_audio, daemon=True).start()


# ====================== 3 MAP CHƠI (mỗi lần bấm "Chơi game" random 1 map) ======================
THEMES = [
    dict(name="Đồng cỏ", deco="meadow", seed=11, dark=False,
         bg=(232, 246, 236), card=(255, 255, 255), board=(244, 252, 242), border=(196, 226, 202),
         text=(26, 40, 34), sub=(92, 116, 100), track=(208, 230, 214), accent=(46, 170, 115),
         halo=(220, 240, 224), veil=(255, 255, 255, 190), line=(206, 226, 212),
         body=(52, 168, 112), head=(30, 150, 92), tail=(120, 208, 150)),
    dict(name="Sa mạc", deco="desert", seed=22, dark=False,
         bg=(252, 238, 214), card=(255, 251, 243), board=(255, 245, 224), border=(234, 204, 160),
         text=(72, 42, 20), sub=(150, 108, 76), track=(240, 220, 190), accent=(226, 120, 50),
         halo=(250, 226, 192), veil=(255, 247, 232, 190), line=(236, 212, 176),
         body=(178, 84, 40), head=(142, 56, 26), tail=(226, 152, 92)),
    dict(name="Đêm neon", deco="night", seed=33, dark=True,
         bg=(8, 13, 28), card=(22, 32, 58), board=(13, 21, 41), border=(44, 78, 124),
         text=(238, 244, 255), sub=(140, 162, 192), track=(28, 40, 70), accent=(56, 230, 160),
         halo=(34, 54, 94), veil=(8, 12, 26, 195), line=(52, 80, 124),
         body=(40, 204, 142), head=(22, 232, 172), tail=(96, 226, 255)),
]
T = THEMES[0]            # map đang chơi
_last_map = None
_deco_cache = {}


def build_deco(th):
    """Hoạ tiết nền riêng của từng map (vẽ 1 lần rồi giữ lại)."""
    rng = random.Random(th["seed"])
    kind, m = th["deco"], 20

    def d(s_, k):
        def X():
            return rng.uniform(m, BW - m) * k

        def Y():
            return rng.uniform(m, BW - m) * k

        if kind == "meadow":
            for _ in range(80):                                         # cọng cỏ nhỏ
                x, y = X(), Y()
                for dx in (-3, 0, 3):
                    pygame.draw.line(s_, (110, 190, 130, 95), (x + dx * k, y), (x + dx * 1.6 * k, y - 6 * k), max(1, I(1.3 * k)))
            for _ in range(28):                                         # hoa
                x, y = X(), Y()
                col = rng.choice(((255, 186, 204, 170), (255, 226, 140, 180), (255, 255, 255, 190)))
                for a in range(5):
                    ang = a * 2 * math.pi / 5
                    pygame.draw.circle(s_, col, (I(x + 3 * k * math.cos(ang)), I(y + 3 * k * math.sin(ang))), I(2.2 * k))
                pygame.draw.circle(s_, (250, 200, 60, 220), (I(x), I(y)), I(1.7 * k))
        elif kind == "desert":
            for row in range(9):                                        # đường cồn cát
                y0 = 40 + row * (BW - 80) / 8
                pts = [((m + x) * k, (y0 + 9 * math.sin(x * 0.022 + row * 1.7) + 5 * math.sin(x * 0.051 + row)) * k)
                       for x in range(0, BW - 2 * m + 1, 6)]
                pygame.draw.lines(s_, (230, 196, 146, 120), False, pts, max(1, I(2.2 * k)))
            for _ in range(34):                                         # sỏi nhỏ
                x, y = X(), Y()
                pygame.draw.ellipse(s_, (214, 174, 124, 130), (I(x), I(y), I(rng.uniform(4, 8) * k), I(3 * k)))
        else:
            for _ in range(110):                                        # sao
                x, y = X(), Y()
                a = rng.randint(60, 200)
                pygame.draw.circle(s_, (190, 215, 255, a), (I(x), I(y)), max(1, I(rng.choice((0.9, 1.2, 1.8)) * k)))
            for _ in range(9):                                          # sao lấp lánh dạng chữ thập
                x, y = X(), Y()
                for dx, dy in ((5, 0), (0, 5)):
                    pygame.draw.line(s_, (200, 230, 255, 150), (x - dx * k, y - dy * k), (x + dx * k, y + dy * k), max(1, I(k)))

    return aa(BW, BW, d, base=th["board"], ss=2)


# ====================== TRẠNG THÁI GAME ======================
best = load_best()
scene = "menu"            # menu | records | play
sel = 0
snake, direction, food = [], RIGHT, None
drl, queue, acc = 0, [], 0
state = "play"            # play | win | lose
new_rec = False
toast, toast_until = "", 0
prev_dir, removed = RIGHT, None   # hướng ở bước trước + ô đuôi vừa bị bỏ (để vẽ nội suy mượt)
food_t0 = 0                       # thời điểm mồi xuất hiện (hiệu ứng pop-in)
confirm_exit, csel = False, 1     # hộp thoại xác nhận thoát (csel: 0 = Có, 1 = Không)
slither_t = 0.0                   # đếm ngược tới lần phát tiếng rắn tiếp theo (ms)


def new_food(sn):
    while True:
        p = (random.randrange(N), random.randrange(N))
        if p not in sn:
            return p, random.choice(EVENTS)


def start_game():
    global snake, direction, food, drl, queue, acc, state, new_rec, toast, toast_until, scene
    global prev_dir, removed, food_t0, slither_t, T, _last_map
    T = random.choice([th for th in THEMES if th is not _last_map])
    _last_map = T
    if T["name"] not in _deco_cache:
        _deco_cache[T["name"]] = build_deco(T)
    snake = [(N // 2, N // 2)]
    direction = prev_dir = RIGHT
    removed = None
    food = new_food(snake)
    food_t0 = pygame.time.get_ticks()
    slither_t = 1500
    drl, queue, acc = 0, [], 0
    state, new_rec, toast, toast_until = "play", False, "", 0
    scene = "play"


def commit_record():
    global best
    if drl > best:
        best = drl
        save_best(best)
        return True
    return False


def step_snake():
    """Một bước logic của rắn (vẫn theo ô để tính ăn mồi/va chạm); hình ảnh được nội suy riêng."""
    global direction, prev_dir, removed, drl, food, food_t0, state, new_rec, toast, toast_until
    old_lv = rank_level(drl)
    prev_dir = direction
    if queue:
        direction = queue.pop(0)
    head = ((snake[0][0] + direction[0]) % N, (snake[0][1] + direction[1]) % N)  # xuyên tường
    if head in snake:                      # cắn đuôi -> hết lượt
        state = "lose"
        new_rec = commit_record()
        sfx("lose")
        return
    snake.insert(0, head)
    removed = None
    if head == food[0]:
        name, pts, _ = food[1]
        drl = min(MAX_DRL, drl + pts)
        toast, toast_until = f"{name} +{pts}", pygame.time.get_ticks() + 1200
        if drl >= MAX_DRL:
            state = "win"
            new_rec = commit_record()
            sfx("win")
        else:
            food = new_food(snake)
            food_t0 = pygame.time.get_ticks()
            new_lv = rank_level(drl)
            sfx("fan%d" % new_lv if new_lv > old_lv else "eat")
    else:
        removed = snake.pop()


def enqueue(d):
    last = queue[-1] if queue else direction
    if d != last and (d[0] + last[0], d[1] + last[1]) != (0, 0) and len(queue) < 3:
        queue.append(d)


# ====================== VẼ GIAO DIỆN ======================
def put(font, s, color, **pos):
    img = font.render(s, True, color)
    screen.blit(img, img.get_rect(**{k: sp(v) for k, v in pos.items()}))


RED, RED_D = (222, 62, 62), (190, 40, 40)


def button(rect, label, hover=False, primary=False, danger=False, dark=False):
    if danger:
        rrect(rect, RED_D if hover else RED, 14)
        fg = WHITE
    elif primary:
        rrect(rect, GREEN_D if hover else GREEN, 14, border=(120, 255, 190) if (dark and hover) else None)
        fg = WHITE
    elif dark:
        rrect(rect, (24, 62, 74) if hover else (14, 30, 42), 14,
              border=(80, 240, 170) if hover else (46, 100, 104))
        fg = WHITE
    else:
        rrect(rect, (232, 240, 252) if hover else WHITE, 14, border=LINE)
        fg = TEXT
    put(f_btn, label, fg, center=rect.center)


def logo_sprite(r):
    """Icon con rắn hình chữ S (có mắt và lưỡi), kích thước 2r x 2r."""
    def d(s, k):
        u = 2 * r * k / 100                 # vẽ trong hệ toạ độ 100x100 rồi co theo kích thước
        P = lambda x, y: (I(x * u), I(y * u))
        for i in range(121):                # thân: đường lượn sóng, nhỏ dần về phía đuôi
            t = i / 120
            x = 50 + 24 * math.sin(2 * math.pi * t)
            pygame.draw.circle(s, BODY, P(x, 24 + 66 * t), I((8.5 - 5 * t) * u))
        pygame.draw.circle(s, HEAD, P(50, 24), I(11 * u))                      # đầu
        tongue = (230, 60, 70)                                                 # lưỡi chẻ đôi
        pygame.draw.line(s, tongue, P(50, 14), P(50, 6), max(1, I(2 * u)))
        pygame.draw.line(s, tongue, P(50, 6), P(46, 2), max(1, I(1.6 * u)))
        pygame.draw.line(s, tongue, P(50, 6), P(54, 2), max(1, I(1.6 * u)))
        for ex in (45, 55):                                                    # mắt
            pygame.draw.circle(s, WHITE, P(ex, 23), I(3.6 * u))
            pygame.draw.circle(s, TEXT, P(ex, 22), I(1.7 * u))
    return sprite(("logo", r), 2 * r, 2 * r, d, base=BODY)


def snake_logo(cx, cy, r):
    spr = logo_sprite(r)
    screen.blit(spr, spr.get_rect(center=sp((cx, cy))))


# ====================== VẼ RẮN LIỀN MẠCH ======================
# Logic vẫn chạy theo ô, nhưng hình ảnh được nội suy theo thời gian (t = 0..1 trong mỗi bước):
# đầu trượt dần sang ô mới, đuôi co dần lại -> chuyển động liên tục ở 60 FPS.
# Thân rắn là MỘT ống cong liền khối (không còn các khối vuông rời nhau).
SNAKE_SS = 2                                    # siêu lấy mẫu để viền mịn
_snake_buf = None                               # dựng trong rebuild_assets() theo độ phân giải thật
TAIL_COLOR = (112, 204, 154)
BODY_R, HEAD_R = 0.40, 0.47                     # bán kính (tính theo đơn vị ô)


def snake_path(t):
    """Đường đi của rắn (toạ độ ô, đầu -> đuôi, chưa 'quấn' qua tường) tại thời điểm t của bước."""
    cells = list(snake) + ([removed] if removed else [])
    half = N / 2
    x, y = cells[0][0] + 0.5, cells[0][1] + 0.5
    pts = [(x, y)]
    for (ax, ay), (bx, by) in zip(cells, cells[1:]):
        x += (bx - ax + half) % N - half         # bước 1 ô, kể cả khi xuyên tường
        y += (by - ay + half) % N - half
        pts.append((x, y))
    if len(pts) >= 2:
        first, second, before, last = pts[0], pts[1], pts[-2], pts[-1]
        pts[0] = (second[0] + (first[0] - second[0]) * t, second[1] + (first[1] - second[1]) * t)
        if removed:                              # không ăn mồi: đuôi co dần về phía trước
            pts[-1] = (last[0] + (before[0] - last[0]) * t, last[1] + (before[1] - last[1]) * t)
    clean = [pts[0]]
    for q in pts[1:]:
        if abs(q[0] - clean[-1][0]) + abs(q[1] - clean[-1][1]) > 1e-6:
            clean.append(q)
    return clean


def chaikin(pts, iters=2):
    """Bo tròn các góc cua (giữ nguyên hai đầu mút)."""
    for _ in range(iters):
        if len(pts) < 3:
            break
        new = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            new.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            new.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        new.append(pts[-1])
        pts = new
    return pts


def resample(pts, step):
    """Lấy mẫu đều theo độ dài đường đi."""
    out, remain = [pts[0]], step
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        ux, uy, pos = dx / L, dy / L, 0.0
        while L - pos >= remain:
            pos += remain
            out.append((a[0] + ux * pos, a[1] + uy * pos))
            remain = step
        remain -= L - pos
    out.append(pts[-1])
    return out


def _offsets(x, y, r):
    """Các vị trí cần vẽ (kể cả bản sao ở mép đối diện) để rắn xuyên tường vẫn liền mạch."""
    xs, ys = [x], [y]
    if x < r:
        xs.append(x + N)
    if x > N - r:
        xs.append(x - N)
    if y < r:
        ys.append(y + N)
    if y > N - r:
        ys.append(y - N)
    return [(X, Y) for X in xs for Y in ys]


def draw_snake(t, ms):
    buf = _snake_buf
    K = buf.get_width() / N                         # pixel trên mỗi ô
    bd, tl, hd = T["body"], T["tail"], T["head"]
    buf.fill((*bd, 0))
    pts = snake_path(t)

    # --- thân: dãy hình tròn xếp sát nhau dọc theo đường cong -> ống liền mạch, đuôi thon dần
    if len(pts) >= 2:
        samples = resample(chaikin(pts), 0.1)
        n = len(samples)
        for i in range(n - 1, -1, -1):                       # vẽ từ đuôi lên đầu
            x, y = samples[i]
            to_tail = (n - 1 - i) * 0.1                      # khoảng cách tới chóp đuôi (ô)
            k = min(1.0, to_tail / 5.0)
            r = BODY_R * (0.45 + 0.55 * k * k * (3 - 2 * k))
            u = i / (n - 1)
            col = tuple(I(bd[c] + (tl[c] - bd[c]) * u * 0.8) for c in range(3))
            for X, Y in _offsets(x % N, y % N, r):
                pygame.draw.circle(buf, col, (I(X * K), I(Y * K)), max(1, I(r * K)))

    # --- đầu: hướng quay nội suy mượt khi rẽ
    e = min(1.0, t * 1.6)
    e = e * e * (3 - 2 * e)
    hx = prev_dir[0] * (1 - e) + direction[0] * e
    hy = prev_dir[1] * (1 - e) + direction[1] * e
    hl = math.hypot(hx, hy) or 1.0
    hx, hy = hx / hl, hy / hl
    sx, sy = -hy, hx
    cx, cy = pts[0][0] % N, pts[0][1] % N
    tongue = 0.55 * max(0.0, math.sin(ms / 230.0)) ** 3      # lưỡi thè ra thụt vào

    def P(X, Y, f, s):
        return (I((X + hx * f + sx * s) * K), I((Y + hy * f + sy * s) * K))

    for X, Y in _offsets(cx, cy, 1.2):
        if tongue > 0.05:
            red, w = (230, 60, 70), max(1, I(0.07 * K))
            tip = HEAD_R * 0.8 + tongue
            pygame.draw.line(buf, red, P(X, Y, HEAD_R * 0.7, 0), P(X, Y, tip, 0), w)
            pygame.draw.line(buf, red, P(X, Y, tip, 0), P(X, Y, tip + 0.16, 0.12), w)
            pygame.draw.line(buf, red, P(X, Y, tip, 0), P(X, Y, tip + 0.16, -0.12), w)
        pygame.draw.circle(buf, hd, (I(X * K), I(Y * K)), I(HEAD_R * K))
        for sg in (1, -1):
            pygame.draw.circle(buf, WHITE, P(X, Y, 0.16, sg * 0.24), max(1, I(0.15 * K)))
            pygame.draw.circle(buf, TEXT, P(X, Y, 0.21, sg * 0.24), max(1, I(0.075 * K)))

    ow = I(BW * S)
    img = buf if buf.get_width() == ow else pygame.transform.smoothscale(buf, (ow, ow))
    screen.blit(img, sp((BX, BY)))


def arrow(d, c):
    pts = {
        UP: [(10, 3), (2, 16), (18, 16)],
        DOWN: [(10, 17), (2, 4), (18, 4)],
        LEFT: [(3, 10), (16, 2), (16, 18)],
        RIGHT: [(17, 10), (4, 2), (4, 18)],
    }[d]

    def dr(s, k):
        pygame.draw.polygon(s, T["text"], [(x * k, y * k) for x, y in pts])
    spr = sprite(("arrow", d, T["text"]), 20, 20, dr, base=T["text"])
    screen.blit(spr, spr.get_rect(center=sp(c)))


# ====================== NỀN 2D ĐỘNG CHO MENU ======================
# Nền tối kiểu "neon": gradient + hoạ tiết vảy rắn, vài con rắn phát sáng bò ngang màn hình,
# đom đóm lấp lánh, icon sự kiện trôi lơ lửng và viền tối (vignette). Mọi thứ tự vẽ bằng code.
LIGHT = (170, 196, 206)


def glow_sprite(r, col, core=0.8, power=1.6):
    """Quầng sáng tròn (nền đen) để vẽ cộng sáng (BLEND_RGB_ADD) -> hiệu ứng neon."""
    d = 2 * r
    spr = pygame.Surface((d, d))
    spr.fill((0, 0, 0))
    for y in range(d):
        for x in range(d):
            dd = math.hypot(x - r + 0.5, y - r + 0.5) / r
            if dd < 1:
                k = (1 - dd) ** power
                c = max(0.0, 1 - dd / 0.4) ** 2 * core * 255
                spr.set_at((x, y), (min(255, I(col[0] * k + c)),
                                    min(255, I(col[1] * k + c)),
                                    min(255, I(col[2] * k + c))))
    return spr


def _lerp3(a, b, k):
    return tuple(I(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _scales(s, k):
    R = 28 * k
    col = (70, 200, 170, 34)
    row, y = 0, 0
    while y < H * k + R:
        x = -R + (R if row % 2 else 0)
        while x < W * k + 2 * R:
            pygame.draw.circle(s, col, (I(x), I(y)), I(R), max(1, I(k)))
            x += 2 * R
        y += R
        row += 1


def build_bg():
    surf = pygame.Surface((WS, HS))
    top, mid, bot = (6, 12, 26), (8, 34, 48), (4, 18, 26)
    for y in range(HS):
        u = y / max(1, HS - 1)
        c = _lerp3(top, mid, u / 0.6) if u < 0.6 else _lerp3(mid, bot, (u - 0.6) / 0.4)
        pygame.draw.line(surf, c, (0, y), (WS, y))
    surf.blit(aa(W, H, _scales, base=(70, 200, 170), ss=2), (0, 0))      # hoạ tiết vảy
    return surf


def build_vignette():
    vw = 48
    vh = max(2, I(vw * H / W))
    v = pygame.Surface((vw, vh), pygame.SRCALPHA)
    for y in range(vh):
        for x in range(vw):
            dx, dy = (x + 0.5) / vw * 2 - 1, (y + 0.5) / vh * 2 - 1
            k = max(0.0, min(1.0, (math.hypot(dx, dy) / 1.414 - 0.45) / 0.55))
            v.set_at((x, y), (0, 0, 0, I(190 * k * k * (3 - 2 * k))))
    return pygame.transform.smoothscale(v, (WS, HS))


def make_icon_big(fn, size):
    size = I(size * S)
    big = size * 4
    s_ = pygame.Surface((big, big), pygame.SRCALPHA)
    s_.fill((255, 255, 255, 0))
    fn(s_, big / 28)
    return pygame.transform.smoothscale(s_, (size, size))


_LOGO_GLOW0 = glow_sprite(130, (24, 120, 86), core=0.0, power=1.4)      # bản gốc kích thước thiết kế

# --- rắn neon
NEON_SNAKES = [
    dict(col=(40, 255, 150), base=0.88, amp=44, freq=0.011, ph=0.0, speed=95, n=62, sp=7, dir=1),
    dict(col=(60, 200, 255), base=0.07, amp=30, freq=0.014, ph=2.0, speed=70, n=48, sp=7, dir=-1),
    dict(col=(160, 100, 255), base=0.58, amp=60, freq=0.008, ph=4.0, speed=55, n=56, sp=7, dir=1),
]
for _sn in NEON_SNAKES:
    _c = tuple(I(v * (0.55 if _sn["dir"] == 1 and _sn["base"] == 0.58 else 0.8)) for v in _sn["col"])
    _sn["head"] = glow_sprite(24, _c, core=1.0)
    _sn["body"] = [glow_sprite(r, _c, core=0.55) for r in (18, 16, 14, 12, 10, 8)]

# --- đom đóm
_rng = random.Random(7)
_FLY_COLS = [(60, 255, 170), (80, 210, 255), (255, 230, 120)]
_FLY_SPR0 = [[glow_sprite(8, tuple(I(v * f) for v in c), core=0.6) for f in (0.35, 0.65, 1.0)] for c in _FLY_COLS]
FIREFLIES = [dict(x=_rng.uniform(0, W), y=_rng.uniform(0, H), vx=_rng.uniform(-6, 6), vy=_rng.uniform(-24, -6),
                  ph=_rng.uniform(0, 6.28), sp=_rng.uniform(0.8, 2.4), c=_rng.randrange(3)) for _ in range(46)]

# --- icon sự kiện trôi lơ lửng
_ICON_FNS = (icon_broom, icon_blood_club, icon_book, icon_ball, icon_music, icon_heart, icon_star)
BG_ICONS = [dict(img=make_icon_big(f, 56), x0=(i + 0.5) * W / len(_ICON_FNS) + _rng.uniform(-20, 20),
                 y0=_rng.uniform(0, H + 120), vy=-_rng.uniform(14, 26), rs=_rng.uniform(-14, 14),
                 ph=_rng.uniform(0, 6.28)) for i, f in enumerate(_ICON_FNS)]


def draw_neon(sn, t):
    n, sp = sn["n"], sn["sp"]
    L = W + n * sp + 120
    hx = (t * sn["speed"]) % L - 60                      # vị trí đầu theo toạ độ "ảo"
    last = None
    for k in range(n - 1, -1, -1):                       # từ đuôi lên đầu
        xv = hx - k * sp
        x = xv if sn["dir"] == 1 else W - xv
        if x < -30 or x > W + 30:
            continue
        y = (H * sn["base"] + sn["amp"] * math.sin(xv * sn["freq"] + sn["ph"])
             + sn["amp"] * 0.4 * math.sin(xv * sn["freq"] * 2.3 + sn["ph"] * 2)
             + 5 * math.sin(t * 3 - k * 0.25))
        spr = sn["head_s"] if k == 0 else sn["body_s"][min(5, k * 6 // n)]
        r = spr.get_width() // 2
        screen.blit(spr, (I(x * S) - r, I(y * S) - r), special_flags=pygame.BLEND_RGB_ADD)
        if k == 0:
            last = (x, y)
    if last:                                             # mắt rắn
        x, y = last
        for sg in (-1, 1):
            pygame.draw.circle(screen, WHITE, sp((x + 7 * sn["dir"], y + sg * 6)), max(1, I(2 * S)))


def draw_bg(ms):
    t = ms / 1000.0
    screen.blit(_bg_static, (0, 0))
    screen.blit(_logo_glow, sp((W // 2 - 130, 120 - 130)), special_flags=pygame.BLEND_RGB_ADD)

    for ic in BG_ICONS:                                  # icon trôi lơ lửng, xoay chậm, mờ
        y = (ic["y0"] + ic["vy"] * t) % (H + 120) - 60
        x = ic["x0"] + 26 * math.sin(t * 0.45 + ic["ph"])
        img = pygame.transform.rotozoom(ic["img"], (t * ic["rs"] + ic["ph"] * 40) % 360, 1.0)
        img.set_alpha(70)
        screen.blit(img, img.get_rect(center=sp((x, y))))

    for sn in NEON_SNAKES:
        draw_neon(sn, t)

    for f in FIREFLIES:                                  # đom đóm lấp lánh
        x = (f["x"] + f["vx"] * t + 8 * math.sin(t * 0.7 + f["ph"])) % W
        y = (f["y"] + f["vy"] * t) % H
        lvl = int((0.5 + 0.5 * math.sin(t * f["sp"] + f["ph"])) * 2.99)
        spr = _FLY_SPR[f["c"]][lvl]
        r = spr.get_width() // 2
        screen.blit(spr, (I(x * S) - r, I(y * S) - r), special_flags=pygame.BLEND_RGB_ADD)

    screen.blit(_vignette, (0, 0))


# --- Menu ---
MENU_ITEMS = ["Chơi game", "Kỷ lục", "Thoát game"]
MENU_RECTS = [pygame.Rect((W - 260) // 2, 300 + i * 72, 260, 54) for i in range(3)]
BACK_RECT = pygame.Rect((W - 200) // 2, 520, 200, 54)
DLG = pygame.Rect(0, 0, 360, 200)
DLG.center = (W // 2, 360)
DLG_YES = pygame.Rect(DLG.x + 24, DLG.bottom - 72, 150, 48)
DLG_NO = pygame.Rect(DLG.right - 174, DLG.bottom - 72, 150, 48)


def draw_confirm():
    screen.blit(_dim, (0, 0))
    rrect(DLG, WHITE, 20, border=LINE)
    put(f_head, "Thoát game?", TEXT, center=(DLG.centerx, DLG.y + 40))
    put(f_txt, "Bạn có chắc muốn thoát game không?", GRAY, center=(DLG.centerx, DLG.y + 82))
    button(DLG_YES, "Có", hover=(csel == 0), danger=True)
    button(DLG_NO, "Không", hover=(csel == 1), primary=True)


def draw_menu():
    draw_bg(pygame.time.get_ticks())
    snake_logo(W // 2, 120, 38)
    put(f_logo, "Rắn Săn Điểm Rèn Luyện", (20, 140, 95), center=(W // 2, 205))     # bóng neon
    put(f_logo, "Rắn Săn Điểm Rèn Luyện", WHITE, center=(W // 2, 202))
    put(f_txt, "Ăn sự kiện, CLB để đạt 100 điểm rèn luyện", LIGHT, center=(W // 2, 240))
    for i, (r, label) in enumerate(zip(MENU_RECTS, MENU_ITEMS)):
        button(r, label, hover=(i == sel), primary=(i == 0), dark=True)
    put(f_lbl, "N: bật/tắt âm thanh" + ("  (đang tắt)" if muted else "") + "   ·   F11: toàn màn hình", LIGHT, center=(W // 2, H - 62))
    put(f_lbl, "Tạo bởi Cao Thiên Phú và Nguyễn Phát Tài", LIGHT, center=(W // 2, H - 36))
    if confirm_exit:
        draw_confirm()


# --- Kỷ lục ---
def draw_records():
    draw_bg(pygame.time.get_ticks())
    put(f_logo, "Kỷ lục", WHITE, center=(W // 2, 120))
    card = pygame.Rect(60, 180, W - 120, 280)
    rrect(card, WHITE, 20)
    put(f_lbl, "Điểm rèn luyện cao nhất", GRAY, center=(card.centerx, card.y + 50))
    put(f_huge, str(best), TEXT, center=(card.centerx, card.y + 120))
    put(f_lbl, f"trên thang {MAX_DRL}", GRAY, center=(card.centerx, card.y + 172))
    put(f_head, f"Xếp loại: {rank(best)}", GREEN_D, center=(card.centerx, card.y + 225))
    button(BACK_RECT, "Quay lại", hover=BACK_RECT.collidepoint(mouse_pos()), primary=True)


# --- Màn chơi ---
DPAD = {
    UP: pygame.Rect(W // 2 - 23, DP_Y, 46, 40),
    LEFT: pygame.Rect(W // 2 - 75, DP_Y + 44, 46, 40),
    DOWN: pygame.Rect(W // 2 - 23, DP_Y + 44, 46, 40),
    RIGHT: pygame.Rect(W // 2 + 29, DP_Y + 44, 46, 40),
}
OVER = pygame.Rect(0, 0, 320, 210)
OVER.center = (W // 2, BY + BW // 2)
OVER_RETRY = pygame.Rect(OVER.x + 16, OVER.bottom - 62, 138, 44)
OVER_MENU = pygame.Rect(OVER.right - 154, OVER.bottom - 62, 138, 44)


def draw_play():
    screen.fill(T["bg"])

    # tiêu đề + mô tả
    title = f_title.render("Rắn Săn Điểm Rèn Luyện", True, T["text"])
    x0 = I((W - (title.get_width() / S + 38)) / 2)
    snake_logo(x0 + 14, 30, 14)
    screen.blit(title, (I((x0 + 38) * S), I(30 * S) - title.get_height() // 2))
    put(f_lbl, "Ăn hoạt động để đạt 100 điểm. Đi qua khung sẽ xuất hiện", T["sub"], center=(W // 2, 62))
    put(f_lbl, "ở phía đối diện, nhưng cắn đuôi là hết lượt!", T["sub"], center=(W // 2, 80))

    # 3 thẻ thống kê
    cw = (BW - 16) // 3
    for i, (val, font, label) in enumerate(((str(drl), f_num, "Điểm rèn luyện"),
                                            (rank(drl), f_rank, "Xếp loại"),
                                            (str(max(best, drl)), f_num, "Kỷ lục"))):
        r = pygame.Rect(BX + i * (cw + 8), 94, cw, 62)
        rrect(r, T["card"], 16)
        put(font, val, T["text"], center=(r.centerx, r.y + 24))
        put(f_lbl, label, T["sub"], center=(r.centerx, r.y + 49))

    # thanh tiến độ
    rrect(pygame.Rect(BX, 166, BW, 12), T["track"], 6)
    fill = BW * drl // MAX_DRL
    if fill > 0:
        rrect(pygame.Rect(BX, 166, max(fill, 12), 12), T["accent"], 6)

    # bảng chơi (phẳng, không lưới ô) + hoạ tiết riêng của map
    rrect(pygame.Rect(BX, BY, BW, BW), T["board"], 16, border=T["border"], bw=2)
    screen.blit(_deco_cache[T["name"]], sp((BX, BY)))
    ms = pygame.time.get_ticks()

    # icon sự kiện: hiện ra mượt (pop-in) rồi nhấp nhô nhẹ
    (fx, fy), ev = food
    c = (BX + fx * CELL + CELL // 2, BY + fy * CELL + CELL // 2)
    p = min(1.0, (ms - food_t0) / 240)
    scale = (0.25 + 0.75 * (1 - (1 - p) ** 3)) * (1 + 0.05 * math.sin(ms / 260))
    halo = sprite(("halo", CELL, T["halo"]), CELL * 2, CELL * 2,
                  lambda s_, k: pygame.draw.circle(s_, T["halo"], (I(CELL * k), I(CELL * k)), I(CELL * 0.62 * k)),
                  base=T["halo"])
    cn = sp(c)
    hs = max(2, I(halo.get_width() * scale))
    screen.blit(pygame.transform.smoothscale(halo, (hs, hs)), (cn[0] - hs // 2, cn[1] - hs // 2))
    icon = ICON_BY_NAME[ev[0]]
    isz = max(2, I(icon.get_width() * scale))
    icon = pygame.transform.smoothscale(icon, (isz, isz))
    screen.blit(icon, icon.get_rect(center=cn))

    # rắn (liền mạch). Khi kết thúc ván thì đứng yên ở vị trí cuối.
    t = min(1.0, acc / STEP_MS) if (scene == "play" and state == "play") else 1.0
    draw_snake(t, ms)

    # thông báo vừa ăn sự kiện
    if toast and pygame.time.get_ticks() < toast_until:
        img = f_lbl.render(toast, True, T["bg"])
        pill = pygame.Rect(0, 0, I(img.get_width() / S) + 24, I(img.get_height() / S) + 12)
        pill.center = (BX + BW // 2, BY + 22)
        rrect(pill, T["text"], 14)
        screen.blit(img, img.get_rect(center=sp(pill.center)))

    # nút điều hướng
    for d, r in DPAD.items():
        rrect(r, T["card"], 12, border=T["border"], bw=1)
        arrow(d, r.center)
    put(f_lbl, "Map: " + T["name"], T["sub"], midleft=(BX, DP_Y + 40))

    # bảng kết thúc
    if state != "play":
        rrect(pygame.Rect(BX, BY, BW, BW), T["veil"], 16)
        rrect(OVER, T["card"], 18, border=T["line"])
        put(f_head, "Hoàn thành 100 điểm!" if state == "win" else "Hết lượt!", T["text"],
            center=(OVER.centerx, OVER.y + 36))
        put(f_txt, f"Điểm rèn luyện: {drl}  ·  Xếp loại: {rank(drl)}", T["sub"],
            center=(OVER.centerx, OVER.y + 72))
        if new_rec:
            put(f_btn, "Kỷ lục mới!", (230, 140, 30), center=(OVER.centerx, OVER.y + 104))
        mp = mouse_pos()
        button(OVER_RETRY, "Chơi lại", OVER_RETRY.collidepoint(mp), primary=True)
        button(OVER_MENU, "Về menu", OVER_MENU.collidepoint(mp), dark=T["dark"])


def gscale(spr):
    """Phóng quầng sáng mềm lên độ phân giải thật (quầng sáng mờ nên phóng không bị mất nét)."""
    if S == 1.0:
        return spr
    return pygame.transform.smoothscale(spr, (max(1, I(spr.get_width() * S)), max(1, I(spr.get_height() * S))))


def rebuild_assets():
    global f_title, f_logo, f_num, f_rank, f_btn, f_head, f_txt, f_lbl, f_huge
    global ICON_BY_NAME, _bg_static, _vignette, _logo_glow, _FLY_SPR, _dim, _snake_buf
    _cache.clear()
    _deco_cache.clear()
    f_title, f_logo, f_num, f_rank = F(28, True), F(32, True), F(30, True), F(21, True)
    f_btn, f_head, f_txt, f_lbl, f_huge = F(20, True), F(24, True), F(15), F(14), F(72, True)
    ICON_BY_NAME = {name: make_icon(fn) for name, fn in _EVENT_FNS.items()}
    _bg_static, _vignette = build_bg(), build_vignette()
    _logo_glow = gscale(_LOGO_GLOW0)
    for sn in NEON_SNAKES:
        sn["head_s"] = gscale(sn["head"])
        sn["body_s"] = [gscale(b) for b in sn["body"]]
    _FLY_SPR = [[gscale(g) for g in row] for row in _FLY_SPR0]
    for ic, fn in zip(BG_ICONS, _ICON_FNS):
        ic["img"] = make_icon_big(fn, 56)
    _dim = pygame.Surface((WS, HS), pygame.SRCALPHA)
    _dim.fill((20, 24, 35, 140))
    ow = I(BW * S)                                    # buffer vẽ rắn: siêu lấy mẫu vừa đủ (nhẹ hơn ở màn hình lớn)
    ss = 2.0 if ow <= 1000 else 1.5 if ow <= 1500 else 1.25
    _snake_buf = pygame.Surface((I(ow * ss), I(ow * ss)), pygame.SRCALPHA)


apply_scale()                                      # dựng toàn bộ hình ảnh lần đầu (S = 1)
pygame.display.set_icon(logo_sprite(16))     # icon con rắn trên thanh tiêu đề cửa sổ

# ====================== VÒNG LẶP CHÍNH ======================
running = True
_last = time.perf_counter()
while running:
    _now = time.perf_counter()
    dt = (_now - _last) * 1000                 # thời gian thực của khung hình trước (ms)
    _last = _now
    for e in pygame.event.get():
        if hasattr(e, "pos"):
            e.pos = to_canvas(e.pos)                            # toạ độ chuột -> toạ độ canvas
        if e.type == pygame.QUIT:
            running = False

        elif e.type == pygame.KEYDOWN and e.key == pygame.K_n:
            muted = not muted                                   # bật/tắt âm thanh

        elif e.type == pygame.KEYDOWN and (e.key == pygame.K_F11 or
                                           (e.key == pygame.K_RETURN and e.mod & pygame.KMOD_ALT)):
            set_fullscreen(not fullscreen)                      # F11 / Alt+Enter: bật/tắt toàn màn hình

        # ---------- MENU ----------
        elif scene == "menu":
            if confirm_exit:                                    # hộp thoại "Thoát game?"
                if e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d, pygame.K_TAB):
                        csel = 1 - csel
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        if csel == 0:
                            running = False
                        else:
                            confirm_exit = False
                    elif e.key == pygame.K_ESCAPE:
                        confirm_exit = False
                elif e.type == pygame.MOUSEMOTION:
                    if DLG_YES.collidepoint(e.pos):
                        csel = 0
                    elif DLG_NO.collidepoint(e.pos):
                        csel = 1
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if DLG_YES.collidepoint(e.pos):
                        running = False
                    elif DLG_NO.collidepoint(e.pos):
                        confirm_exit = False
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % 3
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % 3
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if sel == 0:
                        start_game()
                    elif sel == 1:
                        scene = "records"
                    else:
                        confirm_exit, csel = True, 1
            elif e.type == pygame.MOUSEMOTION:
                for i, r in enumerate(MENU_RECTS):
                    if r.collidepoint(e.pos):
                        sel = i
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, r in enumerate(MENU_RECTS):
                    if r.collidepoint(e.pos):
                        if i == 0:
                            start_game()
                        elif i == 1:
                            scene = "records"
                        else:
                            confirm_exit, csel = True, 1

        # ---------- KỶ LỤC ----------
        elif scene == "records":
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN,
                                                      pygame.K_SPACE, pygame.K_BACKSPACE):
                scene = "menu"
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and BACK_RECT.collidepoint(e.pos):
                scene = "menu"

        # ---------- ĐANG CHƠI ----------
        elif scene == "play":
            if e.type == pygame.KEYDOWN:
                if state == "play":
                    if e.key == pygame.K_ESCAPE:
                        commit_record()
                        scene = "menu"
                    elif e.key in KEYS:
                        enqueue(KEYS[e.key])
                else:
                    if e.key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
                        start_game()
                    elif e.key in (pygame.K_ESCAPE, pygame.K_m):
                        scene = "menu"
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if state == "play":
                    for d, r in DPAD.items():
                        if r.collidepoint(e.pos):
                            enqueue(d)
                elif OVER_RETRY.collidepoint(e.pos):
                    start_game()
                elif OVER_MENU.collidepoint(e.pos):
                    scene = "menu"

    # ---------- NHẠC NỀN (chỉ ở menu / kỷ lục) ----------
    if AUDIO:
        want_music = scene in ("menu", "records")
        if want_music and not music_playing and "music" in SOUNDS:
            music_ch.play(SOUNDS["music"], loops=-1, fade_ms=800)
            music_playing = True
        elif not want_music and music_playing:
            music_ch.fadeout(500)
            music_playing = False
        music_ch.set_volume(0.0 if muted else 0.45)

    # ---------- CẬP NHẬT ----------
    if scene == "play" and state == "play":
        acc += min(dt, 100)                    # chặn dt quá lớn (kéo cửa sổ, lag...)
        while acc >= STEP_MS and state == "play":
            acc -= STEP_MS
            step_snake()
        slither_t -= dt                        # cứ vài giây rắn lại rít/bò một tiếng
        if slither_t <= 0 and state == "play":
            sfx("slither%d" % random.randint(0, 1))
            slither_t = random.uniform(2500, 4000)

    # ---------- VẼ ----------
    if scene == "menu":
        draw_menu()
    elif scene == "records":
        draw_records()
    else:
        draw_play()

    present()
    clock.tick(FPS)

pygame.quit()
