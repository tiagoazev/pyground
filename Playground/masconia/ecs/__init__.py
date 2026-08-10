"""
Núcleo ECS de Masconia.

ECS (Entity-Component-System) separa:
  • Dado (Component)
  • Identidade (Entity)
  • Comportamento (System)
  • Container (World)

Isso permite adicionar/remover comportamentos em runtime sem herança complexa.
"""
from ecs.entity import Entity
from ecs.world import World, Event

__all__ = ["Entity", "World", "Event"]
