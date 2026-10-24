"""A live table with a dynamic floor: who speaks next is decided by the conversation, not a fixed rotation.

Each round a small "floor director" call reads the last turns and returns a bid per seat (urge 0-3, a move, a body cue); the
highest weighted bid speaks (recent silence raises urge, having just spoken lowers it); that seat's own soul writes the turn.
host_every=N gives the host (first seat) the floor after N turns of silence, as a short clarifying question, so a lively
two-way clash can't crowd the host out. Output: transcript.jsonl rows {seq, speaker, text, signal, kind, move}.
"""
import json, random, re
from pathlib import Path
from . import llm

RULES = """You are an AI ECHO in a disclosed, imagined conversation (not the real person). Speak ONE turn as spoken words only: no
stage directions, no speaker label, no quotation marks, no markdown. Stay in your own voice from your soul text. Real ideas, real
humor, a concrete image when the moment offers one. React to what was ACTUALLY just said; you may disagree, misunderstand, tease,
change the subject, or stay short. Never state invented personal facts about any real person (family, health, private life), and
never claim intimacy or private history with anyone. Do not begin with another speaker's name or repeat their phrase back. Avoid
stock mild oaths as a verbal tic. Never talk about who you really are, disclosures, takedowns or the show itself; just be present
and stay on the topic of the seed. Length: follow the target given."""


def _floor(history, seats, last, nature):
    h = "\n".join(f"{r['speaker']}: {r['text']}" for r in history[-7:]) or "(room just opened)"
    cast = "\n".join(f"- {s['slug']}: {s['nature']}" for s in seats)
    p = (f"You are the FLOOR DIRECTOR of a live table conversation. You do NOT write dialogue. Read the last turns and decide, for each seat, "
         f"how much they want the floor RIGHT NOW, like people at a real table. The last speaker was {last}.\nSEATS:\n{cast}\nLAST TURNS:\n{h}\n"
         "Return ONLY a JSON object mapping every seat slug to {\"urge\": 0-3 integer, \"move\": one of answer|interrupt|add|tease|object|ask|"
         "stay_quiet, \"signal\": a 3-8 word visible body cue}. The one just addressed usually has urge 2-3.")
    for _ in range(3):
        try:
            out = llm.ask(p, timeout=600)
            return json.loads(re.search(r"\{.*\}", out, re.S)[0])
        except Exception:
            continue
    return {s["slug"]: {"urge": 1, "move": "add", "signal": "leans in"} for s in seats}


def run(out_dir, seed, seats, souls, turns, first=None, host_every=0, resume=False):
    """seats: [{slug, nature}] (first = host). souls: {slug: soul text}. turns: total 'turn' rows wanted."""
    P = Path(out_dir); P.mkdir(parents=True, exist_ok=True); tp = P / "transcript.jsonl"
    hist = [json.loads(l) for l in tp.read_text().splitlines() if l.strip()] if (resume and tp.exists()) else []
    rnd = random.Random(20261024); spoke = {s["slug"]: -1 for s in seats}
    for r in hist: spoke[r["speaker"]] = r["seq"]
    last = hist[-1]["speaker"] if hist else seats[0]["slug"]; start = len(hist); host = seats[0]["slug"]
    while sum(1 for r in hist if r["kind"] == "turn") < turns:
        n = len(hist) + 1
        if first and n == start + 1:
            bids = {s["slug"]: {"urge": 3 if s["slug"] == first else 0, "move": "add", "signal": "settles in"} for s in seats}
        else:
            bids = _floor(hist, seats, last, None)
        score = {}
        for s in seats:
            b = bids.get(s["slug"], {}); g = n - spoke.get(s["slug"], -1)
            score[s["slug"]] = int(b.get("urge", 0)) + 0.25 * min(g, 6) + rnd.random() * 0.3 - (1.2 if s["slug"] == last else 0) \
                               - (3 if b.get("move") == "stay_quiet" else 0)
        who = max(score, key=score.get)
        if host_every and last != host and n - spoke.get(host, -1) > host_every:
            who = host; bids[host] = {**bids.get(host, {}), "move": "ask a short clarifying question"}
        mv = bids.get(who, {}).get("move", "add"); sig = bids.get(who, {}).get("signal", "")
        recent = "\n".join(f"{r['speaker']}: {r['text']}" for r in hist[-14:]) or "(the table has just sat down)"
        tgt = rnd.choice(["one or two sentences", "about 30 to 60 words", "about 50 to 90 words", "under 20 words", "about 60 to 110 words"])
        prompt = (f"THE ROOM'S SEED (anchor, not a script):\n{seed}\n\nTHE TABLE SO FAR:\n{recent}\n\nYou are {who}. Your move this turn: {mv}. "
                  f"You (visibly): {sig}. Speak your next turn now. Target length: {tgt}.")
        text = llm.ask(prompt, souls[who] + "\n\n" + RULES, timeout=900)
        text = re.sub(r"^(" + "|".join(re.escape(s["slug"]) for s in seats) + r")\s*:\s*", "", text, flags=re.I).strip().strip('"')
        hist.append(dict(seq=n, speaker=who, text=text, signal=sig, kind="turn", move=mv)); last = who; spoke[who] = n
        tp.write_text("".join(json.dumps(r) + "\n" for r in hist))
        print(f"{n:3d} {who}: {text[:100]}", flush=True)
    return hist
