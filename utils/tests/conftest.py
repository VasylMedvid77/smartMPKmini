import builtins
import importlib.util
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "device_MPKmini2_SmartFocus.py"


class MidiEvent:
    def __init__(self, status, data1, data2):
        self.status = status
        self.data1 = data1
        self.data2 = data2
        self.handled = False


@dataclass
class FakeChannels:
    selected: int | None = 0
    names: dict[int, str] = field(default_factory=lambda: {0: "Test Channel"})
    midi_notes: list[tuple[int, int, int]] = field(default_factory=list)

    def selectedChannel(self, canBeNone=True):
        return self.selected

    def getChannelName(self, chan):
        return self.names.get(chan, f"Channel {chan}")

    def midiNoteOn(self, chan, note, velocity):
        self.midi_notes.append((chan, note, velocity))


@dataclass
class FakePlugins:
    names: dict[int, str] = field(default_factory=lambda: {0: "Test Plugin"})
    params: dict[int, dict[int, str]] = field(default_factory=dict)
    set_param_calls: list[tuple[float, int, int]] = field(default_factory=list)
    next_preset_calls: list[int] = field(default_factory=list)
    prev_preset_calls: list[int] = field(default_factory=list)
    fail_set_param: Exception | None = None
    get_param_name_calls: list[tuple[int, int]] = field(default_factory=list)

    def getPluginName(self, chan):
        return self.names.get(chan, "")

    def getParamName(self, index, chan):
        self.get_param_name_calls.append((index, chan))
        return self.params.get(chan, {}).get(index, "")

    def setParamValue(self, value, index, chan):
        if self.fail_set_param is not None:
            raise self.fail_set_param
        self.set_param_calls.append((value, index, chan))

    def nextPreset(self, chan):
        self.next_preset_calls.append(chan)

    def prevPreset(self, chan):
        self.prev_preset_calls.append(chan)


@dataclass
class FakeTransport:
    calls: list[tuple[str, tuple]] = field(default_factory=list)

    def start(self):
        self.calls.append(("start", ()))

    def stop(self):
        self.calls.append(("stop", ()))

    def record(self):
        self.calls.append(("record", ()))

    def setLoopMode(self):
        self.calls.append(("setLoopMode", ()))

    def globalTransport(self, *args):
        self.calls.append(("globalTransport", args))


@dataclass
class FakeUi:
    hints: list[str] = field(default_factory=list)
    snap_mode: int = 0

    def setHintMsg(self, message):
        self.hints.append(message)

    def snapMode(self, delta):
        self.snap_mode += delta

    def getSnapMode(self):
        return self.snap_mode


@dataclass
class FakeGeneral:
    metronome_on: bool = False

    def getUseMetronome(self):
        return int(self.metronome_on)


@dataclass
class FlStudioEnvironment:
    channels: FakeChannels = field(default_factory=FakeChannels)
    plugins: FakePlugins = field(default_factory=FakePlugins)
    transport: FakeTransport = field(default_factory=FakeTransport)
    ui: FakeUi = field(default_factory=FakeUi)
    general: FakeGeneral = field(default_factory=FakeGeneral)
    prints: list[tuple] = field(default_factory=list)
    module: types.ModuleType | None = None

    def load_script(self):
        modules = {
            "channels": _module_from_object("channels", self.channels),
            "plugins": _module_from_object("plugins", self.plugins),
            "transport": _module_from_object("transport", self.transport),
            "ui": _module_from_object("ui", self.ui),
            "general": _module_from_object("general", self.general),
        }
        spec = importlib.util.spec_from_file_location("device_under_test", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        with (
            patch.dict(sys.modules, modules),
            patch.object(builtins, "print", self.capture_print),
        ):
            spec.loader.exec_module(module)
        self.module = module
        return module

    def cc(self, control, value):
        return MidiEvent(0xB0, control, value)

    def note_on(self, note, velocity=100):
        return MidiEvent(0x90, note, velocity)

    def note_off(self, note):
        return MidiEvent(0x80, note, 0)

    def run_with_print_capture(self, callback, *args):
        with patch.object(builtins, "print", self.capture_print):
            return callback(*args)

    def capture_print(self, *args):
        self.prints.append(args)


def _module_from_object(name, source):
    module = types.ModuleType(name)
    for attr in dir(source):
        if not attr.startswith("_"):
            setattr(module, attr, getattr(source, attr))
    return module


@pytest.fixture
def fl_env():
    return FlStudioEnvironment()
