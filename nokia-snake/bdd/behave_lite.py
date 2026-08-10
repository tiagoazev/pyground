"""
A tiny, dependency-free BDD runner used as a fallback when the real
`behave` package isn't installed. Step definition files can do:

    try:
        from behave import given, when, then
    except ImportError:
        from bdd.behave_lite import given, when, then

and work identically either way. Supports the Gherkin subset used by
this project: Feature, Background, Scenario, Given/When/Then/And/But,
and `{param}` placeholders in step strings.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

STEP_REGISTRY: list[tuple[re.Pattern, callable]] = []


def _compile(step_text: str) -> re.Pattern:
    """Turn a behave-style '{param}' step string into a regex."""
    pattern = re.escape(step_text)
    pattern = pattern.replace(r"\{", "{").replace(r"\}", "}")
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>.+?)", pattern)
    return re.compile(f"^{pattern}$")


def _register(step_text: str, func):
    STEP_REGISTRY.append((_compile(step_text), func))
    return func


def given(step_text):
    def deco(func):
        return _register(step_text, func)

    return deco


def when(step_text):
    def deco(func):
        return _register(step_text, func)

    return deco


def then(step_text):
    def deco(func):
        return _register(step_text, func)

    return deco


def step(step_text):
    def deco(func):
        return _register(step_text, func)

    return deco


class Context(SimpleNamespace):
    pass


def _find_step(text):
    for pattern, func in STEP_REGISTRY:
        m = pattern.match(text)
        if m:
            return func, m.groupdict()
    return None, None


def _parse_feature(path: Path):
    lines = [
        line.rstrip("\n")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    feature_name = ""
    background: list[str] = []
    scenarios: list[tuple[str, list[str]]] = []
    current_steps = None
    in_background = False

    step_keywords = ("Given ", "When ", "Then ", "And ", "But ")

    for raw in lines:
        line = raw.strip()
        if line.startswith("Feature:"):
            feature_name = line[len("Feature:") :].strip()
        elif line.startswith("Background:"):
            in_background = True
            current_steps = background
        elif line.startswith("Scenario:") or line.startswith("Scenario Outline:"):
            in_background = False
            name = line.split(":", 1)[1].strip()
            current_steps = []
            scenarios.append((name, current_steps))
        elif line.startswith(step_keywords):
            if current_steps is None:
                continue
            current_steps.append(line.split(" ", 1)[1].strip())
        # ignore other lines (docstrings/tables not needed for this suite)

    return feature_name, background, scenarios


def run_features(features_dir: Path) -> bool:
    all_passed = True
    total = 0
    passed = 0

    for feature_file in sorted(features_dir.glob("*.feature")):
        feature_name, background, scenarios = _parse_feature(feature_file)
        print(f"\nFeature: {feature_name}  ({feature_file.name})")

        for scenario_name, steps in scenarios:
            total += 1
            ctx = Context()
            ok = True
            error = None
            for step_text in background + steps:
                func, kwargs = _find_step(step_text)
                if func is None:
                    ok = False
                    error = f"No matching step definition for: '{step_text}'"
                    break
                try:
                    func(ctx, **kwargs)
                except AssertionError as e:
                    ok = False
                    error = f"Assertion failed on '{step_text}': {e}"
                    break
                except Exception as e:  # noqa: BLE001
                    ok = False
                    error = f"Error on '{step_text}': {e!r}"
                    break

            if ok:
                passed += 1
                print(f"  \u2713 {scenario_name}")
            else:
                all_passed = False
                print(f"  \u2717 {scenario_name}")
                print(f"      {error}")

    print(f"\n{passed}/{total} scenarios passed")
    return all_passed


if __name__ == "__main__":
    features_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("features")
    success = run_features(features_path)
    sys.exit(0 if success else 1)
