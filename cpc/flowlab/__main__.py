"""python3 -m cpc.flowlab <weave.json> --sources sources.json --out RUN_DIR [--listen plain:Opus,plain:Sol] [--seat agent.md]

Walks every route through a weave, cuts every distinct switch into a short clip, transcribes it (cached), measures
silence, has a language model judge whether the switch lands, optionally has one seat read the weakest five, stitches
listen-through audio for chosen routes, and writes REPORT.md + flow.json. Re-runs reuse cached cuts, transcripts and
judgements, so iterating on a weave costs only what changed. Audio stays local; never upload a listen file.
"""
import argparse, json, re, sys, time
from pathlib import Path
from . import walk, seams as SEAMS, judge as JUDGE, report
from .media import Media, concat
from .. import llm


def main():
    ap = argparse.ArgumentParser(prog="cpc.flowlab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weave"); ap.add_argument("--sources", required=True, help='{"files": {video_key_or_youtube_id: path}, "fetch": [own ids yt-dlp may fetch]}')
    ap.add_argument("--out", required=True); ap.add_argument("--cache", default=str(Path.home() / ".cache" / "cpc-flowlab"))
    ap.add_argument("--pad", type=float, default=10.0); ap.add_argument("--listen", default="plain:*", help="routes to stitch, e.g. plain:Opus,plain:Sol or plain:*")
    ap.add_argument("--seat", help="agent/soul file for a qualitative pass over the weakest seams"); ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    W = json.loads(Path(a.weave).read_text()); run = Path(a.out); run.mkdir(parents=True, exist_ok=True)
    media = Media(W, a.sources, a.cache)
    log = lambda *x: print(time.strftime("%H:%M:%S"), *x, flush=True)

    paths = walk.graph_routes(W); plains, info = walk.plain_lines(W); routes = plains + paths
    vids = {W["segs"][k]["video"] for r in routes for k in r["segs"]}
    missing = [v for v in sorted(vids) if media.path(v) is None]
    if missing: sys.exit("no local media for: " + ", ".join(missing) + " (add them to --sources)")
    dur = {v: media.duration(v) for v in vids}
    short = [f"{k} wants {W['segs'][k]['end']:.1f} s of {W['segs'][k]['video']}, file has {dur[W['segs'][k]['video']]:.1f} s"
             for k in W["segs"] if W["segs"][k]["video"] in dur and W["segs"][k].get("end") is not None and dur[W["segs"][k]["video"]]
             and dur[W["segs"][k]["video"]] < W["segs"][k]["end"] - 0.5]
    if short: sys.exit("a source file is shorter than the weave expects (wrong file?):\n  " + "\n  ".join(short))
    for r in routes: r["stats"] = walk.route_stats(W, r, dur)
    log(f"walk: {len(plains)} plain lines, {len(paths)} paths, models {info['models']}")

    trans = SEAMS.transitions(W, routes); log(f"seams: {len(trans)} distinct switches")
    sm = SEAMS.run(W, media, trans, a.pad, run, a.cache); log("seams cut + transcribed")
    meta = {"weave": Path(a.weave).stem, "pad": a.pad, "judge": None}
    if not a.no_judge:
        sm = JUDGE.run(W, sm, a.cache, a.workers); meta["judge"] = {"rubric": JUDGE.RUBRIC_V, "model": llm.describe()}
        log("seams judged")
    routes = report.score_routes(routes, sm)

    listens = []
    want = [x.strip() for x in a.listen.split(",") if x.strip()]
    for r in routes:
        if r["kind"] != "plain" or not any(w in ("plain:*", "plain:" + r["pref"]) for w in want): continue
        parts = []
        for k in r["segs"]:
            g = W["segs"][k]; t0, t1 = SEAMS.bounds(W, media, k); parts.append(media.cut(g["video"], t0, t1))
        f = concat(parts, run / "listen" / f"plain-{r['pref']}.mp3", bitrate="48k", gap=0.8)
        listens.append({"name": report.name(r), "file": str(f), "runtime": r["stats"]["runtime"]}); log("listen:", f)

    seat_text = None
    if a.seat and not a.no_judge:
        body = Path(a.seat).read_text(); body = re.sub(r"^---.*?---\s*", "", body, flags=re.S)
        weak = sorted([s for s in sm if s.get("score") is not None], key=lambda s: (s["score"], -s["uses"]))[:5]
        p = ("You are reading the five weakest switches in a podcast weave (a real podcast that pauses while AI echoes "
             "continue the conversation, then resumes). For each: what drags, what lands, and one concrete fix in a sentence. "
             "Then two sentences on the whole flow. Plain prose, under 350 words.\n\n" +
             "\n\n".join(f"{i}. {s['a']} -> {s['b']}\nA ({W['segs'][s['a']].get('label')}) ends: ...{s['a_words'][-300:]}\n"
                         f"B ({W['segs'][s['b']].get('label')}) begins: {s['b_words'][:300]}...\nJudge said: {s['judge'].get('land')}"
                         for i, s in enumerate(weak, 1)))
        seat_text = f"*{Path(a.seat).stem} (an AI echo, not the real person):*\n\n" + llm.ask(p, system=body, timeout=900)
        log("seat read done")

    rep = report.write(run, W, routes, sm, listens, seat_text, meta); log("report:", rep)


if __name__ == "__main__":
    main()
