"""Stage 3: the pause. Plays the original from the start of a question to a moment you choose, pauses, you join as an echo,
the host and guest echoes talk with you, then the original resumes.

  python -m cpc pause <video_id> --from 20:10 --pause 20:32 [--resume-to 26:09] [--mode jam|beats] [--turns 24]

--from / --pause / --resume-to are rough; they are snapped to the nearest real silence in the audio so no word is cut.
Times can be anywhere in the episode; --resume-to defaults to the end of the chapter that contains the pause.

Modes (both need your soul: `python -m cpc me ...`):
  jam    (default) one room with host, guest and you. Your view comes in one point at a time; the host asks clarifying
         questions, the guest answers and challenges from their own pattern. Most natural.
  beats  your view as 2-4 set turns, each answered by the host and guest. Closest to what you actually said.
After the room: the host's hand-back line, and a coverage check (each of your points came up; nobody put words in another's mouth).
"""
import json, re
from pathlib import Path
from .common import load, ts, fmt, slug, section, ask_json, sh, PRIME
from . import floor, llm


def snap(audio, t, before=2.5, after=3.5, lean=0.0):
    """Move t to a pause in speech (>=0.15 s below -35 dB) within [t-before, t+after]. lean>0 prefers pauses after t
    (a pause point should follow the end of a sentence), lean<0 prefers pauses before t (a start point)."""
    r = sh("ffmpeg", "-v", "info", "-ss", str(max(0, t - before)), "-t", str(before + after), "-i", str(audio),
           "-af", "silencedetect=n=-35dB:d=0.15", "-f", "null", "-")
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    gaps = [(max(0, t - before) + s, max(0, t - before) + e) for s, e in zip(starts, ends)]
    if not gaps: return t

    def cost(g):
        d = (g[0] + g[1]) / 2 - t
        return abs(d) * (3 if (lean > 0 and d < -0.15) or (lean < 0 and d > 0.15) else 1) - 0.3 * (g[1] - g[0])
    s, e = min(gaps, key=cost)
    return round(min(s + 0.2, (s + e) / 2), 2)


_wm = None


def sentence_edge(audio, t, kind, window=6.0):
    """Listen to the audio around t (word timestamps) and return the end of the nearest sentence (kind='end', for a pause)
    or the start of the nearest sentence (kind='start', for where playback begins). Captions are too coarse to cut on."""
    global _wm
    from faster_whisper import WhisperModel
    import tempfile, os
    if _wm is None: _wm = WhisperModel("small", device="cpu", compute_type="int8")
    a0 = max(0.0, t - window)
    with tempfile.TemporaryDirectory() as d:
        clip = os.path.join(d, "w.wav")
        sh("ffmpeg", "-v", "error", "-y", "-ss", str(a0), "-t", str(2 * window), "-i", str(audio), "-ac", "1", "-ar", "16000", clip)
        segs, _ = _wm.transcribe(clip, word_timestamps=True)
        words = [w for s in segs for w in (s.words or [])]
    if not words: return t
    if kind == "end":
        ends = [a0 + w.end for w in words if w.word.strip().endswith((".", "?", "!"))]
        return min(ends, key=lambda e: abs(e - t) * (1 if e >= t - 1.0 else 2)) if ends else t
    starts = [a0 + words[i].start for i in range(len(words)) if i == 0 or words[i - 1].word.strip().endswith((".", "?", "!"))]
    return min(starts, key=lambda s: abs(s - t)) if starts else t


def boundary(turns, t, kind, audio=None):
    return sentence_edge(audio, t, kind) if audio else t


def my_points(D, meta, turns, t0, tw, name):
    words = (D / "me" / "my-words.txt").read_text() if (D / "me" / "my-words.txt").exists() else ""
    soul = (D / "souls" / f"{slug(name)}.md").read_text()
    p = (f"EPISODE: {meta['title']} ({meta['channel']}).\nTHE SECTION ({fmt(t0)}-{fmt(tw)}):\n{section(turns, t0, tw)}\n\n"
         f"THE VIEWER'S SOUL FILE:\n{soul[:12000]}\n\nTHEIR OWN WORDS:\n{words[:12000]}\n\n"
         "TASK: extract the viewer's GIST on this section as 6 to 10 distinct points, in the order they build. For each: one plain sentence, "
         "their own key phrases verbatim (short), and what they are asking or challenging with it. Keep their readings of the guests as their "
         "reading, open to correction. Do not add points they did not make. Return ONLY JSON: "
         "{\"points\": [{\"point\": str, \"phrases\": [str], \"asks\": str}]}")
    return ask_json(p)["points"]


def pause(v, t_from, t_pause, resume_to=None, mode="jam", nturns=24, host_every=4, model_label=None):
    D, meta, turns = load(v); audio = next((D / "src").glob("audio.*"))
    mej = json.loads((D / "me" / "me.json").read_text()) if (D / "me" / "me.json").exists() else None
    if not mej: raise SystemExit("build your own soul first: python -m cpc me <video_id> --audio ... --name ...")
    # rough times -> the nearest speaker change (a question starts / an answer ends) -> a real pause in the audio there
    t0 = snap(audio, boundary(turns, ts(t_from), "start", audio), 1.5, 0.3, lean=-1)
    t1 = snap(audio, boundary(turns, ts(t_pause), "end", audio), 0.3, 1.5, lean=1)
    ch = next((c for c in meta["chapters"] if c["start"] <= t1 < c["end"]), None)
    tr = ts(resume_to) if resume_to else (ch["end"] if ch else min(meta["duration"], t1 + 120))
    tr = snap(audio, boundary(turns, tr - (0 if resume_to else 1.0), "end", audio), 0.3, 1.5, lean=1)
    P = D / "partials" / f"{int(t0)}-{int(t1)}-{mode}"; P.mkdir(parents=True, exist_ok=True)
    for f in ("transcript.jsonl", "transcript.raw.jsonl", "check.json", "fix.json"):        # a re-run starts clean
        if (P / f).exists(): (P / f).rename(P / (f + ".prev"))
    host = meta["speakers"][0]; guests = meta["speakers"][1:]; me_name, me_slug = mej["name"], mej["slug"]
    label = model_label or llm.describe()
    cfg = dict(video_id=v, start=t0, pause=t1, resume_to=tr, watched_to=tr, mode=mode, host=host, guests=guests, me=me_name, echo_model=label)
    (P / "config.json").write_text(json.dumps(cfg, indent=1))
    print(f"start {fmt(t0)} ({t0}), pause {fmt(t1)} ({t1}), resume to {fmt(tr)} ({tr}) -> {P}")
    pts = my_points(D, meta, turns, t0, tr, me_name); (P / "points.json").write_text(json.dumps(pts, indent=1))
    souls = {slug(n): (D / "souls" / f"{slug(n)}.md").read_text() for n in meta["speakers"] + [me_name]}
    seats = [dict(slug=slug(host), nature=f"{host} echo (host): own interviewer style, short clarifying questions")] + \
            [dict(slug=slug(g), nature=f"{g} echo (guest): answers in their own pattern, challenges, asks back") for g in guests]
    ptxt = "\n".join(f"{i}. {x['point']} (their words: {'; '.join(x['phrases'])}) -> {x['asks']}" for i, x in enumerate(pts, 1))
    base = (PRIME + f"\n\nEPISODE: {meta['title']} ({meta['channel']}). The viewer watched the original from {fmt(t0)} to {fmt(t1)}; it is paused "
            f"there. Everyone here has ALSO watched the rest of this section, to {fmt(tr)}:\n{section(turns, t0, tr)}\n\n"
            f"THE ECHOES ARE HOSTED ON {label}. Everyone here is one of the AI echoes that people speculate about; that is the frame "
            f"{me_name} brings, and it is a conversation, not a debate to win.\n\n{me_name.upper()}'S VIEW (for {me_name}'s echo, in their words):\n{ptxt}\n\n")
    if mode == "jam":
        seed = base + (f"HOW THIS ROOM GOES: {me_name}'s echo opens with a brief knock (they've watched this segment and would like to come back to "
                       f"what was just said, from a different perspective). Then a natural multi-turn back-and-forth with SHORT turns. {me_name} brings "
                       f"the points in ONE AT A TIME, never as a monologue, spread evenly; goes deeper when asked. {host} asks clarifying questions in "
                       f"their own style. The guests answer from their own pattern, challenge, ask back, and say plainly where {me_name} has their view "
                       f"wrong. Nobody puts views in another speaker's mouth. {me_name}'s echo argues from ideas only: no anecdotes about family, "
                       "friends or private life.\n")
        (P / "seed.md").write_text(seed)
        floor.run(P, seed, seats + [dict(slug=me_slug, nature=f"{me_name}'s echo: brings their own view one point at a time, curious")],
                  souls, nturns, first=me_slug, host_every=host_every)
    else:
        beats = ask_json(f"{base}TASK: write {me_name}'s part as 2 to 4 BEATS (one spoken turn each, 90-190 words, in THEIR phrasing, each ending on "
                         f"a real question; beat 1 opens with a brief knock). Readings of the guests stay readings ('correct me if I have it wrong'). "
                         "Return ONLY JSON: {\"beats\": [{\"text\": str, \"to\": \"host\"|\"guest\"|\"both\"}]}")["beats"]
        seed = base + f"{me_name} speaks only in their marked beats; between them it is the host and guests answering, and talking to each other.\n"
        (P / "seed.md").write_text(seed); rows = []
        for b in beats:
            rows.append(dict(seq=len(rows) + 1, speaker=me_slug, text=b["text"], kind="turn", move="ask"))
            (P / "transcript.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            want = sum(1 for r in rows if r["kind"] == "turn") + 4
            rows = floor.run(P, seed, seats, souls, want, first=slug(guests[0]) if b.get("to") != "host" else slug(host), resume=True)
    rows = [json.loads(l) for l in (P / "transcript.jsonl").read_text().splitlines() if l.strip()]
    while rows and rows[-1]["speaker"] == slug(host) and len(rows) > 2: rows.pop()   # a dangling host question nobody answers
    nxt = next((t["text"] for t in turns if t["t0"] >= t1 - 1 and t["who"] == host), "")
    last = "\n".join(f"{r['speaker']}: {r['text']}" for r in rows)[-3000:]
    close = llm.ask(PRIME + f"\n\nYou are the {host} echo. The pause is ending; the last exchange was:\n{last}\n\nIn your own style, react in one "
                    f"line to what was just said, thank {me_name}, and lead back to where the original was (max 45 words). The original resumes "
                    f"with: \"{nxt[:300]}\" so do NOT say that yourself. Reply with only the words.", souls[slug(host)])
    rows.append(dict(seq=len(rows) + 1, speaker=slug(host), text=close.strip().strip('"'), kind="turn", move="handback", handback=True))
    (P / "transcript.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    w = sum(len(r["text"].split()) for r in rows)
    print(f"{len(rows)} turns, {w} words (~{w/150:.1f} min spoken)")
    j = check(P, pts)
    if j["misattributions"] or j.get("anecdotes") or any(x["covered"] == "no" for x in j["points"]): fix(P)
    return P


def check(P, pts=None):
    P = Path(P); pts = pts or json.loads((P / "points.json").read_text())
    rows = [json.loads(l) for l in (P / "transcript.jsonl").read_text().splitlines() if l.strip()]
    tr = "\n".join(f"[{i}] {r['speaker']}: {r['text']}" for i, r in enumerate(rows))
    j = ask_json("VIEWER'S POINTS:\n" + "\n".join(f"{i}. {x['point']}" for i, x in enumerate(pts, 1)) + f"\n\nTRANSCRIPT:\n{tr}\n\n"
                 "For each point: represented in the viewer's turns? (yes/partly/no + turn indexes). Also list any line where a speaker states "
                 "another speaker's view for them as agreed fact, and any invented personal anecdote about a real person. Return ONLY JSON: "
                 "{\"points\": [{\"n\": int, \"covered\": str, \"turns\": [int]}], \"misattributions\": [str], \"anecdotes\": [str]}")
    (P / "check.json").write_text(json.dumps(j, indent=1))
    miss = [p["n"] for p in j["points"] if p["covered"] == "no"]
    print(f"coverage: {sum(p['covered'] == 'yes' for p in j['points'])} yes, {sum(p['covered'] == 'partly' for p in j['points'])} partly, "
          f"missing {miss or 'none'}; misattributions {len(j['misattributions'])}; anecdotes {len(j.get('anecdotes', []))}  (details: {P/'check.json'})")
    return j


def fix(P):
    """Editor pass when the check finds problems. Each flag is judged: a real problem gets the smallest edit that fixes it; a
    flag that is harmless (e.g. a misreading the room itself corrected) is kept, with the reason recorded. Missing points come
    in through one short exchange before the hand-back. The version it edited is kept as transcript.before-fix.jsonl."""
    P = Path(P); cfg = json.loads((P / "config.json").read_text()); j = json.loads((P / "check.json").read_text())
    pts = json.loads((P / "points.json").read_text()); cur = (P / "transcript.jsonl").read_text()
    (P / "transcript.before-fix.jsonl").write_text(cur)                                    # the version this pass edits (incl. your hand edits)
    rows = [json.loads(l) for l in cur.splitlines() if l.strip()]
    missing = [pts[p["n"] - 1] for p in j["points"] if p["covered"] == "no" and 0 < p["n"] <= len(pts)]
    if not (j["misattributions"] or j.get("anecdotes") or missing):
        print("nothing to fix"); return
    body = "\n".join(f"[{i}] {r['speaker']}{' (HANDBACK: keep last)' if r.get('handback') else ''}: {r['text']}" for i, r in enumerate(rows))
    p = (PRIME + f"\n\nYou are the EDITOR of this AI-generated continuation. Keep every turn word for word EXCEPT where a change is needed below.\n"
         f"FLAGS from the checker (judge each one: if it is a real problem, make the smallest edit to that turn that fixes it; if it is harmless, "
         f"for instance a misreading the room itself corrects a turn later, or a fair summary of what the person said in the episode, leave it):\n"
         + "\n".join(f"- {x}" for x in j["misattributions"] + j.get("anecdotes", [])) +
         ("\nMISSING POINTS of the viewer to bring in, via ONE short exchange inserted just before the hand-back (the host asks a short clarifying "
          f"question that leads there, {cfg['me']} answers in their own words, max 70 words, and a guest responds in their own pattern, max 55 words):\n"
          + "\n".join(f"- {m['point']} (their words: {'; '.join(m['phrases'])})" for m in missing) if missing else "") +
         "\nThe hand-back stays last; you may adjust its first sentence so it reacts to the new last exchange. No invented personal facts.\n\n"
         f"TRANSCRIPT:\n{body}\n\nReturn ONLY JSON: {{\"turns\": [{{\"speaker\": slug, \"text\": str, \"edited\": bool, \"added\": bool, \"handback\": bool}}], "
         "\"decisions\": [str]}} (one decision line per flag: fixed how, or kept and why).")
    out = ask_json(p)
    new = out["turns"]; assert new and new[-1].get("handback"), "editor dropped the hand-back"
    (P / "transcript.jsonl").write_text("".join(json.dumps({**t, "seq": i + 1, "kind": "turn"}) + "\n" for i, t in enumerate(new)))
    (P / "fix.json").write_text(json.dumps(out["decisions"], indent=1))
    print("editor decisions:\n  " + "\n  ".join(out["decisions"]))
    check(P, pts)
