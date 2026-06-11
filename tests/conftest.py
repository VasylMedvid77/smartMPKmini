import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "smart_MPK_mini_driver.py"


class MidiEvent:
    def __init__(self, status, data1, data2):
        self.status = status
        self.data1 = data1
        self.data2 = data2
        self.handled = False


class FakeChannels:
    def __init__(self):
        self.selected = 0
        self.midi_notes = []

    def selectedChannel(self, canBeNone=True):
        return self.selected

    def channelCount(self):
        return 1

    def midiNoteOn(self, chan, note, velocity):
        self.midi_notes.append((chan, note, velocity))


class FakePlugins:
    def __init__(self):
        self.names = {0: "Test Plugin"}
        self.params = {}
        self.set_param_calls = []
        self.valid_channels = None

    def isValid(self, chan, slotIndex=-1, useGlobalIndex=False):
        if self.valid_channels is not None:
            return chan in self.valid_channels
        return chan in self.names

    def getPluginName(self, chan, slotIndex=-1, userName=False, useGlobalIndex=False):
        return self.names.get(chan, "")

    def getParamCount(self, chan):
        params = self.params.get(chan, {})
        if not params:
            return 0
        return max(params) + 1

    def getParamName(self, index, chan):
        return self.params.get(chan, {}).get(index, "")

    def setParamValue(self, value, index, chan):
        self.set_param_calls.append((value, index, chan))


class FakeTransport:
    def __init__(self):
        self.calls = []

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


class FakeUi:
    def __init__(self):
        self.snap_calls = 0

    def snapMode(self, delta):
        self.snap_calls += delta


class FakeMidi:
    HW_ChannelEvent = 65536


class FlStudioEnvironment:
    def __init__(self):
        self.channels = FakeChannels()
        self.plugins = FakePlugins()
        self.transport = FakeTransport()
        self.ui = FakeUi()
        self.module = None

    def load_script(self):
        modules = {
            "channels": _module_from_object("channels", self.channels),
            "plugins": _module_from_object("plugins", self.plugins),
            "transport": _module_from_object("transport", self.transport),
            "ui": _module_from_object("ui", self.ui),
            "midi": _module_from_object("midi", FakeMidi()),
        }
        spec = importlib.util.spec_from_file_location("device_under_test", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        self.module = module
        return module

    def cc(self, control, value):
        return MidiEvent(0xB0, control, value)

    def note_on(self, note, velocity=100):
        return MidiEvent(0x90, note, velocity)

    def note_off(self, note):
        return MidiEvent(0x80, note, 0)


def _module_from_object(name, source):
    module = types.ModuleType(name)
    for attr in dir(source):
        if not attr.startswith("_"):
            setattr(module, attr, getattr(source, attr))
    return module


@pytest.fixture
def fl_env():
    return FlStudioEnvironment()
