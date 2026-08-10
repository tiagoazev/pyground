"""
DungeonGenerator: geração procedural avançada de masmorras.

Algoritmo:
  1. BSP (Binary Space Partitioning) para layout estruturado
  2. Salas retangulares em cada folha da BSP
  3. Corredores L-shaped com variação (zig-zag, direto)
  4. Salas especiais garantidas: spawn, descanso, loja, elite, boss, tesouro, SECRETA
  5. Preenchimento procedural: inimigos, itens, armadilhas, decoração
  6. Terrenos difíceis: água, lava, cristais (custo de movimento diferente)
  7. Portas (abertas/fechadas) entre salas e corredores
  8. Iluminação: tochas, cristais luminosos, lava
  9. Seed compartilhável para Daily Challenge

Novidades desta versão:
  • Salas secretas: parede falsa que pode ser revelada (inspecionar ou atacar)
  • Armadilhas múltiplas: espinhos, poço, dardo, explosão
  • Terrenos com custo de movimento: água (2x), lava (3x + dano)
  • Decoración: pilastras, estátuas, esqueletos decorativos
  • Portas que bloqueiam linha de visão quando fechadas
  • Sistema de dificuldade escalonada por andar
"""
import random
from typing import List, Tuple, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import IntEnum

from utils.constants import TileType, RoomType, DamageType
from config.settings import MAX_FLOOR


class TrapType(IntEnum):
    """Tipos de armadilhas."""
    SPIKES = 1       # Dano de perfuração
    PIT = 2          # Dano de queda + stun
    DART = 3         # Dano de perfuração + poison
    EXPLOSION = 4    # Dano de fogo em área
    CRYSTAL_SHARD = 5 # Dano de força (cavernas)
    LAVA_VENT = 6    # Dano de fogo + queimadura (covil)


class TerrainModifier(IntEnum):
    """Modificadores de terreno que afetam movimento."""
    NONE = 0
    WATER = 1        # Custo 2x, sem fogo
    LAVA = 2         # Custo 3x, dano de fogo por turno
    ICE = 3          # Chance de escorregar (move extra 1 tile)
    MUD = 4          # Custo 2x
    CRYSTAL_FIELD = 5 # Custo 1.5x, dano de força ao entrar


@dataclass
class Trap:
    """Dados de uma armadilha em um tile."""
    trap_type: TrapType
    damage: str = "1d6"
    damage_type: str = "piercing"
    difficulty: int = 10  # DC para detectar/desarmar
    triggered: bool = False
    detected: bool = False
    disarmed: bool = False
    one_shot: bool = True  # Se True, só dispara uma vez


@dataclass
class Room:
    """Representa uma sala na masmorra."""
    x: int
    y: int
    width: int
    height: int
    room_type: RoomType = RoomType.NORMAL
    biome: str = "crypt"
    enemies: List[Dict] = field(default_factory=list)
    items: List[Dict] = field(default_factory=list)
    traps: List[Tuple[int, int, Trap]] = field(default_factory=list)
    decorations: List[Tuple[int, int, str]] = field(default_factory=list)
    connections: List[int] = field(default_factory=list)
    is_secret: bool = False
    secret_entrance: Optional[Tuple[int, int]] = None

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def tiles(self) -> List[Tuple[int, int]]:
        tiles = []
        for dx in range(self.width):
            for dy in range(self.height):
                tiles.append((self.x + dx, self.y + dy))
        return tiles

    @property
    def border_tiles(self) -> List[Tuple[int, int]]:
        """Tiles na borda da sala (para portas e armadilhas)."""
        borders = []
        for dx in range(self.width):
            borders.append((self.x + dx, self.y))
            borders.append((self.x + dx, self.y + self.height - 1))
        for dy in range(1, self.height - 1):
            borders.append((self.x, self.y + dy))
            borders.append((self.x + self.width - 1, self.y + dy))
        return borders

    @property
    def inner_tiles(self) -> List[Tuple[int, int]]:
        """Tiles internos (não na borda)."""
        inner = []
        for dx in range(1, self.width - 1):
            for dy in range(1, self.height - 1):
                inner.append((self.x + dx, self.y + dy))
        return inner

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def intersects(self, other: "Room", margin: int = 1) -> bool:
        return not (
            self.x + self.width + margin < other.x or
            other.x + other.width + margin < self.x or
            self.y + self.height + margin < other.y or
            other.y + other.height + margin < self.y
        )

    def __repr__(self):
        return f"Room({self.x},{self.y} {self.width}x{self.height}, {self.room_type.name}, secret={self.is_secret})"


class DungeonMap:
    """
    Representação completa do mapa da masmorra.

    Attributes:
        width, height: Dimensões em tiles.
        tiles: Matriz de TileType.
        terrain: Matriz de TerrainModifier (custo de movimento).
        traps: Dict (x,y) -> Trap.
        rooms: Lista de salas.
        biome: Bioma atual.
        floor: Andar atual.
        seed: Seed usada.
        light_sources: Lista de (x, y, radius, color).
    """

    def __init__(self, width: int = 60, height: int = 40):
        self.width = width
        self.height = height
        self.tiles: List[List[TileType]] = [
            [TileType.WALL for _ in range(width)] for _ in range(height)
        ]
        self.terrain: List[List[TerrainModifier]] = [
            [TerrainModifier.NONE for _ in range(width)] for _ in range(height)
        ]
        self.traps: Dict[Tuple[int, int], Trap] = {}
        self.rooms: List[Room] = []
        self.biome = "crypt"
        self.floor = 1
        self.seed = 0
        self._rng = random.Random()
        self.light_sources: List[Tuple[int, int, int, Tuple[int, int, int]]] = []
        self._item_spawns: List[Tuple[int, int, Dict]] = []
        self._enemy_spawns: List[Tuple[int, int, str, bool]] = []

    def set_seed(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_tile(self, x: int, y: int) -> TileType:
        if self.in_bounds(x, y):
            return self.tiles[y][x]
        return TileType.WALL

    def set_tile(self, x: int, y: int, tile_type: TileType):
        if self.in_bounds(x, y):
            self.tiles[y][x] = tile_type

    def get_terrain(self, x: int, y: int) -> TerrainModifier:
        if self.in_bounds(x, y):
            return self.terrain[y][x]
        return TerrainModifier.NONE

    def set_terrain(self, x: int, y: int, terrain: TerrainModifier):
        if self.in_bounds(x, y):
            self.terrain[y][x] = terrain

    def is_walkable(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        return tile in (TileType.FLOOR, TileType.DOOR_OPEN, TileType.STAIRS_DOWN,
                        TileType.STAIRS_UP, TileType.CHEST, TileType.SHRINE,
                        TileType.WATER, TileType.LAVA)

    def is_opaque(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        return tile in (TileType.WALL, TileType.DOOR, TileType.TRAP)

    def get_movement_cost(self, x: int, y: int) -> int:
        """Retorna o custo de movimento para um tile."""
        terrain = self.get_terrain(x, y)
        costs = {
            TerrainModifier.NONE: 1,
            TerrainModifier.WATER: 2,
            TerrainModifier.LAVA: 3,
            TerrainModifier.ICE: 1,
            TerrainModifier.MUD: 2,
            TerrainModifier.CRYSTAL_FIELD: 2,
        }
        return costs.get(terrain, 1)

    def get_trap_at(self, x: int, y: int) -> Optional[Trap]:
        return self.traps.get((x, y))

    def add_trap(self, x: int, y: int, trap: Trap):
        self.traps[(x, y)] = trap
        self.set_tile(x, y, TileType.TRAP)

    def trigger_trap(self, x: int, y: int) -> Optional[Trap]:
        """Dispara uma armadilha. Retorna o trap ou None."""
        trap = self.traps.get((x, y))
        if trap and not trap.triggered and not trap.disarmed:
            trap.triggered = True
            if trap.one_shot:
                # Remove do mapa visual
                self.set_tile(x, y, TileType.FLOOR)
            return trap
        return None

    def detect_trap(self, x: int, y: int, perception_bonus: int = 0) -> bool:
        """Tenta detectar uma armadilha. Retorna True se detectou."""
        trap = self.traps.get((x, y))
        if trap and not trap.detected and not trap.disarmed:
            # d20 + perception vs DC
            roll = self._rng.randint(1, 20) + perception_bonus
            if roll >= trap.difficulty:
                trap.detected = True
                return True
        return False

    def get_room_at(self, x: int, y: int) -> Optional[Room]:
        for room in self.rooms:
            if room.contains(x, y):
                return room
        return None

    def find_empty_tile(self, room: Room = None, avoid_traps: bool = True,
                        avoid_terrain: bool = True) -> Optional[Tuple[int, int]]:
        """Encontra um tile de chão vazio."""
        candidates = []
        search_area = room.inner_tiles if room else [
            (x, y) for y in range(self.height) for x in range(self.width)
            if self.tiles[y][x] == TileType.FLOOR
        ]

        for tx, ty in search_area:
            if avoid_traps and (tx, ty) in self.traps:
                continue
            if avoid_terrain and self.get_terrain(tx, ty) != TerrainModifier.NONE:
                continue
            candidates.append((tx, ty))

        if candidates:
            return self._rng.choice(candidates)
        return None

    def find_wall_tile(self, room: Room = None) -> Optional[Tuple[int, int]]:
        """Encontra um tile de parede."""
        candidates = room.border_tiles if room else [
            (x, y) for y in range(self.height) for x in range(self.width)
            if self.tiles[y][x] == TileType.WALL
        ]
        if candidates:
            return self._rng.choice(candidates)
        return None

    def get_connected_rooms(self, room_idx: int) -> List[int]:
        """Retorna índices das salas conectadas à sala especificada."""
        if 0 <= room_idx < len(self.rooms):
            return self.rooms[room_idx].connections
        return []

    def __repr__(self):
        return f"DungeonMap({self.width}x{self.height}, {len(self.rooms)} rooms, {len(self.traps)} traps, floor={self.floor})"


class DungeonGenerator:
    """
    Gerador procedural avançado de masmorras.

    Suporta:
      • BSP para layout estruturado
      • Salas secretas com paredes falsas
      • Armadilhas múltiplas com detecção
      • Terrenos difíceis (água, lava, gelo)
      • Portas entre salas
      • Iluminação por bioma
      • Dificuldade escalonada por andar
    """

    def __init__(self, biome_data: Dict[str, Any] = None):
        self.biome_data = biome_data or {}
        self._rng = random.Random()

    def generate(self, floor: int, seed: Optional[int] = None,
                 biome: str = "crypt") -> DungeonMap:
        """Gera uma masmorra completa."""
        biome_cfg = self.biome_data.get(biome, {})

        room_count_range = biome_cfg.get("room_count", [8, 12])
        room_size = biome_cfg.get("room_size", {"min": [4, 4], "max": [8, 8]})

        # Mapa cresce com o andar
        map_width = 45 + floor * 3
        map_height = 30 + floor * 2

        if seed is None:
            seed = random.randint(0, 999999)
        self._rng = random.Random(seed)

        dungeon = DungeonMap(map_width, map_height)
        dungeon.set_seed(seed)
        dungeon.floor = floor
        dungeon.biome = biome

        # 1. Gera salas com BSP
        num_rooms = self._rng.randint(*room_count_range)
        rooms = self._generate_rooms_bsp(dungeon, num_rooms, room_size)
        dungeon.rooms = rooms

        # 2. Conecta salas
        self._connect_rooms(dungeon, rooms)

        # 3. Marca salas especiais
        self._assign_special_rooms(dungeon, rooms)

        # 4. Gera salas secretas
        self._generate_secret_rooms(dungeon, rooms)

        # 5. Preenche terrenos difíceis
        self._apply_terrain(dungeon, biome)

        # 6. Coloca armadilhas
        self._place_traps(dungeon, rooms, floor)

        # 7. Coloca decoração
        self._place_decorations(dungeon, rooms, biome)

        # 8. Preenche conteúdo (inimigos, itens)
        self._populate_rooms(dungeon, rooms, biome_cfg, floor)

        # 9. Coloca escadas
        self._place_stairs(dungeon, rooms)

        # 10. Iluminação
        self._place_lighting(dungeon, rooms, biome)

        return dungeon

    def _generate_rooms_bsp(self, dungeon: DungeonMap, num_rooms: int,
                            room_size: Dict) -> List[Room]:
        """Gera salas usando BSP para layout mais estruturado."""
        rooms = []
        min_w, min_h = room_size["min"]
        max_w, max_h = room_size["max"]

        # BSP simples: divide o mapa recursivamente
        partitions = [(1, 1, dungeon.width - 2, dungeon.height - 2)]

        for _ in range(num_rooms - 1):
            if not partitions:
                break
            # Escolhe a maior partição
            partitions.sort(key=lambda p: p[2] * p[3], reverse=True)
            px, py, pw, ph = partitions.pop(0)

            # Decide se divide horizontal ou vertical
            if pw > ph and pw > max_w * 2:
                # Divide verticalmente
                split = self._rng.randint(pw // 3, pw * 2 // 3)
                partitions.append((px, py, split, ph))
                partitions.append((px + split, py, pw - split, ph))
            elif ph > max_h * 2:
                # Divide horizontalmente
                split = self._rng.randint(ph // 3, ph * 2 // 3)
                partitions.append((px, py, pw, split))
                partitions.append((px, py + split, pw, ph - split))
            else:
                # Partição muito pequena, guarda de volta
                partitions.append((px, py, pw, ph))
                break

        # Cria salas em cada partição
        for px, py, pw, ph in partitions:
            if len(rooms) >= num_rooms:
                break

            w = self._rng.randint(min_w, min(max_w, pw - 2))
            h = self._rng.randint(min_h, min(max_h, ph - 2))
            x = px + self._rng.randint(1, max(1, pw - w - 1))
            y = py + self._rng.randint(1, max(1, ph - h - 1))

            room = Room(x, y, w, h)

            # Verifica sobreposição
            overlaps = any(room.intersects(r, margin=2) for r in rooms)
            if not overlaps:
                rooms.append(room)
                # Carve
                for dx in range(w):
                    for dy in range(h):
                        dungeon.set_tile(x + dx, y + dy, TileType.FLOOR)

        return rooms

    def _connect_rooms(self, dungeon: DungeonMap, rooms: List[Room]):
        """Conecta salas com corredores, incluindo portas."""
        for i in range(1, len(rooms)):
            prev = rooms[i - 1]
            curr = rooms[i]

            c1 = prev.center
            c2 = curr.center

            # Corredor com variação
            if self._rng.random() < 0.3:
                # Zig-zag
                self._create_zigzag_corridor(dungeon, c1, c2)
            else:
                # L-shaped
                if self._rng.random() < 0.5:
                    self._create_h_corridor(dungeon, c1[0], c2[0], c1[1])
                    self._create_v_corridor(dungeon, c1[1], c2[1], c2[0])
                else:
                    self._create_v_corridor(dungeon, c1[1], c2[1], c1[0])
                    self._create_h_corridor(dungeon, c1[0], c2[0], c2[1])

            # Porta na conexão (30% chance)
            if self._rng.random() < 0.3:
                self._place_door_between(dungeon, prev, curr)

            prev.connections.append(i)
            curr.connections.append(i - 1)

    def _create_h_corridor(self, dungeon: DungeonMap, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            dungeon.set_tile(x, y, TileType.FLOOR)

    def _create_v_corridor(self, dungeon: DungeonMap, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            dungeon.set_tile(x, y, TileType.FLOOR)

    def _create_zigzag_corridor(self, dungeon: DungeonMap,
                                 start: Tuple[int, int], end: Tuple[int, int]):
        """Corredor em zigue-zague com 2-3 segmentos."""
        x1, y1 = start
        x2, y2 = end

        # Ponto intermediário
        mid_x = (x1 + x2) // 2 + self._rng.randint(-3, 3)
        mid_y = (y1 + y2) // 2 + self._rng.randint(-3, 3)
        mid_x = max(1, min(mid_x, dungeon.width - 2))
        mid_y = max(1, min(mid_y, dungeon.height - 2))

        self._create_h_corridor(dungeon, x1, mid_x, y1)
        self._create_v_corridor(dungeon, y1, mid_y, mid_x)
        self._create_h_corridor(dungeon, mid_x, x2, mid_y)
        self._create_v_corridor(dungeon, mid_y, y2, x2)

    def _place_door_between(self, dungeon: DungeonMap, room1: Room, room2: Room):
        """Coloca uma porta entre duas salas."""
        # Encontra tiles adjacentes entre as salas
        for tx, ty in room1.border_tiles:
            if room2.contains(tx + 1, ty) or room2.contains(tx - 1, ty) or                room2.contains(tx, ty + 1) or room2.contains(tx, ty - 1):
                if dungeon.get_tile(tx, ty) == TileType.FLOOR:
                    # 50% porta fechada, 50% aberta
                    door_type = TileType.DOOR if self._rng.random() < 0.5 else TileType.DOOR_OPEN
                    dungeon.set_tile(tx, ty, door_type)
                    return

    def _assign_special_rooms(self, dungeon: DungeonMap, rooms: List[Room]):
        """Marca salas especiais."""
        if not rooms:
            return

        rooms[0].room_type = RoomType.SPAWN

        if len(rooms) >= 3:
            rooms[min(2, len(rooms) - 1)].room_type = RoomType.SHOP

        if len(rooms) >= 5:
            rooms[len(rooms) // 2].room_type = RoomType.REST

        if len(rooms) >= 7:
            rooms[len(rooms) * 3 // 4].room_type = RoomType.ELITE

        rooms[-1].room_type = RoomType.BOSS

        if len(rooms) >= 4:
            treasure_idx = self._rng.randint(1, len(rooms) - 2)
            rooms[treasure_idx].room_type = RoomType.TREASURE

    def _generate_secret_rooms(self, dungeon: DungeonMap, rooms: List[Room]):
        """Gera salas secretas conectadas a salas existentes."""
        if len(rooms) < 4:
            return

        num_secret = self._rng.randint(1, min(2, len(rooms) // 3))

        for _ in range(num_secret):
            # Escolhe uma sala para conectar
            parent = self._rng.choice(rooms[:-1])  # Não conecta ao boss

            # Tenta criar sala secreta adjacente
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            self._rng.shuffle(directions)

            for dx, dy in directions:
                # Tenta colocar sala secreta do outro lado de uma parede
                sw = self._rng.randint(3, 5)
                sh = self._rng.randint(3, 5)

                if dx == 1:
                    sx = parent.x + parent.width + 1
                    sy = parent.y + self._rng.randint(0, max(0, parent.height - sh))
                elif dx == -1:
                    sx = parent.x - sw - 1
                    sy = parent.y + self._rng.randint(0, max(0, parent.height - sh))
                elif dy == 1:
                    sx = parent.x + self._rng.randint(0, max(0, parent.width - sw))
                    sy = parent.y + parent.height + 1
                else:
                    sx = parent.x + self._rng.randint(0, max(0, parent.width - sw))
                    sy = parent.y - sh - 1

                # Verifica se cabe
                secret = Room(sx, sy, sw, sh, is_secret=True)
                if sx > 0 and sy > 0 and sx + sw < dungeon.width and sy + sh < dungeon.height:
                    overlaps = any(secret.intersects(r, margin=1) for r in rooms)
                    if not overlaps:
                        # Carve sala secreta
                        for cx in range(sw):
                            for cy in range(sh):
                                dungeon.set_tile(sx + cx, sy + cy, TileType.FLOOR)

                        # Cria parede falsa na conexão
                        if dx == 1:
                            wall_x = parent.x + parent.width
                            wall_y = parent.center[1]
                        elif dx == -1:
                            wall_x = parent.x - 1
                            wall_y = parent.center[1]
                        elif dy == 1:
                            wall_x = parent.center[0]
                            wall_y = parent.y + parent.height
                        else:
                            wall_x = parent.center[0]
                            wall_y = parent.y - 1

                        if dungeon.in_bounds(wall_x, wall_y):
                            dungeon.set_tile(wall_x, wall_y, TileType.WALL)
                            secret.secret_entrance = (wall_x, wall_y)

                        rooms.append(secret)
                        break

    def _apply_terrain(self, dungeon: DungeonMap, biome: str):
        """Aplica terrenos difíceis baseado no bioma."""
        terrain_chances = {
            "crypt": [(TerrainModifier.NONE, 0.9), (TerrainModifier.MUD, 0.1)],
            "crystal_caverns": [
                (TerrainModifier.NONE, 0.7),
                (TerrainModifier.WATER, 0.15),
                (TerrainModifier.CRYSTAL_FIELD, 0.15)
            ],
            "dragon_lair": [
                (TerrainModifier.NONE, 0.6),
                (TerrainModifier.LAVA, 0.25),
                (TerrainModifier.MUD, 0.15)
            ],
        }

        chances = terrain_chances.get(biome, [(TerrainModifier.NONE, 1.0)])

        for y in range(dungeon.height):
            for x in range(dungeon.width):
                if dungeon.get_tile(x, y) == TileType.FLOOR:
                    roll = self._rng.random()
                    cumulative = 0
                    for terrain, chance in chances:
                        cumulative += chance
                        if roll < cumulative:
                            if terrain != TerrainModifier.NONE:
                                dungeon.set_terrain(x, y, terrain)
                                # Tiles especiais visuais
                                if terrain == TerrainModifier.LAVA:
                                    dungeon.set_tile(x, y, TileType.LAVA)
                                elif terrain == TerrainModifier.WATER:
                                    dungeon.set_tile(x, y, TileType.WATER)
                            break

    def _place_traps(self, dungeon: DungeonMap, rooms: List[Room], floor: int):
        """Coloca armadilhas em salas e corredores."""
        # Garante pelo menos 1 armadilha no mapa
        min_traps = max(1, floor // 2)
        # Armadilhas por bioma
        trap_types_by_biome = {
            "crypt": [TrapType.SPIKES, TrapType.PIT, TrapType.DART],
            "crystal_caverns": [TrapType.SPIKES, TrapType.CRYSTAL_SHARD, TrapType.EXPLOSION],
            "dragon_lair": [TrapType.EXPLOSION, TrapType.LAVA_VENT, TrapType.PIT],
        }

        available_traps = trap_types_by_biome.get(dungeon.biome, [TrapType.SPIKES])

        # Dificuldade aumenta com o andar
        base_dc = 10 + floor // 3

        for room in rooms:
            if room.room_type in (RoomType.SPAWN, RoomType.REST):
                continue  # Sem armadilhas em spawn e descanso

            # Chance de armadilha por sala
            trap_chance = 0.15 + (floor * 0.02)
            if room.room_type == RoomType.ELITE:
                trap_chance += 0.2

            if self._rng.random() < trap_chance:
                tile = dungeon.find_empty_tile(room)
                if tile:
                    trap_type = self._rng.choice(available_traps)
                    trap = self._create_trap(trap_type, base_dc)
                    dungeon.add_trap(tile[0], tile[1], trap)
                    room.traps.append((tile[0], tile[1], trap))

        # Armadilhas em corredores (garante pelo menos 1)
        corridor_traps = max(1, floor // 2)
        for _ in range(corridor_traps):
            x = self._rng.randint(1, dungeon.width - 2)
            y = self._rng.randint(1, dungeon.height - 2)
            if dungeon.get_tile(x, y) == TileType.FLOOR and (x, y) not in dungeon.traps:
                trap_type = self._rng.choice(available_traps)
                trap = self._create_trap(trap_type, base_dc)
                dungeon.add_trap(x, y, trap)

    def _create_trap(self, trap_type: TrapType, dc: int) -> Trap:
        """Cria uma armadilha com stats apropriados."""
        configs = {
            TrapType.SPIKES: ("2d6", "piercing", 12),
            TrapType.PIT: ("2d8", "bludgeoning", 10),
            TrapType.DART: ("1d6", "piercing", 14),
            TrapType.EXPLOSION: ("3d6", "fire", 13),
            TrapType.CRYSTAL_SHARD: ("2d6", "force", 12),
            TrapType.LAVA_VENT: ("2d8", "fire", 15),
        }
        dmg, dtype, base_dc = configs.get(trap_type, ("1d6", "piercing", 10))
        return Trap(
            trap_type=trap_type,
            damage=dmg,
            damage_type=dtype,
            difficulty=dc + base_dc - 10
        )

    def _place_decorations(self, dungeon: DungeonMap, rooms: List[Room], biome: str):
        """Coloca decoração ambiental nas salas."""
        decorations_by_biome = {
            "crypt": ["skeleton_pile", "broken_pillar", "cobweb", "tombstone"],
            "crystal_caverns": ["crystal_cluster", "stalagmite", "glowing_moss", "geode"],
            "dragon_lair": ["bone_pile", "melted_armor", "gold_coins", "scorch_mark"],
        }

        decos = decorations_by_biome.get(biome, ["rubble"])

        for room in rooms:
            if room.room_type == RoomType.SPAWN:
                continue

            num_deco = self._rng.randint(0, 3)
            for _ in range(num_deco):
                tile = dungeon.find_empty_tile(room)
                if tile:
                    deco = self._rng.choice(decos)
                    room.decorations.append((tile[0], tile[1], deco))

    def _populate_rooms(self, dungeon: DungeonMap, rooms: List[Room],
                        biome_cfg: Dict, floor: int):
        """Preenche salas com inimigos e itens."""
        for room in rooms:
            if room.room_type == RoomType.SPAWN:
                continue

            # Dificuldade de spawn
            if room.room_type == RoomType.ELITE:
                num_enemies = self._rng.randint(2, 4)
                difficulty = "elite"
            elif room.room_type == RoomType.BOSS:
                num_enemies = 1
                difficulty = "boss"
            elif room.room_type == RoomType.TREASURE:
                num_enemies = self._rng.randint(0, 2)
                difficulty = "normal"
            else:
                # Escala com andar
                base_enemies = 1 + floor // 5
                num_enemies = self._rng.randint(base_enemies, base_enemies + 2)
                difficulty = "normal"

            for _ in range(num_enemies):
                tile = dungeon.find_empty_tile(room)
                if tile:
                    room.enemies.append({"x": tile[0], "y": tile[1], "difficulty": difficulty})

            # Itens
            if room.room_type in (RoomType.TREASURE, RoomType.SHOP):
                num_items = self._rng.randint(1, 3)
                for _ in range(num_items):
                    tile = dungeon.find_empty_tile(room)
                    if tile:
                        room.items.append({"x": tile[0], "y": tile[1]})

            # Baú na sala de tesouro
            if room.room_type == RoomType.TREASURE:
                tile = dungeon.find_empty_tile(room)
                if tile:
                    dungeon.set_tile(tile[0], tile[1], TileType.CHEST)

            # Shrine na sala de descanso
            if room.room_type == RoomType.REST:
                tile = dungeon.find_empty_tile(room)
                if tile:
                    dungeon.set_tile(tile[0], tile[1], TileType.SHRINE)

    def _place_stairs(self, dungeon: DungeonMap, rooms: List[Room]):
        """Coloca escadas."""
        if len(rooms) >= 2:
            spawn = rooms[0]
            tile = dungeon.find_empty_tile(spawn)
            if tile:
                dungeon.set_tile(tile[0], tile[1], TileType.STAIRS_UP)

            boss = rooms[-1]
            tile = dungeon.find_empty_tile(boss)
            if tile:
                dungeon.set_tile(tile[0], tile[1], TileType.STAIRS_DOWN)

    def _place_lighting(self, dungeon: DungeonMap, rooms: List[Room], biome: str):
        """Coloca fontes de luz por bioma."""
        colors = {
            "crypt": (120, 100, 60),      # Luz amarelada de tochas
            "crystal_caverns": (100, 200, 220),  # Luz azul de cristais
            "dragon_lair": (200, 80, 30),  # Luz laranja de lava/fogo
        }
        color = colors.get(biome, (200, 200, 200))

        for room in rooms:
            if room.room_type == RoomType.SPAWN:
                continue

            # 1-2 fontes de luz por sala
            num_lights = self._rng.randint(1, 2)
            for _ in range(num_lights):
                tile = dungeon.find_empty_tile(room)
                if tile:
                    radius = self._rng.randint(3, 5)
                    dungeon.light_sources.append((tile[0], tile[1], radius, color))

    def generate_daily(self, date_seed: int) -> DungeonMap:
        """Gera masmorra do Daily Challenge."""
        return self.generate(floor=1, seed=date_seed, biome="crypt")

    def __repr__(self):
        return f"DungeonGenerator(biomes={list(self.biome_data.keys())})"
