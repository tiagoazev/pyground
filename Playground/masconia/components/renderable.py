"""
Componente de renderização.

Armazena sprite, cor de fallback (quando sprite não carregou),
ordem de renderização (z-index), e flags de visibilidade.

Nota: NÃO contém a Surface do Pygame diretamente para evitar
problemas de serialização e testabilidade. O RenderSystem
resolve sprite_path → Surface em cache.
"""
from dataclasses import dataclass, field
from typing import Tuple, Optional


@dataclass
class Renderable:
    """
    Dados visuais de uma entidade.

    Attributes:
        sprite_path: Caminho relativo para o sprite (ex: "sprites/warrior_32.png").
        color: Cor de fallback (R, G, B) se sprite não estiver disponível.
        z_index: Ordem de render (menor = atrás, maior = na frente).
        visible: Se False, não é renderizado.
        alpha: Transparência (0-255).
        animation_state: Estado atual da animação ("idle", "walk", "attack", "hurt", "dead").
        animation_frame: Frame atual da animação.
        animation_timer: Tempo acumulado para troca de frame.
        offset_x, offset_y: Offset em pixels para animação de movimento/impacto.
    """
    sprite_path: str = ""
    color: Tuple[int, int, int] = (200, 200, 200)
    z_index: int = 10
    visible: bool = True
    alpha: int = 255
    animation_state: str = "idle"
    animation_frame: int = 0
    animation_timer: float = 0.0
    offset_x: int = 0
    offset_y: int = 0

    def set_animation(self, state: str):
        """Muda o estado de animação e reseta o frame."""
        if self.animation_state != state:
            self.animation_state = state
            self.animation_frame = 0
            self.animation_timer = 0.0
