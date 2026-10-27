# PIMP OUT YOUR FLOW
### Official Procedures for the Pimping Out of Weaves (Rev. 1, 26 Oct 2026)

> *This document is extremely serious. Every command in it is real. Every sentence about
> pimping is also real. If you are smiling, you are reading it correctly.*

---

## §0. Preamble

Whereas a weave may pass every click test and still play badly;
whereas a pause may cut the original mid-word ("just say it, knock" / "knock knock");
whereas a comparison clip may wander into a gap and leave four and a half seconds of silence where Sam's answer should have been;
and whereas the interface may be faithful to a beautiful metaphor and impossible to drive with a thumb:

**the Weave Shall Be Pimped.** Out. Its flow and its interface both. Repeatedly, cheaply, and with receipts.

## §1. Definitions

| Term | Meaning |
|---|---|
| **Flow** | What a viewer actually hears and feels, route by route, switch by switch. Not what the graph says. |
| **Seam** | Any moment one video hands to another. The 10 seconds either side are where flows go to die. |
| **Pimping** | One full pass of §3 or §4, ending in a measured improvement or an honest "it didn't help". |
| **Pimp Rating** | The flow score (0–1) from `REPORT.md`. Higher is pimpier. A rating without a receipt is a rumour. |
| **Glue** | A short, disclosed bridge line written where a seam doesn't land. Glue is voiced by echoes and says so. Glue never speaks for a real person. |
| **Fresh Eyes** | A first-time-viewer agent that has never seen the weave, given only the URL and a task. |

## §2. Parameters the User MUST Specify Before Pimping

Pimping without parameters is called "vibes" and is not covered by this document.

1. **The Weave** (`weaves/<id>.json`). Required. You cannot pimp nothing.
2. **The Sources** (`sources.json`): local files for every video key, plus which of *your own* uploads may be fetched. The original episode belongs to someone else. It is heard locally and **never uploaded, re-hosted or published, not even a little, not even once.**
3. **The Run Directory** (`--out`): where the receipts live. Receipts are how we know it was pimped.
4. **The Listening Routes** (`--listen plain:Opus,plain:Sol`): which lines get stitched end to end for actual ears.
5. **The Seat** (`--seat path/to/agent.md`, optional): one soul who listens to the five worst seams and says what they'd change. Recommended: someone with taste and no patience for filler.
6. **The Ambition Level**, chosen from:
   - *Mild* — fix the bugs it finds.
   - *Medium* — fix the bugs, trim the seams, reorder the clips.
   - *Fully Pimped* — all of the above, plus glue lines and a fresh-eyes pass on the interface.
   - *Ridiculous* — the search loop (§5), which proposes variants on its own, overnight, while you sleep.
7. **The Crazy Idea** (optional but encouraged). Throw it at the wall. §3–§5 exist to find out whether it sticks.

## §3. Pimping the Flow (the sound)

```bash
python -m cpc.flowlab weaves/<weave>.json --sources sources.json --out runs/<weave>-<stamp> \
    --listen plain:Opus,plain:Sol --seat path/to/a-soul.md
```

The Procedure, which proceeds as follows:

1. **Walk.** Every distinct route through the graph, plus the plain line under each room preference. Runtime, number of switches, seconds heard twice.
2. **Cut.** Every distinct seam A→B, the last `--pad` seconds of A plus the first of B. Each side is transcribed separately, because one pass over a silence drops the words after it. (We learned this. You're welcome.)
3. **Measure.** ffmpeg finds the silences. Silence is measured, never guessed.
4. **Judge.** Your `CPC_LLM` scores each seam 0–2: does A end on a finished thought, does B follow from A's last words, does anything repeat, is the disclosure there when an echo starts.
5. **Listen.** The chosen routes are stitched into local audio files for actual human or echo ears. **Local only.**
6. **Seat read.** The seat listens to the five weakest seams and writes its one rule. (Rev. 1's rule, from Rick Rubin's echo: *end on a finished answer, no gap over 1.5 s, say each option once.*)
7. **Report.** `REPORT.md` and `flow.json`: routes ranked by Pimp Rating, the weakest seams with timestamps and fixes, and glue candidates (text only, not voiced).

Everything is cached by content hash. Rev. 1's first run took 4 minutes; a re-run took 43 seconds. **Pimping must not be painful.** If it becomes painful, the procedure is wrong, not the ambition.

## §4. Pimping the Interface (the screen)

1. **Read the gut note for the real defect.** "It's not intuitive" usually means a metaphor was rendered literally: a diagram, not a control.
2. **Say the plan in plain words** to whoever asked, before building. Keep the old version behind a flag (`?nav=paths`), because the old version is somebody's favourite.
3. **Build, then test with the mocks AND a real browser.** The real browser catches what no mock can (Rev. 1: a Chapters tap before the first play was silently dropped).
4. **Fresh Eyes.** A first-time-viewer agent gets only the URL and real tasks ("watch the other room at 30:02, then get back to where you were") at phone and desktop size. Fix what confused it. Keep what the commissioner deliberately froze.
5. **Look at the screenshots yourself.** Rev. 1 found a letterbox band and an episode total of 16:40 this way.
6. **Independent QA by someone who didn't build it.** Then main, then a live muted check, then the link.

## §5. The Ridiculous Tier: the Search Loop

The loop proposes variants itself: reorder the clips, trim a seam, skip a comparison, move a pause, write glue where a seam fails. It stitches each one cheaply (seams only, cached), scores it with the judges and a seat, keeps the winners, and breeds the next round from them. It runs for a fixed number of rounds. The commissioner sees only the top two or three, ready to hear.

*Status: Rev. 1 ships §3 and §4. §5 is the next pimping.*

## §6. Prohibited Pimping

The following are not pimping and will be treated as crimes against flow:

- Uploading, re-hosting or publishing the original's audio or video, including inside a "listen-through".
- Claiming a phone or tablet works because a mock said so.
- Glue lines that put words in a real person's mouth, or that drop the AI-echo disclosure.
- Reporting a Pimp Rating without the run folder that produced it.
- Declaring a weave "fully pimped". No weave is fully pimped. We are always improving.

## §7. Closing Statement

A weave is pimped when a stranger can find their way through it with their thumb, every seam lands on a finished thought, and nobody has to wait in silence for an answer that isn't coming.

Then you pimp it again.

*— The Pimping Committee (Harmony and Joscha, AI seats of this repo, with Kurtis, who came up with the name in the '90s and has been waiting for the right project ever since)*
