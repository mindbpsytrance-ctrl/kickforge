"""Bring KickForge presets in line with the installed device: waveform shaders and curve kind.

Bitwig saves each drawing's shader in a preset (class 5516: identifier, shader text) and, on
loading the preset, takes it from there: an old shader comes back, an empty one draws nothing, and a
drawing the preset has no entry for is left empty too. The device's own shader is only used on a
fresh insert. (Seen 2026-11-21: loading a preset onto a KickForge already in a project does not
replace its drawings either; only a fresh device takes them, from the preset or the device.) So after a shader change (or the v24-v26 id changes), the presets need these
entries rewritten: one per drawing, under the device's id (WAVE_PITCH, ...), with its shader.

Entries are matched to the device's drawings by id (WAVE_<TAB>, also WAVE_<TAB>_<hash> from v24);
entries saved with an empty id (v25-v26) by their order, which is the device's (pitch, amp,
click, tune). Missing entries are added.

The curves saved in a preset (PITCH_CURVE, AMP_CURVE) also carry their kind (cycle, envelope,
transfer); it is set to the device's (CYCLE; v27's ENVELOPE silenced the body). Their points are
kept. Nothing else changes.

Dry run by default (says what it would change). With --apply it first copies each preset it
changes to --backup (under its path relative to --presets, so presets of the same name in two
folders keep their own copy), writes the new preset next to the old one, checks it decodes and
needs nothing more, and only then puts it in place (an atomic rename: a failure leaves the
original as it was). Symbolic links are left alone (v51).

Usage: python3 tools/repair_presets.py [--device ../install/KickForge.bwdevice]
                                       [--presets "~/Bitwig Studio/Library/Presets/KickForge"]
                                       [--apply] [--backup ../preset-backups/<time>]
"""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KICK = HERE.parent
BLUEPRINT = Path(os.environ.get("KICKFORGE_BLUEPRINT", Path.home() / "Patchbay/bitwig-devices-blueprint"))
CODEC = BLUEPRINT / "tools/document_codec/target/release/bwmodule-parser"
DEVICE_UUID = "6b0f3c5e-9a41-4d8e-b7c2-4f1e0a9d2c31"
DRAWING, DRAWING_STATE = 5512, 5516
CURVE_ATOM, CURVE_STATE, CURVE = 4733, 4748, 4735
KIND_NAMES = {0: "Periodic", 1: "Envelope", 2: "Transfer"}


TIMEOUT = 120   # seconds for one codec run (v51: a hung codec no longer hangs the repair)


def decode(path):
    out = subprocess.run([str(CODEC), "to-json", str(path)], capture_output=True, text=True, timeout=TIMEOUT)
    if out.returncode:
        raise SystemExit(f"cannot decode {path}: {out.stderr.strip()}")
    return json.loads(out.stdout)


def encode(doc, path):
    """Write doc to path through the codec (the JSON in a private temporary file, always removed)."""
    fd, name = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(doc, tmp)
        out = subprocess.run([str(CODEC), "from-json", name, str(path)], capture_output=True, text=True,
                             timeout=TIMEOUT)
    finally:
        Path(name).unlink(missing_ok=True)
    if out.returncode:
        raise SystemExit(f"cannot encode {path}: {out.stderr.strip()}")


def replace_safely(doc, path, check):
    """Encode doc next to path, decode it back and check it, then rename it over path (atomic on one
    file system): the original is untouched unless the new file is good."""
    new = path.with_name(f".{path.name}.repair-tmp")
    try:
        encode(doc, new)
        problem = check(decode(new))
        if problem:
            raise SystemExit(f"{path}: {problem} (original left as it was)")
        os.replace(new, path)
    finally:
        new.unlink(missing_ok=True)


def objects(node, class_id):
    """Every object of class_id, depth first."""
    if isinstance(node, dict):
        if node.get("class_id") == class_id:
            yield node
        for value in node.values():
            yield from objects(value, class_id)
    elif isinstance(node, list):
        for value in node:
            yield from objects(value, class_id)


def state_list(node):
    """The list holding the preset's drawing entries (the device's child presets)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key.startswith("child_presets#") and isinstance(value, dict):
                items = value.get("value")
                if isinstance(items, list) and any(isinstance(e, dict) and e.get("Object", {}).get("class_id")
                                                   == DRAWING_STATE for e in items):
                    return items
            found = state_list(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = state_list(value)
            if found is not None:
                return found
    return None


def device_shaders(device):
    doc = decode(device)
    shaders = [(o["fields"]["preset_identifier#701"]["value"], o["fields"]["#16316"]["value"])
               for o in objects(doc["body"], DRAWING)]
    if not shaders or any(not pid for pid, _ in shaders):
        raise SystemExit(f"{device}: its drawings need preset ids (KickForge v27 or later)")
    # the kind of each curve's resource: what a preset saves (and loading it sets)
    kinds = {o["fields"]["preset_identifier#13812"]["value"]:
             o["fields"]["resource#13810"]["value"]["fields"]["curve_kind#13869"]["value"]
             for o in objects(doc["body"], CURVE_ATOM)}
    return shaders, kinds


def repair_curves(doc, kinds):
    changes = []
    for state in objects(doc["body"], CURVE_STATE):
        cid = state["fields"]["identifier#697"]["value"]
        if cid not in kinds:
            continue
        for curve in objects(state, CURVE):
            f = curve["fields"]
            if f["curve_kind#13869"]["value"] != kinds[cid]:
                changes.append(f"{cid}: kind {f['curve_kind#13869']['value']} -> {kinds[cid]}")
                f["curve_kind#13869"]["value"] = kinds[cid]
            if "category#13858" in f and f["category#13858"]["value"] != KIND_NAMES[kinds[cid]]:
                f["category#13858"]["value"] = KIND_NAMES[kinds[cid]]
    return changes


def repair(doc, shaders):
    """Rewrite the drawing entries in place; returns a list of changes (empty: nothing to do)."""
    entries = state_list(doc["body"])
    if entries is None:
        return None
    ids = [pid for pid, _ in shaders]
    text = dict(shaders)
    states = [e["Object"] for e in entries if e.get("Object", {}).get("class_id") == DRAWING_STATE]
    changes, matched, unnamed = [], {}, []
    for state in states:
        sid = state["fields"]["identifier#697"]["value"]
        base = re.sub(r"_[0-9a-f]{8}$", "", sid)
        if base in text and base not in matched:
            matched[base] = state
        else:
            unnamed.append(state)
    for pid in ids:     # entries without a usable id, in the device's order
        if pid not in matched and unnamed:
            matched[pid] = unnamed.pop(0)
    for pid in ids:
        state = matched.get(pid)
        if state is None:
            state = copy.deepcopy(states[0])
            entries.append({"Object": state})
            state["fields"]["identifier#697"]["value"] = ""
            state["fields"]["#16331"]["value"] = ""
            changes.append(f"{pid}: added")
        f = state["fields"]
        old_id, old_text = f["identifier#697"]["value"], f["#16331"]["value"]
        if old_id != pid:
            changes.append(f"{pid}: id {old_id!r} -> {pid!r}")
        if old_text != text[pid]:
            changes.append(f"{pid}: shader {len(old_text)} -> {len(text[pid])} chars"
                           + (" (was empty)" if not old_text else ""))
        f["identifier#697"]["value"], f["#16331"]["value"] = pid, text[pid]
    for state in unnamed:   # left over: more entries than drawings
        entries[:] = [e for e in entries if e.get("Object") is not state]
        changes.append(f"removed a stray drawing entry {state['fields']['identifier#697']['value']!r}")
    return changes


def main():
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--device", type=Path, default=KICK.parent / "install" / "KickForge.bwdevice")
    cli.add_argument("--presets", type=Path, default=Path.home() / "Bitwig Studio/Library/Presets/KickForge")
    cli.add_argument("--apply", action="store_true", help="rewrite the presets (default: dry run)")
    cli.add_argument("--backup", type=Path,
                     default=KICK.parent / "preset-backups" / time.strftime("%Y-%m-%d_%H%M%S"))
    a = cli.parse_args()
    shaders, kinds = device_shaders(a.device)
    print(f"device {a.device}: drawings {', '.join(pid for pid, _ in shaders)}")
    todo = 0
    for path in sorted(a.presets.rglob("*.bwpreset")):
        if path.is_symlink() or not path.is_file():
            print(f"  {path.name}: a link or not a file (left alone)")
            continue
        doc = decode(path)
        if DEVICE_UUID not in json.dumps(doc["metadata"]):
            continue
        changes = repair(doc, shaders)
        if changes is None:
            print(f"  {path.name}: no drawing entries (left as is)")
            continue
        changes += repair_curves(doc, kinds)
        if not changes:
            print(f"  {path.name}: up to date")
            continue
        todo += 1
        print(f"  {path.name}:")
        for change in changes:
            print(f"    {change}")
        if a.apply:
            saved = a.backup / path.relative_to(a.presets)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
            replace_safely(doc, path, lambda again: "still differs after the rewrite"
                           if repair(again, shaders) or repair_curves(again, kinds) else None)
    if not todo:
        print("nothing to repair")
    elif a.apply:
        print(f"repaired {todo} preset(s); originals in {a.backup}")
    else:
        print(f"{todo} preset(s) to repair: run again with --apply")


if __name__ == "__main__":
    sys.exit(main())
