"""Routes through a weave: every path through the graph, and the plain line under each room preference."""
import re

MODELS = re.compile(r"\b(Opus|Sonnet|Haiku|Fable|Sol|Astra|Gemini|Grok|GPT[-\w.]*)\b", re.I)


def graph_routes(W, cap=20000):
    """Every distinct segment sequence a viewer can play by following next/choices from the start node."""
    G, out, seen = W["graph"], [], set()
    def dfs(n, segs, nodes):
        if len(out) >= cap: return
        node = G[n]; segs = segs + node["seq"]; nodes = nodes + [n]
        nxt = [node["next"]] if node.get("next") else [c["next"] for c in node.get("choices", [])]
        nxt = [x for x in nxt if x in G and x not in nodes]
        if not nxt:
            key = tuple(segs)
            if key not in seen: seen.add(key); out.append({"kind": "path", "nodes": nodes, "segs": list(segs)})
            return
        for x in nxt: dfs(x, segs, nodes)
    dfs(W["start"], [], [])
    return out


def plain_lines(W):
    """The plain navigation's line (weave.js buildPlain/plainLine) for each preference: each model, then original only."""
    S, G = W["segs"], W["graph"]
    origs = sorted([k for k, s in S.items() if s["video"] == "original"], key=lambda k: S[k]["start"])
    guides = {n["guide"]["seg"] for n in G.values() if n.get("guide")}
    at, seen, queue = {}, set(), [(W["start"], S[origs[0]]["start"])]
    while queue:
        nid, c0 = queue.pop(0); key = (nid, c0)
        if key in seen or nid not in G: continue
        seen.add(key); c = c0; n = G[nid]
        for k in n["seq"]:
            g = S.get(k)
            if not g: continue
            if g["video"] == "original": c = g["end"] if g.get("end") is not None else c; continue
            at.setdefault(k, c)
        for nx in [n.get("next")] + [x["next"] for x in n.get("choices", [])]:
            if nx: queue.append((nx, c))
    spots = [S[k]["end"] for k in origs if S[k].get("end") is not None]
    rooms, models = {}, []
    for k, sp in at.items():
        g = S[k]; lab = g.get("label") or ""
        if sp not in spots or g.get("end") is None or k in guides or re.search("describe the choices", lab, re.I): continue
        m = MODELS.search(lab)
        if m and re.match(r"Pause", lab, re.I):
            name = m.group(1)[0].upper() + m.group(1)[1:]
            rooms.setdefault(sp, []).append({"seg": k, "model": name, "notes": not re.search("without", lab, re.I)})
            if name not in models: models.append(name)
    cards = [k for k, s in S.items() if re.match("End card", s.get("label") or "", re.I)]
    def pick(sp, pref):
        rs = rooms.get(sp, [])
        if pref == "original" or not rs: return None
        mine = [r for r in rs if r["model"] == pref]
        r = next((x for x in mine if x["notes"]), None) or (mine[0] if mine else None) or next((x for x in rs if x["notes"]), None) or rs[0]
        return r["seg"]
    lines = []
    for pref in models + ["original"]:
        line = []
        for o in origs:
            line.append(o); sp = S[o].get("end")
            if sp is None: continue
            r = pick(sp, pref)
            if r: line.append(r)
        r45 = pick(spots[-1], pref) if spots else None
        card = next((c for c in cards if r45 and S[c]["video"] == S[r45]["video"]), cards[0] if cards else None)
        if card and S[line[-1]].get("end") is None: line.append(card)
        lines.append({"kind": "plain", "pref": pref, "nodes": ["plain"], "segs": line})
    return lines, {"spots": spots, "rooms": rooms, "models": models}


def seg_len(W, k, durations):
    s = W["segs"][k]; st = s.get("start") or 0
    if s.get("end") is not None: return s["end"] - st
    d = durations.get(s["video"])
    return (d - st) if d else None


def route_stats(W, r, durations):
    lens = [seg_len(W, k, durations) for k in r["segs"]]
    runtime = sum(x for x in lens if x)
    switches = len(r["segs"]) - 1
    heard, rep, rep_sec = {}, 0, 0.0   # media heard twice: an overlap with a range of the same video already played
    for k, ln in zip(r["segs"], lens):
        g = W["segs"][k]; a = g.get("start") or 0; b = a + (ln or 0)
        prev = heard.setdefault(g["video"], [])
        ov = sum(max(0, min(b, y) - max(a, x)) for x, y in prev)
        if ov > 1: rep += 1; rep_sec += ov
        prev.append((a, b))
    return {"runtime": round(runtime, 1), "unknown_len": sum(1 for x in lens if x is None), "switches": switches,
            "repeats": rep, "repeat_sec": round(rep_sec, 1)}
