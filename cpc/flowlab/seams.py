"""Seams: every distinct switch A -> B in any route, as one short clip (A's last seconds, then B's first seconds)."""
import hashlib, json, os
from pathlib import Path
from .media import concat, silences

_MODEL = None


def transitions(W, routes):
    seen = {}
    for r in routes:
        for a, b in zip(r["segs"], r["segs"][1:]):
            seen.setdefault((a, b), 0); seen[(a, b)] += 1
    return seen   # (a, b) -> how many routes use it


def bounds(W, media, k):
    g = W["segs"][k]; a = g.get("start") or 0
    b = g["end"] if g.get("end") is not None else media.duration(g["video"])
    return a, b


def build(W, media, a, b, pad, outdir):
    a0, a1 = bounds(W, media, a); b0, b1 = bounds(W, media, b)
    ta = (max(a0, a1 - pad), a1); tb = (b0, min(b1, b0 + pad))
    wa = media.cut(W["segs"][a]["video"], *ta); wb = media.cut(W["segs"][b]["video"], *tb)
    out = Path(outdir) / f"{a}__{b}.wav"
    concat([wa, wb], out)
    return {"a": a, "b": b, "wav": str(out), "join": round(ta[1] - ta[0], 3), "a_range": ta, "b_range": tb, "_parts": (str(wa), str(wb))}


def _model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        name = os.environ.get("FLOWLAB_WHISPER", "large-v3-turbo")
        try: _MODEL = WhisperModel(name, device="cuda", compute_type="float16")
        except Exception: _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODEL


def transcribe(wav, cache):
    """Word timestamps for a clip, cached by the clip's content hash (re-runs cost nothing)."""
    h = hashlib.sha256(Path(wav).read_bytes()).hexdigest()[:20]
    f = Path(cache) / "transcripts" / (h + ".json")
    if f.exists(): return json.loads(f.read_text())
    segs, _ = _model().transcribe(str(wav), language="en", word_timestamps=True, vad_filter=False, beam_size=5)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(words)); return words


def describe(seam, words, sil):
    j = seam["join"]
    seam["a_words"] = " ".join(w["w"] for w in words if w["s"] < j)
    seam["b_words"] = " ".join(w["w"] for w in words if w["s"] >= j)
    last_a = max([w["e"] for w in words if w["s"] < j] or [0]); first_b = min([w["s"] for w in words if w["s"] >= j] or [j])
    seam["gap_at_join"] = round(max(0.0, first_b - last_a), 2)   # silence from A's last word to B's first word
    seam["silences"] = sil
    near = [s for s in sil if (s[1] or 1e9) > j - 3 and s[0] < j + 3]
    longest = max([((s[1] or j + 10) - s[0]) for s in near] or [0])
    seam["dead_air"] = {"score": 2 if seam["gap_at_join"] < 1.5 and longest < 1.5 else 1 if max(seam["gap_at_join"], longest) < 3 else 0,
                        "why": f"{seam['gap_at_join']} s between A's last word and B's first; longest silence near the switch {round(longest, 2)} s (silencedetect -40 dB, 1.5 s)"}
    return seam


def run(W, media, trans, pad, outdir, cache):
    out = []
    for (a, b), uses in sorted(trans.items(), key=lambda x: -x[1]):
        ga, gb = W["segs"][a], W["segs"][b]
        if ga["video"] == gb["video"] and ga.get("end") is not None and abs(ga["end"] - (gb.get("start") or 0)) < 0.05:
            out.append({"a": a, "b": b, "uses": uses, "continuous": True, "score": 1.0, "join": 0, "wav": None,
                        "a_range": (ga["end"], ga["end"]), "b_range": (gb.get("start") or 0, gb.get("start") or 0), "a_words": "", "b_words": "",
                        "dead_air": {"score": 2, "why": "same video, continuous: the player plays straight through"}, "judge": {}})
            continue
        s = build(W, media, a, b, pad, Path(outdir) / "seams")
        # each side on its own: a single pass over the joined clip drops speech that follows a silence
        wa, wb = s.pop("_parts"); j = s["join"]
        words = transcribe(wa, cache) + [{**w, "s": round(w["s"] + j, 2), "e": round(w["e"] + j, 2)} for w in transcribe(wb, cache)]
        s["uses"] = uses
        out.append(describe(s, words, silences(s["wav"])))
    return out
