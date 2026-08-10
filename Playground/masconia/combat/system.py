"""
CombatSystem v2: combate tático completo com habilidades, condições e táticas.

Integra:
  • Rolagens D&D (d20 + mods, vantagem/desvantagem, críticos, fumbles)
  • Dano tipado com resistências/vulnerabilidades/imunidades
  • Habilidades de classe (combat/abilities.py)
  • Condições de status (combat/conditions.py)
  • Táticas de posicionamento (combat/tactics.py)
  • Cobertura, flanking, altura, backstab
  • Magias de área com efeitos em múltiplos alvos
  • XP, loot, level up

Arquitetura:
  • CombatSystem orquestra todos os subsistemas.
  • Cada subsistema (abilities, conditions, tactics) é independente
    mas coordenado pelo CombatSystem.
  • Eventos ECS comunicam resultados para UI e outros systems.
"""
import json
import os
from typing import Optional, Dict, Any, List, Tuple

from ecs.world import World, Event
from components.position import Position
from components.stats import Stats
from components.fighter import Fighter
from components.inventory import Inventory
from components.renderable import Renderable
from components.ai import AI
from utils.dice import DiceRoller
from utils.constants import DamageType
from config.settings import CRIT_THRESHOLD, FUMBLE_THRESHOLD

from combat.conditions import ConditionSystem, Condition, ConditionType
from combat.abilities import AbilityRegistry, Ability
from combat.tactics import TacticsSystem


class CombatSystem:
    """
    System de combate tático completo.

    Attributes:
        world: Referência ao World ECS.
        dice: Instância de DiceRoller.
        combat_log: Histórico de ações.
        animation_queue: Fila de animações.
        condition_system: System de condições.
        tactics_system: System de táticas.
        _items_data: Dados de itens para loot.
    """

    def __init__(self, seed: Optional[int] = None):
        self.world: Optional[World] = None
        self.dice = DiceRoller(seed)
        self.combat_log: List[str] = []
        self.animation_queue: List[Dict] = []
        self.condition_system = ConditionSystem()
        self.tactics_system = TacticsSystem()
        self._items_data = self._load_items_data()
        self._in_combat = False
        self._combat_entities: List = []
        self._turn_order: List = []
        self._current_turn_index = 0

    def _load_items_data(self) -> Dict:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "items.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def set_seed(self, seed: int):
        self.dice.set_seed(seed)
        self.condition_system.dice.set_seed(seed)

    def set_world(self, world: World):
        """Injeta referência ao World ECS."""
        self.world = world
        self.condition_system.world = world

    def set_dungeon_map(self, dungeon_map):
        """Injeta referência ao mapa para táticas."""
        self.tactics_system.set_dungeon_map(dungeon_map)

    # ── Turnos de Combate ──────────────────────────────────────

    def start_combat(self, entities: List):
        """Inicia um combate com as entidades envolvidas."""
        self._in_combat = True
        self._combat_entities = [e for e in entities if e.active]

        # Ordem de iniciativa: d20 + mod DEX
        initiative = []
        for entity in self._combat_entities:
            stats = entity.get_component(Stats)
            if stats:
                roll, _ = self.dice.d20()
                init = roll + stats.dex_mod
                initiative.append((init, entity))

        initiative.sort(key=lambda x: x[0], reverse=True)
        self._turn_order = [e for _, e in initiative]
        self._current_turn_index = 0

        self.combat_log.append("=== COMBATE INICIADO ===")
        for i, (init, entity) in enumerate(initiative):
            self.combat_log.append(f"  {i+1}. {entity.name} (INI: {init})")

    def end_combat(self):
        """Finaliza o combate atual."""
        self._in_combat = False
        self._combat_entities = []
        self._turn_order = []
        self._current_turn_index = 0
        self.combat_log.append("=== COMBATE ENCERRADO ===")

    def is_in_combat(self) -> bool:
        return self._in_combat

    def get_current_turn_entity(self):
        """Retorna a entidade do turno atual."""
        if self._turn_order and 0 <= self._current_turn_index < len(self._turn_order):
            return self._turn_order[self._current_turn_index]
        return None

    def next_turn(self):
        """Avança para o próximo turno."""
        if not self._in_combat:
            return

        # Processa condições da entidade atual
        current = self.get_current_turn_entity()
        if current:
            self.condition_system.process_turn(current)
            fighter = current.get_component(Fighter)
            if fighter:
                fighter.reset_turn()

        # Avança índice
        self._current_turn_index = (self._current_turn_index + 1) % len(self._turn_order)

        # Remove entidades mortas
        self._turn_order = [e for e in self._turn_order if e.active and e.get_component(Stats) and e.get_component(Stats).is_alive()]

        if not self._turn_order:
            self.end_combat()

    # ── Ataques ────────────────────────────────────────────────

    def process_attack(self, attacker, target):
        """Processa um ataque completo."""
        attacker_stats = attacker.get_component(Stats)
        attacker_fighter = attacker.get_component(Fighter)
        target_stats = target.get_component(Stats)
        target_fighter = target.get_component(Fighter)

        if not all([attacker_stats, attacker_fighter, target_stats, target_fighter]):
            return

        if not attacker_stats.is_alive() or not target_stats.is_alive():
            return

        # Gasta ação
        if not attacker_fighter.use_action():
            return

        # Seleciona ataque
        attack = self._select_attack(attacker)
        if not attack:
            return

        # Calcula modificadores táticos
        tactical_mods = self.tactics_system.calculate_attack_modifiers(attacker, target)

        # Rolagem de ataque
        hit_bonus = attack.get("hit_bonus", 0)
        stat_mod = self._get_attack_stat_mod(attacker, attack)
        proficiency = attacker_stats.proficiency_bonus

        # Aplica modificadores táticos
        hit_bonus += tactical_mods["hit_bonus"]

        # Vantagem/desvantagem
        advantage, disadvantage = self._check_advantage_disadvantage(attacker, target)

        # Aplica vantagem de táticas
        if tactical_mods["advantage"]:
            advantage = True
        if tactical_mods["disadvantage"]:
            disadvantage = True

        # Verifica condições do atacante
        cond_effects = self.condition_system.get_condition_effects(attacker)
        if cond_effects.get("disadvantage_attack"):
            disadvantage = True
        if cond_effects.get("advantage_attack"):
            advantage = True
        if cond_effects.get("cannot_act"):
            self.combat_log.append(f"{attacker.name} está atordoado e não pode atacar!")
            return

        roll_result, natural_roll = self.dice.d20(advantage=advantage, disadvantage=disadvantage)
        total_attack = roll_result + hit_bonus + stat_mod + proficiency

        # Log
        adv_str = " (vantagem)" if advantage else " (desvantagem)" if disadvantage else ""
        log_msg = f"{attacker.name} ataca {target.name}: {natural_roll}{adv_str} + {hit_bonus + stat_mod + proficiency} = {total_attack} vs CA {target_stats.ac}"
        self.combat_log.append(log_msg)

        # Crítico ou fumble
        is_crit = self.dice.is_critical(natural_roll)
        is_fumble = self.dice.is_fumble(natural_roll)

        if is_fumble:
            self._handle_fumble(attacker, target)
            return

        # Aplica bônus de cobertura à CA do alvo
        target_ca = target_stats.ac + tactical_mods["ca_bonus"]

        if is_crit or total_attack >= target_ca:
            self._resolve_damage(attacker, target, attack, is_crit, tactical_mods)
        else:
            self.world.emit(Event("attack_missed", {
                "attacker": attacker,
                "target": target,
                "roll": total_attack,
                "needed": target_ca
            }))
            self.combat_log.append(f"  → Errou!")

    def _select_attack(self, attacker) -> Optional[Dict]:
        """Seleciona o melhor ataque disponível."""
        fighter = attacker.get_component(Fighter)
        if not fighter or not fighter.attacks:
            return {"name": "Ataque Desarmado", "hit_bonus": 0, "damage": "1d4", "damage_type": "bludgeoning"}
        return fighter.attacks[0]

    def _get_attack_stat_mod(self, attacker, attack: Dict) -> int:
        """Determina modificador de atributo para o ataque."""
        stats = attacker.get_component(Stats)
        if not stats:
            return 0

        if attack.get("finesse"):
            return max(stats.str_mod, stats.dex_mod)

        damage_type = attack.get("damage_type", "")
        if damage_type in ["piercing"] and attack.get("range"):
            return stats.dex_mod

        return stats.str_mod

    def _check_advantage_disadvantage(self, attacker, target) -> Tuple[bool, bool]:
        """Verifica vantagem/desvantagem natural."""
        advantage = False
        disadvantage = False

        target_fighter = target.get_component(Fighter)
        if target_fighter:
            if target_fighter.has_condition("Atordoado") or target_fighter.has_condition("Caído"):
                advantage = True

        # Flanking
        _, flanking_with = self.tactics_system._check_flanking(attacker, target)
        if flanking_with:
            advantage = True

        # Invisível
        if self.condition_system.has_condition(attacker, ConditionType.INVISIBLE):
            advantage = True

        # Cego
        if self.condition_system.has_condition(attacker, ConditionType.BLINDED):
            disadvantage = True

        return advantage, disadvantage

    def _resolve_damage(self, attacker, target, attack: Dict, is_crit: bool,
                        tactical_mods: Dict):
        """Calcula e aplica dano."""
        stats = attacker.get_component(Stats)
        target_stats = target.get_component(Stats)
        target_fighter = target.get_component(Fighter)

        # Dano base
        damage_expr = attack.get("damage", "1d4")
        base_damage = self.dice.roll(damage_expr)

        # Modificador de atributo
        stat_mod = self._get_attack_stat_mod(attacker, attack)
        base_damage += stat_mod

        # Dano extra da arma
        extra_damage = 0
        extra_type = None
        if "extra_damage" in attack:
            extra_damage = self.dice.roll(attack["extra_damage"])
            extra_type = attack.get("extra_type")

        # Dano tático (backstab)
        base_damage += tactical_mods.get("damage_bonus", 0)

        # Crítico
        if is_crit:
            base_damage = self.dice.roll(damage_expr) + base_damage
            if extra_damage > 0:
                extra_damage *= 2

        # Condições do atacante
        cond_effects = self.condition_system.get_condition_effects(attacker)
        base_damage = int(base_damage * cond_effects.get("damage_multiplier", 1.0))

        # Tipo de dano
        damage_type_str = attack.get("damage_type", "bludgeoning")
        damage_type = self._str_to_damage_type(damage_type_str)

        # Aplica resistências
        final_damage = self.dice.apply_damage_modifiers(
            base_damage, damage_type,
            target_fighter.resistances,
            target_fighter.weaknesses,
            target_fighter.immunities
        )

        # Dano extra
        if extra_damage > 0 and extra_type:
            extra_dmg_type = self._str_to_damage_type(extra_type)
            extra_final = self.dice.apply_damage_modifiers(
                extra_damage, extra_dmg_type,
                target_fighter.resistances,
                target_fighter.weaknesses,
                target_fighter.immunities
            )
            final_damage += extra_final

        # Aplica dano
        actual_damage = target_stats.take_damage(final_damage)

        # Log
        crit_str = " CRÍTICO!" if is_crit else ""
        self.combat_log.append(f"  → Acertou{crit_str}! {actual_damage} de dano ({damage_type_str})")

        # Eventos
        self.world.emit(Event("damage_dealt", {
            "attacker": attacker,
            "target": target,
            "damage": actual_damage,
            "type": damage_type,
            "is_critical": is_crit,
            "is_fatal": not target_stats.is_alive()
        }))

        # Aplica condições do ataque (veneno, etc.)
        self._apply_attack_conditions(attacker, target, attack)

        # Animação
        self.animation_queue.append({
            "type": "attack",
            "attacker": attacker,
            "target": target,
            "damage": actual_damage,
            "is_critical": is_crit
        })

        # Verifica morte
        if not target_stats.is_alive():
            self._handle_death(attacker, target)

    def _apply_attack_conditions(self, attacker, target, attack: Dict):
        """Aplica condições do ataque (veneno em lâminas, etc.)."""
        # Chance de aplicar poison em ataques de veneno
        if attack.get("damage_type") == "poison":
            if self.dice.roll("1d100") <= 30:
                self.condition_system.apply_condition(target, Condition(
                    ConditionType.POISONED,
                    duration=3,
                    potency=1,
                    source=attacker
                ))

        # Chance de sangramento em ataques cortantes
        if attack.get("damage_type") == "slashing":
            if self.dice.roll("1d100") <= 15:
                self.condition_system.apply_condition(target, Condition(
                    ConditionType.BLEEDING,
                    duration=3,
                    potency=1,
                    source=attacker
                ))

    def _handle_fumble(self, attacker, target):
        """Lida com fumble natural 1."""
        self.combat_log.append(f"  → FALHA CRÍTICA!")

        # Tabela de fumbles
        fumble_roll = self.dice.roll("1d6")
        if fumble_roll == 1:
            self.combat_log.append(f"    Tropeçou! Perde movimento.")
            fighter = attacker.get_component(Fighter)
            if fighter:
                fighter.movement_left = 0
        elif fumble_roll == 2:
            self.combat_log.append(f"    Derrubou a arma! Próximo ataque com desvantagem.")
            self.condition_system.apply_condition(attacker, Condition(
                ConditionType.WEAKENED,
                duration=1,
                potency=0
            ))
        elif fumble_roll == 3:
            self.combat_log.append(f"    Acertou aliado próximo!")
            # TODO: implementar friendly fire
        else:
            self.combat_log.append(f"    Perdeu o equilíbrio!")

        self.world.emit(Event("attack_fumbled", {
            "attacker": attacker,
            "target": target,
            "fumble_type": fumble_roll
        }))

    def _handle_death(self, killer, victim):
        """Lida com a morte de uma entidade."""
        self.combat_log.append(f"  → {victim.name} foi derrotado!")

        # XP
        killer_stats = killer.get_component(Stats)
        victim_stats = victim.get_component(Stats)
        if killer_stats and victim_stats:
            xp_gain = max(10, victim_stats.level * 15)
            leveled_up = killer_stats.add_xp(xp_gain)
            self.world.emit(Event("xp_gained", {
                "entity": killer,
                "amount": xp_gain,
                "leveled_up": leveled_up
            }))

        # Loot
        self._drop_loot(victim)

        # Marca para destruição
        victim.destroy()

        self.world.emit(Event("entity_died", {
            "killer": killer,
            "victim": victim
        }))

    def _drop_loot(self, victim):
        """Gera loot ao derrotar um inimigo."""
        victim_inv = victim.get_component(Inventory)
        if victim_inv:
            gold = self.dice.roll("1d20") * 5
            victim_inv.add_gold(gold)
            self.world.emit(Event("loot_dropped", {
                "entity": victim,
                "gold": gold
            }))

    # ── Habilidades ────────────────────────────────────────────

    def use_ability(self, caster, ability_id: str, target=None,
                    target_pos: Tuple[int, int] = None) -> Dict[str, Any]:
        """Usa uma habilidade pelo ID."""
        ability = AbilityRegistry.get(ability_id)
        if not ability:
            return {"success": False, "error": f"Habilidade não encontrada: {ability_id}"}

        return ability.use(caster, target, target_pos, self.world, self.condition_system)

    def get_available_abilities(self, entity) -> List[Ability]:
        """Retorna habilidades disponíveis da entidade."""
        # Detecta classe
        class_id = None
        if entity.has_tag("player"):
            # Busca classe nos dados do jogador
            # Simplificado: inferimos pela entidade
            pass

        # Retorna habilidades que podem ser usadas
        abilities = []
        if class_id:
            for ability in AbilityRegistry.get_class_abilities(class_id):
                can_use, _ = ability.can_use(entity)
                if can_use:
                    abilities.append(ability)

        return abilities

    # ── Utilitários ──────────────────────────────────────────

    def _str_to_damage_type(self, s: str) -> DamageType:
        mapping = {
            "slashing": DamageType.SLASHING, "piercing": DamageType.PIERCING,
            "bludgeoning": DamageType.BLUDGEONING, "fire": DamageType.FIRE,
            "cold": DamageType.COLD, "lightning": DamageType.LIGHTNING,
            "acid": DamageType.ACID, "poison": DamageType.POISON,
            "necrotic": DamageType.NECROTIC, "radiant": DamageType.RADIANT,
            "force": DamageType.FORCE, "thunder": DamageType.THUNDER,
            "psychic": DamageType.PSYCHIC,
        }
        return mapping.get(s.lower(), DamageType.BLUDGEONING)

    def get_combat_log(self, limit: int = 50) -> List[str]:
        return self.combat_log[-limit:]

    def clear_log(self):
        self.combat_log.clear()

    def __repr__(self):
        return f"CombatSystem(in_combat={self._in_combat}, log={len(self.combat_log)})"
