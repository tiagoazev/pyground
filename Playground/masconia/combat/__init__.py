"""
Sistema de combate de Masconia.
"""
from combat.system import CombatSystem
from combat.conditions import ConditionSystem, Condition, ConditionType
from combat.abilities import AbilityRegistry, Ability
from combat.tactics import TacticsSystem

__all__ = [
    "CombatSystem",
    "ConditionSystem", "Condition", "ConditionType",
    "AbilityRegistry", "Ability",
    "TacticsSystem"
]
