"""
Entidade no padrão ECS (Entity-Component-System).

Uma entidade é apenas um container de ID + conjunto de componentes.
Não possui lógica própria — todo comportamento vem dos Systems.

Por que ECS?
  → Composição sobre herança: um inimigo pode ter "Flying" + "Poisonous"
    sem criar 50 subclasses.
  → Cache-friendly: systems iteram arrays de componentes homogêneos.
  → Flexibilidade: adicionar/remover comportamentos em runtime (buffs, curses).
"""
from typing import Dict, Type, Optional, Any


class Entity:
    """
    Entidade genérica do jogo.

    Attributes:
        uid: Identificador único (incremental).
        name: Nome legível para debug/logs.
        components: Dicionário tipo→instância de componente.
        tags: Conjunto de strings para filtros rápidos ("player", "enemy", "flying").
        active: Se False, a entidade é ignorada por todos os systems.
    """
    _next_uid = 0

    def __init__(self, name: str = "Entity"):
        Entity._next_uid += 1
        self.uid = Entity._next_uid
        self.name = name
        self.components: Dict[Type, Any] = {}
        self.tags: set = set()
        self.active = True
        self._destroyed = False

    def add_component(self, component) -> "Entity":
        """Adiciona um componente. Sobrescreve se já existir do mesmo tipo."""
        self.components[type(component)] = component
        return self

    def get_component(self, component_type: Type) -> Optional[Any]:
        """Retorna o componente do tipo solicitado, ou None."""
        return self.components.get(component_type)

    def has_component(self, component_type: Type) -> bool:
        return component_type in self.components

    def remove_component(self, component_type: Type) -> bool:
        """Remove um componente. Retorna True se existia."""
        if component_type in self.components:
            del self.components[component_type]
            return True
        return False

    def add_tag(self, tag: str) -> "Entity":
        self.tags.add(tag)
        return self

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def remove_tag(self, tag: str) -> bool:
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def destroy(self):
        """Marca a entidade para remoção no final do frame."""
        self._destroyed = True
        self.active = False

    @property
    def is_destroyed(self) -> bool:
        return self._destroyed

    def __repr__(self):
        comps = ", ".join(c.__class__.__name__ for c in self.components.values())
        return f"Entity({self.uid}, {self.name}, tags={self.tags}, comps=[{comps}])"
