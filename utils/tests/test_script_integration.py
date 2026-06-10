import pytest


def test_known_plugin_knob_maps_to_exact_parameter(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {
        10: "Macro 1",
        11: "Macro 2",
    }
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)
    script.OnRefresh(0)

    event = fl_env.cc(1, 64)

    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.plugins.set_param_calls == [(64 / 127.0, 10, 0)]


def test_unknown_plugin_knob_uses_keyword_fallback(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {
        0: "Volume",
        1: "Cutoff",
        2: "Resonance",
    }
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)
    script.OnRefresh(0)

    cutoff_event = fl_env.cc(1, 127)
    resonance_event = fl_env.cc(2, 32)

    script.OnMidiMsg(cutoff_event)
    script.OnMidiMsg(resonance_event)

    assert cutoff_event.handled is True
    assert resonance_event.handled is True
    assert fl_env.plugins.set_param_calls == [(1.0, 1, 0), (32 / 127.0, 2, 0)]


def test_cc9_is_not_a_knob(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {0: "Volume envelope attack"}
    script = fl_env.load_script()

    event = fl_env.cc(9, 127)

    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_unmapped_knob_leaves_event_unhandled(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {0: "Volume"}
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)
    script.OnRefresh(0)

    event = fl_env.cc(1, 100)

    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_knob_mapping_error_is_not_swallowed(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {0: "Filter cutoff"}
    fl_env.plugins.fail_set_param = RuntimeError("set failed")
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)
    script.OnRefresh(0)

    event = fl_env.cc(1, 64)

    with pytest.raises(RuntimeError, match="set failed"):
        script.OnMidiMsg(event)


def test_knob_mapping_works_without_prior_refresh(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {10: "Macro 1"}
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)

    event = fl_env.cc(1, 64)

    script.OnMidiMsg(event)

    assert event.handled is True
    assert fl_env.plugins.set_param_calls == [(64 / 127.0, 10, 0)]


def test_transport_pad_ccs_call_fl_transport(fl_env):
    script = fl_env.load_script()

    play = fl_env.cc(20, 127)
    stop = fl_env.cc(21, 127)
    record_off = fl_env.cc(22, 0)
    snap = fl_env.cc(23, 127)
    songpat = fl_env.cc(24, 127)
    metronome_on = fl_env.cc(27, 127)

    script.OnMidiMsg(play)
    script.OnMidiMsg(stop)
    script.OnMidiMsg(record_off)
    script.OnMidiMsg(snap)
    script.OnMidiMsg(songpat)
    script.OnMidiMsg(metronome_on)

    assert all(
        event.handled for event in (play, stop, record_off, snap, songpat, metronome_on)
    )
    assert fl_env.transport.calls == [
        ("start", ()),
        ("stop", ()),
        ("record", ()),
        ("setLoopMode", ()),
        ("globalTransport", (110, 1)),
    ]


def test_metronome_release_does_not_toggle(fl_env):
    script = fl_env.load_script()

    metronome_off = fl_env.cc(27, 0)

    script.OnMidiMsg(metronome_off)

    assert metronome_off.handled is True
    assert fl_env.transport.calls == []


def test_on_init_skips_channels_without_valid_plugin(fl_env):
    fl_env.channels.names = {0: "Audio Clip", 1: "Synth"}
    fl_env.plugins.names = {1: "FLEX"}
    fl_env.plugins.params = {1: {10: "Macro 1"}}
    fl_env.plugins.valid_channels = {1}
    script = fl_env.load_script()

    fl_env.run_with_print_capture(script.OnInit)

    assert 0 not in script.mappings_cache._items
    assert 1 in script.mappings_cache._items


def test_knob_on_invalid_plugin_does_not_crash(fl_env):
    fl_env.channels.names = {0: "Audio Clip"}
    fl_env.plugins.names = {}
    fl_env.plugins.valid_channels = set()
    fl_env.plugins.params = {}
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)

    event = fl_env.cc(1, 64)
    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.plugins.set_param_calls == []


def test_joystick_preset_controls_are_debounced(fl_env):
    script = fl_env.load_script()

    next_high = fl_env.cc(50, 127)
    next_still_high = fl_env.cc(50, 127)
    next_low = fl_env.cc(50, 0)
    next_high_again = fl_env.cc(50, 127)
    prev_high = fl_env.cc(100, 127)

    for event in (next_high, next_still_high, next_low, next_high_again, prev_high):
        script.OnMidiMsg(event)

    assert all(
        event.handled
        for event in (
            next_high,
            next_still_high,
            next_low,
            next_high_again,
            prev_high,
        )
    )
    assert fl_env.plugins.next_preset_calls == [0, 0]
    assert fl_env.plugins.prev_preset_calls == [0]


def test_fruity_slicer_2_pads_remap_notes_to_slices(fl_env):
    fl_env.plugins.names[0] = "Fruity Slicer 2"
    script = fl_env.load_script()

    note_on = fl_env.note_on(36, 96)
    note_off = fl_env.note_off(36)

    script.OnMidiMsg(note_on)
    script.OnMidiMsg(note_off)

    assert note_on.handled is True
    assert note_off.handled is True
    assert fl_env.channels.midi_notes == [(0, 60, 96), (0, 60, 0)]


def test_non_slicer_notes_are_left_unhandled(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    script = fl_env.load_script()

    event = fl_env.note_on(36, 100)

    script.OnMidiMsg(event)

    assert event.handled is False
    assert fl_env.channels.midi_notes == []


def test_on_init_builds_mapping_cache_and_prints_keys(fl_env):
    fl_env.plugins.names[0] = "Mystery Synth"
    fl_env.plugins.user_names[0] = "Mystery Synth"
    fl_env.plugins.params[0] = {
        0: "Cutoff",
        1: "Resonance",
    }
    script = fl_env.load_script()

    fl_env.run_with_print_capture(script.OnInit)

    assert fl_env.prints == [
        ("Smart MPK Mini Driver - loaded\nMappings cache:\n0",),
    ]


def test_integer_plugin_targets_reuse_scanned_parameter_names(fl_env):
    fl_env.plugins.names[0] = "FLEX"
    fl_env.plugins.params[0] = {10: "Macro 1"}
    script = fl_env.load_script()
    fl_env.run_with_print_capture(script.OnInit)
    script.OnRefresh(0)

    event = fl_env.cc(1, 64)
    script.OnMidiMsg(event)

    assert fl_env.plugins.get_param_name_calls.count((10, 0)) == 1


def test_on_init_prints_startup_banner(fl_env):
    script = fl_env.load_script()

    fl_env.run_with_print_capture(script.OnInit)

    printed_text = "\n".join(
        " ".join(str(part) for part in line) for line in fl_env.prints
    )
    assert "Smart MPK Mini Driver - loaded" in printed_text
    assert "Mappings cache:" in printed_text
