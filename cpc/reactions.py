"""Reactions beside the video: short scripted comments from the cast, with avatars, that scroll in as the page plays.

    python -m cpc grid reactions <video_id> [--per-room 6]

For every rendered room it reads the room's exact per-turn timeline (timeline.json, written by `render`), asks the model
for a few reactions anchored to the turn each one follows, keeps only those that quote the room word for word (if they quote
at all), and places each 0.4 s after its turn ends, at least 5 s apart. Avatars are a cel-shade filter over each person's
picture in the render (their tile, their box on the frozen frame, or their still), so they cannot change who someone is. Writes, in the current
folder: reactions/<id>-choose.json and avatars/<id>/<slug>.png (an avatar file already there is kept: put your own art
there to use it); `grid weave` links the reactions into the page when the file exists.

The page labels every reaction with who it is from and that it is an AI echo. They are written after reading the
transcript, not live comments, and never the real people's views.
"""
import json, re, zlib
from pathlib import Path
from PIL import Image, ImageDraw
from .common import load, slug, ask_json

PALETTE = ["#ffd166", "#61dbf5", "#ffbd61", "#f2a7c9", "#74e693", "#bda1ff"]


def _dur(p):
    from .render import _dur as d
    return d(p)


def timeline(P):
    """[{i, who, t0, t1, text}] in seconds of the rendered pause video. Uses timeline.json when render wrote one; otherwise
    rebuilds it from pf.txt (each turn's frame lasts exactly its wav) checked against pa.txt (that frame's audio is the wav)."""
    P = Path(P)
    if (P / "timeline.json").exists(): return json.loads((P / "timeline.json").read_text())
    rows = [r for r in (json.loads(l) for l in (P / "transcript.jsonl").read_text().splitlines() if l.strip()) if r.get("kind") == "turn" and r.get("text")]
    segs = []
    for i, r in enumerate(rows):
        h = zlib.crc32((r["speaker"] + "|" + r["text"]).encode()) & 0xffffff
        new, old = P / "seg" / f"{i:03d}-{r['speaker']}-{h:06x}.wav", P / "seg" / f"{i:03d}-{r['speaker']}.wav"
        segs.append(new if new.exists() else old)
    ds = [float(x) for x in re.findall(r"^duration ([\d.]+)", (P / "pf.txt").read_text(), re.M)]
    pa = re.findall(r"^file '(.+)'", (P / "pa.txt").read_text(), re.M)
    if len(pa) != len(ds) or not all(s.exists() for s in segs): raise SystemExit(f"{P}: render lists don't match its turns; re-run `render`")
    sd = [_dur(s) for s in segs]; out, t, k = [], 0.0, 0
    for j, d in enumerate(ds):
        if k < len(sd) and abs(d - sd[k]) < 0.002 and abs(_dur(pa[j]) - sd[k]) < 0.03:
            out.append(dict(i=k, who=rows[k]["speaker"], t0=round(t, 2), t1=round(t + d, 2), text=rows[k]["text"])); k += 1
        t += d
    if k != len(sd): raise SystemExit(f"{P}: matched {k} of {len(sd)} turns")
    return out


def avatar(src, out, initials="?"):
    """A round cartoon-ish avatar: cel-shade over the centre of the source image, or initials on a disc if there is none."""
    S = 256; m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).ellipse((3, 3, S - 3, S - 3), fill=255)
    if src and Path(src).exists():
        import numpy as np
        im = Image.open(src).convert("RGB"); w, h = im.size; s = min(w, h, int(h * 0.8))
        im = im.crop(((w - s) // 2, max(0, int(h * 0.42) - s // 2), (w + s) // 2, max(0, int(h * 0.42) - s // 2) + s)).resize((S, S), Image.LANCZOS)
        try:
            import cv2
            a = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
            for _ in range(3): a = cv2.bilateralFilter(a, 9, 45, 45)
            Z = a.reshape(-1, 3).astype(np.float32)
            _, lab, cen = cv2.kmeans(Z, 12, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 12, 1), 3, cv2.KMEANS_PP_CENTERS)
            q = cen.astype(np.uint8)[lab.flatten()].reshape(a.shape); e = cv2.Canny(cv2.medianBlur(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 5), 40, 110)
            q[e > 0] = (q[e > 0] * 0.25).astype(np.uint8); im = Image.fromarray(cv2.cvtColor(q, cv2.COLOR_BGR2RGB))
        except ImportError:   # no OpenCV: a plain posterized crop still reads as an avatar
            from PIL import ImageOps; im = ImageOps.posterize(im, 4)
    else:
        from .render import _font
        im = Image.new("RGB", (S, S), (22, 30, 40)); ImageDraw.Draw(im).text((S // 2, S // 2), initials, font=_font(96, True), fill=(200, 210, 225), anchor="mm")
    o = Image.new("RGBA", (S, S), (0, 0, 0, 0)); o.paste(im, (0, 0), m); Path(out).parent.mkdir(parents=True, exist_ok=True); o.save(out, optimize=True)


def reactions(v, per_room=6):
    from .grid import _load, _gdir, describe
    G = _load(v); D, meta, T = load(v); out = Path.cwd()
    people = meta["speakers"] + [G["me"]]; slugs = {slug(n): n for n in people}
    cast = {s: dict(name=n.split()[0], tag="echo · AI", color=PALETTE[i % len(PALETTE)]) for i, (s, n) in enumerate(slugs.items())}
    host, me = slug(meta["speakers"][0]), slug(G["me"])
    def source(s):   # this person's picture in any room: their tile, else their box on the frozen frame, else their still
        for P in sorted((D / "partials").glob("grid-*")):
            lay = json.loads((P / "layout.json").read_text()) if (P / "layout.json").exists() else {}
            t = lay.get("tiles", {}).get(s)
            if t and Path(t[0]).exists(): return t[0]
            box, fz = lay.get("in_frame", {}).get(s), P / "freeze-hi.png"
            if box and fz.exists():
                im = Image.open(fz); f = im.width / 1280; x0, y0, x1, y1 = (int(c * f) for c in box)
                crop = out / "avatars" / v / f".src-{s}.png"; crop.parent.mkdir(parents=True, exist_ok=True); im.crop((x0, y0, x1, y0 + int((y1 - y0) * 0.75))).save(crop); return crop
            if (P / f"still-{s}.png").exists(): return P / f"still-{s}.png"
        return None
    for s in cast:
        if not (out / "avatars" / v / f"{s}.png").exists():   # an avatar already there is kept, so you can drop in your own art
            avatar(source(s), out / "avatars" / v / f"{s}.png", "".join(w[0] for w in slugs[s].split()[:2]).upper())
        cast[s]["avatar"] = f"avatars/{v}/{s}.png"
    tracks = {}
    for k, x in G["nodes"].items():
        P = D / "partials" / f"grid-{k}"
        if x["status"] != "done" or not (P / "pause.mp4").exists(): continue
        tl = timeline(P); model = describe(G["models"][x["model"]])
        lines = "\n".join(f"[{r['i'] + 1}] {slugs.get(r['who'], r['who'])}: {r['text']}" for r in tl)
        roles = "\n".join(
            f"- {s}: the echo of {n}. " + ("Warm and playful; points out and celebrates moments when someone in the room notices they are an AI or an echo, or plays with it." if s == me else
                                           "The curious host: says why a moment matters." if s == host else
                                           f"When their echo takes a strong or brave position, they joke that they are an AI echo, so don't quote them on it; they can joke about liking a line their {model} seat gave them.")
            for s, n in slugs.items())
        prompt = (f"Write {per_room} short live-chat style reactions that scroll beside this video on a web page while it plays. The video is an AI-generated "
                  f"continuation of a real podcast: AI echoes of {', '.join(people)} talk after a pause, every voice generated on {model}. Each reaction is labelled "
                  f"on the page with who it is from and that it is an AI echo.\n\nTranscript, turn numbers in brackets:\n{lines}\n\nVoices:\n{roles}\n\n"
                  "Rules: at most 120 characters each; at most one emoji in a few; react only to what is in the transcript; never state facts about the real "
                  "people or claim they said or believe anything; spread them across the video, the first one or two in the first third, none before turn 2; "
                  "never mention turn numbers; any quote is word for word.\n"
                  'Answer with JSON only: [{"after_turn": <n>, "who": "<voice slug>", "text": "<reaction>"}]')
        try: got = ask_json(prompt, want=list)
        except RuntimeError as e: print(f"{k}: no reactions ({e})"); continue
        said = " ".join(r["text"] for r in tl)
        ok = [y for y in got if isinstance(y, dict) and y.get("who") in cast and isinstance(y.get("after_turn"), int) and 2 <= y["after_turn"] <= len(tl)
              and len(y.get("text", "")) <= 140 and not re.search(r"\bturn \d", y["text"]) and all(q in said for q in re.findall(r'["\u201c]([^"\u201d]{8,})["\u201d]', y["text"]))]
        items = sorted((dict(t=round(tl[y["after_turn"] - 1]["t1"] + 0.4, 2), who=y["who"], text=y["text"], src=dict(seq=y["after_turn"])) for y in ok), key=lambda y: y["t"])
        placed = []
        for y in items:
            if placed and y["t"] < placed[-1]["t"] + 5: y["t"] = round(placed[-1]["t"] + 5, 2)
            if y["t"] <= tl[-1]["t1"] - 2: placed.append(y)
        tracks[k] = placed; print(f"{k}: {len(placed)} reactions")
    doc = dict(version=1, note=f"Scripted reactions drafted by a model from each room's transcript; not live comments and not the real people.", cast=cast, tracks=tracks)
    (out / "reactions").mkdir(exist_ok=True); (out / "reactions" / f"{v}-choose.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote reactions/{v}-choose.json ({sum(len(t) for t in tracks.values())} reactions); `grid weave` links it into the page")
