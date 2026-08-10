"""
Sistema de rolagem de dados estilo D&D.

Suporta:
  • Rolagens padrão (d20, 2d6+3, etc.)
  • Vantagem/Desvantagem (rolar 2d20, pegar maior/menor)
  • Críticos naturais (20) e fumbles (1)
  • Modificadores de atributo (floor((stat-10)/2))
  • Resistências/vulnerabilidades multiplicadoras

Por que separar em módulo próprio?
  → Testabilidade: podemos mockar o RNG em testes unitários.
  → Reutilização: combate, loot, eventos aleatórios usam o mesmo sistema.
"""
import random
import re
from typing import List, Tuple, Optional

from utils.constants import DamageType


class DiceRoller:
    """Motor de rolagem de dados com seed controlável."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def set_seed(self, seed: int):
        """Define uma seed para runs reproduzíveis (daily challenge)."""
        self._rng = random.Random(seed)

    def roll(self, expression: str) -> int:
        """
        Avalia uma expressão de dado como '2d6+3' ou '1d8'.
        Retorna o total.
        """
        expression = expression.strip().lower()
        match = re.match(r"(\d+)d(\d+)(?:([+-])(\d+))?", expression)
        if not match:
            raise ValueError(f"Expressão de dado inválida: {expression}")

        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = 0
        if match.group(3):
            sign = 1 if match.group(3) == "+" else -1
            modifier = sign * int(match.group(4))

        total = sum(self._rng.randint(1, die_size) for _ in range(num_dice))
        return total + modifier

    def roll_detailed(self, expression: str) -> Tuple[int, List[int]]:
        """
        Como roll(), mas retorna também a lista de resultados individuais.
        Útil para mostrar animação de dados rolando na UI.
        """
        expression = expression.strip().lower()
        match = re.match(r"(\d+)d(\d+)(?:([+-])(\d+))?", expression)
        if not match:
            raise ValueError(f"Expressão de dado inválida: {expression}")

        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = 0
        if match.group(3):
            sign = 1 if match.group(3) == "+" else -1
            modifier = sign * int(match.group(4))

        rolls = [self._rng.randint(1, die_size) for _ in range(num_dice)]
        return sum(rolls) + modifier, rolls

    def d20(self, advantage: bool = False, disadvantage: bool = False) -> Tuple[int, int]:
        """
        Rola um d20. Suporta vantagem/desvantagem.
        Retorna (resultado_final, resultado_natural).

        Se advantage=True:  rola 2d20, pega o maior.
        Se disadvantage=True: rola 2d20, pega o menor.
        """
        if advantage and disadvantage:
            # Cancelam-se
            advantage = disadvantage = False

        roll1 = self._rng.randint(1, 20)
        roll2 = self._rng.randint(1, 20)

        if advantage:
            return max(roll1, roll2), roll1
        if disadvantage:
            return min(roll1, roll2), roll1

        return roll1, roll1

    def is_critical(self, natural_roll: int) -> bool:
        return natural_roll == 20

    def is_fumble(self, natural_roll: int) -> bool:
        return natural_roll == 1

    @staticmethod
    def stat_modifier(stat_value: int) -> int:
        """Calcula modificador de atributo D&D: floor((stat-10)/2)."""
        return (stat_value - 10) // 2

    def apply_damage_modifiers(
        self,
        base_damage: int,
        damage_type: DamageType,
        resistances: List[DamageType],
        weaknesses: List[DamageType],
        immunities: List[DamageType] = None
    ) -> int:
        """
        Aplica multiplicadores de dano baseado em resistências.

        Resistência: dano / 2 (arredondado para baixo)
        Vulnerabilidade: dano * 2
        Imunidade: dano = 0
        """
        immunities = immunities or []
        if damage_type in immunities:
            return 0
        if damage_type in resistances:
            return base_damage // 2
        if damage_type in weaknesses:
            return base_damage * 2
        return base_damage


# Instância global para conveniência (pode ser substituída em testes)
_dice = DiceRoller()


def roll(expression: str) -> int:
    return _dice.roll(expression)


def d20(advantage: bool = False, disadvantage: bool = False) -> Tuple[int, int]:
    return _dice.d20(advantage, disadvantage)


def set_seed(seed: int):
    _dice.set_seed(seed)
