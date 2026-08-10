"""
Systems ECS de Masconia.

Cada system contém a lógica que opera sobre entidades com componentes específicos.
"""
from systems.render_system import RenderSystem
from systems.movement_system import MovementSystem
from systems.ai_system import AISystem

__all__ = ["RenderSystem", "MovementSystem", "AISystem"]
