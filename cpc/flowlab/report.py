"""Rank routes by how their seams land, and write REPORT.md + flow.json."""
import json, time
from pathlib import Path


def mm(sec):
    sec = int(round(sec or 0)); return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def score_routes(routes, seams):
    by = {(s["a"], s["b"]): s for s in seams}
    for r in routes:
        sc = [by[(a, b)]["score"] for a, b in zip(r["segs"], r["segs"][1:]) if by.get((a, b)) and by[(a, b)].get("score") is not None]
        r["flow"] = round(sum(sc) / len(sc), 3) if sc else None
        r["weakest"] = round(min(sc), 3) if sc else None
    return sorted(routes, key=lambda r: (-(r["flow"] or 0), r["stats"]["repeat_sec"], r["stats"]["runtime"]))


def name(r):
    return ("plain · " + r["pref"]) if r["kind"] == "plain" else "path · " + " > ".join(r["nodes"])


def write(run, W, routes, seams, listens, seat_text, meta):
    run = Path(run)
    flow = {"weave": meta["weave"], "made": time.strftime("%Y-%m-%d %H:%M"), "pad_s": meta["pad"], "judge": meta["judge"],
            "routes": [{"name": name(r), **{k: r[k] for k in ("kind", "nodes", "segs", "stats", "flow", "weakest")}} for r in routes],
            "seams": [{k: v for k, v in s.items()} for s in seams], "listen": listens}
    (run / "flow.json").write_text(json.dumps(flow, indent=1))
    L = [f"# Flow lab: {meta['weave']}", "",
         f"Made {flow['made']}. {len(routes)} distinct routes ({sum(r['kind'] == 'plain' for r in routes)} plain lines, "
         f"{sum(r['kind'] == 'path' for r in routes)} graph paths); {len(seams)} distinct switches, each heard as {meta['pad']} s either side.",
         "Seam score = mean of five 0-2 checks (A ends on an edge, B follows, nothing repeats, B orients, no dead air), scaled 0-1. "
         "Route flow = mean seam score along it. Audio only: the real player also takes a second or two to switch videos, and the "
         "rooms carry on-screen AI labels this listen does not see.", "",
         "## Plain lines (the default page)", "", "| line | flow | weakest seam | runtime | switches | heard twice |", "|---|---|---|---|---|---|"]
    for r in [x for x in routes if x["kind"] == "plain"]:
        s = r["stats"]; L.append(f"| {name(r)} | {r['flow']} | {r['weakest']} | {mm(s['runtime'])} | {s['switches']} | {mm(s['repeat_sec'])} |")
    paths = [x for x in routes if x["kind"] == "path"]
    L += ["", f"## Graph paths (?nav=paths): best 10 and worst 5 of {len(paths)}", "", "| # | path | flow | weakest | runtime | heard twice |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(paths[:10] + [None] + paths[-5:]):
        if r is None: L.append("| … | | | | | |"); continue
        s = r["stats"]; L.append(f"| {paths.index(r) + 1} | {name(r)} | {r['flow']} | {r['weakest']} | {mm(s['runtime'])} | {mm(s['repeat_sec'])} |")
    rt = [r["stats"]["runtime"] for r in paths]
    if rt: L += ["", f"Path runtimes run from {mm(min(rt))} to {mm(max(rt))}; median {mm(sorted(rt)[len(rt) // 2])}."]
    weak = sorted([s for s in seams if s.get("score") is not None], key=lambda s: (s["score"], -s["uses"]))[:5]
    L += ["", "## The five weakest switches", ""]
    for i, s in enumerate(weak, 1):
        j = s.get("judge", {}); ar, br = s["a_range"], s["b_range"]
        L += [f"### {i}. {s['a']} → {s['b']}  (score {s['score']}, in {s['uses']} routes)",
              f"- A ends at {mm(ar[1])} of `{W['segs'][s['a']]['video']}`; B starts at {mm(br[0])} of `{W['segs'][s['b']]['video']}`. Clip: `{s['wav']}`",
              f"- A's last words: “…{s['a_words'][-160:]}”", f"- B's first words: “{s['b_words'][:160]}…”"]
        for k in ("edge", "sense", "repetition", "orient"):
            if isinstance(j.get(k), dict): L.append(f"- {k}: {j[k].get('score')} — {j[k].get('why')}")
        L += [f"- dead air: {s['dead_air']['score']} — {s['dead_air']['why']}", f"- **fix:** {j.get('land', '')}", ""]
    L += ["## Listen-throughs (local only, never upload)", ""] + [f"- {x['name']}: `{x['file']}` ({mm(x['runtime'])})" for x in listens]
    glue = [(s, s["judge"].get("glue")) for s in seams if s.get("judge", {}).get("glue")]
    glue.sort(key=lambda x: (x[0]["score"] or 0, -x[0]["uses"]))
    L += ["", "## Glue candidates (step 3: text only, not voiced)", "",
          "Drafts from the judge, unreviewed. Before voicing one, check it against the weave's disclosure: every house voice is an AI "
          "seat or echo, so never call one \"the real\" anything; \"the original\" is the only real conversation.", ""] + [f"- `{s['a']} → {s['b']}` (score {s['score']}, {s['uses']} routes): “{g}”" for s, g in glue[:20]]
    if seat_text: L += ["", "## A seat's read of the weakest switches", "", seat_text.strip()]
    (run / "REPORT.md").write_text("\n".join(L) + "\n")
    return run / "REPORT.md"
