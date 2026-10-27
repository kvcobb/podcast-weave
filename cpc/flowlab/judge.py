"""Judge each seam with a language model: does the switch land for a viewer hearing it?"""
import hashlib, json, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .. import llm

RUBRIC_V = "flowlab-judge-v1"
SYSTEM = """You judge the seams of a "podcast weave": a real podcast that pauses at chosen moments while AI echoes of the
speakers (and of the viewer) continue the conversation in rooms, then the original resumes. A seam is the moment one
clip ends and the next begins. You get the last seconds of clip A and the first seconds of clip B as speech-to-text
(errors are likely), plus both clips' labels. Judge only what a first-time viewer would hear and feel at that switch.
Every room and house clip carries an on-screen AI-echo label for its whole length; the audio check below is only about
whether the SPOKEN opening also orients the viewer.
Answer with ONE JSON object and nothing else:
{"edge": {"score": 0-2, "why": "..."},          // 2 = A stops on a finished sentence/thought; 0 = cut mid-word or mid-thought
 "sense": {"score": 0-2, "why": "..."},         // 2 = B's opening follows naturally from A's last words; 0 = jarring, confusing
 "repetition": {"score": 0-2, "why": "..."},    // 2 = nothing repeats across the switch; 0 = B repeats what A just said
 "orient": {"score": 0-2, "why": "..."},        // 2 = within B's opening a viewer knows where they are (who, what, why now)
 "land": "one sentence: what would make this switch land better, or 'fine as is'",
 "glue": "if a short bridge line (under 12 words, spoken by a house voice) would help, write it; else empty"}
Keep each "why" under 20 words. Be honest and specific; do not praise."""


def _prompt(W, s):
    la = (W["segs"][s["a"]].get("label") or s["a"]); lb = (W["segs"][s["b"]].get("label") or s["b"])
    return (f"A = {la}\nB = {lb}\n\nLast ~10 s of A (speech-to-text):\n{s['a_words'] or '(no speech)'}\n\n"
            f"First ~10 s of B (speech-to-text):\n{s['b_words'] or '(no speech)'}\n\n"
            f"Measured: {s['dead_air']['why']}.\nJudge this switch.")


def judge_one(W, s, cache):
    p = _prompt(W, s); h = hashlib.sha256((RUBRIC_V + SYSTEM + p).encode()).hexdigest()[:20]
    f = Path(cache) / "judge" / (h + ".json")
    if f.exists(): return json.loads(f.read_text())
    txt = llm.ask(p, system=SYSTEM, timeout=600)
    m = re.search(r"\{.*\}", txt, re.S)
    j = json.loads(m.group(0)) if m else {"error": txt[:300]}
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(j)); return j


def run(W, seams, cache, workers=4):
    todo = [s for s in seams if not s.get("continuous")]
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda s: judge_one(W, s, cache), todo))
    for s, j in zip(todo, res):
        s["judge"] = j
        parts = [j.get(k, {}).get("score") for k in ("edge", "sense", "repetition", "orient")] + [s["dead_air"]["score"]]
        parts = [x for x in parts if isinstance(x, (int, float))]
        s["score"] = round(sum(parts) / (2 * len(parts)), 3) if parts else None   # 0..1
    return seams
