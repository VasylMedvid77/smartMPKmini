# MPK Mini Mk2 Smart Focus

FL Studio hardware device script for Akai MPK Mini Mk2.

## What It Does

- Maps knob Bank A (`CC 1-8`) to performance and timbre parameters on the selected plugin.
- Maps knob Bank B (`CC 9-16`) to envelope and modulation parameters.
- Includes exact mappings for Kepler, FLEX, Sawer, Mini Synth Pro, 3x Osc, Granulizer, FPC, and Fruity Slicer 2.
- Falls back to keyword-based parameter mapping for unknown plugins.
- Maps Pad Bank A (`CC 20-27`) to transport, snap, Pattern/Song, and metronome controls.
- Uses joystick `CC 50/100` for preset next/previous.
- Remaps Fruity Slicer 2 pad notes `44-51` to slice notes `60-67`.

## Install

Copy `device_MPKmini2_SmartFocus.py` into your FL Studio hardware scripts folder:

```text
Documents\Image-Line\FL Studio\Settings\Hardware\MPK_Mini_SmartFocus\
```

Then restart FL Studio or reload MIDI scripts, and select `MPK Mini Mk2 Smart Focus` for the controller.

## Development

This script uses FL Studio-provided Python modules (`channels`, `general`, `plugins`, `transport`, `ui`). It is not meant to run as a normal standalone Python program.

Syntax-only check:

```sh
python -m py_compile device_MPKmini2_SmartFocus.py
```

Development checks:

```sh
uv sync --dev
uv run pytest utils/tests
uv run ruff format .
uv run ruff check .
```

Functional testing requires FL Studio with the script installed.
