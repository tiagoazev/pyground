"""
Sistema de Táticas de Combate: Cobertura, Flanking e Altura.

Regras implementadas:
  • Cobertura: entidades atrás de paredes/tiles opacos ganham +2 CA.
  • Cobertura Pesada: entidades em cantos ganham +4 CA.
  • Flanking: se dois aliados estão em lados opostos de um inimigo,
    ambos têm vantagem no ataque.
  • Altura: atacar de tile mais alto (escadas, plataformas) dá +1 de hit.
  • Backstab: atacar pelas costas (inimigo virado para outro lado) dá +2 de hit.

Por que separar táticas em módulo próprio?
  → Centraliza todas as regras de posicionamento em combate.
  → Facilita adicionar novas mecânicas (escuridão, terreno alto, etc.).
  → Permite IA usar táticas (buscar cobertura, flanquear).
"""
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

from ecs.world import World
from components.position import Position
from components.stats import Stats
from components.fighter import Fighter
from dungeon.generator import DungeonMap
from utils.constants import TileType, DamageType


@dataclass
class TacticalInfo:
    """Informações táticas sobre uma posição no mapa."""
    has_cover: bool = False
    cover_bonus: int = 0
    is_flanking: bool = False
    flanking_with: List = None
    height_advantage: int = 0
    is_backstab: bool = False
    in_melee: bool = False
    enemies_adjacent: int = 0
    allies_adjacent: int = 0

    def __post_init__(self):
        if self.flanking_with is None:
            self.flanking_with = []


class TacticsSystem:
    """
    System de táticas de combate.

    Calcula bônus e penalidades baseados em posicionamento.
    """

    def __init__(self, dungeon_map: DungeonMap = None):
        self.dungeon_map = dungeon_map

    def set_dungeon_map(self, dungeon_map: DungeonMap):
        self.dungeon_map = dungeon_map

    def get_tactical_info(self, attacker, target) -> TacticalInfo:
        """
        Calcula informações táticas para um ataque.
        Retorna TacticalInfo com todos os bônus/penalidades.
        """
        info = TacticalInfo()

        if not self.dungeon_map:
            return info

        attacker_pos = attacker.get_component(Position)
        target_pos = target.get_component(Position)

        if not attacker_pos or not target_pos:
            return info

        # Cobertura do alvo
        info.has_cover, info.cover_bonus = self._check_cover(attacker_pos, target_pos)

        # Flanking
        info.is_flanking, info.flanking_with = self._check_flanking(attacker, target)

        # Altura
        info.height_advantage = self._check_height(attacker_pos, target_pos)

        # Backstab
        info.is_backstab = self._check_backstab(attacker_pos, target_pos, target)

        # Adjacência
        info.in_melee = attacker_pos.distance_to(target_pos) <= 1
        info.enemies_adjacent = self._count_adjacent_enemies(target)
        info.allies_adjacent = self._count_adjacent_allies(target)

        return info

    def _check_cover(self, attacker_pos: Position, target_pos: Position) -> Tuple[bool, int]:
        """
        Verifica se o alvo tem cobertura contra o atacante.

        Algoritmo: raycasting de Bresenham do atacante ao alvo.
        Se algum tile opaco está no caminho (exceto o próprio alvo),
        o alvo tem cobertura.
        """
        if not self.dungeon_map:
            return False, 0

        # Linha de Bresenham
        line = self._bresenham_line(attacker_pos.x, attacker_pos.y, target_pos.x, target_pos.y)

        # Remove o primeiro (atacante) e último (alvo)
        line = line[1:-1]

        opaque_tiles = 0
        for x, y in line:
            if self.dungeon_map.is_opaque(x, y):
                opaque_tiles += 1

        if opaque_tiles >= 2:
            return True, 4  # Cobertura pesada
        elif opaque_tiles == 1:
            return True, 2  # Cobertura leve

        return False, 0

    def _check_flanking(self, attacker, target) -> Tuple[bool, List]:
        """
        Verifica se o atacante está flanqueando o alvo.

        Flanking: existe um aliado do atacante em posição oposta
        ao redor do alvo.
        """
        target_pos = target.get_component(Position)
        attacker_pos = attacker.get_component(Position)

        if not target_pos or not attacker_pos:
            return False, []

        # Direção do atacante em relação ao alvo
        dx = attacker_pos.x - target_pos.x
        dy = attacker_pos.y - target_pos.y

        # Posição oposta
        opposite = (target_pos.x - dx, target_pos.y - dy)

        # Tags do atacante
        is_player = attacker.has_tag("player")
        ally_tag = "player" if is_player else "enemy"

        flanking_with = []

        # Verifica se há um aliado na posição oposta
        for entity in self._get_entities_at(opposite[0], opposite[1]):
            if entity != attacker and entity != target:
                if entity.has_tag(ally_tag):
                    flanking_with.append(entity)

        # Também verifica diagonal oposta
        if not flanking_with:
            for odx, ody in [(-dy, dx), (dy, -dx)]:
                diag = (target_pos.x + odx, target_pos.y + ody)
                for entity in self._get_entities_at(diag[0], diag[1]):
                    if entity != attacker and entity != target:
                        if entity.has_tag(ally_tag):
                            flanking_with.append(entity)

        return len(flanking_with) > 0, flanking_with

    def _check_height(self, attacker_pos: Position, target_pos: Position) -> int:
        """
        Verifica vantagem de altura.

        Por enquanto simplificado: escadas dão +1 de altura.
        Em versão futura, teremos tiles com altura variável.
        """
        if not self.dungeon_map:
            return 0

        attacker_tile = self.dungeon_map.get_tile(attacker_pos.x, attacker_pos.y)
        target_tile = self.dungeon_map.get_tile(target_pos.x, target_pos.y)

        attacker_height = 1 if attacker_tile in (TileType.STAIRS_UP, TileType.STAIRS_DOWN) else 0
        target_height = 1 if target_tile in (TileType.STAIRS_UP, TileType.STAIRS_DOWN) else 0

        return max(0, attacker_height - target_height)

    def _check_backstab(self, attacker_pos: Position, target_pos: Position, target) -> bool:
        """
        Verifica se o ataque é pelas costas.

        Se o alvo está olhando para uma direção oposta ao atacante,
        é um backstab.
        """
        target_facing = target.get_component(Position)
        if not target_facing:
            return False

        dx = attacker_pos.x - target_pos.x
        dy = attacker_pos.y - target_pos.y

        # Normaliza para direção
        if abs(dx) > abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"

        # Direções opostas
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}

        return target_facing.facing == opposites.get(direction, "")

    def _count_adjacent_enemies(self, entity) -> int:
        """Conta inimigos adjacentes."""
        pos = entity.get_component(Position)
        if not pos:
            return 0

        tag = "enemy" if entity.has_tag("player") else "player"
        count = 0

        for other in self._get_entities_at(pos.x + 1, pos.y):
            if other.has_tag(tag): count += 1
        for other in self._get_entities_at(pos.x - 1, pos.y):
            if other.has_tag(tag): count += 1
        for other in self._get_entities_at(pos.x, pos.y + 1):
            if other.has_tag(tag): count += 1
        for other in self._get_entities_at(pos.x, pos.y - 1):
            if other.has_tag(tag): count += 1

        return count

    def _count_adjacent_allies(self, entity) -> int:
        """Conta aliados adjacentes."""
        pos = entity.get_component(Position)
        if not pos:
            return 0

        tag = "player" if entity.has_tag("player") else "enemy"
        count = 0

        for other in self._get_entities_at(pos.x + 1, pos.y):
            if other.has_tag(tag) and other != entity: count += 1
        for other in self._get_entities_at(pos.x - 1, pos.y):
            if other.has_tag(tag) and other != entity: count += 1
        for other in self._get_entities_at(pos.x, pos.y + 1):
            if other.has_tag(tag) and other != entity: count += 1
        for other in self._get_entities_at(pos.x, pos.y - 1):
            if other.has_tag(tag) and other != entity: count += 1

        return count

    def _get_entities_at(self, x: int, y: int) -> List:
        """Retorna entidades em uma posição."""
        # Simplificado — em versão completa, usaríamos query espacial
        return []

    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Algoritmo de Bresenham para linha de tiles."""
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            points.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return points

    def calculate_attack_modifiers(self, attacker, target) -> Dict[str, any]:
        """
        Calcula todos os modificadores táticos para um ataque.
        Retorna dict com bônus/penalidades.
        """
        info = self.get_tactical_info(attacker, target)

        modifiers = {
            "hit_bonus": 0,
            "damage_bonus": 0,
            "advantage": False,
            "disadvantage": False,
            "ca_bonus": 0,
            "info": info,
        }

        # Cobertura do alvo → penalidade no hit
        if info.has_cover:
            modifiers["hit_bonus"] -= info.cover_bonus
            modifiers["ca_bonus"] += info.cover_bonus

        # Flanking → vantagem
        if info.is_flanking:
            modifiers["advantage"] = True

        # Altura → bônus de hit
        if info.height_advantage > 0:
            modifiers["hit_bonus"] += info.height_advantage

        # Backstab → bônus de hit
        if info.is_backstab:
            modifiers["hit_bonus"] += 2
            modifiers["damage_bonus"] += 2

        return modifiers

    def find_best_cover(self, entity, enemies: List) -> Optional[Tuple[int, int]]:
        """
        Encontra o melhor tile de cobertura para a entidade.
        Útil para IA defensiva.

        Critérios:
          1. Tile com cobertura contra o máximo de inimigos
          2. Distância do inimigo mais próximo
          3. Proximidade da posição atual
        """
        pos = entity.get_component(Position)
        if not pos or not self.dungeon_map:
            return None

        best_tile = None
        best_score = -999

        # Busca em raio de movimento
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                tx, ty = pos.x + dx, pos.y + dy

                if not self.dungeon_map.is_walkable(tx, ty):
                    continue

                # Calcula score
                score = 0

                # Cobertura contra cada inimigo
                for enemy in enemies:
                    epos = enemy.get_component(Position)
                    if epos:
                        temp_pos = Position(x=tx, y=ty)
                        has_cover, bonus = self._check_cover(epos, temp_pos)
                        if has_cover:
                            score += bonus * 10

                # Penalidade por distância do inimigo mais próximo
                min_dist = min(
                    (abs(tx - e.get_component(Position).x) + abs(ty - e.get_component(Position).y))
                    for e in enemies if e.get_component(Position)
                ) if enemies else 999
                score += min_dist * 2

                # Penalidade por distância da posição atual
                score -= (abs(dx) + abs(dy)) * 3

                if score > best_score:
                    best_score = score
                    best_tile = (tx, ty)

        return best_tile

    def __repr__(self):
        return f"TacticsSystem(dungeon={self.dungeon_map is not None})"
