# name=MPK Mini Mk2 Smart Focus
# url=https://forum.image-line.com

"""
MPK Mini Mk2 Smart Focus
--------------------------
Knobs K1-K8 automatically follow whichever instrument is selected
in the FL Studio Channel Rack, mapped to musically useful parameters.

Knobs K1-K8 send CC 1-8 for performance / timbre controls.
Pad CC bank controls transport/snap/metronome.
Pad note bank can trigger sample slices when a slicer plugin is selected.

Plugin-specific exact mappings for:
  Kepler, FLEX, Sawer, Mini Synth Pro, 3x Osc,
  Granulizer, FPC, Fruity Slicer 2

Unknown plugins fall back to keyword scoring.

Script output shows the full mapping every time you select a channel.
"""

import channels as FL_CHANNELS
import general as FL_GENERAL
import plugins as FL_PLUGINS
import transport as FL_TRANSPORT
import ui as FL_UI


class FLMidiEvent:
    """
    Event object FL Studio passes into MIDI callbacks.

    FL Studio creates this object at runtime; this class only documents the
    fields this script reads or writes.
    """

    status: int
    data1: int
    data2: int
    handled: bool


ParamIndex = int


class MappedParameter:
    def __init__(self, index: ParamIndex, name: str) -> None:
        self.index = index
        self.name = name


KnobMapping = list[MappedParameter | None]
ParametersByIndex = dict[ParamIndex, str]
PluginInstanceKey = tuple[int, str]


class MappingsCache:
    def __init__(self) -> None:
        self._items: dict[PluginInstanceKey, KnobMapping] = {}

    def clear(self) -> None:
        self._items.clear()

    def put(self, key: PluginInstanceKey, mapping: KnobMapping) -> None:
        self._items[key] = mapping

    def get(self, key: PluginInstanceKey) -> KnobMapping | None:
        return self._items.get(key)

    def to_print(self) -> str:
        return "\n".join(str(key) for key in self._items)


mappings_cache = MappingsCache()


# ── CC configuration ───────────────────────────────────────────────────────────


class MidiStatus:
    MASK = 0xF0
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    CONTROL_CHANGE = 0xB0


class PresetDirection:
    NEXT = "next"
    PREVIOUS = "previous"


mpk_controls = {
    "knobs": {
        "K1": {"cc": 1},
        "K2": {"cc": 2},
        "K3": {"cc": 3},
        "K4": {"cc": 4},
        "K5": {"cc": 5},
        "K6": {"cc": 6},
        "K7": {"cc": 7},
        "K8": {"cc": 8},
    },
    "pad_cc_bank": {
        "P1": {"cc": 20, "action": "play_pause"},
        "P2": {"cc": 21, "action": "stop"},
        "P3": {"cc": 22, "action": "record"},
        "P4": {"cc": 23, "action": "snap_next"},
        "P5": {"cc": 24, "action": "songpat"},
        "P8": {"cc": 27, "action": "metronome"},
    },
    "pad_note_bank": {
        "P1": {"note": 44},
        "P2": {"note": 45},
        "P3": {"note": 46},
        "P4": {"note": 47},
        "P5": {"note": 48},
        "P6": {"note": 49},
        "P7": {"note": 50},
        "P8": {"note": 51},
    },
    "joystick": {
        "preset_next": {"cc": 50},
        "preset_previous": {"cc": 100},
        "trigger_value": 64,
    },
}

knob_ccs = [control["cc"] for control in mpk_controls["knobs"].values()]
all_knob_ccs = set(knob_ccs)
pad_cc_actions_by_cc = {
    control["cc"]: control["action"] for control in mpk_controls["pad_cc_bank"].values()
}
pad_note_bank_notes = [
    control["note"] for control in mpk_controls["pad_note_bank"].values()
]


class CC:
    JOYSTICK_PRESET_NEXT = mpk_controls["joystick"]["preset_next"]["cc"]
    JOYSTICK_PRESET_PREV = mpk_controls["joystick"]["preset_previous"]["cc"]
    PRESET_TRIGGER_VALUE = mpk_controls["joystick"]["trigger_value"]

fruity_slicer_2_slice_notes = [60, 61, 62, 63, 64, 65, 66, 67]

# ── Plugin-specific mappings (exact param name strings, case-insensitive) ──────
#
# Each entry maps 8 knobs to strings, parameter indexes, or None.
# Strings are matched against FL_PLUGINS.getParamName() with case-insensitive equality.
# Integer indexes are used directly for stable controls like FLEX macros.
# None = leave knob unassigned (falls through to keyword scoring).
#
# Key = lowercase substring of FL_PLUGINS.getPluginName() output.

plugin_maps = {
    "kepler": [
        "VCF Frequency",
        "VCF Reso",
        "VCF Env",
        "VCF LFO",
        "LFO rate",
        "DCO PWM",
        "HPF Frequency",
        "DCO LFO",
    ],
    "flex": [
        10,  # macro 1
        11,  # macro 2
        12,  # macro 3: preset-dependent label, e.g. Gated/Unison
        13,  # macro 4
        14,  # macro 5
        15,  # macro 6
        "Volume envelope attack",
        "Volume envelope release",
    ],
    "sawer": [
        "Filter cutoff",
        "Filter resolution",
        "EGF amount",
        "Reverb mix",
        "Chorus depth",
        "LFO speed",
        "LFO amount",
        "Noise level",
    ],
    "mini synth": [
        "FLT Freq",
        "FLT Peak",
        "EGF Amnt",
        "LFO Rate",
        "LFO Amnt",
        "DIST",
        "Overdrive",
        "Decimator",
    ],
    "3x osc": [
        "Filter frequency (modulation X)",
        "Filter bandwidth (modulation Y)",
        "Stereo phase randomness",
        "Osc 2 mix level",
        "Osc 3 mix level",
        "Osc 1 coarse pitch",
        "Osc 2 coarse pitch",
        "Osc 3 coarse pitch",
    ],
    "granulizer": [
        "Filter frequency (modulation X)",
        "Filter bandwidth (modulation Y)",
        "Grain attack time",
        "Grain hold time",
        "Grain spacing",
        "Wave spacing",
        "Sample start",
        "Effect depth",
    ],
    "fpc": [
        "Pad 1 volume",
        "Pad 2 volume",
        "Pad 3 volume",
        "Pad 4 volume",
        "Pad 5 volume",
        "Pad 6 volume",
        "Pad 7 volume",
        "Pad 8 volume",
    ],
    "fruity slicer 2": [
        "Cutoff",
        "Res",
        "Transpose",
        "Detune",
        None,
        None,
        None,
        None,
    ],
}

# ── Fallback keyword priority map (for unknown plugins) ────────────────────────
#
# Used when no plugin name matches plugin_maps.
# Format: (knob_index, [keywords...]) — case-insensitive substring match.
# First keyword hit wins. Slots already filled are skipped.

never_map = [
    "volume",
    "master vol",
    "output vol",
    "pan",
    "panorama",
    "panning",
    "master pan",
    "limiter",
]

fallback_priority = [
    (0, ["macro 1", "macro1", "x1 ", "mod x", "filter frequency (modulation x)"]),
    (1, ["macro 2", "macro2", "x2 ", "mod y", "filter bandwidth (modulation y)"]),
    (2, ["macro 3", "macro3", "x3 "]),
    (3, ["macro 4", "macro4", "x4 "]),
    (
        0,
        [
            "filter cutoff",
            "filter frequency",
            "filter freq",
            "vcf frequency",
            "vcf freq",
            "flt freq",
            "cutoff freq",
            "cutoff",
            "lpf freq",
            "lpf cutoff",
            "cut off",
        ],
    ),
    (
        1,
        [
            "filter reso",
            "filter resolution",
            "filter bandwidth",
            "vcf reso",
            "vcf res",
            "flt peak",
            "resonance",
            "reso",
            "emphasis",
            "q ",
        ],
    ),
    (
        2,
        [
            "filter env",
            "vcf env",
            "egf amount",
            "egf amnt",
            "filter env amt",
            "env amt",
            "env amount",
            "filter mod",
        ],
    ),
    (3, ["reverb mix", "reverb wet", "reverb amount", "reverb level"]),
    (4, ["lfo rate", "lfo speed", "lfo freq", "lfo 1 rate"]),
    (5, ["lfo amount", "lfo depth", "lfo amnt", "lfo 1 depth", "lfo level"]),
    (
        6,
        [
            "chorus depth",
            "chorus mix",
            "ensemble",
            "unison detune",
            "detune",
            "spread",
            "character",
        ],
    ),
    (
        7,
        [
            "drive",
            "distort",
            "overdrive",
            "saturat",
            "waveshap",
            "decimat",
            "bit crush",
            "noise level",
        ],
    ),
]

# ── State ──────────────────────────────────────────────────────────────────────

snap_names = {
    0: "Line",
    1: "Cell",
    3: "None",
    4: "1/6 step",
    5: "1/4 step",
    6: "1/3 step",
    7: "1/2 step",
    8: "Step",
    9: "1/6 beat",
    10: "1/4 beat",
    11: "1/3 beat",
    12: "1/2 beat",
    13: "Beat",
    14: "Bar",
}


class MidiHandler:
    def __init__(self) -> None:
        self.active_plugin_key: PluginInstanceKey | None = None
        self.joystick_armed_by = {
            PresetDirection.NEXT: True,
            PresetDirection.PREVIOUS: True,
        }

    def set_active_plugin_key(self, key: PluginInstanceKey | None) -> None:
        self.active_plugin_key = key

    def handle_midi_msg(self, event: FLMidiEvent) -> None:
        match event.status & MidiStatus.MASK:
            case MidiStatus.NOTE_ON | MidiStatus.NOTE_OFF:
                self.handle_note_msg(event)

            case MidiStatus.CONTROL_CHANGE:
                self.handle_cc_msg(event)

            case _:
                return

    def handle_note_msg(self, event: FLMidiEvent) -> None:
        self.handle_fruity_slicer_2_pad_note(event)

    def handle_cc_msg(self, event: FLMidiEvent) -> None:
        cc = event.data1
        value = event.data2

        match cc:
            case CC.JOYSTICK_PRESET_NEXT:
                event.handled = True
                self.handle_preset_joystick(PresetDirection.NEXT, value)

            case CC.JOYSTICK_PRESET_PREV:
                event.handled = True
                self.handle_preset_joystick(PresetDirection.PREVIOUS, value)

            case cc if cc in pad_cc_actions_by_cc:
                event.handled = self.handle_transport_pad(
                    pad_cc_actions_by_cc[cc], value
                )

            case cc if cc in all_knob_ccs:
                event.handled = self.handle_knob_cc(cc, value)

            case _:
                return

    def handle_preset_joystick(self, direction: str, joystick_value: int) -> None:
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return

        match direction:
            case PresetDirection.NEXT:
                preset_action = FL_PLUGINS.nextPreset

            case PresetDirection.PREVIOUS:
                preset_action = FL_PLUGINS.prevPreset

        if joystick_value < CC.PRESET_TRIGGER_VALUE:
            self.joystick_armed_by[direction] = True
            return

        if not self.joystick_armed_by[direction]:
            return

        preset_action(selected_channel_index)
        self.joystick_armed_by[direction] = False

    def handle_knob_cc(self, cc: int, value: int) -> bool:
        if cc not in all_knob_ccs:
            return False

        selected_rack_instance_idx = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_rack_instance_idx is None or selected_rack_instance_idx < 0:
            return False

        knob_idx = knob_ccs.index(cc)

        if self.active_plugin_key is None:
            return False

        mapping = mappings_cache.get(self.active_plugin_key)
        if mapping is None:
            return False
        mapped_parameter = mapping[knob_idx]

        if mapped_parameter is None:
            # Leave event.handled unset so FL Studio's manual MIDI link
            # system can still pick up the CC if the user wants to bind it.
            return False

        scaled_value = value / 127.0

        try:
            FL_PLUGINS.setParamValue(
                scaled_value, mapped_parameter.index, selected_rack_instance_idx
            )
        except Exception as e:
            print("Knob mapping error:", e)

        return True

    def global_transport(self, command: int, value: int = 1) -> None:
        """
        Safe wrapper because FL builds differ on globalTransport argument count.
        """
        try:
            FL_TRANSPORT.globalTransport(command, value)
        except TypeError:
            FL_TRANSPORT.globalTransport(command, value, 0)

    def handle_transport_pad(self, action: str, value: int) -> bool:
        """
        Pads in toggle mode may send any nonzero value as ON and 0 as OFF.
        Do not compare only against 127.
        """
        is_on = value > 0

        try:
            if action == "play_pause":
                if is_on:
                    FL_TRANSPORT.start()
                else:
                    self.global_transport(10, 1)  # Play/Pause command

            elif action == "stop":
                if is_on:
                    FL_TRANSPORT.stop()

            elif action == "record":
                FL_TRANSPORT.record()

            elif action == "snap_next":
                if is_on:
                    FL_UI.snapMode(1)

            elif action == "songpat":
                if is_on:
                    FL_TRANSPORT.setLoopMode()

            elif action == "metronome":
                current_on = FL_GENERAL.getUseMetronome() != 0

                if current_on != is_on:
                    self.global_transport(110, 1)

            return True

        except Exception as e:
            print("Transport pad error:", e)
            return False

    def handle_fruity_slicer_2_pad_note(self, event: FLMidiEvent) -> bool:
        """
        Remap MPK Mini pad note bank notes 44-51 to Fruity Slicer 2 slice notes 60-67.
        This only runs when Fruity Slicer 2 is the selected channel/plugin.
        """
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return False

        plugin_name = FL_PLUGINS.getPluginName(selected_channel_index).lower()

        if "fruity slicer 2" not in plugin_name:
            return False

        status = event.status & 0xF0
        note = event.data1
        velocity = event.data2

        if note not in pad_note_bank_notes:
            return False

        pad_index = pad_note_bank_notes.index(note)
        mapped_note = fruity_slicer_2_slice_notes[pad_index]

        try:
            if status == 0x90 and velocity > 0:
                FL_CHANNELS.midiNoteOn(selected_channel_index, mapped_note, velocity)
            else:
                FL_CHANNELS.midiNoteOn(selected_channel_index, mapped_note, 0)

            event.handled = True
            return True

        except Exception as e:
            print("Fruity Slicer 2 pad remap error:", e)
            return False


class MpkHandler:
    def __init__(self) -> None:
        self.midi_handler = MidiHandler()
        self.last_rack_instance_idx = -99

    def handle_init(self) -> None:
        mappings_cache.clear()
        for rack_instance_idx in range(FL_CHANNELS.channelCount()):
            plugin_visible_name = FL_PLUGINS.getPluginName(
                rack_instance_idx, userName=True
            )
            key = (rack_instance_idx, plugin_visible_name)
            mappings_cache.put(key, self.build_knob_mapping(rack_instance_idx))
        print(
            f"MPK Mini Mk2 Smart Focus - loaded\n"
            f"Mappings cache:\n{mappings_cache.to_print()}"
        )

    def handle_refresh(self, flags: int) -> None:
        selected_rack_instance_idx = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_rack_instance_idx is None or selected_rack_instance_idx < 0:
            self.midi_handler.set_active_plugin_key(None)
            return

        plugin_visible_name = FL_PLUGINS.getPluginName(
            selected_rack_instance_idx, userName=True
        )
        self.last_rack_instance_idx = selected_rack_instance_idx
        active_plugin_key = (selected_rack_instance_idx, plugin_visible_name)
        if mappings_cache.get(active_plugin_key) is None:
            mappings_cache.put(
                active_plugin_key,
                self.build_knob_mapping(selected_rack_instance_idx),
            )
        self.midi_handler.set_active_plugin_key(active_plugin_key)

    def handle_midi_msg(self, event: FLMidiEvent) -> None:
        self.midi_handler.handle_midi_msg(event)

    def scan_plugin_parameters(self, channel_index: int) -> ParametersByIndex:
        """
        Scan plugin parameter names once by FL parameter index.
        """

        param_count = FL_PLUGINS.getParamCount(channel_index)
        # VST wrappers may report 4240 slots; first 4096 are plugin params.
        empty_streak_limit = 64
        scan_limit = min(param_count, 4096)

        parameters_by_index = {}
        empty_streak = 0
        for parameter_index in range(scan_limit):
            name = FL_PLUGINS.getParamName(parameter_index, channel_index)
            if name.strip():
                parameters_by_index[parameter_index] = name.lower()
                empty_streak = 0
            else:
                empty_streak += 1
                if empty_streak >= empty_streak_limit:
                    break
        return parameters_by_index

    def resolve_plugin_map(
        self,
        parameters_by_index: ParametersByIndex,
        plugin_key: str,
    ) -> KnobMapping:
        """
        Build knob list using exact name matching from plugin_maps.
        Returns [...8...].
        """
        used = set()
        blocked_fallback_slots = set()
        result = [None] * 8

        for knob_index, target in enumerate(plugin_maps[plugin_key]):
            if target is None:
                continue

            mapped_parameter = None
            if isinstance(target, int):
                name = parameters_by_index.get(target)
                if name is not None:
                    mapped_parameter = MappedParameter(target, name)
            else:
                target = target.lower()
                for parameter_index, name in parameters_by_index.items():
                    if name == target:
                        mapped_parameter = MappedParameter(parameter_index, name)
                        break

            if mapped_parameter is None:
                blocked_fallback_slots.add(knob_index)
                continue

            result[knob_index] = mapped_parameter
            used.add(mapped_parameter.index)

        self.fill_fallback(
            result, parameters_by_index, used, blocked_fallback_slots
        )
        return result

    def resolve_fallback_map(
        self, parameters_by_index: ParametersByIndex
    ) -> KnobMapping:
        """
        Build 8-knob list using keyword priority for unknown plugins.
        """
        used = set()
        result = [None] * 8
        self.fill_fallback(result, parameters_by_index, used)
        return result

    def fill_fallback(
        self,
        result: KnobMapping,
        parameters_by_index: ParametersByIndex,
        used: set[ParamIndex],
        blocked_slots: set[int] | None = None,
    ) -> None:
        """Apply fallback_priority to any still-None slots."""
        if blocked_slots is None:
            blocked_slots = set()

        for knob_index, keywords in fallback_priority:
            if knob_index in blocked_slots:
                continue
            if result[knob_index] is not None:
                continue
            for parameter_index, name in parameters_by_index.items():
                if parameter_index in used:
                    continue
                if any(keyword in name for keyword in never_map):
                    continue
                if any(keyword in name for keyword in keywords):
                    result[knob_index] = MappedParameter(parameter_index, name)
                    used.add(parameter_index)
                    break

    def build_knob_mapping(self, channel_index: int) -> KnobMapping:
        plugin_name = FL_PLUGINS.getPluginName(channel_index).lower()
        parameters_by_index = self.scan_plugin_parameters(channel_index)

        matched_key = None
        for key in plugin_maps:
            if key in plugin_name:
                matched_key = key
                break

        if matched_key:
            return self.resolve_plugin_map(parameters_by_index, matched_key)
        else:
            return self.resolve_fallback_map(parameters_by_index)


# ── FL Studio callbacks ────────────────────────────────────────────────────────


handler = MpkHandler()


def OnInit() -> None:
    handler.handle_init()


def OnMidiMsg(event: FLMidiEvent) -> None:
    handler.handle_midi_msg(event)


def OnRefresh(flags: int) -> None:
    handler.handle_refresh(flags)


def OnIdle() -> None:
    return
