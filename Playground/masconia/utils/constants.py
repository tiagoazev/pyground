"""
Enums e constantes tipadas para todo o projeto.

Uso de IntEnum permite comparações diretas e serialização limpa.
"""
from enum import IntEnum, auto


class GameState(IntEnum):
    """Estados possíveis da máquina de estados do jogo."""
    MAIN_MENU = auto()
    CLASS_SELECT = auto()
    DUNGEON_GENERATION = auto()
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    COMBAT_ANIMATION = auto()
    INVENTORY = auto()
    SHOP = auto()
    REST_SITE = auto()
    LEVEL_UP = auto()
    GAME_OVER = auto()
    VICTORY = auto()
    DAILY_CHALLENGE = auto()


class DamageType(IntEnum):
    """Tipos de dano para resistências/weaknesses."""
    SLASHING = auto()
    PIERCING = auto()
    BLUDGEONING = auto()
    FIRE = auto()
    COLD = auto()
    LIGHTNING = auto()
    ACID = auto()
    POISON = auto()
    NECROTIC = auto()
    RADIANT = auto()
    FORCE = auto()
    THUNDER = auto()
    PSYCHIC = auto()


class TileType(IntEnum):
    """Tipos de tiles na masmorra."""
    WALL = auto()
    FLOOR = auto()
    DOOR = auto()
    DOOR_OPEN = auto()
    STAIRS_DOWN = auto()
    STAIRS_UP = auto()
    TRAP = auto()
    WATER = auto()
    LAVA = auto()
    CHEST = auto()
    SHRINE = auto()


class RoomType(IntEnum):
    """Tipos especiais de sala garantidos."""
    NORMAL = auto()
    SPAWN = auto()
    REST = auto()
    SHOP = auto()
    ELITE = auto()
    BOSS = auto()
    TREASURE = auto()
    SECRET = auto()


class Rarity(IntEnum):
    """Raridade de itens, inimigos e eventos."""
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    EPIC = auto()
    LEGENDARY = auto()


class Stat(IntEnum):
    """Os 6 atributos clássicos de D&D."""
    STR = auto()   # Força
    DEX = auto()   # Destreza
    CON = auto()   # Constituição
    INT = auto()   # Inteligência
    WIS = auto()   # Sabedoria
    CHA = auto()   # Carisma


class EquipmentSlot(IntEnum):
    """Slots de equipamento do personagem."""
    MAIN_HAND = auto()
    OFF_HAND = auto()
    TWO_HANDS = auto()  # Ocupa ambas as mãos
    BODY = auto()
    HEAD = auto()
    FEET = auto()
    RING = auto()
    AMULET = auto()
    RELIC = auto()
