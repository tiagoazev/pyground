"""
World ECS: gerencia todas as entidades, queries e systems.

Responsabilidades:
  • Criar e destruir entidades
  • Executar systems na ordem correta
  • Queries eficientes (filtrar entidades por componentes/tags)
  • Comunicação entre systems via eventos

Arquitetura:
  Systems são registrados em ordem de execução.
  A cada frame: process input → update → render.
  Eventos são enfileirados e processados entre frames para evitar
  modificações concorrentes na lista de entidades.
"""
from typing import List, Dict, Type, Callable, Optional, Any
from collections import deque

from ecs.entity import Entity


class Event:
    """Evento tipado para comunicação desacoplada entre systems."""
    def __init__(self, event_type: str, data: Dict[str, Any] = None):
        self.type = event_type
        self.data = data or {}


class World:
    """
    Container ECS principal do jogo.

    Attributes:
        entities: Lista de todas as entidades ativas.
        systems: Lista de systems na ordem de execução.
        events: Fila de eventos a serem processados.
        _pending_removals: Entidades marcadas para destruição.
    """

    def __init__(self):
        self.entities: List[Entity] = []
        self.systems: List[Any] = []  # Tipicamente herdam de System base
        self.events: deque = deque()
        self._pending_removals: List[Entity] = []
        self._event_handlers: Dict[str, List[Callable]] = {}

    def create_entity(self, name: str = "Entity") -> Entity:
        """Cria uma nova entidade e a adiciona ao mundo."""
        entity = Entity(name)
        self.entities.append(entity)
        return entity

    def destroy_entity(self, entity: Entity):
        """Marca entidade para remoção segura."""
        entity.destroy()
        if entity not in self._pending_removals:
            self._pending_removals.append(entity)

    def register_system(self, system):
        """Registra um system na ordem de execução."""
        self.systems.append(system)
        system.world = self  # Injeta referência ao mundo
        return system

    def query(self, *component_types: Type, tags: List[str] = None, active_only: bool = True) -> List[Entity]:
        """
        Filtra entidades que possuem TODOS os componentes listados
        e TODAS as tags especificadas.

        Exemplo:
            world.query(Position, Stats, tags=["enemy"])
            → Todas as entidades inimigas com posição e stats.
        """
        tags = tags or []
        result = []
        for entity in self.entities:
            if active_only and not entity.active:
                continue
            if all(entity.has_component(ct) for ct in component_types):
                if all(entity.has_tag(t) for t in tags):
                    result.append(entity)
        return result

    def query_one(self, *component_types: Type, tags: List[str] = None, active_only: bool = True) -> Optional[Entity]:
        """Como query(), mas retorna apenas a primeira entidade encontrada."""
        results = self.query(*component_types, tags=tags, active_only=active_only)
        return results[0] if results else None

    def emit(self, event: Event):
        """Emite um evento para ser processado no próximo ciclo."""
        self.events.append(event)

    def subscribe(self, event_type: str, handler: Callable):
        """Registra um handler para um tipo de evento."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def _process_events(self):
        """Processa todos os eventos pendentes."""
        while self.events:
            event = self.events.popleft()
            handlers = self._event_handlers.get(event.type, [])
            for handler in handlers:
                handler(event)

    def _cleanup_entities(self):
        """Remove entidades destruídas de forma segura."""
        for entity in self._pending_removals:
            if entity in self.entities:
                self.entities.remove(entity)
        self._pending_removals.clear()

    def update(self, dt: float):
        """
        Executa um frame completo do ECS:
        1. Processa eventos pendentes
        2. Atualiza todos os systems
        3. Limpa entidades destruídas
        """
        self._process_events()
        for system in self.systems:
            if hasattr(system, "update"):
                system.update(dt)
        self._cleanup_entities()

    def render(self, screen):
        """Renderiza via systems que possuem método render."""
        for system in self.systems:
            if hasattr(system, "render"):
                system.render(screen)

    def clear(self):
        """Destroi todas as entidades e limpa o mundo."""
        self.entities.clear()
        self._pending_removals.clear()
        self.events.clear()

    def __repr__(self):
        return f"World(entities={len(self.entities)}, systems={len(self.systems)})"
