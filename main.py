import math
import os
import random
import enum

import pygame
from pygame import mixer

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(_SCRIPT_DIR, "fonts", "PressStart2P-Regular.ttf")

# Retro palette
UI_BG = (12, 14, 28)
UI_PANEL = (24, 28, 48)
UI_ACCENT = (0, 255, 170)
UI_ACCENT_DIM = (0, 180, 120)
UI_TEXT = (220, 255, 240)
UI_TEXT_MUTED = (140, 160, 180)
UI_GLOW = (0, 60, 45)


# ==================== GAME STATES ====================
class GameState(enum.Enum):
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3


# ==================== INITIALIZATION ====================
pygame.init()

# Create the screen
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# Background
background = pygame.image.load(os.path.join(_SCRIPT_DIR, "background.png"))

# Sound
mixer.music.load(os.path.join(_SCRIPT_DIR, "background.wav"))
mixer.music.play(-1)

# Caption and Icon
pygame.display.set_caption("Space Invader")
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


# Smaller retro-style UI fonts (Press Start 2P reads best from 10px+)
font_hud = load_ui_font(12)
font_small = load_ui_font(10)
font_menu = load_ui_font(12)
font_title = load_ui_font(18)
font_over = load_ui_font(20)


# ==================== PLAYER ====================
playerImg = pygame.image.load(os.path.join(_SCRIPT_DIR, "player.png"))
hud_life_icon = pygame.transform.smoothscale(playerImg, (20, 18))
playerX = 370.0
playerY = 480
playerX_change = 0.0  # signed move speed (pixels/sec) while key held


# ==================== DIFFICULTY SCALING (tuning; used by enemy creation & progression) ====================
# Difficulty is tracked by elapsed time in the PLAYING state (see game_time_seconds in reset_game / main loop).
DIFFICULTY = {
    'start_enemies': 1,
    'max_enemies': 6,
    'enemy_increase_interval': 24,   # seconds between +1 max enemy slot
    'enemy_speed_min_pps': 10,       # horizontal speed at game start (pixels/sec)
    'enemy_speed_max_pps': 32,       # horizontal speed after full ramp (pixels/sec)
    # Linear ramp: speed blends min→max over this many seconds (smooth gradual increase)
    'enemy_speed_ramp_seconds': 240.0,
    'enemy_vertical_step': 10,    # pixels down when an enemy hits a side wall
}


# ==================== ENEMY ====================
def create_enemies(num_of_enemies=None, initial_speed_pps=None):
    """Create new enemy lists with initial positions (float coords, velocity in px/sec)."""
    if num_of_enemies is None:
        num_of_enemies = DIFFICULTY['start_enemies']
    if initial_speed_pps is None:
        initial_speed_pps = DIFFICULTY['enemy_speed_min_pps']
    enemies = {
        'img': [],
        'X': [],
        'Y': [],
        'X_change': [],
        'Y_change': []
    }
    enemy_path = os.path.join(_SCRIPT_DIR, "enemy.png")
    for i in range(num_of_enemies):
        enemies['img'].append(pygame.image.load(enemy_path))
        enemies['X'].append(float(random.randint(0, 736)))
        enemies['Y'].append(float(random.randint(50, 150)))
        enemies['X_change'].append(float(initial_speed_pps))
        enemies['Y_change'].append(float(DIFFICULTY['enemy_vertical_step']))
    return enemies


# Initialize enemies
enemy_data = create_enemies()
enemyImg = enemy_data['img']
enemyX = enemy_data['X']
enemyY = enemy_data['Y']
enemyX_change = enemy_data['X_change']
enemyY_change = enemy_data['Y_change']


# ==================== BULLET ====================
bulletImg = pygame.image.load(os.path.join(_SCRIPT_DIR, "bullet.png"))
bulletX = 0.0
bulletY = 480.0
bulletX_change = 0
bulletY_change = 10
bullet_state = "ready"

# Ready - You can't see the bullet on the screen
# Fire - The bullet is currently moving


# ==================== SCORE ====================
score_value = 0

# ==================== LIVES SYSTEM ====================
lives = 3


# Difficulty time (seconds in PLAYING); reset in reset_game
game_time_seconds = 0.0

# Firing (seconds)
shot_cooldown_interval = 0.25
fire_cooldown_remaining = 0.0


# ==================== POWER-UP SYSTEM ====================
class PowerUpType:
    """Defines attributes for each power-up type."""
    def __init__(self, name, color, duration, description):
        self.name = name
        self.color = color       # RGB color for rendering
        self.duration = duration # Duration in frames (0 = instant)
        self.description = description


# Power-up definitions
POWERUP_TYPES = {
    'rapid_fire': PowerUpType(
        name="Rapid Fire",
        color=(255, 255, 0),     # Yellow
        duration=7.0,            # seconds
        description="Faster shooting"
    ),
    'shield': PowerUpType(
        name="Shield",
        color=(0, 255, 255),     # Cyan
        duration=6.0,
        description="Temporary immunity"
    ),
    'extra_life': PowerUpType(
        name="Extra Life",
        color=(0, 255, 0),       # Green
        duration=0,              # Instant effect
        description="+1 Life"
    ),
}

# Power-up tuning
POWERUP_SETTINGS = {
    'spawn_chance': 0.003,       # Chance per frame to spawn when enemy count allows
    'fall_speed': 3,             # Pixels per frame
    'size': 20,                  # Size for collision detection
}

# Active power-up state (tracks currently active timed power-ups)
active_powerups = {}  # {powerup_key: remaining_frames}

# Power-up entities (falling power-ups on screen)
powerup_img = []  # List of power-up images
powerup_X = []    # X positions
powerup_Y = []    # Y positions (falling down)
powerup_type = [] # Type key for each power-up


# ==================== SHOOTER TYPES ====================
class ShooterType:
    """Defines attributes for each shooter type."""
    def __init__(self, name, move_speed_pps, damage, shot_cooldown_sec, bullet_speed_pps, description):
        self.name = name
        self.move_speed_pps = move_speed_pps  # Player horizontal speed (pixels/sec)
        self.damage = damage  # Bullet damage (score per kill)
        self.shot_cooldown_sec = shot_cooldown_sec  # Minimum seconds between shots
        self.bullet_speed_pps = bullet_speed_pps  # Bullet upward speed (pixels/sec)
        self.description = description


# Define the 4 shooter types with balanced gameplay
SHOOTER_TYPES = {
    "rapid_blaster": ShooterType(
        name="Rapid Blaster",
        move_speed_pps=215,
        damage=1,
        shot_cooldown_sec=0.055,
        bullet_speed_pps=440,
        description="Fast & weak shots"
    ),
    "heavy_destroyer": ShooterType(
        name="Heavy Destroyer",
        move_speed_pps=148,
        damage=3,
        shot_cooldown_sec=0.22,
        bullet_speed_pps=350,
        description="Slow, heavy hits"
    ),
    "balanced_fighter": ShooterType(
        name="Balanced Fighter",
        move_speed_pps=182,
        damage=2,
        shot_cooldown_sec=0.12,
        bullet_speed_pps=395,
        description="Balanced"
    ),
    "machine_gunner": ShooterType(
        name="Machine Gunner",
        move_speed_pps=205,
        damage=1,
        shot_cooldown_sec=0.04,
        bullet_speed_pps=420,
        description="Spray & pray"
    ),
}

# Menu options now use shooter type keys
menu_options = list(SHOOTER_TYPES.keys())


# ==================== GAME STATE VARIABLES ====================
current_state = GameState.MENU
menu_selection = 0  # For navigating menu options
selected_shooter = None  # Will hold the chosen ShooterType instance


# ==================== FUNCTIONS ====================
def draw_retro_text(surface, text, pos, font_obj, color, outline_color=None):
    """Pixel-game style text with dark outline."""
    if outline_color is None:
        outline_color = UI_BG
    x, y = int(pos[0]), int(pos[1])
    rendered = font_obj.render(text, True, color)
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        o = font_obj.render(text, True, outline_color)
        surface.blit(o, (x + ox, y + oy))
    surface.blit(rendered, (x, y))


def draw_retro_text_centered(surface, text, y, font_obj, color, outline_color=None):
    probe = font_obj.render(text, True, color)
    x = (surface.get_width() - probe.get_width()) // 2
    draw_retro_text(surface, text, (x, y), font_obj, color, outline_color)


def draw_crt_frame(surface):
    """Subtle border + corner brackets."""
    w, h = surface.get_size()
    pygame.draw.rect(surface, UI_ACCENT_DIM, (0, 0, w, h), 2)
    pygame.draw.rect(surface, UI_ACCENT, (4, 4, w - 8, h - 8), 1)
    arm = 28
    thick = 2
    c = UI_ACCENT
    # top-left
    pygame.draw.line(surface, c, (8, 8), (8 + arm, 8), thick)
    pygame.draw.line(surface, c, (8, 8), (8, 8 + arm), thick)
    # top-right
    pygame.draw.line(surface, c, (w - 8, 8), (w - 8 - arm, 8), thick)
    pygame.draw.line(surface, c, (w - 8, 8), (w - 8, 8 + arm), thick)
    # bottom-left
    pygame.draw.line(surface, c, (8, h - 8), (8 + arm, h - 8), thick)
    pygame.draw.line(surface, c, (8, h - 8), (8, h - 8 - arm), thick)
    # bottom-right
    pygame.draw.line(surface, c, (w - 8, h - 8), (w - 8 - arm, h - 8), thick)
    pygame.draw.line(surface, c, (w - 8, h - 8), (w - 8, h - 8 - arm), thick)


def draw_scanlines(surface, step=3, alpha=28):
    """Light CRT-style overlay."""
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for y in range(0, surface.get_height(), step):
        pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (surface.get_width(), y))
    surface.blit(overlay, (0, 0))


def draw_menu_panel():
    panel = pygame.Surface((620, 420), pygame.SRCALPHA)
    panel.fill((*UI_PANEL, 220))
    pygame.draw.rect(panel, UI_ACCENT, (0, 0, 620, 420), 2)
    pygame.draw.rect(panel, UI_ACCENT_DIM, (4, 4, 612, 412), 1)
    screen.blit(panel, (90, 72))


def draw_hud_bar():
    bar = pygame.Surface((800, 40), pygame.SRCALPHA)
    bar.fill((*UI_BG, 200))
    pygame.draw.line(bar, UI_ACCENT_DIM, (0, 39), (800, 39))
    screen.blit(bar, (0, 0))


def show_score(x, y):
    draw_retro_text(screen, f"SCORE {score_value}", (x, y), font_hud, UI_TEXT)


def game_over_text():
    draw_retro_text_centered(screen, "GAME OVER", 218, font_over, UI_ACCENT)


def show_restart_prompt():
    draw_retro_text_centered(screen, "ENTER / SPACE  MENU", 322, font_small, UI_TEXT_MUTED)


def show_lives(x, y):
    draw_retro_text(screen, "LIVES", (x, y), font_hud, UI_TEXT_MUTED)
    for i in range(lives):
        screen.blit(hud_life_icon, (x + 52 + i * 24, y - 2))


def show_title():
    draw_retro_text_centered(screen, "SPACE INVADER", 96, font_title, UI_ACCENT, UI_GLOW)
    draw_retro_text_centered(screen, "CLASSIC ARCADE", 124, font_small, UI_TEXT_MUTED)


def show_menu_options(options, selection):
    """Display shooter type options with names and descriptions."""
    base_y = 200
    row_h = 52
    for i, shooter_key in enumerate(options):
        shooter = SHOOTER_TYPES[shooter_key]
        y = base_y + i * row_h
        sel = i == selection
        if sel:
            pygame.draw.polygon(screen, UI_ACCENT, [(118, y + 6), (118, y + 18), (130, y + 12)])
        name_color = UI_ACCENT if sel else UI_TEXT
        draw_retro_text(screen, shooter.name.upper(), (148, y), font_menu, name_color)
        draw_retro_text(
            screen,
            shooter.description,
            (148, y + 18),
            font_small,
            UI_TEXT_MUTED if not sel else UI_TEXT,
        )


def show_instructions():
    instructions = [
        "ARROWS  MOVE",
        "SPACE  FIRE",
        "DONT LET THEM LAND",
    ]
    y0 = 498
    for i, text in enumerate(instructions):
        draw_retro_text(screen, text, (120, y0 + i * 16), font_small, UI_TEXT_MUTED)


def player(x, y):
    screen.blit(playerImg, (int(round(x)), int(round(y))))


def enemy(x, y, i):
    screen.blit(enemyImg[i], (int(round(x)), int(round(y))))


def fire_bullet(x, y):
    global bullet_state
    bullet_state = "fire"
    screen.blit(bulletImg, (int(round(x)) + 16, int(round(y)) + 10))


def isCollision(enemyX, enemyY, bulletX, bulletY):
    distance = math.sqrt(math.pow(enemyX - bulletX, 2) + (math.pow(enemyY - bulletY, 2)))
    if distance < 27:
        return True
    else:
        return False


def isPlayerCollision(enemyX, enemyY, playerX, playerY):
    """Check if enemy has collided with player."""
    distance = math.sqrt(math.pow(enemyX - playerX, 2) + (math.pow(enemyY - playerY, 2)))
    if distance < 40:  # Larger collision box for player
        return True
    else:
        return False


def remove_enemy(index):
    """Remove an enemy at the given index and respawn it at the top."""
    global enemyX, enemyY, enemyX_change, enemyY_change, enemyImg
    # Remove from all lists
    enemyX.pop(index)
    enemyY.pop(index)
    enemyX_change.pop(index)
    enemyY_change.pop(index)
    enemyImg.pop(index)


def spawn_powerup(x, y):
    """Spawn a random power-up at the given position."""
    import random
    powerup_keys = list(POWERUP_TYPES.keys())
    # Weight: extra_life is rarer than others
    weights = [4, 4, 1]  # rapid_fire, shield, extra_life
    chosen = random.choices(powerup_keys, weights=weights)[0]

    powerup_img.append(pygame.image.load(os.path.join(_SCRIPT_DIR, "enemy.png")))
    powerup_X.append(x)
    powerup_Y.append(y)
    powerup_type.append(chosen)


def update_powerups(frame_dt):
    """Update active power-up timers and apply effects."""
    global shot_cooldown_interval

    for key in list(active_powerups.keys()):
        active_powerups[key] -= frame_dt
        if active_powerups[key] <= 0:
            if key == 'rapid_fire':
                shot_cooldown_interval = SHOOTER_TYPES[selected_shooter].shot_cooldown_sec
            del active_powerups[key]


def apply_powerup(key):
    """Apply a power-up effect when collected."""
    global lives, shot_cooldown_interval, fire_cooldown_remaining

    powerup = POWERUP_TYPES[key]
    shooter = SHOOTER_TYPES[selected_shooter]

    if key == 'extra_life':
        lives += 1
    elif key == 'rapid_fire':
        shot_cooldown_interval = max(0.06, shooter.shot_cooldown_sec * 0.5)
        fire_cooldown_remaining = 0.0
        active_powerups[key] = powerup.duration
    elif key == 'shield':
        active_powerups[key] = powerup.duration


def isPowerupCollision(px, py, playerX, playerY):
    """Check if player has collected a power-up."""
    distance = math.sqrt(math.pow(px - playerX, 2) + (math.pow(py - playerY, 2)))
    if distance < 45:  # Slightly larger than player collision
        return True
    else:
        return False


def show_active_powerups():
    """Display currently active power-ups on screen."""
    y_pos = 560
    for key, remaining in active_powerups.items():
        powerup = POWERUP_TYPES[key]
        seconds_left = max(0, int(math.ceil(remaining)))
        status_text = f"{powerup.name.upper()} {seconds_left}s"
        draw_retro_text(screen, status_text, (10, y_pos), font_small, powerup.color)
        y_pos -= 16


def get_current_difficulty(elapsed_seconds):
    """
    Calculate current difficulty based on elapsed play time (seconds).
    Enemy horizontal speed ramps linearly from min to max over enemy_speed_ramp_seconds.
    Returns (max_enemies, enemy_speed_pps).
    """
    enemy_increase_count = int(elapsed_seconds / DIFFICULTY['enemy_increase_interval'])
    max_enemies = min(
        DIFFICULTY['start_enemies'] + enemy_increase_count,
        DIFFICULTY['max_enemies']
    )

    lo = float(DIFFICULTY['enemy_speed_min_pps'])
    hi = float(DIFFICULTY['enemy_speed_max_pps'])
    ramp = max(1.0, float(DIFFICULTY['enemy_speed_ramp_seconds']))
    t = min(1.0, max(0.0, elapsed_seconds / ramp))
    enemy_speed_pps = lo + t * (hi - lo)

    return max_enemies, float(enemy_speed_pps)


def spawn_enemy(enemy_speed_pps=None):
    """Spawn a single enemy at a random position at the top."""
    if enemy_speed_pps is None:
        _, enemy_speed_pps = get_current_difficulty(game_time_seconds)
    enemy_path = os.path.join(_SCRIPT_DIR, "enemy.png")
    enemyImg.append(pygame.image.load(enemy_path))
    enemyX.append(float(random.randint(0, 736)))
    enemyY.append(float(random.randint(50, 150)))
    sign = random.choice((-1.0, 1.0))
    enemyX_change.append(sign * enemy_speed_pps)
    enemyY_change.append(float(DIFFICULTY['enemy_vertical_step']))


def reset_game():
    """Reset all game variables to initial state."""
    global playerX, playerY, playerX_change
    global bulletX, bulletY, bullet_state, fire_cooldown_remaining, shot_cooldown_interval
    global score_value, lives, game_time_seconds
    global enemyX, enemyY, enemyX_change, enemyY_change, enemyImg
    global selected_shooter
    global powerup_img, powerup_X, powerup_Y, powerup_type
    global active_powerups

    shooter = SHOOTER_TYPES[selected_shooter]
    playerX = 370.0
    playerY = 480
    playerX_change = 0.0
    shot_cooldown_interval = shooter.shot_cooldown_sec

    bulletX = 0.0
    bulletY = 480.0
    bullet_state = "ready"
    fire_cooldown_remaining = 0.0

    score_value = 0
    lives = 3

    game_time_seconds = 0.0

    _, start_enemy_pps = get_current_difficulty(0.0)
    enemy_data = create_enemies(
        num_of_enemies=DIFFICULTY['start_enemies'],
        initial_speed_pps=start_enemy_pps,
    )
    enemyImg = enemy_data['img']
    enemyX = enemy_data['X']
    enemyY = enemy_data['Y']
    enemyX_change = enemy_data['X_change']
    enemyY_change = enemy_data['Y_change']

    # Clear power-ups
    powerup_img = []
    powerup_X = []
    powerup_Y = []
    powerup_type = []
    active_powerups = {}


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
                if event.key == pygame.K_UP:
                    menu_selection = (menu_selection - 1) % len(menu_options)
                if event.key == pygame.K_DOWN:
                    menu_selection = (menu_selection + 1) % len(menu_options)
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    selected_shooter = menu_options[menu_selection]
                    reset_game()
                    current_state = GameState.PLAYING

        elif current_state == GameState.PLAYING:
            shooter = SHOOTER_TYPES[selected_shooter]

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    playerX_change = -shooter.move_speed_pps
                if event.key == pygame.K_RIGHT:
                    playerX_change = shooter.move_speed_pps
                if event.key == pygame.K_SPACE:
                    if fire_cooldown_remaining <= 0:
                        bulletSound = mixer.Sound(os.path.join(_SCRIPT_DIR, "laser.wav"))
                        bulletSound.play()
                        bulletX = playerX
                        bulletY = float(playerY)
                        fire_bullet(bulletX, bulletY)
                        fire_cooldown_remaining = shot_cooldown_interval

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                    playerX_change = 0.0

        elif current_state == GameState.GAME_OVER:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    current_state = GameState.MENU
                    menu_selection = 0

    if current_state == GameState.MENU:
        draw_menu_panel()
        screen.blit(pygame.transform.smoothscale(icon, (44, 44)), (686, 84))
        show_title()
        show_menu_options(menu_options, menu_selection)
        show_instructions()

    elif current_state == GameState.PLAYING:
        draw_hud_bar()
        shooter = SHOOTER_TYPES[selected_shooter]
        update_powerups(dt)

        game_time_seconds += dt
        max_enemies, enemy_speed_pps = get_current_difficulty(game_time_seconds)

        while len(enemyX) < max_enemies:
            spawn_enemy(enemy_speed_pps)

        playerX += playerX_change * dt
        if playerX <= 0:
            playerX = 0.0
        elif playerX >= 736:
            playerX = 736.0

        fire_cooldown_remaining = max(0.0, fire_cooldown_remaining - dt)

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
                spawn_enemy(enemy_speed_pps)
                continue

            sign = 1.0 if enemyX_change[i] >= 0 else -1.0
            enemyX_change[i] = sign * enemy_speed_pps
            enemyX[i] += enemyX_change[i] * dt

            if enemyX[i] < 0:
                enemyX[i] = 0.0
                enemyX_change[i] = enemy_speed_pps
                enemyY[i] += enemyY_change[i]
            elif enemyX[i] > 736:
                enemyX[i] = 736.0
                enemyX_change[i] = -enemy_speed_pps
                enemyY[i] += enemyY_change[i]

            collision = isCollision(enemyX[i], enemyY[i], bulletX, bulletY)
            if collision:
                explosionSound = mixer.Sound(os.path.join(_SCRIPT_DIR, "explosion.wav"))
                explosionSound.play()
                bulletY = 480.0
                bullet_state = "ready"
                score_value += shooter.damage
                remove_enemy(i)
                spawn_enemy(enemy_speed_pps)
                continue

            enemy(enemyX[i], enemyY[i], i)
            i += 1

        if bulletY <= 0:
            bulletY = 480.0
            bullet_state = "ready"

        if bullet_state == "fire":
            fire_bullet(bulletX, bulletY)
            bulletY -= shooter.bullet_speed_pps * dt

        player(playerX, playerY)
        show_score(14, 10)
        show_lives(548, 10)
        draw_retro_text(
            screen,
            SHOOTER_TYPES[selected_shooter].name.upper(),
            (14, 26),
            font_small,
            UI_ACCENT_DIM,
        )
        show_active_powerups()

    elif current_state == GameState.GAME_OVER:
        go_panel = pygame.Surface((540, 200), pygame.SRCALPHA)
        go_panel.fill((*UI_PANEL, 230))
        pygame.draw.rect(go_panel, UI_ACCENT, (0, 0, 540, 200), 2)
        screen.blit(go_panel, (130, 200))
        game_over_text()
        draw_retro_text_centered(screen, f"SCORE {score_value}", 266, font_menu, UI_TEXT)
        draw_retro_text_centered(
            screen,
            SHOOTER_TYPES[selected_shooter].name.upper(),
            290,
            font_small,
            UI_TEXT_MUTED,
        )
        show_restart_prompt()

    draw_crt_frame(screen)
    draw_scanlines(screen)
    pygame.display.update()
