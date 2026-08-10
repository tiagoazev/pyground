"""
Componente de posição no grid da masmorra.

Todas as entidades que existem no espaço do jogo precisam deste componente.
A posição é em tiles (inteiros), não pixels — a conversão para pixels
é feita no RenderSystem (tile * TILE_SIZE).

Por que separar Position de Renderable?
  → Uma entidade pode ter posição mas não ser visível (invisível, fora de FOV).
  → Renderable pode ter offset de animação sem afetar a posição lógica.
"""
from dataclasses import dataclass


@dataclass
class Position:
    """
    Posição em tiles no grid da masmorra.

    Attributes:
        x, y: Coordenadas no grid (0,0 é canto superior esquerdo).
        facing: Direção que a entidade está olhando (para animação de sprite).
    """
    x: int = 0
    y: int = 0
    facing: str = "down"  # up, down, left, right

    def distance_to(self, other: "Position") -> int:
        """Distância de Manhattan (grid-based, usada para pathfinding e range)."""
        return abs(self.x - other.x) + abs(self.y - other.y)

    def distance_euclidean(self, other: "Position") -> float:
        """Distância euclidiana (para efeitos circulares de área)."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y
        return False

    def __repr__(self):
        return f"Position({self.x}, {self.y})"
