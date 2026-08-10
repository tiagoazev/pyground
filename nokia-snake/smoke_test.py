#!/usr/bin/env python3
"""Headless fuzz/smoke test: plays many random games to catch crashes,
infinite loops, or invariant violations that discrete scenarios might miss.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snake_game.game import SnakeGame, Direction

DIRECTIONS = list(Direction)


def play_random_game(seed: int, max_steps: int = 2000) -> None:
    game = SnakeGame(width=20, height=15, seed=seed)
    rng = random.Random(seed)
    steps = 0
    while not game.game_over and steps < max_steps:
        if rng.random() < 0.3:
            game.change_direction(rng.choice(DIRECTIONS))
        game.step()
        steps += 1

        # Invariants that must always hold.
        assert len(set(game.snake)) == len(game.snake), "snake overlaps itself without dying"
        head = game.snake[0]
        assert 0 <= head.x < game.width and 0 <= head.y < game.height, "head left the grid"
        if game.food is not None:
            assert game.food not in game.snake, "food spawned on the snake"
        assert game.score == len(game.snake) - 3, "score/length mismatch"

    print(f"seed={seed}: survived {steps} steps, score={game.score}, game_over={game.game_over}")


if __name__ == "__main__":
    for seed in range(25):
        play_random_game(seed)
    print("\nSmoke test OK: no crashes or invariant violations across 25 random games.")
