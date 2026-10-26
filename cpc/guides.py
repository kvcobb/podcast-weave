"""Spoken choice guides and preview stills for a grid's choose-your-path page (the out-of-box version of what the Sam Altman
weave has by hand).

  python -m cpc grid previews <video_id>            a still per rendered room, with one line said in that room (checked verbatim)
  python -m cpc grid guides <video_id> [--voice <slug>]   short narrated menus: an opener, then one after each pause

previews read work/<id>/partials/grid-<node>/pause.mp4 (run `grid partial` and `render` first) and write grid/<node>/preview.jpg.
guides write grid/guides/<g>/{guide.mp4, timing.json}: g0 plays before the original starts; g<n> plays after pause n while
the choice cards light as each is named. The narrator defaults to the person's own echo voice (voices/<their slug>.wav);
every guide says on screen that it is AI-generated and whose voice clone it uses. Upload each guide.mp4 unlisted with the
AI label, then pass the ids to `grid weave --ids "...,g0=<id>,g1=<id>,..."` (lengths are read from timing.json)."""
import json, re, subprocess, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from .common import WORK, load, fmt, slug, ask_json
from .render import _font, frame_at
from . import tts

W, H, FPS = 1280, 720, 30
BG = (10, 15, 21); CARD = (18, 26, 36); IVORY = (240, 237, 230); MUTED = (153, 163, 176); LABEL = (140, 148, 158)
PALETTE = [(255, 189, 97), (97, 219, 245), (116, 230, 147), (242, 167, 201), (189, 161, 255)]   # one colour per model, in grid order


def model_colors(G): return {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(G["models"])}
def _gdir(v): return WORK / v / "grid"
def _rows(p): return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def _pill(d, x, y, text, rgb, size=26):
    f = _font(size, True); w = d.textlength(text, font=f) + 30; h = size + 18
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(10, 15, 21), outline=rgb, width=3); d.text((x + 15, y + 7), text, font=f, fill=rgb)
    return w


def previews(v):
    from .grid import _load, describe
    G = _load(v); D, meta, T = load(v); C = model_colors(G); made = 0
    for k, x in G["nodes"].items():
        mp4 = D / "partials" / f"grid-{k}" / "pause.mp4"
        if x["status"] != "done" or not mp4.exists(): continue
        rows = [r for r in _rows(_gdir(v) / k / "transcript.jsonl") if r.get("kind", "turn") == "turn" and not r.get("handback")]
        listing = "\n".join(f"[{r['speaker']}] {r['text']}" for r in rows)
        pick = None
        for _ in range(3):
            j = ask_json("Pick ONE sentence from this AI-generated conversation that best shows what this room was about, for a preview card. "
                         "Copy it exactly, word for word, 7 to 16 words, not a question. Prefer a vivid, concrete line.\n\n" + listing +
                         '\n\nReturn ONLY JSON: {"speaker": the speaker label in brackets, "line": the exact sentence}')
            ln = j.get("line", "")
            if 6 <= len(ln.split()) <= 18 and any(r["speaker"] == j.get("speaker") and ln in r["text"] for r in rows): pick = j; break
        if not pick:                                    # fall back to a plain rule: a mid-length sentence from the middle of the room
            sents = [(r["speaker"], s) for r in rows for s in re.split(r"(?<=[.!])\s+", r["text"]) if 7 <= len(s.split()) <= 16]
            if not sents: continue
            pick = dict(zip(("speaker", "line"), sents[len(sents) // 2]))
        tmp = _gdir(v) / k / "preview-frame.png"; frame_at(mp4, 0.42 * float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                                                              "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout), tmp, (W, H))
        im = Image.open(tmp).convert("RGB").filter(ImageFilter.GaussianBlur(3))
        shade = Image.new("L", (1, H)); [shade.putpixel((0, y), int(200 + 40 * y / H)) for y in range(H)]
        im = Image.composite(Image.new("RGB", (W, H), BG), im, shade.resize((W, H))); d = ImageDraw.Draw(im)
        x0 = 44 + _pill(d, 44, 40, f"{G['spots'][x['spot'] - 1]['label']} · {describe(G['models'][x['model']])}", C[x["model"]]) + 14
        if x.get("without_notes"): _pill(d, x0, 40, "without notes", (142, 154, 171))
        names = {slug(n): n for n in meta["speakers"] + [G["me"]]}
        f = _font(58, True); lines = textwrap.wrap("“" + pick["line"] + "”", 34); y = H - 90 - 70 * len(lines)
        for ln in lines: d.text((56, y), ln, font=f, fill=IVORY); y += 70
        d.text((56, H - 70), f"— {names.get(pick['speaker'], pick['speaker'])}'s echo (AI)", font=_font(28), fill=MUTED)
        im.save(_gdir(v) / k / "preview.jpg", quality=86); tmp.unlink(); made += 1
        (_gdir(v) / k / "preview.json").write_text(json.dumps(pick, indent=1)); print(f"{k}: “{pick['line']}”")
    print(f"{made} previews")


def _scripts(G, meta, D, v):
    from .grid import describe, extras
    done = {k for k, x in G["nodes"].items() if x.get("status") == "done"}
    M = list(G["models"]); names = [describe(G["models"][m]) for m in M]; S = G["spots"]; out = {}
    out["g0"] = dict(label="how this weave works", lines=[
        (f"This weave pauses {meta['title']} at {len(S)} moments, and AI echoes carry the conversation on.", []),
        (f"Each pause was run on {' and on '.join(names)}, and each one read every earlier version from {'both' if len(M) == 2 else 'all of them'}." if len(M) > 1 else "", ["map"]),
        ("After each pause you choose what plays next. None of the echoes are the real people.", [])])
    for s in S:
        n = s["n"]; lines = []
        X = extras(M, n, done)   # name only the cards every model's page actually shows after this pause
        kinds = [{k for k, _ in x["shown"]} for x in X.values()]
        if kinds and all("other" in k for k in kinds): lines.append(("You can hear another model's version of this same pause.", ["other"]))
        if kinds and all("variant" in k for k in kinds): lines.append(("Or hear it without the reviewers' notes: the same room with only the notes removed.", ["variant"]))
        if n < len(S):
            nxt = [i for i, m in enumerate(M) if f"p{n + 1}-{m}" in done]   # a next pause that was never rendered has no card
            for j, i in enumerate(nxt): lines.append(((("Or go on to " if j == 0 else "or ") + f"the pause at {S[n]['label']}, on {names[i]}."), ["next" + M[i]]))
        else: lines.append(("Or let the original play on to the end.", ["finish"]))
        out[f"g{n}"] = dict(label=f"after {s['label']}", lines=lines, here=n)
    for g in out.values(): g["lines"] = [l for l in g["lines"] if l[0]]
    return out


def _frame(G, gd, timing, t, C):
    from .grid import describe
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); M = list(G["models"]); S = G["spots"]
    d.text((72, 40), gd["label"].upper(), font=_font(24, True), fill=LABEL); d.line([72, 74, 72 + d.textlength(gd["label"].upper(), font=_font(24, True)), 74], fill=LABEL, width=2)
    cols = [140 + i * (1000 / max(1, len(S) - 1)) if len(S) > 1 else 640 for i in range(len(S))]; rows = [190 + j * 90 for j in range(len(M))]
    cue = {k: c for k, c in timing["cues"].items() if c <= t}; here = gd.get("here")
    for i in range(len(S) - 1):
        for a in rows:
            for b in rows: d.line([cols[i] + 70, a, cols[i + 1] - 70, b], fill=(40, 48, 58), width=2)
    for i, s in enumerate(S):
        d.text((cols[i], 120), s["label"], font=_font(26, True), fill=IVORY if here == s["n"] else MUTED, anchor="mm")
        for j, m in enumerate(M):
            lit = (here == s["n"] and "other" in cue) or (here is not None and s["n"] == here + 1 and ("next" + m) in cue) or ("map" in cue)
            col = C[m]; lab = describe(G["models"][m]); lab = lab.split()[-2] if len(lab.split()) > 1 else lab
            hw = max(70, d.textlength(lab, font=_font(22, True)) / 2 + 16); box = [cols[i] - hw, rows[j] - 30, cols[i] + hw, rows[j] + 30]
            d.rounded_rectangle(box, radius=14, fill=CARD, outline=col if lit else tuple(int(c * 0.45) for c in col), width=4 if lit else 2)
            d.text((cols[i], rows[j]), lab, font=_font(22, True), fill=IVORY if lit else MUTED, anchor="mm")
    if here and "variant" in cue: d.text((cols[here - 1], rows[-1] + 70), "without notes", font=_font(22, True), fill=(170, 180, 194), anchor="mm")
    if here and "finish" in cue: d.text((cols[-1] + 60, 120), "→ to the end", font=_font(22, True), fill=IVORY, anchor="lm")
    cur = next((l for l in timing["lines"] if l["t0"] <= t < l["t1"] + 0.25), None)
    if cur:
        for k, ln in enumerate(textwrap.wrap(cur["text"], 58)): d.text((W // 2, 560 + 40 * k), ln, font=_font(30), fill=IVORY, anchor="mm")
    d.rectangle([0, H - 36, W, H], fill=(5, 9, 13))
    d.text((24, H - 28), f"AI-generated. Narrated by {timing['narrator']}'s echo (a voice clone from their own reference recording).", font=_font(18), fill=(205, 210, 218))
    return im


_wm = None
def _spoken_ok(text, ref, rtext, out, who, tries=3):
    """Voice a line, transcribe it, and retake it if words went missing (cloned voices sometimes drop a short opening word)."""
    global _wm
    from faster_whisper import WhisperModel
    import os
    if _wm is None: _wm = WhisperModel(os.environ.get("CPC_WHISPER_MODEL", "small"), device="auto", compute_type="auto")
    norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
    for k in range(tries):
        w = tts.speak(text, ref, rtext, out, who); segs, _ = _wm.transcribe(str(w), language="en")
        heard = norm(" ".join(x.text for x in segs)); miss = [x for x in norm(text) if x not in heard and not x.isdigit()]
        if len(miss) <= 1: return w
        print(f"  retake {k + 1}: missing {miss[:5]} in: {text[:60]}"); Path(w).unlink()
    print(f"  WARNING: kept a take with missing words; listen before uploading: {text[:60]}")
    return tts.speak(text, ref, rtext, out, who)


def guides(v, voice=None):
    from .grid import _load
    G = _load(v); D, meta, T = load(v); mej = json.loads((D / "me" / "me.json").read_text()); who = voice or mej["slug"]
    ref, rtxt = D / "voices" / f"{who}.wav", D / "voices" / f"{who}.txt"
    if not ref.exists(): raise SystemExit(f"no voice clip voices/{who}.wav (run `python -m cpc voices {v} --me ...`)")
    narrator = {slug(n): n for n in meta["speakers"] + [G["me"]]}.get(who, who); C = model_colors(G)
    for g, gd in _scripts(G, meta, D, v).items():
        O = _gdir(v) / "guides" / g; O.mkdir(parents=True, exist_ok=True); t = 0.7; lines, cues, files = [], {}, []
        for i, (text, kinds) in enumerate(gd["lines"]):
            w = _spoken_ok(text, ref, rtxt.read_text(), O / f"line-{i:02d}.wav", who)
            L = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(w)], capture_output=True, text=True).stdout)
            lines.append(dict(t0=round(t, 2), t1=round(t + L, 2), text=text, who=who)); [cues.setdefault(k, round(t, 2)) for k in kinds]
            files.append((w, t)); t += L + 0.35
        total = round(t + 1.0, 2)
        mix = O / "audio.wav"; args = ["ffmpeg", "-v", "error", "-y"]
        for w, _ in files: args += ["-i", str(w)]
        args += ["-filter_complex", "".join(f"[{i}]adelay={int(st * 1000)}:all=1[a{i}];" for i, (_, st) in enumerate(files)) + "".join(f"[a{i}]" for i in range(len(files)))
                 + f"amix=inputs={len(files)}:normalize=0,apad=whole_dur={total}[o]", "-map", "[o]", "-ar", "44100", "-ac", "1", str(mix)]
        subprocess.run(args, check=True)
        timing = dict(guide=g, label=gd["label"], len=total, lines=lines, cues=cues, speakers=[[l["t0"], l["t1"], who] for l in lines], narrator=narrator)
        (O / "timing.json").write_text(json.dumps(timing, indent=1))
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(mix),
                              "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest",
                              "-movflags", "+faststart", str(O / "guide.mp4")], stdin=subprocess.PIPE)
        for n_ in range(int(total * FPS)): p.stdin.write(_frame(G, gd, timing, n_ / FPS, C).tobytes())
        p.stdin.close(); p.wait(); print(f"{g}: {O / 'guide.mp4'} ({total} s)")
    print("Upload each guide.mp4 unlisted with the altered or synthetic content label, then pass g0=<id>,g1=<id>,... to grid weave --ids.")
