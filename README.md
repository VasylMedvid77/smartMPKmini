# Smart MPK Mini Driver

FL Studio hardware device script for Akai MPK Mini Mk2.

## What It Does

- Maps knobs K1-K8 (`CC 1-8`) to parameters on the selected plugin.
- Includes exact mappings for Kepler, FLEX, Sawer, Mini Synth Pro, 3x Osc, Granulizer, FPC, and Fruity Slicer 2.
- Falls back to keyword-based parameter mapping for unknown plugins.
- Maps pad CC bank (`CC 20-27`) to play/pause, stop, record, snap next, Pattern/Song, and metronome.
- Remaps Fruity Slicer 2 pad notes (`36,38,40,41,43,45,47,48`) to slice notes (`60-67`).
- Uses joystick `CC 50/100` for preset next/previous with debounce.

## Install

Copy `device_smart_MPK_mini_driver.py` into your FL Studio hardware scripts folder:

```text
Documents\Image-Line\FL Studio\Settings\Hardware\smart_MPK_mini_driver\
```

Then restart FL Studio or reload MIDI scripts, and select `Smart MPK Mini Driver` for the controller.

## Development

This script uses FL Studio-provided Python modules (`channels`, `general`, `plugins`, `transport`, `ui`). It is not meant to run as a normal standalone Python program.

Syntax-only check:

```sh
python -m py_compile smart_MPK_mini_driver.py
```

Development checks:

```sh
uv sync --dev
uv run pytest utils/tests
uv run ruff format .
uv run ruff check .
```

Functional testing requires FL Studio with the script installed.
