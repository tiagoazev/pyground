"""
Sistema de Habilidades de Classe e Magias.

Implementa as habilidades especiais de cada classe:
  • Guerreiro: Segundo Fôlego, Ataque Poderoso, Provocar
  • Ladino: Ataque Furtivo, Desengate, Esconder-se
  • Mago: Bola de Fogo, Escudo Arcano, Raio de Gelo, Teleporte
  • Clérigo: Cura de Ferimentos, Repreensão, Bênção, Proteção

Arquitetura:
  • Ability é uma classe base com métodos can_use() e execute().
  • Cada habilidade específica herda de Ability.
  • AbilityRegistry mapeia ability_id → classe de habilidade.
  • Habilidades consomem MP, ações, e têm cooldowns.
  • Magias de área afetam múltiplos tiles/entidades.

Magias de Área:
  • Bola de Fogo: explosão em raio de 2 tiles, dano de fogo
  • Raio de Gelo: linha de 4 tiles, dano de frio + chance de congelar
  • Onda de Força: empurra inimigos em cone
  • Bênção: buff em raio de 3 tiles
  • Repreensão: inimigos em raio de 3 tiles devem fugir
"""
from typing import List, Tuple, Optional, Dict, Any
from abc import ABC, abstractmethod

from ecs.world import World, Event
from components.stats import Stats
from components.fighter import Fighter
from components.position import Position
from components.inventory import Inventory
from components.ai import AI
from combat.conditions import ConditionSystem, Condition, ConditionType
from utils.dice import DiceRoller
from utils.constants import DamageType


class Ability(ABC):
    """
    Classe base para todas as habilidades.

    Attributes:
        ability_id: Identificador único.
        name: Nome legível.
        description: Descrição para UI.
        mana_cost: Custo de MP.
        action_cost: Custo de ações (1 = ação padrão, 0.5 = bônus).
        cooldown: Turnos de recarga.
        range_: Alcance em tiles.
        area: Raio de área (0 = alvo único).
        requires_target: Se precisa de alvo.
        requires_line_of_sight: Se precisa de LOS.
    """

    def __init__(self, ability_id: str, name: str, description: str,
                 mana_cost: int = 0, action_cost: float = 1.0,
                 cooldown: int = 0, range_: int = 1, area: int = 0,
                 requires_target: bool = True, requires_los: bool = True):
        self.ability_id = ability_id
        self.name = name
        self.description = description
        self.mana_cost = mana_cost
        self.action_cost = action_cost
        self.cooldown = cooldown
        self.range = range_
        self.area = area
        self.requires_target = requires_target
        self.requires_los = requires_los
        self.dice = DiceRoller()

    def can_use(self, caster) -> Tuple[bool, str]:
        """
        Verifica se a habilidade pode ser usada.
        Retorna (pode_usar, mensagem_de_erro).
        """
        stats = caster.get_component(Stats)
        fighter = caster.get_component(Fighter)

        if not stats or not fighter:
            return False, "Sem stats ou fighter"

        # Verifica se está vivo
        if not stats.is_alive():
            return False, "Morto"

        # Verifica stun
        if fighter.has_condition("Atordoado"):
            return False, "Atordoado"

        # Verifica MP
        if self.mana_cost > 0 and stats.mp < self.mana_cost:
            return False, f"MP insuficiente ({stats.mp}/{self.mana_cost})"

        # Verifica ação
        if self.action_cost >= 1 and fighter.action_points < 1:
            return False, "Sem ações"
        if self.action_cost < 1 and fighter.bonus_action_used:
            return False, "Ação bônus já usada"

        # Verifica cooldown
        ai = caster.get_component(AI)
        if ai and ai.is_on_cooldown(self.ability_id):
            return False, "Em cooldown"

        return True, ""

    def use(self, caster, target=None, target_pos: Tuple[int, int] = None,
            world: World = None, condition_system: ConditionSystem = None) -> Dict[str, Any]:
        """
        Usa a habilidade. Retorna dict com resultado.
        """
        can_use, error = self.can_use(caster)
        if not can_use:
            return {"success": False, "error": error}

        stats = caster.get_component(Stats)
        fighter = caster.get_component(Fighter)

        # Gasta recursos
        if self.mana_cost > 0:
            stats.spend_mana(self.mana_cost)

        if self.action_cost >= 1:
            fighter.use_action()
        else:
            fighter.use_bonus_action()

        # Set cooldown
        ai = caster.get_component(AI)
        if ai and self.cooldown > 0:
            ai.set_cooldown(self.ability_id, self.cooldown)

        # Executa efeito
        result = self.execute(caster, target, target_pos, world, condition_system)
        result["success"] = True
        result["ability"] = self.name

        if world:
            world.emit(Event("ability_used", {
                "caster": caster,
                "ability": self.ability_id,
                "target": target,
                "result": result
            }))

        return result

    @abstractmethod
    def execute(self, caster, target=None, target_pos: Tuple[int, int] = None,
                world: World = None, condition_system: ConditionSystem = None) -> Dict[str, Any]:
        """Implementação específica da habilidade."""
        pass

    def _get_targets_in_area(self, world: World, center_x: int, center_y: int,
                             radius: int, tags: List[str] = None) -> List:
        """Retorna entidades dentro do raio de área."""
        tags = tags or []
        targets = []
        center = Position(x=center_x, y=center_y)

        for entity in world.query(Position, *([Fighter] if not tags else []), tags=tags):
            pos = entity.get_component(Position)
            if pos.distance_to(center) <= radius:
                targets.append(entity)

        return targets

    def _roll_attack(self, caster, target, hit_bonus: int = 0) -> Tuple[bool, bool, int]:
        """
        Rola ataque mágico/ability.
        Retorna (acertou, crítico, roll_total).
        """
        stats = caster.get_component(Stats)
        target_stats = target.get_component(Stats)

        if not stats or not target_stats:
            return False, False, 0

        # Para magias, usa INT como stat de ataque
        stat_mod = stats.int_mod
        prof = stats.proficiency_bonus

        roll, natural = self.dice.d20()
        total = roll + hit_bonus + stat_mod + prof

        is_crit = self.dice.is_critical(natural)
        is_hit = is_crit or total >= target_stats.ac

        return is_hit, is_crit, total

    def __repr__(self):
        return f"Ability({self.ability_id}, {self.name})"


# ═════════════════════════════════════════════════════════════
# HABILIDADES DO GUERREIRO
# ═════════════════════════════════════════════════════════════

class SecondWind(Ability):
    """Segundo Fôlego: recupera 1d10 + nível de HP. Uma vez por combate."""

    def __init__(self):
        super().__init__(
            ability_id="second_wind",
            name="Segundo Fôlego",
            description="Recupera 1d10 + nível de HP. Uma vez por combate.",
            mana_cost=0,
            action_cost=0.5,  # Bônus action
            cooldown=999,  # Uma vez por combate (resetado entre combates)
            range_=0,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        stats = caster.get_component(Stats)
        heal = self.dice.roll(f"1d10+{stats.level}")
        actual = stats.heal(heal)
        return {"heal": actual, "type": "heal"}


class PowerAttack(Ability):
    """Ataque Poderoso: próximo ataque causa +2d6 de dano."""

    def __init__(self):
        super().__init__(
            ability_id="power_attack",
            name="Ataque Poderoso",
            description="Gasta ação bônus para +2d6 de dano no próximo ataque.",
            mana_cost=0,
            action_cost=0.5,
            cooldown=2,
            range_=0,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        # Aplica buff temporário ao fighter
        fighter = caster.get_component(Fighter)
        fighter.add_condition("Ataque Poderoso", duration=1, data={"bonus_damage": "2d6"})
        return {"buff": "power_attack", "duration": 1}


class Provoke(Ability):
    """Provocar: força inimigos próximos a atacar o guerreiro."""

    def __init__(self):
        super().__init__(
            ability_id="provoke",
            name="Provocar",
            description="Inimigos em raio de 3 tiles devem atacar você.",
            mana_cost=0,
            action_cost=1,
            cooldown=3,
            range_=3,
            area=3,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        pos = caster.get_component(Position)
        targets = self._get_targets_in_area(world, pos.x, pos.y, 3, tags=["enemy"])

        taunted = 0
        for enemy in targets:
            ai = enemy.get_component(AI)
            if ai:
                ai.current_state = "taunted"
                ai.last_known_player_pos = (pos.x, pos.y)
                taunted += 1

        return {"taunted": taunted, "type": "taunt"}


# ═════════════════════════════════════════════════════════════
# HABILIDADES DO LADINO
# ═════════════════════════════════════════════════════════════

class SneakAttack(Ability):
    """Ataque Furtivo: +2d6 de dano se atacar com vantagem ou inimigo adjacente a aliado."""

    def __init__(self):
        super().__init__(
            ability_id="sneak_attack",
            name="Ataque Furtivo",
            description="+2d6 de dano se atacar com vantagem ou inimigo adjacente a aliado.",
            mana_cost=0,
            action_cost=0,  # Passivo, aplica automaticamente
            cooldown=0,
            range_=0,
            requires_target=False
        )

    def can_use(self, caster):
        return False, "Passivo — aplica automaticamente em ataques"

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        return {}  # Nunca chamado diretamente


class Dash(Ability):
    """Desengate: movimento dobrado e não provoca ataques de oportunidade."""

    def __init__(self):
        super().__init__(
            ability_id="dash",
            name="Desengate",
            description="Movimento dobrado e não provoca ataques de oportunidade.",
            mana_cost=0,
            action_cost=0.5,
            cooldown=3,
            range_=0,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        fighter = caster.get_component(Fighter)
        fighter.movement_left += fighter.max_movement
        fighter.add_condition("Desengate", duration=1, data={"no_aoO": True})
        return {"extra_movement": fighter.max_movement, "type": "movement"}


class Hide(Ability):
    """Esconder-se: torna-se invisível por 2 turnos ou até atacar."""

    def __init__(self):
        super().__init__(
            ability_id="hide",
            name="Esconder-se",
            description="Torna-se invisível por 2 turnos ou até atacar.",
            mana_cost=0,
            action_cost=0.5,
            cooldown=4,
            range_=0,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if condition_system:
            condition_system.apply_condition(caster, Condition(
                ConditionType.INVISIBLE,
                duration=2,
                potency=0
            ))
        return {"stealth": True, "duration": 2}


# ═════════════════════════════════════════════════════════════
# HABILIDADES DO MAGO
# ═════════════════════════════════════════════════════════════

class Fireball(Ability):
    """Bola de Fogo: explosão em raio de 2 tiles, 3d6 de dano de fogo."""

    def __init__(self):
        super().__init__(
            ability_id="fireball",
            name="Bola de Fogo",
            description="Magia de área: 3d6 de dano de fogo em raio de 2 tiles.",
            mana_cost=15,
            action_cost=1,
            cooldown=3,
            range_=8,
            area=2,
            requires_target=True,
            requires_los=True
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if not target_pos and target:
            pos = target.get_component(Position)
            target_pos = (pos.x, pos.y)

        if not target_pos:
            return {"success": False, "error": "Sem alvo"}

        tx, ty = target_pos
        targets = self._get_targets_in_area(world, tx, ty, self.area, tags=["enemy", "player"])

        results = []
        for entity in targets:
            if entity == caster:
                continue  # Mago é imune à própria bola de fogo

            is_hit, is_crit, roll = self._roll_attack(caster, entity)

            if is_hit:
                base_damage = self.dice.roll("3d6")
                if is_crit:
                    base_damage *= 2

                stats = entity.get_component(Stats)
                fighter = entity.get_component(Fighter)

                # Aplica resistência
                if fighter and DamageType.FIRE in fighter.resistances:
                    base_damage //= 2
                if fighter and DamageType.FIRE in fighter.weaknesses:
                    base_damage *= 2

                actual = stats.take_damage(base_damage)

                # Chance de queimar
                if condition_system and self.dice.roll("1d100") <= 30:
                    condition_system.apply_condition(entity, Condition(
                        ConditionType.BURNING,
                        duration=2,
                        potency=1,
                        source=caster
                    ))

                results.append({
                    "target": entity.name,
                    "damage": actual,
                    "critical": is_crit,
                    "burning": True
                })
            else:
                results.append({"target": entity.name, "damage": 0, "missed": True})

        return {"targets_hit": len([r for r in results if r.get("damage", 0) > 0]),
                "details": results, "type": "area_fire"}


class ArcaneShield(Ability):
    """Escudo Arcano: +5 CA até o próximo turno. Reação."""

    def __init__(self):
        super().__init__(
            ability_id="shield",
            name="Escudo Arcano",
            description="+5 CA até o próximo turno. Reação.",
            mana_cost=8,
            action_cost=0,  # Reação, não ação
            cooldown=2,
            range_=0,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        stats = caster.get_component(Stats)
        stats.add_modifier("escudo_arcano", "ac_bonus", 5, duration=1)
        return {"ac_bonus": 5, "duration": 1, "type": "buff"}


class FrostRay(Ability):
    """Raio de Gelo: linha de 4 tiles, 2d8 de dano de frio + chance de congelar."""

    def __init__(self):
        super().__init__(
            ability_id="frost_ray",
            name="Raio de Gelo",
            description="Linha de 4 tiles, 2d8 de dano de frio. Chance de congelar.",
            mana_cost=12,
            action_cost=1,
            cooldown=2,
            range_=4,
            area=0,
            requires_target=True
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if not target:
            return {"success": False, "error": "Sem alvo"}

        is_hit, is_crit, roll = self._roll_attack(caster, target)

        if is_hit:
            damage = self.dice.roll("2d8")
            if is_crit:
                damage *= 2

            stats = target.get_component(Stats)
            actual = stats.take_damage(damage)

            frozen = False
            if condition_system and self.dice.roll("1d100") <= 25:
                condition_system.apply_condition(target, Condition(
                    ConditionType.FROZEN,
                    duration=1,
                    potency=0,
                    source=caster
                ))
                frozen = True

            return {"damage": actual, "critical": is_crit, "frozen": frozen, "type": "cold"}

        return {"damage": 0, "missed": True}


class Teleport(Ability):
    """Teleporte: move-se instantaneamente para um tile visível em raio de 6."""

    def __init__(self):
        super().__init__(
            ability_id="teleport",
            name="Teleporte",
            description="Move-se instantaneamente para um tile visível em raio de 6.",
            mana_cost=20,
            action_cost=1,
            cooldown=5,
            range_=6,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if not target_pos:
            return {"success": False, "error": "Selecione um destino"}

        pos = caster.get_component(Position)
        new_x, new_y = target_pos

        # Verifica distância
        if abs(pos.x - new_x) + abs(pos.y - new_y) > self.range:
            return {"success": False, "error": "Fora de alcance"}

        pos.x, pos.y = new_x, new_y
        return {"new_position": (new_x, new_y), "type": "teleport"}


# ═════════════════════════════════════════════════════════════
# HABILIDADES DO CLÉRIGO
# ═════════════════════════════════════════════════════════════

class HealWounds(Ability):
    """Cura de Ferimentos: restaura 2d8 + mod SAB de HP em alvo tocado."""

    def __init__(self):
        super().__init__(
            ability_id="heal",
            name="Cura de Ferimentos",
            description="Restaura 2d8 + mod SAB de HP em alvo tocado.",
            mana_cost=10,
            action_cost=1,
            cooldown=2,
            range_=1,
            requires_target=True
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if not target:
            target = caster  # Auto-cura se nenhum alvo

        stats = caster.get_component(Stats)
        target_stats = target.get_component(Stats)

        heal = self.dice.roll(f"2d8+{stats.wis_mod}")
        actual = target_stats.heal(heal)

        # Remove poison e bleeding
        if condition_system:
            condition_system.remove_condition(target, "Envenenado")
            condition_system.remove_condition(target, "Sangrando")

        return {"heal": actual, "target": target.name, "type": "heal"}


class TurnUndead(Ability):
    """Repreensão: mortos-vivos em raio de 3 tiles devem fugir por 1 turno."""

    def __init__(self):
        super().__init__(
            ability_id="turn_undead",
            name="Repreensão",
            description="Mortos-vivos em raio de 3 tiles devem fugir por 1 turno.",
            mana_cost=12,
            action_cost=1,
            cooldown=4,
            range_=3,
            area=3,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        pos = caster.get_component(Position)
        targets = self._get_targets_in_area(world, pos.x, pos.y, 3, tags=["enemy"])

        turned = 0
        for enemy in targets:
            if enemy.has_tag("undead"):
                if condition_system:
                    condition_system.apply_condition(enemy, Condition(
                        ConditionType.FEARED,
                        duration=1,
                        potency=0,
                        source=caster
                    ))
                turned += 1

        return {"turned": turned, "type": "turn_undead"}


class Bless(Ability):
    """Bênção: aliados em raio de 3 tiles ganham +1d4 em ataques por 3 turnos."""

    def __init__(self):
        super().__init__(
            ability_id="bless",
            name="Bênção",
            description="Aliados em raio de 3 tiles ganham +1d4 em ataques por 3 turnos.",
            mana_cost=15,
            action_cost=1,
            cooldown=4,
            range_=3,
            area=3,
            requires_target=False
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        pos = caster.get_component(Position)
        targets = self._get_targets_in_area(world, pos.x, pos.y, 3, tags=["player"])

        blessed = 0
        for ally in targets:
            stats = ally.get_component(Stats)
            stats.add_modifier("bencao", "hit_bonus", self.dice.roll("1d4"), duration=3)
            blessed += 1

        return {"blessed": blessed, "duration": 3, "type": "buff"}


class DivineProtection(Ability):
    """Proteção Divina: alvo ganha +2 CA e resistência a dano por 3 turnos."""

    def __init__(self):
        super().__init__(
            ability_id="divine_protection",
            name="Proteção Divina",
            description="Alvo ganha +2 CA e resistência a dano por 3 turnos.",
            mana_cost=18,
            action_cost=1,
            cooldown=4,
            range_=3,
            requires_target=True
        )

    def execute(self, caster, target=None, target_pos=None, world=None, condition_system=None):
        if not target:
            target = caster

        if condition_system:
            condition_system.apply_condition(target, Condition(
                ConditionType.PROTECTED,
                duration=3,
                potency=2,
                source=caster
            ))

        return {"target": target.name, "duration": 3, "type": "buff"}


# ═════════════════════════════════════════════════════════════
# REGISTRY
# ═════════════════════════════════════════════════════════════

class AbilityRegistry:
    """Registro central de todas as habilidades."""

    _abilities: Dict[str, type] = {}

    @classmethod
    def register(cls, ability_class: type):
        """Registra uma classe de habilidade."""
        instance = ability_class()
        cls._abilities[instance.ability_id] = ability_class
        return ability_class

    @classmethod
    def get(cls, ability_id: str) -> Optional[Ability]:
        """Retorna uma instância da habilidade pelo ID."""
        ability_class = cls._abilities.get(ability_id)
        if ability_class:
            return ability_class()
        return None

    @classmethod
    def get_class_abilities(cls, class_id: str) -> List[Ability]:
        """Retorna todas as habilidades de uma classe."""
        class_abilities = {
            "warrior": ["second_wind", "power_attack", "provoke"],
            "rogue": ["sneak_attack", "dash", "hide"],
            "mage": ["fireball", "shield", "frost_ray", "teleport"],
            "cleric": ["heal", "turn_undead", "bless", "divine_protection"],
        }

        ability_ids = class_abilities.get(class_id, [])
        return [cls.get(aid) for aid in ability_ids if cls.get(aid)]

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls._abilities.keys())


# Registra todas as habilidades
AbilityRegistry.register(SecondWind)
AbilityRegistry.register(PowerAttack)
AbilityRegistry.register(Provoke)
AbilityRegistry.register(SneakAttack)
AbilityRegistry.register(Dash)
AbilityRegistry.register(Hide)
AbilityRegistry.register(Fireball)
AbilityRegistry.register(ArcaneShield)
AbilityRegistry.register(FrostRay)
AbilityRegistry.register(Teleport)
AbilityRegistry.register(HealWounds)
AbilityRegistry.register(TurnUndead)
AbilityRegistry.register(Bless)
AbilityRegistry.register(DivineProtection)
