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
ControlName = str
PluginName = str
PluginControlTarget = str | int
ControlInput = dict[str, int | None]
PluginControlMapping = dict[ControlName, PluginControlTarget]
SmartGuessMapping = dict[ControlName, list[str]]
ActionMapping = dict[ControlName, str | dict[str, int | str]]
NoteMapping = dict[PluginName, dict[ControlName, int]]


class MappedParameter:
    def __init__(self, index: ParamIndex, name: str) -> None:
        self.index = index
        self.name = name


MidiControlMapping = dict[int, MappedParameter]
PluginRuntimeParameters = dict[PluginControlTarget, MappedParameter]
PluginInstanceKey = tuple[int, str]


class MappingsCache:
    def __init__(self) -> None:
        self._items: dict[PluginInstanceKey, MidiControlMapping] = {}

    def clear(self) -> None:
        self._items.clear()

    def put(self, key: PluginInstanceKey, mapping: MidiControlMapping) -> None:
        self._items[key] = mapping

    def get(self, key: PluginInstanceKey) -> MidiControlMapping | None:
        return self._items.get(key)

    def to_print(self) -> str:
        return "\n".join(str(key) for key in self._items)


mappings_cache = MappingsCache()


# ── Mapping configuration ─────────────────────────────────────────────────────


class MidiStatus:
    MASK = 0xF0
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    CONTROL_CHANGE = 0xB0


DEFAULT_CONTROLS: dict[ControlName, ControlInput] = {
    "k1": {"cc": 1, "note": None},
    "k2": {"cc": 2, "note": None},
    "k3": {"cc": 3, "note": None},
    "k4": {"cc": 4, "note": None},
    "k5": {"cc": 5, "note": None},
    "k6": {"cc": 6, "note": None},
    "k7": {"cc": 7, "note": None},
    "k8": {"cc": 8, "note": None},
    "pad1": {"cc": 20, "note": 44},
    "pad2": {"cc": 21, "note": 45},
    "pad3": {"cc": 22, "note": 46},
    "pad4": {"cc": 23, "note": 47},
    "pad5": {"cc": 24, "note": 48},
    "pad6": {"cc": None, "note": 49},
    "pad7": {"cc": None, "note": 50},
    "pad8": {"cc": 27, "note": 51},
    "joystick_next": {"cc": 50, "note": None},
    "joystick_previous": {"cc": 100, "note": None},
}


class MappingConfig:
    def __init__(self, controls: dict[ControlName, ControlInput] | None = None) -> None:
        self.controls: dict[ControlName, ControlInput] = {}
        self.plugin_mappings: dict[PluginName, PluginControlMapping] = {}
        self.smart_guess_mappings: SmartGuessMapping = {}
        self.action_mappings: ActionMapping = {}
        self.note_mappings: NoteMapping = {}

        self.add_controls(DEFAULT_CONTROLS if controls is None else controls)

    def add_controls(self, controls: dict[ControlName, ControlInput]) -> None:
        controls_by_cc = {}
        for raw_control_name, raw_control_input in controls.items():
            control_name = raw_control_name.strip().lower()
            cc = raw_control_input.get("cc")
            note = raw_control_input.get("note")

            if control_name in self.controls:
                print("Duplicate control:", control_name)
                continue
            if cc is None and note is None:
                print("Control must define cc or note:", control_name)
                continue
            if cc is not None and cc in controls_by_cc:
                print("Duplicate CC:", cc, control_name)
                continue

            self.controls[control_name] = {"cc": cc, "note": note}
            if cc is not None:
                controls_by_cc[cc] = control_name

    def add_plugin_mapping(
        self,
        plugin_name: str,
        control_mapping: PluginControlMapping,
    ) -> None:
        normalized_mapping = {}
        for raw_control_name, raw_target in control_mapping.items():
            control_name = raw_control_name.strip().lower()

            if control_name not in self.controls:
                print("Unknown plugin mapping control:", control_name)
                continue

            if isinstance(raw_target, str):
                target = raw_target.strip().lower()
            else:
                target = raw_target

            normalized_mapping[control_name] = target

        self.plugin_mappings[plugin_name.strip().lower()] = normalized_mapping

    def add_smart_guess_mapping(self, control_mapping: SmartGuessMapping) -> None:
        for raw_control_name, raw_keywords in control_mapping.items():
            control_name = raw_control_name.strip().lower()

            if control_name not in self.controls:
                print("Unknown smart guess control:", control_name)
                continue

            self.smart_guess_mappings[control_name] = [
                keyword.strip().lower() for keyword in raw_keywords
            ]

    def add_action_mapping(self, control_mapping: ActionMapping) -> None:
        for raw_control_name, raw_action in control_mapping.items():
            control_name = raw_control_name.strip().lower()

            if control_name not in self.controls:
                print("Unknown action control:", control_name)
                continue

            if isinstance(raw_action, str):
                self.action_mappings[control_name] = raw_action.strip().lower()
            else:
                self.action_mappings[control_name] = {
                    key.strip().lower(): value.strip().lower()
                    if isinstance(value, str)
                    else value
                    for key, value in raw_action.items()
                }

    def add_note_mapping(
        self,
        plugin_name: str,
        control_mapping: dict[ControlName, int],
    ) -> None:
        normalized_mapping = {}
        for raw_control_name, output_note in control_mapping.items():
            control_name = raw_control_name.strip().lower()

            if control_name not in self.controls:
                print("Unknown note mapping control:", control_name)
                continue

            normalized_mapping[control_name] = output_note

        self.note_mappings[plugin_name.strip().lower()] = normalized_mapping

mapping_config = MappingConfig()

mapping_config.add_plugin_mapping(
    "kepler",
    {
        "k1": "VCF Frequency",
        "k2": "VCF Reso",
        "k3": "VCF Env",
        "k4": "VCF LFO",
        "k5": "LFO rate",
        "k6": "DCO PWM",
        "k7": "HPF Frequency",
        "k8": "DCO LFO",
    },
)
mapping_config.add_plugin_mapping(
    "flex",
    {
        "k1": 10,  # macro 1
        "k2": 11,  # macro 2
        "k3": 12,  # macro 3: preset-dependent label, e.g. Gated/Unison
        "k4": 13,
        "k5": 14,
        "k6": 15,
        "k7": "Volume envelope attack",
        "k8": "Volume envelope release",
    },
)
mapping_config.add_plugin_mapping(
    "sawer",
    {
        "k1": "Filter cutoff",
        "k2": "Filter resolution",
        "k3": "EGF amount",
        "k4": "Reverb mix",
        "k5": "Chorus depth",
        "k6": "LFO speed",
        "k7": "LFO amount",
        "k8": "Noise level",
    },
)
mapping_config.add_plugin_mapping(
    "mini synth",
    {
        "k1": "FLT Freq",
        "k2": "FLT Peak",
        "k3": "EGF Amnt",
        "k4": "LFO Rate",
        "k5": "LFO Amnt",
        "k6": "DIST",
        "k7": "Overdrive",
        "k8": "Decimator",
    },
)
mapping_config.add_plugin_mapping(
    "3x osc",
    {
        "k1": "Filter frequency (modulation X)",
        "k2": "Filter bandwidth (modulation Y)",
        "k3": "Stereo phase randomness",
        "k4": "Osc 2 mix level",
        "k5": "Osc 3 mix level",
        "k6": "Osc 1 coarse pitch",
        "k7": "Osc 2 coarse pitch",
        "k8": "Osc 3 coarse pitch",
    },
)
mapping_config.add_plugin_mapping(
    "granulizer",
    {
        "k1": "Filter frequency (modulation X)",
        "k2": "Filter bandwidth (modulation Y)",
        "k3": "Grain attack time",
        "k4": "Grain hold time",
        "k5": "Grain spacing",
        "k6": "Wave spacing",
        "k7": "Sample start",
        "k8": "Effect depth",
    },
)
mapping_config.add_plugin_mapping(
    "fpc",
    {
        "k1": "Pad 1 volume",
        "k2": "Pad 2 volume",
        "k3": "Pad 3 volume",
        "k4": "Pad 4 volume",
        "k5": "Pad 5 volume",
        "k6": "Pad 6 volume",
        "k7": "Pad 7 volume",
        "k8": "Pad 8 volume",
    },
)
mapping_config.add_plugin_mapping(
    "fruity slicer 2",
    {
        "k1": "Cutoff",
        "k2": "Res",
        "k3": "Transpose",
        "k4": "Detune",
    },
)

mapping_config.add_smart_guess_mapping(
    {
        "k1": [
            "macro 1",
            "macro1",
            "x1 ",
            "mod x",
            "filter frequency (modulation x)",
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
        "k2": [
            "macro 2",
            "macro2",
            "x2 ",
            "mod y",
            "filter bandwidth (modulation y)",
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
        "k3": [
            "macro 3",
            "macro3",
            "x3 ",
            "filter env",
            "vcf env",
            "egf amount",
            "egf amnt",
            "filter env amt",
            "env amt",
            "env amount",
            "filter mod",
        ],
        "k4": [
            "macro 4",
            "macro4",
            "x4 ",
            "reverb mix",
            "reverb wet",
            "reverb amount",
            "reverb level",
        ],
        "k5": ["lfo rate", "lfo speed", "lfo freq", "lfo 1 rate"],
        "k6": ["lfo amount", "lfo depth", "lfo amnt", "lfo 1 depth", "lfo level"],
        "k7": [
            "chorus depth",
            "chorus mix",
            "ensemble",
            "unison detune",
            "detune",
            "spread",
            "character",
        ],
        "k8": [
            "drive",
            "distort",
            "overdrive",
            "saturat",
            "waveshap",
            "decimat",
            "bit crush",
            "noise level",
        ],
    }
)

mapping_config.add_action_mapping(
    {
        "pad1": "play_pause",
        "pad2": "stop",
        "pad3": "record",
        "pad4": "snap_next",
        "pad5": "songpat",
        "pad8": "metronome",
        "joystick_next": {
            "action": "preset",
            "direction": "next",
            "trigger_value": 64,
        },
        "joystick_previous": {
            "action": "preset",
            "direction": "previous",
            "trigger_value": 64,
        },
    }
)

mapping_config.add_note_mapping(
    "fruity slicer 2",
    {
        "pad1": 60,
        "pad2": 61,
        "pad3": 62,
        "pad4": 63,
        "pad5": 64,
        "pad6": 65,
        "pad7": 66,
        "pad8": 67,
    },
)

class MidiHandler:
    def __init__(self) -> None:
        self.active_plugin_key: PluginInstanceKey | None = None
        self.joystick_armed_by = {
            "next": True,
            "previous": True,
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
        self.handle_plugin_note_mapping(event)

    def handle_cc_msg(self, event: FLMidiEvent) -> None:
        cc = event.data1
        value = event.data2

        action = self.action_for_cc(cc)

        if isinstance(action, dict) and action.get("action") == "preset":
            direction = action["direction"]
            trigger_value = action["trigger_value"]
            event.handled = True
            self.handle_preset_joystick(direction, value, trigger_value)
            return

        match action:
            case action if action is not None:
                event.handled = self.handle_transport_pad(action, value)

            case _:
                event.handled = self.handle_knob_cc(cc, value)

    def action_for_cc(self, cc: int) -> str | dict[str, int | str] | None:
        for control_name, action in mapping_config.action_mappings.items():
            control = mapping_config.controls[control_name]
            if control["cc"] == cc:
                return action
        return None

    def handle_preset_joystick(
        self, direction: str, joystick_value: int, trigger_value: int
    ) -> None:
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return

        match direction:
            case "next":
                preset_action = FL_PLUGINS.nextPreset

            case "previous":
                preset_action = FL_PLUGINS.prevPreset

        if joystick_value < trigger_value:
            self.joystick_armed_by[direction] = True
            return

        if not self.joystick_armed_by[direction]:
            return

        preset_action(selected_channel_index)
        self.joystick_armed_by[direction] = False

    def handle_knob_cc(self, cc: int, value: int) -> bool:
        selected_rack_instance_idx = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_rack_instance_idx is None or selected_rack_instance_idx < 0:
            return False

        if self.active_plugin_key is None:
            return False

        mapping = mappings_cache.get(self.active_plugin_key)
        if mapping is None:
            return False
        mapped_parameter = mapping.get(cc)

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

        match action:
            case "play_pause":
                if is_on:
                    FL_TRANSPORT.start()
                else:
                    self.global_transport(10, 1)  # Play/Pause command

            case "stop":
                if is_on:
                    FL_TRANSPORT.stop()

            case "record":
                FL_TRANSPORT.record()

            case "snap_next":
                if is_on:
                    FL_UI.snapMode(1)

            case "songpat":
                if is_on:
                    FL_TRANSPORT.setLoopMode()

            case "metronome":
                current_on = FL_GENERAL.getUseMetronome() != 0

                if current_on != is_on:
                    self.global_transport(110, 1)

        return True

    def handle_plugin_note_mapping(self, event: FLMidiEvent) -> bool:
        """
        Remap configured note inputs when selected plugin has a note mapping.
        """
        selected_channel_index = FL_CHANNELS.selectedChannel(canBeNone=True)
        if selected_channel_index is None or selected_channel_index < 0:
            return False

        plugin_name = FL_PLUGINS.getPluginName(selected_channel_index).lower()

        status = event.status & 0xF0
        note = event.data1
        velocity = event.data2

        note_mapping = None
        for plugin_key, control_mapping in mapping_config.note_mappings.items():
            if plugin_key in plugin_name:
                note_mapping = control_mapping
                break

        if note_mapping is None:
            return False

        mapped_note = None
        for control_name, output_note in note_mapping.items():
            if mapping_config.controls[control_name]["note"] == note:
                mapped_note = output_note
                break

        if mapped_note is None:
            return False

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

    def handle_init(self) -> None:
        mappings_cache.clear()
        for rack_instance_idx in range(FL_CHANNELS.channelCount()):
            plugin_visible_name = FL_PLUGINS.getPluginName(
                rack_instance_idx, userName=True
            )
            key = (rack_instance_idx, plugin_visible_name)
            mappings_cache.put(key, self.resolve_plugin_instance_mapping(rack_instance_idx))
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
        active_plugin_key = (selected_rack_instance_idx, plugin_visible_name)
        if mappings_cache.get(active_plugin_key) is None:
            mappings_cache.put(
                active_plugin_key,
                self.resolve_plugin_instance_mapping(selected_rack_instance_idx),
            )
        self.midi_handler.set_active_plugin_key(active_plugin_key)

    def handle_midi_msg(self, event: FLMidiEvent) -> None:
        self.midi_handler.handle_midi_msg(event)

    def scan_fl_runtime_parameters(self, channel_index: int) -> PluginRuntimeParameters:
        """
        Scan plugin parameter names once by normalized name and FL parameter index.
        """

        param_count = FL_PLUGINS.getParamCount(channel_index)
        # VST wrappers may report 4240 slots; first 4096 are plugin params.
        scan_limit = min(param_count, 4096)

        plugin_runtime_parameters = {}
        for parameter_index in range(scan_limit):
            name = FL_PLUGINS.getParamName(parameter_index, channel_index)
            if name.strip():
                normalized_name = name.strip().lower()
                mapped_parameter = MappedParameter(parameter_index, normalized_name)
                plugin_runtime_parameters[normalized_name] = mapped_parameter
                plugin_runtime_parameters[parameter_index] = mapped_parameter
        return plugin_runtime_parameters

    def resolve_plugin_control_mapping(
        self,
        control_mapping: PluginControlMapping,
        plugin_runtime_parameters: PluginRuntimeParameters,
    ) -> MidiControlMapping:
        midi_control_mapping = {}

        for control_name, target in control_mapping.items():
            control = mapping_config.controls[control_name]
            cc = control["cc"]
            if cc is None:
                continue

            runtime_parameter = plugin_runtime_parameters.get(target)
            if runtime_parameter is None:
                continue

            midi_control_mapping[cc] = runtime_parameter

        return midi_control_mapping

    def resolve_smart_guess_mapping(
        self,
        plugin_runtime_parameters: PluginRuntimeParameters,
    ) -> MidiControlMapping:
        smart_guess_denylist = [
            "volume",
            "master vol",
            "output vol",
            "pan",
            "panorama",
            "panning",
            "master pan",
            "limiter",
        ]
        used = set()
        midi_control_mapping = {}

        for control_name, keywords in mapping_config.smart_guess_mappings.items():
            control = mapping_config.controls[control_name]
            cc = control["cc"]
            if cc is None:
                continue

            for target, runtime_parameter in plugin_runtime_parameters.items():
                if not isinstance(target, str):
                    continue
                if runtime_parameter.index in used:
                    continue
                if any(keyword in target for keyword in smart_guess_denylist):
                    continue
                if any(keyword in target for keyword in keywords):
                    midi_control_mapping[cc] = runtime_parameter
                    used.add(runtime_parameter.index)
                    break

        return midi_control_mapping

    def resolve_plugin_instance_mapping(self, channel_index: int) -> MidiControlMapping:
        plugin_name = FL_PLUGINS.getPluginName(channel_index).lower()
        plugin_runtime_parameters = self.scan_fl_runtime_parameters(channel_index)

        matched_key = None
        for key in mapping_config.plugin_mappings:
            if key in plugin_name:
                matched_key = key
                break

        if matched_key:
            return self.resolve_plugin_control_mapping(
                mapping_config.plugin_mappings[matched_key],
                plugin_runtime_parameters,
            )

        return self.resolve_smart_guess_mapping(plugin_runtime_parameters)


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
