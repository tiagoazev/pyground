"""
Componente de Inteligência Artificial de inimigos.

Define o comportamento tático do inimigo:
  • Tipo de IA (melee_aggressive, hit_and_run, ranged, etc.)
  • Estado atual (idle, chasing, attacking, fleeing)
  • Fase de boss (para inimigos com múltiplas fases)
  • Memória de última posição do jogador
  • Cooldowns de habilidades

A lógica de decisão fica no AISystem; este componente apenas
armazena o estado e parâmetros de configuração.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AI:
    """
    Configuração e estado de IA de um inimigo.

    Attributes:
        behavior_type: Tipo de comportamento base.
        current_state: Estado atual da máquina de estados.
        aggro_range: Distância em tiles para detectar o jogador.
        flee_threshold: % de HP para começar a fugir (0.0 = nunca foge).
        preferred_range: Distância ideal do alvo (0 = melee, >0 = ranged).
        last_known_player_pos: Última posição vista do jogador.
        ability_cooldowns: Dict ability_id → turnos restantes.
        phase_index: Índice da fase atual (para bosses).
        has_seen_player: Se já detectou o jogador alguma vez.
        turn_counter: Contador de turnos para padrões de ataque.
    """
    behavior_type: str = "melee_aggressive"
    current_state: str = "idle"
    aggro_range: int = 8
    flee_threshold: float = 0.25
    preferred_range: int = 0
    last_known_player_pos: Optional[tuple] = None
    ability_cooldowns: Dict[str, int] = field(default_factory=dict)
    phase_index: int = 0
    has_seen_player: bool = False
    turn_counter: int = 0

    def set_cooldown(self, ability_id: str, turns: int):
        self.ability_cooldowns[ability_id] = turns

    def tick_cooldowns(self):
        """Decrementa todos os cooldowns em 1 turno."""
        for k in list(self.ability_cooldowns.keys()):
            self.ability_cooldowns[k] -= 1
            if self.ability_cooldowns[k] <= 0:
                del self.ability_cooldowns[k]

    def is_on_cooldown(self, ability_id: str) -> bool:
        return ability_id in self.ability_cooldowns

    def __repr__(self):
        return f"AI({self.behavior_type}, state={self.current_state}, phase={self.phase_index})"
