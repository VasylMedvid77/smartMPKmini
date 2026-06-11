# Smart MPK Mini Driver

Hardware synths are awesome because you turn them on and they're ready. Every knob does what you expect. No setup between you and the sound.

VSTs sound just as good but you either use the mouse or spend time MIDI-learning every parameter by hand. Switch plugins and you start over.

This script fixes that. Load a VST in FL Studio and all knobs map to useful parameters. Switch plugins — controls follow. Switch back — still mapped, still ready.

## Install

Put `device_smart_MPK_mini_driver.py` in:

```
Documents\Image-Line\FL Studio\Settings\Hardware\smart_MPK_mini_driver\
```

FL Studio → Options → MIDI Settings → pick `Smart MPK Mini Driver` as Controller type.

Done. Load a VST, twist a knob.

## Pre-configured plugins

Hand-tuned mappings for knobs that actually make sense on hardware:

**Kepler** · **FLEX** · **Sawer** · **Mini Synth Pro** · **3x Osc** · **Granulizer** · **FPC** · **Fruity Slicer 2**

Cutoff, resonance, envelope, LFO, reverb, drive — not volume or pan.

## Use with any controller

The mapping system is generic. Define your knobs and CCs, then add plugin mappings:

```python
mapping_config.add_plugin_mapping("cytrus", {
    "k1": "Cutoff",
    "k2": "Resonance",
    "k3": "EG Amount",
    "k4": "LFO Rate",
    "k5": "FM Amount",
    "k6": "Osc Mix",
    "k7": "Reverb",
    "k8": "Chorus",
})
```

See `DEFAULT_CONTROLS` in the source for the layout format.

## Smart guess fallback

No preset for your VST? The script scans parameter names and matches keywords (`cutoff`, `resonance`, `lfo`, `reverb`, `drive`) to the eight knobs. Volume, pan, and limiter are excluded — those belong on the mixer.

Won't be perfect. Will be playable. Still better than MIDI-learn.

## Default layout (MPK Mini Mk2)

| Control | CC | Action |
|---------|----|--------|
| K1-K8 | 1-8 | Plugin parameters |
| Pad 1 | 20 | Play / Pause |
| Pad 2 | 21 | Stop |
| Pad 3 | 22 | Record |
| Pad 4 | 23 | Snap toggle |
| Pad 5 | 24 | Pattern / Song |
| Pad 8 | 27 | Metronome |
| Joystick | 50 / 100 | Next / Previous preset |

Fruity Slicer 2 pads remap MPK notes 36-48 to slice notes 60-67.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                         mapping_config                          │
│  Known plugin maps (Kepler, FLEX, Sawer, ...)                   │
│  + Smart guess keywords (cutoff, resonance, lfo rate, ...)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OnInit / OnRefresh                            │
│  For each channel with a valid plugin:                          │
│    1. Scan plugin parameter names (getParamCount / getParamName) │
│    2. Match against mapping_config                               │
│    3. Build CC → parameter index lookup table                    │
│    4. Cache it for zero-latency recall                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OnMidiMsg                                │
│  MIDI CC arrives (e.g. CC 1, value 64)                          │
│    1. Look up CC in current channel's cached mapping             │
│    2. If found → setParamValue(index, value / 127)              │
│    3. If not found → leave event unhandled                      │
│  Notes → Fruity Slicer 2 pad remap or let through               │
│  Joystick → preset next/previous with debounce                  │
└─────────────────────────────────────────────────────────────────┘
```

## Development

```sh
uv sync --dev
uv run pytest tests
uv run ruff format .
uv run ruff check .
python -m py_compile smart_MPK_mini_driver.py
```
