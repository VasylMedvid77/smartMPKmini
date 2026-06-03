# FL Studio MIDI Script Knowledgebase

Purpose: give LLMs domain context before changing `device_MPKmini2_SmartFocus.py`.

## Runtime Reality

- FL Studio MIDI scripts are plain `.py` files loaded by FL Studio, not normal CLI apps.
- FL Studio provides runtime-only modules such as `channels`, `general`, `plugins`, `transport`, `ui`, `device`, and `midi`.
- Do not add normal app assumptions: no CLI args, no stdout UI, no dependency install inside FL Studio, no long-running process, no background service.
- `print(...)` is valid debug output because users can open FL Studio Script output. It is not CLI UX.
- `ui.setHintMsg(...)` is valid short user feedback inside FL Studio.
- Some API behavior differs by FL Studio version/build. Guard known compatibility edge cases narrowly; do not broad-refactor around imagined Python best practices.

## Script Discovery And Install

- User scripts live under `Documents\Image-Line\FL Studio\Settings\Hardware\<folder>\device_<name>.py`.
- First-line metadata such as `# name=...` matters; FL uses it for Controller type list.
- FL Studio handles the script directly; local `uv`, `pytest`, and `ruff` are repo development tools only.
- Functional validation still requires FL Studio with the script installed and MPK Mini hardware configured.

## Event Model

- FL Studio calls callbacks by name: `OnInit`, `OnMidiIn`, `OnMidiMsg`, `OnNoteOn`, `OnControlChange`, `OnRefresh`, `OnIdle`, etc.
- `OnMidiIn` sees raw MIDI first. `OnMidiMsg` receives messages not handled by `OnMidiIn`.
- If a callback sets `event.handled = True`, FL Studio stops normal propagation for that event.
- Leave `event.handled` unset/false when the script intentionally wants FL Studio generic handling or manual MIDI linking to still see the event.
- `OnIdle` is for small periodic/UI work. Do not put expensive scans, sleeps, blocking I/O, network calls, or long loops there.
- `OnRefresh(flags)` can fire often. Use it to schedule work or respond to dirty state, not as heavy processing by default.

## MIDI Message Basics

- `event.status & 0xF0` identifies broad MIDI type: `0x90` note on, `0x80` note off, `0xB0` control change.
- `event.data1` is note/controller number.
- `event.data2` is velocity/controller value.
- Many pads/buttons send press as nonzero and release as `0`. Do not assume only `127` means pressed.
- Some controllers have absolute knobs, relative encoders, multiple device ports, custom programs, or SysEx-controlled LEDs/screens. MPK Mini Mk2 constraints differ from MPK Mini Mk3/Plus.

## Current Script Contract

- Main source: `device_MPKmini2_SmartFocus.py`.
- Public behavior lives in FL callbacks, especially `OnMidiMsg`, `OnRefresh`, and `OnIdle`.
- Knobs K1-K8 send CC `1-8` and map to selected plugin params.
- Pad CC bank messages CC `20`, `21`, `22`, `23`, `24`, `27` control transport/snap/song-pattern/metronome.
- Joystick CC `50` and `100` triggers preset next/previous with debounce.
- Fruity Slicer 2 remaps MPK pad notes `44-51` to slice notes `60-67`.
- Selected Channel Rack instrument determines smart knob mapping.
- Known plugin maps use exact parameter names or stable indexes; unknown plugins use keyword fallback.
- `NEVER_MAP` intentionally avoids mapping broad volume/pan/limiter params in fallback.

## Testing Rules

- Integration tests are the safety net. They must call FL entrypoints only: `OnInit`, `OnMidiMsg`, `OnRefresh`, `OnIdle`.
- Do not test private helper functions. Helpers may be deleted, merged, renamed, or replaced during refactor.
- Stub FL modules in tests. Never import real FL Studio modules in repo tests.
- Observable effects to assert: `event.handled`, calls to fake FL APIs, hint messages, printed script output, MIDI notes sent.
- Current stable behavior is captured in `utils/tests/test_script_integration.py`.

## Lint And Formatting Caveats

- Ruff is for repo hygiene, not proof of FL runtime correctness.
- Some general Python advice can be wrong here:
  - Do not remove FL callback functions because they appear unused; FL calls them by name.
  - Do not remove FL-provided imports because local Python cannot resolve them normally.
  - Do not replace `print` debug output with CLI logging framework.
  - Do not add package/dependency assumptions to runtime script.
  - Do not make script import repo test helpers or dev-only packages.
  - Do not change `event.handled` semantics just to satisfy style preferences.
- Prefer explicit, boring code over clever abstractions. FL scripts run inside a DAW and should fail visibly but not disrupt playback.

## Useful Existing Approaches

- Official FL docs emphasize event callbacks, `event.handled`, Script output, and leaving generic MIDI handling alone when the script does not need an event.
- Community scripts often route controller controls through callback entrypoints and mark handled only after doing controller-specific work.
- Larger open-source FL controller projects use frameworks/components, but this repo currently needs a small MPK Mini Mk2 script, not a generic controller framework.
- Universal Controller Script supports MPK Mini Mk3 and many plugins, showing that plugin/device support can grow large; avoid importing that complexity until needed.
- Simple controller scripts show practical forwarding patterns: notes/CCs to active or selected generators, preserving generic controller behavior where possible.

## Sources Researched

- Official Image-Line MIDI scripting docs: https://ww2.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm
- FL Studio API stubs/docs: https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/
- Universal Controller Script: https://github.com/MaddyGuthridge/Universal-Controller-Script
- Simple FL Studio MIDI Scripts: https://github.com/MaddyGuthridge/simple-midi-controller-scripts
- MPK Mini Plus FL Studio script: https://github.com/FabulousCodingFox/MpkMiniPlus-FlStudio
- NFXTemplate FL Studio scripting template: https://github.com/nfxbeats/NFXTemplate
- FL controller framework: https://github.com/bcrowe306/fl_controller_framework
