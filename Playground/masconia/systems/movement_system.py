"""
MovementSystem: gerencia movimento de entidades no grid.

Responsabilidades:
  • Verificar colisões com paredes e outras entidades
  • Pathfinding A* para IA
  • Cálculo de alcance de movimento (BFS/DFS)
  • Aplicação de custos de terreno (água, lava, armadilhas)

Por que separar movimento em system?
  → Centraliza regras de colisão em um único lugar.
  → Facilita adicionar terrenos difíceis ou teletransporte.
  → Pathfinding pode ser reutilizado por jogador (auto-explore) e IA.
"""
import heapq
from typing import List, Tuple, Optional, Set, Dict

from ecs.world import World, Event
from components.position import Position
from components.fighter import Fighter


class MovementSystem:
    """
    System de movimento e pathfinding.

    Attributes:
        world: Referência ao World ECS.
        dungeon_map: Referência ao mapa atual (para colisões).
    """

    def __init__(self):
        self.world: Optional[World] = None
        self.dungeon_map = None  # Será injetado pelo DungeonSystem

    def set_dungeon_map(self, dungeon_map):
        """Injeta referência ao mapa da masmorra."""
        self.dungeon_map = dungeon_map

    def can_move_to(self, x: int, y: int, mover_entity=None) -> bool:
        """
        Verifica se uma entidade pode mover-se para (x, y).

        Regras:
          • Tile deve ser passável (não parede, não porta fechada).
          • Não pode ter outra entidade bloqueante no tile.
        """
        if not self.dungeon_map:
            return False

        # Verifica tile
        if not self.dungeon_map.is_walkable(x, y):
            return False

        # Verifica colisão com outras entidades
        for entity in self.world.query(Position):
            if entity == mover_entity:
                continue
            pos = entity.get_component(Position)
            if pos.x == x and pos.y == y:
                # Entidades inimigas bloqueiam movimento
                if entity.has_tag("enemy") or entity.has_tag("player"):
                    return False

        return True

    def move_entity(self, entity, dx: int, dy: int) -> bool:
        """
        Tenta mover uma entidade por (dx, dy).
        Retorna True se conseguiu.
        """
        pos = entity.get_component(Position)
        fighter = entity.get_component(Fighter)

        if not pos:
            return False

        new_x = pos.x + dx
        new_y = pos.y + dy

        # Verifica se pode mover
        if not self.can_move_to(new_x, new_y, entity):
            return False

        # Verifica movimento restante
        if fighter and not fighter.can_move(abs(dx) + abs(dy)):
            return False

        # Executa movimento
        pos.x = new_x
        pos.y = new_y

        # Atualiza direção
        if dx > 0:
            pos.facing = "right"
        elif dx < 0:
            pos.facing = "left"
        elif dy > 0:
            pos.facing = "down"
        elif dy < 0:
            pos.facing = "up"

        # Gasta movimento
        if fighter:
            fighter.move(abs(dx) + abs(dy))

        # Trigger evento de movimento
        self.world.emit(Event("entity_moved", {
            "entity": entity,
            "from": (pos.x - dx, pos.y - dy),
            "to": (new_x, new_y)
        }))

        return True

    def get_movement_range(self, entity, max_distance: int) -> List[Tuple[int, int]]:
        """
        Retorna todos os tiles alcançáveis em até max_distance passos.
        Usa BFS.
        """
        pos = entity.get_component(Position)
        if not pos:
            return []

        visited = set()
        queue = [(pos.x, pos.y, 0)]
        reachable = []

        while queue:
            cx, cy, dist = queue.pop(0)
            if (cx, cy) in visited or dist > max_distance:
                continue
            visited.add((cx, cy))
            if dist > 0:
                reachable.append((cx, cy))

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if self.can_move_to(nx, ny, entity) and (nx, ny) not in visited:
                    queue.append((nx, ny, dist + 1))

        return reachable

    def get_attack_range(self, entity, attack_range: int = 1) -> List[Tuple[int, int]]:
        """
        Retorna tiles dentro do alcance de ataque (distância de Manhattan).
        Inclui tiles com inimigos.
        """
        pos = entity.get_component(Position)
        if not pos:
            return []

        tiles = []
        for dx in range(-attack_range, attack_range + 1):
            for dy in range(-attack_range, attack_range + 1):
                if abs(dx) + abs(dy) <= attack_range and (dx, dy) != (0, 0):
                    nx, ny = pos.x + dx, pos.y + dy
                    if self.dungeon_map and self.dungeon_map.in_bounds(nx, ny):
                        tiles.append((nx, ny))
        return tiles

    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int],
                  max_steps: int = 50) -> Optional[List[Tuple[int, int]]]:
        """
        Pathfinding A* no grid da masmorra.
        Retorna lista de tiles do caminho, ou None se não encontrou.
        """
        if not self.dungeon_map:
            return None

        if start == goal:
            return []

        # A*
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], int] = {start: 0}
        f_score: Dict[Tuple[int, int], int] = {start: self._heuristic(start, goal)}

        visited: Set[Tuple[int, int]] = set()

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            if current in visited:
                continue
            visited.add(current)

            if g_score.get(current, 0) >= max_steps:
                continue

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if not self.can_move_to(neighbor[0], neighbor[1]):
                    continue

                tentative_g = g_score[current] + 1
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return None  # Não encontrou caminho

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        """Heurística de Manhattan para A*."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _reconstruct_path(self, came_from: Dict, current: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Reconstrói o caminho do goal até o start."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path[1:]  # Remove o tile inicial

    def __repr__(self):
        return f"MovementSystem(map={self.dungeon_map is not None})"
