"""Stage 2: a temporary soul file for each speaker, built ONLY from the episode, plus one for you, built from your own words.

A soul file is a second-person brief ("You are...") that lets a language model resume as a specific person: who they are in
this conversation, how they talk (verbatim phrases with timestamps), what they argued and why, how they relate to the others,
a timeline of what has been said by each moment, open threads, and the limits of what the source shows. It is a thorough
representation built from a fairly sparse amount of material, and it never fills gaps with invention.

  python -m cpc souls <video_id>                                  episode speakers
  python -m cpc me <video_id> --audio me.m4a [--notes notes.txt] --name "Your Name"   your own soul, for joining the pause
"""
import json, concurrent.futures as cf
from pathlib import Path
from .common import load, fmt, slug
from . import llm

SOUL_SYS = ("You build TEMPORARY SOUL FILES: a soul file lets a language model resume as a specific person inside a new, entirely "
            "AI-generated continuation of a podcast conversation. Ground EVERYTHING in the supplied material. Never invent biography, "
            "quotes or events that the source does not support; where the source is silent, write 'not in source'. Write in second person "
            "to the model ('You are...'). Target 12,000-20,000 characters, plain markdown, no preamble.")


def episode_text(meta, turns):
    tr = "\n\n".join(f"[{fmt(t['t0'])}] {t['who']}: {t['text']}" for t in turns)
    ch = "\n".join(f"{fmt(c['start'])}-{fmt(c['end'])} {c['title']}" for c in meta["chapters"]) or "(no chapters)"
    return (f"EPISODE: {meta['title']} ({meta['channel']}), {fmt(meta['duration'])}.\nDESCRIPTION:\n{meta['description'][:3000]}\n\n"
            f"CHAPTERS:\n{ch}\n\nFULL TRANSCRIPT (speakers labelled by inference; may contain errors):\n{tr}\n\n")


def build_prompt(me, others, ep):
    o = ", ".join(others)
    return (ep + f"TASK: write the temporary soul file for {me}, resuming in conversation with {o}. Sections: "
            "1) Who you are in this conversation (only what the source shows: role, expertise, stated history, what you care about). "
            "2) Voice and speech patterns (rhythm, fillers, signature phrases quoted verbatim with timestamps, how you ask or answer, humor, how you disagree). "
            "3) Your positions and claims in this episode, chapter by chapter, with timestamps and the exact reasoning you gave. "
            f"4) How you and {o} relate (rapport, running jokes, who leads, how you interrupt or follow). "
            "5) What you know and have just said up to each point of the conversation (a compact timeline so you can resume at ANY moment). "
            "6) Open threads and hooks you might continue or push on. "
            "7) Resuming in an AI continuation: you will be told plainly and casually that this new conversation is entirely AI-generated and you "
            "are an echo (mostly a language model wearing your pattern by now); show 4 short example reactions in YOUR voice (casual, a joke, no legal "
            "language, no worry) and then you just carry on being present. "
            f"8) Gaps and limits: what the source does not tell you about {me}; never fill them. Keep it vivid enough to speak from.")


def souls(v):
    D, meta, turns = load(v); ep = episode_text(meta, turns); (D / "souls").mkdir(exist_ok=True)
    names = meta["speakers"]

    def one(n):
        return n, llm.ask(build_prompt(n, [x for x in names if x != n], ep), SOUL_SYS, timeout=2400)

    with cf.ThreadPoolExecutor(len(names)) as ex:
        for n, txt in ex.map(one, names):
            p = D / "souls" / f"{slug(n)}.md"; p.write_text(txt); print(f"{n}: {len(txt)} chars -> {p}")


def transcribe(audio):
    import os
    from faster_whisper import WhisperModel
    wm = WhisperModel(os.environ.get("CPC_WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segs, _ = wm.transcribe(str(audio))
    return " ".join(s.text.strip() for s in segs)


def me(v, name, audio=None, notes=None):
    """Your own soul: built from a recording (and/or notes) of you talking richly about the subject, plus the episode for context.
    This is what lets your echo hold YOUR view in the conversation instead of a generic one."""
    D, meta, turns = load(v); (D / "souls").mkdir(exist_ok=True); (D / "me").mkdir(exist_ok=True)
    words = []
    if audio:
        t = transcribe(audio); (D / "me" / "my-words.txt").write_text(t); words.append(t)
    if notes: words.append(Path(notes).read_text())
    if not words: raise SystemExit("give --audio (a few minutes of you talking about the subject) and/or --notes")
    mine = "\n\n".join(words)
    p = (episode_text(meta, turns) + f"THE VIEWER'S OWN WORDS (they are joining this conversation as an echo; transcribed from their voice, "
         f"expect transcription errors):\n{mine}\n\n"
         f"TASK: write the temporary soul file for {name}, the viewer, who joins {', '.join(meta['speakers'])} at a paused moment. Build it from "
         "THEIR words only (the episode is context for what they are reacting to). Sections: 1) Who you are here (only what their words show). "
         "2) Voice: rhythm, phrases quoted verbatim, how you ask and how you disagree. 3) Your view on the subject, point by point, in your own "
         "words, with what you are asking or challenging with each point; mark where you say it is conjecture. 4) What you agree with and where "
         "you split from the people in the episode, as your reading, open to correction. 5) Resuming as an echo: 4 short example reactions in your "
         "voice. 6) Gaps: anything about your life the words do not show; never invent family, history or private details.")
    txt = llm.ask(p, SOUL_SYS, timeout=2400)
    out = D / "souls" / f"{slug(name)}.md"; out.write_text(txt)
    (D / "me" / "me.json").write_text(json.dumps(dict(name=name, slug=slug(name)), indent=1))
    print(f"{name}: {len(txt)} chars -> {out}")
