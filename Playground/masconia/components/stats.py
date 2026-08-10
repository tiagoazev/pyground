"""
Componente de atributos e stats de combate.

Segue o modelo D&D 5e:
  • 6 atributos base (STR, DEX, CON, INT, WIS, CHA)
  • Modificadores calculados automaticamente
  • HP, MP, XP com max/current
  • CA (Classe de Armadura) calculada com equipamentos
  • Nível e proficiência

Por que dataclass?
  → Imutabilidade parcial: stats base são fixos, mas buffs temporários
    podem ser aplicados via lista de modifiers.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any

from utils.dice import DiceRoller


@dataclass
class Stats:
    """
    Stats de personagem/inimigo.

    Attributes:
        str_, dex, con, int_, wis, cha: Atributos base (3-20 tipicamente).
        hp, max_hp: Pontos de vida.
        mp, max_mp: Pontos de mana (para magos e clérigos).
        xp, xp_to_next: Experiência.
        level: Nível do personagem.
        ac_base: Classe de Armadura base (sem equipamento).
        ac_bonus: Bônus de CA de escudos/armaduras.
        proficiency_bonus: Bônus de proficiência (calculado por nível).
        temp_hp: HP temporário (absorve dano antes do HP real).
        modifiers: Lista de buffs/debuffs temporários.
    """
    # Atributos base
    str_: int = 10
    dex: int = 10
    con: int = 10
    int_: int = 10
    wis: int = 10
    cha: int = 10

    # Recursos
    hp: int = 10
    max_hp: int = 10
    mp: int = 0
    max_mp: int = 0
    xp: int = 0
    xp_to_next: int = 100
    level: int = 1

    # Defesa
    ac_base: int = 10
    ac_bonus: int = 0
    temp_hp: int = 0

    # Modificadores temporários
    modifiers: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def str_mod(self) -> int:
        return DiceRoller.stat_modifier(self.str_)

    @property
    def dex_mod(self) -> int:
        return DiceRoller.stat_modifier(self.dex)

    @property
    def con_mod(self) -> int:
        return DiceRoller.stat_modifier(self.con)

    @property
    def int_mod(self) -> int:
        return DiceRoller.stat_modifier(self.int_)

    @property
    def wis_mod(self) -> int:
        return DiceRoller.stat_modifier(self.wis)

    @property
    def cha_mod(self) -> int:
        return DiceRoller.stat_modifier(self.cha)

    @property
    def ac(self) -> int:
        """CA total = base + bônus de equipamento + DEX (limitado por armadura)."""
        # DEX contribui para CA, mas algumas armaduras limitam o bônus
        dex_contrib = self.dex_mod
        # TODO: aplicar limitação de DEX por tipo de armadura
        return self.ac_base + self.ac_bonus + dex_contrib

    @property
    def proficiency_bonus(self) -> int:
        """Bônus de proficiência D&D: 2 + (nível-1)//4."""
        return 2 + (self.level - 1) // 4

    def take_damage(self, amount: int) -> int:
        """
        Aplica dano. Temp HP absorve primeiro.
        Retorna dano real aplicado ao HP.
        """
        if self.temp_hp > 0:
            absorbed = min(self.temp_hp, amount)
            self.temp_hp -= absorbed
            amount -= absorbed
        actual = min(amount, self.hp)
        self.hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        """Cura HP. Não ultrapassa max_hp. Retorna quanto curou."""
        before = self.hp
        self.hp = min(self.hp + amount, self.max_hp)
        return self.hp - before

    def restore_mana(self, amount: int) -> int:
        """Restaura MP. Não ultrapassa max_mp."""
        before = self.mp
        self.mp = min(self.mp + amount, self.max_mp)
        return self.mp - before

    def spend_mana(self, amount: int) -> bool:
        """Gasta MP. Retorna True se conseguiu."""
        if self.mp >= amount:
            self.mp -= amount
            return True
        return False

    def add_xp(self, amount: int) -> bool:
        """
        Adiciona XP. Se ultrapassa xp_to_next, sobe de nível.
        Retorna True se level up ocorreu.
        """
        self.xp += amount
        if self.xp >= self.xp_to_next:
            self._level_up()
            return True
        return False

    def _level_up(self):
        """Sobe de nível e ajusta stats."""
        self.level += 1
        self.xp -= self.xp_to_next
        self.xp_to_next = int(self.xp_to_next * 1.5)
        # Aumenta max HP (roll do hit die + CON mod)
        # Simplificado: +CON mod + dado de vida da classe
        hp_gain = max(1, self.con_mod + 5)  # Média de d8
        self.max_hp += hp_gain
        self.hp = self.max_hp
        # Aumenta max MP
        mp_gain = max(1, self.int_mod + 3)
        self.max_mp += mp_gain
        self.mp = self.max_mp

    def is_alive(self) -> bool:
        return self.hp > 0

    def add_modifier(self, name: str, stat: str, value: int, duration: int = -1):
        """
        Adiciona um modificador temporário.

        Args:
            name: Identificador do efeito.
            stat: Qual stat afeta ("str", "dex", "ac_bonus", etc.).
            value: Valor do bônus/penalidade.
            duration: Turnos restantes (-1 = permanente até removido).
        """
        self.modifiers.append({
            "name": name,
            "stat": stat,
            "value": value,
            "duration": duration
        })

    def tick_modifiers(self):
        """Decrementa duração de modifiers temporários."""
        self.modifiers = [m for m in self.modifiers if m["duration"] != 0]
        for m in self.modifiers:
            if m["duration"] > 0:
                m["duration"] -= 1

    def get_modified_stat(self, stat_name: str) -> int:
        """Retorna o valor base + soma de todos os modifiers ativos."""
        base = getattr(self, stat_name, 0)
        bonus = sum(m["value"] for m in self.modifiers if m["stat"] == stat_name)
        return base + bonus

    def __repr__(self):
        return (f"Stats(HP={self.hp}/{self.max_hp}, MP={self.mp}/{self.max_mp}, "
                f"LV={self.level}, AC={self.ac}, STR={self.str_}, DEX={self.dex})")
