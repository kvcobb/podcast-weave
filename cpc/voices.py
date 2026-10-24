"""Reference clips for cloning: ~15-20 s of each episode speaker talking alone (picked from the episode itself), and your own clip.

  python -m cpc voices <video_id>                      pick a clip per episode speaker (prints the choice; listen to it)
  python -m cpc voices <video_id> --me my-voice.m4a    normalise your own clip (15-30 s of you talking clearly, no music)
  python -m cpc voices <video_id> --use "Name=clip.wav"  supply a clip for a speaker yourself (e.g. a host who never talks long)
Each clip is saved as work/<id>/voices/<slug>.wav with the words it contains in <slug>.txt (cloning uses both).
"""
import json, re
from pathlib import Path
import numpy as np
from .common import load, slug, sh

WIN = 18.0


def _whisper():
    from faster_whisper import WhisperModel
    return WhisperModel("small", device="cpu", compute_type="int8")


def _norm(src, dst, start=None, dur=None):
    a = ["ffmpeg", "-v", "error", "-y"] + (["-ss", str(start)] if start is not None else []) + ["-i", str(src)] + \
        (["-t", str(dur)] if dur else []) + ["-ac", "1", "-ar", "24000", "-af", "loudnorm=I=-18:TP=-2,afade=t=in:d=0.05" +
                                              (f",afade=t=out:st={dur-0.3}:d=0.3" if dur else ""), str(dst)]
    r = sh(*a)
    if r.returncode: raise SystemExit(r.stderr[-500:])


def voices(v, me=None, use=None):
    D, meta, turns = load(v); V = D / "voices"; V.mkdir(exist_ok=True); audio = next((D / "src").glob("audio.*"))
    wm = _whisper()
    if use:
        name, clip = use.split("=", 1); out = V / f"{slug(name)}.wav"; _norm(clip, out)
        segs, _ = wm.transcribe(str(out)); (V / f"{slug(name)}.txt").write_text(" ".join(s.text.strip() for s in segs)); print("saved", out); return
    if me:
        mej = json.loads((D / "me" / "me.json").read_text()); out = V / f"{mej['slug']}.wav"; _norm(me, out)
        segs, _ = wm.transcribe(str(out)); txt = " ".join(s.text.strip() for s in segs)
        (V / f"{mej['slug']}.txt").write_text(txt); print("saved", out, "|", txt[:120]); return
    import soundfile as sf
    full = D / "src" / "full24k.wav"
    if not full.exists(): sh("ffmpeg", "-v", "error", "-y", "-i", str(audio), "-ac", "1", "-ar", "24000", str(full))
    x, sr = sf.read(str(full))
    for name in meta["speakers"]:
        cands = []
        for t in sorted((t for t in turns if t["who"] == name), key=lambda t: t["t1"] - t["t0"], reverse=True)[:8]:
            span = t["t1"] - t["t0"]
            if span < WIN + 4: continue
            for off in (2.0, span / 2 - WIN / 2, span - WIN - 2):
                cands.append(t["t0"] + max(2.0, off))
        if not cands:
            print(f"{name}: no stretch of {WIN:.0f}+ s talking alone; supply one with --use \"{name}=clip.wav\""); continue
        best = None
        for i, a in enumerate(cands[:12]):
            seg = x[int(a * sr):int((a + WIN) * sr)]
            if len(seg) < sr * WIN * 0.9: continue
            frames = seg[: len(seg) // 2400 * 2400].reshape(-1, 2400); rms = np.sqrt((frames ** 2).mean(1)) + 1e-9
            steady = float(np.std(np.log(rms)))                 # lower = steadier level (less music, fewer jumps)
            tmp = V / f".cand-{slug(name)}-{i}.wav"; sf.write(str(tmp), seg, sr)
            s, _ = wm.transcribe(str(tmp)); txt = " ".join(z.text.strip() for z in s); wps = len(txt.split()) / WIN
            score = wps - steady - (2 if "[" in txt or "music" in txt.lower() else 0)
            if not best or score > best[0]: best = (score, a, txt)
            tmp.unlink()
        if not best: continue
        out = V / f"{slug(name)}.wav"; _norm(full, out, best[1], WIN)
        (V / f"{slug(name)}.txt").write_text(best[2])
        print(f"{name}: {best[1]:.0f}-{best[1]+WIN:.0f} s -> {out}\n   \"{best[2][:140]}\"")
    print("Listen to each clip before rendering: one voice, no music, no laughter over it.")
