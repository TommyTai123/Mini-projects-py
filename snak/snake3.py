import json
import math
import os
import random
import time

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

screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Rắn Săn Điểm Rèn Luyện")
clock = pygame.time.Clock()

FONT_NAMES = ["segoeui", "arial", "tahoma", "dejavusans"]   # font có hỗ trợ tiếng Việt


def F(size, bold=False):
    return pygame.font.SysFont(FONT_NAMES, size, bold=bold)


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
    s = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
    s.fill((*base[:3], 0))                  # tránh viền đen khi thu nhỏ
    draw(s, ss)
    return pygame.transform.smoothscale(s, (w, h))


def rrect(rect, color, radius, border=None, bw=2):
    if rect.w <= 0 or rect.h <= 0:
        return
    key = ("rr", rect.w, rect.h, color, radius, border, bw)
    spr = _cache.get(key)
    if spr is None:
        def d(s, k):
            box = (0, 0, rect.w * k, rect.h * k)
            pygame.draw.rect(s, color, box, border_radius=radius * k)
            if border:
                pygame.draw.rect(s, border, box, bw * k, border_radius=radius * k)
        spr = aa(rect.w, rect.h, d, base=color, ss=4 if rect.w * rect.h < 120000 else 2)
        _cache[key] = spr
    screen.blit(spr, rect.topleft)


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
    size = CELL + 2
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


def new_food(sn):
    while True:
        p = (random.randrange(N), random.randrange(N))
        if p not in sn:
            return p, random.choice(EVENTS)


def start_game():
    global snake, direction, food, drl, queue, acc, state, new_rec, toast, toast_until, scene
    global prev_dir, removed, food_t0
    snake = [(N // 2, N // 2)]
    direction = prev_dir = RIGHT
    removed = None
    food = new_food(snake)
    food_t0 = pygame.time.get_ticks()
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
    prev_dir = direction
    if queue:
        direction = queue.pop(0)
    head = ((snake[0][0] + direction[0]) % N, (snake[0][1] + direction[1]) % N)  # xuyên tường
    if head in snake:                      # cắn đuôi -> hết lượt
        state = "lose"
        new_rec = commit_record()
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
        else:
            food = new_food(snake)
            food_t0 = pygame.time.get_ticks()
    else:
        removed = snake.pop()


def enqueue(d):
    last = queue[-1] if queue else direction
    if d != last and (d[0] + last[0], d[1] + last[1]) != (0, 0) and len(queue) < 3:
        queue.append(d)


# ====================== VẼ GIAO DIỆN ======================
def put(font, s, color, **pos):
    img = font.render(s, True, color)
    screen.blit(img, img.get_rect(**pos))


def button(rect, label, hover=False, primary=False):
    if primary:
        rrect(rect, GREEN_D if hover else GREEN, 14)
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
    screen.blit(spr, spr.get_rect(center=(cx, cy)))


# ====================== VẼ RẮN LIỀN MẠCH ======================
# Logic vẫn chạy theo ô, nhưng hình ảnh được nội suy theo thời gian (t = 0..1 trong mỗi bước):
# đầu trượt dần sang ô mới, đuôi co dần lại -> chuyển động liên tục ở 60 FPS.
# Thân rắn là MỘT ống cong liền khối (không còn các khối vuông rời nhau).
SNAKE_SS = 2                                    # siêu lấy mẫu để viền mịn
_snake_buf = pygame.Surface((BW * SNAKE_SS, BW * SNAKE_SS), pygame.SRCALPHA)
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
    buf, K = _snake_buf, CELL * SNAKE_SS
    buf.fill((*BODY, 0))
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
            col = tuple(I(BODY[c] + (TAIL_COLOR[c] - BODY[c]) * u * 0.8) for c in range(3))
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
        pygame.draw.circle(buf, HEAD, (I(X * K), I(Y * K)), I(HEAD_R * K))
        for sg in (1, -1):
            pygame.draw.circle(buf, WHITE, P(X, Y, 0.16, sg * 0.24), max(1, I(0.15 * K)))
            pygame.draw.circle(buf, TEXT, P(X, Y, 0.21, sg * 0.24), max(1, I(0.075 * K)))

    screen.blit(pygame.transform.smoothscale(buf, (BW, BW)), (BX, BY))


def arrow(d, c):
    pts = {
        UP: [(10, 3), (2, 16), (18, 16)],
        DOWN: [(10, 17), (2, 4), (18, 4)],
        LEFT: [(3, 10), (16, 2), (16, 18)],
        RIGHT: [(17, 10), (4, 2), (4, 18)],
    }[d]

    def dr(s, k):
        pygame.draw.polygon(s, TEXT, [(x * k, y * k) for x, y in pts])
    spr = sprite(("arrow", d), 20, 20, dr, base=TEXT)
    screen.blit(spr, spr.get_rect(center=c))


# --- Menu ---
MENU_ITEMS = ["Chơi game", "Kỷ lục", "Thoát game"]
MENU_RECTS = [pygame.Rect((W - 260) // 2, 300 + i * 72, 260, 54) for i in range(3)]
BACK_RECT = pygame.Rect((W - 200) // 2, 520, 200, 54)


def draw_menu():
    screen.fill(BG)
    snake_logo(W // 2, 120, 38)
    put(f_logo, "Rắn Săn Điểm Rèn Luyện", TEXT, center=(W // 2, 202))
    put(f_txt, "Ăn sự kiện, CLB để đạt 100 điểm rèn luyện", GRAY, center=(W // 2, 240))
    for i, (r, label) in enumerate(zip(MENU_RECTS, MENU_ITEMS)):
        button(r, label, hover=(i == sel), primary=(i == 0))
    put(f_lbl, "Tạo bởi Cao Thiên Phú và Nguyễn Phát Tài", GRAY, center=(W // 2, H - 36))


# --- Kỷ lục ---
def draw_records():
    screen.fill(BG)
    put(f_logo, "Kỷ lục", TEXT, center=(W // 2, 120))
    card = pygame.Rect(60, 180, W - 120, 280)
    rrect(card, WHITE, 20)
    put(f_lbl, "Điểm rèn luyện cao nhất", GRAY, center=(card.centerx, card.y + 50))
    put(f_huge, str(best), TEXT, center=(card.centerx, card.y + 120))
    put(f_lbl, f"trên thang {MAX_DRL}", GRAY, center=(card.centerx, card.y + 172))
    put(f_head, f"Xếp loại: {rank(best)}", GREEN_D, center=(card.centerx, card.y + 225))
    button(BACK_RECT, "Quay lại", hover=BACK_RECT.collidepoint(pygame.mouse.get_pos()), primary=True)


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
    screen.fill(BG)

    # tiêu đề + mô tả
    title = f_title.render("Rắn Săn Điểm Rèn Luyện", True, TEXT)
    x0 = (W - (title.get_width() + 38)) // 2
    snake_logo(x0 + 14, 30, 14)
    screen.blit(title, (x0 + 38, 30 - title.get_height() // 2))
    put(f_lbl, "Ăn hoạt động để đạt 100 điểm. Đi qua khung sẽ xuất hiện", GRAY, center=(W // 2, 62))
    put(f_lbl, "ở phía đối diện, nhưng cắn đuôi là hết lượt!", GRAY, center=(W // 2, 80))

    # 3 thẻ thống kê
    cw = (BW - 16) // 3
    for i, (val, font, label) in enumerate(((str(drl), f_num, "Điểm rèn luyện"),
                                            (rank(drl), f_rank, "Xếp loại"),
                                            (str(max(best, drl)), f_num, "Kỷ lục"))):
        r = pygame.Rect(BX + i * (cw + 8), 94, cw, 62)
        rrect(r, WHITE, 16)
        put(font, val, TEXT, center=(r.centerx, r.y + 24))
        put(f_lbl, label, GRAY, center=(r.centerx, r.y + 49))

    # thanh tiến độ
    rrect(pygame.Rect(BX, 166, BW, 12), TRACK, 6)
    fill = BW * drl // MAX_DRL
    if fill > 0:
        rrect(pygame.Rect(BX, 166, max(fill, 12), 12), GREEN, 6)

    # bảng chơi (phẳng, không còn lưới ô)
    rrect(pygame.Rect(BX, BY, BW, BW), BOARD, 16)
    ms = pygame.time.get_ticks()

    # icon sự kiện: hiện ra mượt (pop-in) rồi nhấp nhô nhẹ
    (fx, fy), ev = food
    c = (BX + fx * CELL + CELL // 2, BY + fy * CELL + CELL // 2)
    p = min(1.0, (ms - food_t0) / 240)
    scale = (0.25 + 0.75 * (1 - (1 - p) ** 3)) * (1 + 0.05 * math.sin(ms / 260))
    halo = sprite(("halo", CELL), CELL * 2, CELL * 2,
                  lambda s_, k: pygame.draw.circle(s_, (232, 238, 250), (CELL * k, CELL * k), I(CELL * 0.62 * k)),
                  base=(232, 238, 250))
    hs = max(2, I(CELL * 2 * scale))
    screen.blit(pygame.transform.smoothscale(halo, (hs, hs)), (c[0] - hs // 2, c[1] - hs // 2))
    icon = ev[2]
    isz = max(2, I(icon.get_width() * scale))
    icon = pygame.transform.smoothscale(icon, (isz, isz))
    screen.blit(icon, icon.get_rect(center=c))

    # rắn (liền mạch). Khi kết thúc ván thì đứng yên ở vị trí cuối.
    t = min(1.0, acc / STEP_MS) if (scene == "play" and state == "play") else 1.0
    draw_snake(t, ms)

    # thông báo vừa ăn sự kiện
    if toast and pygame.time.get_ticks() < toast_until:
        img = f_lbl.render(toast, True, WHITE)
        pill = img.get_rect(center=(BX + BW // 2, BY + 22)).inflate(24, 12)
        rrect(pill, TEXT, 14)
        screen.blit(img, img.get_rect(center=pill.center))

    # nút điều hướng
    for d, r in DPAD.items():
        rrect(r, WHITE, 12)
        arrow(d, r.center)

    # bảng kết thúc
    if state != "play":
        rrect(pygame.Rect(BX, BY, BW, BW), (255, 255, 255, 190), 16)
        rrect(OVER, WHITE, 18, border=LINE)
        put(f_head, "Hoàn thành 100 điểm!" if state == "win" else "Hết lượt!", TEXT,
            center=(OVER.centerx, OVER.y + 36))
        put(f_txt, f"Điểm rèn luyện: {drl}  ·  Xếp loại: {rank(drl)}", GRAY,
            center=(OVER.centerx, OVER.y + 72))
        if new_rec:
            put(f_btn, "Kỷ lục mới!", (230, 140, 30), center=(OVER.centerx, OVER.y + 104))
        mp = pygame.mouse.get_pos()
        button(OVER_RETRY, "Chơi lại", OVER_RETRY.collidepoint(mp), primary=True)
        button(OVER_MENU, "Về menu", OVER_MENU.collidepoint(mp))


pygame.display.set_icon(logo_sprite(16))     # icon con rắn trên thanh tiêu đề cửa sổ

# ====================== VÒNG LẶP CHÍNH ======================
running = True
_last = time.perf_counter()
while running:
    _now = time.perf_counter()
    dt = (_now - _last) * 1000                 # thời gian thực của khung hình trước (ms)
    _last = _now
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        # ---------- MENU ----------
        elif scene == "menu":
            if e.type == pygame.KEYDOWN:
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
                        running = False
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
                            running = False

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

    # ---------- CẬP NHẬT ----------
    if scene == "play" and state == "play":
        acc += min(dt, 100)                    # chặn dt quá lớn (kéo cửa sổ, lag...)
        while acc >= STEP_MS and state == "play":
            acc -= STEP_MS
            step_snake()

    # ---------- VẼ ----------
    if scene == "menu":
        draw_menu()
    elif scene == "records":
        draw_records()
    else:
        draw_play()

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
