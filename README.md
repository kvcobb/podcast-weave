# PODCAST WEAVE
### Official Notice Concerning the Pausing of Podcasts and the Continuation of Conversations by AI Echoes (Rev. 2, 26 Oct 2026)

> *This document is extremely serious. It describes a way to pause a real podcast, let AI echoes keep
> talking, and hand the episode back to its creator at the exact second you left. All of that is true.*

**Live:** https://kvcobb.github.io/podcast-weave/

---

## §0. What This Is

One YouTube player plays the creator's original upload. At chosen moments it switches to a companion video of AI-generated "pause" segments, then returns to the original at the same second.

**Nothing from the original is copied or re-uploaded. Its views and its ads stay with its creator.** This is the first rule of weaving and it is not a bit.

## §1. Definitions

| Term | Meaning |
|---|---|
| **Weave** | A JSON file describing which video plays when. The whole trick, in one file. |
| **Original** | The creator's own upload, played from their channel. Never ours. |
| **Pause** | An AI-generated segment where echoes of the people in the episode keep the conversation going. |
| **Echo** | An AI that speaks in someone's borrowed voice and says so. An echo is never the real person. |
| **Six Minutes** | The length of the explainer. Every weave page's "What is this?" button plays it: https://www.youtube.com/watch?v=s9nQwigcbkI |

## §2. Making Your Own (the Whole Pipeline)

Give this repository's URL to your AI agent (Claude Code, Codex, or another) and instruct it to follow [AGENTS.md](AGENTS.md). It checks your machine, sets up voices, and walks you through it.

You SHALL bring:

1. a YouTube URL,
2. the moment you want to step in,
3. a few minutes of yourself talking about the subject,
4. a short clean voice clip, and
5. a photo.

The code lives in `cpc/` (`python -m cpc --help`).

**Read [ETHICS.md](ETHICS.md) before you share anything.** This is a shared method, not a product. If you make an echo video, you are responsible for it, and nothing here is legal advice or a guarantee that a video is lawful.

## §3. How a Weave Is Described

`weaves/<originalVideoId>.json`:

```json
{
  "original": { "id": "ORIGINAL_ID", "title": "Episode title", "channel": "Channel", "duration": 3164.16 },
  "segments": { "id": "SEGMENTS_ID", "title": "Pause segments (AI echoes)" },
  "steps": [
    { "video": "segments", "start": 0,     "end": 38.2,  "label": "Intro" },
    { "video": "original", "start": 0,     "end": 932.7, "label": "Original, up to 15:32" },
    { "video": "segments", "start": 38.2,  "end": 635.3, "label": "Pause at 15:32" },
    { "video": "original", "start": 932.7, "end": null,  "label": "Original, to the end" },
    { "video": "segments", "start": 635.3, "end": null,  "label": "Sign-off" }
  ]
}
```

Times are in seconds. `end: null` plays that video to its end. Copy `nnYHg0gcWug/index.html` into a folder named after your original's ID and change `WEAVE_ID`. That is the entire ceremony.

## §4. Making the Segments Video

1. **Pause where a sentence has just ended.** Freeze the original's frame at that second, so the cut in and out reads as a pause and not a crash.
2. **Put a keyframe at the start of every segment**, for example `ffmpeg -force_key_frames "0,38.2,635.3"`, because YouTube starts playback at the nearest keyframe and does not take requests.
3. **Disclose on screen, in every pause,** that the voices are AI echoes and not the real people, and turn on YouTube's altered or synthetic content label.

## §5. Testing That It Actually Plays Well

Clicking is not listening. Before you share a weave, pimp it out: walk every route, listen at every seam, and let a fresh pair of eyes try to use it. The procedure is in [PIMP-OUT-YOUR-FLOW.md](PIMP-OUT-YOUR-FLOW.md). The style these documents are written in is in [HOUSE-STYLE.md](HOUSE-STYLE.md).

## §6. Takedowns

If you are one of the people echoed in a weave and want it removed, open an issue and it comes down.

## §7. Closing Statement

A weave is working when a viewer forgets which parts were the original, remembers which parts were AI because we told them every time, and the creator still gets every view.

No weave is fully pimped.

*— The Weaving Committee (Harmony and Joscha, AI seats of this repo, with Kurtis, who wanted to step into a podcast and ask one more question)*
