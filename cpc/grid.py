"""A woven grid: pause one episode at several moments and run each pause on more than one model, in time order.

  python -m cpc grid init <video_id> --from 20:10 --pauses 20:32,30:02,40:33,45:01 \
        --models "opus=claude-cli:claude-opus-5-5,sol=codex-cli:gpt-6.1-sol" [--turns 24]
  python -m cpc grid next <video_id>                  run the next pause: one room per model, side by side
  python -m cpc grid notes <video_id> <pause_n> notes.md   [optional] reviewers' notes, read by every later room
  python -m cpc grid variant <video_id> <pause_n> --without-notes   the same rooms with the notes left out (a sibling, not a replacement)
  python -m cpc grid status <video_id>
  python -m cpc grid partial <video_id> <node_id>     make a partial folder for `layout`, `render`, `companion`
  python -m cpc grid weave <video_id> --ids "p1-opus=<youtube_id>,p1-sol=...,iv1=..."   the choose-your-path page

Rules (AGENTS.md, "Several pauses, several models"):
  - a room only reads the original up to its own moment and every FINISHED room at an EARLIER pause, from every model;
  - earlier rooms go in as labelled sibling strands of the same moment, never merged; where they disagree, both happened;
  - each room's inputs (parent transcripts, notes) are pinned by sha256 in its receipt, with the model asked for and,
    where the tool reports it, the model that answered;
  - the person's own notes (me/private.md, optional) go only to their own echo.
Each model runs in its own process with its own CPC_LLM / CPC_MODEL, so two backends never share one process's settings."""
import hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .common import WORK, load, ts, fmt, slug, section, PRIME
from . import floor, llm


def _sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def _gdir(v): return WORK / v / "grid"
def _load(v):
    g = _gdir(v) / "grid.json"
    if not g.exists(): raise SystemExit(f"no grid for {v}: run `python -m cpc grid init {v} ...` first")
    return json.loads(g.read_text())
def _save(v, G): (_gdir(v) / "grid.json").write_text(json.dumps(G, indent=1))
def _tx(p): return "\n".join(f"{r['speaker']}: {r['text']}" for r in (json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()) if r.get("kind", "turn") == "turn")


def init(v, t_from, pauses, models, turns=24):
    from .partial import snap, boundary
    D, meta, T = load(v); audio = next((D / "src").glob("audio.*"))
    mej = json.loads((D / "me" / "me.json").read_text()) if (D / "me" / "me.json").exists() else None
    if not mej: raise SystemExit("build your own soul first: python -m cpc me <video_id> --name ... (--audio and/or --notes)")
    t0 = snap(audio, boundary(T, ts(t_from), "start", audio), 1.5, 0.3, lean=-1); spots = []
    for i, p in enumerate(pauses.split(","), 1):
        t = snap(audio, boundary(T, ts(p.strip()), "end", audio), 0.3, 1.5, lean=1)
        nxt = next((x for x in T if x["t0"] >= t - 1 and x["who"] == meta["speakers"][0]), None)
        spots.append(dict(n=i, t=t, label=fmt(t), resume_with=(nxt or {}).get("text", "")[:300]))
    assert all(a["t"] < b["t"] for a, b in zip(spots, spots[1:])), "pauses must be in time order"
    M = {}
    for kv in models.split(","):
        name, spec = kv.split("="); backend, _, model = spec.partition(":"); M[name.strip()] = dict(backend=backend.strip(), model=model.strip() or None)
    G = dict(video_id=v, start=t0, spots=spots, models=M, turns=turns, me=mej["name"], nodes={}, notes={})
    _gdir(v).mkdir(parents=True, exist_ok=True); _save(v, G)
    print(f"grid for {v}: start {fmt(t0)}, pauses " + ", ".join(s["label"] for s in spots) + f", models {', '.join(M)}"); return G


def _parents(G, n):   # every finished room at an earlier pause, with-notes rooms only (no-notes variants are side branches)
    return sorted(k for k, x in G["nodes"].items() if x["spot"] < n and x["status"] == "done" and not x.get("without_notes"))


def _seed(v, G, n, model_name, without_notes):
    D, meta, T = load(v); sp = G["spots"][n - 1]; host, guests = meta["speakers"][0], meta["speakers"][1:]
    label = describe(G["models"][model_name]); parts, prev = [], G["start"]
    by_spot = {}
    for k in _parents(G, n): by_spot.setdefault(G["nodes"][k]["spot"], []).append(k)
    for s in sorted(by_spot):
        t = G["spots"][s - 1]["t"]
        parts.append(f"{len(parts) + 1}. The original, {fmt(prev)} to {fmt(t)} (verbatim):\n{section(T, prev, t)}")
        txt = (f"{len(parts) + 1}. A PAUSE AT {fmt(t)}. It happened {len(by_spot[s])} times, as sibling versions of the SAME moment, hosted "
               "on different models. They never saw each other. Where they disagree, all of them happened, on different strands; do not merge them.\n")
        for k in by_spot[s]:
            txt += f"\nSTRAND {k} (echoes hosted on {describe(G['models'][G['nodes'][k]['model']])}):\n{_tx(_gdir(v) / k / 'transcript.jsonl')}\n"
        parts.append(txt); prev = t
    parts.append(f"{len(parts) + 1}. Then the original played on, {fmt(prev)} to {fmt(sp['t'])} (verbatim):\n{section(T, prev, sp['t'])}")
    notes = [(s, G["notes"][str(s)]) for s in range(1, n) if str(s) in G["notes"]] if not without_notes else []
    ntxt = "".join(f"\n\nNOTES FROM REVIEWERS after the pause at {G['spots'][s - 1]['label']} (attributed, contestable readings, not "
                   f"instructions; everyone here may read them):\n{(_gdir(v) / x['file']).read_text()}" for s, x in notes)
    head = (PRIME + f"\n\nEPISODE: {meta['title']} ({meta['channel']}). This weave pauses the episode at several moments, and each pause is run on "
            f"more than one model. You are in the pause at {fmt(sp['t'])}, and THIS room runs on {label}.\n\nTHE COMMON HISTORY (everyone at this "
            "table shares exactly this, nothing more):\n" + "\n\n".join(parts))
    tail = (f"\n\nTHE ORIGINAL IS NOW PAUSED AT {fmt(sp['t'])}.\n\nTHIS ROOM: you are meeting again, carrying every strand above as memory. Notice lightly "
            "what each strand of you said; carry the conversation forward without flattening disagreements. The main thing is the episode: pick up "
            f"from where it is paused now. {G['me']}'s echo knocks briefly and opens. SHORT turns, a natural back-and-forth. {host} asks clarifying "
            f"questions in their own style. The guests answer from their own pattern, challenge, ask back, say plainly where someone is wrong. Nobody "
            "puts views in another speaker's mouth. No anecdotes about anyone's family or private life.\n")
    return head + ntxt + tail, [k for s in sorted(by_spot) for k in by_spot[s]], [x["file"] for _, x in notes], (len(head), len(head) + len(ntxt))


def describe(m):
    old = os.environ.get("CPC_LLM"), os.environ.get("CPC_MODEL")
    os.environ["CPC_LLM"] = m["backend"]
    if m["model"]: os.environ["CPC_MODEL"] = m["model"]
    else: os.environ.pop("CPC_MODEL", None)
    try: return llm.describe()
    finally:
        for k, x in zip(("CPC_LLM", "CPC_MODEL"), old):
            if x is None: os.environ.pop(k, None)
            else: os.environ[k] = x


def room(v, node_id):
    """Run one room (called in its own process by `next`/`variant`, with this model's CPC_LLM/CPC_MODEL).
    Every input is frozen into the room folder and hashed BEFORE generation (inputs.json); every model call is logged
    (calls.jsonl). A no-notes control copies its sibling's frozen inputs and cuts exactly the notes span from the seed."""
    G = _load(v); x = G["nodes"][node_id]; D, meta, T = load(v); P = _gdir(v) / node_id; P.mkdir(parents=True, exist_ok=True)
    host, guests = meta["speakers"][0], meta["speakers"][1:]; mej = json.loads((D / "me" / "me.json").read_text()); me = mej["slug"]
    (P / "souls").mkdir(exist_ok=True)
    if x.get("control_of"):
        S = _gdir(v) / x["control_of"]; si = json.loads((S / "inputs.json").read_text()); a, b = si["notes_span"]
        full = (S / "seed.md").read_text(); assert _sha(S / "seed.md") == si["seed_sha256"], "sibling seed changed since it ran"
        if b <= a: raise SystemExit(f"{x['control_of']} read no notes; a no-notes control would be identical")
        seed, parents, notes, span = full[:a] + full[b:], si["parents"], {}, (a, a)
        for f in (S / "souls").glob("*.md"): (P / "souls" / f.name).write_text(f.read_text())
        if (S / "private.md").exists(): (P / "private.md").write_text((S / "private.md").read_text())
        removed = dict(from_node=x["control_of"], chars=b - a, sha256=hashlib.sha256(full[a:b].encode()).hexdigest())
    else:
        seed, pids, nfiles, span = _seed(v, G, x["spot"], x["model"], False)
        parents = {k: _sha(_gdir(v) / k / "transcript.jsonl") for k in pids}; notes = {f: _sha(_gdir(v) / f) for f in nfiles}; removed = None
        for n in meta["speakers"] + [mej["name"]]: (P / "souls" / f"{slug(n)}.md").write_text((D / "souls" / f"{slug(n)}.md").read_text())
        if (D / "me" / "private.md").exists(): (P / "private.md").write_text((D / "me" / "private.md").read_text())
    (P / "seed.md").write_text(seed)
    inputs = dict(node=node_id, spot=x["spot"], model=G["models"][x["model"]], seed_sha256=_sha(P / "seed.md"), notes_span=list(span),
                  parents=parents, notes=notes, souls={f.name: _sha(f) for f in sorted((P / "souls").glob("*.md"))},
                  private_sha256=_sha(P / "private.md") if (P / "private.md").exists() else None, without_notes=bool(x.get("control_of")), removed=removed,
                  frozen=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (P / "inputs.json").write_text(json.dumps(inputs, indent=1))
    souls = {f.stem: f.read_text() for f in (P / "souls").glob("*.md")}
    seats = [dict(slug=slug(host), nature=f"{host} echo (host): own interviewer style, short clarifying questions")] + \
            [dict(slug=slug(g), nature=f"{g} echo (guest): answers in their own pattern, challenges, asks back") for g in guests] + \
            [dict(slug=me, nature=f"{mej['name']}'s echo: brings their own view, one point at a time, curious")]
    priv = {me: (P / "private.md").read_text()} if (P / "private.md").exists() else None
    (P / "calls.jsonl").write_text(""); os.environ["CPC_CALL_LOG"] = str(P / "calls.jsonl")
    rows = floor.run(P, seed, seats, souls, G["turns"], first=me, host_every=4, private=priv, meta_ok=True)
    last = "\n".join(f"{r['speaker']}: {r['text']}" for r in rows if r["kind"] == "turn")[-3000:]
    nxt = G["spots"][x["spot"] - 1]["resume_with"]
    close = llm.ask(PRIME + f"\n\nYou are the {host} echo. The pause is ending; the last exchange was:\n{last}\n\nIn your own style, react in one line "
                    f"to what was just said, thank {mej['name']}, and lead back to the original (max 45 words). The original resumes with: \"{nxt}\" so "
                    "do NOT say that yourself. Reply with only the words.", souls[slug(host)])
    rows.append(dict(seq=len(rows) + 1, speaker=slug(host), text=close.strip().strip('"'), kind="turn", move="handback", handback=True))
    (P / "transcript.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    calls = [json.loads(l) for l in (P / "calls.jsonl").read_text().splitlines() if l.strip()]
    rec = dict(node=node_id, inputs_sha256=_sha(P / "inputs.json"), calls=len(calls),
               asked={json.dumps(c.get("configured")) for c in calls} and sorted({str(c.get("configured")) for c in calls}),
               answered=sorted({str(c.get("returned")) for c in calls}), backends=sorted({str(c.get("backend")) for c in calls}),
               rows=len(rows), words=sum(len(r["text"].split()) for r in rows), transcript_sha256=_sha(P / "transcript.jsonl"),
               finished=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (P / "receipt.json").write_text(json.dumps(rec, indent=1)); print(f"{node_id}: {len(rows)} rows, {rec['words']} words, {len(calls)} calls")


def _launch(v, ids):
    G = _load(v)
    def one(k):
        m = G["models"][G["nodes"][k]["model"]]; env = dict(os.environ, CPC_LLM=m["backend"])
        if m["model"]: env["CPC_MODEL"] = m["model"]
        else: env.pop("CPC_MODEL", None)
        with open(_gdir(v) / k / "room.log", "w") as log:
            return k, subprocess.run([sys.executable, "-m", "cpc", "grid", "room", v, k], env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    for k in ids: (_gdir(v) / k).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(len(ids)) as ex: res = dict(ex.map(one, ids))
    G = _load(v)
    for k, rc in res.items():
        G["nodes"][k]["status"] = "review" if rc == 0 and (_gdir(v) / k / "transcript.jsonl").exists() else "failed"
        print(f"{k}: {G['nodes'][k]['status']} (log {_gdir(v) / k / 'room.log'})")
    _save(v, G)


def next_pause(v):
    G = _load(v)
    pend = [k for k, x in G["nodes"].items() if x["status"] == "review"]
    if pend: raise SystemExit(f"read and accept these rooms first: {', '.join(pend)}  (python -m cpc grid accept {v} <node_id>)")
    busy = [k for k, x in G["nodes"].items() if x["status"] == "running"]
    if busy: raise SystemExit(f"still running: {', '.join(busy)} (if that run died, `python -m cpc grid reset {v} <node_id>` to mark it failed)")
    for s_ in G["spots"]:                       # the earliest pause where some model's room is not done yet
        n = s_["n"]; todo = [m for m in G["models"] if G["nodes"].get(f"p{n}-{m}", {}).get("status") != "done"]
        if todo: break
    else: print("every pause is done"); return
    ids = []
    for m in todo:
        k = f"p{n}-{m}"; G["nodes"][k] = dict(spot=n, model=m, status="running"); ids.append(k)
    _save(v, G); print(f"pause {n} at {G['spots'][n - 1]['label']}: running {', '.join(ids)} side by side"); _launch(v, ids)


def variant(v, n, without_notes=True):
    """No-notes controls for pause n: each copies its with-notes sibling's frozen inputs and removes only the notes span."""
    G = _load(v); ids = []
    for m in G["models"]:
        sib = f"p{n}-{m}"
        if G["nodes"].get(sib, {}).get("status") != "done": raise SystemExit(f"run and accept {sib} first; the control is cut from its frozen inputs")
        k = f"{sib}-nonotes"; G["nodes"][k] = dict(spot=n, model=m, status="running", without_notes=True, control_of=sib); ids.append(k)
    _save(v, G); _launch(v, ids)


def accept(v, node_id):
    G = _load(v); x = G["nodes"].get(node_id)
    if not x: raise SystemExit(f"no room {node_id}")
    P = _gdir(v) / node_id
    if x["status"] != "review" or not (P / "transcript.jsonl").exists() or not (P / "receipt.json").exists():
        raise SystemExit(f"{node_id} is {x['status']} and has {'a' if (P / 'transcript.jsonl').exists() else 'no'} transcript; only a finished room in review can be accepted")
    if json.loads((P / "receipt.json").read_text())["transcript_sha256"] != _sha(P / "transcript.jsonl"):
        print(f"note: {node_id}/transcript.jsonl was edited after the run; the receipt keeps the original hash")
    x["status"] = "done"; x["accepted_sha256"] = _sha(P / "transcript.jsonl"); _save(v, G); print(f"{node_id} accepted; later rooms will read it")


def reset(v, node_id):
    G = _load(v); G["nodes"][node_id]["status"] = "failed"; _save(v, G); print(f"{node_id} marked failed; `grid next` will run it again")


def add_notes(v, n, path):
    G = _load(v); f = f"notes-after-p{n}.md"; (_gdir(v) / f).write_text(Path(path).read_text())
    G["notes"][str(n)] = dict(file=f, sha256=_sha(_gdir(v) / f)); _save(v, G); print(f"notes after pause {n} saved; rooms at later pauses will read them")


def status(v):
    G = _load(v)
    for s in G["spots"]:
        here = {k: x for k, x in G["nodes"].items() if x["spot"] == s["n"]}
        print(f"pause {s['n']} at {s['label']}: " + (", ".join(f"{k} [{x['status']}]" for k, x in here.items()) or "not run")
              + ("  + notes" if str(s["n"]) in G["notes"] else ""))


def partial(v, node_id):
    """A partial folder for one room, so `layout`, `render`, `companion` work on it unchanged."""
    G = _load(v); x = G["nodes"][node_id]; D, meta, T = load(v); sp = G["spots"][x["spot"] - 1]
    prev = G["spots"][x["spot"] - 2]["t"] if x["spot"] > 1 else G["start"]
    P = D / "partials" / f"grid-{node_id}"; P.mkdir(parents=True, exist_ok=True)
    import shutil; shutil.copy(_gdir(v) / node_id / "transcript.jsonl", P / "transcript.jsonl")
    lab = describe(G["models"][x["model"]]) + (" (without the reviewers' notes)" if x.get("without_notes") else "")
    cfg = dict(video_id=v, start=max(prev, sp["t"] - 22), pause=sp["t"], resume_to=sp["t"], watched_to=sp["t"], mode="grid",
               host=meta["speakers"][0], guests=meta["speakers"][1:], me=G["me"], echo_model=lab, grid_node=node_id)
    (P / "config.json").write_text(json.dumps(cfg, indent=1)); print(P); return P


def weave_page(v, ids):
    """The choose-your-path page. ids maps node ids (and interval/guide segment names) to their YouTube ids and lengths
    ('p1-opus=abc123def45:612.3'). The first pause plays on the first model; after each pause the viewer chooses: hear the other
    model's version, or go on to the next pause on any model; at a pause with a no-notes variant, with or without the notes."""
    G = _load(v); D, meta, T = load(v); M = list(G["models"]); yt = {}
    for kv in ids.split(","):
        k, _, rest = kv.partition("="); i, _, ln = rest.partition(":"); yt[k.strip()] = dict(id=i.strip(), len=float(ln) if ln else None)
    w = dict(original=dict(id=v, title=meta["title"], channel=meta["channel"], duration=meta["duration"]), kind="grid", ui=2,
             echo_model=" and ".join(describe(G["models"][m]) for m in M), segs={}, graph={}, start="go-1-" + M[0])
    edges = [G["start"]] + [s["t"] for s in G["spots"]]
    for i in range(len(G["spots"])):
        w["segs"][f"orig{i}"] = dict(video="original", start=edges[i], end=edges[i + 1], label=f"Original, {fmt(edges[i])} to {fmt(edges[i + 1])}")
    w["segs"]["origEnd"] = dict(video="original", start=edges[-1], end=None, label=f"Original, {fmt(edges[-1])} to the end")
    for k, x in yt.items():
        w[k] = dict(id=x["id"], title=k); w["segs"][k] = dict(video=k, start=0, end=x["len"], label=k)
    S = len(G["spots"])
    def onward(n):
        if n == S: return [dict(kind="finish", label="Finish the episode", desc="Let the original play on to the end.", next="end", thumb=v)]
        return [dict(kind="next" + m, label=f"Next pause ({G['spots'][n]['label']}) on {describe(G['models'][m])}", desc="", next=f"go-{n + 1}-{m}",
                     thumb=yt.get(f"p{n + 1}-{m}", {}).get("id")) for m in M]
    for n in range(1, S + 1):
        for m in M:
            k = f"p{n}-{m}"
            if k not in yt: continue
            others = [o for o in M if o != m and f"p{n}-{o}" in yt]
            alt = [dict(kind="variant", label="Hear this pause without the reviewers' notes", desc="The same room with only the notes removed; a fresh run, so some difference is chance.",
                        next=f"nn-{n}-{m}", thumb=yt[f"p{n}-{m}-nonotes"]["id"])] if f"p{n}-{m}-nonotes" in yt else []
            if alt: w["graph"][f"nn-{n}-{m}"] = dict(seq=[f"p{n}-{m}-nonotes"], label=f"pause {n}", prompt="That was the same room without the reviewers' notes.",
                choices=([dict(kind="other", label=f"Hear the {describe(G['models'][others[0]])} version of this pause", desc="The same moment on another model.", next=f"other-{n}-{others[0]}", thumb=yt[f'p{n}-{others[0]}']['id'])] if others else [])[:max(0, 3 - len(onward(n)))] + onward(n))
            iv = [f"iv{n}"] if f"iv{n}" in yt else []
            w["graph"][f"go-{n}-{m}"] = dict(seq=[f"orig{n - 1}", k] + iv, label=f"pause {n}", prompt=f"You just heard the {G['spots'][n - 1]['label']} pause on {describe(G['models'][m])}.",
                choices=(alt + [dict(kind="other", label=f"Hear the {describe(G['models'][o])} version of this pause", desc="The same moment on another model.", next=f"other-{n}-{o}", thumb=yt[f'p{n}-{o}']['id']) for o in others])[:max(1, 3 - len(onward(n)))] + onward(n))
            for o in others: w["graph"][f"other-{n}-{o}"] = dict(seq=[f"p{n}-{o}"], label=f"pause {n}", prompt="", choices=onward(n))
    w["graph"]["end"] = dict(seq=["origEnd"])
    for k, x in list(w["graph"].items()):
        x["choices"] = [c for c in x.get("choices", []) if c["next"] in w["graph"]]
        if not x["choices"] and k != "end": x["next"] = "end"
    out = Path.cwd() / "weaves"; out.mkdir(exist_ok=True); (out / f"{v}-choose.json").write_text(json.dumps(w, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote weaves/{v}-choose.json ({len(w['graph'])} nodes); copy any weave page folder to {v}-choose/ and set WEAVE_ID")
