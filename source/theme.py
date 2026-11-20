"""KickForge's colours, shared by the Blender art (knobs/), the waveform shader and the build.

One analogous palette, cyan -> azure -> indigo -> violet -> orchid -> rose (sRGB, as shown):
each part of the device takes a neighbouring stretch of it, the switches glow deep
blue-violet (indigo), the panel is a cold near-black.
"""

PALETTE = {
    "cyan": (0.26, 0.86, 1.00),
    "azure": (0.30, 0.58, 1.00),
    "indigo": (0.40, 0.34, 1.00),   # deep blue-violet: the switches' LEDs
    "violet": (0.62, 0.40, 1.00),
    "orchid": (0.86, 0.38, 0.98),
    "rose": (1.00, 0.42, 0.70),
}

# Knob LED sweeps: (first LED, last LED)
SECTIONS = {
    "pitch": ("violet", "orchid"),
    "amp": ("cyan", "azure"),
    "click": ("orchid", "rose"),
    "global": ("indigo", "violet"),   # (the master tab's knobs, v39)
}

# The waveform drawings' colours per tab (kick_wave.sksl.in @COLOR@ -> @COLOR2@): the attack's,
# fading to the tail's across the view
WAVE = {
    "pitch": ((0.90, 0.48, 1.00), (0.56, 0.44, 1.00)),
    "amp": ((0.30, 0.90, 1.00), (0.36, 0.56, 1.00)),
    "click": ((1.00, 0.46, 0.74), (0.86, 0.42, 1.00)),
    "tune": ((0.74, 0.70, 1.00), (0.74, 0.70, 1.00)),
    "master": ((0.72, 0.62, 1.00), (0.42, 0.52, 1.00)),   # v39: the oscilloscope, indigo to violet
}

PAD_LIT = PALETTE["indigo"]            # rubber switch pads, lit from beneath
PANEL = (0.372, 0.37, 0.362)           # panel paint (sRGB; v57: a neutral grey, rendered about Bitwig's own device strip, 91; v38-v56 a blue-black 0.055, 0.055, 0.075)
PANEL_LIGHT = (0.95, 0.95, 0.93)       # the white panel's paint (v40, the PANEL switch's LIGHT)
LIGHT_EXPOSURE = 4.5                   # the white panel's render brightened (a vivid white, v40)
LEGEND_DARK = (70, 70, 80)             # the controls' titles on the white panel
RUBBER = (0.135, 0.135, 0.15)          # the silicone of the pads, the fader's cap and the knobs' grips (sRGB)

# Bitwig's display colours (enum RCp, serialized ids): the curve line of each editor
DISPLAY_COLOR = {"RED": 0, "ORANGE": 1, "YELLOW": 2, "GREEN": 3, "BLUE": 4, "PURPLE": 5, "WHITE": 6,
                 "TURQUOISE": 11}
CURVE_COLOR = {"pitch": DISPLAY_COLOR["PURPLE"], "amp": DISPLAY_COLOR["BLUE"]}


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def linear(c):
    """sRGB -> linear (Cycles colours)."""
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# Panel layout, in Bitwig panel grid units. build_kick.py places the controls on it;
# knobs/render_panel_art.py draws the panel art to it.
# Bitwig draws an SVG at PX_PER_UNIT SVG px per grid unit (measured on the v23 screenshot: a pad
# group, the name plate and the inlay lines all fit 4.0; 5.1 was a misreading). An image larger
# than its cell is not centred but hangs from the cell's top left corner, so every image is made
# exactly the size of its cell.
PX_PER_UNIT = 4.0
# the one angle every control is seen from (v42): the knobs, the selectors, the pads and the fader,
# the cameras aimed at the panel's plane so their feet sit where the top-down panel art has them
# (v41: knobs 24, pads 16, fader 0 degrees, which looked out of line)
VIEW_TILT = 12.0
# v38: more room (146 x 53 -> 158 x 61): every compartment (the header, the screen, the tab's
# controls) in a frame like the screen's (render_panel_art.arcade_frame), about two units apart and
# from the panel's edges. v39: the global column went into the Master tab: one tray of three
# columns for the tab's controls (158 -> 136 wide)
PANEL_W, PANEL_H = 124, 53   # (v44: 61 -> 53, Bitwig's standard chain height (blueprint PANEL002, as Normalizer / Growl): at 61 the device stood taller than its neighbours) (v43: back to 61 high: Bitwig fits the panel to the chain's height, and at 68 every part drew ~10 % smaller; 136 -> 124 wide)
CHEEK = 3                       # wooden end cheeks, each side
FRAME = 1.7                     # a compartment's frame: its outer edge to its inside
VIEW_RECT = (6, 15, 64, 35)   # (v44: 43 -> 35 high) (v43: 72 -> 64 wide)     # the curve / waveform view: x, y, w, h (v29: 82 x 46 -> 72 x 44:
                                # room for the knobs, and for the arcade bezel round the screen)
HEADER_Y, HEADER_H = 4, 6       # tab switches, length mode, tune (v37: 4 -> 5 high, v41: 6, bigger pads)
TAB_X, COL_W = 76, 40           # the tab's tray: three knob columns (the master tab's)
TAB2_X = TAB_X + 2              # the pitch, amp and click tabs' 2 x 2 grid, centred in the tray
CELL = 18                       # a knob cell's width (v42: 15 -> 20, four big knobs a tab)
CELL_H = 17                     # its height: KNOB_BOX of encoder + 3 of label
KNOB_BOX = CELL_H - 3           # the encoder's box: CELL wide, KNOB_BOX high
KNOB_UNITS = 12                 # (v57: 14 -> 12, the rows crowded the tray: about 1 unit to the header line, 4 between knobs; now 2 and 6) (v41: 10 -> 12, taller knobs filling their box) the encoder's diameter (centred in its box; v37: 11 -> 10, they were big)
KNOB_DY = KNOB_BOX - KNOB_UNITS   # (v57) the encoder sits at the bottom of its box, on its caption as at 14; the spare room above
assert KNOB_DY >= 0
ROWS = (11, 28)                 # (v44: a unit higher) (v41: one lower, under the taller header) the two knob rows (top of the cells)
# (the name plate, PLATE_RECT: under the control groups' trays, v48)
# pieces of the panel art (x, y, w, h): they overlap, so a small scale error leaves no gap
DECO_PIECES = {"body_l": (2, 0, 80, PANEL_H), "body_r": (80, 0, PANEL_W - 82, PANEL_H),
               "cheek_l": (0, 0, 4, PANEL_H), "cheek_r": (PANEL_W - 4, 0, 4, PANEL_H)}
# switch groups (native button groups covered by rubber pads): name -> (w, h, labels)
PAD_GROUPS = {"view": (62, 6, ("MASTER", "PITCH", "AMP", "CLICK", "FX")), "sync": (22, 6, ("TIME", "SYNC")),
              "scale": (14, 6, ("LIN", "dB")), "keytrack": (6, 6, ("FIX", "KEY")),
              "clickedit": (16, 6, ("PITCH", "AMP")),   # (v70) the click tab's curve shown on the screen   # (v58: one pad showing FIX or KEY; v39-v57 a FIX | KEY pair, 13 wide)
             
              "panel": (6, 3, ("DARK", "LIGHT"))}   # (v45: the view switch 51 -> 62 wide, over the whole header; the theme switch small, at the plate)   # (v41: 5 -> 6 high)
# where each switch group sits (x, y of the native group): view and length mode in the header,
# amp scale in the right cell of the second knob row (centred on the encoder), keytrack in the
# master tab's header after the tune (v39; FIX: the tune as set, KEY: it follows the played key)
PAD_AT = {"view": (VIEW_RECT[0] + 1, HEADER_Y), "sync": (TAB2_X + 7, HEADER_Y),   # (v46: 22 wide, its pads 10 as the view switch's; v45: 30)
         
          "scale": (TAB2_X + CELL + 2, ROWS[1] + 4), "keytrack": (TAB_X + 34, HEADER_Y),
          "clickedit": (TAB_X, HEADER_Y),   # (v70: at the header's left end, the noise's screen after it)   # (v58: 27 -> 34, at the header's right end, after the wider fader)
         
          "panel": (TAB_X - 2, 48)}   # (v48: under the tray's left edge)   # (v45: under the tab tray, left of the name plate, on every tab; v40-v44 in the header, master tab only)
# the wells a switch group's pads sit in (v41), in the group's own units (0 .. w): the view switch
# in three, MASTER | PITCH AMP CLICK | FX. The native buttons under them stay one row of equal
# parts: each pad stays over its own button (the end pads are narrower, at the outer ends).
# (v46) every pad in its own well, PAD_GAP apart, GROUP_GAP between the view switch's sets, all
# the pads of a switch as wide; each stays over its own native button (equal parts of the group)
PAD_GAP, GROUP_GAP = 2.0, 4.0
PAD_SETS = {"view": [[0], [1, 2, 3], [4]]}


def pad_wells(group):
    w, h, labels = PAD_GROUPS[group]
    n = len(labels)
    if group in PAD_SINGLE:   # one pad (v42), its legend the state's
        return [(0.0, w, [0])]
    sets = PAD_SETS.get(group, [list(range(n))])
    first = {s[0] for s in sets}
    pw = (w - PAD_GAP * (n - len(sets)) - GROUP_GAP * (len(sets) - 1)) / n
    wells, x = [], 0.0
    for k in range(n):
        if k:
            x += GROUP_GAP if k in first else PAD_GAP
        assert k * w / n - 1e-6 <= x and x + pw <= (k + 1) * w / n + 1e-6, (group, k)
        wells.append((x, x + pw, [k]))
        x += pw
    return wells


# one pad, not a pair (v42): the theme switch shows the theme it is in, lit; each press turns it
# over (build_kick.theme_toggle: the native pair moves so the other theme's button is under it)
PAD_SINGLE = {"panel", "keytrack"}   # (v58: keytrack too)
# the theme switch's native pair (x, y, w, h, vertical) for each theme, and the panel art laid over
# the half that is off the pad (it takes the press too, and changes nothing: that theme is on)
# (v45: side by side, the pair's off half to the left (dark) or right (light); v42-v44 upright)
_PX, _PY = PAD_AT["panel"]
_PW, _PH = PAD_GROUPS["panel"][:2]
# (v48: the pair's halves _TH wide, a unit narrower than the pad each side: the off half stays clear
# of the screen's display; v45-v47 as wide as the pad)
_TH = _PW - 2
# (v50) Bitwig draws a button group at least about 5 units high, from its cell's top: at 3 high it
# ran to the panel's bottom, a grey and red strip under the pad (seen in Bitwig, v45-v49). The pair
# is the pad's image's height (the cell grown by 1), and the covers reach the panel's bottom.
# (v68) the pair a unit lower (its top edge inside the pad's image, its bottom the panel's) and the
# pad's image widened over the whole pair and a unit past it (TOGGLE_IMAGE, the pad on the panel
# art): every edge of the native buttons lies under one opaque image. v50-v67: the pad's image and
# three covers met exactly on the buttons' edges, and Bitwig showed those edges as thin lines round
# the LIGHT pad and across the name plate
TOGGLE_AT = {0: (_PX + 1 - _TH, _PY, 2 * _TH, PANEL_H - _PY), 1: (_PX + 1, _PY, 2 * _TH, PANEL_H - _PY)}
TOGGLE_IMAGE = (_PX - _TH, _PY - 1, 2 * _TH + _PW - 2 + 4, PANEL_H - _PY + 1)
TOGGLE_COVERS = {}
assert TOGGLE_IMAGE[0] < TOGGLE_AT[0][0] and TOGGLE_IMAGE[0] + TOGGLE_IMAGE[2] > sum(TOGGLE_AT[1][::2])
assert TOGGLE_IMAGE[1] < TOGGLE_AT[0][1] and TOGGLE_IMAGE[1] + TOGGLE_IMAGE[3] == PANEL_H
assert TOGGLE_AT[0][0] >= VIEW_RECT[0] + VIEW_RECT[2]   # (clear of the screen's display)
# (v40: MASTER first in the view switch; the panel's DARK / LIGHT switch at the header's right
# end, shown in the master tab: LIGHT, a white faceplate; the screen, knobs and pads unchanged)
# the tune fader in the header (the native slider's cell, x y w h), between the TUNE label and the
# note: one notch per semitone (C0 .. C1), the silicone cap drawn at each notch
# (v39: in the master tab's header; v36-v38 in the header between the view switch and the tab's
# controls; before, the global column's header): the label, the fader, the note
TUNE_X = TAB_X
TUNE_LABEL_W, TUNE_NOTE_W = 6, 8
FADER_RECT = (TUNE_X + TUNE_LABEL_W, HEADER_Y - 1, 18, HEADER_H + 2)   # (v62: its art a unit taller each side, as the pads' images: the fader as tall as the FIX pad, 6.3) (v58: 12 -> 18, in the room of the keytrack pair's second pad; v43: 14 -> 12 wide)
FADER_STEPS = 13
FADER_CAP_W = 2.8                 # (v59: 2.2 -> 2.8, the fader thicker) the cap's width; its travel leaves FADER_CAP_W / 2 + 0.35 each end


def fader_x(k):
    """Centre of notch k (0 .. FADER_STEPS - 1), in grid units from the fader cell's left."""
    lo = FADER_CAP_W / 2 + 0.35
    return lo + (FADER_RECT[2] - 2 * lo) * k / (FADER_STEPS - 1)
# the control groups' trays (outer x y w h), each in a frame like the screen's (v38; v32-v37 a
# lower, plainer moulding): the header (the view switch) and the tab's controls (v39: the global
# column's tray went, its controls into the master tab)
_SX0, _SX1 = VIEW_RECT[0] - FRAME, VIEW_RECT[0] + VIEW_RECT[2] + FRAME   # the screen frame's sides
# (v48, one rule) MARGIN from the cheeks (and the panel's bottom), GAP between the blocks: the
# tray's sides follow from them (v38-v47 from TAB_X, 2.5 from the right cheek, 1.8 from the screen);
# the knob grid stays centred in it (within 0.1)
MARGIN, GAP = _SX0 - CHEEK, 0.8
_TOP = 1.5
_TX0, _TX1 = _SX1 + GAP, PANEL_W - CHEEK - MARGIN
_TRAY_B = ROWS[1] + CELL_H + 0.1 + FRAME     # (v48: 0.3 -> 0.1 under the last row: GAP to the plate)
GROUP_RECTS = {"header": (_SX0, _TOP, _SX1 - _SX0, HEADER_Y + HEADER_H + 0.8 + FRAME - _TOP),
               "tab": (_TX0, _TOP, _TX1 - _TX0, _TRAY_B - _TOP)}
assert abs((_TX0 + _TX1) / 2 - (TAB2_X + CELL)) <= 0.15
# the name plate (drawn half a unit in at each end), in the row under the tray: from GAP past the
# theme switch's rim to the tray's right side as far in as the switch's rim is from its left; its
# top GAP under the tray, its bottom level with the screen frame's (v44-v47 placed by hand)
_RIM_IN = _PX - 0.55 - _TX0
_PLATE_Y = _TRAY_B + GAP
_PLATE_X = _PX + _PW + 0.55 + GAP - 0.5
PLATE_RECT = (_PLATE_X, _PLATE_Y, _TX1 - _RIM_IN + 0.5 - _PLATE_X, _SX0 + VIEW_RECT[1] + VIEW_RECT[3] + FRAME - _SX0 - _PLATE_Y)
# (v34's detail pane: the curve's first 1/DETAIL; its drawings stay, unused, for the saved presets)
DETAIL = 4
# the curve editors show the curves' x from 0 to X_END (v37; before, to 1): the line Bitwig draws
# from a cycle curve's last point (x = 1) back to its first, up the right edge, is then cut off
X_END = 0.99
# the LED colour of a switch's lit pad, per group (default PAD_LIT): the view switch's pads light in
# their curve's colour (pitch: orchid, as the purple pitch curve; amp: azure, as the blue amp
# curve; click: rose, as the click's waveform)
PAD_COLOURS = {"view": (PALETTE["violet"], PALETTE["orchid"], PALETTE["azure"], PALETTE["rose"], PALETTE["indigo"]),
               "clickedit": (PALETTE["orchid"], PALETTE["azure"])}   # (v70: as the pitch and amp curves)

# (v58) keytrack as one pad (FIX or KEY, lit), each press turns it over, as the theme switch: a
# native pair (FIX | KEY) placed for each state so that the other state's button is under the pad;
# its other half off the pad: under the note's screen and a cover (FIX), or a cover (KEY)
_KX, _KY = PAD_AT["keytrack"]
_KW, _KH = PAD_GROUPS["keytrack"][:2]
_KT = _KW - 2
KEY_TOGGLE_AT = {0: (_KX + 1 - _KT, _KY, 2 * _KT, _KH), 1: (_KX + 1, _KY, 2 * _KT, _KH)}
KEY_COVERS = {"cover_key_left": (_KX - 2, _KY - 1, 1, _KH + 2), "cover_key_right": (_KX + _KW + 1, _KY - 1, 2 * _KT - _KW, _KH + 2)}
assert KEY_TOGGLE_AT[1][0] + KEY_TOGGLE_AT[1][2] == KEY_COVERS["cover_key_right"][0] + KEY_COVERS["cover_key_right"][2]



# the mini LED screens (v37): segment displays in a framed window, one image per value
# (knobs/make_panel_svgs.py): the tune's note beside the fader, and the length's note value under
# its selector knob (Sync), in place of the "Length" label. Cells x y w h.
NOTE_RECT = (FADER_RECT[0] + FADER_RECT[2], HEADER_Y - 1, TUNE_NOTE_W, HEADER_H + 2)   # (v62: as the fader and the pads, 8 high, its window 6.3)
PAD_BODY = (0.85, HEADER_H + 0.3)   # (v62) a header pad's silicone in its image (top, height): the fader and the note screen as tall
assert NOTE_RECT[0] + NOTE_RECT[2] == _KX - 2 and KEY_TOGGLE_AT[0][0] >= NOTE_RECT[0]   # (the FIX half under the screen)
DIV_RECT = (TAB2_X, ROWS[0] + KNOB_BOX, CELL, 3)
# (v39: per art; the master tab's length, the amp length, is in its first column)
DIV_AT = {"pitch": DIV_RECT, "amp": DIV_RECT, "global": DIV_RECT}   # (v40: the master tab's grid is 2 x 2 too)
# and the click's noise, in the click tab's header (over its native chooser: a click on the screen
# opens the list)
NOISE_RECT = (TAB_X + 18, HEADER_Y - 1, COL_W - 17, HEADER_H + 2)   # (v70: after the PITCH | AMP pads, to the header's right end as the FIX pad; v64-v69 at TAB_X + 4, 32 wide)   # (v64: framed as the note's screen, as tall as the pads: 8 high, its window 6.3)
NOISE_NAMES = ["WHITE NOISE", "PINK NOISE", "BROWN NOISE", "BLUE NOISE", "VIOLET NOISE", "CRACKLE",
               "909 HAT", "GREY NOISE", "808 HAT", "606 HAT"]   # (v62: IMPULSE -> 909 HAT, 808 HAT added)
LCD_COLOURS = {"note": PAD_LIT, "pitch": PALETTE["orchid"], "amp": PALETTE["azure"], "click": PALETTE["rose"],
               "global": PALETTE["violet"], "fx_on": PALETTE["violet"], "fx_off": (0.42, 0.40, 0.56)}
DIV_NAMES = ["1/64", "1/32T", "1/32", "1/16T", "1/16", "1/8T", "1/16D", "1/8", "1/4T", "1/8D",
             "1/4", "1/2T", "1/4D", "1/2", "1/2D", "1BAR"]
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DETENTS = len(DIV_NAMES)        # the note value's selector: a notch per value

# v39: the controls' titles (under the knobs, the pads) printed in the pads' legend font, size and
# grey, as images (Bitwig's own labels were in another font, and larger). text -> image name
CAPTIONS = ["Length", "Pitch", "Time", "Scale", "Velocity", "Click", "Decay", "Tone", "Low Cut",
            "Phase", "Drive", "Level", "Tune", "Comp", "Low", "Mid", "High", "EQ", "Delay"]   # (v60: Mid Drive went: the drive is "Drive")
CAPTION_SIZE = 1.46             # (v52: 1.22 -> 1.46, with the pads' legends 1.84 -> 2.2) the em of the pads' legends as rendered (measured on the mock)
LEGEND_GREY = (196, 196, 202)   # sRGB: the controls' titles on the dark panel (v57: 128 -> 196, the panel lighter)


def caption_name(text):
    return "cap_" + text.lower().replace(" ", "_")


# the FX tab's on / off (v49): a mini LED screen in the tab's header, FX ON (lit) or FX OFF (dim),
# each press turns it over: under it a native pair (OFF | ON) placed for each state so that the
# other state's button is under the screen, its other half off the screen under a piece of the
# panel art (FX_COVERS), as the theme switch
FX_RECT = (TAB2_X + 8, HEADER_Y - 1, 20, HEADER_H + 2)   # (v64: as the note's screen, 8 high; the native pair stays in the header row)
FX_NAMES = ["FX OFF", "FX ON"]
_FX0, _FXW, _FH = FX_RECT[0], FX_RECT[2], 14
FX_TOGGLE_AT = {0: (_FX0 + 3 - _FH, HEADER_Y, 2 * _FH, HEADER_H), 1: (_FX0 + 3, HEADER_Y, 2 * _FH, HEADER_H)}
FX_COVERS = {"cover_fx_left": (_FX0 + 3 - _FH, HEADER_Y, _FH - 3, HEADER_H),
             "cover_fx_right": (_FX0 + _FXW, HEADER_Y, _FH - 3, HEADER_H)}
assert abs(_FX0 + _FXW / 2 - (TAB2_X + CELL)) < 0.01   # centred over the knob grid
assert FX_TOGGLE_AT[0][0] >= GROUP_RECTS["tab"][0] + FRAME and FX_TOGGLE_AT[1][0] + 2 * _FH <= GROUP_RECTS["tab"][0] + GROUP_RECTS["tab"][2] - FRAME


# (v60) the FX tab: Drive | Comp on the first row (big encoders); under them, across the tray, the
# EQ's frame with three encoders 10 across (v58-v59: 6 across in a frame beside the mid drive:
# Bitwig draws a native knob at least about 6.5 units across, it showed round them), the frame's
# title in a gap of its top rim. The chain: Drive, EQ, Comp.
EQ_RECT = (TAB2_X - 3, ROWS[1] + 1, 42, 16)        # (75, 29, 42, 16), centred on the tray (96)
EQ_UNITS = 10                   # the EQ encoders' diameter
EQ_BOX = (14, 10)               # an EQ encoder's box (its SVG), the encoder centred across it, at its top
EQ_KNOBS = [(EQ_RECT[0] + k * EQ_BOX[0], EQ_RECT[1] + 2) for k in range(3)]   # boxes' top left
EQ_NATIVE = 6                   # the native knob under one (square, centred on the encoder)
EQ_TITLE = (EQ_RECT[0] + EQ_BOX[0], EQ_RECT[1] - 1, EQ_BOX[0], 3)   # centred on the frame's top rim
EQ_TITLE_GAP = 4.6              # the gap cut in the top rim for it
EQ_CAPTIONS = [(x, y + EQ_BOX[1], EQ_BOX[0], 3) for x, y in EQ_KNOBS]
assert abs(EQ_RECT[0] + EQ_RECT[2] / 2 - (TAB2_X + CELL)) < 1e-9 and 3 * EQ_BOX[0] == EQ_RECT[2]
assert EQ_RECT[0] >= GROUP_RECTS["tab"][0] + FRAME and EQ_RECT[0] + EQ_RECT[2] <= GROUP_RECTS["tab"][0] + GROUP_RECTS["tab"][2] - FRAME
assert EQ_RECT[1] + EQ_RECT[3] <= GROUP_RECTS["tab"][1] + GROUP_RECTS["tab"][3] - FRAME + 0.2
assert EQ_CAPTIONS[0][1] + 3 <= EQ_RECT[1] + EQ_RECT[3] - 1
# (a caption's cell when not the knobs' CELL x 3)
# (v73) the click tab's five knobs, EQ-sized (the EQ's art, knobs/out/eq): Level | Delay | Length
# across the tray as the EQ's three, Tone | Low Cut centred under them; captions CELL wide
# (the other knobs' caption images), centred under each box
CLICK_ROWS = (13, 30)           # the two rows' boxes' top (the noise's screen ends at 11, the tray's inside at 45)
CLICK_KNOBS = [(EQ_RECT[0] + k * EQ_BOX[0], CLICK_ROWS[0]) for k in range(3)] + \
              [(EQ_RECT[0] + EQ_BOX[0] // 2 + k * EQ_BOX[0], CLICK_ROWS[1]) for k in range(2)]
CLICK_CAPTIONS = [(x - (CELL - EQ_BOX[0]) // 2, y + EQ_BOX[1], CELL, 3) for x, y in CLICK_KNOBS]
assert CLICK_ROWS[0] >= NOISE_RECT[1] + NOISE_RECT[3] + 2 and CLICK_ROWS[0] + EQ_BOX[1] + 3 <= CLICK_ROWS[1] - 3
assert CLICK_ROWS[1] + EQ_BOX[1] + 3 <= GROUP_RECTS["tab"][1] + GROUP_RECTS["tab"][3] - FRAME
assert abs(CLICK_KNOBS[3][0] + EQ_BOX[0] - (TAB2_X + CELL)) < 1e-9   # the second row centred on the tray

CAPTION_CELLS = {"Tune": (TUNE_LABEL_W, HEADER_H), "Low": EQ_CAPTIONS[0][2:], "Mid": EQ_CAPTIONS[1][2:],
                 "High": EQ_CAPTIONS[2][2:], "EQ": EQ_TITLE[2:]}
