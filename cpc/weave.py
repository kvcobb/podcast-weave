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
from .common import WORK, sh, fmt
from .render import _font, frame_at, _dur

SITE = Path(__file__).resolve().parent.parent


def endcard(P, cfg, meta):
    video = next((WORK / cfg["video_id"] / "src").glob("video.*"))
    fr = Image.open(frame_at(video, cfg["resume_to"] - 0.3, P / "endframe.png")).convert("RGB").resize((1280, 720))
    im = Image.blend(fr.filter(ImageFilter.GaussianBlur(26)), Image.new("RGB", (1280, 720), (10, 15, 21)), 0.78); d = ImageDraw.Draw(im)
    people = ", ".join([cfg["host"]] + cfg["guests"]) + f" and {cfg['me']}"
    y = 200; d.text((90, y), "That was a partial continuation.", font=_font(40, True), fill=(240, 240, 245)); y += 70
    for line in [f"The pause was AI-generated: {people} there are AI echoes", f"({cfg.get('echo_model', 'AI')}), not the real people. Everything else is the original."]:
        d.text((90, y), line, font=_font(22), fill=(205, 208, 218)); y += 34
    y += 40; d.text((90, y), f"Watch the whole conversation on {meta['channel']}'s channel:", font=_font(24), fill=(235, 235, 240)); y += 40
    d.text((90, y), meta["title"][:90], font=_font(24, True), fill=(240, 240, 245)); y += 38
    d.text((90, y), f"youtube.com/watch?v={cfg['video_id']}", font=_font(24), fill=(170, 190, 255))
    d.text((90, 640), "Make your own: github.com/kvcobb/podcast-weave", font=_font(18), fill=(150, 156, 170))
    im.save(P / "endcard.png")
    sh("ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", "8", "-i", str(P / "endcard.png"), "-f", "lavfi", "-t", "8", "-i", "anullsrc=r=44100:cl=stereo",
       "-vf", "fps=15,format=yuv420p", "-c:v", "libx264", "-tune", "stillimage", "-crf", "26", "-c:a", "aac", "-b:a", "96k", "-shortest", str(P / "endcard.mp4"))


def companion(P):
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); meta = json.loads((WORK / cfg["video_id"] / "meta.json").read_text())
    endcard(P, cfg, meta); d = _dur(P / "pause.mp4")
    (P / "comp.txt").write_text(f"file '{(P / 'pause.mp4').resolve()}'\nfile '{(P / 'endcard.mp4').resolve()}'\n")
    # a keyframe exactly where the end card starts: YouTube can only start playback at a keyframe
    r = sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(P / "comp.txt"), "-c:v", "libx264", "-crf", "26",
           "-force_key_frames", f"0,{d}", "-r", "15", "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-movflags", "+faststart", str(P / "companion.mp4"))
    if r.returncode: raise SystemExit(r.stderr[-800:])
    cfg["pause_len"] = round(d, 2); (P / "config.json").write_text(json.dumps(cfg, indent=1))
    people = ", ".join([cfg["host"]] + cfg["guests"])
    (P / "youtube-description.txt").write_text(
        f"Companion video for a paused-podcast experiment: the AI-generated pause segment, meant to be watched inside the weave page, which plays "
        f"{meta['channel']}'s real episode from its own YouTube upload and switches to this pause at {fmt(cfg['pause'])}.\n\n"
        f"The real conversation: {meta['title']} on {meta['channel']}: https://www.youtube.com/watch?v={cfg['video_id']}\n\n"
        f"Everything in this video is AI-generated. Every voice is an AI echo built from the episode, not the real person: {people} and {cfg['me']} "
        f"are all echoes here. None of it was said by the real people, and nothing here is their view. Echoes: {cfg.get('echo_model')}.\n\n"
        "If you are one of the people echoed here and want this taken down, comment or get in touch and it comes down within 24 hours.\n"
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
    page = (SITE / "nnYHg0gcWug" / "index.html").read_text().replace('WEAVE_ID = "nnYHg0gcWug"', f'WEAVE_ID = "{v}"')
    (SITE / v).mkdir(exist_ok=True); (SITE / v / "index.html").write_text(page)
    print(f"weave written: weaves/{v}.json and {v}/index.html. Watch locally: python -m cpc serve, then http://localhost:8000/{v}/")


def serve(port=8000):
    import http.server, functools
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    print(f"serving {SITE} at http://localhost:{port}/  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever()
