"""
Sistema de Condições de Status (Status Effects).

Condições são efeitos temporários que alteram o comportamento ou stats
de uma entidade. Inspirado em D&D 5e com extensões para roguelikes.

Condições implementadas:
  • Poisoned: dano por turno, desvantagem em ataques
  • Stunned: não pode agir, CA reduzida
  • Burning: dano de fogo por turno, chance de espalhar
  • Frozen: não pode mover, CA aumentada
  • Bleeding: dano por turno, acumula
  • Blinded: desvantagem em ataques, inimigos têm vantagem
  • Weakened: dano reduzido pela metade
  • Empowered: dano aumentado
  • Hasted: movimento dobrado, ação extra
  • Regenerating: cura por turno
  • Cursed: não pode curar, stats reduzidos
  • Fear: deve fugir do alvo

Arquitetura:
  • Condition é um dataclass com dados do efeito.
  • ConditionSystem aplica e processa condições a cada turno.
  • Condições são armazenadas no componente Fighter.
  • Condições podem ter duração em turnos ou serem permanentes até curadas.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import IntEnum

from ecs.world import World, Event
from components.stats import Stats
from components.fighter import Fighter
from components.position import Position
from utils.dice import DiceRoller
from utils.constants import DamageType


class ConditionType(IntEnum):
    """Tipos de condição."""
    POISONED = 1
    STUNNED = 2
    BURNING = 3
    FROZEN = 4
    BLEEDING = 5
    BLINDED = 6
    WEAKENED = 7
    EMPOWERED = 8
    HASTED = 9
    REGENERATING = 10
    CURSED = 11
    FEARED = 12
    CHARMED = 13
    INVISIBLE = 14
    PROTECTED = 15
    MARKED = 16


@dataclass
class Condition:
    """
    Condição de status em uma entidade.

    Attributes:
        condition_type: Tipo da condição.
        duration: Turnos restantes (-1 = permanente).
        potency: Intensidade (ex: dano do veneno, quantidade de cura).
        source: Entidade que aplicou a condição.
        data: Dados extras específicos do tipo.
        stacks: Se True, pode acumular múltiplas instâncias.
        max_stacks: Máximo de acúmulos.
        stack_count: Quantas vezes está acumulada.
    """
    condition_type: ConditionType
    duration: int = 3
    potency: int = 0
    source: Any = None
    data: Dict[str, Any] = field(default_factory=dict)
    stacks: bool = False
    max_stacks: int = 1
    stack_count: int = 1

    @property
    def name(self) -> str:
        names = {
            ConditionType.POISONED: "Envenenado",
            ConditionType.STUNNED: "Atordoado",
            ConditionType.BURNING: "Queimando",
            ConditionType.FROZEN: "Congelado",
            ConditionType.BLEEDING: "Sangrando",
            ConditionType.BLINDED: "Cego",
            ConditionType.WEAKENED: "Enfraquecido",
            ConditionType.EMPOWERED: "Empoderado",
            ConditionType.HASTED: "Acelerado",
            ConditionType.REGENERATING: "Regenerando",
            ConditionType.CURSED: "Amaldiçoado",
            ConditionType.FEARED: "Amedrontado",
            ConditionType.CHARMED: "Encantado",
            ConditionType.INVISIBLE: "Invisível",
            ConditionType.PROTECTED: "Protegido",
            ConditionType.MARKED: "Marcado",
        }
        return names.get(self.condition_type, "Desconhecido")

    @property
    def is_permanent(self) -> bool:
        return self.duration == -1

    @property
    def is_expired(self) -> bool:
        return self.duration == 0 and not self.is_permanent


class ConditionSystem:
    """
    System que processa condições a cada turno.

    Responsabilidades:
      • Aplicar efeitos de condições (dano, cura, etc.)
      • Decrementar durações
      • Remover condições expiradas
      • Emitir eventos para UI
    """

    def __init__(self):
        self.world: Optional[World] = None
        self.dice = DiceRoller()

    def apply_condition(self, target, condition: Condition) -> bool:
        """
        Aplica uma condição a uma entidade.
        Retorna True se foi aplicada (ou acumulada).
        """
        fighter = target.get_component(Fighter)
        if not fighter:
            return False

        # Verifica imunidades
        if self._is_immune(target, condition.condition_type):
            return False

        # Se acumula, procura instância existente
        if condition.stacks:
            for existing in fighter.conditions:
                if existing["name"] == condition.name:
                    existing["data"]["stack_count"] = min(
                        existing["data"].get("stack_count", 1) + 1,
                        condition.max_stacks
                    )
                    existing["duration"] = max(existing.get("duration", 0), condition.duration)
                    self.world.emit(Event("condition_stacked", {
                        "target": target,
                        "condition": condition.name,
                        "stacks": existing["data"]["stack_count"]
                    }))
                    return True

        # Adiciona nova condição
        fighter.add_condition(
            name=condition.name,
            duration=condition.duration,
            data={
                "type": condition.condition_type.value,
                "potency": condition.potency,
                "source": condition.source,
                "stacks": condition.stacks,
                "max_stacks": condition.max_stacks,
                "stack_count": 1
            }
        )

        self.world.emit(Event("condition_applied", {
            "target": target,
            "condition": condition.name,
            "duration": condition.duration,
            "potency": condition.potency
        }))

        return True

    def remove_condition(self, target, condition_name: str) -> bool:
        """Remove uma condição pelo nome."""
        fighter = target.get_component(Fighter)
        if not fighter:
            return False

        for i, cond in enumerate(fighter.conditions):
            if cond["name"] == condition_name:
                fighter.conditions.pop(i)
                self.world.emit(Event("condition_removed", {
                    "target": target,
                    "condition": condition_name
                }))
                return True
        return False

    def process_turn(self, entity):
        """Processa todas as condições de uma entidade no início do turno."""
        fighter = entity.get_component(Fighter)
        stats = entity.get_component(Stats)
        if not fighter or not stats:
            return

        expired = []

        for cond in fighter.conditions:
            if cond.get("duration", 0) > 0:
                self._apply_condition_effect(entity, stats, fighter, cond)
                cond["duration"] -= 1
            elif cond.get("duration", 0) == 0:
                expired.append(cond)

        # Remove expiradas
        for cond in expired:
            if cond in fighter.conditions:
                fighter.conditions.remove(cond)
                self.world.emit(Event("condition_expired", {
                    "target": entity,
                    "condition": cond["name"]
                }))

    def _apply_condition_effect(self, entity, stats: Stats, fighter: Fighter,
                                 cond: Dict):
        """Aplica o efeito mecânico de uma condição."""
        data = cond.get("data", {})
        cond_type = data.get("type", 0)
        potency = data.get("potency", 0)
        stacks = data.get("stack_count", 1)

        if cond_type == ConditionType.POISONED:
            # Dano de veneno por turno
            damage = max(1, self.dice.roll(f"{potency}d4")) * stacks
            actual = stats.take_damage(damage)
            self.world.emit(Event("condition_damage", {
                "target": entity,
                "condition": "Envenenado",
                "damage": actual,
                "type": DamageType.POISON
            }))

        elif cond_type == ConditionType.BURNING:
            # Dano de fogo por turno
            damage = self.dice.roll(f"{potency}d6") * stacks
            actual = stats.take_damage(damage)
            self.world.emit(Event("condition_damage", {
                "target": entity,
                "condition": "Queimando",
                "damage": actual,
                "type": DamageType.FIRE
            }))
            # Chance de espalhar para inimigos adjacentes
            if self.dice.roll("1d100") <= 20 * stacks:
                self._spread_burn(entity)

        elif cond_type == ConditionType.BLEEDING:
            # Dano de sangramento
            damage = self.dice.roll(f"{potency}d4") * stacks
            actual = stats.take_damage(damage)
            self.world.emit(Event("condition_damage", {
                "target": entity,
                "condition": "Sangrando",
                "damage": actual,
                "type": DamageType.SLASHING
            }))

        elif cond_type == ConditionType.REGENERATING:
            # Cura por turno
            heal = self.dice.roll(f"{potency}d4") * stacks
            actual = stats.heal(heal)
            self.world.emit(Event("condition_heal", {
                "target": entity,
                "condition": "Regenerando",
                "heal": actual
            }))

        elif cond_type == ConditionType.CURSED:
            # Dano necrótico por turno
            damage = self.dice.roll(f"{potency}d6") * stacks
            actual = stats.take_damage(damage)
            self.world.emit(Event("condition_damage", {
                "target": entity,
                "condition": "Amaldiçoado",
                "damage": actual,
                "type": DamageType.NECROTIC
            }))

    def _spread_burn(self, source_entity):
        """Tenta espalhar queimadura para entidades adjacentes."""
        pos = source_entity.get_component(Position)
        if not pos:
            return

        for entity in self.world.query(Position, Fighter):
            if entity == source_entity:
                continue
            epos = entity.get_component(Position)
            if epos.distance_to(pos) <= 1:
                self.apply_condition(entity, Condition(
                    ConditionType.BURNING,
                    duration=2,
                    potency=1,
                    source=source_entity
                ))

    def _is_immune(self, entity, condition_type: ConditionType) -> bool:
        """Verifica se a entidade é imune a uma condição."""
        fighter = entity.get_component(Fighter)
        if not fighter:
            return False

        # Undead são imunes a poison e bleeding
        if entity.has_tag("undead"):
            if condition_type in (ConditionType.POISONED, ConditionType.BLEEDING):
                return True

        # Elementais de fogo são imunes a burning
        if entity.has_tag("fire_elemental"):
            if condition_type == ConditionType.BURNING:
                return True

        # Golems são imunes a poison, bleeding, fear
        if entity.has_tag("golem"):
            if condition_type in (ConditionType.POISONED, ConditionType.BLEEDING, ConditionType.FEARED):
                return True

        return False

    def has_condition(self, entity, condition_type: ConditionType) -> bool:
        """Verifica se a entidade tem uma condição específica."""
        fighter = entity.get_component(Fighter)
        if not fighter:
            return False

        type_name = Condition(condition_type).name
        return any(c["name"] == type_name for c in fighter.conditions)

    def get_condition_effects(self, entity) -> Dict[str, Any]:
        """
        Retorna um resumo de todos os efeitos ativos na entidade.
        Útil para calcular modificadores de combate.
        """
        fighter = entity.get_component(Fighter)
        if not fighter:
            return {}

        effects = {
            "disadvantage_attack": False,
            "disadvantage_defense": False,
            "advantage_attack": False,
            "cannot_act": False,
            "cannot_move": False,
            "damage_multiplier": 1.0,
            "movement_multiplier": 1.0,
            "ca_modifier": 0,
        }

        for cond in fighter.conditions:
            cond_type = cond.get("type", 0)

            if cond_type == ConditionType.POISONED:
                effects["disadvantage_attack"] = True
            elif cond_type == ConditionType.STUNNED:
                effects["cannot_act"] = True
                effects["cannot_move"] = True
                effects["ca_modifier"] -= 2
            elif cond_type == ConditionType.FROZEN:
                effects["cannot_move"] = True
                effects["ca_modifier"] += 2
            elif cond_type == ConditionType.BLINDED:
                effects["disadvantage_attack"] = True
                effects["advantage_attack_enemy"] = True
            elif cond_type == ConditionType.WEAKENED:
                effects["damage_multiplier"] *= 0.5
            elif cond_type == ConditionType.EMPOWERED:
                effects["damage_multiplier"] *= 1.5
            elif cond_type == ConditionType.HASTED:
                effects["movement_multiplier"] *= 2
                effects["extra_action"] = True
            elif cond_type == ConditionType.FEARED:
                effects["must_flee"] = True
            elif cond_type == ConditionType.INVISIBLE:
                effects["advantage_attack"] = True
                effects["disadvantage_defense"] = True
            elif cond_type == ConditionType.PROTECTED:
                effects["ca_modifier"] += 2
                effects["damage_reduction"] = effects.get("damage_reduction", 0) + 2

        return effects

    def __repr__(self):
        count = 0
        if self.world:
            for e in self.world.query(Fighter):
                fighter = e.get_component(Fighter)
                if fighter:
                    count += len(fighter.conditions)
        return f"ConditionSystem(active_conditions={count})"
