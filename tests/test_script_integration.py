def test_known_plugin_knob_sets_parameter(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {10: "Macro 1", 11: "Macro 2"}
    script = fl_env.load_script()
    script.OnInit()
    script.OnRefresh(0)

    event = fl_env.cc(1, 64)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.plugins.set_param_calls == [(64 / 127.0, 10, 0)]


def test_unknown_plugin_keyword_fallback(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {0: "Volume", 1: "Cutoff", 2: "Resonance"}
    script = fl_env.load_script()
    script.OnInit()
    script.OnRefresh(0)

    cutoff = fl_env.cc(1, 127)
    resonance = fl_env.cc(2, 32)
    script.OnMidiMsg(cutoff)
    script.OnMidiMsg(resonance)

    assert cutoff.handled is True
    assert resonance.handled is True
    assert fl_env.plugins.set_param_calls == [(1.0, 1, 0), (32 / 127.0, 2, 0)]


def test_knob_outside_controls_unhandled(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {0: "Volume envelope attack"}
    script = fl_env.load_script()

    event = fl_env.cc(9, 127)
    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_knob_on_denylist_only_params_unhandled(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {0: "Volume"}
    script = fl_env.load_script()
    script.OnInit()
    script.OnRefresh(0)

    event = fl_env.cc(1, 100)
    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_knob_on_invalid_channel_no_crash(fl_env):
    fl_env.plugins.names = {}
    fl_env.plugins.valid_channels = set()
    fl_env.plugins.params = {}
    script = fl_env.load_script()
    script.OnInit()

    event = fl_env.cc(1, 64)
    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_knob_lazy_resolve_without_oninit(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {10: "Macro 1"}
    script = fl_env.load_script()

    event = fl_env.cc(1, 64)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.plugins.set_param_calls == [(64 / 127.0, 10, 0)]


def test_transport_pad_play(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(20, 127)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == [("start", ())]


def test_transport_pad_stop(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(21, 127)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == [("stop", ())]


def test_transport_pad_record_unconditional(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(22, 0)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == [("record", ())]


def test_transport_pad_snap(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(23, 127)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.ui.snap_calls == 1


def test_transport_pad_songpat(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(24, 127)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == [("setLoopMode", ())]


def test_transport_pad_metronome(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(27, 127)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == [("globalTransport", (110, 1))]


def test_transport_pad_metronome_release(fl_env):
    script = fl_env.load_script()

    event = fl_env.cc(27, 0)
    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.transport.calls == []


def test_fruity_slicer_2_note_remap(fl_env):
    fl_env.plugins.names[0] = "Fruity Slicer 2"
    script = fl_env.load_script()

    note_on = fl_env.note_on(36, 96)
    note_off = fl_env.note_off(36)
    script.OnMidiMsg(note_on)
    script.OnMidiMsg(note_off)

    assert note_on.handled is True
    assert note_off.handled is True
    assert fl_env.channels.midi_notes == [(0, 60, 96), (0, 60, 0)]


def test_non_slicer_note_unhandled(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    script = fl_env.load_script()

    event = fl_env.note_on(36, 100)
    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.channels.midi_notes == []
