"""
Componentes ECS de Masconia.

Cada componente é um dataclass pura — apenas dados, zero lógica.
A lógica fica nos Systems correspondentes.
"""
from components.position import Position
from components.renderable import Renderable
from components.stats import Stats
from components.inventory import Inventory
from components.ai import AI
from components.fighter import Fighter

__all__ = ["Position", "Renderable", "Stats", "Inventory", "AI", "Fighter"]
