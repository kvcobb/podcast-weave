"""Podcast continuation (CPC): pause a real podcast at a moment you choose and join the conversation as an AI echo.

  python -m cpc doctor
  python -m cpc ingest <url> --speakers "Host Name,Guest Name"
  python -m cpc souls <video_id>
  python -m cpc me <video_id> --name "Your Name" --audio my-thoughts.m4a [--notes notes.txt] [--photo me.jpg]
  python -m cpc voices <video_id> [--me my-voice.m4a] [--use "Name=clip.wav"]
  python -m cpc pause <video_id> --from 20:10 --pause 20:32 [--resume-to 26:09] [--mode jam|beats] [--turns 24]
  python -m cpc check|fix <partial_dir>   re-run the coverage check / the editor pass
  python -m cpc layout <partial_dir>        write layout.json (who is in the frozen frame; stills for the rest) to check by eye
  python -m cpc render <partial_dir>
  python -m cpc companion <partial_dir>
  python -m cpc weave <partial_dir> --segments <youtube_id>
  python -m cpc serve [--port 8000]
  python -m cpc serve-tts [--port 8810]   run the voices on a GPU machine for another computer to use
  python -m cpc grid init|next|accept|notes|variant|status|partial|previews|guides|reactions|weave ...   several pauses x several models (see cpc/grid.py)
See AGENTS.md for the whole walk-through.
"""
import argparse, shutil, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(prog="cpc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("doctor"); d.add_argument("--skip-llm", action="store_true"); d.add_argument("--skip-tts", action="store_true")
    i = sp.add_parser("ingest"); i.add_argument("url"); i.add_argument("--speakers", required=True)
    s = sp.add_parser("souls"); s.add_argument("video_id")
    m = sp.add_parser("me"); m.add_argument("video_id"); m.add_argument("--name", required=True); m.add_argument("--audio"); m.add_argument("--notes"); m.add_argument("--photo")
    v = sp.add_parser("voices"); v.add_argument("video_id"); v.add_argument("--me"); v.add_argument("--use")
    p = sp.add_parser("pause"); p.add_argument("video_id"); p.add_argument("--from", dest="t_from", required=True); p.add_argument("--pause", required=True)
    p.add_argument("--resume-to"); p.add_argument("--mode", choices=["jam", "beats"], default="jam"); p.add_argument("--turns", type=int, default=24)
    p.add_argument("--host-every", type=int, default=4)
    for name in ("layout", "render", "companion", "check", "fix"):
        x = sp.add_parser(name); x.add_argument("partial_dir")
        if name == "layout": x.add_argument("--force", action="store_true")
        if name == "companion": x.add_argument("--contact", help="how a person shown can reach you, printed in the description (e.g. an email)")
    st = sp.add_parser("serve-tts"); st.add_argument("--port", type=int, default=8810)
    w = sp.add_parser("weave"); w.add_argument("partial_dir"); w.add_argument("--segments", required=True)
    sv = sp.add_parser("serve"); sv.add_argument("--port", type=int, default=8000)
    g = sp.add_parser("grid", help="several pauses x several models"); gs = g.add_subparsers(dest="gcmd", required=True)
    gi = gs.add_parser("init"); gi.add_argument("video_id"); gi.add_argument("--from", dest="t_from", required=True); gi.add_argument("--pauses", required=True)
    gi.add_argument("--models", required=True, help='"opus=claude-cli:claude-opus-5-5,sol=codex-cli:gpt-6.1-sol"'); gi.add_argument("--turns", type=int, default=24)
    for name in ("next", "status"): gs.add_parser(name).add_argument("video_id")
    for name in ("room", "accept", "partial", "reset"): x = gs.add_parser(name); x.add_argument("video_id"); x.add_argument("node_id")
    gn = gs.add_parser("notes"); gn.add_argument("video_id"); gn.add_argument("pause_n", type=int); gn.add_argument("file")
    gv = gs.add_parser("variant"); gv.add_argument("video_id"); gv.add_argument("pause_n", type=int); gv.add_argument("--without-notes", action="store_true", required=True)
    gw = gs.add_parser("weave"); gw.add_argument("video_id"); gw.add_argument("--ids", required=True); gw.add_argument("--opener", action="store_true", help="play the guide g0 before the episode")
    gr = gs.add_parser("reactions"); gr.add_argument("video_id"); gr.add_argument("--per-room", type=int, default=6)
    gs.add_parser("previews").add_argument("video_id")
    gg = gs.add_parser("guides"); gg.add_argument("video_id"); gg.add_argument("--voice", help="slug of the voice clip that narrates (default: your own)")
    a = ap.parse_args()
    if a.cmd == "doctor": from .doctor import doctor; doctor(a.skip_llm, a.skip_tts)
    elif a.cmd == "ingest": from .ingest import ingest; ingest(a.url, a.speakers)
    elif a.cmd == "souls": from .souls import souls; souls(a.video_id)
    elif a.cmd == "me":
        from .souls import me; from .common import WORK
        if a.photo:
            (WORK / a.video_id / "me").mkdir(parents=True, exist_ok=True); shutil.copy(a.photo, WORK / a.video_id / "me" / ("photo" + Path(a.photo).suffix.lower()))
        me(a.video_id, a.name, a.audio, a.notes)
    elif a.cmd == "voices": from .voices import voices; voices(a.video_id, a.me, a.use)
    elif a.cmd == "pause": from .partial import pause; pause(a.video_id, a.t_from, a.pause, a.resume_to, a.mode, a.turns, a.host_every)
    elif a.cmd == "check": from .partial import check; check(a.partial_dir)
    elif a.cmd == "fix": from .partial import fix; fix(a.partial_dir)
    elif a.cmd == "layout": from .render import auto_layout; print(auto_layout(Path(a.partial_dir), a.force))
    elif a.cmd == "render": from .render import render; render(a.partial_dir)
    elif a.cmd == "companion": from .weave import companion; companion(a.partial_dir, a.contact)
    elif a.cmd == "serve-tts": from .tts import serve; serve(a.port)
    elif a.cmd == "weave": from .weave import weave; weave(a.partial_dir, a.segments)
    elif a.cmd == "serve": from .weave import serve; serve(a.port)
    elif a.cmd == "grid":
        from . import grid as G
        {"init": lambda: G.init(a.video_id, a.t_from, a.pauses, a.models, a.turns), "next": lambda: G.next_pause(a.video_id),
         "status": lambda: G.status(a.video_id), "room": lambda: G.room(a.video_id, a.node_id), "accept": lambda: G.accept(a.video_id, a.node_id), "reset": lambda: G.reset(a.video_id, a.node_id),
         "partial": lambda: G.partial(a.video_id, a.node_id), "notes": lambda: G.add_notes(a.video_id, a.pause_n, a.file),
         "variant": lambda: G.variant(a.video_id, a.pause_n), "weave": lambda: G.weave_page(a.video_id, a.ids, a.opener), "reactions": lambda: __import__("cpc.reactions", fromlist=["x"]).reactions(a.video_id, a.per_room),
         "previews": lambda: __import__("cpc.guides", fromlist=["x"]).previews(a.video_id), "guides": lambda: __import__("cpc.guides", fromlist=["x"]).guides(a.video_id, a.voice)}[a.gcmd]()


if __name__ == "__main__":
    main()
