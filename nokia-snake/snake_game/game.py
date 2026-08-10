"""
Core game logic for a Nokia-3310-style Snake game.

Deliberately free of any rendering / input dependency so it can be
driven directly by tests (unit or BDD) as well as by the Pygame UI.

Rules replicated from the original Nokia Snake:
  - Fixed rectangular grid, no wrap-around: hitting a wall ends the game.
  - The snake dies if its head enters a cell occupied by its own body.
  - The snake cannot reverse directly into itself (pressing the opposite
    direction is ignored, just like on the original phone).
  - Eating food grows the snake by one segment and increases the score.
  - Food never spawns on a cell currently occupied by the snake.
  - The game speeds up slightly as the score increases (classic behaviour).
"""
from __future__ import annotations

from collections import namedtuple
from enum import Enum
import random

Point = namedtuple("Point", ["x", "y"])


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


_OPPOSITE = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

# Nokia-style speed curve: base delay in ms between ticks, gets faster
# (lower delay) as the score rises, with a floor so it never becomes
# unplayable.
BASE_TICK_MS = 200
MIN_TICK_MS = 70
SPEEDUP_PER_FOOD_MS = 4


class SnakeGame:
    def __init__(self, width: int = 20, height: int = 15, seed=None):
        if width < 5 or height < 5:
            raise ValueError("Grid must be at least 5x5")
        self.width = width
        self.height = height
        self._rng = random.Random(seed)
        self.reset()

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        cx, cy = self.width // 2, self.height // 2
        # Snake starts with length 3, heading right.
        self.snake = [Point(cx, cy), Point(cx - 1, cy), Point(cx - 2, cy)]
        self.direction = Direction.RIGHT
        self.pending_direction = Direction.RIGHT
        self.score = 0
        self.game_over = False
        self.food: Point | None = None
        self._place_food()

    def _place_food(self) -> None:
        free_cells = [
            Point(x, y)
            for x in range(self.width)
            for y in range(self.height)
            if Point(x, y) not in self.snake
        ]
        if not free_cells:
            # Snake fills the whole board - you win! Nothing left to place.
            self.food = None
            return
        self.food = self._rng.choice(free_cells)

    # ------------------------------------------------------------------ #
    # Player input
    # ------------------------------------------------------------------ #
    def change_direction(self, direction: Direction) -> None:
        """Queue a direction change; ignored if it's a direct reversal."""
        if direction == _OPPOSITE[self.direction]:
            return
        self.pending_direction = direction

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #
    def step(self) -> None:
        """Advance the game by one tick."""
        if self.game_over:
            return

        self.direction = self.pending_direction
        dx, dy = self.direction.value
        head = self.snake[0]
        new_head = Point(head.x + dx, head.y + dy)

        if not (0 <= new_head.x < self.width and 0 <= new_head.y < self.height):
            self.game_over = True
            return

        if new_head in self.snake:
            self.game_over = True
            return

        self.snake.insert(0, new_head)

        if self.food is not None and new_head == self.food:
            self.score += 1
            self._place_food()
        else:
            self.snake.pop()

    def current_tick_ms(self) -> int:
        """Speed of the game loop for the current score (Nokia-style ramp)."""
        return max(MIN_TICK_MS, BASE_TICK_MS - self.score * SPEEDUP_PER_FOOD_MS)
