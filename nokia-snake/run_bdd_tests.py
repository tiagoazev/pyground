#!/usr/bin/env python3
"""
Runs the BDD test suite.

If `behave` is installed, prefer it (matches real-world CI usage):
    behave features/

Otherwise fall back to the bundled dependency-free runner, which is
what this script does by default so the suite works out of the box.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Import step definitions so they register themselves with whichever
# given/when/then implementation is available.
import features.steps.snake_steps  # noqa: F401,E402
import features.steps.ui_steps  # noqa: F401,E402
from bdd.behave_lite import run_features  # noqa: E402


if __name__ == "__main__":
    success = run_features(ROOT / "features")
    sys.exit(0 if success else 1)
