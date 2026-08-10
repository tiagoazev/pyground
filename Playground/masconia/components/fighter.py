"""
Componente de combate.

Armazena ataques disponíveis, resistências, vulnerabilidades,
e flags de estado de combate (stunned, poisoned, etc.).

Separado de Stats porque:
  → Stats são atributos intrínsecos (não mudam com buffs temporários de combate).
  → Fighter contém dados específicos de combate que mudam frequentemente.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any

from utils.constants import DamageType


@dataclass
class Fighter:
    """
    Dados de combate de uma entidade.

    Attributes:
        attacks: Lista de ataques disponíveis (cada um com nome, hit_bonus, damage, type).
        resistances: Tipos de dano aos quais a entidade é resistente (dano / 2).
        weaknesses: Tipos de dano aos quais a entidade é vulnerável (dano * 2).
        immunities: Tipos de dano que causam 0.
        conditions: Estados de condição ativos (stunned, poisoned, etc.).
        action_points: Pontos de ação por turno (D&D: 1 ação + 1 bônus + movimento).
        bonus_action_used: Se já usou ação bônus neste turno.
        reaction_used: Se já usou reação neste turno.
        movement_left: Movimento restante em tiles este turno.
        max_movement: Movimento máximo por turno.
    """
    attacks: List[Dict[str, Any]] = field(default_factory=list)
    resistances: List[DamageType] = field(default_factory=list)
    weaknesses: List[DamageType] = field(default_factory=list)
    immunities: List[DamageType] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    action_points: int = 1
    bonus_action_used: bool = False
    reaction_used: bool = False
    movement_left: int = 5
    max_movement: int = 5

    def reset_turn(self):
        """Reseta ações e movimento para o início do turno."""
        self.action_points = 1
        self.bonus_action_used = False
        self.reaction_used = False
        self.movement_left = self.max_movement

    def use_action(self) -> bool:
        if self.action_points > 0:
            self.action_points -= 1
            return True
        return False

    def use_bonus_action(self) -> bool:
        if not self.bonus_action_used:
            self.bonus_action_used = True
            return True
        return False

    def use_reaction(self) -> bool:
        if not self.reaction_used:
            self.reaction_used = True
            return True
        return False

    def can_move(self, distance: int = 1) -> bool:
        return self.movement_left >= distance

    def move(self, distance: int = 1) -> bool:
        if self.can_move(distance):
            self.movement_left -= distance
            return True
        return False

    def add_condition(self, name: str, duration: int, data: Dict[str, Any] = None):
        """Adiciona uma condição (stunned, poisoned, etc.)."""
        self.conditions.append({
            "name": name,
            "duration": duration,
            "data": data or {}
        })

    def tick_conditions(self):
        """Decrementa duração das condições."""
        self.conditions = [c for c in self.conditions if c["duration"] != 0]
        for c in self.conditions:
            if c["duration"] > 0:
                c["duration"] -= 1

    def has_condition(self, name: str) -> bool:
        return any(c["name"] == name for c in self.conditions)

    def __repr__(self):
        return f"Fighter(AP={self.action_points}, move={self.movement_left}, conditions={len(self.conditions)})"
