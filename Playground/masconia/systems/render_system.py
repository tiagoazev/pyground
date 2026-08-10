"""
RenderSystem: desenha todas as entidades com Position + Renderable.

Responsabilidades:
  • Cache de sprites (evita recarregar a mesma imagem toda frame)
  • Ordenação por z-index (entidades mais próximas na frente)
  • Conversão tile→pixel
  • Efeitos visuais (highlight de movimento, range de ataque)
  • Fog of War (FOV) — só renderiza tiles/entidades visíveis
  • UI overlay (barras de HP, nomes, etc.)

Por que separar renderização em system?
  → Centraliza toda a lógica de draw em um único lugar.
  → Facilita adicionar efeitos globais (shaders, screen shake, bloom).
  → Permite desacoplar a lógica do jogo da engine gráfica.
"""
import os
from typing import Dict, Optional

import pygame

from ecs.world import World, Event
from components.position import Position
from components.renderable import Renderable
from components.stats import Stats
from config.settings import TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, SPRITES_DIR


class RenderSystem:
    """
    System de renderização.

    Attributes:
        world: Referência ao World ECS.
        screen: Surface principal do Pygame.
        camera_offset: Offset da câmera (segue o jogador).
        sprite_cache: Dict path → Surface (cache de sprites carregados).
        font: Fonte para textos na UI.
        show_debug: Se True, desenha grid e informações de debug.
    """

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.world: Optional[World] = None
        self.screen = screen
        self.camera_offset = (0, 0)
        self.sprite_cache: Dict[str, pygame.Surface] = {}
        self.font = font
        self.show_debug = False
        self._missing_sprite = None  # Surface de fallback

    def _get_sprite(self, path: str) -> pygame.Surface:
        """Carrega sprite do cache, ou cria um quadrado colorido se não existir."""
        if path in self.sprite_cache:
            return self.sprite_cache[path]

        full_path = os.path.join(SPRITES_DIR, path)
        if os.path.exists(full_path):
            try:
                sprite = pygame.image.load(full_path).convert_alpha()
                sprite = pygame.transform.scale(sprite, (TILE_SIZE, TILE_SIZE))
                self.sprite_cache[path] = sprite
                return sprite
            except pygame.error:
                pass

        # Fallback: quadrado colorido
        if self._missing_sprite is None:
            self._missing_sprite = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            self._missing_sprite.fill((255, 0, 255, 200))
        return self._missing_sprite

    def _world_to_screen(self, x: int, y: int) -> tuple:
        """Converte coordenadas de tile para pixels na tela."""
        return (
            x * TILE_SIZE - self.camera_offset[0],
            y * TILE_SIZE - self.camera_offset[1]
        )

    def update(self, dt: float):
        """Atualiza animações (troca de frames baseado em timer)."""
        for entity in self.world.query(Position, Renderable):
            rend = entity.get_component(Renderable)
            if not rend.visible:
                continue
            rend.animation_timer += dt
            # Troca frame a cada 0.15s
            if rend.animation_timer > 0.15:
                rend.animation_timer = 0
                rend.animation_frame = (rend.animation_frame + 1) % 4

    def render(self, screen: pygame.Surface):
        """
        Renderiza o frame completo.
        Ordem: tiles → sombras → entidades → UI.
        """
        # 1. Fundo
        screen.fill((20, 20, 30))

        # 2. Coleta entidades renderizáveis
        renderables = []
        for entity in self.world.query(Position, Renderable):
            pos = entity.get_component(Position)
            rend = entity.get_component(Renderable)
            if not rend.visible:
                continue
            renderables.append((rend.z_index, pos, rend, entity))

        # Ordena por z-index
        renderables.sort(key=lambda x: x[0])

        # 3. Desenha tiles do mapa (se houver componente de mapa)
        self._render_map(screen)

        # 4. Desenha entidades
        for _, pos, rend, entity in renderables:
            sx, sy = self._world_to_screen(pos.x, pos.y)
            # Só renderiza se estiver na tela (+ margem de 1 tile)
            if -TILE_SIZE <= sx < SCREEN_WIDTH + TILE_SIZE and -TILE_SIZE <= sy < SCREEN_HEIGHT + TILE_SIZE:
                sprite = self._get_sprite(rend.sprite_path)
                # Aplica offset de animação
                draw_x = sx + rend.offset_x
                draw_y = sy + rend.offset_y
                # Aplica alpha se necessário
                if rend.alpha < 255:
                    sprite_copy = sprite.copy()
                    sprite_copy.set_alpha(rend.alpha)
                    screen.blit(sprite_copy, (draw_x, draw_y))
                else:
                    screen.blit(sprite, (draw_x, draw_y))

                # Barra de HP sobre a entidade
                stats = entity.get_component(Stats)
                if stats:
                    self._draw_hp_bar(screen, draw_x, draw_y, stats)

        # 5. UI overlay
        self._render_ui(screen)

        if self.show_debug:
            self._render_debug(screen)

    def _render_map(self, screen: pygame.Surface):
        """Renderiza o mapa da masmorra (placeholder — integrado com DungeonMap)."""
        # O mapa é renderizado pelo DungeonSystem; este método é um hook
        # para efeitos visuais globais (partículas, iluminação dinâmica).
        pass

    def _draw_hp_bar(self, screen: pygame.Surface, x: int, y: int, stats: Stats):
        """Desenha uma mini barra de HP sobre a entidade."""
        bar_width = TILE_SIZE - 4
        bar_height = 4
        bar_x = x + 2
        bar_y = y - 6

        # Fundo vermelho
        pygame.draw.rect(screen, (200, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        # HP atual verde
        hp_ratio = stats.hp / max(stats.max_hp, 1)
        pygame.draw.rect(
            screen, (50, 150, 50),
            (bar_x, bar_y, int(bar_width * hp_ratio), bar_height)
        )

    def _render_ui(self, screen: pygame.Surface):
        """Renderiza UI básica (placeholder para HUD completo)."""
        # Busca jogador para mostrar stats
        from components.stats import Stats
        player = self.world.query_one(Stats, tags=["player"])
        if player:
            stats = player.get_component(Stats)
            inv = player.get_component("Inventory")  # type: ignore

            # Painel de stats
            panel_y = SCREEN_HEIGHT - 80
            pygame.draw.rect(screen, (30, 30, 40), (10, panel_y, 200, 70))
            pygame.draw.rect(screen, (80, 80, 100), (10, panel_y, 200, 70), 1)

            lines = [
                f"HP: {stats.hp}/{stats.max_hp}",
                f"MP: {stats.mp}/{stats.max_mp}",
                f"LV: {stats.level}  AC: {stats.ac}",
            ]
            if inv:
                lines.append(f"Ouro: {inv.gold}")

            for i, line in enumerate(lines):
                text = self.font.render(line, True, (220, 220, 220))
                screen.blit(text, (15, panel_y + 5 + i * 16))

    def _render_debug(self, screen: pygame.Surface):
        """Informações de debug."""
        debug_text = f"Entities: {len(self.world.entities)} | Camera: {self.camera_offset}"
        text = self.font.render(debug_text, True, (0, 255, 0))
        screen.blit(text, (10, 10))

    def set_camera_target(self, position: Position):
        """Centraliza a câmera em uma posição (tipicamente o jogador)."""
        center_x = position.x * TILE_SIZE - SCREEN_WIDTH // 2 + TILE_SIZE // 2
        center_y = position.y * TILE_SIZE - SCREEN_HEIGHT // 2 + TILE_SIZE // 2
        self.camera_offset = (center_x, center_y)

    def highlight_tiles(self, screen: pygame.Surface, tiles: list, color: tuple):
        """Destaca tiles específicos (range de movimento/ataque)."""
        overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        overlay.fill(color)
        for tx, ty in tiles:
            sx, sy = self._world_to_screen(tx, ty)
            if -TILE_SIZE <= sx < SCREEN_WIDTH + TILE_SIZE and -TILE_SIZE <= sy < SCREEN_HEIGHT + TILE_SIZE:
                screen.blit(overlay, (sx, sy))

    def __repr__(self):
        return f"RenderSystem(sprites_cached={len(self.sprite_cache)})"
