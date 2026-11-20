# KickForge panel art (Blender)

Everything the panel shows that is not a native Bitwig control is rendered in Blender (Cycles,
CPU) and placed as SVG images (`image_panel_item`). Colours and the panel layout live in one
place, `kick/theme.py`, read by the renders, the waveform shader and `build_kick.py`.

## Knobs

Each knob is a 3D LED-ring encoder drawn over Bitwig's native knob. The native knob stays
underneath, invisible, and still handles the mouse, the value and automation. Since Bitwig only
shows still images, the moving parts are separate images that panel expressions show or hide
according to the value:

| Image | Count | Shown when |
| --- | --- | --- |
| `base_<colour>` (bezel, LEDs off, soft-touch silicone grip, alu cap without its pointer, shadow) | 1 per knob | always |
| `led_<colour>_<i>` (the light LED i adds: lens, channel, bezel) | 15 | the pointer has reached LED i |
| `ptr_<k>` (white pointer) | 71 | the value is closest to position k (every LED and 4 points between two, 3.9 degrees apart; v32's 29, 10 degrees apart, made turning a knob feel notched) |

Each LED is rendered over the whole scene in a box round it, and the base is subtracted, so its
light on the channel and the bezel comes with it. The knob's title moves under the encoder
(`PanelBuilder.encoder` in `build_kick.py`), printed as an image in the pads' legend font, size
and grey (`theme.CAPTIONS`, `cap_<title>`, made by `make_panel_svgs.py`; v39: before, Bitwig's
own label, in another font and larger). The encoder is 10 units across
(`theme.KNOB_UNITS`; 11 up to v36, large beside the pads). Its grip is the pads' silicone
(`theme.RUBBER`, the same sheen, translucency and stippled skin at the same size in grid units;
v38: before, a finer, four times shallower stipple that read as plastic), and the spun-aluminium
cap is smaller (v38: radius 0.33 of the art's half size, was 0.47), so a ring of the grip's top
shows round it; the pointer runs across both to the grip's edge.

**Notched selector** (`out/sel/`, v37): the length's note value in Sync mode (16 values, 1/64 ..
1 bar; before, a drop-down list; v39: also the master tab's length, in its colours) is a knob too, with one LED, one pointer and a printed tick per
notch (`render_knobs.py --detents 16`), so it turns in steps. The native knob under it is bound
to the list itself (an indexed atom, as SHARD's band count). The value shows on a mini LED screen
in place of the label.

## Switches and panel

- **Silicone pads** (`pads_<group>_<k>`): each native button group (`theme.PAD_GROUPS`, placed at
  `theme.PAD_AT`) is covered by silicone blocks (velvet sheen, stippled skin brought out by a
  grazing light, round-shouldered top) in a recessed well, seen from a little in front
  (`PAD_TILT`, as the knobs) so their sides show; one image per lit pad, shown while the value is
  that pad's. The legend is a translucent inlay on the top, rendered with the pad (v35; before, it
  was printed on afterwards): the lit pad's LED shows through its legend and its sides only, and
  lights the well round its foot; an unlit legend is a pale grey. The LED is `theme.PAD_LIT`, but
  the view pads take their curve's colour (`theme.PAD_COLOURS`, v36: pitch orchid, amp azure,
  click rose; v39: master violet). Keytrack is FIX / KEY, in the master tab's header. One render set per group, as the legends differ. The camera leans 12 degrees and
  aims at the pads' mid-height (v36; v35's 25 degrees cut the tops off and looked odd). The pads
  are 5 units high (v37; 4 before, small beside the knobs), their legends the size they were.
- **Tune fader** (`fader_<k>`, `theme.FADER_RECT`): in the master tab's header (v39; v36-v38
  in the header between the view pads and the tab's pads; before, in the global column), "TUNE"
  before it in the pads' legend font and grey (an image shown with the tab, v39; v37-v38 printed
  on the panel), the note on a mini LED screen after it. The cap keeps its height (3.6 units) in the taller header. Over the native slider, a brushed-aluminium rail
  with the slot cut through it and a scallop cut into both edges of the slot at each semitone
  (C0 .. C1: 13 detents; v31-v34: grey tick bars), C0, F# and C1 marked by a dot, and the silicone
  cap (as the pads) with a lit indigo line; one opaque image per notch, shown while the value is
  that notch's. The cap's shadow is rendered on a shadow catcher.
- **Panel** (`deco_<piece>`): a satin faceplate, an arcade-cabinet frame round the curve view (a
  raised moulding, a chamfer down to a glossy step, a screw in each corner), walnut end cheeks with
  screws, silver inlay lines between the columns and a brushed-aluminium name
  plate (engraved KICKFORGE, KICK DRUM SYNTHESIZER and, v39, "by MindB") (the grain in two scales, a sheen across it from a soft light that lights the plate only,
  by light linking). (The chrome inlay round the screen went in v29.)
- **Glass** (`glass_view`, made by `make_panel_svgs.py`): over the curve view, above the curve (an
  image takes no clicks): the bezel's shadow on the recessed screen, a faint diagonal reflection, a
  bulge highlight top right, rounded corners; the middle stays clear. (v30's curved CRT glass was
  dropped in v32: back to this one.) The faceplate is lit by one large soft light (v30; v29's narrow
  "sheen" light left a hard-edged streak on the right) under a thinner clear coat.
- **Compartments** (`theme.GROUP_RECTS`, v38): the header (view pads) and the tab's controls
  (v39: one tray of three columns, 136 x 61 units: the global column went into the master tab;
  the other tabs' 2 x 2 grid is centred in it) each sit in a tray framed exactly as the screen (`render_panel_art
  .arcade_frame`: the raised satin moulding with its broad chamfer, the glossy black lip, a screw
  in each corner) round a matte floor; a silver line under the tab tray's header. The panel grew
  to 158 x 61 units (146 x 53) so that the compartments stand about 2 units apart and from the
  edges (v32-v37: lower, plainer mouldings, nearly touching). The frames are hollowed by booleans,
  the moulding cut out under the lip: cut at the lip's outer edge, its 0.5 chamfer on both edges of
  a ring that narrow folded its top across the hole, a black lid over the tray (v38 first render).
  It is one render cut into overlapping pieces (`theme.DECO_PIECES`), so a small scale error
  leaves no gap.

- **Mini LED screens** (`lcd_*`, v37): a window like the pads' wells (a chrome rim, a black
  moulding, a recessed smoked glass; `render_panel_art.py --what screens`) with the value in
  14-segment characters (`make_panel_svgs.py`): the lit segments hot at the core with a glow, the
  unlit ones faintly visible, a soft reflection on the glass. One opaque image per value, shown by
  a panel expression: the tune's note (`lcd_note_<k>`, indigo; v27-v36 the shader drew it), the
  length's note value (`lcd_div_<tab>_<i>`, the tab's colour) and the click's noise
  (`lcd_noise_<i>`, rose). The noise screen covers the native chooser: a click on it opens the
  list.

## Commands (from `kick/`)

| Step | Command |
| --- | --- |
| Knobs (about 6 min) | `blender -b -P knobs/render_knobs.py -- --size 512 --samples 64` (`--only-pointers`: the pointers, 2 min) |
| Panel and pads (about 3 min) | `blender -b -P knobs/render_panel_art.py -- --what deco` then `-- --what pads` |
| Tune fader (10 s) | `blender -b -P knobs/render_panel_art.py -- --what fader --scale 24 --samples 64` |
| LED screen windows (10 s) | `blender -b -P knobs/render_panel_art.py -- --what screens --scale 30 --samples 64` |
| Notched selector (40 s per colour) | `blender -b -P knobs/render_knobs.py -- --size 512 --samples 64 --detents 16 --colours pitch,amp,global --out knobs/render/sel` |
| Knob SVGs | `python3 knobs/make_knob_svgs.py` (`--px 40` = `theme.KNOB_UNITS` grid units, `--embed 4`), then `--src knobs/render/sel --out knobs/out/sel` |
| Panel SVGs | `python3 knobs/make_panel_svgs.py` (after `make_knob_svgs.py`: that one clears `out/`) |
| Build | `~/Patchbay/bitwig-devices-blueprint/.venv/bin/python build_kick.py --out build/KickForge-vNN.bwdevice` |
| Build without the art | add `--no-knob-art` |

- **Scale**: Bitwig draws 4.0 SVG px per panel grid unit (`theme.PX_PER_UNIT`, measured on the v23
  screenshot). An image is drawn at its own size and, when it is larger than its cell, hangs from
  the cell's top left corner instead of being centred. So every SVG is made exactly its cell's size:
  the encoders are `theme.CELL` x `theme.KNOB_BOX` units (60 x 48 px) with the 40 px encoder centred
  in them, and the panel pieces and pads are their cells times 4.0.
- **Palette** (`theme.PALETTE`): cyan, azure, indigo, violet, orchid, rose. Knob sweeps: amp cyan to
  azure, global indigo to violet, pitch violet to orchid, click orchid to rose. The curve lines use
  Bitwig's display colours (pitch purple, amp blue); the waveforms run from the attack's colour to
  the tail's (`theme.WAVE`).
- **SVGs**: Bitwig reads them with Batik (SVG 1.1), so `<image>` needs `xlink:href`; a plain
  `href` is rejected.
- **Previews**: `out/preview.png` (each knob colour at 0, 30, 62 and 100 %),
  `out/preview_actual_size_x3.png`, `out/panel_preview.png` (panel and pads).

## Waveform drawings, presets and saved projects

A drawing's shader (class 5512) is device state: a project or preset saves it (class 5516, under
the drawing's preset id) and loading one takes it from there. Only a fresh insert uses the
device's own shader:

| The project or preset holds, under the drawing's id | The drawing gets |
| --- | --- |
| a shader | that shader, even an old one (v23 drew v22's amber waveform) or an empty one |
| nothing (another or no id: v24's renamed ids, v25-v26's empty ids) | an empty shader: nothing drawn ("missing 'main' function" in `~/.BitwigStudio/log/BitwigStudio.log`) |

So the ids stay `WAVE_PITCH`, `WAVE_AMP`, `WAVE_CLICK`, `WAVE_TUNE` for good, and after a shader
change the presets are brought up to date with `tools/repair_presets.py` (from `kick/`, after
installing): a dry run lists the changes, `--apply` makes them, copying each preset first to
`../preset-backups/<time>/`. It also sets the kind of the curves saved in the presets to the
device's (CYCLE. v27 tried ENVELOPE, to drop the editor's line from the last point back to the
first, and the body went silent: those curves do not read the phase input the same way).

## Native controls under the art

- The native knob draws a value ring as large as its cell, so it is shrunk to 6 x 7 units, centred
  under the encoder, where the base is fully opaque (v37; 7 x 8 under the 44 px encoder).
- The pad images are opaque (the panel art of their cell is baked in), so nothing of the native
  button group, such as its red selection line, shows through the soft edge of the well.
- The maximized view is the curve alone, stretched over the whole window, as Compressor+'s (v33,
  v37). Only a plain display stretches with the window, and a plain display cannot zoom; a
  zoomable one keeps the size it is made with, about 125 units high however it is laid out
  (v26-v32; v36 had it so, a band across the window). The zoom stays in the device view. (v35 had
  a strip repeating the device's controls under the curve: not wanted.) (v34's detail pane went in v35; its drawings
  `WAVE_*_DETAIL` stay, unused, so saved presets and projects keep matching the device.)
- The Tune fader's native slider is inset by a unit under its image: at the image's size its
  orange frame showed round the fader (v31-v32).

## Live waveform

While idle, the phase core (`kick_phase.nitro`) sweeps 11 points across both curves, at x =
(k/10)^2 on each (denser near the start); the displays pack them for the shader. The curve atoms
answer per block (512 samples) and may be a block late, so each point is held 768 samples and
read from 640 on, the first of a sweep (after the last, the most different) twice as long: a full
refresh in about 0.19 s at 48 kHz.

Since v39 the points are taken on the curves, not in time: the shader puts them in time with the
lengths and time scales of the moment (the frequency integrates exactly between points: it is
log-linear in x and dt/dx = length L/k e^(xL)). With v38's live tune, pitch amount and amp scale,
turning Length, Time, Tune, Pitch or Lin/dB redraws at once. Up to v38 the points were taken at
(k/10)^2 of the shown tab's length in time, so the lengths and time scales moved them and each
turn redrew the waveform point by point over a sweep, in jolts. Still redrawn over a sweep: an
edited curve, and the pitch Scale (the points carry the shaped value: as a raw value 8 bits were
far too coarse near the bottom of a strongly scaled curve).

The shader has three four-float inputs (`audioLow`, `audioMedium`, `audioHigh`: Bitwig gives no
more), each float an exact 24-bit word: the 22 points, the playhead and every setting fill them to
the bit (`kick_display.nitro.in` lists the fields). The master tab's oscilloscope has its own
display, which sends the drive in place of the playhead.

**Master** (v39): the whole kick, evenly in time, as an oscilloscope: body and click summed, after
the drive (the mid saturator is not drawn).

**Phase** (v39): the offset fades in as the pitch lands on the fundamental and only once the click
is over (five times its decay; 2 ms after an impulse), in the voice and in the drawing, so the body
under the click, and the click's blend with it, never change with the Phase.

The curve editors show x from 0 to `theme.X_END` (0.99, v37), and the waveform follows: Bitwig
draws a cycle curve with a line from its last point (x = 1) back to its first, a vertical up the
right edge, now out of view with the end point (which is never moved).

The waveform's glow reaches out in proportion to the view's size (v37): the reach made for the
maximized view smeared the wave in the small device view.

The envelope drawn over the waveform between those 11 points is a monotone cubic (Hermite,
tangents flattened where the curve turns, clamped between the two points), so it no longer breaks
into straight segments and never overshoots. The outline round the waveform (fill, rim, halo) went
in v30: its straight segments and corners did not follow the waveform.

The waveform's labels (the divisions along the top, the pitch view's frequencies) are drawn by the
shader in a monoline stroke font, anti-aliased, 1.4 to 2 pixels per font unit (v35; before, a
3x5 pixel font scaled by 1 to 3 whole pixels: big and blocky). A division's label is centred on
its line and drawn over the waveform; the frequencies sit at the right edge (on the left they ran
over the attack and its points).

## v40: white panel, FX tab, trims

- **Tabs**: MASTER, PITCH, AMP, CLICK, FX (VIEW 0..4; the length modes read `VIEW + 5 * X_SYNC`).
  The master tab is a 2 x 2 grid (Length | Phase, Click | Level); the FX tab one row at `theme.FX_Y`
  (Comp | Drive | Mid Drive). The master oscilloscope shows in both (`SHOW["scope"]`).
- **Panel finish** (`PANEL`, the DARK / LIGHT pads in the master tab's header): the white panel is
  a second deco render, `blender -b -P knobs/render_panel_art.py -- --what deco --look light`
  (`deco_light.exr`, paint `theme.PANEL_LIGHT`, silver rims and trims). `make_panel_svgs.py` brightens
  it by `theme.LIGHT_EXPOSURE` (a vivid white), keeps the walnut as rendered, and makes every image
  laid over the panel art twice (`<name>_light`: pads, fader, LED screens, titles in
  `theme.LEGEND_DARK`). `PanelBuilder.add` puts such an image in twice, shown with `PANEL == 0` / `1`.
  The screen, knobs and pads themselves are the same on both.
- **Trims**: frame rims are brushed anodised metal with crisp chamfers; engraved separators
  (`groove()`: a dark channel, its lower or right wall lit) under the tab tray's header and between
  the tab switches and the panel switch (`theme.SEPARATOR_X`); brushed trims along the top and bottom.
- **Shader decode**: words are read with `floor(x * 2^24 + 0.25)`; with `+ 0.5`, an odd word from
  2^23 up rounded to even (one too many), which carried a byte of 255 into its neighbour.

## v41: bigger, taller controls

- **Knobs**: 12 units (`theme.KNOB_UNITS`, filling the 12-high box), a taller knurled grip
  (`SKIRT_H` 0.44) on a chamfered flange (`FLANGE_R`), seen from 24 degrees; the key light a little
  lower for a longer shadow. Own shapes: VCV Rack's component graphics are CC BY-NC 4.0 (no use in a
  product sold outside the VCV Library) and Analog Obsession's art is theirs, so neither is used.
- **Pads**: 6 high (`HEADER_H` 6, the rows one lower, the plate 13 high), taller keys
  (`PAD_TOP` 1.6) seen from 16 degrees. `theme.pad_wells(group)` sets the wells: the view switch in
  three, MASTER | PITCH AMP CLICK | FX, over the one native row of five equal buttons.
- **Scope** (master / FX): drawn as the body in the other views, a neon tube with a white-hot core,
  a halo, a lit fill to the axis and a glint on the crests.

## v42: one angle

Every control is seen from `theme.VIEW_TILT` (12 degrees): the knobs and selectors
(`render_knobs.TILT`), the pads (`PAD_TILT`) and the tune fader, each camera aimed at the panel's
plane, so the controls' feet sit where the top-down panel art has them and only their tops lean.
(v41: knobs 24, pads 16, the fader straight from above: out of line with each other.)
- **Bigger knobs** (v42): cells 20 x 19 (`theme.CELL`, `CELL_H`), encoders 16 units in a 16-high box
  (`KNOB_UNITS`, `KNOB_BOX`), the native knob 9 x 10 under them; the panel 68 high (the screen 50,
  the plate 12); every tab a 2 x 2 grid (FX: Comp | Drive, Mid Drive centred under them).
- **Theme switch** (v42): one pad showing the theme it is in, lit (`theme.PAD_SINGLE`); each press
  turns it over. Under it a native pair of buttons, upright, placed per theme
  (`theme.TOGGLE_AT`) so the other theme's button is under the pad; the half off the pad lies
  under panel art (`TOGGLE_COVERS`, crops of the deco), and pressing it changes nothing.
- **Scope core** (v42): the distance to the line through the pixel's ends, across it (as the body),
  so the master / FX trace is anti-aliased; the click's noise span stays lit where it is loud.

## v43: 61 high, 124 wide

Bitwig fits a device panel to the device chain's height: the taller the panel in grid units, the
smaller every unit draws. At 68 high (v42) the pads, titles and plate went small and the panel wide;
back to 61 high, 124 wide (the screen 64 wide), with the parts in step:

| Part | Units |
| --- | --- |
| Knob cell / encoder | 18 x 17 / 14 (`CELL`, `CELL_H`, `KNOB_UNITS`), native knob 8 x 9 |
| Pads | 6 high; tabs 51 wide in three wells, theme pad 8 |
| Tune fader | 12 wide |
| Plate | 44 x 10, its lettering scaled with its height |

## v44

- Back to Bitwig's standard chain height, 53 rows (the blueprint's PANEL002, as Normalizer and
  Growl): at 61 KickForge stood taller than the devices beside it. Still 124 wide.
- Knobs, pads, fader and screens keep their v43 sizes: the screen 43 -> 35 high, the knob rows a
  unit higher (11, 28), the name plate a slim badge under the tray (10 -> 4.4 high: the name, its
  lit line and the maker's mark, a screw at each end).

## v45

- The theme switch left the header: a small pad (6 x 3) left of the name plate, on every tab
  (v42-v44: in the header, the master tab only). Its native pair lies side by side, the off half
  to the left (dark) or right (light) under a piece of the panel art. The plate is 34 wide.
- The view switch fills the header (51 -> 62 wide); TIME and SYNC are two pads apart (the group
  26 -> 30 wide, a gap of 4 between their wells).

## v46

- One rule for every switch: each pad in its own well, 2 units apart, 4 between the view switch's
  sets (MASTER | PITCH AMP CLICK | FX), all the pads of a switch as wide (theme.pad_wells,
  PAD_GAP / GROUP_GAP / PAD_SETS). TIME | SYNC 22 wide, its pads 10 as the view switch's.

## v47

- The length's note-value screen (master tab, Sync) is centred under its selector: its window was
  placed for the 15 wide cells of v37-v41 (at 2.3, centred on 7.5), 1.5 units left of the 18 wide
  cells' centre; now centred on the cell's width (render_panel_art.SCREENS["div"]).

## v48

- One spacing rule (theme.MARGIN, GAP): 1.3 from the cheeks and the panel's bottom on both sides
  (v47: 1.3 left, 2.5 right; the plate 1.0 from the bottom), 0.8 between every two blocks
  (v47: 1.8 screen | tray, 0.8 header | screen, 0.6 tray | plate). The tray's sides follow from
  them (72.5 .. 119.7), the knob grid centred in it within 0.1.
- The bottom row under the tray: the theme switch under the tray's left edge, the plate from 0.8
  past it to the tray's right edge, both 0.95 in from the tray's sides, the plate's bottom level
  with the screen frame's. The switch's native halves are 4 wide (a unit in from the pad each
  side), so the dark theme's off half stays clear of the screen's display.
- The top margin stays 1.5 (1.3 would need the screen at a half unit).

## v49

- FX on / off: a mini LED screen centred in the FX tab's header, FX ON (violet) or FX OFF (dim);
  each press turns it over (a native OFF | ON pair placed for each state, the other state's
  button under the screen, its other half under panel art: theme.FX_RECT, FX_TOGGLE_AT,
  FX_COVERS). The atom FX_ON (Off, On; default On, automatable): OFF sets Comp, Drive and Mid
  Drive to 0 in the voice (their settings kept) and draws the master scope undriven. Presets
  saved before have no FX_ON and load with the FX on, as they sounded.
- The 14-segment font has an X (the four diagonals).

## v50

- The theme switch's native pair: Bitwig draws a button group at least about 5 units high, from
  its cell's top; at 3 high it ran to the panel's bottom, a grey and red strip under the pad
  (seen in Bitwig). The pair is now the pad image's height (5) and the covers reach the bottom.

## v51 (review: lighter, faster, guarded)

- Opaque images (pads, mini screens, fader, covers) in JPEG, quality 92, colour at full
  resolution, as the panel art already was: no visible difference, the device 16.8 -> 10.4 MB.
- Voice: the coefficients (pitch scale, click filters, crossover, grey noise, compressor release,
  the tune's semitones) cached, recomputed only when their parameter or the sample rate changes;
  idle (no kick, no ring-out, the band filters settled) computes nothing; an output guard turns a
  NaN or infinity into silence (filters cleared) and holds the level within +-4.
- Phase core: the warps' constants and the root cached. Display cores: the lanes worked out every
  16 samples and held (a scan point's settled window is 128 samples).
- Shader: the division labels' loop only runs in the top band (labels light nothing below 7.6 ls):
  the nine reference drawings (tools/render_wave.py) pixel-identical, rendered 2.6x faster.
- Tools: repair_presets.py writes each preset next to the original, checks it, then renames it
  over (atomic); backups keep the folder structure; links left alone; codec runs time out; the
  temporary JSON is always removed. mock_panel.py evaluates visibility expressions on their syntax
  tree instead of eval. build_kick.py's codec run times out.

## v52

- An unlit pad's legend glows too, in its own pad's colour, at 0.64 of a lit one's strength
  (render_panel_art.LEGEND_IDLE): only the legend, not the pad (v35-v51: plain grey).
- The pads' legends about a fifth bigger (at most 1.84 -> 2.2; h * 0.52, pw * 0.40), a long word
  scaled to fit the pad's top; the knobs' captions with them (theme.CAPTION_SIZE 1.22 -> 1.46),
  the same size as the pads' legends.

## v53

- Unlit pads' legends glow white (0.35 of the lit legend's strength), the lit pad's legend in its
  pad's colour (0.8 of it, strength 5 -> 6; v35-v52 near white): the tab shown reads at a glance.

## v54

- The maker's mark on the plate bigger (1.2 -> 1.65).

## v55

- Sharper mini LED screens: the glow hugging the segments tighter and fainter (0.06 -> 0.02 of
  the glass height, 0.55 -> 0.25); at Bitwig's size it blurred their edges. The wide halo kept
  (0.35 -> 0.3). (Checked first: the v51 JPEG is not the cause, 0.84 / 255 mean error.)

## v56

- Sharp pad legends: the pads' glow only from what is brighter than an unlit legend (bloom
  threshold 0.65 -> 2.4: the lit pad's LED and legend), its radii 0.6 of before (finish spread): the
  glowing white legends had a 2.6 px haze at Bitwig's size. The mini screens' segments bolder
  (0.14 -> 0.165 of the character height).

## v57 — dark panel in Bitwig's grey, smaller knobs

- Dark look: `theme.PANEL` 0.055/0.055/0.075 (blue-black) -> 0.372/0.37/0.362 sRGB, a neutral grey
  calibrated on the render: the tab tray's floor reads about 90 (Bitwig's device strip 91,91,91,
  measured on a screenshot). The satin paint's coat reflects the scene a lot, so the paint is
  not the rendered value: measure `knobs/out/panel_preview.png` after a change.
- Knob captions `LEGEND_GREY` 128 -> 196 for the lighter panel.
- Encoders `KNOB_UNITS` 14 -> 12, sat at the bottom of their box (`theme.KNOB_DY` = 2; before,
  centred) so the caption still hugs the knob; the native knob 8 x 8, centred under the art
  (`NATIVE_DY`). Gaps in grid units, before -> after: header line -> knob 1 -> 3, caption -> next
  knob 0 -> 2, knob -> knob 4 -> 6, tray walls 7.5 -> 8.5. The base's opaque disc is 40 SVG px
  across over a 32 px native ring.
- Rebuild order: render deco, `make_knob_svgs.py` (both), `make_panel_svgs.py`.

## v58 — EQ in the FX tab, keytrack as one pad, wider tune fader

- EQ (`EQ_LOW`, `EQ_MID`, `EQ_HIGH`, +-15 dB, held as dB): after the drives, before the level,
  bypassed by FX OFF. Console-style curves (RBJ biquads, TDF-II, coefficients cached): low shelf
  80 Hz and high shelf 5 kHz at Q 0.9 (about 0.5 dB of dip / bump on the other side at 15 dB), a
  400 Hz bell whose Q goes 0.6 + 0.1 |dB| (2.1 at 15 dB). A band at 0 dB is skipped once settled.
- FX tab: Mid Drive under Comp; under Drive the EQ frame (`theme.EQ_RECT`, 95,30 22 x 15,
  `--what frames`: a hollow chrome bead and moulding), its title and three small encoders
  (`theme.SMALL_UNITS` 6, art `knobs/out/small`: `make_knob_svgs.py --src knobs/render --out
  knobs/out/small --px 24 --box 6 6 --dy 0`), LEDs lit from the middle (0 dB) out to the value.
- Keytrack: one pad (`PAD_SINGLE`), FIX or KEY lit; a native pair per state (`KEY_TOGGLE_AT`),
  the off half under the note screen and `KEY_COVERS`. The tune fader 12 -> 18 wide (the note
  screen moved: re-render `--what screens`, `--what fader`, `--what pads`).

## v59 — a thicker tune fader

- The fader about 1.5 x thicker across, its length unchanged (18): rail 2.6 -> 4.0 high, slot
  0.68 -> 1.1, detent scallops 0.19 -> 0.26, cap 3.6 x 2.2 -> 4.8 x 2.8 (`theme.FADER_CAP_W`).
- The rail's ends pulled in (0.35 -> about 0.8 from the cell's edges) and the image's alpha faded
  over its last 0.35 unit (make_panel_svgs): the bigger shadows had been cut at the cell's edge, a
  grey box round the fader on the white panel.
- Keytrack (checked, unchanged): it moves only the bottom of the pitch curve, the fundamental (with
  the tune); the top of the sweep stays at G0 + Pitch, the click is untouched, the sweep in between
  follows in proportion (it lands on the new fundamental). The mid drive's crossover follows the
  fundamental (2.5 x), by design.

## v60 — FX chain Drive, EQ, Comp; the EQ across the tray

- The whole kick's drive (`DRIVE`) removed (voice and the master scope's drawing, head 0); the mid
  drive (`MID_DRIVE`, id kept for presets) is now titled "Drive". Chain: Drive (mids), EQ, Comp.
- Comp moved last: a peak follower on the whole kick after the EQ (v40-v59 on the body only,
  before the click); same law (0 .. -24 dB, 3:1, half made up, 60 ms release, reset per hit).
- EQ gains held linear (`EQ_MIN`..`EQ_MAX` = -15..+15 dB, default 1.0, `D_LOG`, unit dB): Bitwig's
  panel expressions refused negative literals ("EQ_LOW > -14.5"), so v58-v59's LED / pointer
  images on the negative side showed always, on every tab. The builder now asserts no "-" in the
  EQ's expressions; pointer edges are spaced in log (`log_pointer_ranges`). To check in Bitwig:
  the knob's middle reads 0.0 dB.
- Bitwig draws a native knob at least about 6.5 units across: the v58 4 x 4 knobs showed round the
  6-unit art. Now 10-unit EQ encoders (`knobs/out/eq`: `make_knob_svgs.py --src knobs/render --out
  knobs/out/eq --px 40 --box 14 10 --dy 0`) over 6 x 6 native knobs, in a 42 x 16 frame across
  the tray (`theme.EQ_RECT`), its title EQ in a gap of the top rim. Drive | Comp on the first row.

## v61 — click delay, symmetric cheeks

- `CLICK_DELAY` (0 .. 5 ms, the Click tab, in Level's place: the click's level stays in the master
  tab): the click starts this late; nothing of it runs before (noise, filters), so it is the same
  click whatever the delay. The Phase's fade-in waits for the delayed click's end (voice and
  scope). Phase acts on the fundamental only (after the attack), unchanged.
- The master display sends the delay as its head byte (head = delay x 200 / 0.005 ms ... q8),
  the master scope draws the click that late (`clickDelay`); the drive's drawing is off (0).
- The right cheek is the left one mirrored (make_panel_svgs): lit from the left, it rendered
  darker and flatter, looking like another shape.

## v62 — tall fader and note screen, click delay to 15 ms, 909 / 808 hats

- The tune fader and the note screen as tall as the FIX pad (`theme.PAD_BODY`: 6.3 in an 8-high
  image, a unit over the header row each side as the pads'): `FADER_RECT` / `NOTE_RECT` 8 high,
  the native slider as before (y + 2, 4 high); rail and cap 6.3, slot 1.7. The note's digits
  `text_h` 2.9 units (the glass is taller).
- Click delay 0 .. 15 ms (was 5). The click view now reads the master display (its head byte is the
  delay; no playhead in the click view): the click drawn Delay in, after the body's start, so it can
  be set on the transient by eye. The master display now precedes the drawings in the components.
- Noise types: Impulse (6) -> 909 Hat, 808 Hat added (8). Simulated: six square oscillators (808:
  205.3, 304.4, 369.6, 522.7, 540, 800 Hz, summed; 909: higher, ring-modulated pairs mixed with
  noise, cut to 6 bits), high-passed at 7 kHz, then the click's Tone, Low Cut and Decay. The
  display draws type 8 as 6 (three bits). LCD glyphs 9, 5, 7 added.

## v63 — 606 hat

- Noise type 9, 606 Hat (simulated): six squares at 245, 306, 365, 415, 437, 619 Hz, 0.7 of them
  with 0.3 white noise, through the hats' 7 kHz high-pass; drawn as the 909's (type 6).

## v64 — the header's screens framed

- The click's noise screen and the FX ON / OFF screen framed as the note's (v62): 8-high cells
  (`NOISE_RECT`, `FX_RECT` a unit over the header row each side), the rim and moulding 6.3 high
  (`theme.PAD_BODY`, as the pads), the text 2.9 units. The native chooser and the FX pair stay in
  the header row (6 high).

## v65 — the header's screens in the pads' frame

- Note, noise and FX screens framed as the pads (render_panel_art `_well`): the chrome rim and
  black well flush with the panel (0.45 / 0.55 in, as `pads()`), the glass where a pad's silicone
  is (0.85 in, 6.3 high), raised a little; the v62-v64 raised chrome bead and moulding went.

## v66 — no popup on the tune fader

- The native slider's value popup off (`show_value_popup` False): it showed "MIDI 29" while
  dragging; the note is on the screen beside the fader.

## v67 — écrans LED propres
- Le verre des mini-écrans (note, FX, noise, div) est aplati en noir uni à l'intérieur de son biseau : le reflet diagonal du rendu Blender (bas droite) faisait une ombre sur le texte.
- Plus de segments fantômes (les « 8 » éteints) ni de halo large : seulement les segments allumés et leur lueur serrée.

## v68 — écrans en caoutchouc, interrupteur DARK/LIGHT sans traits
- Les mini-écrans d'en-tête (note, FX, noise) sont rendus comme un pad : même bloc de silicone texturé, même caméra inclinée, le verre encastré dans le dessus avec 0.6 unité de caoutchouc autour (`SCREEN_LIP`). `screens.json` donne le verre projeté par la caméra.
- Interrupteur de thème : la paire native descend d'une unité (48..53) et l'image du pad couvre toute la paire plus une unité (`theme.TOGGLE_IMAGE`, 70..86 × 47..53). Plus de caches : aucun bord de bouton natif ne tombe sur une jointure d'images (c'étaient les traits autour de LIGHT et sur la plaque).

## v69 — rail sous l'en-tête, écrans comme en v67
- Écrans LED revenus au rendu v67 (la version caoutchouc v68 est annulée ; snapshot `render_panel_art.py.v68`).
- Le trait sous l'en-tête du plateau des onglets n'est plus une rainure noire gravée : c'est un petit rail dans l'alu brossé des cadres (`moulding`), chanfreiné (rendus `deco` sombre et clair refaits).

## v70 — courbes PITCH et AMP du clic
- Onglet CLICK : deux petits pads PITCH | AMP (`theme.PAD_GROUPS["clickedit"]`, à gauche de l'en-tête, l'écran du bruit à droite, 23 de large) choisissent la courbe du clic éditée sur l'écran principal, au-dessus de la waveform du clic (`CLICK_EDIT`, 0 Pitch, 1 Amp).
- Deux curve atoms `CLICK_PITCH_CURVE` (0.5 = hauteur d'origine, 0/1 = −24/+24 demi-tons) et `CLICK_AMP_CURVE` (niveau), sur la durée `CLICK_DECAY`, renommé Length (1..200 ms, défaut 30 ms ; l'id est gardé pour les presets).
- Les curve atoms ne répondent que par bloc de 512 échantillons : le cœur de phase balaie donc les courbes du clic en continu (21 points, x = k/20). La voix les garde dans `ctab_p`/`ctab_a` et les joue échantillon par échantillon. Le pitch rééchantillonne la source comme un sample transposé (jusqu'à 4 pas par échantillon), avant Tone et Low Cut.
- Un 4e display (`kick_display_click`, `@CLICK@ = 1`) envoie les points pairs des courbes du clic à la place de ceux du corps. La vue clic ne montre plus le corps : elle montre le clic seul sur sa durée, aligné sur l'éditeur. L'oscilloscope dessine le clic comme une décroissance de Length/5.
- Presets convertis une fois (2026-11-20) : la valeur `CLICK_DECAY` (l'ancien decay) a été multipliée par 5 pour en faire une Length (l'ancien clic durait environ 5 decays), bornée à 1..200 ms. Originaux dans `preset-backups/2026-11-20_101122_click-length`. Il ne faut pas le refaire.

## v71 — écrans encadrés comme l'EQ, fond de filtre teinté
- Les écrans d'en-tête (note, FX, noise) ont le cadre de l'EQ (`frames()`) : un liseré chromé creux autour d'une moulure noire, l'écran enfoncé dans l'ouverture (`render_panel_art.screens`, branche `well`).
- Le fond de l'écran n'est plus un noir uni : c'est un filtre fumé teinté de la couleur des LEDs, un peu plus clair en haut. Il est ombré sous le bord du cadre (surtout en haut et à gauche), avec un reflet doux horizontal en haut, un fin trait clair au bord supérieur, et la lumière des segments allumés diffusée faiblement autour d'eux. Toujours pas de segments fantômes (`make_panel_svgs.lcd`).

## v72 — son par défaut : [MindB] Kick 01
- Bitwig n'ouvre un device sur un preset que s'il trouve `/opt/bitwig-studio/Library/device-settings/<uuid>/Default.bwpreset` (un preset d'usine ; son journal dit « Default factory preset missing » pour KickForge). Ce n'est pas le cas ici, donc le son par défaut est intégré au device : les valeurs de `[MindB] Kick 01` deviennent les défauts de `build_kick.py`.
- Valeurs reprises : Click 28,5 %, Length 18,3 ms, Tone 13,2 kHz, Low Cut 934 Hz, Level 52,6 %, bruit 909 Hat, et les courbes pitch et amp du kick. Vérifié : les 36 réglages du preset correspondent, sauf VIEW (le preset est enregistré sur AMP ; l'ouverture reste sur MASTER).
- Le double-clic sur un rotatif ramène aussi à ces valeurs.

## v73 : le volume du clic dans l'onglet CLICK

- Le niveau du clic (CLICK, « Level ») quitte l'onglet MASTER pour l'onglet CLICK. MASTER garde Length | Phase, puis Level centré dessous.
- L'onglet CLICK a cinq petits rotatifs au gabarit de l'EQ (art `knobs/out/eq`, 14 x 10, `base_click` / `led_click_*`) : Level | Delay | Length sur la première rangée, Tone | Low Cut centrés dessous (`theme.CLICK_KNOBS`, `theme.CLICK_CAPTIONS`).
- `PanelBuilder.eq_encoder(..., bipolar=False)` : le même petit rotatif, mais ses LED s'allument depuis la gauche (`led_thresholds`) et son pointeur suit `pointer_ranges`, comme les gros rotatifs.
- Les légendes (CELL x 3) sont centrées sous chaque boîte de 14 de large ; aucun rendu Blender n'est à refaire.
- Les presets ne changent pas : le paramètre garde son identifiant.
