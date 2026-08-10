"""
AISystem: controla o comportamento de todos os inimigos.

Responsabilidades:
  • Percepção: detectar jogador dentro do aggro_range
  • Decisão: escolher ação baseada no behavior_type e estado atual
  • Execução: emitir eventos de movimento/ataque para outros systems
  • Boss phases: transicionar entre fases baseado em % de HP
  • Cooldowns: gerenciar recarga de habilidades especiais

Tipos de IA implementados:
  • melee_aggressive: Corre até o jogador e ataca.
  • melee_slow: Move-se a cada 2 turnos, mas dano alto.
  • hit_and_run: Ataque e recuo, mantém distância.
  • ranged: Mantém distância ideal, ataca à distância.
  • swarm: Coordena com outros inimigos próximos.
  • boss_phases: Múltiplas fases com comportamentos diferentes.
  • defensive: Fica atrás de cobertura, usa habilidades defensivas.

Por que separar IA em system?
  → Todas as decisões de IA são centralizadas.
  → Facilita debug (pode pausar e inspecionar decisões).
  → Permite "dificuldade dinâmica" ajustando parâmetros globais.
"""
import random
from typing import Optional, List, Tuple

from ecs.world import World, Event
from components.position import Position
from components.stats import Stats
from components.ai import AI
from components.fighter import Fighter
from systems.movement_system import MovementSystem


class AISystem:
    """
    System de inteligência artificial dos inimigos.

    Attributes:
        world: Referência ao World ECS.
        movement_system: Referência para pathfinding.
        combat_system: Referência para emitir ataques.
    """

    def __init__(self, movement_system: MovementSystem):
        self.world: Optional[World] = None
        self.movement_system = movement_system
        self.combat_system = None  # Injetado depois

    def set_combat_system(self, combat_system):
        self.combat_system = combat_system

    def update(self, dt: float):
        """
        Executa o turno de todos os inimigos.
        Chamado durante o estado ENEMY_TURN.
        """
        enemies = self.world.query(Position, Stats, AI, Fighter, tags=["enemy"])
        player = self.world.query_one(Position, Stats, tags=["player"])

        if not player:
            return

        player_pos = player.get_component(Position)

        for enemy in enemies:
            if not enemy.active:
                continue
            self._process_enemy_turn(enemy, player, player_pos)

    def _process_enemy_turn(self, enemy, player, player_pos: Position):
        """Processa o turno de um único inimigo."""
        ai = enemy.get_component(AI)
        stats = enemy.get_component(Stats)
        fighter = enemy.get_component(Fighter)
        pos = enemy.get_component(Position)

        if not stats.is_alive():
            return

        # Reseta ações do turno
        fighter.reset_turn()
        ai.tick_cooldowns()
        ai.turn_counter += 1

        # Atualiza fase de boss se aplicável
        if ai.behavior_type == "boss_phases":
            self._update_boss_phase(enemy, ai, stats)

        # Percepção: vê o jogador?
        dist = pos.distance_to(player_pos)
        can_see = dist <= ai.aggro_range

        if can_see:
            ai.has_seen_player = True
            ai.last_known_player_pos = (player_pos.x, player_pos.y)

        # Se nunca viu o jogador, fica idle
        if not ai.has_seen_player:
            ai.current_state = "idle"
            return

        # Decide ação baseada no behavior_type
        handler = getattr(self, f"_behavior_{ai.behavior_type}", self._behavior_melee_aggressive)
        handler(enemy, player, pos, player_pos, ai, stats, fighter, dist)

    def _update_boss_phase(self, enemy, ai: AI, stats: Stats):
        """Verifica se o boss deve mudar de fase baseado no HP."""
        from components.fighter import Fighter
        fighter = enemy.get_component(Fighter)
        if not fighter or not fighter.phases:
            return

        hp_ratio = stats.hp / stats.max_hp
        for i, phase in enumerate(fighter.phases):
            if hp_ratio <= phase.get("hp_threshold", 1.0):
                if ai.phase_index != i:
                    ai.phase_index = i
                    ai.current_state = phase.get("behavior", ai.current_state)
                    # Emite evento de mudança de fase
                    self.world.emit(Event("boss_phase_changed", {
                        "entity": enemy,
                        "phase": i,
                        "behavior": ai.current_state
                    }))
                break

    def _behavior_melee_aggressive(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Corre até o jogador e ataca."""
        if dist <= 1:
            # Ataca
            ai.current_state = "attacking"
            self._attempt_attack(enemy, player)
        else:
            # Move-se em direção ao jogador
            ai.current_state = "chasing"
            self._move_towards(enemy, pos, player_pos, fighter)

    def _behavior_melee_slow(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Move-se a cada 2 turnos, mas ataca quando próximo."""
        if dist <= 1:
            ai.current_state = "attacking"
            self._attempt_attack(enemy, player)
        elif ai.turn_counter % 2 == 0:
            ai.current_state = "chasing"
            self._move_towards(enemy, pos, player_pos, fighter)
        else:
            ai.current_state = "waiting"

    def _behavior_hit_and_run(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Ataca e recua para manter distância."""
        if dist <= 1:
            # Ataca e recua
            self._attempt_attack(enemy, player)
            # Move-se para longe
            self._move_away(enemy, pos, player_pos, fighter)
            ai.current_state = "retreating"
        elif dist > ai.preferred_range + 1:
            # Aproxima-se
            self._move_towards(enemy, pos, player_pos, fighter)
            ai.current_state = "approaching"
        else:
            # Na distância ideal, ataca
            self._attempt_attack(enemy, player)
            ai.current_state = "attacking"

    def _behavior_ranged(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Mantém distância e ataca à distância."""
        if dist <= 1:
            # Muito perto, recua
            self._move_away(enemy, pos, player_pos, fighter)
            ai.current_state = "retreating"
        elif dist <= ai.preferred_range:
            # Distância ideal, ataca
            self._attempt_attack(enemy, player)
            ai.current_state = "attacking"
        else:
            # Aproxima-se
            self._move_towards(enemy, pos, player_pos, fighter)
            ai.current_state = "approaching"

    def _behavior_swarm(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Coordena com outros inimigos próximos para cercar o jogador."""
        # Conta quantos inimigos estão próximos do jogador
        nearby_enemies = sum(
            1 for e in self.world.query(Position, tags=["enemy"])
            if e != enemy and e.get_component(Position).distance_to(player_pos) <= 3
        )

        if dist <= 1:
            self._attempt_attack(enemy, player)
        elif nearby_enemies < 2:
            # Poucos aliados próximos, aproxima-se
            self._move_towards(enemy, pos, player_pos, fighter)
        else:
            # Já tem aliados suficientes, fica na retaguarda
            self._move_away(enemy, pos, player_pos, fighter)

    def _behavior_boss_phases(self, enemy, player, pos, player_pos, ai, stats, fighter, dist):
        """Boss com fases dinâmicas — delega para o comportamento da fase atual."""
        phase_behavior = ai.current_state
        if phase_behavior == "aggressive_melee" or phase_behavior == "aggressive":
            self._behavior_melee_aggressive(enemy, player, pos, player_pos, ai, stats, fighter, dist)
        elif phase_behavior == "ranged":
            ai.preferred_range = 4
            self._behavior_ranged(enemy, player, pos, player_pos, ai, stats, fighter, dist)
        elif phase_behavior == "defensive":
            # Fica parado, usa habilidades defensivas
            if not ai.is_on_cooldown("defend"):
                self.world.emit(Event("ai_ability", {"entity": enemy, "ability": "defend"}))
                ai.set_cooldown("defend", 3)
            elif dist <= 1:
                self._attempt_attack(enemy, player)
        elif phase_behavior == "summoner":
            # Invoca aliados
            if not ai.is_on_cooldown("summon"):
                self.world.emit(Event("ai_ability", {"entity": enemy, "ability": "summon"}))
                ai.set_cooldown("summon", 4)
            self._behavior_ranged(enemy, player, pos, player_pos, ai, stats, fighter, dist)
        elif phase_behavior == "desperate":
            # HP baixo, ataca freneticamente
            if dist <= 1:
                self._attempt_attack(enemy, player)
                # Ataque extra se possível
                if fighter.use_bonus_action():
                    self._attempt_attack(enemy, player)
            else:
                self._move_towards(enemy, pos, player_pos, fighter)
        elif phase_behavior == "flying":
            # Ignora terreno, move-se livremente
            ai.preferred_range = 5
            self._behavior_ranged(enemy, player, pos, player_pos, ai, stats, fighter, dist)
        else:
            self._behavior_melee_aggressive(enemy, player, pos, player_pos, ai, stats, fighter, dist)

    def _move_towards(self, enemy, pos: Position, target: Position, fighter: Fighter):
        """Move a entidade em direção ao alvo usando pathfinding."""
        path = self.movement_system.find_path(
            (pos.x, pos.y), (target.x, target.y),
            max_steps=fighter.movement_left
        )
        if path:
            next_tile = path[0]
            dx = next_tile[0] - pos.x
            dy = next_tile[1] - pos.y
            self.movement_system.move_entity(enemy, dx, dy)

    def _move_away(self, enemy, pos: Position, target: Position, fighter: Fighter):
        """Move a entidade para longe do alvo."""
        # Direção oposta
        dx = 0
        dy = 0
        if pos.x < target.x:
            dx = -1
        elif pos.x > target.x:
            dx = 1
        if pos.y < target.y:
            dy = -1
        elif pos.y > target.y:
            dy = 1

        # Tenta mover na direção oposta
        if self.movement_system.can_move_to(pos.x + dx, pos.y + dy, enemy):
            self.movement_system.move_entity(enemy, dx, dy)
        else:
            # Tenta direções alternativas
            for adx, ady in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                if self.movement_system.can_move_to(pos.x + adx, pos.y + ady, enemy):
                    self.movement_system.move_entity(enemy, adx, ady)
                    break

    def _attempt_attack(self, enemy, target):
        """Emite evento de ataque para o CombatSystem processar."""
        if self.combat_system:
            self.combat_system.process_attack(enemy, target)
        else:
            self.world.emit(Event("attack_request", {
                "attacker": enemy,
                "target": target
            }))

    def __repr__(self):
        return f"AISystem(enemies={len(self.world.query(AI, tags=['enemy'])) if self.world else 0})"
