# MPK Handler Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `device_MPKmini2_SmartFocus.py` into a single-file `MpkHandler` architecture without changing FL Studio behavior.

**Architecture:** Keep FL Studio callback names (`OnInit`, `OnMidiMsg`, `OnRefresh`, `OnIdle`) as tiny wrappers because FL calls them by exact name. Move state and behavior into one `MpkHandler` instance, using `self` instead of module globals. Use type aliases to make mapping types readable.

**Tech Stack:** FL Studio MIDI scripting Python runtime, local `uv`, `ruff`, `pytest`, integration tests under `utils/tests`.

---

## File Structure

- Modify: `device_MPKmini2_SmartFocus.py`
- Keep: `utils/tests/test_script_integration.py`
- Keep: `utils/tests/conftest.py`
- No new runtime files. FL Studio script must remain standalone.

## Rules

- Read `knowledgebase.md` first.
- Do not change script behavior.
- Do not import repo test helpers or dev packages into `device_MPKmini2_SmartFocus.py`.
- Do not rename FL callbacks.
- Do not add unit tests against helper methods; integration tests are contract.
- Run `uv run pytest utils/tests` after each task.

---

### Task 1: Add Readable Type Aliases

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Run baseline integration tests**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

- [ ] **Step 2: Add aliases near `FLMidiEvent`**

Add:

```python
ParamIndex = int
BankName = str
KnobMapping = dict[BankName, list[ParamIndex | None]]
ParamIndexByName = dict[str, ParamIndex]
BlockedFallbackSlots = set[tuple[BankName, int]]
```

- [ ] **Step 3: Replace ugly nested mapping annotations**

Change signatures:

```python
def build_param_index(chan: int, exclude_never_map: bool = True) -> ParamIndexByName:
def build_full_param_index(chan: int) -> ParamIndexByName:
def resolve_plugin_map(
    chan: int,
    full_index: ParamIndexByName,
    filtered_index: ParamIndexByName,
    plugin_key: str,
) -> KnobMapping:
def resolve_fallback_map(chan: int, param_index: ParamIndexByName) -> KnobMapping:
def fill_fallback(
    result: KnobMapping,
    param_index: ParamIndexByName,
    used: set[ParamIndex],
    blocked_slots: BlockedFallbackSlots | None = None,
) -> None:
def score_params(chan: int) -> KnobMapping:
def get_mapping(chan: int) -> KnobMapping:
```

- [ ] **Step 4: Verify**

Run: `uv run ruff format . && uv run ruff check . && uv run pytest utils/tests && uv run python -m py_compile device_MPKmini2_SmartFocus.py`

Expected: Ruff clean, `10 passed`, compile succeeds.

---

### Task 2: Introduce `MpkHandler` State Shell

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Create class with state only**

Add below constants:

```python
class MpkHandler:
    def __init__(self) -> None:
        self.mapping_cache: dict[tuple[int, str], KnobMapping] = {}
        self.last_channel = -99
        self.joystick_next_armed = True
        self.joystick_prev_armed = True
        self.pending_refresh_channel: int | None = None
        self.pending_refresh_ticks = 0
```

- [ ] **Step 2: Create handler instance**

Add before FL callbacks:

```python
handler = MpkHandler()
```

- [ ] **Step 3: Verify no behavior changed**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 3: Move Refresh And Idle State To `MpkHandler`

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Add methods**

Move `OnRefresh` body into:

```python
def on_refresh(self, flags: int) -> None:
    chan = FL_CHANNELS.selectedChannel(canBeNone=True)
    if chan is None or chan < 0:
        return

    if chan != self.last_channel:
        self.last_channel = chan
        self.pending_refresh_channel = chan
        self.pending_refresh_ticks = refresh_delay_ticks
```

Move `OnIdle` body into:

```python
def on_idle(self) -> None:
    if self.pending_refresh_channel is None:
        return

    if self.pending_refresh_ticks > 0:
        self.pending_refresh_ticks -= 1
        return

    chan = self.pending_refresh_channel
    self.pending_refresh_channel = None

    selected = FL_CHANNELS.selectedChannel(canBeNone=True)
    if selected != chan:
        return

    self.clear_channel_cache(chan)
    self.print_mapping(chan)
```

- [ ] **Step 2: Update FL wrappers**

```python
def OnRefresh(flags: int) -> None:
    handler.on_refresh(flags)


def OnIdle() -> None:
    handler.on_idle()
```

- [ ] **Step 3: Move dependent helpers into class**

Move `clear_channel_cache`, `print_mapping`, and `get_mapping` into `MpkHandler`; add `self.` for calls.

- [ ] **Step 4: Delete module globals now owned by class**

Delete:

```python
mapping_cache = {}
last_channel = -99
pending_refresh_channel = None
pending_refresh_ticks = 0
```

- [ ] **Step 5: Verify**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 4: Move Joystick State To `MpkHandler`

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Move joystick handler into class**

Change:

```python
def handle_preset_joystick(cc: int, value: int) -> bool:
```

To:

```python
def handle_preset_joystick(self, cc: int, value: int) -> bool:
```

Use `self.joystick_next_armed` and `self.joystick_prev_armed`.

- [ ] **Step 2: Delete joystick module globals**

Delete:

```python
joystick_next_armed = True
joystick_prev_armed = True
```

- [ ] **Step 3: Verify**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 5: Move MIDI Routing Into `MpkHandler`

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Add callback method**

Move `OnMidiMsg` body into:

```python
def on_midi_msg(self, event: FLMidiEvent) -> None:
```

- [ ] **Step 2: Split routing methods**

Create methods:

```python
def handle_note_event(self, event: FLMidiEvent) -> bool:
def handle_cc_event(self, event: FLMidiEvent) -> bool:
def handle_knob_cc(self, cc: int, value: int) -> bool:
def handle_transport_pad_cc(self, cc: int, value: int) -> bool:
def handle_joystick_cc(self, cc: int, value: int) -> bool:
```

Return `True` only when event was handled by script.

- [ ] **Step 3: Update FL wrapper**

```python
def OnMidiMsg(event: FLMidiEvent) -> None:
    handler.on_midi_msg(event)
```

- [ ] **Step 4: Verify**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 6: Move Mapping Logic Into `MpkHandler`

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Move mapping methods into class**

Move these into `MpkHandler`:

```python
build_param_index
build_full_param_index
resolve_plugin_map
resolve_fallback_map
fill_fallback
score_params
selected_plugin_name_lower
```

- [ ] **Step 2: Update internal calls to `self.`**

Examples:

```python
self.build_full_param_index(chan)
self.resolve_plugin_map(chan, full_index, filtered_index, matched_key)
self.fill_fallback(result, param_index, used)
```

- [ ] **Step 3: Verify**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 7: Move Transport And Slicer Helpers Into `MpkHandler`

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Move remaining helpers into class**

Move:

```python
global_transport
set_metronome
snap_name
handle_transport_pad
handle_fruity_slicer_2_pad_note
```

- [ ] **Step 2: Update internal calls to `self.`**

Examples:

```python
self.global_transport(110, 1)
self.snap_name()
self.handle_fruity_slicer_2_pad_note(event)
```

- [ ] **Step 3: Verify**

Run: `uv run pytest utils/tests`

Expected: `10 passed`.

---

### Task 8: Add `on_init` And Final Cleanup

**Files:**
- Modify: `device_MPKmini2_SmartFocus.py`
- Test: `utils/tests/test_script_integration.py`

- [ ] **Step 1: Move init body into class**

```python
def on_init(self) -> None:
    print("==========================================")
    print("  MPK Mini Mk2 Smart Focus - loaded")
    print("  Bank A (CC 1-8):   performance params")
    print("  Joystick Y (CC 100/50): preset next/previous")
    print("  Bank B (CC 9-16):  envelope/mod params")
    print("  Pad Bank A (CC 20-27): transport/snap")
    print("  Fruity Slicer 2 pads: notes 44-51 -> 72-79")
    print("==========================================")
```

- [ ] **Step 2: Update FL wrapper**

```python
def OnInit() -> None:
    handler.on_init()
```

- [ ] **Step 3: Remove leftover free helper functions**

After this task, only free runtime functions should be:

```python
def OnInit() -> None:
def OnMidiMsg(event: FLMidiEvent) -> None:
def OnRefresh(flags: int) -> None:
def OnIdle() -> None:
```

- [ ] **Step 4: Run final verification**

Run: `uv run ruff format . && uv run ruff check . && uv run pytest utils/tests && uv run python -m py_compile device_MPKmini2_SmartFocus.py`

Expected: Ruff clean, `10 passed`, compile succeeds.

---

## Self-Review

- Spec coverage: Plan covers single `MpkHandler`, FL wrappers, no globals, readable type aliases, event routing, mapping, transport, Slicer, joystick, refresh/idle.
- Placeholder scan: No TBD/TODO/fill-later placeholders.
- Type consistency: `KnobMapping`, `ParamIndexByName`, `BlockedFallbackSlots`, and `FLMidiEvent` are introduced before use.
- Scope check: Single focused refactor, no behavior change, no new runtime files.
