"""Stage 1: a YouTube URL -> metadata, the creator's chapters, a timestamped transcript, speaker-labelled turns, and the
source video/audio, all in work/<video_id>/.

  python -m cpc ingest <url> --speakers "Matthew Berman,Sam Altman"   (first name = host; names as they appear in the episode)
"""
import json, re, subprocess, concurrent.futures as cf
from pathlib import Path
from .common import WORK, vid, fmt, ask_json, sh


def _captions(v):
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        t = YouTubeTranscriptApi().fetch(v)
        return [dict(start=s.start, dur=s.duration, text=s.text) for s in t]
    except Exception:
        return None


def _whisper(audio):
    """No captions: transcribe locally (faster-whisper). Slow on CPU for long episodes, but it works offline."""
    from faster_whisper import WhisperModel
    import os
    dev = "cuda" if os.environ.get("CPC_WHISPER_DEVICE", "auto") != "cpu" and _has_cuda() else "cpu"
    wm = WhisperModel(os.environ.get("CPC_WHISPER_MODEL", "small"), device=dev, compute_type="float16" if dev == "cuda" else "int8")
    segs, _ = wm.transcribe(str(audio), language=None)
    return [dict(start=s.start, dur=s.end - s.start, text=s.text.strip()) for s in segs]


def _has_cuda():
    try:
        import torch; return torch.cuda.is_available()
    except Exception:
        return False


def ingest(url, speakers):
    v = vid(url); D = WORK / v; S = D / "src"; S.mkdir(parents=True, exist_ok=True)
    names = [s.strip() for s in speakers.split(",") if s.strip()]
    if len(names) < 2: raise SystemExit("--speakers needs at least two names, host first, e.g. 'Matthew Berman,Sam Altman'")
    info_p = S / "info.json"
    if not info_p.exists():
        r = sh("yt-dlp", "-J", "--skip-download", f"https://www.youtube.com/watch?v={v}")
        if r.returncode: raise SystemExit("yt-dlp could not read the video:\n" + r.stderr[-800:])
        info_p.write_text(r.stdout)
    info = json.loads(info_p.read_text())
    if not list(S.glob("video.*")):
        sh("yt-dlp", "-f", "bv*[height<=1440][ext=mp4]/bv*[height<=1440]", "-o", str(S / "video.%(ext)s"), f"https://www.youtube.com/watch?v={v}")
    if not list(S.glob("audio.*")):
        sh("yt-dlp", "-f", "bestaudio", "-o", str(S / "audio.%(ext)s"), f"https://www.youtube.com/watch?v={v}")
    audio = next(S.glob("audio.*"), None); video = next(S.glob("video.*"), None)
    if not audio or not video:
        raise SystemExit("yt-dlp could not download the " + ("audio" if not audio else "video") + ". Update it (pip install -U yt-dlp); if YouTube "
                         "asks you to confirm you're not a bot, see yt-dlp's notes on cookies (--cookies-from-browser).")
    segs = _captions(v)
    if not segs:
        print("no YouTube captions available (or blocked); transcribing locally with Whisper, which can take a while on a CPU")
        segs = _whisper(audio)
    (D / "segments.json").write_text(json.dumps(segs))
    dur = float(info.get("duration") or (segs[-1]["start"] + segs[-1]["dur"]))
    chapters = [dict(start=c["start_time"], end=c["end_time"], title=c["title"]) for c in (info.get("chapters") or [])]
    meta = dict(video_id=v, title=info.get("title", ""), channel=info.get("channel") or info.get("uploader", ""),
                description=info.get("description", ""), upload_date=info.get("upload_date"), duration=dur,
                chapters=chapters, speakers=names, host=names[0])
    (D / "meta.json").write_text(json.dumps(meta, indent=1))
    turns = label(segs, meta)
    (D / "turns.json").write_text(json.dumps(turns, indent=1))
    print(f"{v}: {len(segs)} caption lines, {len(turns)} turns, {len(chapters)} chapters -> {D}")
    for c in chapters: print(f"  {fmt(c['start'])}-{fmt(c['end'])} {c['title']}")


def label(segs, meta, B=70, O=12):
    """Assign each caption line to a speaker, in overlapping blocks (captions carry no speaker names)."""
    names = meta["speakers"]; tags = [f"S{i}" for i in range(len(names))]
    roster = "; ".join(f"{t} = {n}{' (host)' if i == 0 else ''}" for i, (t, n) in enumerate(zip(tags, names)))
    sysmsg = (f"You label speakers in a podcast transcript. Title: {meta['title']} ({meta['channel']}). Speakers: {roster}. "
              "The host usually asks questions and reacts; guests answer at length. Output ONLY JSON.")
    blocks = [(i, min(len(segs), i + B)) for i in range(0, len(segs), B)]

    def one(b):
        s, e = b; ctx = max(0, s - O)
        lines = "\n".join(f"{i}|{segs[i]['text'].replace(chr(10), ' ')}" for i in range(ctx, e))
        p = (f"Lines {ctx} to {e-1}; lines before {s} are context only. Return JSON: a list of runs "
             f"[{{\"from\": id, \"to\": id, \"who\": one of {tags}}}] covering ids {s}..{e-1} in order with no gaps "
             f"(a run changes when the speaker changes; infer from content and flow).\n\n{lines}")
        return b, ask_json(p, sysmsg, want=list)

    who = [tags[-1]] * len(segs)
    with cf.ThreadPoolExecutor(6) as ex:
        for b, runs in ex.map(one, blocks):
            for r in runs:
                if r.get("who") not in tags: continue
                for i in range(max(b[0], r["from"]), min(b[1] - 1, r["to"]) + 1): who[i] = r["who"]
    turns = []
    for i, sg in enumerate(segs):
        name = names[tags.index(who[i])]; txt = sg["text"].replace("\n", " ")
        if turns and turns[-1]["who"] == name:
            turns[-1]["text"] += " " + txt; turns[-1]["t1"] = sg["start"] + sg["dur"]
        else:
            turns.append(dict(who=name, t0=sg["start"], t1=sg["start"] + sg["dur"], text=txt))
    return turns
