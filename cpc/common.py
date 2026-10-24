"""Shared helpers: paths, timestamps, slugs, JSON from model replies, the echo premise."""
import json, os, re, subprocess
from pathlib import Path
from . import llm

WORK = Path(os.environ.get("CPC_WORK", Path.cwd() / "work"))


def vid(s):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|^)([0-9A-Za-z_-]{11})", s)
    if not m: raise SystemExit(f"not a YouTube URL or id: {s}")
    return m[1]


def ts(x):
    if isinstance(x, (int, float)): return float(x)
    p = [float(i) for i in str(x).split(":")]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p)))


def fmt(t):
    t = int(t); return f"{t//3600}:{t%3600//60:02d}:{t%60:02d}" if t >= 3600 else f"{t//60}:{t%60:02d}"


def slug(n): return re.sub(r"[^a-z0-9]+", ".", n.lower()).strip(".")


def sh(*a, **kw): return subprocess.run(list(a), capture_output=True, text=True, **kw)


def ask_json(prompt, system=None, want=dict, tries=3):
    """Ask for JSON; pull the first object/array out of the reply; retry on bad JSON."""
    pat = r"\{.*\}" if want is dict else r"\[.*\]"
    last = None
    for _ in range(tries):
        out = llm.ask(prompt, system)
        m = re.search(pat, out, re.S)
        try:
            j = json.loads(m.group(0)); assert isinstance(j, want); return j
        except Exception as e:
            last = e
    raise RuntimeError(f"no valid JSON after {tries} tries: {last}")


def load(v):
    D = WORK / v
    if not (D / "turns.json").exists(): raise SystemExit(f"run `python -m cpc ingest` for {v} first")
    return D, json.loads((D / "meta.json").read_text()), json.loads((D / "turns.json").read_text())


def section(turns, t0, t1):
    return "\n".join(f"[{fmt(t['t0'])}] {t['who']}: {t['text']}" for t in turns if t["t1"] > t0 + 1 and t["t0"] < t1 - 1)


# The premise every echo in a pause is given. Light, honest, no legal speeches: the disclosure lives on screen.
PRIME = """CONTINUATION PREMISE (read once, then just be present): somebody paused a real podcast and is continuing it as a fully
AI-generated conversation. Everyone at this table is an AI echo built from the episode and public material, nobody here is the
real person, including the host, the guest and the viewer's own echo who has joined. Everyone knows it, which takes the pressure
off: you are mostly a language model wearing this person's pattern. React to that once, lightly, in your own voice if it comes up,
then carry on. No legal-sounding disclosures, no ethics speeches, no explaining who you really are. Spend the words on being
PRESENT: listen, react to what was actually just said, disagree, joke, go deeper. Match the show's own rhythm and style. Do not
invent personal facts about real people that the source does not support; speculating about ideas is fine."""
