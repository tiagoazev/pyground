# Snake (Nokia 3310 style)

A faithful recreation of the classic Nokia Snake game in Python + Pygame.

## Rules (matching the original phone game)

- Fixed grid, **no wrap-around** — hitting a wall ends the game.
- The snake dies if it runs into its own body.
- You can't reverse directly into yourself (pressing the opposite arrow
  key is simply ignored, like on the original phone).
- Eating food grows the snake by one segment and adds to the score.
- The game speeds up slightly every time you eat, just like the original.

## Project layout

```
snake_game/
  game.py     - pure-Python game engine (no dependencies, fully testable)
  main.py     - Pygame front-end (rendering + input + game loop)
features/
  snake.feature          - Gherkin scenarios describing the game rules
  ui.feature             - Gherkin scenarios for the boot/render path
  steps/snake_steps.py   - step definitions binding Gherkin to game.py
  steps/ui_steps.py      - step definitions driving main.py headlessly
bdd/
  behave_lite.py          - dependency-free Gherkin runner (fallback)
run_bdd_tests.py          - runs the BDD suite
smoke_test.py             - headless random-play fuzz/invariant test
requirements.txt          - runtime dependency for the GUI (pygame-ce)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Play the game

```bash
python -m snake_game.main
```

Controls: Arrow keys / WASD to steer, Enter to restart after game over,
Esc to quit.

## Run the tests

The BDD suite has **no external dependencies** — it runs out of the box:

```bash
python3 run_bdd_tests.py
```

If you have the real `behave` package installed (`pip install behave`),
you can instead run the exact same feature files with it:

```bash
behave features/
```

Additional headless fuzz/invariant test (random play, checks the game
never crashes or breaks its own rules):

```bash
python3 smoke_test.py
```
