"""
Step definitions for features/ui.feature.

Runs the real Pygame front-end headlessly (SDL "dummy" video driver) so
the boot-and-render path is exercised by the BDD suite even on CI
machines with no display. This is the layer where a broken pygame
install (e.g. missing font module) blows up, which pure game-logic
scenarios can never catch.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Must be set before pygame creates a display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

try:
    from behave import given, then  # type: ignore
except ImportError:
    from bdd.behave_lite import given, then  # type: ignore

from snake_game.game import SnakeGame, Point
from snake_game import main as ui


def _cell_center_px(cell: Point) -> tuple[int, int]:
    """Screen pixel at the centre of a grid cell (clear of grid lines)."""
    x = ui.MARGIN + cell.x * ui.CELL_SIZE + ui.CELL_SIZE // 2
    y = ui.SCORE_BAR_HEIGHT + cell.y * ui.CELL_SIZE + ui.CELL_SIZE // 2
    return x, y


@given("a headless pygame display")
def step_headless_display(ctx):
    ctx.screen, ctx.font = ui.init_ui()


@given("a rendered frame of a fresh game")
def step_render_fresh_game(ctx):
    ctx.game = SnakeGame(width=ui.GRID_WIDTH, height=ui.GRID_HEIGHT, seed=1234)
    ui.draw(ctx.screen, ctx.font, ctx.game)
    ctx.frame_drawn = True


@given("a rendered frame of a game that is over")
def step_render_game_over(ctx):
    ctx.game = SnakeGame(width=ui.GRID_WIDTH, height=ui.GRID_HEIGHT, seed=1234)
    ctx.game.game_over = True
    ui.draw(ctx.screen, ctx.font, ctx.game)
    ctx.frame_drawn = True


@then("the screen and the score font should be ready")
def step_check_ui_ready(ctx):
    assert ctx.screen is not None, "expected a screen surface"
    assert ctx.font is not None, "expected a font"
    assert ctx.font.render("Score: 0", True, ui.FG_COLOR) is not None


@then("the snake head cell should be drawn in the LCD foreground color")
def step_check_head_pixel(ctx):
    px, py = _cell_center_px(ctx.game.snake[0])
    color = ctx.screen.get_at((px, py))[:3]
    assert color == ui.FG_COLOR, (
        f"expected head pixel {ui.FG_COLOR}, got {color} at ({px}, {py})"
    )


@then("an empty cell should be drawn in the LCD background color")
def step_check_empty_pixel(ctx):
    game = ctx.game
    empty = next(
        Point(x, y)
        for x in range(game.width)
        for y in range(game.height)
        if Point(x, y) not in game.snake and Point(x, y) != game.food
    )
    px, py = _cell_center_px(empty)
    color = ctx.screen.get_at((px, py))[:3]
    assert color == ui.BG_COLOR, (
        f"expected empty pixel {ui.BG_COLOR}, got {color} at ({px}, {py})"
    )


@then("the frame should have been drawn")
def step_check_frame_drawn(ctx):
    assert getattr(ctx, "frame_drawn", False), "expected draw() to have completed"
