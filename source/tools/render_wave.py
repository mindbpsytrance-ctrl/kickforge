"""Preview the waveform drawings offline: scan the default curves like kick_phase.nitro (v39: at
x = (k/10)^2 on both curves), pack like kick_display.nitro.in, draw with
build/kick_wave_<name>.sksl (Skia)."""
import math, struct, sys
from pathlib import Path
import skia
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

def f32(x): return struct.unpack("f", struct.pack("f", x))[0]
def lim(x, lo=0.0, hi=1.0): return min(hi, max(lo, x))
def q8(x): return math.floor(lim(x) * 255.0 + 0.5)
def qn(x, n): return math.floor(lim(x) * n + 0.5)
def pack3(a, b, c): return f32((a * 65536.0 + b * 256.0 + c) / 16777216.0)
def packn(n): return f32(n / 16777216.0)

def curve(points, x):  # linear segments (curvature 0)
    for (p0, v0, _), (p1, v1, _) in zip(points, points[1:]):
        if p0 <= x <= p1:
            return v0 + (v1 - v0) * ((x - p0) / max(1e-9, p1 - p0))
    return points[-1][1]

def lanes(tab, pitch_pts, amp_pts, p_len, a_len, midi=31, amount=60.0, head=None, phase=0.0, mpb=500.0,
          pts=0.668, ats=0.347, pscale=0.0, ascale=0, ctype=0, level=0.3, decay=0.006, tone=6000.0, hp=300.0,
          drive=None):
    fb, ab = [], []
    k_curve = math.exp(6.908754779 * pscale) - 1.0
    for k in range(11):
        x = min(0.999, (k * 0.1) ** 2)
        pv = max(0.0, (curve(pitch_pts, x) - 0.02) / 0.98)
        shaped = math.log(1 + k_curve * pv) / math.log(1 + k_curve) if k_curve > 1e-4 else pv
        fb.append(q8(shaped)); ab.append(q8(curve(amp_pts, x)))
    span = p_len if tab == 0 else a_len
    hd = 255 if head is None else math.floor(lim(head / span) * 250 + 0.5)
    if drive is not None: hd = q8(drive)
    xb = qn(math.log(tone / 200) / 4.605170186, 31) * 8 + ctype
    l0 = [pack3(fb[0], fb[1], fb[2]), pack3(fb[3], fb[4], fb[5]), pack3(fb[6], fb[7], fb[8]), pack3(fb[9], fb[10], ab[0])]
    l1 = [pack3(ab[1], ab[2], ab[3]), pack3(ab[4], ab[5], ab[6]), pack3(ab[7], ab[8], ab[9]), pack3(ab[10], hd, xb)]
    lp, la = (qn(math.log(L / 5) / 7.377758908, 2047) for L in (p_len, a_len))
    lx = packn(lp * 8192 + la * 4 + ascale * 2)
    ly = pack3(q8(phase / 360), math.floor(amount * 1.75 + 0.5), q8(pscale))
    lz = pack3(q8(pts), q8(ats), q8(math.log(decay / 0.0002) / 6.907755279))
    lw = packn(math.floor(lim(mpb, 10, 2047) + 0.5) * 8192 + qn(level, 31) * 256
               + qn(math.log(hp / 20) / 5.991464547, 15) * 16 + (midi - 24))
    return l0, l1, [lx, ly, lz, lw]

def render(out, name, w, h, **kw):
    tab = 0 if name.startswith("pitch") else 1
    src = "uniform float3 iResolution;\n" + (HERE / "build" / f"kick_wave_{name}.sksl").read_text()
    effect = skia.RuntimeEffect.MakeForShader(src)
    if effect is None:
        raise SystemExit("SkSL did not compile")
    l0, l1, l2 = lanes(tab, **kw)
    data = struct.pack("3f", w, h, 1.0) + struct.pack("4f", *l0) + struct.pack("4f", *l1) + struct.pack("4f", *l2)
    surface = skia.Surface(w, h)
    surface.getCanvas().drawRect(skia.Rect(0, 0, w, h), skia.Paint(Shader=effect.makeShader(skia.Data.MakeWithCopy(data))))
    surface.makeImageSnapshot().save(str(out), skia.kPNG)

if __name__ == "__main__":
    from build_kick import PITCH_POINTS, AMP_POINTS
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    common = dict(pitch_pts=PITCH_POINTS, amp_pts=AMP_POINTS, p_len=300.0, a_len=600.0, mpb=60000 / 128)
    render(out / "pitch.png", "pitch", 760, 136, **common)
    render(out / "amp.png", "amp", 760, 136, **common)
    render(out / "amp-playing.png", "amp", 760, 136, head=150.0, **common)
    render(out / "amp-short.png", "amp", 336, 52, **dict(common, a_len=120.0))
    render(out / "amp-time0.png", "amp", 760, 136, **dict(common, ats=0.0))
    render(out / "click.png", "click", 760, 136, **common)
    render(out / "master.png", "master", 760, 300, drive=0.0, **common)
    render(out / "master-drive.png", "master", 760, 300, drive=0.6, **common)
    render(out / "master-phase90.png", "master", 760, 300, drive=0.0, **dict(common, phase=90.0))
    print("ok", out)
