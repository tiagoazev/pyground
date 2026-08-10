"""
Pygame front-end for the Nokia-style Snake game.

Run with:
    python -m snake_game.main

Controls:
    Arrow keys / WASD - steer
    Enter             - restart after game over
    Esc               - quit
"""
import sys
import pygame

from snake_game.game import SnakeGame, Direction

CELL_SIZE = 24
GRID_WIDTH = 24
GRID_HEIGHT = 18
MARGIN = 12
SCORE_BAR_HEIGHT = 40

# Classic Nokia 3310 monochrome LCD palette.
BG_COLOR = (196, 207, 161)
FG_COLOR = (40, 46, 27)
GRID_LINE_COLOR = (176, 188, 143)

KEY_TO_DIRECTION = {
    pygame.K_UP: Direction.UP,
    pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
    pygame.K_d: Direction.RIGHT,
}


def draw(screen, font, game: SnakeGame) -> None:
    screen.fill(BG_COLOR)

    # Score bar
    score_surf = font.render(f"Score: {game.score}", True, FG_COLOR)
    screen.blit(score_surf, (MARGIN, 8))

    board_top = SCORE_BAR_HEIGHT
    # Grid lines (subtle, like the pixel grid of the old LCD)
    for x in range(GRID_WIDTH + 1):
        px = MARGIN + x * CELL_SIZE
        pygame.draw.line(
            screen, GRID_LINE_COLOR, (px, board_top), (px, board_top + GRID_HEIGHT * CELL_SIZE)
        )
    for y in range(GRID_HEIGHT + 1):
        py = board_top + y * CELL_SIZE
        pygame.draw.line(
            screen, GRID_LINE_COLOR, (MARGIN, py), (MARGIN + GRID_WIDTH * CELL_SIZE, py)
        )

    # Border
    border_rect = pygame.Rect(MARGIN, board_top, GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE)
    pygame.draw.rect(screen, FG_COLOR, border_rect, width=2)

    # Food
    if game.food is not None:
        rect = pygame.Rect(
            MARGIN + game.food.x * CELL_SIZE + 2,
            board_top + game.food.y * CELL_SIZE + 2,
            CELL_SIZE - 4,
            CELL_SIZE - 4,
        )
        pygame.draw.rect(screen, FG_COLOR, rect)

    # Snake
    for segment in game.snake:
        rect = pygame.Rect(
            MARGIN + segment.x * CELL_SIZE + 1,
            board_top + segment.y * CELL_SIZE + 1,
            CELL_SIZE - 2,
            CELL_SIZE - 2,
        )
        pygame.draw.rect(screen, FG_COLOR, rect)

    if game.game_over:
        overlay_font = pygame.font.SysFont("couriernew", 28, bold=True)
        msg1 = overlay_font.render("GAME OVER", True, FG_COLOR)
        msg2 = font.render("Press Enter to restart", True, FG_COLOR)
        screen.blit(
            msg1,
            (
                border_rect.centerx - msg1.get_width() // 2,
                border_rect.centery - msg1.get_height(),
            ),
        )
        screen.blit(
            msg2,
            (
                border_rect.centerx - msg2.get_width() // 2,
                border_rect.centery + 6,
            ),
        )

    pygame.display.flip()


def init_ui() -> tuple[pygame.Surface, pygame.font.Font]:
    """Initialise pygame and return the (screen, font) pair used by draw()."""
    pygame.init()
    pygame.display.set_caption("Snake (Nokia 3310 style)")

    width_px = GRID_WIDTH * CELL_SIZE + MARGIN * 2
    height_px = GRID_HEIGHT * CELL_SIZE + SCORE_BAR_HEIGHT + MARGIN
    screen = pygame.display.set_mode((width_px, height_px))
    font = pygame.font.SysFont("couriernew", 20, bold=True)
    return screen, font


def main() -> None:
    screen, font = init_ui()
    clock = pygame.time.Clock()

    game = SnakeGame(width=GRID_WIDTH, height=GRID_HEIGHT)

    TICK_EVENT = pygame.USEREVENT + 1
    pygame.time.set_timer(TICK_EVENT, game.current_tick_ms())

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN and game.game_over:
                    game.reset()
                    pygame.time.set_timer(TICK_EVENT, game.current_tick_ms())
                elif event.key in KEY_TO_DIRECTION:
                    game.change_direction(KEY_TO_DIRECTION[event.key])
            elif event.type == TICK_EVENT:
                game.step()
                # Re-arm timer at the (possibly new) speed for this score.
                pygame.time.set_timer(TICK_EVENT, game.current_tick_ms())

        draw(screen, font, game)
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
