"""One-off (v75): turn KickForge presets' note values from lists into numbers.

KickForge v37-v74 held each curve's note value (Sync mode) as a list parameter, P_DIV / A_DIV
(an indexed atom: the preset saves the item's index). Bitwig does not let modulators reach a
list, so v75 holds them as decimal parameters, P_NOTE / A_NOTE, 0 .. 15 (the same index, as a
number). This replaces each preset's P_DIV / A_DIV entry with a P_NOTE / A_NOTE entry of the same
value; a preset without them (or already converted) is left alone.

Usage: python3 tools/convert_div_presets.py [--presets DIR] [--apply] [--backup DIR]
Dry run by default. With --apply, every preset it changes is first copied to the backup folder,
then rewritten next to itself, decoded back and checked, and only then renamed over the
original (repair_presets.replace_safely).
"""
import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_presets import DEVICE_UUID, KICK, decode, replace_safely  # noqa: E402

RENAME = {"P_DIV": "P_NOTE", "A_DIV": "A_NOTE"}
INDEXED, DECIMAL = 247, 133


def entries(node):
    """Every preset value entry ({"Object": {...identifier#697...}}) with its holder."""
    if isinstance(node, dict):
        for value in node.values():
            yield from entries(value)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            obj = value.get("Object") if isinstance(value, dict) else None
            if isinstance(obj, dict) and "identifier#697" in obj.get("fields", {}):
                yield node, i, obj
            yield from entries(value)


def convert(doc):
    """The changes made to doc (in place): [(old id, index, new id)]."""
    found = {obj["fields"]["identifier#697"]["value"]: (holder, i, obj) for holder, i, obj in entries(doc["body"])}
    if any(new in found for new in RENAME.values()):
        if any(old in found for old in RENAME):
            raise ValueError("holds both the old and the new note value")
        return []
    template = next((obj for _, _, obj in found.values() if obj.get("class_id") == DECIMAL
                     and set(obj["fields"]) == {"identifier#697", "value#310"}), None)
    changes = []
    for old, new in RENAME.items():
        if old not in found:
            continue
        holder, i, obj = found[old]
        if obj.get("class_id") != INDEXED:
            raise ValueError(f"{old} is class {obj.get('class_id')}, not a list")
        index = obj["fields"]["value#627"]["value"]
        if not 0 <= index <= 15:
            raise ValueError(f"{old} = {index}, out of 0 .. 15")
        if template is None:
            raise ValueError("no decimal entry to model the new one on")
        entry = copy.deepcopy(template)
        entry["fields"]["identifier#697"]["value"] = new
        entry["fields"]["value#310"] = {"type": "Double", "value": float(index)}
        holder[i] = {"Object": entry}
        changes.append((old, index, new))
    return changes


def check(changes):
    def verify(again):
        values = {obj["fields"]["identifier#697"]["value"]: obj for _, _, obj in entries(again["body"])}
        for old, index, new in changes:
            if old in values:
                return f"{old} still there"
            got = values.get(new)
            if got is None or got.get("class_id") != DECIMAL or got["fields"]["value#310"]["value"] != float(index):
                return f"{new} not {float(index)}"
        return None
    return verify


def main():
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--presets", type=Path, default=Path.home() / "Bitwig Studio/Library/Presets/KickForge")
    cli.add_argument("--apply", action="store_true", help="rewrite the presets (default: dry run)")
    cli.add_argument("--backup", type=Path,
                     default=KICK.parent / "preset-backups" / time.strftime("%Y-%m-%d_%H%M%S_note-decimal"))
    a = cli.parse_args()
    todo = 0
    for path in sorted(a.presets.rglob("*.bwpreset")):
        if path.is_symlink() or not path.is_file():
            continue
        doc = decode(path)
        if DEVICE_UUID not in json.dumps(doc["metadata"]):
            continue
        changes = convert(doc)
        if not changes:
            print(f"  {path.name}: nothing to convert")
            continue
        todo += 1
        print(f"  {path.name}: " + ", ".join(f"{old} {index} -> {new} {float(index)}" for old, index, new in changes))
        if a.apply:
            saved = a.backup / path.relative_to(a.presets)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
            replace_safely(doc, path, check(changes))
    if a.apply and todo:
        print(f"converted {todo} preset(s); originals in {a.backup}")
    else:
        print(f"{todo} preset(s) to convert" + ("" if a.apply else " (dry run: --apply to convert)"))


if __name__ == "__main__":
    sys.exit(main())
