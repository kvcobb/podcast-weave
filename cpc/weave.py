"""Stage 5: package the pause for watching.

  python -m cpc companion <partial_dir>                      pause + end card -> companion.mp4 (upload this to YouTube, unlisted)
  python -m cpc weave <partial_dir> --segments <youtube_id>  write weaves/<original_id>.json and the <original_id>/ page
  python -m cpc serve                                        watch it at http://localhost:8000/<original_id>/

The weave page plays the ORIGINAL from the creator's own upload (its views and ads stay with the creator) and switches to your
companion video for the pause. Both play through YouTube's player, so the companion must be on YouTube (unlisted is fine).
"""
import json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from .common import WORK, sh, fmt, slug
from .render import _font, frame_at, _dur, W, H, Z

SITE = Path(__file__).resolve().parent.parent


def endcard(P, cfg, meta):
    video = next((WORK / cfg["video_id"] / "src").glob("video.*"))
    fr = Image.open(frame_at(video, cfg["resume_to"] - 0.3, P / "endframe.png", (W, H))).convert("RGB").resize((W, H))
    im = Image.blend(fr.filter(ImageFilter.GaussianBlur(Z(26))), Image.new("RGB", (W, H), (10, 15, 21)), 0.78); d = ImageDraw.Draw(im)
    F = lambda n, b=False: _font(Z(n), b); xy = lambda x, y: (Z(x), Z(y))                     # layout in 1280x720 terms, drawn at 1440p
    people = ", ".join([cfg["host"]] + cfg["guests"]) + f" and {cfg['me']}"
    y = 200; d.text(xy(90, y), "That was a partial continuation.", font=F(40, True), fill=(240, 240, 245)); y += 70
    for line in [f"The pause was AI-generated: {people} there are AI echoes", f"({cfg.get('echo_model', 'AI')}), not the real people. Everything else is the original."]:
        d.text(xy(90, y), line, font=F(22), fill=(205, 208, 218)); y += 34
    y += 40; d.text(xy(90, y), f"Watch the whole conversation on {meta['channel']}'s channel:", font=F(24), fill=(235, 235, 240)); y += 40
    d.text(xy(90, y), meta["title"][:90], font=F(24, True), fill=(240, 240, 245)); y += 38
    d.text(xy(90, y), f"youtube.com/watch?v={cfg['video_id']}", font=F(24), fill=(170, 190, 255))
    d.text(xy(90, 640), "Make your own: github.com/kvcobb/podcast-weave", font=F(18), fill=(150, 156, 170))
    im.save(P / "endcard.png")
    sh("ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "8", "-i", str(P / "endcard.png"), "-f", "lavfi", "-t", "8", "-i", "anullsrc=r=44100:cl=stereo",
       "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-crf", "16", "-c:a", "aac", "-b:a", "96k", "-shortest", str(P / "endcard.mp4"))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Podcast Weave</title>
<meta name="description" content="A real YouTube episode with AI-generated pause segments woven in.">
<link rel="stylesheet" href="../weave.css">
</head>
<body>
<div id="stage"><div id="player"></div></div>
<div id="note" hidden></div>
<div id="about">Tap play. You'll watch <a id="orig" href="#">the original episode</a> from its creator's own YouTube upload, with a pause where AI echoes join the conversation. The pause is AI-generated, not the real people. <a href="../">What is this?</a></div>
<script>window.WEAVE_ID = "%s"; window.WEAVE_BASE = "../";</script>
<script src="../weave.js"></script>
<script src="https://www.youtube.com/iframe_api"></script>
</body>
</html>
"""


def companion(P, contact=None):
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); meta = json.loads((WORK / cfg["video_id"] / "meta.json").read_text())
    endcard(P, cfg, meta); d = _dur(P / "pause.mp4")
    (P / "comp.txt").write_text(f"file '{(P / 'pause.mp4').resolve()}'\nfile '{(P / 'endcard.mp4').resolve()}'\n")
    # a keyframe exactly where the end card starts: YouTube can only start playback at a keyframe
    r = sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(P / "comp.txt"), "-c:v", "libx264", "-preset", "slow", "-crf", "16",
           "-force_key_frames", f"0,{d}", "-r", "30", "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-movflags", "+faststart", str(P / "companion.mp4"))
    if r.returncode: raise SystemExit(r.stderr[-800:])
    cfg["pause_len"] = round(d, 2); (P / "config.json").write_text(json.dumps(cfg, indent=1))
    people = ", ".join([cfg["host"]] + cfg["guests"])
    src = WORK / cfg["video_id"] / "voices" / "sources.json"; src = json.loads(src.read_text()) if src.exists() else {}
    names = [cfg["host"]] + cfg["guests"] + [cfg["me"]]
    from_ep = [n for n in names if src.get(slug(n), {}).get("kind") == "episode"]
    supplied = [n for n in names if src.get(slug(n), {}).get("kind") == "supplied"]
    unknown = [n for n in names if n not in from_ep + supplied]
    vparts = ([f"{', '.join(from_ep)}: cloned from this episode"] if from_ep else []) + \
             ([f"{', '.join(supplied)}: cloned from a reference recording supplied by the person making this"] if supplied else []) + \
             ([f"{', '.join(unknown)}: source not recorded"] if unknown else [])
    (P / "youtube-description.txt").write_text(
        f"Companion video for a paused-podcast experiment: the AI-generated pause segment, meant to be watched inside the weave page, which plays "
        f"{meta['channel']}'s real episode from its own YouTube upload and switches to this pause at {fmt(cfg['pause'])}.\n\n"
        f"The real conversation: {meta['title']} on {meta['channel']}: https://www.youtube.com/watch?v={cfg['video_id']}\n\n"
        f"Everything in this video is AI-generated. Every voice is an AI echo, not the real person: {people} and {cfg['me']} "
        f"are all echoes here. None of it was said by the real people, and nothing here is their view. Echoes: {cfg.get('echo_model')}. "
        f"Voices ({'; '.join(vparts)}).\n\n"
        "If you are one of the people echoed here, or their family, and want this taken down, comment or get in touch"
        + (f" ({contact})" if contact else "") + " and it comes down within 24 hours.\n"
        "Made with https://github.com/kvcobb/podcast-weave\n")
    print(f"companion: {P/'companion.mp4'} ({_dur(P/'companion.mp4'):.1f} s). Upload it to YouTube as UNLISTED, turn on the altered or "
          f"synthetic content label, paste {P/'youtube-description.txt'} as the description, then run: python -m cpc weave {P} --segments <new video id>")


def weave(P, segments):
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); meta = json.loads((WORK / cfg["video_id"] / "meta.json").read_text())
    v, L = cfg["video_id"], cfg["pause_len"]
    w = dict(original=dict(id=v, title=meta["title"], channel=meta["channel"], duration=meta["duration"]),
             segments=dict(id=segments, title="Pause segment (AI echoes)"), kind="partial", echo_model=cfg.get("echo_model"),
             steps=[dict(video="original", start=cfg["start"], end=cfg["pause"], label=f"Original, {fmt(cfg['start'])} to {fmt(cfg['pause'])}"),
                    dict(video="segments", start=0, end=L, label=f"Pause at {fmt(cfg['pause'])}: {cfg['me']} joins"),
                    dict(video="original", start=cfg["pause"], end=cfg["resume_to"], label=f"Original, {fmt(cfg['pause'])} to {fmt(cfg['resume_to'])}"),
                    dict(video="segments", start=L, end=None, label="End card")])
    (SITE / "weaves").mkdir(exist_ok=True); (SITE / "weaves" / f"{v}.json").write_text(json.dumps(w, indent=1))
    (SITE / v).mkdir(exist_ok=True); (SITE / v / "index.html").write_text(PAGE % v)
    print(f"weave written: weaves/{v}.json and {v}/index.html. Watch locally: python -m cpc serve, then http://localhost:8000/{v}/\n"
          f"To list it on the landing page, add a card for {v}/ in index.html.")


def serve(port=8000):
    import http.server, functools
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    print(f"serving {SITE} at http://localhost:{port}/  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever()
