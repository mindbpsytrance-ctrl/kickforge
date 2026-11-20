"""Mock the device panel offline (v41; replaces the scratch mock_v24.py, lost with its folder).

Usage: python3 tools/mock_panel.py build/vNN.json out.png [PARAM=value ...]

Draws the main panel at 10 px per grid unit: every item on the grid whose visibility expression
(attribute 6309) holds for the given parameter values (unset ones read 0). Images are drawn from
their embedded PNG / JPEG; native controls as outlines with their class. Reports:
  - image/cell size mismatches: an SVG not exactly its cell x theme.PX_PER_UNIT (Bitwig hangs a
    larger image from the cell's corner instead of centring it)
  - overlaps: two visible native controls (they take the clicks) sharing grid cells
"""
import ast
import base64
import io
import json
import operator
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import theme  # noqa: E402

PX = 10
CONTROLS = {"knob_panel_item", "button_group_chooser_panel_item", "slider_panel_item", "popup_chooser_panel_item", "stack_panel_item",
            "display_panel_item", "button_panel_item"}


def owned(root):
    yield root
    for entry in root.get("fields", {}).values():
        kind, value = entry.get("type"), entry.get("value")
        if kind == "Object" and isinstance(value, dict):
            yield from owned(value)
        elif kind == "ObjectList" and isinstance(value, list):
            for item in value:
                if isinstance(item.get("Object"), dict):
                    yield from owned(item["Object"])


def grid_rect(item):
    lay = item["fields"].get("layout_settings#6226", {}).get("value")
    if not isinstance(lay, dict) or lay.get("class_name") != "grid_panel_item_layout_settings":
        return None
    f = lay["fields"]
    return tuple(f[k]["value"] for k in ("x#6215", "y#6216", "width#6217", "height#6218"))


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Gt: operator.gt, ast.GtE: operator.ge, ast.USub: operator.neg, ast.Not: operator.not_}


def holds(expr, values):
    """A visibility expression (Bitwig's: && || ! == != < <= > >= + - * /, names, numbers),
    evaluated on its syntax tree (v51; before, eval): anything else is refused."""
    py = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ").replace(" not =", "!=")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BoolOp):
            parts = [ev(v) for v in node.values]
            return all(parts) if isinstance(node.op, ast.And) else any(parts)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for op, right in zip(node.ops, node.comparators):
                r = ev(right)
                if type(op) not in _OPS or not _OPS[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(node, ast.Name):
            return values.get(node.id, 0.0)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"not a visibility expression: {expr!r}")

    return bool(ev(ast.parse(py.strip(), mode="eval")))


def svg_image(svg):
    """The SVG's size and its picture drawn on a canvas of that size (each <image> at its own
    x, y, width, height: the encoders' art is embedded smaller than its box, centred)."""
    m = re.search(r'<svg[^>]*width="([\d.]+)" height="([\d.]+)"', svg)
    if not m:
        return None, None
    size = (float(m.group(1)), float(m.group(2)))
    k = 4
    canvas = Image.new("RGBA", (round(size[0] * k), round(size[1] * k)), (0, 0, 0, 0))
    for tag in re.findall(r"<image[^>]*>", svg):
        attr = dict(re.findall(r'([\w:]+)="([^"]*)"', tag))
        data = attr.get("xlink:href", attr.get("href", "")).split("base64,")[-1]
        im = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
        x, y = float(attr.get("x", 0)), float(attr.get("y", 0))
        w, h = float(attr.get("width", size[0])), float(attr.get("height", size[1]))
        canvas.alpha_composite(im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS),
                               (round(x * k), round(y * k)))
    return size, canvas


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    values = {}
    for arg in sys.argv[3:]:
        k, v = arg.split("=")
        values[k] = float(v)
    doc = json.loads(src.read_text())
    body = doc["body"]
    ids = {id(o): i for i, o in enumerate(owned(body), 1)}
    panel = body["fields"]["panels#6213"]["value"][0]["Object"]
    pf = panel["fields"]
    W, H = pf["width#6232"]["value"], pf["height#6233"]["value"]
    shows = {}
    for e in pf["expressions#6277"]["value"]:
        ef = e["Object"]["fields"]
        if ef["attribute_id#6316"]["value"] == 6309:
            shows[ef["panel_item#6275"]["value"]] = ef["expression#6274"]["value"]
    canvas = Image.new("RGBA", (W * PX, H * PX), (40, 40, 48, 255))
    draw = ImageDraw.Draw(canvas)
    mismatches, controls = [], []
    for item in owned(pf["root_item#6212"]["value"]):
        rect = grid_rect(item)
        if rect is None or item.get("class_name") == "grid_panel_item":
            continue
        expr = shows.get(ids[id(item)])
        if expr and not holds(expr, values):
            continue
        x, y, w, h = rect
        cls = item.get("class_name")
        if cls == "image_panel_item":
            size, im = svg_image(item["fields"]["svg_data#6259"]["value"])
            if size and (abs(size[0] - w * theme.PX_PER_UNIT) > 0.6 or abs(size[1] - h * theme.PX_PER_UNIT) > 0.6):
                mismatches.append(f"{rect} svg {size}")
            if im is not None:
                canvas.alpha_composite(im.resize((w * PX, h * PX), Image.LANCZOS), (x * PX, y * PX))
        else:
            if cls in CONTROLS:
                controls.append((rect, cls))
            if cls not in ("knob_panel_item", "button_group_chooser_panel_item", "slider_panel_item"):
                draw.rectangle((x * PX, y * PX, (x + w) * PX - 1, (y + h) * PX - 1), outline=(150, 140, 255, 255))
                draw.text((x * PX + 6, y * PX + 4), cls.replace("_panel_item", ""), fill=(170, 160, 255, 255))
    overlaps = []
    for i, ((ax, ay, aw, ah), ac) in enumerate(controls):
        for (bx, by, bw, bh), bc in controls[i + 1:]:
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                overlaps.append(f"{ac} {(ax, ay, aw, ah)} / {bc} {(bx, by, bw, bh)}")
    canvas.convert("RGB").save(out)
    print(out, "image/cell size mismatches:", "; ".join(mismatches) or "none")
    print(out, "overlaps:", "; ".join(overlaps) or "none")


if __name__ == "__main__":
    main()
