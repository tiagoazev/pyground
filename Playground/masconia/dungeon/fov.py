"""
Field of View (FOV) / Fog of War com Shadow Casting.

Algoritmo: Raycasting simples em 360 graus (otimizado).
Para cada ângulo, lança um raio até o limite de alcance.
Tiles opacos bloqueiam o raio.

Este é mais simples que shadow casting recursivo e funciona
corretamente para roguelikes em grid.
"""
import math
from typing import Set, Tuple, List, Optional
from dataclasses import dataclass, field

from dungeon.generator import DungeonMap
from utils.constants import TileType


@dataclass
class FOVMap:
    """Mapa de visibilidade e memória de exploração."""
    width: int
    height: int
    explored: Set[Tuple[int, int]] = field(default_factory=set)
    visible: Set[Tuple[int, int]] = field(default_factory=set)
    lit: Set[Tuple[int, int]] = field(default_factory=set)
    light_sources: List[Tuple[int, int, int]] = field(default_factory=list)

    def clear_visible(self):
        self.visible.clear()

    def compute_fov(self, origin_x: int, origin_y: int, radius: int,
                    dungeon: DungeonMap):
        """Calcula FOV com raycasting em 360 graus."""
        self.clear_visible()
        self._set_visible(origin_x, origin_y)

        # Lança raios em múltiplos ângulos
        num_rays = 360
        for i in range(num_rays):
            angle = (2 * math.pi * i) / num_rays
            self._cast_ray(origin_x, origin_y, angle, radius, dungeon)

        self._apply_light_sources(dungeon)

    def _cast_ray(self, ox: int, oy: int, angle: float, radius: int,
                  dungeon: DungeonMap):
        """Lança um raio em um ângulo específico."""
        dx = math.cos(angle)
        dy = math.sin(angle)

        for dist in range(1, radius + 1):
            x = int(ox + dx * dist)
            y = int(oy + dy * dist)

            if not dungeon.in_bounds(x, y):
                break

            self._set_visible(x, y)

            if dungeon.is_opaque(x, y):
                break  # Raio bloqueado

    def _set_visible(self, x: int, y: int):
        self.visible.add((x, y))
        self.explored.add((x, y))

    def _apply_light_sources(self, dungeon: DungeonMap):
        for lx, ly, radius in self.light_sources:
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        tx, ty = lx + dx, ly + dy
                        if dungeon.in_bounds(tx, ty):
                            self.lit.add((tx, ty))
                            if (tx, ty) in self.explored:
                                self.visible.add((tx, ty))

    def add_light_source(self, x: int, y: int, radius: int):
        self.light_sources.append((x, y, radius))

    def is_visible(self, x: int, y: int) -> bool:
        return (x, y) in self.visible

    def is_explored(self, x: int, y: int) -> bool:
        return (x, y) in self.explored

    def is_lit(self, x: int, y: int) -> bool:
        return (x, y) in self.lit

    def get_visibility(self, x: int, y: int) -> str:
        if self.is_visible(x, y):
            return "visible"
        if self.is_lit(x, y):
            return "lit"
        if self.is_explored(x, y):
            return "explored"
        return "unseen"

    def __repr__(self):
        return f"FOVMap({self.width}x{self.height}, explored={len(self.explored)}, visible={len(self.visible)})"
