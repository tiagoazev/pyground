"""
Configurações globais de Masconia.

Centraliza todas as constantes de gameplay, resolução, cores e paths.
Isso permite ajustar o balanceamento sem tocar na lógica de jogo.
"""
import os

# ── Paths ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
SPRITES_DIR = os.path.join(ASSETS_DIR, "sprites")
TILESETS_DIR = os.path.join(ASSETS_DIR, "tilesets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# ── Display ────────────────────────────────────────────────
TILE_SIZE = 32          # Pixel art 32x32 por tile
GRID_WIDTH = 30         # Tiles horizontais visíveis
GRID_HEIGHT = 20        # Tiles verticais visíveis
SCREEN_WIDTH = TILE_SIZE * GRID_WIDTH   # 960px
SCREEN_HEIGHT = TILE_SIZE * GRID_HEIGHT # 640px
FPS = 60
TITLE = "Masconia: Chronicles of the Mysterious Smoke"

# ── Cores UI ───────────────────────────────────────────────
COLOR_BG = (20, 20, 30)
COLOR_TEXT = (220, 220, 220)
COLOR_TEXT_DIM = (140, 140, 140)
COLOR_HP = (200, 50, 50)
COLOR_HP_BAR = (50, 150, 50)
COLOR_MANA = (50, 100, 200)
COLOR_XP = (200, 180, 50)
COLOR_GOLD = (255, 215, 0)
COLOR_HIGHLIGHT = (255, 255, 100, 128)
COLOR_SELECT = (0, 200, 255, 160)
COLOR_ATTACK_RANGE = (255, 80, 80, 100)
COLOR_MOVE_RANGE = (80, 200, 80, 100)

# ── Gameplay ───────────────────────────────────────────────
MAX_FLOOR = 15
XP_PER_KILL_BASE = 10
XP_LEVEL_UP_BASE = 100
LEVEL_UP_STAT_BONUS = 1
CRIT_THRESHOLD = 20      # Natural 20 = crítico
FUMBLE_THRESHOLD = 1     # Natural 1 = falha crítica
ADVANTAGE_BONUS = 5      # Bônus simplificado para vantagem

# ── Meta-progressão ────────────────────────────────────────
DRAGON_SOUL_PER_BOSS = 50
DRAGON_SOUL_PER_MINIBOSS = 20
DRAGON_SOUL_PER_FLOOR = 5

# Classes desbloqueáveis (inicialmente apenas as 4 básicas)
UNLOCKABLE_CLASSES = ["paladin", "ranger", "warlock", "monk"]

# Relíquias iniciais desbloqueadas
STARTING_RELICS = ["broken_dice"]
