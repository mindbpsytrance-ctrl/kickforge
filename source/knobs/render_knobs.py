"""KickForge knob art: a 3D LED-ring encoder rendered in Blender (Cycles, CPU).

The art covers Bitwig's native knob, which stays underneath (invisible) and takes the mouse.
Bitwig can only show still images, so the moving parts are separate images that panel
expressions show or hide from the knob's value:
  base_<colour>.exr        bezel, LED ring with every LED off, knob without its pointer,
                           and its drop shadow on the panel (shadow catcher)
  led_<colour>_<i>.exr     LED i lit, alone (everything else held out, so it is cut exactly)
  ptr_<k>.exr              the pointer at position k of POINTERS (same for every colour)
and layout.json for make_knob_svgs.py.

Looks: a dark anodised bezel with a chrome lip and a smoked LED channel, a knurled
soft-touch silicone skirt and a spun-aluminium cap (radial anisotropic highlights), lit from the top left, seen
from 18 degrees in front (orthographic) so the skirt shows.
The LED colours run along a palette shared by the whole device (PALETTE): each part of the
device takes its own stretch of it.

Usage: blender -b -P render_knobs.py -- [--out DIR] [--size PX] [--samples N]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import theme  # noqa: E402
from theme import PALETTE, SECTIONS as COLOURS, linear  # noqa: E402  (one palette for the device)

LEDS = 15
# the pointer stops on every LED and at 4 points between two: 71 positions, 3.9 degrees apart
# (v32: 29 positions, 10 degrees apart, and turning a knob felt notched)
POINTERS = 5 * (LEDS - 1) + 1
SWEEP = 270.0
START = 225.0               # first LED angle (degrees, counter-clockwise from +X), then clockwise
TILT = theme.VIEW_TILT      # (v42: the device's one angle, 12; v41: 24, v38: 18) camera tilt from straight down (degrees), from the front (-Y)

# Geometry, in units of the art's half size (the camera frames +-ORTHO/2).
ORTHO = 2.0
BEZEL_R = 0.93
LED_R = 0.745
LED_SIZE = 0.07
SKIRT_R = 0.52
SKIRT_H = 0.44              # (v41: 0.30 -> 0.44, a taller knob)
FLANGE_R, FLANGE_H = 0.60, 0.07   # (v41) a skirt flange round the grip's foot, as on hardware knobs
CAP_R = 0.33               # (v38: 0.47 -> 0.33: a ring of the silicone grip's top shows round the cap)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=HERE / "render")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--only-pointers", action="store_true", help="render the pointers only")
    p.add_argument("--no-pointers", action="store_true", help="leave the pointers as they are")
    # a notched selector (v37: the length's note value): N positions, one LED and one pointer
    # each, a printed tick at each; only the given colours
    p.add_argument("--detents", type=int, default=0, help="a selector with N notches (LEDs = pointers = N)")
    p.add_argument("--colours", default="", help="comma-separated colours (default: all)")
    return p.parse_args(argv)


def led_colour(name, i):
    a, b = (PALETTE[k] for k in COLOURS[name])
    t = i / (LEDS - 1)
    return linear(tuple(x + (y - x) * t for x, y in zip(a, b)))


def led_angle(i):
    return START - SWEEP * i / (LEDS - 1)


def ptr_angle(k):
    return START - SWEEP * k / (POINTERS - 1)


def principled(name, base, rough=0.4, metal=0.0, coat=0.0, aniso=0.0, radial=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Coat Weight"].default_value = coat
    if aniso:
        bsdf.inputs["Anisotropic"].default_value = aniso
        if radial:   # spun metal: highlights in rings round the centre
            tangent = nodes.new("ShaderNodeTangent")
            tangent.direction_type = "RADIAL"
            tangent.axis = "Z"
            m.node_tree.links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])
    return m


def grain(m, scale, strength):
    """A fine noise bump (bead-blasted / satin finish)."""
    nodes, links = m.node_tree.nodes, m.node_tree.links
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.002
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], nodes["Principled BSDF"].inputs["Normal"])
    return m


# knob units (the art's half size) per panel grid unit: the encoder, 2 x BEZEL_R across, is
# theme.KNOB_UNITS grid units
GRID = 2 * 0.93 / 10


def silicone(m):
    """The pads' silicone (render_panel_art.rubber, unlit; v38, so a knob's grip reads as the same
    material: before, a finer, four times shallower stipple, read as plastic), its sizes from grid
    units: a velvet sheen, some translucency, a stippled skin (Voronoi cells about 0.4 grid unit)
    and a mottled roughness."""
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Sheen Weight"].default_value = 0.7
    bsdf.inputs["Sheen Roughness"].default_value = 0.35
    bsdf.inputs["Subsurface Weight"].default_value = 0.25
    bsdf.inputs["Subsurface Radius"].default_value = tuple(v * GRID for v in (0.5, 0.5, 0.6))
    bsdf.inputs["Coat Weight"].default_value = 0.0
    scale = 2.3 / GRID
    coords = nodes.new("ShaderNodeTexCoord")
    stipple = nodes.new("ShaderNodeTexVoronoi")
    stipple.feature = "SMOOTH_F1"
    stipple.inputs["Scale"].default_value = scale
    stipple.inputs["Randomness"].default_value = 0.85
    links.new(coords.outputs["Object"], stipple.inputs["Vector"])
    mottle = nodes.new("ShaderNodeTexNoise")
    mottle.inputs["Scale"].default_value = 1.4 / GRID
    mottle.inputs["Detail"].default_value = 4.0
    links.new(coords.outputs["Object"], mottle.inputs["Vector"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.45
    rough.inputs["To Max"].default_value = 0.68
    links.new(mottle.outputs["Fac"], rough.inputs["Value"])
    links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.09 * GRID
    links.new(stipple.outputs["Distance"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def lathe(m):
    """Concentric lathe rings on a spun cap (with its radial anisotropy)."""
    nodes, links = m.node_tree.nodes, m.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    rings = nodes.new("ShaderNodeTexWave")
    rings.wave_type = "RINGS"
    rings.rings_direction = "Z"
    rings.inputs["Scale"].default_value = 60.0
    rings.inputs["Distortion"].default_value = 1.5
    rings.inputs["Detail"].default_value = 1.0
    links.new(coords.outputs["Object"], rings.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.001
    links.new(rings.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], nodes["Principled BSDF"].inputs["Normal"])
    return m


def set_emit(m, colour, strength):
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.inputs["Base Color"].default_value = (*[x * (0.9 if strength > 0.5 else 0.06) for x in colour], 1.0)


def finish(obj, mat, smooth=True):
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    obj.data.materials.append(mat)
    return obj


def cylinder(name, radius, depth, z, mat, bevel=0.0, segs=4, verts=192):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segs
        mod.limit_method = "ANGLE"
        mod.harden_normals = False
    return finish(obj, mat)


def torus(name, major, minor, z, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=192,
                                     minor_segments=18, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    return finish(obj, mat)


def knurled_skirt(mat):
    """A grip: a prism with RIDGES rounded ridges, slightly tapered to the top."""
    ridges, steps = 64, 4
    bm = bmesh.new()
    rings = []
    for z, scale in ((0.0, 1.0), (SKIRT_H, 0.94)):
        ring = []
        for j in range(ridges * steps):
            a = 2 * math.pi * j / (ridges * steps)
            bump = 0.5 + 0.5 * math.cos(2 * math.pi * (j % steps) / steps)
            r = SKIRT_R * scale * (0.962 + 0.038 * bump)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    n = len(rings[0])
    for j in range(n):
        bm.faces.new((rings[0][j], rings[0][(j + 1) % n], rings[1][(j + 1) % n], rings[1][j]))
    bm.faces.new(rings[1])
    mesh = bpy.data.meshes.new("skirt")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("skirt", mesh)
    bpy.context.collection.objects.link(obj)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = 0.012
    mod.segments = 2
    mod.limit_method = "ANGLE"
    return finish(obj, mat)


def pointer(mat):
    """A white line set into the cap and down the skirt; turned by rotation_euler.z."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    mesh = bpy.data.meshes.new("pointer")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("pointer", mesh)
    bpy.context.collection.objects.link(obj)
    # a bar from 0.16 across the cap and the grip's top to its edge, plus a notch down the skirt
    # (v38; before, the cap covered the grip's top and the bar stopped at the cap's edge)
    edge = SKIRT_R * 0.94 - 0.01
    for v in obj.data.vertices:
        x, y, z = v.co
        v.co = ((x + 0.5) * (edge - 0.16) + 0.16, y * 0.052, SKIRT_H + 0.0185 + z * 0.037)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (SKIRT_R * 0.985 + x * 0.03, y * 0.052, SKIRT_H * 0.5 + z * SKIRT_H * 0.9)
    notch = bpy.data.meshes.new("notch")
    bm.to_mesh(notch)
    bm.free()
    obj2 = bpy.data.objects.new("pointer_notch", notch)
    bpy.context.collection.objects.link(obj2)
    obj2.parent = obj
    for o in (obj, obj2):
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = 0.008
        mod.segments = 2
        o.data.materials.append(mat)
    return obj


def scene_setup(size, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.seed = 7
    sc.cycles.use_animated_seed = False
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    fmt = sc.render.image_settings
    fmt.file_format = "OPEN_EXR"
    fmt.color_depth = "32"
    fmt.color_mode = "RGBA"

    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.06, 1.0)
    sc.world = world

    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = ORTHO
    cam_obj = bpy.data.objects.new("cam", cam)
    t = math.radians(TILT)
    cam_obj.location = (0, -10 * math.sin(t), 10 * math.cos(t) + 0.1)
    cam_obj.rotation_euler = (t, 0, 0)
    sc.collection.objects.link(cam_obj)
    sc.camera = cam_obj

    # key: a soft box at the top left (its shadow falls to the bottom right); a cool rim light
    # from behind on the right for the chrome edges; a low warm fill from the front
    # (v41: the key a little lower, 4.2 -> 3.6: a longer shadow, more relief)
    for name, loc, energy, size_, colour in (("key", (-2.6, 2.4, 3.6), 230, 2.2, (1.0, 0.97, 0.92)),
                                             ("rim", (3.0, 3.0, 1.6), 90, 1.2, (0.75, 0.85, 1.0)),
                                             ("fill", (0.5, -4.0, 2.5), 40, 4.0, (1.0, 0.92, 0.85))):
        light = bpy.data.lights.new(name, "AREA")
        light.energy = energy
        light.size = size_
        light.color = colour
        obj = bpy.data.objects.new(name, light)
        obj.location = loc
        sc.collection.objects.link(obj)
        obj.rotation_euler = (-obj.location.normalized()).to_track_quat("-Z", "Y").to_euler()
    return sc


def build():
    bezel = grain(principled("bezel", (0.016, 0.016, 0.022), rough=0.38, coat=0.45), 900.0, 0.08)
    channel = principled("channel", (0.004, 0.004, 0.007), rough=0.12, coat=1.0)
    chrome = principled("chrome", (0.82, 0.83, 0.86), rough=0.12, metal=1.0)
    # the grip: soft-touch silicone over the knurls (cells about 2 screen px at Bitwig's size)
    skirt = silicone(principled("skirt", linear(theme.RUBBER), rough=0.55))
    cap = lathe(principled("cap", (0.56, 0.57, 0.60), rough=0.22, metal=1.0, aniso=0.9, radial=True))
    paint = principled("ticks", (0.85, 0.85, 0.88), rough=0.5)
    white = principled("pointer", (0.92, 0.92, 0.9), rough=0.35)
    bsdf = white.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.9

    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0, 0, -0.08))
    catcher = bpy.context.object
    catcher.name = "shadow"
    catcher.is_shadow_catcher = True

    cylinder("bezel", BEZEL_R, 0.08, -0.04, bezel, bevel=0.03)
    torus("lip", BEZEL_R - 0.01, 0.012, 0.0, chrome)
    torus("channel", LED_R, LED_SIZE * 1.55, -0.125, channel)   # top under the LEDs
    torus("lip_in", 0.625, 0.008, 0.0, chrome)
    # the grip's foot: a flange, its top chamfered, a fine chrome line round its edge (v41)
    cylinder("flange", FLANGE_R, FLANGE_H, FLANGE_H / 2, skirt, bevel=0.03, segs=3)
    torus("flange_edge", FLANGE_R - 0.012, 0.006, FLANGE_H - 0.004, chrome)
    # printed ticks outside the ring: min and max; on a selector, one per notch
    for angle in ([START - SWEEP * k / (LEDS - 1) for k in range(LEDS)] if DETENTS else (START, START - SWEEP)):
        a = math.radians(angle)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.86 * math.cos(a), 0.86 * math.sin(a), 0.002))
        tick = bpy.context.object
        tick.name = f"tick{angle:.0f}"
        tick.scale = (0.055, 0.012, 0.004)
        tick.rotation_euler.z = a
        finish(tick, paint, smooth=False)
    leds = []
    for i in range(LEDS):
        a = math.radians(led_angle(i))
        m = principled(f"led{i}", (0.05, 0.05, 0.05), rough=0.1, coat=1.0)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=LED_SIZE,
                                             location=(LED_R * math.cos(a), LED_R * math.sin(a), -0.005))
        obj = bpy.context.object
        obj.name = f"led{i}"
        obj.scale = (1.0, 1.0, 0.5)
        finish(obj, m)
        leds.append((obj, m))
    knurled_skirt(skirt)
    cylinder("cap", CAP_R, 0.04, SKIRT_H + 0.005, cap, bevel=0.015)
    torus("cap_edge", CAP_R - 0.004, 0.01, SKIRT_H + 0.022, chrome)
    ptr = pointer(white)
    return leds, ptr


DETENTS = 0


def main():
    global LEDS, POINTERS, DETENTS
    a = args()
    if a.detents:
        LEDS = POINTERS = DETENTS = a.detents
    colours = [c for c in a.colours.split(",") if c] or list(COLOURS)
    a.out.mkdir(parents=True, exist_ok=True)
    sc = scene_setup(a.size, a.samples)
    leds, ptr = build()
    lights = [o for o in sc.objects if o.type == "LIGHT"]
    meshes = [o for o in sc.objects if o.type == "MESH"]
    catcher = bpy.data.objects["shadow"]
    ptr_parts = {ptr, *ptr.children}

    def render(path, keep=None, hide=(), border=None):
        """keep: the objects drawn; everything else is held out (cut away, still occluding).
        hide: objects left out of the render altogether. border: (x0, y0, x1, y1) 0..1, the
        only part rendered (the rest stays empty)."""
        for o in meshes:
            o.is_holdout = keep is not None and o not in keep and o is not catcher
            o.hide_render = o in hide or (keep is not None and o is catcher)
        sc.render.use_border = border is not None
        sc.render.use_crop_to_border = False
        if border:
            (sc.render.border_min_x, sc.render.border_min_y,
             sc.render.border_max_x, sc.render.border_max_y) = border
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print("rendered", path)

    def box(obj, r=0.075):
        p = world_to_camera_view(sc, sc.camera, obj.matrix_world.translation)
        return (max(0.0, p.x - r), max(0.0, p.y - r), min(1.0, p.x + r), min(1.0, p.y + r))

    for name in ([] if a.only_pointers else colours):
        for i, (obj, m) in enumerate(leds):
            set_emit(m, led_colour(name, i), 0.025)
        render(a.out / f"base_{name}.exr", hide=ptr_parts)
        ptr.rotation_euler.z = math.radians(ptr_angle(0))
        for i, (obj, m) in enumerate(leds):
            set_emit(m, led_colour(name, i), 4.0)
            render(a.out / f"led_{name}_{i}.exr", hide=ptr_parts, border=box(obj))
            set_emit(m, led_colour(name, i), 0.025)
    for k in range(0 if a.no_pointers else POINTERS):
        ptr.rotation_euler.z = math.radians(ptr_angle(k))
        render(a.out / f"ptr_{k}.exr", keep=ptr_parts)

    layout = {"leds": LEDS, "pointers": POINTERS, "colours": colours, "led_mode": "difference",
              "palette": PALETTE, "sections": COLOURS}
    (a.out / "layout.json").write_text(json.dumps(layout, indent=1))
    bpy.ops.wm.save_as_mainfile(filepath=str(a.out / "knob_encoder.blend"))


main()
