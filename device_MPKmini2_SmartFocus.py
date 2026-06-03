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


class PluginParameters:
    def __init__(self, name: str) -> None:
        self.name = name
        self.by_name = {}
        self.safe_by_name = {}
        self.by_index = {}


KnobMapping = list[MappedParameter | None]
MappedParametersByName = dict[str, MappedParameter]


# ── CC configuration ───────────────────────────────────────────────────────────


class MidiStatus:
    MASK = 0xF0
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    CONTROL_CHANGE = 0xB0


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
joystick_preset_next_cc = mpk_controls["joystick"]["preset_next"]["cc"]
joystick_preset_prev_cc = mpk_controls["joystick"]["preset_previous"]["cc"]
joystick_preset_trigger_value = mpk_controls["joystick"]["trigger_value"]
fruity_slicer_2_slice_notes = [60, 61, 62, 63, 64, 65, 66, 67]

max_scan = 4096
debug_mapping = False

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

refresh_delay_ticks = 5

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


class MpkHandler:
    def __init__(self) -> None:
        self.knob_mappings_by_channel = {}
        self.last_channel = -99
        self.joystick_next_armed = True
        self.joystick_prev_armed = True
        self.pending_refresh_channel = None
        self.pending_refresh_ticks = 0

    def handle_init(self) -> None:
        print("==========================================")
        print("  MPK Mini Mk2 Smart Focus - loaded")
        print("  Knobs K1-K8 (CC 1-8): performance params")
        print("  Joystick Y (CC 100/50): preset next/previous")
        print("  Pad CC bank (CC 20-27): transport/snap")
        print("  Fruity Slicer 2 pads: notes 44-51 -> 60-67")
        print("==========================================")

    def get_mapping(self, channel_index: int) -> KnobMapping:
        if channel_index not in self.knob_mappings_by_channel:
            self.knob_mappings_by_channel[channel_index] = self.build_knob_mapping(
                channel_index
            )
        return self.knob_mappings_by_channel[channel_index]

    def invalidate_channel_mapping(self, channel_index: int) -> None:
        self.knob_mappings_by_channel.pop(channel_index, None)

    def print_mapping(self, channel_index: int) -> None:
        mapping = self.get_mapping(channel_index)
        channel_name = FL_CHANNELS.getChannelName(channel_index)
        plugin_name = FL_PLUGINS.getPluginName(channel_index)

        print("")
        print(f"  [ Smart Focus -> {channel_name} ({plugin_name}) ]")
        print("  Knobs:")
        for knob_index, mapped_parameter in enumerate(mapping):
            cc = knob_ccs[knob_index]
            name = "(unmapped)" if mapped_parameter is None else mapped_parameter.name
            print(f"    K{knob_index + 1} CC{cc}  ->  {name}")
        print("")

    def handle_refresh(self, flags: int) -> None:
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return

        if selected_channel_index != self.last_channel:
            self.last_channel = selected_channel_index
            self.pending_refresh_channel = selected_channel_index
            self.pending_refresh_ticks = refresh_delay_ticks

    def handle_idle(self) -> None:
        if self.pending_refresh_channel is None:
            return

        if self.pending_refresh_ticks > 0:
            self.pending_refresh_ticks -= 1
            return

        channel_index = self.pending_refresh_channel
        self.pending_refresh_channel = None

        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index != channel_index:
            return

        self.invalidate_channel_mapping(channel_index)
        self.print_mapping(channel_index)

    def handle_preset_joystick(self, cc: int, value: int) -> bool:
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return False

        try:
            if cc == joystick_preset_next_cc:
                if value < joystick_preset_trigger_value:
                    self.joystick_next_armed = True
                    return True
                if not self.joystick_next_armed:
                    return True
                FL_PLUGINS.nextPreset(selected_channel_index)
                FL_UI.setHintMsg("Preset: Next")
                self.joystick_next_armed = False

            elif cc == joystick_preset_prev_cc:
                if value < joystick_preset_trigger_value:
                    self.joystick_prev_armed = True
                    return True
                if not self.joystick_prev_armed:
                    return True
                FL_PLUGINS.prevPreset(selected_channel_index)
                FL_UI.setHintMsg("Preset: Previous")
                self.joystick_prev_armed = False

            else:
                return False

            return True

        except Exception as e:
            print("Preset joystick error:", e)
            return False

    def handle_midi_msg(self, event: FLMidiEvent) -> None:
        match event.status & MidiStatus.MASK:
            case MidiStatus.NOTE_ON | MidiStatus.NOTE_OFF:
                self.handle_fruity_slicer_2_pad_note(event)

            case MidiStatus.CONTROL_CHANGE:
                self.handle_control_change(event)

            case _:
                return

    def handle_control_change(self, event: FLMidiEvent) -> None:
        cc = event.data1
        value = event.data2

        match cc:
            case cc if cc in (joystick_preset_next_cc, joystick_preset_prev_cc):
                event.handled = self.handle_preset_joystick(cc, value)

            case cc if cc in pad_cc_actions_by_cc:
                event.handled = self.handle_transport_pad(
                    pad_cc_actions_by_cc[cc], value
                )

            case cc if cc in all_knob_ccs:
                event.handled = self.handle_knob_cc(cc, value)

            case _:
                return

    def handle_knob_cc(self, cc: int, value: int) -> bool:
        if cc not in all_knob_ccs:
            return False

        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return False

        knob_index = knob_ccs.index(cc)

        mapping = self.get_mapping(selected_channel_index)
        mapped_parameter = mapping[knob_index]

        if mapped_parameter is None:
            # Leave event.handled unset so FL Studio's manual MIDI link
            # system can still pick up the CC if the user wants to bind it.
            return False

        scaled_value = value / 127.0

        try:
            FL_PLUGINS.setParamValue(
                scaled_value, mapped_parameter.index, selected_channel_index
            )
            channel_name = FL_CHANNELS.getChannelName(selected_channel_index)
            pct = round(scaled_value * 100)
            FL_UI.setHintMsg(
                f"{channel_name}  |  K{knob_index + 1}: {mapped_parameter.name} = {pct}%"
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
                    FL_UI.setHintMsg("Transport: Play")
                else:
                    self.global_transport(10, 1)  # Play/Pause command
                    FL_UI.setHintMsg("Transport: Pause")

            elif action == "stop":
                if is_on:
                    FL_TRANSPORT.stop()
                    FL_UI.setHintMsg("Transport: Stop")

            elif action == "record":
                FL_TRANSPORT.record()
                if is_on:
                    FL_UI.setHintMsg("Transport: Record ON")
                else:
                    FL_UI.setHintMsg("Transport: Record OFF")

            elif action == "snap_next":
                if is_on:
                    FL_UI.snapMode(1)
                    try:
                        snap_name = snap_names.get(
                            FL_UI.getSnapMode(),
                            f"mode {FL_UI.getSnapMode()}",
                        )
                    except Exception:
                        snap_name = "changed"
                    FL_UI.setHintMsg(f"Snap: {snap_name}")

            elif action == "songpat":
                if is_on:
                    FL_TRANSPORT.setLoopMode()
                    FL_UI.setHintMsg("Transport: Pattern/Song toggle")

            elif action == "metronome":
                current_on = FL_GENERAL.getUseMetronome() != 0

                if current_on != is_on:
                    self.global_transport(110, 1)

                if is_on:
                    FL_UI.setHintMsg("Metronome: ON")
                else:
                    FL_UI.setHintMsg("Metronome: OFF")

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

        try:
            plugin_name = FL_PLUGINS.getPluginName(selected_channel_index).lower()
        except Exception:
            plugin_name = ""

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
                FL_UI.setHintMsg(
                    f"Fruity Slicer 2: Pad {pad_index + 1} -> Slice note {mapped_note}"
                )
            else:
                FL_CHANNELS.midiNoteOn(selected_channel_index, mapped_note, 0)

            event.handled = True
            return True

        except Exception as e:
            print("Fruity Slicer 2 pad remap error:", e)
            return False

    def scan_plugin_parameters(self, channel_index: int) -> PluginParameters:
        """
        Scan plugin parameter names once and keep both lookup shapes needed by
        exact plugin maps and fallback keyword matching.
        """
        try:
            plugin_name = FL_PLUGINS.getPluginName(channel_index).lower()
        except Exception:
            plugin_name = ""

        parameters = PluginParameters(plugin_name)
        empty_streak = 0
        for parameter_index in range(max_scan):
            try:
                name = FL_PLUGINS.getParamName(parameter_index, channel_index)
            except Exception:
                break
            if name and name.strip():
                name_lower = name.lower()
                mapped_parameter = MappedParameter(parameter_index, name)
                parameters.by_index[parameter_index] = mapped_parameter
                if name_lower not in parameters.by_name:
                    parameters.by_name[name_lower] = mapped_parameter
                if not any(keyword in name_lower for keyword in never_map):
                    parameters.safe_by_name[name_lower] = mapped_parameter
                empty_streak = 0
            else:
                empty_streak += 1
                if empty_streak >= 64:
                    break
        return parameters

    def resolve_plugin_map(
        self,
        channel_index: int,
        parameters: PluginParameters,
        plugin_key: str,
    ) -> KnobMapping:
        """
        Build knob list using exact name matching from plugin_maps.
        Uses unfiltered params for explicit user choices, then safe params
        (never_map excluded) for per-knob fallback.
        Returns [...8...].
        """
        spec = plugin_maps[plugin_key]
        used = set()
        blocked_fallback_slots = set()
        result = [None] * 8

        for knob_index, target_name in enumerate(spec):
            if target_name is None:
                continue
            if isinstance(target_name, int):
                mapped_parameter = parameters.by_index.get(target_name)
                if mapped_parameter is None:
                    mapped_parameter = MappedParameter(
                        target_name,
                        FL_PLUGINS.getParamName(target_name, channel_index),
                    )
            else:
                mapped_parameter = parameters.by_name.get(target_name.lower())
            if debug_mapping:
                print(
                    "DEBUG map",
                    plugin_key,
                    knob_index + 1,
                    repr(target_name),
                    "->",
                    None if mapped_parameter is None else mapped_parameter.index,
                )
            if mapped_parameter is not None:
                result[knob_index] = mapped_parameter
                used.add(mapped_parameter.index)
            else:
                blocked_fallback_slots.add(knob_index)

        # Fill remaining None slots via fallback keywords (filtered index only)
        self.fill_fallback(result, parameters.safe_by_name, used, blocked_fallback_slots)
        return result

    def resolve_fallback_map(self, mapped_parameters_by_name: MappedParametersByName) -> KnobMapping:
        """
        Build 8-knob list using keyword priority for unknown plugins.
        mapped_parameters_by_name must be pre-filtered (never_map excluded).
        """
        used = set()
        result = [None] * 8
        self.fill_fallback(result, mapped_parameters_by_name, used)
        return result

    def fill_fallback(
        self,
        result: KnobMapping,
        mapped_parameters_by_name: MappedParametersByName,
        used: set[ParamIndex],
        blocked_slots: set[int] | None = None,
    ) -> None:
        """Apply fallback_priority to any still-None slots.
        Assumes mapped_parameters_by_name has already been filtered against never_map."""
        if blocked_slots is None:
            blocked_slots = set()

        for knob_index, keywords in fallback_priority:
            if knob_index in blocked_slots:
                continue
            if result[knob_index] is not None:
                continue
            for name_lower, mapped_parameter in mapped_parameters_by_name.items():
                if mapped_parameter.index in used:
                    continue
                if any(keyword in name_lower for keyword in keywords):
                    result[knob_index] = mapped_parameter
                    used.add(mapped_parameter.index)
                    break

    def build_knob_mapping(self, channel_index: int) -> KnobMapping:
        parameters = self.scan_plugin_parameters(channel_index)

        matched_key = None
        for key in plugin_maps:
            if key in parameters.name:
                matched_key = key
                break

        if matched_key:
            if debug_mapping:
                print(
                    "DEBUG plugin",
                    parameters.name,
                    "channel index",
                    channel_index,
                    "param count",
                    len(parameters.by_name),
                )
                if matched_key == "flex":
                    for name_lower, mapped_parameter in parameters.by_name.items():
                        if (
                            "gated" in name_lower
                            or "character" in name_lower
                            or "filter envelope attack" in name_lower
                            or "reverb" in name_lower
                            or "delay" in name_lower
                        ):
                            print(
                                "DEBUG flex param",
                                mapped_parameter.index,
                                repr(name_lower),
                            )
            return self.resolve_plugin_map(channel_index, parameters, matched_key)
        else:
            # Unknown plugin — fallback only sees safe params
            return self.resolve_fallback_map(parameters.safe_by_name)


# ── FL Studio callbacks ────────────────────────────────────────────────────────


handler = MpkHandler()


def OnInit() -> None:
    handler.handle_init()


def OnMidiMsg(event: FLMidiEvent) -> None:
    handler.handle_midi_msg(event)


def OnRefresh(flags: int) -> None:
    handler.handle_refresh(flags)


def OnIdle() -> None:
    handler.handle_idle()
