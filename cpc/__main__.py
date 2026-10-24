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
    w = sp.add_parser("weave"); w.add_argument("partial_dir"); w.add_argument("--segments", required=True)
    sv = sp.add_parser("serve"); sv.add_argument("--port", type=int, default=8000)
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
    elif a.cmd == "layout": from .render import auto_layout; print(auto_layout(Path(a.partial_dir)))
    elif a.cmd == "render": from .render import render; render(a.partial_dir)
    elif a.cmd == "companion": from .weave import companion; companion(a.partial_dir)
    elif a.cmd == "weave": from .weave import weave; weave(a.partial_dir, a.segments)
    elif a.cmd == "serve": from .weave import serve; serve(a.port)


if __name__ == "__main__":
    main()
