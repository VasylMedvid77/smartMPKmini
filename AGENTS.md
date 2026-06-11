# Repository Instructions

## Current State

- Read `knowledgebase.md` before any development on `smart_MPK_mini_driver.py` or tests. It contains FL Studio MIDI scripting runtime constraints that override generic Python assumptions.
- Main source file is `smart_MPK_mini_driver.py` at repo root.
- Original seed source came from `C:\Users\User\Documents\Image-Line\FL Studio\Settings\Hardware\MPK_Mini_SmartFocus` (`/mnt/c/Users/User/Documents/Image-Line/FL Studio/Settings/Hardware/MPK_Mini_SmartFocus` in WSL).
- Project tooling uses `uv` with `pyproject.toml`.
- Integration tests live under `tests/` and stub FL Studio-provided modules.

## Script Context

- `smart_MPK_mini_driver.py` is an FL Studio hardware device script for Smart MPK Mini Driver.
- It imports FL Studio-provided modules (`channels`, `general`, `plugins`, `transport`, `ui`); do not expect normal Python runtime execution outside FL Studio.
- FL Studio modules are internal host APIs, not external services. Do not treat them like unreliable network or REST dependencies. Guard only documented or observed FL-version compatibility issues narrowly; otherwise let invalid host/script assumptions fail visibly.
- Before adding any `try`/`except` block, prove it handles a documented, observed, or tested failure mode. Do not add defensive exception handling for imagined failures, invalid assumptions, or tool-satisfying noise.
- FL Studio entrypoints in the script are `OnInit`, `OnMidiMsg`, `OnRefresh`, and `OnIdle`.
- Main behavior: map knobs CC 1-8/9-16 to selected plugin params, map Pad Bank A CC 20-27 to transport/snap/metronome actions, use joystick CC 50/100 for preset next/previous, and remap Fruity Slicer 2 pad notes 36-48 to slice notes 60-67.

## Architecture Discipline

- Before proposing architecture, refactor options, or new object boundaries, explicitly check Single Responsibility Principle boundaries. This is not optional or cosmetic: SRP is a fundamental architecture principle that tames complexity, prevents mistakes, and makes future changes easier.
- For each proposed object, module, or shared state entity, state what single responsibility it owns, why that responsibility belongs there, what state it owns, what it must not know, and which consumers may call it for what purpose.
- Reject designs that mix storage/cache concerns with runtime business state, orchestration, MIDI event handling, UI feedback, or domain decisions. Convenience bundles are not acceptable when they blur ownership.
- This repository is intended to be publicly available code that showcases the owner's engineering ability. Tangled architecture, unclear responsibility boundaries, or careless coupling can directly harm that goal.

## Verification

- Do not invoke the `verification-before-completion` skill for this repo.
- Do not run baseline tests before making changes unless the user explicitly asks or you are diagnosing a suspected regression.
- Run verification once after changes when it is meaningful for the task; use the narrowest relevant command instead of repeating the same checks.
- Install/sync dev tooling: `uv sync --dev`.
- Run unit tests: `uv run pytest utils/tests`.
- Format Python: `uv run ruff format .`.
- Lint Python: `uv run ruff check .`.
- Apply safe lint fixes: `uv run ruff check . --fix`.
- Syntax-only check: `python -m py_compile smart_MPK_mini_driver.py`.
- If local shell does not provide `python`, install the distro mapping to Python 3 first, then rerun the syntax check.
- Functional validation requires FL Studio with the MPK Mini script installed under the Hardware settings folder.

## TDD Workflow

- Do not invoke or follow the `test-driven-development` skill in this repo unless the user explicitly asks for TDD. Discuss and settle implementation first; write or update tests after the implementation direction is approved.
- Tests in this repo should cover observable FL Studio script behavior through entrypoints (`OnInit`, `OnMidiMsg`, `OnRefresh`, `OnIdle`), not private helper functions.
- Do not add unit tests that call internal helpers such as `_score_params`, `_get_mapping`, or `_handle_transport_pad`; those functions may be deleted, merged, or rewritten during refactors.
- Use integration tests in `tests/` with stubbed `channels`, `general`, `plugins`, `transport`, and `ui` modules.
- For behavior changes, write or update a focused integration test when the behavior is not already covered.
- Make the smallest script change that satisfies the requested behavior.
- Do not extract a helper/function for logic used only once in one place unless the user explicitly asks or there is a concrete runtime/testing constraint.
- Prefer one final targeted verification pass after changes; do not repeatedly rerun the same tests on unchanged code.
- Do not refactor `smart_MPK_mini_driver.py` unless the user explicitly asks for script refactoring.
