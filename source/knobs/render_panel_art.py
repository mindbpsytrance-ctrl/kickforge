"""KickForge panel art in Blender (Cycles, CPU): the panel itself and the rubber switch pads.

  --what deco   the whole panel seen from above, one render (render/deco.exr): a dark satin
                faceplate, the screen bezel round the curve view, walnut end cheeks, silver inlay
                lines, a brushed-aluminium name plate with screws. make_panel_svgs.py cuts it
                into the overlapping pieces of theme.DECO_PIECES.
  --what fader  the tune fader (theme.FADER_RECT), one render per notch (render/fader_<k>.exr): a
                slot between rows of engraved notches, one per semitone (the octave's ends
                longer; the cap's notch lit), and a silicone cap with a lit indicator line,
                standing on notch k. The faceplate is a shadow catcher: the cap's shadow only.
  --what pads   each switch group (theme.PAD_GROUPS) as rubber pads in a recessed well, one
                render per lit pad (render/pads_<w>x<h>_<n>_<k>.exr): the lit pad glows deep
                blue-violet from an LED beneath it, brightest on its sides, and lights the well
                round its foot (as backlit rubber pads on a controller). The labels are printed
                on afterwards (make_panel_svgs.py).

Coordinates: 1 Blender unit = 1 panel grid unit, x right, y up (panel y down = -Y).
Usage: blender -b -P render_panel_art.py -- --what deco|pads|fader [--scale PX_PER_UNIT] [--samples N]
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import theme  # noqa: E402

FONTS = Path(os.environ.get("KICKFORGE_FONTS", "/usr/share/fonts/inter"))   # Inter (Nerd Font build), SIL OFL


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--what", choices=("deco", "pads", "fader", "screens", "frames"), required=True)
    p.add_argument("--out", type=Path, default=HERE / "render")
    p.add_argument("--scale", type=float, default=15.0, help="render px per grid unit")
    p.add_argument("--samples", type=int, default=96)
    p.add_argument("--look", choices=("dark", "light"), default="dark",
                   help="deco: the dark faceplate (deco.exr) or the white one (deco_light.exr, v40)")
    return p.parse_args(argv)


# --- materials -------------------------------------------------------------------------------

def material(name, base, rough=0.5, metal=0.0, coat=0.0, aniso=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*theme.linear(base), 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Anisotropic"].default_value = aniso
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*theme.linear(emit), 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return m


def nodes_of(m):
    return m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def bump(m, height_socket, strength, distance=0.01):
    nodes, links, bsdf = nodes_of(m)
    b = nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    links.new(height_socket, b.inputs["Height"])
    links.new(b.outputs["Normal"], bsdf.inputs["Normal"])


def satin(name, base, rough=0.45, coat=0.25, grain=0.25):
    """Painted / anodised metal with a fine grain."""
    m = material(name, base, rough=rough, coat=coat)
    nodes, links, _ = nodes_of(m)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 160.0
    noise.inputs["Detail"].default_value = 3.0
    bump(m, noise.outputs["Fac"], grain, 0.004)
    return m


def brushed(name, base, rough=0.28, vertical=False):
    """Brushed aluminium: highlights stretched across the grain (the grain along x), the grain in
    two scales (coarse streaks, fine hairlines) in the relief and a little in the colour."""
    m = material(name, base, rough=rough, metal=1.0, aniso=0.9)
    nodes, links, bsdf = nodes_of(m)
    tangent = nodes.new("ShaderNodeTangent")
    tangent.direction_type = "RADIAL"
    tangent.axis = "X" if vertical else "Y"   # round Y: along x on a plate in the xy plane (round X: along y)
    links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])
    coords = nodes.new("ShaderNodeTexCoord")
    grains = []
    for scale, stretch in ((8.0, 30.0), (40.0, 160.0)):
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (stretch, 0.04, 1.0) if vertical else (0.04, stretch, 1.0)
        links.new(coords.outputs["Object"], mapping.inputs["Vector"])
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = scale
        noise.inputs["Detail"].default_value = 8.0
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        grains.append(noise)
    mix = nodes.new("ShaderNodeMath")
    mix.operation = "ADD"
    links.new(grains[0].outputs["Fac"], mix.inputs[0])
    links.new(grains[1].outputs["Fac"], mix.inputs[1])
    bump(m, mix.outputs["Value"], 0.45, 0.003)
    half = nodes.new("ShaderNodeMath")
    half.operation = "MULTIPLY"
    half.inputs[1].default_value = 0.5
    links.new(mix.outputs["Value"], half.inputs[0])
    tint = nodes.new("ShaderNodeValToRGB")
    els = tint.color_ramp.elements
    els[0].position, els[0].color = 0.3, (*[0.86 * c for c in theme.linear(base)], 1.0)
    els[1].position, els[1].color = 0.7, (*[min(1.0, 1.1 * c) for c in theme.linear(base)], 1.0)
    links.new(half.outputs["Value"], tint.inputs["Fac"])
    links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def plate_light(sc, objs, x, y, w, h, z0):
    """A soft light just over the name plate, lighting it only (light linking): a sheen across
    the brushed grain, brightest a third of the way in, fading to the ends."""
    rx = bpy.data.collections.new("plate_rx")
    sc.collection.children.link(rx)
    for o in objs:
        rx.objects.link(o)
    lamp = light(sc, "plate_sheen", (x + w * 0.3, -(y + h * 0.5), z0 + 10.0), 420, 3.0, (1.0, 0.98, 0.96),
                 (x + w * 0.3, -(y + h * 0.5), 0.0))
    lamp.data.shape = "RECTANGLE"          # a band across the grain (the grain runs along x)
    lamp.data.size, lamp.data.size_y = 3.0, 3.0 * h
    lamp.visible_camera = False
    lamp.light_linking.receiver_collection = rx
    rx.hide_render = False
    return lamp


def walnut(name):
    """Varnished walnut, the grain running down the cheek (along y)."""
    m = material(name, (0.3, 0.15, 0.07), rough=0.32, coat=0.7)
    nodes, links, bsdf = nodes_of(m)
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 0.06, 1.0)
    links.new(coords.outputs["Object"], mapping.inputs["Vector"])
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 0.9
    wave.inputs["Distortion"].default_value = 9.0
    wave.inputs["Detail"].default_value = 5.0
    wave.inputs["Detail Scale"].default_value = 1.2
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*theme.linear((0.13, 0.06, 0.03)), 1.0)
    els[1].position, els[1].color = 1.0, (*theme.linear((0.42, 0.22, 0.10)), 1.0)
    mid = els.new(0.55)
    mid.color = (*theme.linear((0.27, 0.13, 0.06)), 1.0)
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    pores = nodes.new("ShaderNodeTexNoise")
    pores.inputs["Scale"].default_value = 90.0
    links.new(mapping.outputs["Vector"], pores.inputs["Vector"])
    bump(m, pores.outputs["Fac"], 0.12, 0.004)
    return m


def rubber(name, lit, colour=None):
    """Silicone pad lit (or not) from beneath: a soft satin sheen, a fine stippled skin with a
    slightly mottled matte, some translucency; the light comes through its sides and bevels
    (facing away from the camera) more than through its top."""
    m = material(name, theme.RUBBER, rough=0.55)
    nodes, links, bsdf = nodes_of(m)
    colour = theme.linear(colour or theme.PAD_LIT)
    # silicone: velvet-like sheen, no clear coat, light let through (unlit: a little, grey)
    bsdf.inputs["Sheen Weight"].default_value = 0.7
    bsdf.inputs["Sheen Roughness"].default_value = 0.35
    bsdf.inputs["Subsurface Weight"].default_value = 0.25
    bsdf.inputs["Subsurface Radius"].default_value = (0.5, 0.5, 0.6)
    bsdf.inputs["Emission Color"].default_value = (*colour, 1.0)
    weight = nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.35
    # the LED's light on the sides and bevels only: nothing on faces turned to the camera (the
    # top, seen a little from the front, faces it at about 0.1)
    curve = nodes.new("ShaderNodeMapRange")
    curve.inputs["From Min"].default_value = 0.3
    curve.inputs["From Max"].default_value = 0.9
    curve.inputs["To Min"].default_value = 0.0
    curve.inputs["To Max"].default_value = 7.0 if lit else 0.0
    links.new(weight.outputs["Facing"], curve.inputs["Value"])
    links.new(curve.outputs["Result"], bsdf.inputs["Emission Strength"])
    if lit:   # (the top as an unlit pad's, a hint of the LED in it: v35, only the sides and the legend glow)
        bsdf.inputs["Base Color"].default_value = (*[0.05 * c + 0.13 for c in colour], 1.0)
        bsdf.inputs["Subsurface Weight"].default_value = 0.35
        bsdf.inputs["Subsurface Radius"].default_value = (0.4, 0.4, 0.6)
    # the skin: a stipple (cells about 0.3 grid unit, 2 screen px: it reads as a moulded silicone
    # texture, not as noise) and a mottled roughness
    coords = nodes.new("ShaderNodeTexCoord")
    stipple = nodes.new("ShaderNodeTexVoronoi")
    stipple.feature = "SMOOTH_F1"
    stipple.inputs["Scale"].default_value = 2.3
    stipple.inputs["Randomness"].default_value = 0.85
    links.new(coords.outputs["Object"], stipple.inputs["Vector"])
    mottle = nodes.new("ShaderNodeTexNoise")
    mottle.inputs["Scale"].default_value = 1.4
    mottle.inputs["Detail"].default_value = 4.0
    links.new(coords.outputs["Object"], mottle.inputs["Vector"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.45
    rough.inputs["To Max"].default_value = 0.68
    links.new(mottle.outputs["Fac"], rough.inputs["Value"])
    links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump(m, stipple.outputs["Distance"], 1.0, 0.09)
    return m


# --- geometry --------------------------------------------------------------------------------

def finish(obj, mat, smooth=True):
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    obj.data.materials.append(mat)
    return obj


def slab(name, x, y, w, h, z0, z1, mat):
    """A plain box over panel rect (x, y, w, h), from z0 to z1."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x + w / 2, -(y + h / 2), (z0 + z1) / 2))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (w, h, z1 - z0)
    return finish(obj, mat, smooth=False)


def rounded_rect(name, x, y, w, h, z0, z1, mat, radius, bevel=0.0, taper=0.0, segs=4):
    """A rounded-rectangle block (corner radius in the panel plane), optionally tapered and
    bevelled on its top edge."""
    import bmesh
    r = min(radius, w / 2 - 1e-3, h / 2 - 1e-3)
    bm = bmesh.new()

    def outline(inset):
        pts = []
        rr = max(r - inset, 0.001)
        cx = (x + inset + rr, x + w - inset - rr)
        cy = (y + inset + rr, y + h - inset - rr)
        for (ox, oy, a0) in ((cx[1], cy[0], -90), (cx[1], cy[1], 0), (cx[0], cy[1], 90), (cx[0], cy[0], 180)):
            for k in range(9):
                a = math.radians(a0 + 90 * k / 8)
                pts.append((ox + rr * math.cos(a), -(oy + rr * math.sin(a))))
        return pts

    low = [bm.verts.new((px, py, z0)) for px, py in outline(0.0)]
    high = [bm.verts.new((px, py, z1)) for px, py in outline(taper)]
    n = len(low)
    for j in range(n):
        bm.faces.new((low[j], low[(j + 1) % n], high[(j + 1) % n], high[j]))
    bm.faces.new(list(reversed(high)))
    bm.faces.new(low)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segs
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(50)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    mod = obj.modifiers.new("autosmooth", "EDGE_SPLIT")
    mod.split_angle = math.radians(50)
    return obj


def screw(x, y, z, mat, slot, r=0.62):
    k = r / 0.62
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=(x, -y, z))
    head = bpy.context.object
    head.scale = (1.0, 1.0, 0.38)
    finish(head, mat)
    for angle in (35, 125):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, -y, z + 0.2 * k))
        s = bpy.context.object
        s.scale = (0.95 * k, 0.13 * k, 0.12 * k)
        s.rotation_euler.z = math.radians(angle)
        finish(s, slot, smooth=False)


def text(body, x, y, z, size, mat, font, spacing=1.0, align="CENTER"):
    curve = bpy.data.curves.new("text", "FONT")
    curve.body = body
    curve.size = size
    curve.space_character = spacing
    curve.align_x = align
    curve.align_y = "CENTER"
    curve.extrude = 0.03
    path = FONTS / font
    if path.exists():
        curve.font = bpy.data.fonts.load(str(path))
    obj = bpy.data.objects.new("text", curve)
    obj.location = (x, -y, z)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


# --- scene -----------------------------------------------------------------------------------

def scene(w, h, scale, samples, cx, cy):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.seed = 3
    sc.render.film_transparent = True
    sc.render.resolution_x = round(w * scale)
    sc.render.resolution_y = round(h * scale)
    sc.view_settings.view_transform = "Standard"
    fmt = sc.render.image_settings
    fmt.file_format = "OPEN_EXR"
    fmt.color_depth = "32"
    fmt.color_mode = "RGBA"
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.055, 0.055, 0.07, 1.0)
    sc.world = world
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = max(w, h)
    cam_obj = bpy.data.objects.new("cam", cam)
    cam_obj.location = (cx, -cy, 60.0)
    sc.collection.objects.link(cam_obj)
    sc.camera = cam_obj
    return sc


def light(sc, name, loc, energy, size, colour=(1.0, 1.0, 1.0), target=(0.0, 0.0, 0.0)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    data.color = colour
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    sc.collection.objects.link(obj)
    from mathutils import Vector
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def render(sc, path):
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def hollow(obj, cutter):
    """Cut cutter out of obj (a boolean, first in the stack), the cutter left out of the render."""
    cutter.hide_render = True
    cut = obj.modifiers.new("cut", "BOOLEAN")
    cut.operation, cut.object, cut.solver = "DIFFERENCE", cutter, "EXACT"
    obj.modifiers.move(len(obj.modifiers) - 1, 0)
    return obj


def arcade_frame(name, x, y, w, h, moulding, bezel, screw_metal, slot, inside=None):
    """The screen's frame, arcade-cabinet style (outer rect x y w h, theme.FRAME wide): a raised
    moulding (satin, a broad chamfer) down to a glossy black lip, a screw in each corner. With
    inside (a material), the frame is a ring round a floor of it, a step below the lip (the control
    groups' trays, v38); without, it is solid (the screen sits on it). Hollowed by a boolean: as a
    solid block a bevelled top showed a diagonal shading crease across a tray (v32)."""
    f = theme.FRAME
    # (v40: a machined rim, crisp chamfers that catch the light, as a synth's extruded trim; v38-v39
    # a soft rounded moulding)
    ring = rounded_rect(f"frame_{name}", x, y, w, h, 0.0, 0.75, moulding, 1.2, bevel=0.42, taper=0.2, segs=2)
    # (hollow, the lip is a ring 0.75 wide: a bevel of 0.3 on both its edges, after a taper of 0.25,
    # folded its top across the hole, a black lid over the tray (v38 first render))
    lip = rounded_rect(f"lip_{name}", x + f - 0.75, y + f - 0.75, w - 2 * f + 1.5, h - 2 * f + 1.5, 0.0, 0.8,
                       bezel, 0.9, bevel=0.3 if inside is None else 0.1, taper=0.25 if inside is None else 0.12)
    if inside is not None:
        # the ring cut out under the lip (1.5 wide: its chamfer, 0.5 on each edge after a 0.35 taper,
        # folded a narrower ring's top across the hole, a black lid over the tray, v38 first render)
        hollow(ring, rounded_rect(f"cut_{name}", x + f - 0.2, y + f - 0.2, w - 2 * f + 0.4, h - 2 * f + 0.4,
                                  -0.3, 1.0, inside, 0.7))
        hollow(lip, rounded_rect(f"cut2_{name}", x + f, y + f, w - 2 * f, h - 2 * f, -0.3, 1.0, inside, 0.6))
        rounded_rect(f"floor_{name}", x + f - 0.2, y + f - 0.2, w - 2 * f + 0.4, h - 2 * f + 0.4, 0.0, 0.2, inside, 0.7)
    for sx, sy in ((x + 0.5, y + 0.5), (x + w - 0.5, y + 0.5), (x + 0.5, y + h - 0.5), (x + w - 0.5, y + h - 0.5)):
        screw(sx, sy, 0.78, screw_metal, slot, r=0.36)


def groove(name, x, y, length, vertical, dark, shine):
    """An engraved separator (v40): a narrow dark channel cut in the floor, its far wall (bottom or
    right: the light comes from the top left) catching the light as a fine bright line."""
    w, h = (0.32, length) if vertical else (length, 0.32)
    rounded_rect(f"groove_{name}", x, y, w, h, 0.17, 0.215, dark, 0.12)
    if vertical:
        rounded_rect(f"groove_lit_{name}", x + 0.3, y, 0.09, length, 0.2, 0.23, shine, 0.04)
    else:
        rounded_rect(f"groove_lit_{name}", x, y + 0.3, length, 0.09, 0.2, 0.23, shine, 0.04)


def deco(a):
    W, H = theme.PANEL_W, theme.PANEL_H
    sc = scene(W, H, a.scale, a.samples, W / 2, H / 2)
    cx, cy = W / 2, -H / 2
    # key light from the top left (shadows fall to the bottom right), cool fill, warm kicker
    light(sc, "key", (cx - 90, cy + 70, 110), 260000, 60, (1.0, 0.97, 0.93), (cx, cy, 0))
    light(sc, "fill", (cx + 80, cy - 60, 140), 60000, 120, (0.8, 0.85, 1.0), (cx, cy, 0))
    # (no "sheen" light: its reflection in the faceplate's varnish was a hard-edged light
    # triangle on the right, v29; a broad soft fill from above instead)
    light(sc, "sky", (cx, cy + 40, 260), 120000, 400, (0.9, 0.92, 1.0), (cx, cy, 0))

    light_look = a.look == "light"
    paint = theme.PANEL_LIGHT if light_look else theme.PANEL
    face = satin("faceplate", paint, rough=0.45, coat=0.15, grain=0.3)
    bezel = material("bezel", (0.018, 0.018, 0.024), rough=0.2, coat=0.9)
    glass = material("screen", (0.01, 0.01, 0.016), rough=0.08, coat=1.0)
    chrome = material("chrome", (0.78, 0.79, 0.83), rough=0.18, metal=1.0)
    plate = brushed("plate", (0.70, 0.71, 0.74))
    ink = material("ink", (0.05, 0.05, 0.07), rough=0.6)
    accent = material("accent", (0.2, 0.18, 0.5), rough=0.3, emit=theme.PAD_LIT, strength=2.5)
    slot = material("slot", (0.02, 0.02, 0.02), rough=0.8)
    wood = walnut("walnut")
    screw_metal = material("screw", (0.55, 0.56, 0.6), rough=0.25, metal=1.0)

    # faceplate
    slab("face", 0, 0, W, H, -1.0, 0.0, face)
    # screen, arcade-cabinet style: a raised moulded frame (satin, fine texture) with a chamfer
    # down to a glossy black step, the screen set in below it; a screw in each corner. The glass
    # over the screen is a separate image above the curve (make_panel_svgs.glass), not here.
    vx, vy, vw, vh = theme.VIEW_RECT
    f = theme.FRAME
    # the frames' rims: dark anodised, brushed aluminium (v40; before, satin black moulding)
    moulding = brushed("rim", (0.60, 0.61, 0.64) if light_look else (0.16, 0.16, 0.185), rough=0.3)
    arcade_frame("screen", vx - f, vy - f, vw + 2 * f, vh + 2 * f, moulding, bezel, screw_metal, slot)
    rounded_rect("screen", vx, vy, vw, vh, 0.0, 0.82, glass, 0.6)
    # the control groups (theme.GROUP_RECTS: the header, the tab's controls, the global ones), each
    # in a tray framed as the screen (v38; v32-v37 a lower, plainer moulding), round a floor of
    # faceplate; a silver inlay line under the tab tray's header
    # (the trays' floor without a clear coat: a coat mirrored the big soft light's edge as a
    # hard-edged triangle in each tray)
    tray = satin("tray", paint, rough=0.55, coat=0.0, grain=0.3)
    for name, (gx0, gy0, gw, gh) in theme.GROUP_RECTS.items():
        arcade_frame(name, gx0, gy0, gw, gh, moulding, bezel, screw_metal, slot, inside=tray)
        if name == "tab":   # under the tab tray's header
            # (v69) a small rail in the frames' own brushed rim (moulding), chamfered as their trim:
            # v40-v68 an engraved dark channel with a chrome glint, which at Bitwig's size read as a
            # flat black line, another material than the frames round it
            rounded_rect(f"rail_{name}", gx0 + f + 0.6, theme.HEADER_Y + theme.HEADER_H + 0.7,
                         gw - 2 * f - 1.2, 0.5, 0.0, 0.32, moulding, 0.2, bevel=0.14, segs=2)
    # (v40-v44: an engraved line between the tab switches and DARK / LIGHT; v45: the switch is at the plate)
    # the faceplate's top and bottom edges: brushed gunmetal trims between the cheeks (v40)
    trim = brushed("trim", (0.66, 0.67, 0.70) if light_look else (0.30, 0.30, 0.33), rough=0.26)
    for ty in (0.0, H - 0.9):
        rounded_rect(f"trim{ty}", theme.CHEEK - 0.3, ty, W - 2 * theme.CHEEK + 0.6, 0.9, 0.0, 0.45, trim, 0.2,
                     bevel=0.18, segs=2)
    # (v39: "TUNE" is no longer printed here: it is the master tab's, an image shown with it)
    # name plate: brushed aluminium, chamfered, four screws, engraved name
    px, py, pw, ph = theme.PLATE_RECT
    plate_obj = rounded_rect("plate", px + 0.5, py, pw - 1.0, ph, 0.0, 0.55, plate, 0.8, bevel=0.22)
    plate_light(sc, [plate_obj], px, py, pw, ph, 0.55)
    if ph >= 8:   # (v38-v43) the tall plate: four screws, name, subtitle, the maker's mark
        for sx, sy in ((px + 2.0, py + 1.6), (px + pw - 2.0, py + 1.6), (px + 2.0, py + ph - 1.6),
                       (px + pw - 2.0, py + ph - 1.6)):
            screw(sx, sy, 0.55, screw_metal, slot)
        k = ph / 14.0   # (v43: the lettering scaled with the plate's height, k = 1 at 14)
        text("KICKFORGE", px + pw / 2, py + ph * 0.42, 0.53, 4.6 * k, ink, "InterNerdFontPropo-ExtraBold.otf", 1.12)
        text("KICK DRUM SYNTHESIZER", px + pw / 2, py + ph * 0.70, 0.53, 1.55 * k, ink,
             "InterNerdFontPropo-SemiBold.otf", 1.6)
        rounded_rect("plate_line", px + pw * 0.2, py + ph * 0.585, pw * 0.6, 0.2 * k, 0.55, 0.6, accent, 0.1)
        text("by MindB", px + pw / 2, py + ph * 0.86, 0.53, 1.45 * k, ink, "InterNerdFontPropo-SemiBoldItalic.otf", 1.15)
    else:   # (v44) a slim badge: a screw at each end, the name, the lit line under it, the maker's mark
        for sx in (px + 2.0, px + pw - 2.0):
            screw(sx, py + ph / 2, 0.5, screw_metal, slot)
        nx = px + pw * 0.41
        text("KICKFORGE", nx, py + ph * 0.44, 0.53, 2.5, ink, "InterNerdFontPropo-ExtraBold.otf", 1.12)
        rounded_rect("plate_line", nx - 8.0, py + ph * 0.80, 16.0, 0.16, 0.55, 0.6, accent, 0.08)
        # (v54: the maker's mark 1.2 -> 1.65)
        text("by MindB", px + pw - 3.2, py + ph * 0.52, 0.53, 1.65, ink, "InterNerdFontPropo-SemiBoldItalic.otf",
             1.1, align="RIGHT")
    # end cheeks with a screw top and bottom: walnut on the white panel, brushed aluminium (brushed
    # along their length) on the dark one (v41; before, walnut on both)
    cheek = wood if light_look else brushed("cheek_alu", (0.62, 0.63, 0.66), rough=0.26, vertical=True)
    for x in (0, W - theme.CHEEK):
        rounded_rect(f"cheek{x}", x, 0, theme.CHEEK, H, 0.0, 1.4, cheek, 0.5, bevel=0.45, segs=5)
        for sy in (2.4, H - 2.4):
            screw(x + theme.CHEEK / 2, sy, 1.4, screw_metal, slot)
    render(sc, a.out / ("deco_light.exr" if light_look else "deco.exr"))


PAD_TILT = theme.VIEW_TILT   # (v42: the device's one angle; v41: 16) degrees: the pads seen from a little in front (v35: 22, the tops ran off the image)
LEGEND_IDLE = 0.35  # (v53: 0.64 -> 0.35 of the lit legend's 6, white reading brighter than a colour) an unlit legend's glow
PAD_TOP = 1.6       # (v41: 1.1 -> 1.6, taller keys) the pads' height (grid units; v34: 0.9, v35: 1.5)


def pads(a):
    """One render per group shape and lit pad. The image covers the group's cell grown by
    1 unit each side (the well round the pads hides the native buttons under them)."""
    done = {}
    meta = {}
    for name, (w, h, labels) in theme.PAD_GROUPS.items():
        # one render set per group: the legends are part of the render (v35)
        key = (w, h, len(labels))
        meta[name] = {"shape": f"pads_{name}", "labels": list(labels)}
        done[key] = True
        W, H = w + 2, h + 2
        # a group in the header is cut at the panel's top edge (its image starts at the cell's
        # top, not a unit above): the camera aims half a unit lower, so the well stays whole
        oy = -0.5 if theme.PAD_AT[name][1] < 1 else 0.0
        for lit in range(len(labels)):
            sc = scene(W, H, a.scale, a.samples, W / 2, H / 2)
            # seen from a little in front, as the knobs (v35): the pads' front sides show
            cam = sc.camera
            tilt = math.radians(PAD_TILT)
            # aimed at the pads' mid-height, so they sit in the middle of their image
            # aimed at the panel's plane (v42; before, at the pads' mid-height): the well's foot
            # where the panel art has it, as the knobs and the fader
            cam.location = (W / 2, -H / 2 - oy - 60.0 * math.sin(tilt), 60.0 * math.cos(tilt))
            cam.rotation_euler = (tilt, 0.0, 0.0)
            led = theme.PAD_COLOURS.get(name, (theme.PAD_LIT,) * len(labels))[lit]
            # (v53) the lit pad's legend in its pad's colour (0.8 of it; v35-v52 0.45, near white)
            legend_on = material("legend_on", (0.9, 0.9, 1.0), rough=0.4,
                                 emit=tuple(0.8 * c + 0.2 for c in led), strength=6.0)
            # an unlit pad's legend glows white, a little less than a lit one (LEGEND_IDLE of its
            # strength); only the legend, not the pad (v53; v52 in its pad's colour; v35-v51 plain grey)
            legend_off = [material(f"legend_off{k}", (0.55, 0.55, 0.6), rough=0.45,
                                   emit=(0.93, 0.93, 0.97), strength=6.0 * LEGEND_IDLE)
                          for k in range(len(labels))]
            light(sc, "key", (W / 2 - 30, -H / 2 + 25, 40), 9000, 20, (1.0, 0.97, 0.94), (W / 2, -H / 2, 0))
            light(sc, "fill", (W / 2 + 25, -H / 2 - 20, 50), 3000, 40, (0.8, 0.85, 1.0), (W / 2, -H / 2, 0))
            # a grazing light from the left: brings out the silicone's stippled skin
            light(sc, "rake", (-30, -H / 2 + 6, 5), 2500, 10, (0.95, 0.95, 1.0), (W / 2, -H / 2, 0.6))
            well = material("well", (0.012, 0.012, 0.018), rough=0.5)
            rim = material("rim", (0.6, 0.61, 0.66), rough=0.22, metal=1.0)
            glow = material("glow", (0.0, 0.0, 0.0), rough=1.0, emit=led, strength=6.0)
            off_rubber, on_rubber = rubber("rubber", False), rubber("rubber_lit", True, led)
            # the wells (theme.pad_wells; v41: the view switch in three): each its span of the native
            # group's cell (1, 1, w, h) grown by 0.45
            gap = 0.55
            spots = {}
            for j, (wx0, wx1, ks) in enumerate(theme.pad_wells(name)):
                ww = wx1 - wx0
                rounded_rect(f"rim{j}", 0.45 + wx0, 0.45, ww + 1.1, h + 1.1, -0.2, 0.0, rim, 0.75, bevel=0.08)
                rounded_rect(f"well{j}", 0.55 + wx0, 0.55, ww + 0.9, h + 0.9, -0.2, 0.02, well, 0.65)
                pw = (ww + 0.3 - gap * (len(ks) - 1)) / len(ks)
                for i, k in enumerate(ks):
                    spots[k] = (0.85 + wx0 + i * (pw + gap), pw)
            single = name in theme.PAD_SINGLE   # (v42: one pad showing the state, lit)
            for k in ([0] if single else range(len(labels))):
                x0, pw = spots[k]
                on = single or k == lit
                legend = labels[lit] if single else labels[k]
                if on:   # the LED's light spilling round the pad's foot
                    rounded_rect("halo", x0 - 0.16, 0.69, pw + 0.32, h + 0.62, 0.02, 0.03, glow, 0.6)
                # silicone block: tall sides (lit by the LED on the lit pad), a round-shouldered top
                rounded_rect(f"pad{k}", x0, 0.85, pw, h + 0.3, 0.03, PAD_TOP, on_rubber if on else off_rubber,
                             0.6, bevel=0.3, taper=0.1, segs=8)
                # the legend: translucent, flush with the top, lit through by the LED (the lit pad's)
                # (v52: about a fifth bigger, 1.84 -> 2.2 at most; v37: the pads grew, not their legends)
                size = min(2.2, h * 0.52, pw * 0.40)
                word = text(legend, x0 + pw / 2, 0.85 + (h + 0.3) / 2, PAD_TOP + 0.012, size,
                            legend_on if on else legend_off[k], "InterNerdFontPropo-Bold.otf")
                # a long word kept within the pad's top (its shoulders round off 0.8 each side)
                bpy.context.view_layer.update()
                room = pw - 1.6
                if word.dimensions.x > room:
                    word.scale = (room / word.dimensions.x,) * 3
                word.data.extrude = 0.01
            render(sc, a.out / f"pads_{name}_{lit}.exr")
    (a.out / "pads.json").write_text(json.dumps(meta, indent=1))


def fader(a):
    """The tune fader, one render per notch k: the cap stands on notch k."""
    _, _, W, H = theme.FADER_RECT
    mid = H / 2
    for lit in range(theme.FADER_STEPS):
        sc = scene(W, H, a.scale, a.samples, W / 2, H / 2)
        # seen from the device's one angle (v42; before, from straight above), aimed at the panel
        tilt = math.radians(theme.VIEW_TILT)
        sc.camera.location = (W / 2, -H / 2 - 60.0 * math.sin(tilt), 60.0 * math.cos(tilt))
        sc.camera.rotation_euler = (tilt, 0.0, 0.0)
        light(sc, "key", (W / 2 - 30, -H / 2 + 25, 40), 9000, 20, (1.0, 0.97, 0.94), (W / 2, -H / 2, 0))
        light(sc, "fill", (W / 2 + 25, -H / 2 - 20, 50), 3000, 40, (0.8, 0.85, 1.0), (W / 2, -H / 2, 0))
        light(sc, "rake", (-30, -H / 2 + 6, 5), 2500, 10, (0.95, 0.95, 1.0), (W / 2, -H / 2, 0.6))
        # the faceplate is the panel art under the image: here only a shadow catcher
        catcher = slab("catcher", -2, -2, W + 4, H + 4, -0.5, 0.0, material("catch", theme.PANEL))
        catcher.is_shadow_catcher = True
        chrome = material("chrome", (0.62, 0.63, 0.68), rough=0.25, metal=1.0)
        well = material("well", (0.008, 0.008, 0.012), rough=0.35, coat=0.6)
        glow = material("glow", (0.0, 0.0, 0.0), rough=1.0, emit=theme.PAD_LIT, strength=7.0)
        dim = material("dim", (0.05, 0.05, 0.08), rough=0.5, emit=theme.PAD_LIT, strength=0.25)
        # the track: a brushed-aluminium rail plate with the slot cut through it, a scallop cut into
        # both edges of the slot at each semitone (the detents, as on a notched fader; v31-v34 had
        # grey tick bars above and below), over a black channel; C0, F# and C1 marked by a dot
        # (v59) about 1.5 x thicker across (the rail 2.6 -> 4.0 high, the slot 0.68 -> 1.1, the cap
        # 3.6 -> 5.2 high and 2.2 -> 2.8 wide): the fader as tall in the header as the pads
        # (the rail's ends a unit inside the cell: its soft shadow fades out within the image, not
        # cut at its edge, a grey box seen on the white panel)
        x0, x1 = theme.fader_x(0) - 0.6, theme.fader_x(theme.FADER_STEPS - 1) + 0.6
        alu = brushed("rail", (0.52, 0.53, 0.57), rough=0.32)
        # (v62) as tall as the FIX pad (theme.PAD_BODY, 6.3; v59 4.0), the cap too, the slot 1.7
        rh = theme.PAD_BODY[1]
        rounded_rect("channel", x0 - 0.1, mid - 1.15, x1 - x0 + 0.2, 2.3, 0.0, 0.04, well, 0.6)
        rail = rounded_rect("rail", x0 - 0.15, mid - rh / 2, x1 - x0 + 0.3, rh, 0.0, 0.22, alu, 0.75, bevel=0.07, segs=3)
        cuts = bpy.data.collections.new("cuts")
        bpy.context.scene.collection.children.link(cuts)
        slot = rounded_rect("slot", x0, mid - 0.85, x1 - x0, 1.7, -0.3, 0.6, well, 0.85)
        for k in range(theme.FADER_STEPS):
            for sign in (-1, 1):
                bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.34, depth=0.9,
                                                    location=(theme.fader_x(k), -(mid + sign * 0.85), 0.15))
                hole = bpy.context.object
                bpy.context.collection.objects.unlink(hole)
                cuts.objects.link(hole)
        bpy.context.collection.objects.unlink(slot)
        cuts.objects.link(slot)
        for o in cuts.objects:
            o.hide_render = True
        cut = rail.modifiers.new("cut", "BOOLEAN")
        cut.operation, cut.operand_type, cut.collection, cut.solver = "DIFFERENCE", "COLLECTION", cuts, "EXACT"
        rail.modifiers.move(len(rail.modifiers) - 1, 0)
        for k in (0, theme.FADER_STEPS // 2, theme.FADER_STEPS - 1):
            for sign in (-1, 1):
                bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.13 if k != theme.FADER_STEPS // 2 else 0.1,
                                                    depth=0.04, location=(theme.fader_x(k), -(mid + sign * 2.3), 0.22))
                finish(bpy.context.object, glow if k == lit else dim)
        # the cap: a silicone pillow across the slot, its indicator line lit
        cx, cw = theme.fader_x(lit), theme.FADER_CAP_W
        cap = rubber("cap", False)
        ch = theme.PAD_BODY[1]   # (v62: 6.3, as the pad; v59: 3.6 -> 4.8, its shadow kept in the cell; v37: the header grew to 5; the cap kept its size, centred)
        cy0 = (H - ch) / 2
        rounded_rect("cap", cx - cw / 2, cy0, cw, ch, 0.0, 1.3, cap, 0.55, bevel=0.42, taper=0.14, segs=8)
        rounded_rect("cap_line", cx - 0.11, cy0 + 0.65, 0.22, ch - 1.3, 1.28, 1.34, glow, 0.1)
        render(sc, a.out / f"fader_{lit}.exr")


# the mini LED screens' windows (v37), in grid units within their cells: the frame (a chrome rim,
# a black moulding) and the glass the segments are drawn on (make_panel_svgs.py)
_NH = theme.HEADER_H   # the header's screens are 3.6 high, centred
_PT, _PB = theme.PAD_BODY   # (v62: the note's window as tall as the FIX pad beside it)
# (v65) the header's screens in the pads' frame: the chrome rim and black well round each pad
# (render_panel_art.pads), the glass where the pad's silicone would be, as tall (6.3)
def _well(cell):
    _, _, w, h = cell
    return {"cell": cell, "well": True, "rim": (0.45, 0.45, w - 0.9, h - 0.9), "glass": (0.85, _PT, w - 1.7, _PB),
            "text_h": 2.9}


SCREENS = {"note": _well(theme.NOTE_RECT),
           # (v47: centred in its cell, under the encoder; v37-v46 at 2.3, centred in the 15 wide cells of before)
           "div": {"cell": theme.DIV_RECT, "rim": ((theme.DIV_RECT[2] - 10.4) / 2, 0.05, 10.4, 2.9),
                   "glass": ((theme.DIV_RECT[2] - 9.8) / 2, 0.32, 9.8, 2.36)},
           # (v64: the header's screens framed as the note's, as tall as the pads; v37-v63 3.6 high)
           "fx": _well(theme.FX_RECT),          # (v49: FX ON / OFF)
           "noise": _well(theme.NOISE_RECT)}


def screens(a):
    """Each mini LED screen's window, empty (render/screen_<name>.exr): a chrome rim round a black
    moulding, as the pads' wells, and a recessed smoked glass. The faceplate is a shadow catcher."""
    for name, s in SCREENS.items():
        _, _, W, H = s["cell"]
        sc = scene(W, H, a.scale, a.samples, W / 2, H / 2)
        light(sc, "key", (W / 2 - 30, -H / 2 + 25, 40), 9000, 20, (1.0, 0.97, 0.94), (W / 2, -H / 2, 0))
        light(sc, "fill", (W / 2 + 25, -H / 2 - 20, 50), 3000, 40, (0.8, 0.85, 1.0), (W / 2, -H / 2, 0))
        light(sc, "rake", (-30, -H / 2 + 6, 5), 2500, 10, (0.95, 0.95, 1.0), (W / 2, -H / 2, 0.6))
        catcher = slab("catcher", -2, -2, W + 4, H + 4, -0.5, 0.0, material("catch", theme.PANEL))
        catcher.is_shadow_catcher = True
        rim = material("rim", (0.6, 0.61, 0.66), rough=0.22, metal=1.0)
        moulding = satin("moulding", (0.03, 0.03, 0.038), rough=0.5, coat=0.2, grain=0.4)
        glass = material("glass", (0.006, 0.006, 0.01), rough=0.06, coat=1.0)
        rx, ry, rw, rh = s["rim"]
        gx, gy, gw, gh = s["glass"]
        if s.get("well"):
            # (v71) framed as the EQ (frames()): a hollow chrome bead round a black moulding, the
            # screen sunk in its opening (v65-v70: the pads' flush chrome rim and black well)
            m, bead, inner = 0.3, 0.16, 0.3
            o = m + bead + inner
            outer = rounded_rect("rim", m, m, W - 2 * m, H - 2 * m, 0.0, 0.26, rim, 1.0, bevel=0.06, segs=3)
            hollow(outer, rounded_rect("rim_cut", o, o, W - 2 * o, H - 2 * o, -1.0, 1.0, rim, 0.6))
            mould = rounded_rect("moulding", m + bead, m + bead, W - 2 * (m + bead), H - 2 * (m + bead), 0.0, 0.3,
                                 moulding, 0.85, bevel=0.08, segs=4)
            hollow(mould, rounded_rect("mould_cut", o, o, W - 2 * o, H - 2 * o, -1.0, 1.0, rim, 0.6))
            rounded_rect("well", o - 0.05, o - 0.05, W - 2 * o + 0.1, H - 2 * o + 0.1, -0.2, 0.0,
                         material("well", (0.012, 0.012, 0.018), rough=0.5), 0.62)
            rounded_rect("glass", gx, gy, gw, gh, 0.0, 0.08, glass, 0.55, bevel=0.03, segs=2)
        else:
            rounded_rect("rim", rx, ry, rw, rh, 0.0, 0.32, rim, 0.55, bevel=0.07, segs=3)
            rounded_rect("moulding", rx + 0.08, ry + 0.08, rw - 0.16, rh - 0.16, 0.0, 0.36, moulding, 0.45,
                         bevel=0.1, taper=0.06, segs=4)
            rounded_rect("glass", gx, gy, gw, gh, 0.0, 0.2, glass, 0.3)
        render(sc, a.out / f"screen_{name}.exr")
    (a.out / "screens.json").write_text(json.dumps(SCREENS, indent=1))


def frames(a):
    """(v58) The FX tab's EQ frame (theme.EQ_RECT), render/frame_eq.exr: a hollow chrome bead round
    a black moulding, as the mini screens' rims, its middle open on the panel art; the faceplate a
    shadow catcher."""
    _, _, W, H = theme.EQ_RECT
    sc = scene(W, H, a.scale, a.samples, W / 2, H / 2)
    light(sc, "key", (W / 2 - 30, -H / 2 + 25, 40), 9000, 20, (1.0, 0.97, 0.94), (W / 2, -H / 2, 0))
    light(sc, "fill", (W / 2 + 25, -H / 2 - 20, 50), 3000, 40, (0.8, 0.85, 1.0), (W / 2, -H / 2, 0))
    light(sc, "rake", (-30, -H / 2 + 6, 5), 2500, 10, (0.95, 0.95, 1.0), (W / 2, -H / 2, 0.6))
    catcher = slab("catcher", -2, -2, W + 4, H + 4, -0.5, 0.0, material("catch", theme.PANEL))
    catcher.is_shadow_catcher = True
    rim = material("rim", (0.6, 0.61, 0.66), rough=0.22, metal=1.0)
    moulding = satin("moulding", (0.03, 0.03, 0.038), rough=0.5, coat=0.2, grain=0.4)
    m, bead, inner = 0.3, 0.16, 0.3   # margin in the cell, chrome width, moulding width
    outer = rounded_rect("rim", m, m, W - 2 * m, H - 2 * m, 0.0, 0.26, rim, 1.0, bevel=0.06, segs=3)
    hollow(outer, rounded_rect("rim_cut", m + bead + inner, m + bead + inner, W - 2 * (m + bead + inner),
                               H - 2 * (m + bead + inner), -1.0, 1.0, rim, 0.6))
    mould = rounded_rect("moulding", m + bead, m + bead, W - 2 * (m + bead), H - 2 * (m + bead), 0.0, 0.3,
                         moulding, 0.85, bevel=0.08, segs=4)
    hollow(mould, rounded_rect("mould_cut", m + bead + inner, m + bead + inner, W - 2 * (m + bead + inner),
                               H - 2 * (m + bead + inner), -1.0, 1.0, rim, 0.6))
    # (v60) a gap in the top rim for the title (theme.EQ_TITLE, a caption over it)
    for o, name in ((outer, "gap_rim"), (mould, "gap_mould")):
        hollow(o, slab(name, W / 2 - theme.EQ_TITLE_GAP / 2, -1.0, theme.EQ_TITLE_GAP, 2.5, -1.0, 1.0, rim))
    render(sc, a.out / "frame_eq.exr")


def main():
    a = args()
    a.out.mkdir(parents=True, exist_ok=True)
    {"deco": deco, "pads": pads, "fader": fader, "screens": screens, "frames": frames}[a.what](a)


main()
