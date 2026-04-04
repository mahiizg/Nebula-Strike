import math
import os
import random
import enum
import time

import pygame
from pygame import mixer

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(_SCRIPT_DIR, "fonts", "PressStart2P-Regular.ttf")

# ── Colour palette ──────────────────────────────────────────────────────────
UI_BG           = (8,   6,  24)
UI_PANEL        = (18,  14, 42)
UI_ACCENT       = (160, 80, 255)   # electric violet
UI_ACCENT2      = (80, 200, 255)   # cyan-blue
UI_ACCENT_DIM   = (80,  40, 140)
UI_TEXT         = (240, 230, 255)
UI_TEXT_MUTED   = (130, 110, 180)
UI_GLOW         = (50,  10,  90)
UI_GOLD         = (255, 210,  60)
UI_ORANGE       = (255, 140,  30)

# ── Glow-shine palette per fighter (colour A, colour B, halo) ───────────────
FIGHTER_GLOW = {
    "rapid_blaster":    ((255, 100, 50),  (255, 200, 80),  (255, 80, 20)),    # orange fire
    "heavy_destroyer":  ((120, 60, 255),  (200, 100, 255), (80, 20, 200)),    # purple storm
    "balanced_fighter": ((30, 200, 255),  (80, 255, 220),  (0, 120, 200)),    # cyan aurora
    "machine_gunner":   ((255, 50, 180),  (255, 150, 80),  (200, 20, 120)),   # pink-magenta
}


# ==================== GAME STATES ====================
class GameState(enum.Enum):
    MENU    = 1
    PLAYING = 2
    GAME_OVER = 3


# ==================== INITIALIZATION ====================
pygame.init()

screen = pygame.display.set_mode((800, 600))
clock  = pygame.time.Clock()

background = pygame.image.load(os.path.join(_SCRIPT_DIR, "background.png"))

mixer.music.load(os.path.join(_SCRIPT_DIR, "background.wav"))
mixer.music.play(-1)

pygame.display.set_caption("Nebula Strike")
icon = pygame.image.load(os.path.join(_SCRIPT_DIR, "ufo.png"))
pygame.display.set_icon(icon)


def load_ui_font(size):
    try:
        return pygame.font.Font(FONT_PATH, size)
    except OSError:
        path = pygame.font.match_font("couriernew,courier,freemono,monospace")
        if path:
            return pygame.font.Font(path, max(size, 12))
        return pygame.font.Font(None, max(size, 14))


font_hud   = load_ui_font(12)
font_small = load_ui_font(10)
font_menu  = load_ui_font(11)
font_title = load_ui_font(20)
font_over  = load_ui_font(22)


# ==================== PLAYER ====================
PLAYER_FALLBACK_PATH   = os.path.join(_SCRIPT_DIR, "player.png")
_default_player_sheet  = pygame.image.load(PLAYER_FALLBACK_PATH).convert_alpha()
PLAYER_GAMEPLAY_SIZE   = _default_player_sheet.get_size()
MENU_FIGHTER_THUMB_SIZE = 110

FIGHTER_IMAGE_CANDIDATES = {
    "rapid_blaster":   ["fighter1.png","Fighter 1.png","fighter 1.png","fighter_1.png","Fighter1.png"],
    "heavy_destroyer": ["fighter2.png","Fighter 2.png","fighter 2.png","fighter_2.png","Fighter2.png"],
    "balanced_fighter":["fighter3.png","Fighter 3.png","fighter 3.png","fighter_3.png","Fighter3.png"],
    "machine_gunner":  ["fighter4.png","Fighter 4.png","fighter 4.png","fighter_4.png","Fighter4.png"],
}


def load_fighter_source_image(shooter_key):
    for fname in FIGHTER_IMAGE_CANDIDATES[shooter_key]:
        path = os.path.join(_SCRIPT_DIR, fname)
        if os.path.isfile(path):
            return pygame.image.load(path).convert_alpha()
    return _default_player_sheet.copy()


fighter_source_images = {k: load_fighter_source_image(k) for k in FIGHTER_IMAGE_CANDIDATES}
fighter_menu_thumbs   = {
    k: pygame.transform.smoothscale(img, (MENU_FIGHTER_THUMB_SIZE, MENU_FIGHTER_THUMB_SIZE))
    for k, img in fighter_source_images.items()
}

playerImg        = pygame.transform.smoothscale(fighter_source_images["rapid_blaster"], PLAYER_GAMEPLAY_SIZE)
hud_life_icon    = pygame.transform.smoothscale(playerImg, (20, 18))
playerX          = 370.0
playerY          = 480
playerX_change   = 0.0


def player_x_max():
    return float(800 - playerImg.get_width())


def apply_fighter_sprite(shooter_key):
    global playerImg, hud_life_icon
    src       = fighter_source_images[shooter_key]
    playerImg = pygame.transform.smoothscale(src, PLAYER_GAMEPLAY_SIZE)
    hud_life_icon = pygame.transform.smoothscale(playerImg, (20, 18))


# ==================== GLOW / SHINE HELPERS ====================
def make_glow_surface(radius, color, alpha_center=200, alpha_edge=0):
    """Radial gradient glow circle."""
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = radius, radius
    for r in range(radius, 0, -1):
        t     = r / radius          # 1 at edge → 0 at center
        alpha = int(alpha_center + (alpha_edge - alpha_center) * t)
        col   = (*color, max(0, min(255, alpha)))
        pygame.draw.circle(surf, col, (cx, cy), r)
    return surf


def make_shine_overlay(w, h, color_a, color_b):
    """Diagonal gloss sheen on a portrait."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(w + h):
        t     = i / (w + h)
        alpha = int(60 * math.sin(math.pi * t))
        r = int(color_a[0] + (color_b[0] - color_a[0]) * t)
        g = int(color_a[1] + (color_b[1] - color_a[1]) * t)
        b = int(color_a[2] + (color_b[2] - color_a[2]) * t)
        pygame.draw.line(surf, (r, g, b, alpha), (i, 0), (0, i))
    return surf


def draw_fighter_portrait(surface, thumb, pos, selected):
    """Render fighter portrait cleanly – just the image, thin neon line if selected."""
    x, y   = pos
    tw, th = thumb.get_size()
    surface.blit(thumb, (x, y))
    if selected:
        # Thin neon underline below the selected ship
        pygame.draw.line(surface, UI_ACCENT, (x, y + th + 2), (x + tw, y + th + 2), 2)


# ==================== DIFFICULTY ====================
DIFFICULTY = {
    'start_enemies':            1,
    'max_enemies':              12,          # high cap
    'enemy_increase_interval':  10,          # +1 enemy every 10s
    'enemy_speed_min_pps':      30,          # start faster
    'enemy_speed_max_pps':      140,         # very fast horizontal ceiling
    'enemy_speed_ramp_seconds': 120.0,       # full ramp in 2 min
    'enemy_vertical_step':      25,          # starting descent per bounce
    'enemy_descent_ramp_sec':   60.0,        # reach max descent in 60s
    'enemy_descent_max_step':   120,         # max descent per bounce
    # Enemy shooting (unlocks once player has killed this many enemies)
    'enemy_shoot_unlock_kills':  3,          # shoot after 3 kills
    'enemy_shoot_interval_min':  1.2,        # fastest enemy fire rate (sec)
    'enemy_shoot_interval_max':  3.5,        # slowest enemy fire rate (sec)
    'enemy_shoot_speed_pps':     280,        # enemy bullet downward speed
}


# ==================== ENEMY ====================
def create_enemies(num_of_enemies=None, initial_speed_pps=None):
    if num_of_enemies is None:
        num_of_enemies = DIFFICULTY['start_enemies']
    if initial_speed_pps is None:
        initial_speed_pps = DIFFICULTY['enemy_speed_min_pps']
    enemies = {'img': [], 'X': [], 'Y': [], 'X_change': [], 'Y_change': []}
    enemy_path = os.path.join(_SCRIPT_DIR, "enemy.png")
    for _ in range(num_of_enemies):
        enemies['img'].append(pygame.image.load(enemy_path))
        enemies['X'].append(float(random.randint(0, 736)))
        enemies['Y'].append(float(random.randint(50, 150)))
        enemies['X_change'].append(float(initial_speed_pps))
        enemies['Y_change'].append(float(DIFFICULTY['enemy_vertical_step']))
    return enemies


enemy_data     = create_enemies()
enemyImg       = enemy_data['img']
enemyX         = enemy_data['X']
enemyY         = enemy_data['Y']
enemyX_change  = enemy_data['X_change']
enemyY_change  = enemy_data['Y_change']


# ==================== ENEMY BULLETS ====================
# Each entry: {'x', 'y', 'vy'}  — goes straight down
enemy_bullets   = []

# Per-enemy fire cooldown timers (index matches enemyX/Y lists)
enemy_fire_timers = []

# Track total enemies killed to unlock enemy shooting
total_kills = 0


def make_enemy_bullet_surface():
    """Small glowing red-orange downward bolt."""
    w, h = 6, 14
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (255, 60, 0, 80),  (0, 0, w, h))
    pygame.draw.ellipse(surf, (255, 160, 0, 200), (1, 1, w - 2, h - 2))
    pygame.draw.ellipse(surf, (255, 255, 180, 255), (2, 2, w - 4, h - 4))
    return surf


ENEMY_BULLET_SURF = make_enemy_bullet_surface()


def reset_enemy_fire_timers():
    """Reset per-enemy shoot timers to match current enemy list."""
    global enemy_fire_timers
    enemy_fire_timers = [
        random.uniform(1.0, DIFFICULTY['enemy_shoot_interval_max'])
        for _ in enemyX
    ]


def update_enemy_bullets(dt):
    """Move enemy bullets down; remove those off-screen."""
    global enemy_bullets
    for b in enemy_bullets:
        b['y'] += b['vy'] * dt
    enemy_bullets = [b for b in enemy_bullets if b['y'] < 650]


def draw_enemy_bullets():
    for b in enemy_bullets:
        screen.blit(ENEMY_BULLET_SURF, (int(b['x']) - 3, int(b['y'])))


def check_enemy_bullet_player_collision():
    """Return True and remove bullet if any enemy bullet hits the player."""
    global enemy_bullets, lives
    pw, ph = playerImg.get_size()
    pcx = playerX + pw / 2
    pcy = playerY + ph / 2
    hit = False
    surviving = []
    for b in enemy_bullets:
        dist = math.sqrt((b['x'] - pcx) ** 2 + (b['y'] - pcy) ** 2)
        if dist < 28:
            lives -= 1
            hit = True
            # don't add to surviving — bullet consumed
        else:
            surviving.append(b)
    enemy_bullets = surviving
    return hit



def make_shiny_bullet_surface(size_t):
    size_t = max(0.12, min(0.36, float(size_t)))
    rw = max(2, int(round(1.4 + 2.2 * size_t)))
    rh = max(5, int(round(5.0 + 9.0 * size_t)))
    pad = 3
    w, h = rw + pad * 2, rh + pad * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx   = w // 2
    pygame.draw.ellipse(surf, (40, 120, 210, 65),  (0, 0, w, h - 1))
    pygame.draw.ellipse(surf, (90, 200, 255, 140), (1, 1, w - 2, h - 3))
    pygame.draw.ellipse(surf, (200, 250, 255, 245),(pad, pad - 1, rw, rh + 1))
    pygame.draw.ellipse(surf, (255, 255, 255, 255),(pad + 1, pad, max(1, rw - 2), rh))
    glint_x = cx - 1
    for gy in range(pad + 1, min(pad + rh, h - 2)):
        surf.set_at((glint_x, gy), (255, 255, 255, 255))
        if glint_x + 1 < w:
            surf.set_at((glint_x + 1, gy), (230, 255, 255, 220))
    pygame.draw.circle(surf, (255, 255, 255, 255), (glint_x, pad + 1), 1)
    return surf


bulletImg        = make_shiny_bullet_surface(0.2)
# Legacy single-bullet kept only for compatibility; actual firing uses active_bullets
bulletX          = 0.0
bulletY          = 480.0
bulletX_change   = 0
bulletY_change   = 10
bullet_state     = "ready"


# ==================== SCORE / LIVES ====================
score_value = 0
lives       = 3

game_time_seconds       = 0.0
shot_cooldown_interval  = 0.25
fire_cooldown_remaining = 0.0


# ==================== POWER-UPS ====================
class PowerUpType:
    def __init__(self, name, color, duration, description):
        self.name = name
        self.color = color
        self.duration = duration
        self.description = description


POWERUP_TYPES = {
    'rapid_fire': PowerUpType("Rapid Fire", (255, 255, 0),  7.0, "Faster shooting"),
    'shield':     PowerUpType("Shield",     (0, 255, 255),  6.0, "Temporary immunity"),
    'extra_life': PowerUpType("Extra Life", (0, 255, 0),    0,   "+1 Life"),
}

POWERUP_SETTINGS = {'spawn_chance': 0.003, 'fall_speed': 3, 'size': 20}

active_powerups = {}
powerup_img     = []
powerup_X       = []
powerup_Y       = []
powerup_type    = []


# ==================== SHOOTER TYPES ====================
class ShooterType:
    def __init__(self, name, fighter_label, move_speed_pps, damage,
                 shot_cooldown_sec, bullet_speed_pps, bullet_scale,
                 bullet_count, bullet_spread_deg, description):
        self.name              = name
        self.fighter_label     = fighter_label
        self.move_speed_pps    = move_speed_pps
        self.damage            = damage
        self.shot_cooldown_sec = shot_cooldown_sec
        self.bullet_speed_pps  = bullet_speed_pps
        self.bullet_scale      = bullet_scale
        self.bullet_count      = bullet_count       # how many bullets per shot
        self.bullet_spread_deg = bullet_spread_deg  # total spread angle in degrees
        self.description       = description


SHOOTER_TYPES = {
    "rapid_blaster": ShooterType(
        name="Rapid Blaster",    fighter_label="Fighter 1",
        move_speed_pps=215,      damage=1,
        shot_cooldown_sec=0.09,  bullet_speed_pps=640,
        bullet_scale=0.22,       bullet_count=3,  bullet_spread_deg=24,
        description="Triple fast shots"
    ),
    "heavy_destroyer": ShooterType(
        name="Heavy Destroyer",  fighter_label="Fighter 2",
        move_speed_pps=148,      damage=3,
        shot_cooldown_sec=0.28,  bullet_speed_pps=510,
        bullet_scale=0.28,       bullet_count=2,  bullet_spread_deg=14,
        description="Twin heavy blasts"
    ),
    "balanced_fighter": ShooterType(
        name="Balanced Fighter", fighter_label="Fighter 3",
        move_speed_pps=182,      damage=2,
        shot_cooldown_sec=0.15,  bullet_speed_pps=575,
        bullet_scale=0.25,       bullet_count=3,  bullet_spread_deg=18,
        description="Balanced spread"
    ),
    "machine_gunner": ShooterType(
        name="Machine Gunner",   fighter_label="Fighter 4",
        move_speed_pps=205,      damage=1,
        shot_cooldown_sec=0.055, bullet_speed_pps=610,
        bullet_scale=0.18,       bullet_count=5,  bullet_spread_deg=36,
        description="5-way spray"
    ),
}

menu_options = list(SHOOTER_TYPES.keys())


def set_bullet_for_shooter(shooter_key):
    global bulletImg
    bulletImg = make_shiny_bullet_surface(SHOOTER_TYPES[shooter_key].bullet_scale)


set_bullet_for_shooter(menu_options[0])


# ==================== GAME STATE ====================
current_state  = GameState.MENU
menu_selection = 0
selected_shooter = None
menu_pulse_t   = 0.0   # animated timer for menu glow


# ==================== DRAWING HELPERS ====================
def draw_retro_text(surface, text, pos, font_obj, color, outline_color=None):
    if outline_color is None:
        outline_color = UI_BG
    x, y     = int(pos[0]), int(pos[1])
    rendered  = font_obj.render(text, True, color)
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        o = font_obj.render(text, True, outline_color)
        surface.blit(o, (x + ox, y + oy))
    surface.blit(rendered, (x, y))


def draw_retro_text_centered(surface, text, y, font_obj, color, outline_color=None):
    probe = font_obj.render(text, True, color)
    x = (surface.get_width() - probe.get_width()) // 2
    draw_retro_text(surface, text, (x, y), font_obj, color, outline_color)


def draw_crt_frame(surface):
    w, h = surface.get_size()
    pygame.draw.rect(surface, UI_ACCENT_DIM, (0, 0, w, h), 2)
    pygame.draw.rect(surface, UI_ACCENT,     (4, 4, w - 8, h - 8), 1)
    arm, thick, c = 28, 2, UI_ACCENT
    pygame.draw.line(surface, c, (8, 8), (8 + arm, 8), thick)
    pygame.draw.line(surface, c, (8, 8), (8, 8 + arm), thick)
    pygame.draw.line(surface, c, (w-8, 8), (w-8-arm, 8), thick)
    pygame.draw.line(surface, c, (w-8, 8), (w-8, 8+arm), thick)
    pygame.draw.line(surface, c, (8, h-8), (8+arm, h-8), thick)
    pygame.draw.line(surface, c, (8, h-8), (8, h-8-arm), thick)
    pygame.draw.line(surface, c, (w-8, h-8), (w-8-arm, h-8), thick)
    pygame.draw.line(surface, c, (w-8, h-8), (w-8, h-8-arm), thick)


def draw_scanlines(surface, step=3, alpha=22):
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for y in range(0, surface.get_height(), step):
        pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (surface.get_width(), y))
    surface.blit(overlay, (0, 0))


def draw_hud_bar():
    bar = pygame.Surface((800, 44), pygame.SRCALPHA)
    bar.fill((10, 6, 28, 210))
    # gradient line at bottom
    for x in range(800):
        t   = x / 800
        r   = int(UI_ACCENT[0] * t + UI_ACCENT2[0] * (1 - t))
        g   = int(UI_ACCENT[1] * t + UI_ACCENT2[1] * (1 - t))
        b   = int(UI_ACCENT[2] * t + UI_ACCENT2[2] * (1 - t))
        bar.set_at((x, 43), (r, g, b, 200))
    screen.blit(bar, (0, 0))


def show_score(x, y):
    draw_retro_text(screen, f"SCORE {score_value}", (x, y), font_hud, UI_GOLD)


def game_over_text():
    draw_retro_text_centered(screen, "GAME OVER", 218, font_over, UI_ACCENT)


def show_restart_prompt():
    draw_retro_text_centered(screen, "ENTER / SPACE  MENU", 322, font_small, UI_TEXT_MUTED)


def show_lives(x, y):
    draw_retro_text(screen, "LIVES", (x, y), font_hud, UI_TEXT_MUTED)
    for i in range(lives):
        screen.blit(hud_life_icon, (x + 52 + i * 24, y - 2))


def show_title():
    draw_retro_text_centered(screen, "NEBULA  STRIKE", 56, font_title, UI_ACCENT, UI_GLOW)
    draw_retro_text_centered(screen, "SELECT YOUR FIGHTER", 90, font_small, UI_TEXT_MUTED)
    pygame.draw.line(screen, UI_ACCENT_DIM, (80, 108), (720, 108), 1)


def menu_move_selection(selection, key):
    if key == pygame.K_UP:    return selection - 2 if selection >= 2 else selection
    if key == pygame.K_DOWN:  return selection + 2 if selection < 2 else selection
    if key == pygame.K_LEFT:  return selection - 1 if selection % 2 == 1 else selection
    if key == pygame.K_RIGHT: return selection + 1 if selection % 2 == 0 and selection < 3 else selection
    return selection


# Neon label colours per fighter (pure vivid hues, no glow needed)
FIGHTER_NEON = {
    "rapid_blaster":    (255, 80,  200),  # hot pink
    "heavy_destroyer":  (140, 80,  255),  # violet
    "balanced_fighter": (0,   220, 255),  # cyan
    "machine_gunner":   (255, 200,  0),   # gold
}


def draw_fighter_select_menu(options, selection):
    """4 fighters in 2x2 grid – perfectly centered, plain portraits, neon text."""
    SCREEN_W   = 800
    thumb_size = MENU_FIGHTER_THUMB_SIZE   # 110
    gap_x      = 270   # horizontal gap between cell centers
    gap_y      = 188   # vertical gap between rows

    # Total grid width = one gap between two columns
    grid_w = thumb_size + gap_x
    base_x = (SCREEN_W - grid_w) // 2  # left edge of column 0
    base_y = 130

    for i, shooter_key in enumerate(options):
        col, row = i % 2, i // 2
        # Center of each cell, then offset left by half thumb
        cx = base_x + col * gap_x
        cy = base_y + row * gap_y
        thumb = fighter_menu_thumbs[shooter_key]
        tw, th = thumb.get_size()
        tx = cx + (thumb_size - tw) // 2

        sel = (i == selection)
        draw_fighter_portrait(screen, thumb, (tx, cy), sel)

        # Shooter name – bright neon when selected, dimmed when not
        st    = SHOOTER_TYPES[shooter_key]
        label = st.name.upper()
        neon  = FIGHTER_NEON[shooter_key]
        lc    = neon if sel else UI_TEXT_MUTED
        lw    = font_menu.render(label, True, lc).get_width()
        lx    = tx + (tw - lw) // 2
        draw_retro_text(screen, label, (lx, cy + th + 10), font_menu, lc)

        # Description – white when selected
        desc  = st.description
        dc    = UI_TEXT if sel else UI_TEXT_MUTED
        dw    = font_small.render(desc, True, dc).get_width()
        dx    = tx + (tw - dw) // 2
        draw_retro_text(screen, desc, (dx, cy + th + 26), font_small, dc)


def show_instructions():
    instructions = [
        ("ARROWS", "  SELECT FIGHTER"),
        ("ENTER",  "  START"),
        ("SPACE",  "  FIRE  IN GAME"),
    ]
    y0 = 556
    SCREEN_W = 800
    for i, (key, rest) in enumerate(instructions):
        full_text = key + rest
        total_w = font_small.render(full_text, True, UI_TEXT_MUTED).get_width()
        start_x = (SCREEN_W - total_w) // 2
        draw_retro_text(screen, key, (start_x, y0 + i * 14), font_small, (0, 220, 255))
        kw = font_small.render(key, True, (0, 220, 255)).get_width()
        draw_retro_text(screen, rest, (start_x + kw, y0 + i * 14), font_small, UI_TEXT_MUTED)


def player(x, y):
    screen.blit(playerImg, (int(round(x)), int(round(y))))


def enemy(x, y, i):
    screen.blit(enemyImg[i], (int(round(x)), int(round(y))))


# ==================== MULTI-BULLET FIRING ====================
def fire_bullets(x, y, shooter_key):
    """Spawn bullets going straight up for the chosen shooter."""
    global active_bullets
    st     = SHOOTER_TYPES[shooter_key]
    count  = st.bullet_count
    spd    = st.bullet_speed_pps
    pw, ph = playerImg.get_size()
    bw, bh = bulletImg.get_size()
    by0    = int(round(y)) + max(4, ph // 8)

    # Space bullets evenly across the ship width, all going straight up
    if count == 1:
        offsets = [pw // 2 - bw // 2]
    else:
        spread_px = min(pw - bw, 40 * (count - 1))
        offsets = [
            pw // 2 - bw // 2 + int((k - (count - 1) / 2) * spread_px / max(count - 1, 1))
            for k in range(count)
        ]

    for off in offsets:
        bx0 = int(round(x)) + off
        active_bullets.append({'x': float(bx0), 'y': float(by0), 'vx': 0.0, 'vy': -spd})


def draw_bullets():
    for b in active_bullets:
        screen.blit(bulletImg, (int(b['x']), int(b['y'])))


def update_bullets(dt):
    global active_bullets
    for b in active_bullets:
        b['x'] += b['vx'] * dt
        b['y'] += b['vy'] * dt
    active_bullets = [b for b in active_bullets if -20 < b['y'] < 640 and -20 < b['x'] < 820]


# ==================== COLLISION ====================
def isCollision(enemyX, enemyY, bulletX, bulletY):
    distance = math.sqrt((enemyX - bulletX) ** 2 + (enemyY - bulletY) ** 2)
    return distance < 27


def isPlayerCollision(ex, ey, px, py):
    distance = math.sqrt((ex - px) ** 2 + (ey - py) ** 2)
    return distance < 40


def remove_enemy(index):
    global enemyX, enemyY, enemyX_change, enemyY_change, enemyImg
    enemyX.pop(index)
    enemyY.pop(index)
    enemyX_change.pop(index)
    enemyY_change.pop(index)
    enemyImg.pop(index)


def spawn_powerup(x, y):
    powerup_keys = list(POWERUP_TYPES.keys())
    weights      = [4, 4, 1]
    chosen       = random.choices(powerup_keys, weights=weights)[0]
    powerup_img.append(pygame.image.load(os.path.join(_SCRIPT_DIR, "enemy.png")))
    powerup_X.append(x)
    powerup_Y.append(y)
    powerup_type.append(chosen)


def update_powerups(frame_dt):
    global shot_cooldown_interval
    for key in list(active_powerups.keys()):
        active_powerups[key] -= frame_dt
        if active_powerups[key] <= 0:
            if key == 'rapid_fire':
                shot_cooldown_interval = SHOOTER_TYPES[selected_shooter].shot_cooldown_sec
            del active_powerups[key]


def apply_powerup(key):
    global lives, shot_cooldown_interval, fire_cooldown_remaining
    powerup  = POWERUP_TYPES[key]
    shooter  = SHOOTER_TYPES[selected_shooter]
    if key == 'extra_life':
        lives += 1
    elif key == 'rapid_fire':
        shot_cooldown_interval = max(0.06, shooter.shot_cooldown_sec * 0.5)
        fire_cooldown_remaining = 0.0
        active_powerups[key]   = powerup.duration
    elif key == 'shield':
        active_powerups[key] = powerup.duration


def isPowerupCollision(px, py, playerX, playerY):
    return math.sqrt((px - playerX) ** 2 + (py - playerY) ** 2) < 45


def show_active_powerups():
    y_pos = 560
    for key, remaining in active_powerups.items():
        powerup      = POWERUP_TYPES[key]
        seconds_left = max(0, int(math.ceil(remaining)))
        status_text  = f"{powerup.name.upper()} {seconds_left}s"
        draw_retro_text(screen, status_text, (10, y_pos), font_small, powerup.color)
        y_pos -= 16


# ==================== DIFFICULTY ====================
def get_current_difficulty(elapsed_seconds):
    enemy_increase_count = int(elapsed_seconds / DIFFICULTY['enemy_increase_interval'])
    max_enemies = min(
        DIFFICULTY['start_enemies'] + enemy_increase_count,
        DIFFICULTY['max_enemies']
    )
    lo   = float(DIFFICULTY['enemy_speed_min_pps'])
    hi   = float(DIFFICULTY['enemy_speed_max_pps'])
    ramp = max(1.0, float(DIFFICULTY['enemy_speed_ramp_seconds']))
    t    = min(1.0, max(0.0, elapsed_seconds / ramp))
    enemy_speed_pps = lo + t * (hi - lo)

    # Enemy descent step also increases over time (faster fall)
    base_step = float(DIFFICULTY['enemy_vertical_step'])
    max_step  = float(DIFFICULTY['enemy_descent_max_step'])
    d_ramp    = max(1.0, float(DIFFICULTY['enemy_descent_ramp_sec']))
    dt_frac   = min(1.0, elapsed_seconds / d_ramp)
    descent_step = base_step + dt_frac * (max_step - base_step)

    return max_enemies, float(enemy_speed_pps), float(descent_step)


def spawn_enemy(enemy_speed_pps=None, descent_step=None):
    if enemy_speed_pps is None:
        _, enemy_speed_pps, descent_step = get_current_difficulty(game_time_seconds)
    if descent_step is None:
        descent_step = float(DIFFICULTY['enemy_vertical_step'])
    enemy_path = os.path.join(_SCRIPT_DIR, "enemy.png")
    enemyImg.append(pygame.image.load(enemy_path))
    enemyX.append(float(random.randint(0, 736)))
    enemyY.append(float(random.randint(50, 150)))
    sign = random.choice((-1.0, 1.0))
    enemyX_change.append(sign * enemy_speed_pps)
    enemyY_change.append(descent_step)


def reset_game():
    global playerX, playerY, playerX_change
    global bullet_state, fire_cooldown_remaining, shot_cooldown_interval
    global score_value, lives, game_time_seconds
    global enemyX, enemyY, enemyX_change, enemyY_change, enemyImg
    global selected_shooter
    global powerup_img, powerup_X, powerup_Y, powerup_type
    global active_powerups, active_bullets
    global enemy_bullets, enemy_fire_timers, total_kills
    global playerImg, hud_life_icon

    shooter = SHOOTER_TYPES[selected_shooter]
    apply_fighter_sprite(selected_shooter)
    set_bullet_for_shooter(selected_shooter)
    playerX  = (800 - playerImg.get_width()) / 2.0
    playerY  = 480
    playerX_change      = 0.0
    shot_cooldown_interval  = shooter.shot_cooldown_sec
    bullet_state            = "ready"
    fire_cooldown_remaining = 0.0

    score_value = 0
    lives       = 3
    game_time_seconds = 0.0

    _, start_pps, d_step = get_current_difficulty(0.0)
    enemy_data = create_enemies(DIFFICULTY['start_enemies'], start_pps)
    enemyImg      = enemy_data['img']
    enemyX        = enemy_data['X']
    enemyY        = enemy_data['Y']
    enemyX_change = enemy_data['X_change']
    enemyY_change = enemy_data['Y_change']

    powerup_img  = []
    powerup_X    = []
    powerup_Y    = []
    powerup_type = []
    active_powerups = {}
    active_bullets  = []
    enemy_bullets   = []
    total_kills     = 0
    reset_enemy_fire_timers()


# ==================== MAIN GAME LOOP ====================
running = True
while running:
    dt = min(clock.tick(60) / 1000.0, 0.05)

    screen.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if current_state == GameState.MENU:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                    menu_selection = menu_move_selection(menu_selection, event.key)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    selected_shooter = menu_options[menu_selection]
                    reset_game()
                    current_state = GameState.PLAYING

        elif current_state == GameState.PLAYING:
            shooter = SHOOTER_TYPES[selected_shooter]

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:  playerX_change = -shooter.move_speed_pps
                if event.key == pygame.K_RIGHT: playerX_change =  shooter.move_speed_pps
                if event.key == pygame.K_SPACE:
                    if fire_cooldown_remaining <= 0:
                        bulletSound = mixer.Sound(os.path.join(_SCRIPT_DIR, "laser.wav"))
                        bulletSound.play()
                        fire_bullets(playerX, playerY, selected_shooter)
                        fire_cooldown_remaining = shot_cooldown_interval

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    playerX_change = 0.0

        elif current_state == GameState.GAME_OVER:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    current_state  = GameState.MENU
                    menu_selection = 0

    # ── MENU ──────────────────────────────────────────────────────────────────
    if current_state == GameState.MENU:
        # Semi-transparent dark overlay so background doesn't overpower
        overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
        overlay.fill((0, 0, 10, 155))
        screen.blit(overlay, (0, 0))

        show_title()
        draw_fighter_select_menu(menu_options, menu_selection)
        show_instructions()

    # ── PLAYING ───────────────────────────────────────────────────────────────
    elif current_state == GameState.PLAYING:
        draw_hud_bar()
        shooter = SHOOTER_TYPES[selected_shooter]
        update_powerups(dt)
        update_bullets(dt)

        game_time_seconds += dt
        max_enemies, enemy_speed_pps, descent_step = get_current_difficulty(game_time_seconds)

        while len(enemyX) < max_enemies:
            spawn_enemy(enemy_speed_pps, descent_step)

        # Player movement
        playerX += playerX_change * dt
        playerX  = max(0.0, min(playerX, player_x_max()))

        fire_cooldown_remaining = max(0.0, fire_cooldown_remaining - dt)

        # Enemy update & bullet collision
        i = 0
        while i < len(enemyX):
            if isPlayerCollision(enemyX[i], enemyY[i], playerX, playerY):
                lives -= 1
                remove_enemy(i)
                if lives <= 0:
                    current_state = GameState.GAME_OVER
                continue

            if enemyY[i] > 600:
                remove_enemy(i)
                spawn_enemy(enemy_speed_pps, descent_step)
                continue

            # Update enemy horizontal speed towards current difficulty speed
            sign = 1.0 if enemyX_change[i] >= 0 else -1.0
            enemyX_change[i]  = sign * enemy_speed_pps
            enemyY_change[i]  = descent_step    # always current descent step
            enemyX[i]        += enemyX_change[i] * dt

            if enemyX[i] < 0:
                enemyX[i]    = 0.0
                enemyX_change[i] = enemy_speed_pps
                enemyY[i]   += enemyY_change[i]
            elif enemyX[i] > 736:
                enemyX[i]    = 736.0
                enemyX_change[i] = -enemy_speed_pps
                enemyY[i]   += enemyY_change[i]

            # Check each active bullet against this enemy
            hit = False
            for bi in range(len(active_bullets) - 1, -1, -1):
                b = active_bullets[bi]
                if isCollision(enemyX[i], enemyY[i], b['x'], b['y']):
                    explosionSound = mixer.Sound(os.path.join(_SCRIPT_DIR, "explosion.wav"))
                    explosionSound.play()
                    active_bullets.pop(bi)
                    score_value += shooter.damage
                    total_kills += 1
                    # Chance to drop power-up
                    if random.random() < POWERUP_SETTINGS['spawn_chance'] * 300:
                        spawn_powerup(enemyX[i], enemyY[i])
                    # Sync fire timer list after removal
                    if i < len(enemy_fire_timers):
                        enemy_fire_timers.pop(i)
                    remove_enemy(i)
                    spawn_enemy(enemy_speed_pps, descent_step)
                    # Add timer for new enemy
                    enemy_fire_timers.append(
                        random.uniform(1.5, DIFFICULTY['enemy_shoot_interval_max'])
                    )
                    hit = True
                    break

            if hit:
                continue

            # Enemy shooting logic (unlocked after enough kills)
            if total_kills >= DIFFICULTY['enemy_shoot_unlock_kills']:
                # Ensure timer list stays in sync with enemy list
                while len(enemy_fire_timers) <= i:
                    enemy_fire_timers.append(
                        random.uniform(1.0, DIFFICULTY['enemy_shoot_interval_max'])
                    )
                enemy_fire_timers[i] -= dt
                if enemy_fire_timers[i] <= 0:
                    # Fire a bullet straight down from this enemy
                    ex_center = enemyX[i] + 32  # approx center of enemy sprite
                    enemy_bullets.append({'x': ex_center, 'y': enemyY[i] + 32,
                                          'vy': DIFFICULTY['enemy_shoot_speed_pps']})
                    # Reset with faster interval as game progresses
                    interval = max(
                        DIFFICULTY['enemy_shoot_interval_min'],
                        DIFFICULTY['enemy_shoot_interval_max'] - game_time_seconds * 0.015
                    )
                    enemy_fire_timers[i] = random.uniform(interval * 0.7, interval)

            enemy(enemyX[i], enemyY[i], i)
            i += 1

        # Draw player bullets
        draw_bullets()

        # Update & draw enemy bullets + check player hit
        update_enemy_bullets(dt)
        draw_enemy_bullets()
        if check_enemy_bullet_player_collision():
            if lives <= 0:
                current_state = GameState.GAME_OVER

        # Power-ups
        j = 0
        while j < len(powerup_X):
            powerup_Y[j] += POWERUP_SETTINGS['fall_speed']
            if powerup_Y[j] > 600:
                powerup_img.pop(j); powerup_X.pop(j)
                powerup_Y.pop(j);  powerup_type.pop(j)
                continue
            if isPowerupCollision(powerup_X[j], powerup_Y[j], playerX, playerY):
                apply_powerup(powerup_type[j])
                powerup_img.pop(j); powerup_X.pop(j)
                powerup_Y.pop(j);  powerup_type.pop(j)
                continue
            pt   = POWERUP_TYPES[powerup_type[j]]
            pu_s = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.circle(pu_s, (*pt.color, 220), (9, 9), 9)
            screen.blit(pu_s, (int(powerup_X[j]), int(powerup_Y[j])))
            j += 1

        player(playerX, playerY)
        show_score(14, 12)
        show_lives(548, 12)
        draw_retro_text(screen,
                        SHOOTER_TYPES[selected_shooter].fighter_label.upper(),
                        (14, 28), font_small, UI_ACCENT_DIM)
        show_active_powerups()

    # ── GAME OVER ─────────────────────────────────────────────────────────────
    elif current_state == GameState.GAME_OVER:
        # Dark overlay
        ov = pygame.Surface((800, 600), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))

        go_panel = pygame.Surface((540, 210), pygame.SRCALPHA)
        go_panel.fill((*UI_PANEL, 235))
        pygame.draw.rect(go_panel, UI_ACCENT, (0, 0, 540, 210), 2)
        # Top gradient bar
        for gx in range(540):
            t = gx / 540
            r = int(UI_ACCENT[0] * (1 - t) + UI_ACCENT2[0] * t)
            g = int(UI_ACCENT[1] * (1 - t) + UI_ACCENT2[1] * t)
            b = int(UI_ACCENT[2] * (1 - t) + UI_ACCENT2[2] * t)
            pygame.draw.line(go_panel, (r, g, b, 200), (gx, 0), (gx, 3))
        screen.blit(go_panel, (130, 195))

        game_over_text()
        draw_retro_text_centered(screen, f"SCORE {score_value}", 262, font_menu, UI_GOLD)
        draw_retro_text_centered(screen,
                                 SHOOTER_TYPES[selected_shooter].fighter_label.upper(),
                                 286, font_small, UI_TEXT_MUTED)
        show_restart_prompt()

    draw_crt_frame(screen)
    draw_scanlines(screen)
    pygame.display.update()
