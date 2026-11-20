"""Turn the panel renders (render_panel_art.py) into KickForge's panel SVGs.

  out/deco_<piece>.svg      the panel art cut into theme.DECO_PIECES (opaque, JPEG inside)
  out/pads_<group>_<k>.svg  switch group <group> with pad k lit and every label printed on
  out/fader_<k>.svg         the tune fader with its cap on notch k (opaque, over the panel art)
  out/lcd_note_<k>.svg      the tune's mini LED screen showing note k of the fader (C0 .. C1)
  out/lcd_div_<tab>_<i>.svg the length's mini LED screen showing note value i (theme.DIV_NAMES),
                            in the tab's colour (opaque, over the panel art, like the fader)
  out/glass_view.svg        the glass over the curve view (above the curve, transparent)
  out/panel.json            each SVG's grid cell (x, y, w, h) for build_kick.py
  out/panel_preview.png     the panel with the art, as laid out (no controls)

A pad group's image covers its native button group grown by 1 unit each side (cut at the panel's
edge) and is opaque (the panel art under it is baked in), so it hides the native buttons.
Usage: python3 make_panel_svgs.py [--src render] [--out out]
"""
import argparse
import base64
import io
import os
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import theme  # noqa: E402
from make_knob_svgs import finish, gauss, read_exr  # noqa: E402

FONT = os.path.join(os.environ.get("KICKFORGE_FONTS", "/usr/share/fonts/inter"), "InterNerdFontPropo-Bold.otf")


def b64(im, fmt):
    buf = io.BytesIO()
    if fmt == "JPEG":
        # (v51) every opaque image (the panel art and what has it baked in: pads, mini screens,
        # fader, covers): quality 92, colour at full resolution (no 4:2:0, which bled the LCDs'
        # saturated glow); a quarter of the PNG's size, no visible difference
        # (the panel art's alpha, at its outer edge only, is dropped as it always was: covers are cut from it)
        im.convert("RGB").save(buf, "JPEG", quality=92, subsampling=0, optimize=True, progressive=False)
    else:
        im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def svg(im, w_units, h_units, fmt):
    w, h = w_units * theme.PX_PER_UNIT, h_units * theme.PX_PER_UNIT
    mime = "jpeg" if fmt == "JPEG" else "png"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w:.2f}" height="{h:.2f}" viewBox="0 0 {w:.2f} {h:.2f}"><image x="0" y="0" '
            f'width="{w:.2f}" height="{h:.2f}" preserveAspectRatio="none" '
            f'xlink:href="data:image/{mime};base64,{b64(im, fmt)}"/></svg>')


def bloom(raw, threshold=0.65, spread=1.0):
    """finish() with a glow from what is brighter than threshold."""
    rgb = raw[..., :3]
    emit = np.clip(rgb - threshold, 0.0, None)
    return finish(raw, emit if emit.max() > 0 else None, spread)


def crop_units(im, scale, x0, y0, x1, y1):
    return im.crop((round(x0 * scale), round(y0 * scale), round(x1 * scale), round(y1 * scale)))


# --- the mini LED screens (v37): 14-segment characters on the window's glass ------------------
# segment ends in a character box of width CW x height 1 (y down); H.. are the diagonals
CW = 0.6
SEGMENTS = {"A": ((0, 0), (1, 0)), "B": ((1, 0), (1, .5)), "C": ((1, .5), (1, 1)), "D": ((0, 1), (1, 1)),
            "E": ((0, .5), (0, 1)), "F": ((0, 0), (0, .5)), "G1": ((0, .5), (.5, .5)), "G2": ((.5, .5), (1, .5)),
            "I": ((.5, 0), (.5, .5)), "L": ((.5, .5), (.5, 1)), "H": ((0, 0), (.5, .5)), "J": ((1, 0), (.5, .5)),
            "K": ((0, 1), (.5, .5)), "N": ((1, 1), (.5, .5))}
GLYPHS = {"0": "A B C D E F", "1": "I L", "2": "A B G1 G2 E D", "3": "A B C D G2", "4": "F G1 G2 B C",
          "6": "A F E D C G1 G2", "8": "A B C D E F G1 G2", "/": "J K", "T": "A I L", "D": "A B C D I L",
          "B": "A B C D G2 I L", "A": "A B C E F G1 G2", "R": "A B F E G1 G2 N", "C": "A F E D",
          "E": "A D E F G1 G2", "F": "A E F G1 G2", "G": "A F E D C G2", " ": "",
          "H": "B C E F G1 G2", "I": "A D I L", "N": "B C E F H N", "O": "A B C D E F", "S": "A F G1 G2 C D",
          "P": "A B E F G1 G2", "K": "E F G1 J N", "W": "B C E F K N", "L": "D E F", "U": "B C D E F",
          "V": "E F K J", "Y": "H J L", "M": "B C E F H J", "X": "H J K N",   # (v49: X, for FX)
          "9": "A B C D F G1 G2", "5": "A F G1 G2 C D", "7": "A B C"}   # (v62: 909 / 808 HAT)
# the sharp: a narrow raised sign of its own (two uprights, two bars), as on a tuner's display
SHARP = {"u1": ((.32, .04), (.32, .62)), "u2": ((.72, .02), (.72, .6)), "b1": ((.0, .22), (1, .16)),
         "b2": ((.0, .46), (1, .4))}
SHARP_W = 0.42
SLANT = 0.1


def seg_polygon(p, q, ox, oy, h, w, t, diagonal):
    """A segment from p to q (character units) as a pointed bar, in pixels; slanted forward."""
    # (small gaps: at Bitwig's size, about 10 px a character, wider ones cut a 1 or a / into dots)
    ins = (0.5 * t if diagonal else 0.08 * t) + 0.008 * h
    (x0, y0), (x1, y1) = ((ox + t / 2 + u * (w - t), oy + t / 2 + v * (h - t)) for u, v in (p, q))
    dx, dy = x1 - x0, y1 - y0
    n = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    dx, dy = dx / n, dy / n
    nx, ny = -dy, dx
    ax, ay, bx, by = x0 + dx * ins, y0 + dy * ins, x1 - dx * ins, y1 - dy * ins
    s = t / 2
    pts = [(ax, ay), (ax + dx * s + nx * s, ay + dy * s + ny * s), (bx - dx * s + nx * s, by - dy * s + ny * s),
           (bx, by), (bx - dx * s - nx * s, by - dy * s - ny * s), (ax + dx * s - nx * s, ay + dy * s - ny * s)]
    if diagonal:   # square ends: a plain bar
        pts = [(ax + nx * s, ay + ny * s), (bx + nx * s, by + ny * s), (bx - nx * s, by - ny * s), (ax - nx * s, ay - ny * s)]
    return [(x + (oy + h / 2 - y) * SLANT, y) for x, y in pts]


def lcd_layers(text, size, h, colour):
    """The lit segments and the unlit ("ghost") ones of text, centred in an image of size
    (w, h px; character height h): two float masks."""
    big = 4
    W, Hh = size[0] * big, size[1] * big
    ch = h * big
    t = 0.165 * ch   # (v56: 0.14 -> 0.165, bolder segments: they hold up at Bitwig's size)
    lit, ghost = Image.new("L", (W, Hh), 0), Image.new("L", (W, Hh), 0)
    dl, dg = ImageDraw.Draw(lit), ImageDraw.Draw(ghost)
    adv = [(SHARP_W if c == "#" else CW) * ch + 0.26 * ch for c in text]
    fit = min(1.0, 0.94 * W / (sum(adv) - 0.26 * ch))   # a long name: smaller characters
    ch, t = ch * fit, t * fit
    adv = [a * fit for a in adv]
    x = (W - (sum(adv) - 0.26 * ch)) / 2
    y = (Hh - ch) / 2
    for c, a in zip(text, adv):
        if c == "#":
            w = SHARP_W * ch
            for (u0, v0), (u1, v1) in SHARP.values():
                pts = [(x + u * w + (y + ch / 2 - (y + v * ch)) * SLANT, y + v * ch) for u, v in ((u0, v0), (u1, v1))]
                for d in (dg, dl):
                    d.line(pts, fill=255, width=max(1, round(t * 0.7)))
        else:
            w = CW * ch
            on = GLYPHS[c].split()
            for name, (p, q) in SEGMENTS.items():
                poly = seg_polygon(p, q, x, y, ch, w, t, name in ("H", "J", "K", "N"))
                dg.polygon(poly, fill=255)
                if name in on:
                    dl.polygon(poly, fill=255)
        x += a
    lit = np.asarray(lit.resize(size, Image.LANCZOS), dtype=np.float32) / 255.0
    ghost = np.asarray(ghost.resize(size, Image.LANCZOS), dtype=np.float32) / 255.0
    return lit, ghost


def lcd(back, housing, glass, scale, text, colour, text_h=None):
    """A mini LED screen: the window (housing, over the panel art back) with text lit on its glass
    in colour, behind a smoked filter tinted in it (v71), a glow round the lit segments."""
    im = back.copy()
    im.alpha_composite(housing)
    gx, gy, gw, gh = (round(v * scale) for v in glass)
    lit, ghost = lcd_layers(text, (gw, gh), 0.8 * gh if text_h is None else text_h * scale, colour)   # (v62: text_h, units)
    rgb = np.asarray(im, dtype=np.float32)[..., :3] / 255.0
    region = rgb[gy:gy + gh, gx:gx + gw]
    # (v71: a real window, not a flat black) the LEDs behind a smoked filter tinted in their own
    # colour: a deep tinted ground, a little lighter towards the top (the light from above through
    # the acrylic), shaded where the frame overhangs it (top and left most, the key light comes
    # from the top left), a soft broad reflection across its upper part (horizontal: v66's diagonal
    # sheen read as a shadow), a fine bright line at its top edge, and the lit segments' light
    # spreading faintly into the filter round them. The rendered glass's bevel is kept at its edge
    # (feathered over 0.15 unit). (v67-v70: one flat black; still no ghost segments)
    c = np.array(colour, dtype=np.float32)
    py, px = np.mgrid[0:gh, 0:gw].astype(np.float32)
    yu, xu = py / scale, px / scale                       # units from the glass's top left
    hu, wu = gh / scale, gw / scale
    edge = np.minimum(np.minimum(xu, wu - xu), np.minimum(yu, hu - yu))
    m = np.clip((edge - 0.15) / 0.15, 0, 1)[..., None]
    v = (py / max(gh - 1, 1))[..., None]                  # 0 top .. 1 bottom
    ground = 0.030 + 0.075 * c + (0.030 + 0.03 * c) * (1.0 - v) ** 2
    shade = (1.0 - 0.55 * np.exp(-yu / 0.55) - 0.35 * np.exp(-xu / 0.5)
             - 0.18 * np.exp(-(wu - xu) / 0.5) - 0.22 * np.exp(-(hu - yu) / 0.5))
    ground = ground * np.clip(shade, 0.25, 1.0)[..., None]
    sheen = np.clip((0.42 - v) / 0.42, 0, 1) ** 1.6 * 0.045
    ground = ground + sheen * np.array([0.9, 0.92, 1.0], np.float32) + (yu < 0.12)[..., None] * 0.035
    region = region * (1 - m) + ground * m
    core = c * 0.62 + 0.38      # a lit segment: the colour, hot (near white) at its core
    # (v55: sharper segments) the glow hugging the segments tight; (v71) and their light diffused
    # in the filter, wide and faint, in their colour (on the tinted ground it reads as light, not
    # as v66's dull cloud on black)
    glow = gauss(lit, 0.02 * gh)
    spread = gauss(lit, 0.16 * gh)
    out = region * (1 - lit[..., None]) + lit[..., None] * core
    out = out + glow[..., None] * c * 0.3 + spread[..., None] * c * 0.14 * m
    rgb[gy:gy + gh, gx:gx + gw] = np.clip(out, 0, 1)
    alpha = np.asarray(im, dtype=np.float32)[..., 3:4] / 255.0
    return Image.fromarray((np.concatenate([rgb, alpha], axis=-1) * 255 + 0.5).astype(np.uint8), "RGBA")


def labels(im, scale, w, h, names, lit):
    """Print the labels on the pads (same pad layout as render_panel_art.pads)."""
    n = len(names)
    gap = 0.55
    pw = (w + 0.3 - gap * (n - 1)) / n
    size = round(min(h * 0.46, pw * 0.36) * scale)
    font = ImageFont.truetype(FONT, size)
    text = Image.new("RGBA", im.size, (0, 0, 0, 0))
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for k, name in enumerate(names):
        cx = (0.85 + k * (pw + gap) + pw / 2) * scale
        cy = (0.85 + (h + 0.3) / 2) * scale
        on = k == lit
        colour = (250, 248, 255, 255) if on else (128, 128, 142, 255)
        ImageDraw.Draw(text).text((cx, cy), name, font=font, fill=colour, anchor="mm")
        if on:
            halo = tuple(round(255 * c) for c in theme.PAD_LIT) + (210,)
            ImageDraw.Draw(glow).text((cx, cy), name, font=font, fill=halo, anchor="mm")
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.35))
    out = im.copy()
    out.alpha_composite(glow)
    out.alpha_composite(text)
    return out


def glass(w, h, scale):
    """The glass over the curve view (arcade-cabinet screen), drawn above the curve: the
    shadow of the bezel's lip on the recessed screen (top and left), a light rim on the lower
    edge, a faint diagonal reflection, a bulge highlight in the top right corner, darker
    rounded corners. The middle stays almost clear (at most a few % over the curve)."""
    W, H = round(w * scale), round(h * scale)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) / scale       # grid units
    rgb = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)

    def over(colour, a):
        nonlocal rgb, alpha
        a = np.clip(a, 0.0, 1.0)
        out = a + alpha * (1 - a)
        rgb = np.where(out[..., None] > 1e-6,
                       (np.array(colour, np.float32) * a[..., None] + rgb * (alpha * (1 - a))[..., None])
                       / np.maximum(out, 1e-6)[..., None], 0.0)
        alpha = out

    dark, light = (0.0, 0.0, 0.01), (0.86, 0.88, 1.0)
    # the lip's shadow: deep along the top, lighter along the left, a hint right and bottom
    over(dark, 0.42 * np.exp(-yy / 0.55) + 0.28 * np.exp(-xx / 0.5)
         + 0.12 * np.exp(-(w - xx) / 0.35) + 0.10 * np.exp(-(h - yy) / 0.35))
    # light caught on the lower edge of the glass, 1 px
    over(light, 0.16 * np.exp(-((h - yy - 0.12) / 0.07) ** 2))
    # a broad diagonal reflection from the top left, and a narrow streak across it
    d = (xx / w + yy / h)                                          # 0 top left .. 2 bottom right
    over(light, 0.06 * np.clip(1 - d / 0.8, 0, 1) ** 1.5)
    s = (xx / w - 0.62 + (yy / h) * 0.55)
    over(light, 0.04 * np.exp(-(s / 0.03) ** 2) * np.clip(1 - yy / h, 0, 1))
    over(light, 0.025 * np.exp(-((s - 0.09) / 0.012) ** 2) * np.clip(1 - yy / h, 0, 1))
    # the bulge of the glass catching the light in the top right corner
    ex, ey = (xx - w * 0.9) / (w * 0.13), (yy - h * 0.1) / (h * 0.11)
    over(light, 0.09 * np.exp(-(ex * ex + ey * ey) * 1.6))
    # corners: a soft vignette, then rounded off (radius 0.6) in the bezel's black
    cx, cy = np.minimum(xx, w - xx), np.minimum(yy, h - yy)
    corner = np.hypot(np.clip(3.0 - cx, 0, None), np.clip(3.0 - cy, 0, None)) / 3.0
    over(dark, 0.16 * np.clip(corner - 0.55, 0, None) / 0.45)
    r = 0.6
    out = np.hypot(np.clip(r - cx, 0, None), np.clip(r - cy, 0, None)) - r
    over((0.012, 0.012, 0.016), 0.9 * np.clip(out * scale + 0.5, 0, 1))
    pixels = np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], axis=-1)
    srgb = np.where(pixels[..., :3] <= 0.0031308, pixels[..., :3] * 12.92,
                    1.055 * np.power(pixels[..., :3], 1 / 2.4) - 0.055)
    out_px = np.concatenate([srgb, pixels[..., 3:]], axis=-1)
    return Image.fromarray((np.clip(out_px, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--src", type=Path, default=HERE / "render")
    cli.add_argument("--out", type=Path, default=HERE / "out")
    cli.add_argument("--scale", type=float, default=15.0, help="render px per grid unit")
    cli.add_argument("--fader-scale", type=float, default=24.0, help="the fader's render px per grid unit")
    a = cli.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for old in list(a.out.glob("deco_*.svg")) + list(a.out.glob("pads_*.svg")) + list(a.out.glob("glass_*.svg")) \
            + list(a.out.glob("fader_*.svg")) + list(a.out.glob("strip_*.svg")) + list(a.out.glob("lcd_*.svg")) + list(a.out.glob("cap_*.svg")) + list(a.out.glob("cover_*.svg")):
        old.unlink()
    cells = {}
    W, H = theme.PANEL_W, theme.PANEL_H
    # v40: two finishes, the dark panel (deco.exr) and the white one (deco_light.exr, names
    # ending in _light): everything laid over the panel art is made over each
    looks = [("", a.src / "deco.exr")] + ([("_light", a.src / "deco_light.exr")]
                                         if (a.src / "deco_light.exr").exists() else [])
    preview = None
    for sfx, deco_path in looks:
        raw = read_exr(deco_path)
        if sfx:   # the white panel: a bright white, as a white plastic controller's (v40)
            raw = raw.copy()
            raw[..., :3] *= theme.LIGHT_EXPOSURE
        deco = bloom(raw, 2.5 if sfx else 0.8)
        if preview is None:
            preview = deco.copy()
        for name, (x, y, w, h) in theme.DECO_PIECES.items():
            piece = crop_units(deco, a.scale, x, y, x + w, y + h)
            if sfx and name.startswith("cheek"):
                # the walnut as rendered (not brightened), the white faceplate beside it
                wood = crop_units(bloom(read_exr(deco_path), 0.8), a.scale, x, y, x + w, y + h)
                wx0 = 0 if x < W / 2 else round((w - theme.CHEEK) * a.scale)
                box = (wx0, 0, wx0 + round(theme.CHEEK * a.scale), piece.size[1])
                piece = piece.copy()
                piece.paste(wood.crop(box), box[:2])
            # (v61) the right cheek the left one mirrored: the key light comes from the left, so the
            # right cheek rendered darker and flatter, as if of another shape (seen in Bitwig)
            cw = round(theme.CHEEK * a.scale)
            if name == "cheek_l":
                left_cheek = piece.crop((0, 0, cw, piece.size[1]))
            elif name == "cheek_r":
                piece = piece.copy()
                piece.paste(ImageOps.mirror(left_cheek), (piece.size[0] - cw, 0))
            (a.out / f"deco_{name}{sfx}.svg").write_text(svg(piece, w, h, "JPEG"), encoding="utf-8")
            cells[f"deco_{name}{sfx}"] = [x, y, w, h]
        meta = json.loads((a.src / "pads.json").read_text())
        for group, (w, h, names) in theme.PAD_GROUPS.items():
            gx, gy = theme.PAD_AT[group]
            # the rendered image covers (gx - 1, gy - 1, w + 2, h + 2); keep what is on the panel
            x0, y0 = max(gx - 1, 0), max(gy - 1, 0)
            x1, y1 = min(gx + w + 1, W), min(gy + h + 1, H)
            # (v68) the theme switch: its image as wide as theme.TOGGLE_IMAGE (the pad on the panel art)
            ex0, ey0, ew, eh = theme.TOGGLE_IMAGE if group == "panel" else (x0, y0, x1 - x0, y1 - y0)
            for k in range(len(names)):
                raw = read_exr(a.src / f"{meta[group]['shape']}_{k}.exr")
                # the legend is part of the render (v35: lit through by the LED). (v56) The glow only
                # from what is brighter than an unlit legend (threshold 0.65 -> 2.4: the lit pad's
                # LED and legend), its radii 0.6 of the panel art's: the white legends glowed into
                # a 2.6 px haze at Bitwig's size, blurring their letters
                im = bloom(raw, threshold=2.4, spread=0.6)
                im = crop_units(im, a.scale, x0 - (gx - 1), y0 - (gy - 1), x1 - (gx - 1), y1 - (gy - 1))
                # opaque: laid over the panel art of its own cell, so nothing of the native buttons
                # under it shows through the soft edge of the well (their red selection line did)
                back = crop_units(deco, a.scale, x0, y0, x1, y1).convert("RGBA")
                back.alpha_composite(im.resize(back.size, Image.LANCZOS) if im.size != back.size else im)
                im = crop_units(deco, a.scale, ex0, ey0, ex0 + ew, ey0 + eh).convert("RGBA")
                im.paste(back, (round((x0 - ex0) * a.scale), round((y0 - ey0) * a.scale)))
                (a.out / f"pads_{group}_{k}{sfx}.svg").write_text(svg(im, ew, eh, "JPEG"), encoding="utf-8")
                cells[f"pads_{group}_{k}{sfx}"] = [ex0, ey0, ew, eh]
                if k == 0 and not sfx:
                    preview.alpha_composite(im, (round(ex0 * a.scale), round(ey0 * a.scale)))
        # the panel art laid over the theme switch's native half off its pad (v42)
        for cname, (x, y, w, h) in {**theme.TOGGLE_COVERS, **theme.FX_COVERS, **theme.KEY_COVERS}.items():
            piece = crop_units(deco, a.scale, x, y, x + w, y + h)
            (a.out / f"{cname}{sfx}.svg").write_text(svg(piece, w, h, "JPEG"), encoding="utf-8")
            cells[cname + sfx] = [x, y, w, h]
        # (v58) the FX tab's EQ frame: its render over the panel art, opaque
        if (a.src / "frame_eq.exr").exists():
            x, y, w, h = theme.EQ_RECT
            frame = bloom(read_exr(a.src / "frame_eq.exr"))
            back = crop_units(deco, a.scale, x, y, x + w, y + h).convert("RGBA").resize(frame.size, Image.LANCZOS)
            back.alpha_composite(frame)
            (a.out / f"frame_eq{sfx}.svg").write_text(svg(back, w, h, "JPEG"), encoding="utf-8")
            cells["frame_eq" + sfx] = [x, y, w, h]
        # the tune fader: opaque like the pads (the native slider under it must not show)
        fx, fy, fw, fh = theme.FADER_RECT
        back = crop_units(deco, a.scale, fx, fy, fx + fw, fy + fh).convert("RGBA")
        for k in range(theme.FADER_STEPS):
            im = bloom(read_exr(a.src / f"fader_{k}.exr"))
            # (v59) the soft shadows faded out over the cell's last 0.35 unit, not cut at its edge
            fade = round(0.35 * im.size[1] / fh)
            ramp = np.minimum(1.0, (np.minimum.outer(np.minimum(np.arange(im.size[1]), np.arange(im.size[1])[::-1]),
                                                     np.minimum(np.arange(im.size[0]), np.arange(im.size[0])[::-1])) + 0.5) / fade)
            al = np.asarray(im.getchannel("A"), dtype=np.float32) * ramp
            im.putalpha(Image.fromarray(al.round().astype(np.uint8)))
            base = back.resize(im.size, Image.LANCZOS)
            base.alpha_composite(im)
            (a.out / f"fader_{k}{sfx}.svg").write_text(svg(base, fw, fh, "JPEG"), encoding="utf-8")
            cells[f"fader_{k}{sfx}"] = [fx, fy, fw, fh]
            if k == 7 and not sfx:
                preview.alpha_composite(base.resize((round(fw * a.scale), round(fh * a.scale)), Image.LANCZOS),
                                        (round(fx * a.scale), round(fy * a.scale)))
        # the mini LED screens: the window (render_panel_art --what screens) over the panel art, the
        # value lit on its glass
        screens = json.loads((a.src / "screens.json").read_text())
        for name, s in screens.items():
            housing = finish(read_exr(a.src / f"screen_{name}.exr"), None)
            if name == "note":
                values = [("note", f"lcd_note_{i}", theme.NOTE_NAMES[i % 12] + str(i // 12), s["cell"])
                          for i in range(theme.FADER_STEPS)]
            elif name == "fx":   # (v49)
                values = [("fx_on" if i else "fx_off", f"lcd_fx_{i}", n, s["cell"]) for i, n in enumerate(theme.FX_NAMES)]
            elif name == "noise":
                values = [("click", f"lcd_noise_{i}", n, s["cell"]) for i, n in enumerate(theme.NOISE_NAMES)]
            else:   # (v39: one set per art, each over the panel at its own cell, theme.DIV_AT)
                values = [(tab, f"lcd_div_{tab}_{i}", d, cell) for tab, cell in theme.DIV_AT.items()
                          for i, d in enumerate(theme.DIV_NAMES)]
            for colour, out_name, label, (x, y, w, h) in values:
                k = housing.size[0] / w
                back = crop_units(deco, a.scale, x, y, x + w, y + h).convert("RGBA").resize(housing.size, Image.LANCZOS)
                im = lcd(back, housing, s["glass"], k, label, theme.LCD_COLOURS[colour], s.get("text_h"))
                (a.out / f"{out_name}{sfx}.svg").write_text(svg(im, w, h, "JPEG"), encoding="utf-8")
                cells[out_name + sfx] = [x, y, w, h]
                if not sfx and out_name in ("lcd_note_7", "lcd_div_pitch_4", "lcd_noise_7"):
                    preview.alpha_composite(im.resize((round(w * a.scale), round(h * a.scale)), Image.LANCZOS),
                                            (round(x * a.scale), round(y * a.scale)))
        # the controls' titles (v39): the pads' legend font, size and grey, on a clear ground
        font = ImageFont.truetype(FONT, round(theme.CAPTION_SIZE * a.scale * 2))
        for text in theme.CAPTIONS:
            w, h = theme.CAPTION_CELLS.get(text, (theme.CELL, 3))
            big = Image.new("RGBA", (round(w * a.scale * 2), round(h * a.scale * 2)), (0, 0, 0, 0))
            ImageDraw.Draw(big).text((big.size[0] / 2, big.size[1] / 2), text.upper(), font=font,
                                     fill=(*(theme.LEGEND_DARK if sfx else theme.LEGEND_GREY), 255), anchor="mm")
            im = big.resize((round(w * a.scale), round(h * a.scale)), Image.LANCZOS)
            name = theme.caption_name(text)
            (a.out / f"{name}{sfx}.svg").write_text(svg(im, w, h, "PNG"), encoding="utf-8")
            cells[name + sfx] = [0, 0, w, h]
    vx, vy, vw, vh = theme.VIEW_RECT
    pane = glass(vw, vh, a.scale)
    (a.out / "glass_view.svg").write_text(svg(pane, vw, vh, "PNG"), encoding="utf-8")
    cells["glass_view"] = [vx, vy, vw, vh]
    screen = Image.new("RGBA", pane.size, (14, 13, 30, 255))
    screen.alpha_composite(pane)
    preview.alpha_composite(screen, (round(vx * a.scale), round(vy * a.scale)))
    (a.out / "panel.json").write_text(json.dumps(cells, indent=1))
    preview.convert("RGB").save(a.out / "panel_preview.png")
    sizes = {p.name: p.stat().st_size // 1024 for p in a.out.glob("deco_*.svg")}
    if (a.src / "deco_light.exr").exists():   # the white panel's preview, with its pads and titles
        raw = read_exr(a.src / "deco_light.exr").copy()
        raw[..., :3] *= theme.LIGHT_EXPOSURE
        light = bloom(raw, 2.5)
        for name, (x, y, w, h) in cells.items():
            if name.endswith("_light") and not name.startswith("deco_") and not name.startswith("cap_"):
                piece = Image.open(io.BytesIO(base64.b64decode(
                    (a.out / f"{name}.svg").read_text().split("base64,")[1].split('"')[0]))).convert("RGBA")
                light.alpha_composite(piece.resize((round(w * a.scale), round(h * a.scale)), Image.LANCZOS),
                                      (round(x * a.scale), round(y * a.scale)))
        light.convert("RGB").save(a.out / "panel_preview_light.png")
    print("deco KiB", sizes, "pads KiB", sum(p.stat().st_size for p in a.out.glob("pads_*.svg")) // 1024)


if __name__ == "__main__":
    main()
