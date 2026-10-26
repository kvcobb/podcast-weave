"""Stage 4: voice every turn and draw the pause segment.

The original's frame at the pause freezes, eases smaller, and portrait tiles for the people NOT visible in that frame appear in
the right-hand column; everyone but the speaker is dimmed under a soft spotlight (no outlines), and each in-frame echo is labelled just under the frame. At the
end everything eases back to the untouched frozen frame, so the cut back to the original looks like pressing play. Every frame
carries the disclosure band, except the brief untouched freeze at the very start and end (so the cut from and back to
the original is clean).

  python -m cpc render <partial_dir>          reads layout.json if present (see below), writes pause.mp4

layout.json (optional; written by `python -m cpc layout <partial_dir>` and worth checking by eye):
  {"in_frame": {"slug": [x0, y0, x1, y1]}, "tiles": {"slug": ["image.png", [l, t, r, b] or null]}}
  coordinates are in the 1280x720 frozen frame. Anyone in neither list gets an automatic still from their own longest turn.
"""
import json, os, glob, subprocess, zlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from .common import WORK, slug, fmt, sh
from . import tts

FPS, GAP, GLIDE = 30, 0.45, 0.25     # K 16403: glide ~2.4x faster, same ease. K 16339: smoother pause transitions; the speaker spotlight glides during the gap between turns
TINT = 0.50              # how much darker everyone but the speaker gets (K 261025: stronger spotlight; was 0.30)
U = 2                    # K 261025: draw at 2560x1440 (layout numbers stay in 1280x720 space) so YouTube serves it sharp
W0, H0 = 1280, 720; W, H = W0 * U, H0 * U
Z = lambda x: round(x * U)
PX, SC, OX, OY = 1008, 0.74, 28, 94



def trim_frame(im):
    """Cut off a thin uniform border baked into a portrait file (K 261025: no box of any kind around a portrait)."""
    px = im.load(); w, h = im.size; lim = max(2, round(min(w, h) * 0.04))
    def flat(pts):
        v = [px[p] for p in pts]; m = [sum(c[i] for c in v) / len(v) for i in range(3)]
        return max(abs(c[i] - m[i]) for c in v for i in range(3)) < 14
    t = l = 0; b, r = h, w
    while t < lim and flat([(x, t) for x in range(0, w, 4)]): t += 1
    while h - b < lim and flat([(x, b - 1) for x in range(0, w, 4)]): b -= 1
    while l < lim and flat([(l, y) for y in range(0, h, 4)]): l += 1
    while w - r < lim and flat([(r - 1, y) for y in range(0, h, 4)]): r -= 1
    return im.crop((l, t, r, b)) if (l or t or r < w or b < h) else im

def _font(n, bold=False):
    for f in (["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttc"] if bold else ["DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"]):
        for d in ("/usr/share/fonts/truetype/dejavu", "/Library/Fonts", "/System/Library/Fonts", "C:/Windows/Fonts", ""):
            try: return ImageFont.truetype(os.path.join(d, f) if d else f, n)
            except Exception: pass
    return ImageFont.load_default()


def frame_at(video, t, out, size=(1280, 720)):
    sh("ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}:flags=lanczos", str(out))
    return out


def auto_layout(P, force=False):
    """Default layout: nobody marked in-frame; a still per episode speaker from the middle of their longest turn; your photo.
    Also writes freeze.png (the frame at the pause) so you can check who is visible. Won't overwrite a layout.json you edited
    unless force=True."""
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); D = WORK / cfg["video_id"]; turns = json.loads((D / "turns.json").read_text())
    video = next((D / "src").glob("video.*")); tiles = {}
    frame_at(video, cfg["pause"] - 0.05, P / "freeze.png"); frame_at(video, cfg["pause"] - 0.05, P / "freeze-hi.png", (W, H))
    if (P / "layout.json").exists() and not force:
        print(f"kept your {P/'layout.json'} (use --force to regenerate); freeze.png refreshed"); return json.loads((P / "layout.json").read_text())
    me_s = slug(cfg["me"]); photo = next(iter(sorted((D / "me").glob("photo.*"))), None)
    tiles[me_s] = [str(photo.resolve()), None] if photo else None
    for name in [cfg["host"]] + cfg["guests"]:
        own = [x for x in turns if x["who"] == name]
        if not own: print(f"no labelled turns for {name}; give them a tile image in layout.json"); continue
        t = max(own, key=lambda x: x["t1"] - x["t0"])
        img = (P / f"still-{slug(name)}.png").resolve(); frame_at(video, (t["t0"] + t["t1"]) / 2, img); tiles[slug(name)] = [str(img), [280, 0, 1000, 720]]
    if not tiles.get(me_s):                                          # no photo: a plain labelled tile, so the echo is still marked
        ph = (P / f"placeholder-{me_s}.png").resolve(); im = Image.new("RGB", (480, 480), (22, 30, 40)); d = ImageDraw.Draw(im)
        ini = "".join(w[0] for w in cfg["me"].split()[:2]).upper(); d.text((240, 240), ini, font=_font(150, True), fill=(200, 210, 225), anchor="mm"); im.save(ph)
        tiles[me_s] = [str(ph), None]
    lay = {"in_frame": {}, "tiles": {k: v for k, v in tiles.items() if v}}
    (P / "layout.json").write_text(json.dumps(lay, indent=1)); return lay


def render(P):
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); D = WORK / cfg["video_id"]; meta = json.loads((D / "meta.json").read_text())
    lay = json.loads((P / "layout.json").read_text()) if (P / "layout.json").exists() else auto_layout(P)
    names = {slug(n): n for n in meta["speakers"] + [cfg["me"]]}
    video = next((D / "src").glob("video.*")); freeze_p = P / "freeze.png"
    if not freeze_p.exists(): frame_at(video, cfg["pause"] - 0.05, freeze_p)
    hi_p = P / "freeze-hi.png"                                       # the same frame at full resolution, drawn into the 1440p canvas
    if not hi_p.exists(): frame_at(video, cfg["pause"] - 0.05, hi_p, (W, H))
    freeze = Image.open(hi_p).convert("RGB").resize((W, H), Image.LANCZOS)
    bg = Image.blend(freeze.filter(ImageFilter.GaussianBlur(Z(28))), Image.new("RGB", freeze.size, (10, 15, 21)), 0.72)
    boxes = lay.get("in_frame", {}); order = [k for k in lay["tiles"] if k not in boxes]
    n = max(1, len(order)); CAP = 52; PS = int(min(236, (560 - (n - 1) * 14) / n - CAP)); step = PS + CAP + 14
    PY = {k: 64 + i * step for i, k in enumerate(order)}

    def tile_img(path, box):
        im = Image.open(path).convert("RGB")
        if box: im = im.crop(tuple(box))
        im = trim_frame(im)
        m = min(im.size); l = (im.width - m) // 2
        return im.crop((l, 0, l + m, m)).resize((Z(PS), Z(PS)), Image.LANCZOS)
    pimg = {k: tile_img(*lay["tiles"][k]) for k in order}
    model = cfg.get("echo_model", "AI"); F, FB = (lambda s: _font(Z(s))), (lambda s: _font(Z(s), True))
    label = f"PAUSED at {fmt(cfg['pause'])}  \u00b7  {cfg['host']} with {', '.join(cfg['guests'])}"
    vname = {"omnivoice": "OmniVoice", "omnivoice-server": "OmniVoice", "elevenlabs": "ElevenLabs"}.get(tts.backend(), tts.backend())
    voices_line = cfg.get("voices_line") or f"Voices: {vname}, cloned from short clips  \u00b7  Echoes: {model}  \u00b7  github.com/kvcobb/podcast-weave"

    def fit(d, text, size, width):
        while size > 9 and d.textlength(text, font=F(size)) > Z(width): size -= 1
        return F(size)

    def spot_rect(who):
        """Where the spotlight sits for a speaker: their box inside the shrunk frozen frame, or their tile; a little loose."""
        if who in boxes:
            x0, y0, x1, y1 = boxes[who]; r = (OX + x0 * SC, OY + y0 * SC, OX + x1 * SC, OY + y1 * SC); pad = 22
        elif who in PY:
            r = (PX, PY[who], PX + PS, PY[who] + PS + CAP); pad = 18
        else:
            return None
        j = (zlib.crc32(who.encode()) % 17) - 8                      # each speaker's opening is a touch irregular, never a tight box
        return (r[0] - pad - j, r[1] - pad + j / 2, r[2] + pad + j / 2, min(662, r[3] + pad - j))

    def tint(im, rect, strength):
        """Darken the whole paused page except a soft, feathered opening around the speaker."""
        if strength <= 0: return im
        m = Image.new("L", im.size, int(255 * TINT * strength)); dm = ImageDraw.Draw(m)
        if rect:
            x0, y0, x1, y1 = rect; rad = Z(min(x1 - x0, y1 - y0) * 0.28)
            dm.rounded_rectangle((Z(x0), Z(y0), Z(x1), Z(y1)), radius=rad, fill=0)
            m = m.filter(ImageFilter.GaussianBlur(Z(22)))
        return Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, m)

    def frame(t, speaker=None, present=(), alpha=None, spot=None, strength=0.0):
        alpha = alpha or {}; s = 1 + (SC - 1) * t; ox, oy = OX * t, OY * t
        im = bg.copy() if t > 0 else freeze.copy()
        if t > 0: im.paste(freeze.resize((Z(W0 * s), Z(H0 * s)), Image.LANCZOS), (Z(ox), Z(oy)))
        d = ImageDraw.Draw(im)
        for k in present:
            # K 261025: the portrait sits on the page by itself, no panel behind it; its label is plain text under it
            a = alpha.get(k, 1.0); base = im.crop((Z(PX), Z(PY[k]), Z(PX + PS), Z(PY[k] + PS + CAP))); tile = base.copy(); tile.paste(pimg[k], (0, 0))
            td = ImageDraw.Draw(tile); nm = names.get(k, k); cap = f"AI echo \u00b7 {model}"
            td.text((Z(8), Z(PS + 6)), nm, font=fit(td, nm, 17, PS - 14), fill=(235, 235, 240)); td.text((Z(8), Z(PS + 29)), cap, font=fit(td, cap, 14, PS - 14), fill=(170, 175, 190))
            im.paste(Image.blend(base, tile, a), (Z(PX), Z(PY[k])))
        if t >= 1 and strength > 0:
            im = tint(im, spot, strength); d = ImageDraw.Draw(im)
        if t > 0:
            d.rectangle((Z(OX), Z(33), Z(OX + 6), Z(53)), fill=(235, 235, 240)); d.rectangle((Z(OX + 11), Z(33), Z(OX + 17), Z(53)), fill=(235, 235, 240))
            d.text((Z(OX + 30), Z(30)), label, font=FB(20), fill=(235, 235, 240))
            if t >= 1:
                # K 261025: each in-frame echo's label sits just under the shrunk original, centred on that person, plain text, no box
                wl, wr, wb = Z(ox), Z(ox + W0 * s), Z(oy + H0 * s + 7)
                for k, (x0, y0, x1, y1) in boxes.items():
                    lab = f"{names.get(k, k)}  \u00b7  AI echo \u00b7 {model}"; w = d.textlength(lab, font=F(14))
                    cx = min(max(Z(ox + (x0 + x1) / 2 * s) - w / 2, wl), wr - w)
                    d.text((cx, wb), lab, font=F(14), fill=(232, 235, 242))
            band = Image.new("RGB", (W, Z(58)), (6, 9, 13)); im.paste(Image.blend(im.crop((0, Z(662), W, H)), band, 0.82), (0, Z(662))); d = ImageDraw.Draw(im)
            d.text((Z(OX), Z(668)), "AI-generated continuation: every voice in this paused segment is an AI echo, not the real person. The original resumes after.", font=F(15), fill=(225, 228, 235))
            d.text((Z(OX), Z(692)), voices_line, font=F(14), fill=(160, 166, 180))
        return im

    rows = [json.loads(l) for l in (P / "transcript.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("kind") == "turn" and r.get("text")]
    (P / "seg").mkdir(exist_ok=True); seq = []
    for i, r in enumerate(rows):
        ref = D / "voices" / f"{r['speaker']}.wav"
        if not ref.exists(): raise SystemExit(f"no voice clip for {r['speaker']}: run `python -m cpc voices` (see AGENTS.md)")
        h = zlib.crc32((r["speaker"] + "|" + r["text"]).encode()) & 0xffffff                 # an edited line gets new audio
        old = P / "seg" / f"{i:03d}-{r['speaker']}.wav"; new = P / "seg" / f"{i:03d}-{r['speaker']}-{h:06x}.wav"
        if old.exists() and not new.exists() and (P / "seg" / ".legacy-ok").exists(): new = old
        wav = tts.speak(r["text"], ref, (D / "voices" / f"{r['speaker']}.txt").read_text(), new, r["speaker"])
        seq.append((r["speaker"], wav)); print(i, r["speaker"], round(_dur(wav), 1), flush=True)
    fr = P / "pf"; fr.mkdir(exist_ok=True)
    for f in glob.glob(f"{fr}/*"): os.remove(f)
    items, audio = [], []

    def put(im, d, a="sil"):
        p = fr / f"{len(items):05d}.png"; im.save(p); items.append((p, d)); audio.append((a, d))
    def ease(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)
    def lerp(a, b, u): return tuple(a[k] + (b[k] - a[k]) * u for k in range(4))
    NS, NT = int(0.9 * FPS), int(0.5 * FPS)                          # frames for the shrink/grow and for a tile fading in
    put(frame(0), 0.9)
    for i in range(1, NS + 1): put(frame(ease(i / NS)), 1 / FPS)
    present = []; cur, strength = None, 0.0
    for who, wav in seq:
        if who in pimg and who not in present:
            present.append(who)
            for i in range(1, NT + 1): put(frame(1, None, present, {who: ease(i / NT)}, cur, strength), 1 / FPS)
        tgt = spot_rect(who)
        if tgt and tgt != cur:                                       # glide the opening to the new speaker during the gap
            n = int(GLIDE * FPS); start = cur or tgt; s0 = strength          # K 261025: keep this glide, it reads like a hand-held light
            for i in range(1, n + 1):
                u = ease(i / n); put(frame(1, None, present, None, lerp(start, tgt, u), s0 + (1 - s0) * u), 1 / FPS)
            cur, strength = tgt, 1.0
        else:
            put(frame(1, None, present, None, cur, strength), GAP)
        put(frame(1, who, present, None, cur, strength), _dur(wav), wav)
    for i in range(1, NT + 1): put(frame(1, None, present, None, cur, 1 - ease(i / NT)), 1 / FPS)
    for i in range(1, NT + 1): put(frame(1, None, present, {k: 1 - ease(i / NT) for k in present}), 1 / FPS)
    for i in range(NS, -1, -1): put(frame(ease(i / NS)), 1 / FPS)
    put(frame(0), 0.6)
    (P / "pf.txt").write_text("".join(f"file '{p.resolve()}'\nduration {d:.4f}\n" for p, d in items) + f"file '{items[-1][0].resolve()}'\n")
    parts = []
    for i, (src, d) in enumerate(audio):
        o = fr / f"a{i:04d}.wav"
        if src == "sil": sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{d:.4f}", str(o))
        else: sh("ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-ac", "2", str(o))
        parts.append(o)
    (P / "pa.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(P / "pa.txt"), str(P / "pa.wav"))
    r = sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(P / "pf.txt"), "-i", str(P / "pa.wav"), "-vf", f"fps={FPS},format=yuv420p",
           "-af", "apad", "-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "16", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(P / "pause.mp4"))
    if r.returncode: raise SystemExit(r.stderr[-800:])
    print("pause segment:", P / "pause.mp4", f"{_dur(P / 'pause.mp4'):.1f} s")


def _dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)
