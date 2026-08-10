"""
Step definitions for features/snake.feature.

Uses the real `behave` package if it is installed, otherwise falls back
to the dependency-free `bdd.behave_lite` shim so the suite always runs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from behave import given, when, then  # type: ignore
except ImportError:
    from bdd.behave_lite import given, when, then  # type: ignore

from snake_game.game import SnakeGame, Direction, Point


@given("a new snake game with width {width} and height {height}")
def step_new_game(ctx, width, height):
    ctx.game = SnakeGame(width=int(width), height=int(height), seed=1234)


@given("food is placed directly in front of the snake")
def step_food_in_front(ctx):
    head = ctx.game.snake[0]
    dx, dy = ctx.game.direction.value
    ctx.game.food = Point(head.x + dx, head.y + dy)


@given("the snake is heading left right next to the left wall")
def step_heading_left_near_wall(ctx):
    game = ctx.game
    game.snake = [Point(0, 7), Point(1, 7), Point(2, 7)]
    game.direction = Direction.LEFT
    game.pending_direction = Direction.LEFT


@given("the snake is heading up right next to the top wall")
def step_heading_up_near_wall(ctx):
    game = ctx.game
    game.snake = [Point(10, 0), Point(10, 1), Point(10, 2)]
    game.direction = Direction.UP
    game.pending_direction = Direction.UP


@given("the snake is set up to collide with itself")
def step_setup_self_collision(ctx):
    game = ctx.game
    # A looped body: moving down immediately re-enters the snake's own tail.
    game.snake = [
        Point(5, 5),
        Point(5, 6),
        Point(5, 7),
        Point(6, 7),
        Point(6, 6),
        Point(6, 5),
    ]
    game.direction = Direction.DOWN
    game.pending_direction = Direction.DOWN


@when("the snake moves {n} step")
@when("the snake moves {n} steps")
def step_move_n(ctx, n):
    for _ in range(int(n)):
        ctx.game.step()


@when("the snake attempts to reverse direction")
def step_attempt_reverse(ctx):
    opposite = {
        Direction.UP: Direction.DOWN,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.RIGHT,
        Direction.RIGHT: Direction.LEFT,
    }[ctx.game.direction]
    ctx.game.change_direction(opposite)


@when("the game is reset")
def step_reset(ctx):
    ctx.game.reset()


@then("the snake head should be at position {pos}")
def step_check_head(ctx, pos):
    x_str, y_str = pos.split(",")
    expected = Point(int(x_str), int(y_str))
    assert ctx.game.snake[0] == expected, f"expected head {expected}, got {ctx.game.snake[0]}"


@then("the snake length should be {length}")
def step_check_length(ctx, length):
    assert len(ctx.game.snake) == int(length), (
        f"expected length {length}, got {len(ctx.game.snake)}"
    )


@then("the score should be {score}")
def step_check_score(ctx, score):
    assert ctx.game.score == int(score), f"expected score {score}, got {ctx.game.score}"


@then("the game should be over")
def step_check_game_over(ctx):
    assert ctx.game.game_over is True, "expected game_over to be True"


@then("the game should not be over")
def step_check_game_not_over(ctx):
    assert ctx.game.game_over is False, "expected game_over to be False"


@then("the snake direction should still be {direction}")
def step_check_direction(ctx, direction):
    expected = Direction[direction]
    assert ctx.game.pending_direction == expected, (
        f"expected pending direction {expected}, got {ctx.game.pending_direction}"
    )
    assert ctx.game.direction == expected, (
        f"expected direction {expected}, got {ctx.game.direction}"
    )


@then("the food position should not overlap the snake body")
def step_check_food_not_on_snake(ctx):
    assert ctx.game.food not in ctx.game.snake, "food spawned on top of the snake"
