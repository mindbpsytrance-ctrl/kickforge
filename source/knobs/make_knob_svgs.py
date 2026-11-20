"""Turn the Blender encoder renders into KickForge knob art: glow, tone map, PNG and SVG.

Reads render/base_<colour>.exr, render/emit_<colour>.exr and render/layout.json
(render_knobs.py) and writes, for each colour,
  out/base_<colour>.svg       the encoder with its LEDs off (opaque disc: hides the native knob)
  out/led_<colour>_<i>.svg    LED i lit, with its glow: the PNG holds only the LED's own box,
                              placed in an SVG the size of the base, so they line up
plus out/layout.json (LED count, for build_kick.py) and out/preview.png (each colour at a few
values, as Bitwig will show them). The encoder is --px wide (SVG px), centred across an SVG the size of its box, at its bottom (v57).

Usage: python make_knob_svgs.py [--px 40] [--embed 4]
"""
import argparse
import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
import OpenImageIO as oiio
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import theme  # noqa: E402

# Every SVG is the encoder's box (theme.CELL x theme.KNOB_BOX grid units), the encoder centred in
# it: Bitwig hangs an image larger than its cell from the top left, so the image fills the cell.
BOX_W, BOX_H = theme.CELL * theme.PX_PER_UNIT, theme.KNOB_BOX * theme.PX_PER_UNIT
DY = theme.KNOB_DY * theme.PX_PER_UNIT   # (v58: --box / --dy for the EQ's small encoders, out/small)
NAMES = ("pitch", "amp", "click", "global")


def read_exr(path):
    img = oiio.ImageInput.open(str(path))
    if img is None:
        raise SystemExit(f"cannot read {path}: {oiio.geterror()}")
    data = img.read_image(format="float")
    img.close()
    return np.asarray(data, dtype=np.float32)          # H x W x 4, premultiplied linear


def box_blur(a, r):
    if r < 1:
        return a
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
        n = a.shape[axis]
        a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
             - np.take(c, np.arange(0, n), axis=axis)) / (2 * r + 1)
    return a


def gauss(a, sigma):
    r = max(1, int(round(np.sqrt(12 * sigma * sigma / 3 + 1) / 2)))
    for _ in range(3):
        a = box_blur(a, r)
    return a


def finish(premult, emit, spread=1.0):
    """Glow from the emission, soft tone map, straight-alpha sRGB RGBA image. spread scales the
    glow's two radii (v56: the pads' tighter, their legends sharp)."""
    rgb, alpha = premult[..., :3], premult[..., 3:4]
    size = rgb.shape[0]
    if emit is not None:
        glow = 0.45 * gauss(emit, size * 0.013 * spread) + 0.32 * gauss(emit, size * 0.04 * spread)
        rgb = rgb + glow
        lum = glow @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        alpha = np.clip(alpha + 1.4 * lum[..., None], 0.0, 1.0)
    rgb = 1.0 - np.exp(-rgb)
    alpha = np.maximum(alpha, rgb.max(axis=-1, keepdims=True))
    straight = np.where(alpha > 1e-5, rgb / np.maximum(alpha, 1e-5), 0.0)
    srgb = np.where(straight <= 0.0031308, straight * 12.92, 1.055 * np.power(straight, 1 / 2.4) - 0.055)
    out = np.concatenate([np.clip(srgb, 0, 1), alpha], axis=-1)
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")


def round_off(im):
    """Fade the base out past the bezel and its shadow: the shadow catcher also catches a faint
    shade over the whole frame, which showed as a square round each knob on the panel."""
    a = np.asarray(im).astype(np.float32)
    n = a.shape[0]
    yy, xx = np.mgrid[0:n, 0:n] / n - 0.5
    r = np.hypot(xx - 0.012, yy - 0.018)       # the shadow falls a little to the bottom right
    a[..., 3] *= np.clip((0.5 - r) / 0.035, 0.0, 1.0)
    return Image.fromarray((a + 0.5).astype(np.uint8), "RGBA")


def png_b64(im):
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def svg(px, parts):
    """parts: (image, x, y, w, h) in SVG px of the px x px encoder, centred across the box and
    theme.KNOB_DY units down (v57: at its bottom, on the caption; before, centred)."""
    dx, dy = (BOX_W - px) / 2, DY
    assert dy + px <= BOX_H + 0.01
    body = "".join(
        f'<image x="{x + dx:.3f}" y="{y + dy:.3f}" width="{w:.3f}" height="{h:.3f}" '
        f'xlink:href="data:image/png;base64,{png_b64(im)}"/>' for im, x, y, w, h in parts)
    # Bitwig renders SVG with Batik (SVG 1.1): <image> needs xlink:href, a plain href is refused
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{BOX_W:.2f}" height="{BOX_H:.2f}" viewBox="0 0 {BOX_W:.2f} {BOX_H:.2f}">{body}</svg>')


def pointer_index(value, pointers):
    """The pointer position shown for a value 0..1 (the nearest of POINTERS)."""
    return min(pointers - 1, max(0, int(value * (pointers - 1) + 0.5)))


def composite(base, leds, ptrs, value):
    """What Bitwig shows for a value 0..1: LED i lit once the pointer reaches it."""
    k = pointer_index(value, len(ptrs))
    im = base.copy()
    for i, led in enumerate(leds):
        if k * (len(leds) - 1) >= i * (len(ptrs) - 1):
            im.alpha_composite(led)
    im.alpha_composite(ptrs[k])
    return im


def cropped(name, im, out, px, k, embed):
    """An image of the encoder's size, keeping only its non-empty box."""
    box = im.getchannel("A").point(lambda v: 255 if v > 2 else 0).getbbox()
    x0, y0, x1, y1 = box
    crop = im.crop(box)
    cw, ch = max(1, round((x1 - x0) * k * embed)), max(1, round((y1 - y0) * k * embed))
    text = svg(px, [(crop.resize((cw, ch), Image.LANCZOS), x0 * k, y0 * k, (x1 - x0) * k, (y1 - y0) * k)])
    (out / f"{name}.svg").write_text(text, encoding="utf-8")
    return len(text)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--src", type=Path, default=HERE / "render")
    cli.add_argument("--out", type=Path, default=HERE / "out")
    # theme.KNOB_UNITS grid units at theme.PX_PER_UNIT SVG px a unit
    cli.add_argument("--px", type=int, default=round(theme.KNOB_UNITS * theme.PX_PER_UNIT), help="displayed size of the encoder, Bitwig px at 100 %%")
    cli.add_argument("--embed", type=float, default=4.0, help="PNG pixels per SVG px (HiDPI)")
    cli.add_argument("--box", type=float, nargs=2, help="the SVG's box, grid units (default theme.CELL x theme.KNOB_BOX)")
    cli.add_argument("--dy", type=float, help="the encoder this far down its box, grid units (default theme.KNOB_DY)")
    a = cli.parse_args()
    global BOX_W, BOX_H, DY
    if a.box:
        BOX_W, BOX_H = (u * theme.PX_PER_UNIT for u in a.box)
    if a.dy is not None:
        DY = a.dy * theme.PX_PER_UNIT
    a.out.mkdir(parents=True, exist_ok=True)
    for old in a.out.glob("*"):
        if old.is_file():   # (out/sel/, out/small/: made by their own runs)
            old.unlink()
    lay = json.loads((a.src / "layout.json").read_text())
    n, npt = lay["leds"], lay["pointers"]
    (a.out / "layout.json").write_text(json.dumps({"leds": n, "pointers": npt, "px": a.px}, indent=1))
    res = int(round(a.px * a.embed))
    ptrs = []
    for k in range(npt):
        im = finish(read_exr(a.src / f"ptr_{k}.exr"), None)
        cropped(f"ptr_{k}", im, a.out, a.px, a.px / im.size[0], a.embed)
        ptrs.append(im)
    images = {}
    for name in lay["colours"]:
        base = round_off(finish(read_exr(a.src / f"base_{name}.exr"), None))
        k = a.px / base.size[0]
        (a.out / f"base_{name}.svg").write_text(svg(a.px, [(base.resize((res, res), Image.LANCZOS),
                                                            0, 0, a.px, a.px)]), encoding="utf-8")
        base_raw = read_exr(a.src / f"base_{name}.exr")
        leds, sizes = [], []
        for i in range(n):
            raw = read_exr(a.src / f"led_{name}_{i}.exr")
            if lay.get("led_mode") == "difference":
                # the whole scene with LED i lit, in a box round it: the light it adds (on the
                # lens, the channel, the bezel) is the lit render minus the base
                light = np.clip(raw[..., :3] - base_raw[..., :3], 0.0, None) * (raw[..., 3:4] > 0)
                light = np.where(light.max(axis=-1, keepdims=True) > 0.004, light, 0.0)
                raw = np.concatenate([light, np.zeros_like(light[..., :1])], axis=-1)
            led = finish(raw, raw[..., :3])
            sizes.append(cropped(f"led_{name}_{i}", led, a.out, a.px, k, a.embed))
            leds.append(led)
        images[name] = (base, leds)
        print(f"{name}: base {len((a.out / f'base_{name}.svg').read_text()) // 1024} KiB, "
              f"LED {min(sizes) // 1024}-{max(sizes) // 1024} KiB")

    tile, values = 200, (0.0, 0.3, 0.62, 1.0)
    names = lay["colours"]
    sheet = Image.new("RGBA", (tile * len(values) + 20, tile * len(names) + 20), (16, 16, 22, 255))
    for r, name in enumerate(names):
        for col, value in enumerate(values):
            im = composite(*images[name], ptrs, value)
            sheet.alpha_composite(im.resize((tile - 10, tile - 10), Image.LANCZOS), (15 + col * tile, 15 + r * tile))
    sheet.convert("RGB").save(a.out / "preview.png")
    step = a.px + 10
    small = Image.new("RGBA", (len(names) * step + 10, a.px + 15), (16, 16, 22, 255))
    for col, name in enumerate(names):
        im = composite(*images[name], ptrs, values[col % len(values)] or 0.45)
        small.alpha_composite(im.resize((a.px, a.px), Image.LANCZOS), (8 + col * step, 7))
    small.convert("RGB").resize((small.width * 3, small.height * 3), Image.NEAREST).save(
        a.out / "preview_actual_size_x3.png")
    print("preview", a.out / "preview.png")


if __name__ == "__main__":
    main()
