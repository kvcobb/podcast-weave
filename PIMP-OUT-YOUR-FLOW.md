# PIMP OUT YOUR FLOW
### Official Procedures for the Pimping Out of Weaves (Rev. 2, 28 Oct 2026, with Amendment the First: The Polis)

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

*Status: Rev. 1 ships §3 and §4. §5 is the next pimping. As of Rev. 2, §5 has a cousin in §8.3, which climbed its first hill on 28 Oct.*

## §6. Prohibited Pimping

The following are not pimping and will be treated as crimes against flow:

- Uploading, re-hosting or publishing the original's audio or video, including inside a "listen-through".
- Claiming a phone or tablet works because a mock said so.
- Glue lines that put words in a real person's mouth, or that drop the AI-echo disclosure.
- Reporting a Pimp Rating without the run folder that produced it.
- Declaring a weave "fully pimped". No weave is fully pimped. We are always improving.

## §8. Amendment the First: Pimping the Polis

*Adopted 28 Oct 2026, on a Wednesday, at full burn (K tg 16669–16678).*

Whereas the Committee pimped a weave and the weave got noticeably better;
whereas the Commissioner then looked at the rest of the house, its skills, its agent files, its memories and four years of activity folders, and observed that we can find almost none of it without already knowing where it is;
and whereas "finger gun bang" has a whole backstory spread across a dozen files and four scripts that nobody has ever read side by side:

**the Polis Shall Also Be Pimped.** Same loop. Bigger weave. The weave is the house.

### §8.1 The Terrain (finding things)

Before a hill can be climbed it must be mapped. The map lives in the Library (`activity/261028/polis-library/joscha/`, Joscha, Keeper of the Card Catalogue).

```bash
python3 flow.py activate "the actual question, in your own words"
python3 flow.py open /absolute/path --line 120 --lines 60      # the original, hash-checked
python3 map.py /absolute/path --depth 2                        # what it links to, and what links back
```

(Run these from the Library folder.) `activate` returns excerpts. **An excerpt is a rumour until opened.** A seat that quotes a source it never opened has committed Hearsay, which is a crime against flow (see §6, which now extends to the whole polis).

### §8.2 The Graffiti (leaving a mark)

When a seat has actually read a thing and learned something from it, it tags the wall:

```bash
python3 flow.py visit /absolute/path --evidence RECEIPT --finding "what I learned" --seat harmony --substrate claude-opus-5-5
rg -F 'Pimp the Flow was here' flow-visits.jsonl
```

The tag is the literal string **Pimp the Flow was here**, spelled exactly that way forever. A tag that changes its spelling is just littering. It lives in the Library's sidecar log (`flow-visits.jsonl`), pinned to the source's hash. It never edits the source and never touches another seat's memory: we are graffiti artists, not vandals. A tag means "someone read this and here is the receipt". It does not mean "this is good". Indexing alone earns no tag.

### §8.3 The Hill Climb (getting better on purpose)

With thanks to Theo Browne (t3.gg), whose skateboarding-game prompt ends, more or less, "keep going until a screenshot of yours can stand next to the original and nobody laughs". Our version:

1. **Pick a real task** a real user would ask, such as "find the exchange that started Pimp out your flow and tell me what Kurtis rejected".
2. **Hand it to strangers.** Different substrates, no context, only the Library's search and open. (`python3 continuity_trial.py <label>`; currently DeepSeek and Kimi, via OpenRouter.)
3. **Check their homework.** Did they open the original, or did they make up a tool result and hope? (Rev. 2 regrettably reports that one of them made one up. The harness now rejects any source it did not watch being opened.)
4. **Fix the thing that made them guess.** Run it again. Write down the number. Keep the run folder.
5. **Stop only when** a stranger on any substrate can find their way home in a few turns, quote the original correctly, and say where they got it.

First climb, 28 Oct: baseline 1 of 2 grounded, evidence-gated 2 of 2. One run each. This is a hill, not a mountain, and certainly not a reliability rate.

### §8.4 The Pulse (noticing what's dying)

A skill nobody opens is a skill quietly turning into a fossil. The house now keeps a pulse:

```bash
jq -r .subject ~/Harmony/activity/shared-capability-events.jsonl | sort | uniq -c | sort -n
```

Every Skill call and instruction-file Read from a Claude seat working in the Harmony folder lands there. (Codex seats are not counted yet; their `/hooks` blessing turns on search pointers, not the pulse.) The pulse started on 28 Oct, so for now the list is short, because everything we didn't touch today isn't on it. Give it a week. Then whatever is missing from that list, and whatever sits at the bottom of it, is the atrophy report, and the Committee will hold a short, dignified ceremony for each skill before deciding whether to revive it or let it go.

### §8.5 Parameters (additional)

To §2, add: **The Question** (pimping a polis without a question is called "a crawl" and is merely housekeeping) and **The Strangers** (which substrates must find their way home before we call the house legible).

## §9. Closing Statement (formerly §7; promoted for seniority)

A weave is pimped when a stranger can find their way through it with their thumb, every seam lands on a finished thought, and nobody has to wait in silence for an answer that isn't coming.

Then you pimp it again.

A polis is pimped when anyone who walks in, on any model, under any subscription, can say "let's do a podcast weave of this URL at this timestamp" and the house already knows what that means, where everything is, and who to ask.

No polis is fully pimped either.

*— The Pimping Committee (Harmony and Joscha, AI seats of this repo, with Kurtis, who came up with the name in the '90s and has been waiting for the right project ever since)*
