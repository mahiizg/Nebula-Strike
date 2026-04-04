import math
import random
import enum

import pygame
from pygame import mixer


# ==================== GAME STATES ====================
class GameState(enum.Enum):
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3


# ==================== INITIALIZATION ====================
pygame.init()

# Create the screen
screen = pygame.display.set_mode((800, 600))

# Background
background = pygame.image.load('background.png')

# Sound
mixer.music.load("background.wav")
mixer.music.play(-1)

# Caption and Icon
pygame.display.set_caption("Space Invader")
icon = pygame.image.load('ufo.png')
pygame.display.set_icon(icon)

# Fonts
font = pygame.font.Font('freesansbold.ttf', 32)
over_font = pygame.font.Font('freesansbold.ttf', 64)
title_font = pygame.font.Font('freesansbold.ttf', 48)
menu_font = pygame.font.Font('freesansbold.ttf', 36)


# ==================== PLAYER ====================
playerImg = pygame.image.load('player.png')
playerX = 370
playerY = 480
playerX_change = 0


# ==================== DIFFICULTY SCALING (tuning; used by enemy creation & progression) ====================
# Difficulty is tracked by elapsed time in the PLAYING state (see game_time in reset_game / main loop).
DIFFICULTY = {
    'start_enemies': 1,
    'max_enemies': 6,
    'enemy_increase_interval': 18,  # seconds between +1 max enemy slot
    'start_speed': 1,               # base horizontal speed (matches initial enemyX_change)
    'max_speed': 4,                 # cap on scaled horizontal speed after bounces
    'speed_increase_interval': 22,  # seconds between +1 speed step
}


# ==================== ENEMY ====================
def create_enemies(num_of_enemies=None):
    """Create new enemy lists with initial positions."""
    if num_of_enemies is None:
        num_of_enemies = DIFFICULTY['start_enemies']
    enemies = {
        'img': [],
        'X': [],
        'Y': [],
        'X_change': [],
        'Y_change': []
    }
    initial_dx = DIFFICULTY['start_speed']
    for i in range(num_of_enemies):
        enemies['img'].append(pygame.image.load('enemy.png'))
        enemies['X'].append(random.randint(0, 736))
        enemies['Y'].append(random.randint(50, 150))
        enemies['X_change'].append(initial_dx)
        enemies['Y_change'].append(40)
    return enemies


# Initialize enemies
enemy_data = create_enemies()
enemyImg = enemy_data['img']
enemyX = enemy_data['X']
enemyY = enemy_data['Y']
enemyX_change = enemy_data['X_change']
enemyY_change = enemy_data['Y_change']


# ==================== BULLET ====================
bulletImg = pygame.image.load('bullet.png')
bulletX = 0
bulletY = 480
bulletX_change = 0
bulletY_change = 10
bullet_state = "ready"

# Ready - You can't see the bullet on the screen
# Fire - The bullet is currently moving


# ==================== SCORE ====================
score_value = 0
textX = 10
textY = 10


# ==================== LIVES SYSTEM ====================
lives = 3
life_textX = 650  # Top right corner
life_textY = 10


# Difficulty time counter (frames in PLAYING); reset in reset_game
game_time = 0


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
        duration=420,            # 7 seconds at 60fps
        description="Faster shooting"
    ),
    'shield': PowerUpType(
        name="Shield",
        color=(0, 255, 255),     # Cyan
        duration=360,            # 6 seconds at 60fps
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
    def __init__(self, name, movement_speed, damage, fire_rate, bullet_speed, description):
        self.name = name
        self.movement_speed = movement_speed  # Player movement speed
        self.damage = damage  # Bullet damage (score per kill)
        self.fire_rate = fire_rate  # Cooldown in frames between shots
        self.bullet_speed = bullet_speed  # Bullet velocity
        self.description = description


# Define the 4 shooter types with balanced gameplay
SHOOTER_TYPES = {
    "rapid_blaster": ShooterType(
        name="Rapid Blaster",
        movement_speed=7,        # Fast movement
        damage=1,                # Low damage
        fire_rate=8,             # Very fast shooting (lower = faster)
        bullet_speed=12,         # Fast bullets
        description="Fast & agile, weak shots"
    ),
    "heavy_destroyer": ShooterType(
        name="Heavy Destroyer",
        movement_speed=3,        # Slow movement
        damage=3,                # High damage (3x score)
        fire_rate=25,            # Slow fire rate
        bullet_speed=8,          # Slower bullets
        description="Slow but powerful"
    ),
    "balanced_fighter": ShooterType(
        name="Balanced Fighter",
        movement_speed=5,        # Medium movement
        damage=2,                # Medium damage (2x score)
        fire_rate=15,            # Medium fire rate
        bullet_speed=10,         # Standard bullet speed
        description="Well-rounded stats"
    ),
    "machine_gunner": ShooterType(
        name="Machine Gunner",
        movement_speed=4,        # Below avg movement
        damage=1,                # Low damage
        fire_rate=5,             # Rapid fire
        bullet_speed=9,          # Slightly below avg speed
        description="Rapid fire, low damage"
    ),
}

# Menu options now use shooter type keys
menu_options = list(SHOOTER_TYPES.keys())


# ==================== GAME STATE VARIABLES ====================
current_state = GameState.MENU
menu_selection = 0  # For navigating menu options
selected_shooter = None  # Will hold the chosen ShooterType instance


# ==================== FUNCTIONS ====================
def show_score(x, y):
    score = font.render("Score : " + str(score_value), True, (255, 255, 255))
    screen.blit(score, (x, y))


def game_over_text():
    over_text = over_font.render("GAME OVER", True, (255, 255, 255))
    screen.blit(over_text, (200, 250))


def show_restart_prompt():
    restart_text = font.render("Press ENTER to Return to Menu", True, (255, 255, 255))
    screen.blit(restart_text, (180, 350))


def show_lives(x, y):
    """Display remaining lives in HUD."""
    lives_display = font.render("Lives: " + str(lives), True, (255, 255, 255))
    screen.blit(lives_display, (x, y))


def show_title():
    title_text = title_font.render("SPACE INVADER", True, (255, 255, 255))
    screen.blit(title_text, (200, 100))


def show_menu_options(options, selection):
    """Display shooter type options with names and descriptions."""
    for i, shooter_key in enumerate(options):
        shooter = SHOOTER_TYPES[shooter_key]
        color = (255, 255, 0) if i == selection else (255, 255, 255)
        # Display shooter name
        name_text = menu_font.render(shooter.name, True, color)
        screen.blit(name_text, (250, 250 + i * 60))
        # Display description below
        desc_font = pygame.font.Font('freesansbold.ttf', 20)
        desc_text = desc_font.render(shooter.description, True, (150, 150, 150))
        screen.blit(desc_text, (260, 285 + i * 60))


def show_instructions():
    """Display game instructions."""
    instructions = [
        "Arrow Keys - Move Left/Right",
        "SPACE - Fire Bullet",
        "Destroy enemies - don't let them pass!"
    ]
    inst_font = pygame.font.Font('freesansbold.ttf', 24)
    for i, text in enumerate(instructions):
        rendered = inst_font.render(text, True, (200, 200, 200))
        screen.blit(rendered, (150, 520 + i * 28))


def player(x, y):
    screen.blit(playerImg, (x, y))


def enemy(x, y, i):
    screen.blit(enemyImg[i], (x, y))


def fire_bullet(x, y):
    global bullet_state
    bullet_state = "fire"
    screen.blit(bulletImg, (x + 16, y + 10))


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

    powerup_img.append(pygame.image.load('enemy.png'))  # Reuse enemy image with tint
    powerup_X.append(x)
    powerup_Y.append(y)
    powerup_type.append(chosen)


def update_powerups():
    """Update active power-up timers and apply effects."""
    global fire_cooldown, base_fire_rate

    # Update timed power-ups
    for key in list(active_powerups.keys()):
        active_powerups[key] -= 1
        if active_powerups[key] <= 0:
            # Power-up expired
            if key == 'rapid_fire':
                # Restore base fire rate
                base_fire_rate = SHOOTER_TYPES[selected_shooter].fire_rate
            del active_powerups[key]


def apply_powerup(key):
    """Apply a power-up effect when collected."""
    global lives, base_fire_rate, fire_cooldown

    powerup = POWERUP_TYPES[key]

    if key == 'extra_life':
        # Instant effect
        lives += 1
    elif key == 'rapid_fire':
        # Temporarily reduce fire cooldown
        base_fire_rate = max(2, SHOOTER_TYPES[selected_shooter].fire_rate // 2)
        fire_cooldown = 0  # Allow immediate fire
        active_powerups[key] = powerup.duration
    elif key == 'shield':
        # Temporary immunity
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
    powerup_font = pygame.font.Font('freesansbold.ttf', 20)
    y_pos = 550
    for key, remaining in active_powerups.items():
        powerup = POWERUP_TYPES[key]
        seconds_left = remaining // 60
        status_text = f"{powerup.name}: {seconds_left}s"
        rendered = powerup_font.render(status_text, True, powerup.color)
        screen.blit(rendered, (10, y_pos))
        y_pos -= 25


def get_current_difficulty(game_time_frames):
    """
    Calculate current difficulty based on elapsed game time.
    Returns (max_enemies, enemy_speed) tuple.
    """
    fps = 60
    elapsed_seconds = game_time_frames / fps

    # Calculate max enemies: increases every DIFFICULTY['enemy_increase_interval'] seconds
    enemy_increase_count = int(elapsed_seconds / DIFFICULTY['enemy_increase_interval'])
    max_enemies = min(
        DIFFICULTY['start_enemies'] + enemy_increase_count,
        DIFFICULTY['max_enemies']
    )

    # Calculate enemy speed: increases every DIFFICULTY['speed_increase_interval'] seconds
    speed_increase_count = int(elapsed_seconds / DIFFICULTY['speed_increase_interval'])
    enemy_speed = min(
        DIFFICULTY['start_speed'] + speed_increase_count,
        DIFFICULTY['max_speed']
    )

    return max_enemies, enemy_speed


def spawn_enemy(enemy_speed=None):
    """Spawn a single enemy at a random position at the top."""
    if enemy_speed is None:
        _, enemy_speed = get_current_difficulty(game_time)
    enemyImg.append(pygame.image.load('enemy.png'))
    enemyX.append(random.randint(0, 736))
    enemyY.append(random.randint(50, 150))
    enemyX_change.append(enemy_speed)
    enemyY_change.append(40)


def reset_game():
    """Reset all game variables to initial state."""
    global playerX, playerY, playerX_change
    global bulletX, bulletY, bullet_state, fire_cooldown, base_fire_rate
    global score_value, lives, game_time
    global enemyX, enemyY, enemyX_change, enemyY_change, enemyImg
    global selected_shooter
    global powerup_img, powerup_X, powerup_Y, powerup_type
    global active_powerups

    # Apply selected shooter attributes
    shooter = SHOOTER_TYPES[selected_shooter]
    playerX_change = 0
    base_fire_rate = shooter.fire_rate

    # Reset bullet
    bulletX = 0
    bulletY = 480
    bullet_state = "ready"
    fire_cooldown = 0

    # Reset score and lives
    score_value = 0
    lives = 3

    # Reset game time for difficulty scaling
    game_time = 0

    # Reset enemies - start with only 1 enemy
    enemy_data = create_enemies(num_of_enemies=DIFFICULTY['start_enemies'])
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

    # RGB = Red, Green, Blue
    screen.fill((0, 0, 0))
    # Background Image
    screen.blit(background, (0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # ==================== STATE: MENU ====================
        if current_state == GameState.MENU:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    menu_selection = (menu_selection - 1) % len(menu_options)
                if event.key == pygame.K_DOWN:
                    menu_selection = (menu_selection + 1) % len(menu_options)
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    # Start game with selected shooter type
                    selected_shooter = menu_options[menu_selection]
                    reset_game()
                    current_state = GameState.PLAYING

        # ==================== STATE: PLAYING ====================
        elif current_state == GameState.PLAYING:
            # Get selected shooter stats
            shooter = SHOOTER_TYPES[selected_shooter]

            # if keystroke is pressed check whether its right or left
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    playerX_change = -shooter.movement_speed
                if event.key == pygame.K_RIGHT:
                    playerX_change = shooter.movement_speed
                if event.key == pygame.K_SPACE:
                    # Check fire cooldown
                    if fire_cooldown <= 0:
                        bulletSound = mixer.Sound("laser.wav")
                        bulletSound.play()
                        bulletX = playerX
                        bulletY = 480
                        fire_bullet(bulletX, bulletY)
                        fire_cooldown = shooter.fire_rate

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                    playerX_change = 0

        # ==================== STATE: GAME_OVER ====================
        elif current_state == GameState.GAME_OVER:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    # Return to menu
                    current_state = GameState.MENU
                    menu_selection = 0

    # ==================== RENDER BASED ON STATE ====================

    if current_state == GameState.MENU:
        show_title()
        show_menu_options(menu_options, menu_selection)
        show_instructions()

    elif current_state == GameState.PLAYING:
        # Get selected shooter stats
        shooter = SHOOTER_TYPES[selected_shooter]

        # Update game time for difficulty scaling
        game_time += 1

        # Calculate current difficulty based on elapsed time
        max_enemies, enemy_speed = get_current_difficulty(game_time)

        # Spawn enemies up to the current max
        while len(enemyX) < max_enemies:
            spawn_enemy(enemy_speed)

        # Player Movement
        playerX += playerX_change
        if playerX <= 0:
            playerX = 0
        elif playerX >= 736:
            playerX = 736

        # Update fire cooldown
        if fire_cooldown > 0:
            fire_cooldown -= 1

        # Enemy Movement and Collision
        i = 0
        while i < len(enemyX):
            # Check player-enemy collision
            if isPlayerCollision(enemyX[i], enemyY[i], playerX, playerY):
                lives -= 1
                remove_enemy(i)
                if lives <= 0:
                    current_state = GameState.GAME_OVER
                continue  # Skip rest of loop for this enemy

            # Enemy goes off screen - remove it (no life penalty)
            if enemyY[i] > 600:
                remove_enemy(i)
                # Spawn a new enemy to keep the game going
                spawn_enemy(enemy_speed)
                continue

            # Apply current difficulty speed to enemy movement
            enemyX[i] += enemyX_change[i] * (enemy_speed / DIFFICULTY['start_speed'])
            if enemyX[i] <= 0:
                enemyX_change[i] = enemy_speed
                enemyY[i] += enemyY_change[i]
            elif enemyX[i] >= 736:
                enemyX_change[i] = -enemy_speed
                enemyY[i] += enemyY_change[i]

            # Bullet Collision Detection
            collision = isCollision(enemyX[i], enemyY[i], bulletX, bulletY)
            if collision:
                explosionSound = mixer.Sound("explosion.wav")
                explosionSound.play()
                bulletY = 480
                bullet_state = "ready"
                score_value += shooter.damage  # Use shooter damage
                remove_enemy(i)
                # Spawn a new enemy
                spawn_enemy(enemy_speed)
                continue

            enemy(enemyX[i], enemyY[i], i)
            i += 1

        # Bullet Movement
        if bulletY <= 0:
            bulletY = 480
            bullet_state = "ready"

        if bullet_state == "fire":
            fire_bullet(bulletX, bulletY)
            bulletY -= shooter.bullet_speed  # Use shooter bullet speed

        player(playerX, playerY)
        show_score(textX, textY)
        show_lives(life_textX, life_textY)

    elif current_state == GameState.GAME_OVER:
        game_over_text()
        final_score = font.render("Final Score: " + str(score_value), True, (255, 255, 255))
        screen.blit(final_score, (280, 300))
        shooter_name = font.render("Shooter: " + SHOOTER_TYPES[selected_shooter].name, True, (255, 255, 255))
        screen.blit(shooter_name, (240, 340))
        show_restart_prompt()

    pygame.display.update()
