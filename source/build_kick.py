"""Build the KickForge native Bitwig instrument (.bwdevice) for Bitwig 6.1.7 Linux.

Structure follows a working note_to_audio device: an audio proxy and a note
proxy in proxy_in_ports, an audio_source_atom, the parameter atoms, one Nitro
core whose input 0 is the NoteEvent port fed by the note proxy, and the stereo
output proxy fed by Nitro output 0.

Usage: python build_kick.py [--out PATH]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
# polarity/bitwig-devices-blueprint (its Python helpers, Nitro bridge and document codec);
# set KICKFORGE_BLUEPRINT if it is not at ~/Patchbay/bitwig-devices-blueprint
BLUEPRINT = Path(os.environ.get("KICKFORGE_BLUEPRINT", Path.home() / "Patchbay" / "bitwig-devices-blueprint"))
sys.path[:0] = [str(BLUEPRINT), str(BLUEPRINT / "scripts")]

import compiler_profiles  # noqa: E402
import theme  # noqa: E402  (kick/theme.py: colours and panel layout)
from devices.common.document_graph import iter_owned_objects  # noqa: E402
from devices.common.panel_helpers import connection, grid_layout, obj, value as v  # noqa: E402

INPUTS = BLUEPRINT / "local/host-tools/linux-x86_64-bitwig-6.1.7/compiler-inputs.json"
CODEC = BLUEPRINT / "tools/document_codec/target/release/bwmodule-parser"

UUID = "6b0f3c5e-9a41-4d8e-b7c2-4f1e0a9d2c31"
NAME = "KickForge"
CREATOR = "KickForge"
DESCRIPTION = "Kick drum synth with freely editable pitch and amp curves, click, drive, EQ and compressor"
KEYWORDS = "kick drum 808 909 bass synth curve"
VERSION = "6.1.7"

# Bitwig's serialized numeric units and domains (bo / bn ids, read from 6.1.7's enums ge / gd).
# A value is held in its domain (DECIBEL: dB, PITCH: MIDI note, PITCH_RELATIVE: semitones),
# converted to a linear value (gain, Hz, ratio; time in seconds) and shown in the unit.
U_NONE, U_PCT, U_DB, U_S, U_HZ, U_ST, U_BEATS, U_CENTS, U_ST_REL, U_DEG, U_MS = 0, 1, 2, 3, 4, 5, 8, 9, 10, 15, 18
D_LIN, D_DB, D_PITCH, D_PITCH_REL, D_LOG = 0, 1, 2, 6, 7

EQ_MIN, EQ_MAX = 10 ** (-15 / 20), 10 ** (15 / 20)   # (v60) the EQ's gains, -15 .. +15 dB, linear
# (preset id, nitro port name, label, short, min, max, default, unit, decimals, origin, domain)
# Inputs of the voice core, in this order after its fixed inputs.
PARAMS = [
    ("PITCH", "pitch_amount", "Pitch Amount", "Pitch", 0.0, 144.0, 96.0, U_ST_REL, 1, 0, D_PITCH_REL),
    ("PHASE", "start_phase", "Phase", "Phase", 0.0, 360.0, 0.0, U_DEG, 0, 0, D_LIN),
    ("CLICK", "click_level", "Click Level", "Click", 0.0, 1.0, 0.285215, U_PCT, 0, 0, D_LIN),
    # (v70) the click's Length: the span of its two curves (pitch, amp); the id kept for the presets
    # (v1-v69 Click Decay, an exponential decay's time, 0.2 .. 200 ms)
    ("CLICK_DECAY", "click_decay", "Click Length", "Length", 0.001, 0.2, 0.018263, U_MS, 1, 0, D_LIN),
    ("CLICK_TONE", "click_tone", "Click Tone", "Tone", 200.0, 20000.0, 13227.193359, U_HZ, 0, 0, D_LIN),
    ("CLICK_HP", "click_hp", "Click High-pass", "Low Cut", 20.0, 8000.0, 933.881445, U_HZ, 0, 0, D_LIN),
    ("VELOCITY", "velocity", "Velocity", "Velocity", 0.0, 1.0, 0.5, U_PCT, 0, 0, D_LIN),
    ("LEVEL", "level", "Level", "Level", 0.0, 1.0, 0.525762, U_PCT, 0, 0, D_LIN),
    # v39: saturation of the mids only (between 2.5 x the root and 5 kHz): the fundamental stays clean
    ("MID_DRIVE", "mid_drive", "Drive", "Drive", 0.0, 1.0, 0.0, U_PCT, 0, 0, D_LIN),   # (v60: named Drive, the whole kick's drive gone; the id kept for the presets)
    # v40: the body's compressor (the FX tab): takes the body's attack down towards its tail
    ("COMP", "body_comp", "Comp", "Comp", 0.0, 1.0, 0.0, U_PCT, 0, 0, D_LIN),   # (v60: last in the chain, the whole kick)
    # (v60: the gains held linear on a log knob, 0 dB in the middle, so the panel's expressions
    # compare positive numbers: Bitwig did not take "EQ_LOW > -14.5", the art's LEDs and pointers
    # then showing on every tab; v58-v59 held in dB, -15..15)
    # v58: a console-style three-band EQ after the drives (the FX tab), gains in dB (held as dB, as
    # the Nitro core gets them): a low shelf at 80 Hz, a mid bell at 400 Hz whose Q narrows with the
    # gain, a high shelf at 5 kHz
    ("EQ_LOW", "eq_low", "EQ Low", "Low", EQ_MIN, EQ_MAX, 1.0, U_DB, 1, 0, D_LOG),
    ("EQ_MID", "eq_mid", "EQ Mid", "Mid", EQ_MIN, EQ_MAX, 1.0, U_DB, 1, 0, D_LOG),
    ("EQ_HIGH", "eq_high", "EQ High", "High", EQ_MIN, EQ_MAX, 1.0, U_DB, 1, 0, D_LOG),
    # v61: the click starts this late, to sit it on the body's transient (the Click tab)
    ("CLICK_DELAY", "click_delay", "Click Delay", "Delay", 0.0, 0.005, 0.0, U_MS, 2, 0, D_LIN),   # (v62: 5 -> 15 ms; v79: back to 5 ms, finer)
]
# Inputs of the phase core: the curve lengths (seconds, shown in ms) and the tune.
LENGTHS = [
    ("P_LEN", "pitch_length", "Pitch Length", "Length", 0.005, 2.0, 0.3, U_MS, 0, 0, D_LIN),
    ("A_LEN", "amp_length", "Amp Length", "Length", 0.01, 4.0, 0.6, U_MS, 0, 0, D_LIN),
    # vertical scale of the pitch curve: 0 = every octave the same height, up = more room for the
    # highs (k = 1001^scale - 1); 30.1 % = k 7, the curve of the earlier "Log" mode
    ("P_CURVE", "pitch_scale", "Pitch Scale", "Scale", 0.0, 1.0, 0.30098, U_PCT, 0, 0, D_LIN),
    # horizontal scale of each curve: 0 = time even across the curve, up = more room for the start
    # of the kick (curve x = log(1 + k t) / log(1 + k), k = 1001^scale - 1)
    ("P_TIME", "pitch_time_scale", "Pitch Time Scale", "Time", 0.0, 1.0, 0.66807, U_PCT, 0, 0, D_LIN),
    ("A_TIME", "amp_time_scale", "Amp Time Scale", "Time", 0.0, 1.0, 0.34707, U_PCT, 0, 0, D_LIN),
]

# (Grey came in v37, last: a preset saves the index, so the others keep theirs)
# (v62: Impulse -> 909 Hat, 808 Hat added last: a preset saves the index)
CLICK_TYPES = ["White", "Pink", "Brown", "Blue", "Violet", "Crackle", "909 Hat", "Grey", "808 Hat", "606 Hat"]   # (v63: 606 Hat)

# Default curves: (phase 0..1, value 0..1, curvature -1..1)
# (pitch values for the curve's log response: v = (2^(3 u) - 1) / 7 of the old linear u)
# x = position on the curve: the kick's time (0, 0.02, 0.08, 0.3, 1) through the default time scale
# (v72) the device's default sound is [MindB] Kick 01's (its curves, levels, click; v1-v71 a plain kick)
PITCH_POINTS = [(0.0, 1.0, 0.16), (0.0199, 0.572, 0.3), (0.1891, 0.2379, 0.2), (0.7441, 0.0275, 0.0), (0.9527, 0.0, 0.0), (1.0, 0.0, 0.0)]
# (v70) the click's curves: its pitch (0.5 = as it is, 0 / 1 = -24 / +24 semitones) and its level,
# across its Length (an exponential decay by default, about e^-5t)
CLICK_PITCH_POINTS = [(0.0, 0.5, 0.0), (1.0, 0.5, 0.0)]
CLICK_AMP_POINTS = [(0.0, 1.0, 0.0), (0.1, 0.6, 0.0), (0.3, 0.22, 0.0), (0.6, 0.05, 0.0), (1.0, 0.0, 0.0)]
AMP_POINTS = [(0.0, 0.4694, 0.14), (0.0262, 0.813, 0.24), (0.1155, 0.3023, 0.0), (0.223, 0.5155, 0.0), (0.3856, 0.8449, 0.0), (0.9572, 0.5091, 0.0), (1.0, 0.0, 0.0)]   # (v72: Kick 01's; v1-v71 times 0, 0.08, 0.35, 0.75, 1)


def owned(*objects):
    return [{"Object": item} for item in objects]


def settings(connections=()):
    desktop = obj(17, "desktop_settings", {
        "x#17": v("Int16", 0), "y#18": v("Int16", 0),
        "color#19": v("Color", [0.5, 0.5, 0.5, 1.0]),
    })
    return v("Object", obj(236, "component_settings", {
        "desktop_settings#612": v("Object", desktop),
        "inport_connections#614": v("ObjectList", list(connections)),
        "is_polyphonic#615": v("Bool", False),
    }))


def proxy_in(*, note):
    fields = {
        "name#498": v("String", ""), "description#4741": v("String", ""),
        "decorated_name#499": v("String", " Note out" if note else " Audio out (PARENT)"),
        "is_inport#500": v("Bool", False), "is_optional#1384": v("Bool", False),
        "exclude_from_graph#7174": v("Bool", False),
    }
    if note:
        fields["oversampling#13326"] = v("Byte", 0)
        port = obj(61, "note_port", fields)
    else:
        fields.update({"channel_count#372": v("Byte", 3), "oversampling#13324": v("Byte", 0)})
        port = obj(242, "audio_port", fields)
    return obj(154, "proxy_in_port_component", {"settings#6194": settings(), "port#301": v("Object", port)})


def proxy_out(connections):
    port = obj(242, "audio_port", {
        "name#498": v("String", ""), "description#4741": v("String", ""),
        "decorated_name#499": v("String", " Audio in (PARENT)"), "is_inport#500": v("Bool", True),
        "is_optional#1384": v("Bool", False), "exclude_from_graph#7174": v("Bool", False),
        "channel_count#372": v("Byte", 3), "oversampling#13324": v("Byte", 0),
    })
    return obj(50, "proxy_out_port_component", {"settings#6194": settings(connections), "port#301": v("Object", port)})


def decimal_atom(pid, label, short, lo, hi, default, unit, decimals, origin, domain=D_LIN):
    # engine_domain = domain: the Nitro core gets the value as held (as Polarity's dB knob)
    value_type = obj(123, "decimal_value_type", {
        "min#292": v("Double", lo), "max#293": v("Double", hi),
        "default_value#891": v("Double", default), "domain#294": v("Byte", domain),
        "engine_domain#295": v("Byte", domain), "value_origin#3014": v("Byte", origin),
        "pixel_step_size#1988": v("Double", -1.0), "unit#296": v("Byte", unit),
        "parameter_smoothing#4433": v("Bool", False), "allow_automation_curves#4434": v("Bool", True),
        "#297": v("Byte", decimals),
    })
    return obj(289, "decimal_value_atom", {
        "settings#6194": settings(), "channel_count#607": v("Byte", 0), "oversampling#608": v("Byte", 0),
        "name#374": v("String", label), "short_name#821": v("String", short),
        "preset_identifier#701": v("String", pid), "modulations_to_ignore#3826": v("String", ""),
        "value_type#702": v("Object", value_type), "value#712": v("Double", default),
        "allow_automation#7489": v("Bool", True), "allow_modulation#7490": v("Bool", True),
    })


def integer_atom(pid, label, lo, hi, default, prefix="", postfix=""):
    # whole numbers: a slider bound to it moves in steps (Bitwig's sliders take decimal or integer
    # atoms, not indexed ones)
    value_type = obj(143, "integer_value_type", {
        "min#345": v("Int32", lo), "max#346": v("Int32", hi), "default_value#6956": v("Int32", default),
        "value_prefix#819": v("String", prefix), "value_postfix#820": v("String", postfix),
        "value_origin#4723": v("Byte", 0), "pixel_step_size#4724": v("Double", -1.0),
    })
    return obj(394, "integer_value_atom", {
        "settings#6194": settings(), "channel_count#607": v("Byte", 0), "oversampling#608": v("Byte", 0),
        "preset_identifier#701": v("String", pid), "name#374": v("String", label),
        "short_name#821": v("String", label), "should_inherit_name#10561": v("Bool", False),
        "modulations_to_ignore#3826": v("String", ""), "value_type#702": v("Object", value_type),
        "allow_automation#7489": v("Bool", True), "allow_modulation#7490": v("Bool", True),
        "value#828": v("Int32", default),
    })


def indexed_atom(pid, label, items, default, automate=True):
    entries = [obj(258, "indexed_value_item", {
        "id#650": v("Byte", i), "name#651": v("String", name), "icon#9823": v("String", ""),
        "description#9824": v("String", ""), "deprecated#10795": v("Bool", False),
    }) for i, name in enumerate(items)]
    value_type = obj(155, "indexed_value_type", {
        "items#393": v("ObjectList", owned(*entries)), "default_value#6958": v("Byte", default),
        "is_periodic#16667": v("Bool", False),
    })
    return obj(180, "indexed_value_atom", {
        "settings#6194": settings(), "channel_count#607": v("Byte", 0), "oversampling#608": v("Byte", 0),
        "preset_identifier#701": v("String", pid), "name#374": v("String", label),
        "short_name#821": v("String", label), "should_inherit_name#10561": v("Bool", False),
        "modulations_to_ignore#3826": v("String", ""), "value_type#702": v("Object", value_type),
        "allow_automation#7489": v("Bool", automate), "allow_modulation#7490": v("Bool", automate),
        "value#457": v("Byte", default),
    })


def nitro_port(name, index, channels, kind, *, output=False, event=""):
    return obj(2428, "nitro_port_info", {
        "name#8557": v("String", name), "desc#8558": v("String", ""),
        "channel_count#8559": v("Byte", channels), "index#8560": v("Byte", index),
        "kind#8561": v("Byte", kind), "is_input#8562": v("Bool", not output),
        "is_double_precision#10071": v("Bool", False), "is_compressed_mask#8563": v("Int32", 16777215),
        "is_compressable#8564": v("Bool", False), "event_size#8565": v("Byte", 44 if event else 0),
        "event_type#8566": v("String", event),
    })


def layout(x, y, w, h):
    return v("Object", grid_layout(x, y, w, h))


def label(text, x, y, w, h=3, align=1):
    return obj(1683, "label_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "text#6219": v("String", text),
        "color#6520": v("Int16", 6), "horizontal_alignment#6400": v("Byte", align),
        "vertical_alignment#6401": v("Byte", 1), "is_visible#6309": v("Bool", True),
    })


def knob(binding, title, tooltip, x, y, w=11, h=12):
    return obj(1687, "knob_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "is_visible#6309": v("Bool", True),
        "is_enabled#6310": v("Bool", True), "tooltip_text#6867": v("String", tooltip),
        "data_model#6220": binding, "title#6241": v("String", title), "knob_size#6223": v("Byte", 1),
        "show_value_popup#10569": v("Bool", True), "attribute_id#11012": v("Int16", 712),
        "knob_style#7055": v("Byte", 3), "label_color#7056": v("Int16", 6), "pie_color#7057": v("Byte", 0),
        "help_id#10543": v("String", ""),
    })


# Knob art: a Blender-rendered LED-ring encoder over each native knob (knobs/render_knobs.py
# renders it, knobs/make_knob_svgs.py makes the SVGs). Added after its knob, so it covers the
# native knob (which still takes the mouse: images are not interactive); its LEDs are separate
# images, each shown by a panel expression once the knob's value passes it.
KNOB_ART = HERE / "knobs" / "out"
KNOB_ART_ON = True
KNOB_ART_DY = 0        # grid units: the encoder's box starts this far below the knob cell's top
KNOB_ART_H = theme.KNOB_BOX   # grid units: the encoder's box (its SVG is exactly the box), label under it
NATIVE_KNOB = (8, 8)   # grid units: the native knob under the encoder, centred on it (v57: 8 x 8 under the 48 px encoder, ring 32 px in its opaque disc; v43: 8 x 9 under the 56 px encoder; v42: 6 x 7 -> 9 x 10 under the 64 px encoder; v41: ring 6 units = 24 px; the 40 px encoder's disc is opaque to about 29; v36: 7 x 8 under 44 px)
# (v57) the native knob's top: centred on the encoder, which sits theme.KNOB_DY down its box
NATIVE_DY = theme.KNOB_DY + (theme.KNOB_UNITS - NATIVE_KNOB[1]) // 2
assert (theme.KNOB_UNITS - NATIVE_KNOB[1]) % 2 == 0 and (theme.CELL - NATIVE_KNOB[0]) % 2 == 0
KNOB_ART_SCALE = 1.0   # image_panel_item scale (the SVG size is in knobs/out/layout.json)


def knob_art(svg_name, x, y, w):
    """One layer of the encoder (base_<colour> or led_<colour>_<i>), centred in the box at the
    top of the knob cell. The SVG is the box's size (theme.CELL x theme.KNOB_BOX)."""
    assert w == theme.CELL, f"knob cell {w} wide: the encoder SVGs are made {theme.CELL} wide"
    svg = (KNOB_ART / f"{svg_name}.svg").read_text(encoding="utf-8")
    return obj(1719, "image_panel_item", {
        "layout_settings#6226": layout(x, y + KNOB_ART_DY, w, KNOB_ART_H), "is_visible#6309": v("Bool", True),
        "svg_data#6259": v("String", svg), "horizontal_alignment#6400": v("Byte", 1),
        "vertical_alignment#6401": v("Byte", 1), "scale#6767": v("Double", KNOB_ART_SCALE),
        "opacity#6768": v("Double", 1.0),
    })


def lcd_images(pb, prefix, rect, cond_of, count, visible_if=None):
    """A mini LED screen (knobs/make_panel_svgs.py): one opaque image per value, <prefix>_<i>,
    in rect, shown while cond_of(i) holds."""
    cells = panel_cells()
    for i in range(count):
        assert cells[f"{prefix}_{i}"] == list(rect), f"{prefix}_{i}: made for {cells[f'{prefix}_{i}']}, placed at {rect}"
        cond = cond_of(i)
        pb.add(panel_image(f"{prefix}_{i}", *rect), f"({visible_if}) && ({cond})" if visible_if else cond)


# panel_image items by id: (svg name, cell), for PanelBuilder.add's white-panel twins (v40)
IMAGES = {}


def panel_image(svg_name, x, y, w, h):
    """A piece of panel art (knobs/make_panel_svgs.py) filling its cell exactly."""
    svg = (KNOB_ART / f"{svg_name}.svg").read_text(encoding="utf-8")
    item = obj(1719, "image_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "is_visible#6309": v("Bool", True),
        "svg_data#6259": v("String", svg), "horizontal_alignment#6400": v("Byte", 1),
        "vertical_alignment#6401": v("Byte", 1), "scale#6767": v("Double", 1.0),
        "opacity#6768": v("Double", 1.0),
    })
    IMAGES[id(item)] = (svg_name, (x, y, w, h))
    return item


def caption(pb, text, x, y, w, h, visible_if=None):
    """A control's title: an image in the pads' legend font (theme.CAPTIONS, v39), or Bitwig's
    label without the art."""
    if not KNOB_ART_ON:
        return pb.add(label(text, x, y, w, h, 1), visible_if)
    name = theme.caption_name(text)
    assert panel_cells()[name][2:] == [w, h], f"{name}: made {panel_cells()[name][2:]}, placed {w} x {h}"
    return pb.add(panel_image(name, x, y, w, h), visible_if)


def panel_cells():
    return json.loads((KNOB_ART / "panel.json").read_text())


EQ_ART = KNOB_ART / "eq"   # (v60) the EQ's encoders (make_knob_svgs --px 40 --box 14 10 --dy 0 --out knobs/out/eq)


def eq_art(svg_name, x, y):
    """One layer of an EQ encoder (knobs/out/eq), its box theme.EQ_BOX at x, y."""
    w, h = theme.EQ_BOX
    svg = (EQ_ART / f"{svg_name}.svg").read_text(encoding="utf-8")
    assert f'width="{w * theme.PX_PER_UNIT:.2f}" height="{h * theme.PX_PER_UNIT:.2f}"' in svg, svg_name
    return obj(1719, "image_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "is_visible#6309": v("Bool", True),
        "svg_data#6259": v("String", svg), "horizontal_alignment#6400": v("Byte", 1),
        "vertical_alignment#6401": v("Byte", 1), "scale#6767": v("Double", KNOB_ART_SCALE),
        "opacity#6768": v("Double", 1.0),
    })


def log_pointer_ranges(atom):
    """pointer_ranges for a log-mapped parameter (v60, the EQ's gains): the pointer positions
    evenly over the knob's travel, in the log of the value."""
    _, m, lo, hi = _art_layout(atom)
    ln = lambda f: math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * f)
    edge = [ln((k + 0.5) / (m - 1) + 3.1415926e-6) for k in range(m - 1)]
    return [(edge[k - 1] if k else None, edge[k] if k < m - 1 else None) for k in range(m)]


def _art_layout(atom):
    lay = json.loads((KNOB_ART / "layout.json").read_text())
    vt = atom["fields"]["value_type#702"]["value"]["fields"]
    return lay["leds"], lay["pointers"], vt["min#292"]["value"], vt["max#293"]["value"]


def pointer_ranges(atom):
    """For each pointer position k of m (evenly over the sweep), the values (in the parameter's
    own units, what panel expressions read) for which it is the nearest: (low, high), None for
    an open end. As make_knob_svgs.pointer_index."""
    _, m, lo, hi = _art_layout(atom)
    # nudged off round numbers: a value exactly on an edge would match neither "<" nor ">"
    # and show no pointer
    edge = [lo + (hi - lo) * ((k + 0.5) / (m - 1) + 3.1415926e-6) for k in range(m - 1)]
    return [(edge[k - 1] if k else None, edge[k] if k < m - 1 else None) for k in range(m)]


def num(x):
    """(v79) A number for a panel expression: as %.9g, but never in exponent form (6.25e-05: Bitwig
    refuses the minus sign in an expression), so tiny thresholds (the 5 ms click delay) are written out."""
    text = f"{x:.9g}"
    if "e" not in text:
        return text
    digits = max(0, 8 - math.floor(math.log10(abs(x))))
    return f"{x:.{digits}f}".rstrip("0").rstrip(".")


def led_thresholds(atom):
    """The value past which each LED lights: LED i of n sits at pointer position i (m-1)/(n-1)
    and lights once the pointer reaches it (LED 0 is always lit: threshold None)."""
    n, m, lo, hi = _art_layout(atom)
    edges = [low for low, _ in pointer_ranges(atom)]
    return [edges[i * (m - 1) // (n - 1)] for i in range(n)]


def slider(binding, tooltip, x, y, w, h):
    # a horizontal fader with its value (Hz and note, for the tune) in its frame
    return obj(1685, "slider_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "is_visible#6309": v("Bool", True),
        "is_enabled#6310": v("Bool", True), "tooltip_text#6867": v("String", tooltip),
        "data_model#6220": binding, "is_horizontal#6244": v("Bool", True),
        "allow_jump#11134": v("Bool", False), "style#6263": v("Byte", 2),
        # (v66: no value popup while dragging: it read "MIDI 29"; the note is on the screen beside it)
        "show_value_popup#10599": v("Bool", False), "help_id#10543": v("String", ""),
    })


def toggle_group(binding, tooltip, x, y, w, h):
    return obj(1712, "button_group_chooser_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "is_visible#6309": v("Bool", True),
        "is_enabled#6310": v("Bool", True), "tooltip_text#6867": v("String", tooltip),
        "help_id#10543": v("String", ""), "help_location#10546": v("Byte", 0),
        "data_model#6220": binding, "attribute_id#11012": v("Int16", 457),
        "is_horizontal#6255": v("Bool", True), "break_count#6256": v("Byte", 0),
        "label_style#6257": v("Byte", 0), "button_style#7548": v("Byte", 0), "color#10143": v("Int16", 0),
    })


# Bitwig's curve kinds (float_core.curve_kind): CYCLE 0, ENVELOPE 1, TRANSFER 2. CYCLE: the
# input is the position on the curve (0..1). ENVELOPE (v27, to drop the editor's segment from the
# last point back to the first) silenced the body: its curves do not read the input that way.
CURVE_KIND = 0


def curve_resource(name, points):
    pts = [obj(4734, "curve_point", {
        "value#13821": v("Double", val), "phase#13822": v("Double", ph), "curvature#13823": v("Double", cu),
    }) for ph, val, cu in points]
    return obj(4735, "curve", {
        "curve_kind#13869": v("Byte", CURVE_KIND), "is_grid_active#13894": v("Bool", False),
        "grid_x#13825": v("Int32", 16), "grid_y#13826": v("Int32", 4), "tool#13877": v("Byte", 0),
        "points#13827": v("ObjectList", owned(*pts)),
        "hold_point_index#14216": v("Int32", -1), "loop_start_index#13925": v("Int32", -1),
        "loop_end_index#13926": v("Int32", -1), "name#13835": v("String", name),
    })


def curve_atom(pid, name, points, connections):
    # Bitwig's native curve (as in the Curves modules): CYCLE kind (CURVE_KIND), the input is a
    # 0..1 phase (kick_phase.nitro keeps it under 1), the output the curve's value there (0..1).
    return obj(4733, "curve_atom", {
        "settings#6194": settings(connections), "channel_count#607": v("Byte", 0),
        "oversampling#608": v("Byte", 0),
        "curve_kind#13870": v("Byte", CURVE_KIND), "resource#13810": v("Object", curve_resource(name, points)),
        "preset_identifier#13812": v("String", pid), "bipolar#13909": v("Bool", False),
        "reflect#14728": v("Bool", False), "envelope_behavior#14215": v("Byte", 0),
        "anti_alias#14147": v("Bool", False),
    })


def curve_display(binding, editor_panel, x, y, w, h, tooltip, axes, zoom=False, under=None, color=2):
    # A native curve editor: a display (no scroll/zoom: a zoomable display crashed with bound
    # elements) holding the curve atom's display element, edited in place. A display_panel
    # would make a click open Bitwig's curve popup instead (left empty). Axes: CURVE_AXES.
    element = obj(4763, "curve_atom_display_element_panel_item", {
        "component#7561": binding, "interactive#13889": v("Bool", True),
        "color#6518": v("Int16", color), "can_use_tools#13897": v("Bool", True),
        "show_gradient#14010": v("Bool", False),   # the line only: the waveform shows under it
        "display_panel#13997": editor_panel if editor_panel is not None else v("NullObject"),
    })
    return obj(1804, "display_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "tooltip_text#6867": v("String", tooltip),
        "is_visible#6309": v("Bool", True), "is_enabled#6310": v("Bool", True),
        # border style 0 = NONE (1 = FILLED painted an opaque background over the waveform)
        "border_style#6228": v("Byte", 0), "brightness#6245": v("Byte", 0),
        "x_min#6504": v("Double", 0.0), "x_max#6505": v("Double", axes["x_max"]),
        "x_domain#6506": v("Byte", D_LIN), "x_unit#6507": v("Byte", axes["x_unit"]),
        "y_min#6508": v("Double", axes["y_min"]), "y_max#6509": v("Double", axes["y_max"]),
        "y_domain#6510": v("Byte", axes["y_domain"]), "y_unit#6511": v("Byte", axes["y_unit"]),
        "left_margin_visible#10289": v("Bool", False), "right_margin_visible#10290": v("Bool", False),
        "top_margin_visible#10291": v("Bool", False), "bottom_margin_visible#10292": v("Bool", False),
        # Bitwig's own zoom (Ctrl+Alt+wheel): on in the device, off in the maximized view.
        # A zoomable display keeps the size it was made with (v14: too small when maximized).
        "can_scroll_and_zoom_x#13958": v("Bool", zoom), "can_scroll_beyond_content_x#13965": v("Bool", False),
        "can_scroll_and_zoom_y#13966": v("Bool", zoom), "can_scroll_beyond_content_y#13967": v("Bool", False),
        # the waveform drawing (under) inside the display, at the back: it zooms with the curve
        # (v79: under may be a list, back to front: the click view's body layer over its click)
        "items#6221": v("ObjectList", owned(*(under if isinstance(under, list) else [under] if under is not None else []),
                                            element)),
    })



def grid(items, layout_settings=None):
    return obj(1681, "grid_panel_item", {
        "layout_settings#6226": layout_settings or v("NullObject"), "items#6221": v("ObjectList", owned(*items)),
        "border_style#6228": v("Byte", 0), "title#6242": v("String", ""),
        "show_title#6243": v("Bool", False), "title_color#6522": v("Byte", 6), "brightness#6245": v("Byte", 0),
    })


DIVISIONS = ["1/64", "1/32T", "1/32", "1/16T", "1/16", "1/8T", "1/16D", "1/8", "1/4T", "1/8D",
             "1/4", "1/2T", "1/4D", "1/2", "1/2D", "1 Bar"]

WAVE_TIP = ("The kick's waveform from the curves (redrawn while you edit them; white line = playhead; "
            "grid: bars, beats and note values at the project tempo; pitch: a line per note, C labelled; "
            "click: the noise over ten times its decay, the body in grey)")


def popup_chooser(binding, tooltip, x, y, w, h):
    return obj(1714, "popup_chooser_panel_item", {
        "layout_settings#6226": layout(x, y, w, h), "data_model#6220": binding,
        "attribute_id#11012": v("Int16", 457), "label_style#6262": v("Byte", 0),
        "style#6266": v("Byte", 7), "color#7528": v("Int16", 6), "tooltip_text#6867": v("String", tooltip),
    })


def wave_surface(binding, x, y, w, h):
    # The SkSL drawing (class 5512) shown by this surface (class 5517).
    return obj(5517, "", {
        "layout_settings#6226": layout(x, y, w, h),
        "is_visible#6309": v("Bool", True), "is_enabled#6310": v("Bool", True),
        "tooltip_text#6867": v("String", WAVE_TIP),
        "help_id#10543": v("String", ""), "help_location#10546": v("Byte", 0),
        "data_model#6220": binding,
    })


def panel(name, items, width, height, expressions=(), root=None, resizeable=False):
    fields = {
        "name#6211": v("String", name), "root_item#6212": v("Object", root or grid(items)),
        "width#6232": v("Int16", width), "height#6233": v("Byte", height),
    }
    if resizeable:   # the root box follows the size Bitwig gives the panel
        fields.update({"width_is_resizeable#10404": v("Bool", True), "height_is_resizeable#10405": v("Bool", True)})
    fields["expressions#6277"] = v("ObjectList", owned(*expressions))
    return obj(1680, "panel", fields)


def box_layout(width, height, expand_width=False, expand_height=False):
    # a child's size in a box: its preferred size, and whether it takes the free space
    return v("Object", obj(1695, "box_panel_item_layout_settings", {
        "width#6217": v("Int16", width), "height#6218": v("Int16", height),
        "expand_width#7552": v("Bool", expand_width), "expand_height#7553": v("Bool", expand_height),
    }))


def box(items, horizontal, layout_settings=None):
    # Bitwig's stretching row / column (box_panel_item)
    return obj(1679, "box_panel_item", {
        "layout_settings#6226": layout_settings or v("NullObject"), "items#6221": v("ObjectList", owned(*items)),
        "border_style#6228": v("Byte", 0), "title#6242": v("String", ""),
        "show_title#6243": v("Bool", False), "title_color#6522": v("Byte", 6), "brightness#6245": v("Byte", 0),
        "is_horizontal#6209": v("Bool", horizontal), "include_gap#9821": v("Bool", True),
        "horizontal_alignment#6210": v("Byte", 0), "vertical_alignment#6225": v("Byte", 0),
    })


def stack_layout(width, height):
    return v("Object", obj(1803, "stack_panel_item_layout_settings", {
        "width#6217": v("Int16", width), "height#6218": v("Int16", height),
    }))


def stack(items, layout_settings=None):
    # Bitwig's stack_panel_item: its children lie on top of each other, first one at the back
    return obj(1802, "stack_panel_item", {
        "layout_settings#6226": layout_settings or v("NullObject"), "items#6221": v("ObjectList", owned(*items)),
        "border_style#6228": v("Byte", 0), "title#6242": v("String", ""),
        "show_title#6243": v("Bool", False), "title_color#6522": v("Byte", 6), "brightness#6245": v("Byte", 0),
    })


class PanelBuilder:
    """Items of one panel plus their panel expressions: visibility (tabs, modes) and
    numeric attributes (the curve displays' axis ranges)."""

    def __init__(self, ref):
        self._ref = ref
        self.targets = {}   # id(ref wrapper) -> its target, to find the atom a knob is bound to
        self.items = []
        self.expressions = []
        self.art = None   # the knob art colour for the knobs added next (None: no encoder)

    @contextlib.contextmanager
    def tab_layer(self, tab):
        """(v74) A tab's controls in a layer of their own: the items added inside go into a grid
        over the tab's tray (theme.TAB_LAYER, their places made relative to it), shown with
        SHOW[tab]; their own expressions lose the tab's condition (LAYER_SHOW: true in the layer).
        Switching tabs then shows and hides five layers instead of some 800 images, one by one
        (v73 and before: each with its own "VIEW == n", a lag on switching). Items outside the
        tray stay where they were, in the panel's grid, with their expressions as they were."""
        start, e_start = len(self.items), len(self.expressions)
        yield
        lx, ly, lw, lh = theme.TAB_LAYER
        added, exprs = self.items[start:], self.expressions[e_start:]
        del self.items[start:], self.expressions[e_start:]

        def rect(item):
            f = item["fields"]["layout_settings#6226"]["value"]["fields"]
            return [f[k]["value"] for k in ("x#6215", "y#6216", "width#6217", "height#6218")], f

        inside, outside = [], []
        for item in added:
            (x, y, w, h), _ = rect(item)
            (inside if lx <= x and ly <= y and x + w <= lx + lw and y + h <= ly + lh else outside).append(item)
        ids = {id(item) for item in inside}
        target = {id(e): self.ref_target(e["fields"]["panel_item#6275"]) for e in exprs}
        kept = []
        for e in exprs:
            if id(target[id(e)]) not in ids:
                kept.append(e)
                continue
            text = layer_expression(e["fields"]["expression#6274"]["value"], tab)
            if text is not None:
                e["fields"]["expression#6274"]["value"] = text
                kept.append(e)
            elif e["fields"]["attribute_id#6316"]["value"] != 6309:
                raise AssertionError(f"{tab} layer: an attribute expression would go")
        for item in inside:
            _, f = rect(item)
            f["x#6215"]["value"] -= lx
            f["y#6216"]["value"] -= ly
        layer = grid(inside, layout(lx, ly, lw, lh))
        self.items.extend([layer] + outside)
        self.expressions.extend(kept)
        self.expression(layer, 6309, SHOW[tab])
        self.layers = getattr(self, "layers", []) + [(tab, len(inside), len(outside))]

    def ref_target(self, wrapper):
        return self.targets[id(wrapper)]

    def ref(self, target):
        wrapper = self._ref(target)
        self.targets[id(wrapper)] = target
        return wrapper

    def expression(self, item, attribute, text):
        self.expressions.append(obj(1728, "panel_expression", {
            "expression#6274": v("String", text), "attribute_id#6316": v("Int16", attribute),
            "panel_item#6275": self.ref(item),
        }))

    def add(self, item, visible_if=None, attributes=()):
        # v40: a piece of panel art made over both finishes (make_panel_svgs: <name>_light) goes in
        # twice, the dark one shown on the dark panel (PANEL 0), the white one on the white (1)
        art = IMAGES.get(id(item))
        if art and KNOB_ART_ON and f"{art[0]}_light" in panel_cells():
            both = (lambda look: f"({visible_if}) && (PANEL == {look})") if visible_if else (lambda look: f"PANEL == {look}")
            self.items.append(item)
            self.expression(item, 6309, both(0))
            twin = panel_image(f"{art[0]}_light", *art[1])
            self.items.append(twin)
            self.expression(twin, 6309, both(1))
            return item
        self.items.append(item)
        if visible_if:
            self.expression(item, 6309, visible_if)
        for attribute, text in attributes:
            self.expression(item, attribute, text)
        if self.art and KNOB_ART_ON and item.get("class_name") == "knob_panel_item":
            self.encoder(item, visible_if)
        return item

    def switch(self, binding, tooltip, group, visible_if=None):
        """A native button group (theme.PAD_GROUPS / PAD_AT) under its rubber pads: one image
        per lit pad, shown while the value is that pad's (the pads take no clicks: the native
        buttons under them do)."""
        w, h, names = theme.PAD_GROUPS[group]
        x, y = theme.PAD_AT[group]
        item = self.add(toggle_group(binding, tooltip, x, y, w, h), visible_if)
        if not KNOB_ART_ON:
            return item
        pid = self.targets[id(binding)]["fields"]["preset_identifier#701"]["value"]
        cells = panel_cells()
        for k in range(len(names)):
            cond = f"{pid} == {k}"
            name = f"pads_{group}_{k}"
            self.add(panel_image(name, *cells[name]), f"({visible_if}) && ({cond})" if visible_if else cond)
        return item

    def fader(self, binding, tooltip, visible_if=None):
        """The tune fader: the native slider (theme.FADER_RECT) under one opaque image per notch
        (knobs/make_panel_svgs.py: the slot, the notches, the silicone cap on notch k), shown
        while the value is that notch's. The images take no clicks: the slider under them does."""
        x, y, w, h = theme.FADER_RECT
        # the native slider inset by a unit all round: it draws a frame (orange) at its edge, which
        # showed round the fader's image when it had the image's cell (v31-v32)
        item = self.add(slider(binding, tooltip, x + 1, y + 2, w - 2, h - 4), visible_if)   # (v62: the art 8 high, the slider as before)
        if not KNOB_ART_ON:
            return item
        atom = self.targets[id(binding)]
        pid = atom["fields"]["preset_identifier#701"]["value"]
        vt = atom["fields"]["value_type#702"]["value"]["fields"]
        lo, hi = vt["min#345"]["value"], vt["max#346"]["value"]
        assert hi - lo + 1 == theme.FADER_STEPS, f"{pid}: {hi - lo + 1} values, the fader has {theme.FADER_STEPS} notches"
        cells = panel_cells()
        for k in range(theme.FADER_STEPS):
            # between the half steps (an integer atom: exactly lo + k, but no "==" on a number)
            parts = [f"{pid} > {lo + k - 0.5}" if k else "", f"{pid} < {lo + k + 0.5}" if k < theme.FADER_STEPS - 1 else ""]
            name = f"fader_{k}"
            cond = " && ".join(part for part in parts if part)
            self.add(panel_image(name, *cells[name]), f"({visible_if}) && ({cond})" if visible_if else cond)
        return item

    def encoder(self, knob_item, visible_if):
        """The encoder art over a knob. The knob's cell shrinks to the encoder's box (KNOB_ART_H
        rows) and its title moves to a label under it, so the art never covers text. Then the
        art: the base, one image per LED (lit once the pointer reaches it) and one per pointer
        position (shown while the value is nearest to it)."""
        fields = knob_item["fields"]
        f = fields["layout_settings#6226"]["value"]["fields"]
        x, y, w = (f[k]["value"] for k in ("x#6215", "y#6216", "width#6217"))
        # the native knob draws a value ring as large as its cell: shrink it (centred) so the ring
        # stays under the encoder's opaque disc (v24: an arc showed over the encoder's top)
        f["x#6215"]["value"], f["width#6217"]["value"] = x + (w - NATIVE_KNOB[0]) // 2, NATIVE_KNOB[0]
        f["y#6216"]["value"], f["height#6218"]["value"] = y + NATIVE_DY, NATIVE_KNOB[1]
        title = fields["title#6241"]["value"]
        fields["title#6241"] = v("String", "")
        caption(self, title, x, y + KNOB_ART_H, w, 3, visible_if)
        atom = self.targets[id(fields["data_model#6220"])]
        pid = atom["fields"]["preset_identifier#701"]["value"]

        def when(condition):
            return (f"({visible_if}) && ({condition})" if visible_if else condition) if condition else visible_if

        self.add(knob_art(f"base_{self.art}", x, y, w), visible_if)
        for i, threshold in enumerate(led_thresholds(atom)):
            self.add(knob_art(f"led_{self.art}_{i}", x, y, w), when(threshold and f"{pid} > {num(threshold)}"))
        for k, (low, high) in enumerate(pointer_ranges(atom)):
            parts = [f"{pid} > {num(low)}" if low is not None else "", f"{pid} < {num(high)}" if high is not None else ""]
            self.add(knob_art(f"ptr_{k}", x, y, w), when(" && ".join(part for part in parts if part)))

    def eq_encoder(self, binding, title, tooltip, box, cap, visible_if, bipolar=True):
        """(v60) An EQ encoder: a native knob (theme.EQ_NATIVE square, centred on the encoder) under
        the art (theme.EQ_BOX at box), its title on a caption at cap. The gain is held linear on a
        log knob (the panel's expressions then compare positive numbers only); its LEDs light from
        the middle one (0 dB) out towards the value, either way (a cut as a boost).
        (v73) bipolar=False: the same small encoder on any knob (the click tab's), its pointer and
        LEDs as the big encoders' (pointer_ranges, led_thresholds: lit from the left up to the value)."""
        x, y = box
        bw, bh = theme.EQ_BOX
        n = theme.EQ_NATIVE
        cx, cy = x + bw / 2, y + theme.EQ_UNITS / 2
        assert (cx - n / 2) == int(cx - n / 2) and (cy - n / 2) == int(cy - n / 2)
        item = knob(binding, "", tooltip, int(cx - n / 2), int(cy - n / 2), n, n)
        self.items.append(item)   # (not add(): that puts the big encoder art over a knob)
        if visible_if:
            self.expression(item, 6309, visible_if)
        caption(self, title, *cap, visible_if)
        if not KNOB_ART_ON:
            return item
        atom = self.targets[id(binding)]
        pid = atom["fields"]["preset_identifier#701"]["value"]
        leds, m, lo, hi = _art_layout(atom)
        assert json.loads((EQ_ART / "layout.json").read_text())["leds"] == leds

        def when(condition):
            return (f"({visible_if}) && ({condition})" if visible_if else condition) if condition else visible_if

        exprs = []
        if not bipolar:
            self.add(eq_art(f"base_{self.art}", x, y), visible_if)
            for i, threshold in enumerate(led_thresholds(atom)):
                exprs.append(f"{pid} > {num(threshold)}" if threshold else "")
                self.add(eq_art(f"led_{self.art}_{i}", x, y), when(exprs[-1]))
            for k, (low, high) in enumerate(pointer_ranges(atom)):
                parts = [f"{pid} > {num(low)}" if low is not None else "", f"{pid} < {num(high)}" if high is not None else ""]
                exprs.append(" && ".join(part for part in parts if part))
                self.add(eq_art(f"ptr_{k}", x, y), when(exprs[-1]))
            assert not any("-" in e for e in exprs), "a negative number in a panel expression (Bitwig refuses them)"
            return item
        ranges = log_pointer_ranges(atom)
        mid = (leds - 1) // 2
        assert abs(math.log(lo) + math.log(hi)) < 1e-9 and (mid * (m - 1)) % (leds - 1) == 0 and 2 * mid * (m - 1) // (leds - 1) == m - 1
        self.add(eq_art(f"base_{self.art}", x, y), visible_if)
        for i in range(leds):
            k = i * (m - 1) // (leds - 1)
            cond = "" if i == mid else (f"{pid} > {num(ranges[k][0])}" if i > mid else f"{pid} < {num(ranges[k][1])}")
            exprs.append(cond)
            self.add(eq_art(f"led_{self.art}_{i}", x, y), when(cond))
        for k, (low, high) in enumerate(ranges):
            parts = [f"{pid} > {num(low)}" if low is not None else "", f"{pid} < {num(high)}" if high is not None else ""]
            exprs.append(" && ".join(part for part in parts if part))
            self.add(eq_art(f"ptr_{k}", x, y), when(exprs[-1]))
        assert not any("-" in e for e in exprs), "a negative number in a panel expression (Bitwig refuses them)"
        return item

    def selector(self, binding, tooltip, x, y, visible_if):
        """A notched knob over a list (v37: the length's note value; before, a drop-down list): a
        native knob on the indexed atom (as SHARD's band count: Bitwig steps it through the
        items) under the selector art (knobs/out/sel: one LED and one pointer per item, a tick
        at each notch), LEDs lit up to the item, and the item's name on a mini LED screen
        under it, where the other knobs have their label."""
        atom = self.targets[id(binding)]
        pid = atom["fields"]["preset_identifier#701"]["value"]
        # (v75) a decimal atom 0 .. n - 1 (v37-v74 an indexed one, attribute 255): its value
        # rounded to the nearest item (a modulator moves it in between)
        vt = atom["fields"]["value_type#702"]["value"]["fields"]
        n = len(DIVISIONS)
        assert (vt["min#292"]["value"], vt["max#293"]["value"]) == (0.0, n - 1.0), pid
        item = knob(binding, "", tooltip, x, y, theme.CELL, theme.CELL_H)
        item["fields"]["show_value_popup#10569"] = v("Bool", False)   # (it would show the index: the screen shows the note)
        f = item["fields"]["layout_settings#6226"]["value"]["fields"]
        f["x#6215"]["value"], f["width#6217"]["value"] = x + (theme.CELL - NATIVE_KNOB[0]) // 2, NATIVE_KNOB[0]
        f["y#6216"]["value"], f["height#6218"]["value"] = y + NATIVE_DY, NATIVE_KNOB[1]
        self.items.append(item)   # (not add(): that puts the encoder art over a knob)
        self.expression(item, 6309, visible_if)
        if not KNOB_ART_ON:
            return item
        lay = json.loads((KNOB_ART / "sel" / "layout.json").read_text())
        assert lay["leds"] == lay["pointers"] == n, f"{pid}: {n} items, the selector art has {lay['leds']} notches"

        def when(cond):
            return f"({visible_if}) && ({cond})" if cond else visible_if

        def nearest(i):   # the value rounds to item i (no negative literal: Bitwig refuses them)
            return " && ".join(p for p in (f"{pid} > {i - 0.5}" if i else "", f"{pid} < {i + 0.5}" if i < n - 1 else "") if p)

        self.add(knob_art(f"sel/base_{self.art}", x, y, theme.CELL), visible_if)
        for i in range(n):
            self.add(knob_art(f"sel/led_{self.art}_{i}", x, y, theme.CELL), when(f"{pid} > {i - 0.5}" if i else ""))
        for i in range(n):
            self.add(knob_art(f"sel/ptr_{i}", x, y, theme.CELL), when(nearest(i)))
        lcd_images(self, f"lcd_div_{self.art}", theme.DIV_AT[self.art], nearest, n, visible_if)
        return item


# Visibility, one expression per item, numeric as in Polarity's devices
# (VIEW: 0 Master, 1 Pitch, 2 Amp, 3 Click (v40; v39: 0 Pitch .. 3 Master); *_SYNC: 0 Time, 1 Sync).
SHOW = {
    "master": "VIEW == 0", "pitch": "VIEW == 1", "amp": "VIEW == 2", "click": "VIEW == 3", "fx": "VIEW == 4",
    # the oscilloscope: in the master tab and the FX tab (v40)
    "scope": "VIEW * (4 - VIEW) == 0",
    # (v40: 5 tabs, so VIEW + 5 * sync: one number per tab and mode)
    "p_time": "VIEW + 5 * P_SYNC == 1", "p_sync": "VIEW + 5 * P_SYNC == 6",
    "a_time": "VIEW + 5 * A_SYNC == 2", "a_sync": "VIEW + 5 * A_SYNC == 7",
    # the master tab's length is the amp's (the kick's length)
    "m_time": "VIEW + 5 * A_SYNC == 0", "m_sync": "VIEW + 5 * A_SYNC == 5",
}

# (v74) inside a tab's layer (PanelBuilder.tab_layer) the tab's condition holds: each SHOW text
# that names the tab becomes what is left of it there (TRUE: nothing left)
TRUE = "\u00a7"
LAYER_SHOW = {
    "master": {SHOW["master"]: TRUE, SHOW["scope"]: TRUE, SHOW["m_time"]: "A_SYNC == 0", SHOW["m_sync"]: "A_SYNC == 1"},
    "pitch": {SHOW["pitch"]: TRUE, SHOW["p_time"]: "P_SYNC == 0", SHOW["p_sync"]: "P_SYNC == 1"},
    "amp": {SHOW["amp"]: TRUE, SHOW["a_time"]: "A_SYNC == 0", SHOW["a_sync"]: "A_SYNC == 1"},
    "click": {SHOW["click"]: TRUE},
    "fx": {SHOW["fx"]: TRUE, SHOW["scope"]: TRUE},
}


def layer_expression(text, tab):
    """An expression of an item in tab's layer, without the tab's condition (None: always true)."""
    for whole in sorted(LAYER_SHOW[tab], key=len, reverse=True):
        text = text.replace(whole, LAYER_SHOW[tab][whole])
    while True:
        before = text
        text = text.replace(f"({TRUE}) && ", "").replace(f" && ({TRUE})", "").replace(f"({TRUE})", TRUE)
        if text.startswith("(") and text.endswith(")") and text.count("(") == 1:
            text = text[1:-1]
        if text == before:
            break
    if text == TRUE:
        return None
    assert TRUE not in text and "VIEW" not in text, f"{tab} layer: {text!r}"
    return text


DIV_BEATS = [0.0625, 0.0833333, 0.125, 0.1666667, 0.25, 0.3333333, 0.375, 0.5, 0.6666667, 0.75,
             1.0, 1.3333333, 1.5, 2.0, 3.0, 4.0]


def div_beats_expression(var):
    text = str(DIV_BEATS[-1])
    for index in range(len(DIV_BEATS) - 2, -1, -1):
        text = f"({var} == {index} ? {DIV_BEATS[index]} : {text})"
    return text


# Both axes of a curve editor are plain curve positions (0..1): the time across is warped by
# the tab's time scale, so the drawn grid under it gives the time.
# Zoom: Bitwig's own (Ctrl+Alt+wheel) on the device's editor. Not in the maximized view: a
# zoomable display keeps the size it was made with, and stayed small there (v14, v18-v21).
# x_max: theme.X_END, short of 1 (v37): a cycle curve is drawn with a line from its last point
# (x = 1) back to its first, a vertical at the right edge; past x_max it is out of view, with the
# end point (never moved). (v27's envelope curves have no such line but silenced the body.)
CURVE_AXES = dict(y_domain=D_LIN, y_unit=U_NONE, y_min=0.0, y_max=1.0, x_unit=U_NONE, x_max=theme.X_END)


EDIT_TIP = ("Drag a point; double-click to add a point, double-click a point to delete it; drag a segment "
            "to bend it. Right-click: copy, paste, flip, reset... Bigger editor: the device's maximize "
            "button (left of the device).")


def knob_cell(pb, binding, title, tooltip, col, row, visible_if=None):
    """A knob in cell (col 0..1 of a column at x = col's x, row 0..1 of theme.ROWS)."""
    return pb.add(knob(binding, title, tooltip, col, theme.ROWS[row], theme.CELL, theme.CELL_H), visible_if)


def tab_side(pb, c, tab):
    """A tab's own controls in the tab column: the length mode in the header, then a 2 x 2
    grid: length (ms knob, or note value) | pitch amount or velocity, time scale | vertical
    scale (pitch: a knob; amp: Lin/dB)."""
    ref, p = pb.ref, c["param"]
    pb.art = tab
    t = "p" if tab == "pitch" else "a"
    T = t.upper()
    x0, x1 = theme.TAB2_X, theme.TAB2_X + theme.CELL
    r0, r1 = theme.ROWS
    extra = "PITCH" if tab == "pitch" else "VELOCITY"
    pb.switch(ref(c[f"{T}_SYNC"]), "Length in milliseconds (Time) or as a note value (Sync)", "sync", SHOW[tab])
    knob_cell(pb, ref(p[f"{T}_LEN"][0]), "Length", p[f"{T}_LEN"][1][2], x0, 0, SHOW[f"{t}_time"])
    if KNOB_ART_ON:
        assert theme.DIV_AT[tab][:2] == (x0, r0 + KNOB_ART_H)
        pb.selector(ref(c[f"{T}_DIV"]), "Length as a note value (follows the project tempo): turn to step "
                    "through 1/64 .. 1 bar (T: triplet, D: dotted)", x0, r0, SHOW[f"{t}_sync"])
    else:
        pb.add(knob(ref(c[f"{T}_DIV"]), "", "Length as a note value (follows the project tempo)",
                    x0, r0, theme.CELL, theme.CELL_H), SHOW[f"{t}_sync"])   # (v75: a decimal, no popup)
        caption(pb, "Length", x0, r0 + KNOB_ART_H, theme.CELL, 3, SHOW[f"{t}_sync"])
    extra_tip = ("Pitch: the top of the curve, in semitones above G0 (49 Hz). It stays put when you "
                 "change the tune: the tune only moves the bottom (the fundamental)"
                 if tab == "pitch" else p[extra][1][2])
    knob_cell(pb, ref(p[extra][0]), p[extra][1][3], extra_tip, x1, 0, SHOW[tab])
    knob_cell(pb, ref(p[f"{T}_TIME"][0]), "Time",
              "Horizontal scale of the curve: 0 % = time even across; higher = more room for the start "
              "of the kick (finer editing of the attack). The points stay where they are, so turning "
              "it changes the sound", x0, 1, SHOW[tab])
    if tab == "pitch":
        knob_cell(pb, ref(p["P_CURVE"][0]), "Scale",
                  "Vertical scale of the pitch curve: 0 % = every octave the same height; higher = more "
                  "room for the high frequencies (finer editing of the click), less for the body. The "
                  "points stay where they are, so turning it changes the sound", x1, 1, SHOW[tab])
    else:
        pb.switch(ref(c["A_SCALE"]),
                  "Amp scale: Lin = the curve is the level; dB = the curve is -60 dB .. 0 dB. The "
                  "points stay where they are, so switching changes the sound", "scale", SHOW[tab])
        caption(pb, "Scale", x1, r1 + KNOB_ART_H, theme.CELL, 3, SHOW[tab])


def click_tab(pb, c):
    """The click's controls in the tab column: the noise source and the PITCH | AMP pads in the
    header, then five small knobs (v73; v61-v72 four big ones, the level in the master tab):
    Level | Delay | Length, Tone | Low Cut (theme.CLICK_KNOBS)."""
    ref, p = pb.ref, c["param"]
    pb.art = "click"
    # the chooser under a mini LED screen showing the noise's name (v37): a click on the screen
    # opens the chooser's list (images take no clicks)
    pb.add(popup_chooser(ref(c["CLICK_TYPE"]),
                         "Click source: white, pink, brown, blue, violet or grey noise (grey: even to the "
                         "ear), crackle, or a 909, 808 or 606 hat, simulated (the same on every hit). Click to choose",
                         theme.NOISE_RECT[0], theme.HEADER_Y, theme.NOISE_RECT[2], theme.HEADER_H), SHOW["click"])   # (v64: the screen's art 8 high, the chooser in the header row)
    if KNOB_ART_ON:
        lcd_images(pb, "lcd_noise", theme.NOISE_RECT, lambda i: f"CLICK_TYPE == {i}", len(CLICK_TYPES), SHOW["click"])
    # (v70) which of the click's curves the screen edits: two small pads, PITCH | AMP
    pb.switch(ref(c["CLICK_EDIT"]), "The click's curve shown on the screen for editing: PITCH (its pitch "
              "across its Length) or AMP (its level)", "clickedit", SHOW["click"])
    # (v73) the click's level back in its tab, first: five small encoders (the EQ's size)
    for pid, box, cap in zip(("CLICK", "CLICK_DELAY", "CLICK_DECAY", "CLICK_TONE", "CLICK_HP"),
                             theme.CLICK_KNOBS, theme.CLICK_CAPTIONS):
        title = "Level" if pid == "CLICK" else p[pid][1][3]
        pb.eq_encoder(ref(p[pid][0]), title, p[pid][1][2], box, cap, SHOW["click"], bipolar=False)


def master_tab(pb, c):
    """The master tab (v39; v31-v38 a global column beside the tab's): in the header the tune
    (its title, the fader, the note on a mini LED screen), keytrack and the panel's finish; then
    a grid as the other tabs' (v40; the drives went to the FX tab): the kick's length (the
    amp's: a knob in Time, the note value in Sync) | Phase, then Level, centred (v73: the click's
    level went to the click tab; v40-v72 Click level | Level)."""
    ref, p = pb.ref, c["param"]
    pb.art = "global"
    show = SHOW["master"]
    y, h = theme.HEADER_Y, theme.HEADER_H
    cols = [theme.TAB2_X + i * theme.CELL for i in range(2)]
    key_tip = "Keytrack, FIX or KEY: press to turn it over (FIX: the tune as set; KEY: it follows the played key, C3 = the tune)"
    for state, (kx, ky, kw, kh) in theme.KEY_TOGGLE_AT.items():   # (v58: under the pad, before the screen covers its FIX half)
        pb.add(toggle_group(ref(c["keytrack"]), key_tip, kx, ky, kw, kh), f"({show}) && (KEYTRACK == {state})")
    caption(pb, "Tune", theme.TUNE_X, y, theme.TUNE_LABEL_W, h, show)
    fader = pb.fader(ref(c["TUNE"]), "Root of the body (the bottom of the pitch curve): C0 .. C1, in semitones", show)
    if KNOB_ART_ON:
        # the note on a mini LED screen, one image per notch (v37)
        atom = pb.targets[id(fader["fields"]["data_model#6220"])]
        pid = atom["fields"]["preset_identifier#701"]["value"]
        lo = atom["fields"]["value_type#702"]["value"]["fields"]["min#345"]["value"]
        last = theme.FADER_STEPS - 1
        lcd_images(pb, "lcd_note", theme.NOTE_RECT, lambda k: " && ".join(
            part for part in (f"{pid} > {lo + k - 0.5}" if k else "", f"{pid} < {lo + k + 0.5}" if k < last else "")
            if part), theme.FADER_STEPS, show)
    else:
        pb.add(wave_surface(ref(c["draw_tune"]), *theme.NOTE_RECT), show)
    if KNOB_ART_ON:   # (v58) keytrack: one pad showing FIX or KEY (theme.KEY_TOGGLE_AT), as the theme switch
        cells = panel_cells()
        for state in theme.KEY_TOGGLE_AT:
            pb.add(panel_image(f"pads_keytrack_{state}", *cells[f"pads_keytrack_{state}"]), f"({show}) && (KEYTRACK == {state})")
        for name in theme.KEY_COVERS:
            pb.add(panel_image(name, *cells[name]), show)
    length_tip = "The kick's length (the amp curve's; Time or Sync is set in the Amp tab)"
    knob_cell(pb, ref(p["A_LEN"][0]), "Length", length_tip, cols[0], 0, SHOW["m_time"])
    if KNOB_ART_ON:
        assert theme.DIV_AT["global"][:2] == (cols[0], theme.ROWS[0] + KNOB_ART_H)
        pb.selector(ref(c["A_DIV"]), length_tip + ": a note value, turn to step through 1/64 .. 1 bar",
                    cols[0], theme.ROWS[0], SHOW["m_sync"])
    else:
        pb.add(knob(ref(c["A_DIV"]), "Length", length_tip, cols[0], theme.ROWS[0], theme.CELL, theme.CELL_H), SHOW["m_sync"])
    knob_cell(pb, ref(p["PHASE"][0]), "Phase", "Phase of the body once the click is over and the pitch has "
              "landed on the fundamental (the attack and the click are left as they are), degrees", cols[1], 0, show)
    knob_cell(pb, ref(p["LEVEL"][0]), "Level", p["LEVEL"][1][2], theme.TAB2_X + theme.CELL // 2, 1, show)


def theme_toggle(pb, c):
    """The panel's theme as one pad (v42; v40-v41 a DARK | LIGHT pair): it shows the theme it is in,
    lit, and each press turns it over. Under it, a native pair of buttons, upright, placed for each
    theme so that the other theme's button is under the pad (theme.TOGGLE_AT); the pair's other
    half sits off the pad, under a piece of the panel art (theme.TOGGLE_COVERS), and pressing it
    changes nothing (that theme is on)."""
    ref = pb.ref
    tip = "The panel's theme, DARK or LIGHT: press to turn it over (the screen, knobs and pads stay as they are)"
    pid = "PANEL"
    for look, (x, y, w, h) in theme.TOGGLE_AT.items():
        pb.add(toggle_group(ref(c["PANEL"]), tip, x, y, w, h), f"{pid} == {look}")
    if not KNOB_ART_ON:
        return
    cells = panel_cells()
    for look in theme.TOGGLE_AT:
        name = f"pads_panel_{look}"
        pb.add(panel_image(name, *cells[name]), f"{pid} == {look}")
    for name in theme.TOGGLE_COVERS:
        pb.add(panel_image(name, *cells[name]))


def fx_switch(pb, c, show):
    """The FX tab's on / off (v49): a mini LED screen, FX ON or FX OFF; each press turns it over
    (a native OFF | ON pair placed for each state, the other state's button under the screen, as
    theme_toggle)."""
    ref = pb.ref
    tip = "FX on / off: OFF bypasses Drive, EQ and Comp (their settings are kept)"
    for state, (x, y, w, h) in theme.FX_TOGGLE_AT.items():
        pb.add(toggle_group(ref(c["FX_ON"]), tip, x, y, w, h), f"({show}) && (FX_ON == {state})")
    if not KNOB_ART_ON:
        return
    lcd_images(pb, "lcd_fx", theme.FX_RECT, lambda i: f"FX_ON == {i}", len(theme.FX_NAMES), show)
    cells = panel_cells()
    for name in theme.FX_COVERS:
        pb.add(panel_image(name, *cells[name]), show)


def fx_tab(pb, c):
    """The FX tab (v40), in the signal's order Drive, EQ, Comp (v60): Drive | Comp on the first
    row (big encoders), the EQ's frame across the tray under them, three encoders (Low, Mid, High).
    (v58-v59: Comp | Drive, the mid drive and a small EQ beside it; v42-v57 Comp | Drive, the mid
    drive centred under them; v40-v41 one row)"""
    ref, p = pb.ref, c["param"]
    pb.art = "global"
    show = SHOW["fx"]
    x0, x1 = theme.TAB2_X, theme.TAB2_X + theme.CELL
    knob_cell(pb, ref(p["MID_DRIVE"][0]), "Drive", "Saturation of the mids (from 2.5 x the fundamental up to "
              "5 kHz): grit without touching the fundamental or the click's top. First in the chain: Drive, EQ, Comp",
              x0, 0, show)
    knob_cell(pb, ref(p["COMP"][0]), "Comp", "Compressor on the whole kick, last in the chain (Drive, EQ, Comp): "
              "takes the attack down towards the tail, for an even waveform. Turn up for more (threshold 0 .. -24 dB, "
              "3:1, half made up)", x1, 0, show)
    fx_switch(pb, c, show)
    if KNOB_ART_ON:
        pb.add(panel_image("frame_eq", *panel_cells()["frame_eq"]), show)
    caption(pb, "EQ", *theme.EQ_TITLE, show)
    tips = {"EQ_LOW": "EQ low: a shelf at 80 Hz, +-15 dB (the sub and the body)",
            "EQ_MID": "EQ mid: a bell at 400 Hz, +-15 dB, narrower the more it boosts or cuts (cut for less box)",
            "EQ_HIGH": "EQ high: a shelf at 5 kHz, +-15 dB (the click's snap)"}
    for (key, tip), title, box, cap in zip(tips.items(), ("Low", "Mid", "High"), theme.EQ_KNOBS, theme.EQ_CAPTIONS):
        pb.eq_encoder(ref(p[key][0]), title, tip + ". After the Drive, before the Comp; bypassed by FX OFF", box, cap, show)


def device_panel(ref, c, name):
    """The device (theme.py layout): the panel art at the back; the tab switches; the curve
    editor with the kick's waveform under it (a stack: the drawing at the back, the editor on
    top; Bitwig's zoom, Ctrl+Alt+wheel, always on here); the tab's controls; the global column;
    the name plate is part of the panel art."""
    pb = PanelBuilder(ref)
    if KNOB_ART_ON:
        cells = panel_cells()
        for piece in theme.DECO_PIECES:
            pb.add(panel_image(f"deco_{piece}", *cells[f"deco_{piece}"]))
    pb.switch(pb.ref(c["VIEW"]), "Master (the kick's oscilloscope, tune and output) / Pitch curve / "
              "Amp curve / Click (noise) / FX (drive, EQ, compressor)", "view")
    vx, vy, vw, vh = theme.VIEW_RECT
    layers = []
    for tab in ("pitch", "amp"):
        wave = wave_surface(ref(c[f"draw_{tab}"]), 0, 0, 1, 1)
        wave["fields"]["layout_settings#6226"] = stack_layout(vw, vh)
        item = curve_display(ref(c[f"{tab}_curve"]), None, 0, 0, 1, 1, EDIT_TIP, CURVE_AXES, zoom=True,
                             under=wave, color=theme.CURVE_COLOR[tab])
        item["fields"]["layout_settings#6226"] = stack_layout(vw, vh)
        pb.expression(item, 6309, SHOW[tab])
        layers.append(item)
        with pb.tab_layer(tab):
            tab_side(pb, c, tab)
    pb.add(stack(layers, layout(vx, vy, vw, vh)), "VIEW > 0 && VIEW < 3")
    # (v70) the click's curves, PITCH or AMP (CLICK_EDIT), over its waveform
    pb.add(stack(click_editors(pb, ref, c, vw, vh, True), layout(vx, vy, vw, vh)), SHOW["click"])
    pb.add(wave_surface(ref(c["draw_master"]), vx, vy, vw, vh), SHOW["scope"])
    if KNOB_ART_ON:   # the glass over the screen (images take no clicks: the curve stays editable)
        pb.add(panel_image("glass_view", *panel_cells()["glass_view"]))
    with pb.tab_layer("click"):
        click_tab(pb, c)
    with pb.tab_layer("master"):
        master_tab(pb, c)
    with pb.tab_layer("fx"):
        fx_tab(pb, c)
    for tab, inside, outside in pb.layers:
        print(f"  {tab} layer: {inside} items, {outside} outside the tray")
    theme_toggle(pb, c)   # (v45: on every tab, at the name plate)
    return panel(name, pb.items, theme.PANEL_W, theme.PANEL_H, pb.expressions)


CLICK_EDIT_TIP = ("The click's curve, across its Length: PITCH (middle = as it is, top / bottom = +24 / -24 "
                  "semitones, as a sample transposed) or AMP (its level). " + EDIT_TIP)


def click_editors(pb, ref, c, w, h, zoom, show=None):
    """(v70) The click's two curve editors (PITCH, AMP), each over the click's waveform, for a
    stack w x h; each shown with its CLICK_EDIT (and show, if given)."""
    items = []
    for k, (name, color) in enumerate((("click_pitch_curve", theme.CURVE_COLOR["pitch"]),
                                       ("click_amp_curve", theme.CURVE_COLOR["amp"]))):
        wave = wave_surface(ref(c["draw_click"]), 0, 0, 1, 1)
        wave["fields"]["layout_settings#6226"] = stack_layout(w, h)
        # (v79) the body, in grey over the click (its own drawing: the click's has no room for it)
        body = wave_surface(ref(c["draw_click_body"]), 0, 0, 1, 1)
        body["fields"]["layout_settings#6226"] = stack_layout(w, h)
        item = curve_display(ref(c[name]), None, 0, 0, 1, 1, CLICK_EDIT_TIP, CURVE_AXES, zoom=zoom,
                             under=[wave, body], color=color)
        item["fields"]["layout_settings#6226"] = stack_layout(w, h)
        pb.expression(item, 6309, f"({show}) && (CLICK_EDIT == {k})" if show else f"CLICK_EDIT == {k}")
        items.append(item)
    return items


def main_panel(ref, c):
    return device_panel(ref, c, "Main")


# The maximized view: the curve stretched over the whole window, as Compressor+'s (v33, v35, v37).
# Only a plain display stretches with the window, and a plain display does not zoom; a zoomable one
# keeps the size it is made with, about 125 units high (v26-v32, v36: zoomable but a band across
# the window). The zoom (Ctrl+Alt+wheel) stays in the device. (v34's detail pane went in v35: its
# drawings stay, unused, so that projects and presets saved since keep matching the device.)


def big_panel(ref, c):
    """Shown by the device's maximize button (device_contents.maximized_panel): the current
    tab's curve over the whole window (the controls stay in the device)."""
    pb = PanelBuilder(ref)
    layers = []
    for tab in ("pitch", "amp"):
        wave = wave_surface(ref(c[f"draw_{tab}"]), 0, 0, 1, 1)
        wave["fields"]["layout_settings#6226"] = stack_layout(250, 120)
        item = curve_display(ref(c[f"{tab}_curve"]), None, 0, 0, 1, 1, EDIT_TIP, CURVE_AXES, zoom=False,
                             under=wave, color=theme.CURVE_COLOR[tab])
        item["fields"]["layout_settings#6226"] = stack_layout(250, 120)
        pb.expression(item, 6309, SHOW[tab])
        layers.append(item)
    layers += click_editors(pb, ref, c, 250, 120, False, SHOW["click"])   # (v70)
    scope = wave_surface(ref(c["draw_master"]), 0, 0, 1, 1)
    scope["fields"]["layout_settings#6226"] = stack_layout(250, 120)
    pb.expression(scope, 6309, SHOW["scope"])
    layers.append(scope)
    root = box([stack(layers, box_layout(250, 120, True, True))], False)
    return panel("Maximized", [], 250, 120, pb.expressions, root=root, resizeable=True)


def metadata(revision):
    fields = {
        "application_version_name": v("String", VERSION), "branch": v("String", ""),
        "comment": v("String", ""), "creator": v("String", CREATOR),
        "device_category": v("String", "Synth"), "device_creator": v("String", CREATOR),
        "device_description": v("String", DESCRIPTION), "device_id": v("String", UUID),
        "device_name": v("String", NAME), "device_type": v("String", "note_to_audio"),
        "device_uuid": v("Uuid", UUID), "has_audio_input": v("Bool", False),
        "has_audio_output": v("Bool", True), "has_note_input": v("Bool", True),
        "has_note_output": v("Bool", False), "preset_name": v("String", NAME),
        "revision_id": v("String", revision), "revision_no": v("Int32", 1),
        "suggest_for_audio_input": v("Bool", False), "suggest_for_note_input": v("Bool", True),
        "tags": v("String", KEYWORDS), "type": v("String", "application/bitwig-device"),
    }
    return {**obj(4, "meta", fields), "wide_names": [False] * len(fields)}



def check_backward_refs(root):
    """Walk the body in Bitwig's reading order (depth-first, fields in order): a reference may
    only name an object already started at that point."""
    started = 0

    def check(target, where):
        if target > started:
            raise SystemExit(f"forward ObjectRef {target} (only {started} objects read) in {where}")

    def walk(item):
        nonlocal started
        started += 1
        for key, entry in item.get("fields", {}).items():
            kind, value = entry.get("type"), entry.get("value")
            if kind == "ObjectRef":
                check(value, f"{item.get('class_name')}.{key}")
            elif kind == "Object" and isinstance(value, dict):
                walk(value)
            elif kind == "ObjectList":
                for element in value:
                    if isinstance(element.get("Object"), dict):
                        walk(element["Object"])
                    elif "ObjectRef" in element:
                        check(element["ObjectRef"], f"{item.get('class_name')}.{key}[]")

    walk(root)

def document(binaries, shaders):
    bindings = []

    def ref(target):
        wrapper = v("ObjectRef", 0)
        bindings.append((wrapper, target))
        return wrapper

    def wire(target, port=0):
        entry = connection(port=port)
        entry["Object"]["fields"]["source_component#248"] = ref(target)
        return entry

    def nitro(name_binary, inputs, input_wires, outputs):
        return obj(1721, "nitro_atom", {
            "settings#6194": settings(input_wires),
            "channel_count#607": v("Byte", 0), "oversampling#608": v("Byte", 0),
            "fft_order#6567": v("Byte", 0), "code_storage#10421": v("ByteArray", [0, *name_binary]),
            "is_code_storage_binary_ast#14616": v("Bool", True),
            "use_code_path#11360": v("Bool", False), "code_path#11357": v("String", ""),
            "nitro_inputs#15756": v("ObjectList", owned(*inputs)),
            "nitro_outputs#15757": v("ObjectList", owned(*outputs)),
        })

    audio_proxy = proxy_in(note=False)
    note_proxy = proxy_in(note=True)
    audio_source = obj(2000, "audio_source_atom", {
        "settings#6194": settings([wire(audio_proxy)]), "channel_count#607": v("Byte", 0),
        "oversampling#608": v("Byte", 0), "port_color#10378": v("Int16", 999),
        "name#3639": v("String", "In"), "preset_identifier#3640": v("String", "IN"),
    })
    keytrack = indexed_atom("KEYTRACK", "Keytrack", ["Off", "On"], 0)
    fx_on = indexed_atom("FX_ON", "FX", ["Off", "On"], 1)   # (v49) the FX tab's on / off
    atoms = {p[0]: (decimal_atom(p[0], *p[2:]), p) for p in PARAMS + LENGTHS}

    # UI state and modes (indexed atoms; VIEW is the tab, panel-only)
    view = indexed_atom("VIEW", "View", ["Master", "Pitch", "Amp", "Click", "FX"], 0, automate=False)
    # the panel's finish (v40): the dark faceplate or a white one, panel-only
    panel_look = indexed_atom("PANEL", "Panel", ["Dark", "Light"], 0, automate=False)
    modes = {
        # preset id TUNE_NOTE, not TUNE: up to v17 TUNE was a decimal atom, and a project saved
        # with it crashed Bitwig on load (an integer atom given a decimal preset value).
        "TUNE": integer_atom("TUNE_NOTE", "Tune", 24, 36, 31, prefix="MIDI "),
        "P_SYNC": indexed_atom("P_SYNC", "Pitch Length Mode", ["Time", "Sync"], 1),
        # (v75) the note values: decimal parameters 0 .. 15 (an index into DIVISIONS, rounded by the
        # phase core), so that modulators reach them (v37-v74 indexed atoms P_DIV / A_DIV: Bitwig
        # does not modulate a list); new ids, as a decimal atom given an indexed preset value is
        # trouble (v17's TUNE): tools/convert_div_presets.py turned the presets' P_DIV / A_DIV over
        "P_DIV": decimal_atom("P_NOTE", "Pitch Length Note", "Note", 0.0, len(DIVISIONS) - 1.0,
                              float(DIVISIONS.index("1/8")), U_NONE, 0, 0),
        "A_SYNC": indexed_atom("A_SYNC", "Amp Length Mode", ["Time", "Sync"], 1),
        "A_DIV": decimal_atom("A_NOTE", "Amp Length Note", "Note", 0.0, len(DIVISIONS) - 1.0,
                              float(DIVISIONS.index("1/8")), U_NONE, 0, 0),
        "A_SCALE": indexed_atom("A_SCALE", "Amp Scale", ["Lin", "dB"], 0),
        "CLICK_TYPE": indexed_atom("CLICK_TYPE", "Click Noise", CLICK_TYPES, CLICK_TYPES.index("909 Hat")),   # (v72: the default, [MindB] Kick 01's)
        # (v70) which of the click's curves the screen edits (the click tab's PITCH / AMP pads)
        "CLICK_EDIT": indexed_atom("CLICK_EDIT", "Click Curve", ["Pitch", "Amp"], 1, automate=False),
        # no longer shown (v29: both editors always zoom); kept so projects and presets saved
        # with it load as before
        "ZOOM": indexed_atom("ZOOM", "Zoom", ["Off", "On"], 0, automate=False),
    }
    # the project transport: output 2 = beats per sample (as Polarity's tempo-synced devices)
    transport = obj(1839, "transport_component", {
        "settings#6194": settings(), "use_double_precision_beattime#10070": v("Bool", True),
    })

    # 1. phase clock: notes -> pitch and amp phases (0..1 of each curve's length); idle: scan.
    #    Also the root frequency (tune) and the tempo.
    phase_core = nitro(binaries["phase"],
        [nitro_port("note_in", 0, 1, 2, event="NoteEvent"),
         nitro_port("pitch_length", 1, 1, 1), nitro_port("amp_length", 2, 1, 1),
         nitro_port("pitch_sync", 3, 1, 3), nitro_port("pitch_div", 4, 1, 1),   # (v75: audio, a decimal)
         nitro_port("amp_sync", 5, 1, 3), nitro_port("amp_div", 6, 1, 1),
         nitro_port("beats_per_frame", 7, 1, 1), nitro_port("tune_note", 8, 1, 3),
         nitro_port("pitch_time_scale", 9, 1, 1), nitro_port("amp_time_scale", 10, 1, 1),
         nitro_port("view", 11, 1, 3)],
        [wire(note_proxy), wire(atoms["P_LEN"][0]), wire(atoms["A_LEN"][0]),
         wire(modes["P_SYNC"]), wire(modes["P_DIV"]), wire(modes["A_SYNC"]), wire(modes["A_DIV"]),
         wire(transport, 2), wire(modes["TUNE"]),
         wire(atoms["P_TIME"][0]), wire(atoms["A_TIME"][0]), wire(view)],
        [nitro_port("pitch_phase", 0, 1, 1, output=True), nitro_port("amp_phase", 1, 1, 1, output=True),
         nitro_port("ctl", 2, 4, 1, output=True), nitro_port("tune_hz", 3, 1, 1, output=True),
         nitro_port("ms_per_beat_out", 4, 1, 1, output=True),
         nitro_port("click_phase", 5, 1, 1, output=True), nitro_port("click_ctl", 6, 2, 1, output=True)])
    # 2. the two native curves
    pitch_curve = curve_atom("PITCH_CURVE", "Pitch", PITCH_POINTS, [wire(phase_core, 0)])
    amp_curve = curve_atom("AMP_CURVE", "Amp", AMP_POINTS, [wire(phase_core, 1)])
    # (v70) the click's two curves, swept by the phase core all the time (the voice plays its copy)
    click_pitch_curve = curve_atom("CLICK_PITCH_CURVE", "Click Pitch", CLICK_PITCH_POINTS, [wire(phase_core, 5)])
    click_amp_curve = curve_atom("CLICK_AMP_CURVE", "Click Amp", CLICK_AMP_POINTS, [wire(phase_core, 5)])
    # 3. voice: notes + curve values + parameters -> stereo
    fixed = [("note_in", 2, wire(note_proxy)), ("keytrack", 3, wire(keytrack)),
             ("pitch_curve", 1, wire(pitch_curve)), ("amp_curve", 1, wire(amp_curve)),
             ("ctl", 1, wire(phase_core, 2)), ("tune_hz", 1, wire(phase_core, 3)),
             ("click_type", 3, wire(modes["CLICK_TYPE"])),
             ("pitch_scale", 1, wire(atoms["P_CURVE"][0])), ("amp_scale", 3, wire(modes["A_SCALE"])),
             ("click_pitch_curve", 1, wire(click_pitch_curve)), ("click_amp_curve", 1, wire(click_amp_curve)),
             ("click_ctl", 1, wire(phase_core, 6))]
    lanes = {"ctl": 4, "click_ctl": 2}
    voice_ports = [nitro_port(name, i, lanes.get(name, 1), kind, event="NoteEvent" if kind == 2 else "")
                   for i, (name, kind, _) in enumerate(fixed)]
    voice_ports += [nitro_port(p[1], len(fixed) + i, 1, 1) for i, p in enumerate(PARAMS)]
    voice_ports.append(nitro_port("fx_on", len(fixed) + len(PARAMS), 1, 3))   # (v49, after the parameters)
    voice_core = nitro(binaries["voice"], voice_ports,
        [w for _, _, w in fixed] + [wire(atoms[p[0]][0]) for p in PARAMS] + [wire(fx_on)],
        [nitro_port("out", 0, 2, 1, output=True)])
    output_proxy = proxy_out([wire(voice_core, 0)])

    # 4. waveform drawings, one per tab: a display core keeps the scanned points, an SkSL
    #    drawing reads its three four-lane outputs (audioLow, audioMedium, audioHigh)
    displays, drawings = {}, {}
    for tab in ("pitch", "amp", "master", "click"):   # (v70: the click's own, with its curves)
        displays[tab] = nitro(binaries[f"display_{tab}"],
            [nitro_port("pitch_curve", 0, 1, 1), nitro_port("amp_curve", 1, 1, 1), nitro_port("ctl", 2, 4, 1),
             nitro_port("tune_hz", 3, 1, 1), nitro_port("pitch_amount", 4, 1, 1),
             nitro_port("start_phase", 5, 1, 1), nitro_port("ms_per_beat", 6, 1, 1),
             nitro_port("pitch_scale", 7, 1, 1), nitro_port("amp_scale", 8, 1, 3),
             nitro_port("click_type", 9, 1, 3), nitro_port("click_level", 10, 1, 1),
             nitro_port("click_decay", 11, 1, 1), nitro_port("click_tone", 12, 1, 1),
             nitro_port("click_hp", 13, 1, 1), nitro_port("pitch_time_scale", 14, 1, 1),
             nitro_port("amp_time_scale", 15, 1, 1), nitro_port("click_delay", 16, 1, 1), nitro_port("fx_on", 17, 1, 3),
             nitro_port("click_pitch_curve", 18, 1, 1), nitro_port("click_amp_curve", 19, 1, 1),
             nitro_port("click_ctl", 20, 2, 1),
             # (v76) the FX, for the oscilloscope's display (the master tab's) to draw the kick after them
             nitro_port("mid_drive", 21, 1, 1), nitro_port("body_comp", 22, 1, 1),
             nitro_port("eq_low", 23, 1, 1), nitro_port("eq_mid", 24, 1, 1), nitro_port("eq_high", 25, 1, 1)],
            [wire(pitch_curve), wire(amp_curve), wire(phase_core, 2), wire(phase_core, 3),
             wire(atoms["PITCH"][0]), wire(atoms["PHASE"][0]), wire(phase_core, 4),
             wire(atoms["P_CURVE"][0]), wire(modes["A_SCALE"]), wire(modes["CLICK_TYPE"]),
             wire(atoms["CLICK"][0]), wire(atoms["CLICK_DECAY"][0]), wire(atoms["CLICK_TONE"][0]),
             wire(atoms["CLICK_HP"][0]), wire(atoms["P_TIME"][0]), wire(atoms["A_TIME"][0]),
             wire(atoms["CLICK_DELAY"][0]), wire(fx_on),
             wire(click_pitch_curve), wire(click_amp_curve), wire(phase_core, 6),
             *(wire(atoms[key][0]) for key in ("MID_DRIVE", "COMP", "EQ_LOW", "EQ_MID", "EQ_HIGH"))],
            [nitro_port("lane0", 0, 4, 1, output=True), nitro_port("lane1", 1, 4, 1, output=True),
             nitro_port("lane2", 2, 4, 1, output=True)])
    # the click's drawing reads the amp display (the body's length and level, the click's settings)
    # (the detail drawings, of the maximized view's detail pane, came in v34: a project saved
    # before has nothing under their ids, so they draw nothing until the device is inserted again)
    # (v39: the master tab's oscilloscope reads its own display, which sends the drive)
    # (v62: the click's drawing reads the master display, which sends the click's delay)
    probe = None
    if "probe" in binaries:   # (--probe-ctl) the master drawing's inputs 3 .. 8 fed known values
        probe = nitro(binaries["probe"], [], [], [nitro_port(f"out{n}", n - 3, 4, 1, output=True) for n in range(3, 9)])
    for tab, source in (("pitch", "pitch"), ("amp", "amp"), ("click", "click"), ("tune", "pitch"),
                        ("pitch_detail", "pitch"), ("amp_detail", "amp"), ("master", "master"),
                        ("click_body", "master")):   # (v79: the click view's body, over its click)
        extra = [wire(probe, i) for i in range(6)] if (probe is not None and tab == "master") else \
                [connection() for _ in range(6)]
        drawings[tab] = obj(5512, "", {
            "settings#6194": settings([wire(displays[source], 0), wire(displays[source], 1),
                                       wire(displays[source], 2), *extra]),
            "channel_count#607": v("Byte", 0), "name#374": v("String", ""),
            "prevent_parent_from_sleeping#11002": v("Bool", False),
            # The shader is device state: a project or preset saves it (class 5516, by this id) and
            # loading one sets it from there, the device's own shader only on a fresh insert:
            #   saved text under this id -> that text, even old (v23 drew v22's amber) or empty;
            #   nothing under this id -> empty, nothing drawn (v24's renamed ids; v25-v26's "").
            # So the ids stay WAVE_<TAB> for good, and tools/repair_presets.py rewrites the saved
            # drawings of the KickForge presets with the installed shaders after a change.
            "preset_identifier#701": v("String", f"WAVE_{tab.upper()}"), "#16316": v("WideString", shaders[tab]),
        })

    c = {"VIEW": view, "PANEL": panel_look, **modes, "keytrack": keytrack, "FX_ON": fx_on, "param": atoms,
         "pitch_curve": pitch_curve, "amp_curve": amp_curve,
         "click_pitch_curve": click_pitch_curve, "click_amp_curve": click_amp_curve,
         "draw_pitch": drawings["pitch"], "draw_amp": drawings["amp"], "draw_click": drawings["click"],
         "draw_tune": drawings["tune"], "draw_pitch_detail": drawings["pitch_detail"],
         "draw_amp_detail": drawings["amp_detail"], "draw_master": drawings["master"],
         "draw_click_body": drawings["click_body"]}
    big = big_panel(ref, c)
    main = main_panel(ref, c)
    maximized = v("ObjectRef", 0)

    body = obj(151, "device_contents", {
        "proxy_in_ports#177": v("ObjectList", owned(audio_proxy, note_proxy)),
        "child_components#173": v("ObjectList", owned(
            audio_source, keytrack, *(a for a, _ in atoms.values()), view, panel_look, *modes.values(), fx_on,
            transport, phase_core, pitch_curve, amp_curve, click_pitch_curve, click_amp_curve, voice_core,
            displays["pitch"], displays["amp"], displays["master"], displays["click"],   # (v62: master before the drawings: the click's reads it)
            *([probe] if probe is not None else []),
            drawings["pitch"], drawings["amp"], drawings["click"], drawings["tune"],
            drawings["pitch_detail"], drawings["amp_detail"], drawings["master"], drawings["click_body"])),
        "panels#6213": v("ObjectList", owned(main, big)),
        "proxy_out_ports#178": v("ObjectList", owned(output_proxy)),
        "device_UUID#385": v("Uuid", UUID), "device_name#386": v("String", NAME),
        "description#2057": v("String", DESCRIPTION), "creator#387": v("String", CREATOR),
        "category#390": v("String", "Synth"),
        "suggest_for_note_input#4846": v("Bool", True), "suggest_for_audio_input#4847": v("Bool", False),
        "settings#6194": v("NullObject"), "fft_order#6566": v("Byte", 0),
        "analysis_fft_order#11047": v("Byte", 11), "analysis_fft_fall_speed#11110": v("Byte", 1),
        "device_revision#13647": v("Byte", 1), "sleep_level_threshold#1977": v("Double", -96.0),
        "sleep_level_timeout#1978": v("Double", 0.05),
        # the waveform scan runs while the kick is silent: keep the device awake
        "prevent_sleep#14608": v("Bool", True),
        "comment#388": v("String", ""), "keywords#389": v("String", KEYWORDS),
        "device_type#391": v("Byte", 2), "has_been_modified#392": v("Bool", True),
        "color_tint#13354": v("Color", [0.0, 0.0, 0.0, 0.0]),
        # the device's maximize button shows the big panel (as Bitwig's own devices)
        "header_area_panel#6417": v("NullObject"), "maximized_panel#7549": maximized,
        "synth_display_panel#10713": v("NullObject"), "synth_overview_panel#10727": v("NullObject"),
        "mixer_eq_panel#10992": v("NullObject"), "is_allowed_to_show_maximized_panel#10663": v("Bool", True),
    })

    ids = {id(item): index for index, item in enumerate(iter_owned_objects(body), 1)}
    for wrapper, target in bindings:
        wrapper["value"] = ids[id(target)]
    maximized["value"] = ids[id(big)]
    # every reference must point backwards in reading order (Bitwig resolves them while reading)
    check_backward_refs(body)

    revision = hashlib.sha1(f"{UUID}/v79-click-delay-5ms{'-probe' if 'probe' in binaries else ''}".encode()).hexdigest()
    return {
        "header": {"format_version": 3, "serialization_format": 2, "document_version": 207,
                   "object_offset": 0, "resources_offset": 0, "flags": 0},
        "metadata": metadata(revision), "body": body,
        "meta_nonce": "0" * 32, "body_nonce": "0" * 32,
    }


def check_port_order(doc, sources, binaries):
    """(v78) Each Nitro core's ports, as the document lists them, in the order its source declares
    them: Bitwig wires them by position (v76-v77 declared the display's FX inputs before the
    click's, numbered after: the click's curves fed the scope's FX, the click display got none)."""
    import re
    cores = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("class_id") == 1721:
                cores.append(n["fields"])
            for value in n.values():
                walk(value)
        elif isinstance(n, list):
            for value in n:
                walk(value)
    walk(doc)

    def names(fields, key):
        out = []
        for entry in fields[key]["value"]:
            port = entry.get("Object", entry)
            out.append(next(v["value"] for k, v in port["fields"].items() if k.startswith("name#")))
        return out
    for key, source in sources.items():
        text = Path(source).read_text(encoding="utf-8")
        declared_in = re.findall(r"^\s*(?:audio|value|event)_inport\s+[^\s;]+\s+(\w+)", text, re.M)
        declared_out = re.findall(r"^\s*(?:audio|value|event)_outport\s+[^\s;]+\s+(\w+)", text, re.M)
        storage = [0, *binaries[key]]
        matched = [f for f in cores if f["code_storage#10421"]["value"] == storage]
        assert matched, f"{key}: no Nitro core in the document"
        for fields in matched:
            got_in, got_out = names(fields, "nitro_inputs#15756"), names(fields, "nitro_outputs#15757")
            assert got_in == declared_in, f"{key}: inputs {got_in} != source {declared_in}"
            assert got_out == declared_out, f"{key}: outputs {got_out} != source {declared_out}"


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, default=HERE / "build" / f"{NAME}.bwdevice")
    cli.add_argument("--json", type=Path, help="also write the document JSON here")
    cli.add_argument("--no-knob-art", action="store_true", help="native knobs only, no neon rings")
    cli.add_argument("--probe-ctl", action="store_true",
                     help="test build: the master drawing's inputs 3-8 fed known values, its screen prints "
                          "the uniforms Bitwig declares (ctl, cvGate0, beatTime, iTime, width, height)")
    args = cli.parse_args()
    global KNOB_ART_ON
    KNOB_ART_ON = not args.no_knob_art
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    (HERE / "build").mkdir(exist_ok=True)   # the display sources and shaders are kept there
    with TemporaryDirectory(dir=out.parent) as tmp:
        tmp = Path(tmp)
        binaries, shaders = {}, {}
        sources = {"phase": HERE / "kick_phase.nitro", "voice": HERE / "kick_voice.nitro"}
        if args.probe_ctl:
            sources["probe"] = HERE / "kick_probe.nitro"
        template = (HERE / "kick_display.nitro.in").read_text(encoding="utf-8")
        wave = (HERE / "kick_wave.sksl.in").read_text(encoding="utf-8")
        # the device palette (theme.py): each tab's attack and tail colours
        for index, tab in enumerate(("pitch", "amp", "click", "tune", "master")):
            color, color2 = ("float3(%.3f, %.3f, %.3f)" % c for c in theme.WAVE[tab])
            if tab in ("pitch", "amp", "master", "click"):
                # (v70) the click's display: the master's (its head, the click's delay) with the
                # click's curves in place of the body's
                source = HERE / "build" / f"kick_display_{tab}.nitro"
                source.write_text(template.replace("@TAB@", str(min(index, 1)))
                                  .replace("@MASTER@", str(int(tab in ("master", "click"))))
                                  .replace("@CLICK@", str(int(tab == "click")))
                                  .replace("@SCOPE@", str(int(tab == "master"))).replace("@NAME@", tab), encoding="utf-8")
                sources[f"display_{tab}"] = source
            for name, detail in ((tab, 1), *(((f"{tab}_detail", theme.DETAIL),) if tab in ("pitch", "amp") else ())):
                shaders[name] = (wave.replace("@NAME@", name).replace("@COLOR@", color).replace("@COLOR2@", color2)
                                 .replace("@MODE@", f"{index}.0").replace("@DETAIL@", f"{detail}.0")
                                 .replace("@X_END@", repr(float(theme.X_END))).replace("@OVERLAY@", "0.0"))
                if args.probe_ctl and name == "master":
                    shaders[name] = (shaders[name].replace("half4 main(float2 fragCoord) {", "half4 scopeMain(float2 fragCoord) {")
                                     + (HERE / "probe_screen.sksl").read_text(encoding="utf-8"))
                (HERE / "build" / f"kick_wave_{name}.sksl").write_text(shaders[name], encoding="utf-8")
        # (v79) the click view's body layer: the click view's span, the body from the oscilloscope's display
        color, color2 = ("float3(%.3f, %.3f, %.3f)" % c for c in theme.WAVE["click"])
        shaders["click_body"] = (wave.replace("@NAME@", "click_body").replace("@COLOR@", color).replace("@COLOR2@", color2)
                                 .replace("@MODE@", "2.0").replace("@DETAIL@", "1.0")
                                 .replace("@X_END@", repr(float(theme.X_END))).replace("@OVERLAY@", "1.0"))
        (HERE / "build" / "kick_wave_click_body.sksl").write_text(shaders["click_body"], encoding="utf-8")
        for key, source in sources.items():
            binary = tmp / (key + ".nitrobin")
            compiler_profiles.compile_source(source, binary, INPUTS)
            binaries[key] = binary.read_bytes()
        doc = document(binaries, shaders)
        check_port_order(doc, sources, binaries)
        source = tmp / "device.json"
        source.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        if args.json:
            args.json.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        candidate = tmp / out.name
        result = subprocess.run([str(CODEC), "from-json", str(source), str(candidate)], capture_output=True, text=True,
                                timeout=300)
        if result.returncode:
            raise SystemExit(f"codec failed: {result.stderr or result.stdout}")
        candidate.replace(out)
    print(f"{hashlib.sha256(out.read_bytes()).hexdigest()}  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
