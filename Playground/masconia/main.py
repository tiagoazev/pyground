#!/usr/bin/env python3
"""
Masconia: Chronicles of the Mysterious Smoke

Entry point do jogo. Inicializa Pygame, cria a janela,
e executa o loop principal da máquina de estados.

Uso:
    python main.py

Dependências:
    pygame-ce
"""
import sys
import os

# Adiciona o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pygame
except ImportError:
    print("Erro: pygame-ce não está instalado.")
    print("Instale com: pip install pygame-ce")
    sys.exit(1)

from config.settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE
from screens.game_state import GameStateManager


def main():
    """Loop principal do jogo."""
    pygame.init()

    # Cria janela
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)

    # Cria gerenciador de estados
    game = GameStateManager(screen)

    # Loop principal
    running = True
    while running:
        # ── Eventos ──────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_input(event)

        # ── Update ───────────────────────────────────────────
        game.update()

        # ── Render ───────────────────────────────────────────
        game.render()

        # ── FPS ──────────────────────────────────────────────
        game.clock.tick(FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
