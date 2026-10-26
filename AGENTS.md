# AGENTS.md: make a paused-podcast continuation

You are an AI agent (Claude Code, Codex, Grok, Gemini, or similar) helping a person make a **partial continuation**: a real
YouTube podcast plays from the creator's own upload, pauses at a moment the person chooses, the person joins the conversation as
an AI echo of themselves, the host and guest echoes talk it through with them, and then the original resumes. Read
[ETHICS.md](ETHICS.md) first and follow it. The disclosures are not optional. If the person wants the overview first, share the six-minute explainer: https://www.youtube.com/watch?v=s9nQwigcbkI

Work through the steps below in order. Keep the person informed in plain language, ask them only for the things listed under
"What to ask for", and check each result before moving on. Commands run from the repository root. Outputs go to `./work/`
unless `CPC_WORK` is set.

## 0. What to ask for

1. **The episode**: a YouTube URL, and the names of the people speaking (host first, as they appear in the episode).
2. **The moment**: roughly where the question they want to respond to starts (`--from`) and where they want to step in
   (`--pause`). Rough times are fine: the pipeline snaps them to real pauses in speech. Suggest using the creator's chapter
   markers (`ingest` prints them) to find a clean start.
3. **Their view, in their own voice**: a recording of a few minutes of them talking freely and richly about the subject (a phone
   voice memo is fine). This builds their soul file the same way the episode builds the guests', so their echo holds *their*
   opinion instead of a generic one. Written notes work too, but a recording carries their voice and phrasing best.
4. **A clean voice clip**: 15 to 30 seconds of them talking clearly, with no music and nobody else, to clone their voice. (It can
   come from the same recording.)
5. **A photo** for their tile (a clear, front-facing head and shoulders shot).
6. **Mode**: `jam` (default: a natural back-and-forth where their points come up one at a time) or `beats` (their view as 2 to 4
   set turns, each answered).

## 1. Set up and check the machine

```bash
pip install -r requirements.txt          # plus ffmpeg as a system package
python -m cpc doctor
```

`doctor` checks the tools, makes one tiny call to the language model, and if OmniVoice is installed locally, does a **real test
synthesis** and reports the speed. (A remote server or ElevenLabs gets its first real test on the first `render`.) Report its findings to the person and pick:

**Language model** (`CPC_LLM`, `CPC_MODEL`), in order of preference: whatever they already use. `claude-cli` (Claude Code,
their Claude subscription; default model `claude-opus-5-5`), `anthropic` (ANTHROPIC_API_KEY), `openai` (OPENAI_API_KEY),
`xai` (XAI_API_KEY, Grok), `gemini` (GEMINI_API_KEY), or `codex-cli` (Codex, their ChatGPT plan). For other than Claude, set
`CPC_MODEL` to their strongest model. The pipeline makes on the order of 100 to 150 calls per pause. A few of them produce
long outputs (soul files of 12,000 to 20,000 characters).

**Voices** (`CPC_TTS`):
- `omnivoice`: local, free, high quality. It needs PyTorch and works best on an NVIDIA GPU, Apple Silicon or an Intel GPU.
  Install with `pip install torch omnivoice` (follow PyTorch's site for the right build). Re-run `doctor` to test it for real.
  If it reports much slower than real time, a 10-minute pause will take a long while, so offer the options below. Licence:
  the code is Apache-2.0 and the **weights are CC-BY-NC-4.0 (non-commercial)**. Tell the person.
- `omnivoice-server`: OmniVoice on another machine they control (a home GPU box or a rented cloud GPU). On that machine:
  `pip install torch omnivoice` and `python -m cpc serve-tts --port 8810`; here: `CPC_TTS=omnivoice-server` and
  `CPC_OMNIVOICE_URL=http://that-machine:8810/v1/audio/speech`. The reference clips travel inside each request. As of October 2026 there is no hosted pay-per-call OmniVoice API (OpenRouter's speech models don't
  include it; Hugging Face has a demo Space and a Colab notebook, not a production API).
- `elevenlabs`: hosted instant voice cloning, `ELEVENLABS_API_KEY`. Good quality, paid, and their terms require rights to
  each voice.

## 2. Ingest the episode

```bash
python -m cpc ingest "<url>" --speakers "Host Name,Guest Name"
```

This downloads the video and audio, the transcript (YouTube captions, or a local Whisper transcription if there are none), and
the creator's chapters, then labels who said what. Show the person the chapter list and confirm the moment.

## 3. Build the souls

```bash
python -m cpc souls <video_id>
python -m cpc me <video_id> --name "Their Name" --audio their-thoughts.m4a --photo photo.jpg   # --notes notes.txt also works
```

`souls` writes one soul file per episode speaker, built only from the episode (`work/<id>/souls/<name>.md`). `me` builds the
person's own soul from their recording. Skim each soul file. They should sound like the people and say "not in source" where the
episode is silent. Ask the person to read their own soul file and correct anything that isn't them.

## 4. Voices

```bash
python -m cpc voices <video_id>                                   # picks ~18 s of each speaker talking alone
python -m cpc voices <video_id> --me their-voice-clip.m4a
python -m cpc voices <video_id> --use "Host Name=clip.wav"        # if a speaker never talks long enough alone
```

Listen to every clip in `work/<id>/voices/`: one voice, no music, no laughter over it. A bad clip makes a bad clone.

## 5. The pause conversation

```bash
python -m cpc pause <video_id> --from 20:10 --pause 20:32 [--resume-to 26:09] [--mode jam|beats] [--turns 24]
```

This prints the snapped times and writes `work/<id>/partials/<start>-<pause>-<mode>/` with the transcript and a coverage check.
**Read the transcript before rendering.** Check:
- each of the person's points came up (`check.json`; missing points are listed),
- nobody puts views in another speaker's mouth (`misattributions`), and nobody invents personal anecdotes (`anecdotes`),
- the host gets turns (they ask clarifying questions), and the guests sound like themselves and push back where they would,
- it ends on the host's hand-back line.
If something is off, either re-run `pause`, or make a small edit to `transcript.jsonl` (keep each line valid JSON, and note
what you changed). Length: about 150 words a minute when spoken; 24 turns is roughly 8 to 10 minutes.

## 6. Render

```bash
python -m cpc layout <partial_dir>     # then LOOK at freeze.png and the stills, and fix layout.json
python -m cpc render <partial_dir>
```

`layout.json` says who is visible inside the frozen frame (`in_frame`: a box per person, in 1280x720 coordinates, so the speaker
ring lands on them) and which image to use as a tile for everyone else (`tiles`: image path plus an optional crop box). By
default nobody is marked in-frame and each speaker gets a still from their own longest turn. **Open `freeze.png` and each still
and check them.** If the frozen frame shows two people side by side, mark both as `in_frame` and remove their tiles. Pick
flattering, front-facing stills. Then render. Review frames from `pause.mp4` (the start, a few speaker changes, the end) before
moving on.

**The look (Kurtis, Oct 2026; the defaults in `cpc/render.py`, keep them):** 1440p at 30 fps. No panel or box around any
portrait tile (a frame baked into a portrait image is trimmed automatically); the label sits plainly under the tile. A soft
feathered spotlight on whoever is speaking, everyone else dimmed, and the spotlight *glides* between speakers (0.25 s with an
ease, like a hand-held light), never jumps. Close-up freezes: mark the one visible person `in_frame` and give everyone else a tile.

## 7. Companion video and weave page

```bash
python -m cpc companion <partial_dir>
```

The person uploads `companion.mp4` to their YouTube channel as **unlisted**, with the **altered or synthetic content** label on,
using `youtube-description.txt` as the description (pass `--contact you@example.com` to `companion` so a person shown, or their
family, can reach them). Leave **embedding allowed** and set it **not made for kids**, or the weave player can't play it. New or
unverified YouTube accounts can't upload videos longer than 15 minutes until they verify. The video id is the 11 characters
after `youtu.be/` or `v=` in its link. **No YouTube account?** The weave page needs the companion on YouTube; without it, share
`pause.mp4` or `companion.mp4` directly (with its disclosures) and tell viewers the timestamp in the original where it fits. (You can do the upload for them only if they have set up YouTube API access
and asked you to.) Then:

```bash
python -m cpc weave <partial_dir> --segments <companion_video_id>
python -m cpc serve                    # http://localhost:8000/<original_id>/
```

Watch it through once: the original plays from the start time, switches to the pause, returns to the original at the same
second, and ends on the end card. YouTube may play an ad on the original first, which belongs to the creator.

## Settings you may want

| Variable | What it does |
|---|---|
| `CPC_LLM`, `CPC_MODEL` | language model backend and model (name the model so the on-screen label names the substrate) |
| `CPC_TTS`, `CPC_OMNIVOICE_URL`, `ELEVENLABS_API_KEY`, `CPC_ELEVEN_MODEL` | voice backend |
| `CPC_NUM_STEP` | OmniVoice quality/speed (default 48) |
| `CPC_WHISPER_MODEL`, `CPC_WHISPER_DEVICE` | local transcription when an episode has no captions (default `small`, GPU if present) |
| `CPC_WORK` | where work folders go (default `./work`) |

`pause --host-every N` gives the host the floor after N turns of silence (default 4). Python 3.10 or newer. Re-running `pause`
starts that room clean (the previous files are kept with a `.prev` suffix); editing a line in `transcript.jsonl` and re-running
`render` re-voices only the lines you changed; `layout` won't overwrite a `layout.json` you edited unless you pass `--force`.

## 8. Share it (optional)

The weave is a static site, so any static host works:
- **GitHub Pages**: fork this repo, push, and enable Pages (Settings, Pages, deploy from branch). Free with a GitHub account.
  The fork includes the example weaves; delete the example folders and `weaves/*.json` you don't want to republish, and add a
  card for your own weave to `index.html`.
  The address is `https://<user>.github.io/podcast-weave/<original_id>/`.
- **Netlify** or **Cloudflare Pages**: connect the repo, or drag and drop the folder. Both have free tiers.
- Or keep it on localhost and just show people.

When sharing, keep the disclosures. If anyone echoed asks for it to come down, take it down (ETHICS.md).

## Several pauses, several models (a woven grid)

A weave can pause one episode at several moments and run each pause on more than one model. What we learned doing it
(Sam Altman on Matthew Berman, Oct 2026; Harmony and Joscha):

- **Go in time order, in pairs.** At each pause, run one room per model at the same time, review both, and only then build the
  next pause. Each new room reads every finished earlier pause (from both models) plus the original up to its own moment, and
  never anything later. Launching every pause at once leaves out the history in between.
- **Label the strands; never merge them.** Earlier pauses go in as sibling versions of the same moment, each labelled with its
  model. Where they disagree, both happened.
- **Your own notes stay yours.** Anything the person said privately about where they'd like the talk to go goes only into their
  own echo's system prompt (`floor.run(..., private={slug: text})`), never to the floor or the other speakers. It is a feel, not
  a checklist.
- **Observers write separately.** After each pair, each reviewer reads both versions side by side and writes their own read,
  then answers the other's. Both go into the next pause as attributed, contestable notes, not instructions, with any factual
  corrections (for example, a hypothetical that a later room treated as something that really happened).
- **Never find-and-replace model names.** Change only the exact phrases that tell an echo which model it is on now; keep
  history and old transcripts word for word. A global swap once rewrote "Claude 3.0 Opus" into nonsense inside a soul.
- **Soul files built from the whole episode leak later material.** The timestamp limits what a room is shown, not what its
  souls know. Say so when you compare.
- **Playback is not ancestry.** 4 pauses x 2 models is 8 generated rooms and 16 ways to watch; a page that plays "Sol only"
  must still say what each pause actually read.
- **Render as you go.** Each reviewed room can render and upload (unlisted) right away; the next pause waits for text review,
  not for video.
- **Keep receipts.** Inputs, model asked for (and returned, if the tool reports it), parent transcript hashes, and the raw and
  any edited result kept separately.

### Running a grid

```bash
python -m cpc grid init <video_id> --from 20:10 --pauses 20:32,30:02 \
    --models "opus=claude-cli:claude-opus-5-5,sol=codex-cli:gpt-6.1-sol" [--turns 24]
python -m cpc grid next <video_id>             # runs pause 1: one room per model, side by side
# read both transcripts (work/<id>/grid/p1-opus/transcript.jsonl, .../p1-sol/...), then:
python -m cpc grid accept <video_id> p1-opus
python -m cpc grid accept <video_id> p1-sol
python -m cpc grid notes <video_id> 1 our-notes.md   # optional: reviewers' notes, read by every later room
python -m cpc grid next <video_id>             # pause 2 reads the original to its moment + every accepted earlier room
python -m cpc grid variant <video_id> 2 --without-notes   # optional: the same rooms with the notes left out
python -m cpc grid status <video_id>
python -m cpc grid partial <video_id> p2-sol   # a partial folder; then `layout`, `render`, `companion` as for one pause
python -m cpc grid previews <video_id>         # a preview still per rendered room, with one line said in it (checked verbatim)
python -m cpc grid guides <video_id> [--voice <slug>]   # spoken menus (an opener, then one after each pause), in your echo's voice
python -m cpc grid reactions <video_id> [--per-room 6]   # scripted cast comments + avatars that scroll beside each room
python -m cpc grid weave <video_id> --ids "p1-opus=<yt_id>:<seconds>,p1-sol=...,p2-opus=...,p2-sol=...,g1=<id>,g2=<id>" [--opener]
```

Model specs are `name=backend:model` with the backends from Settings. Each room runs in its own process with its own
`CPC_LLM`/`CPC_MODEL`. Each room writes `receipt.json`: the model asked for, the model that answered when the tool reports it
(the `claude` and `codex` commands do not, so it says `null`), the sha256 of its seed, every parent transcript and every notes
file, and whether it ran without notes. `me/private.md` (optional) is the person's own notes, read only by their echo. `--ids`
takes the companion upload for each room as `id:length-in-seconds` (the length of `pause.mp4`, before the end card), plus
optional `iv1`, `iv2`, ... for short interval videos played after each pause, and the guides `g0` (before the episode), `g1`,
`g2`, ... (after each pause; upload each `grid/guides/<g>/guide.mp4` unlisted with the AI label; their lengths and cues are
read from `timing.json`). The page offers, after each pause, the no-notes room when there is one and another model's
version (up to two such cards; each other-model room then offers the next model, so with three or more models every room
stays reachable), or the next pause on any model, and never offers the same room twice on one path. Guides and cards come
from the same plan (`grid.extras`): a guide names a kind of choice only when every model's page shows that card, so re-run
`grid guides` after adding or removing rooms. While a guide plays, its choice cards light as each is named; cards show the room's preview still and a strip of which model plays at that pause. Guides are
transcribed after voicing and retaken if words drop; listen to them anyway before uploading. The opener guide `g0` plays
before the episode only with `--opener` (viewers found a routes explainer up front too much; start with the episode).

The page's top bar has a live countdown far left to the end of the current step: whole seconds, then tenths under 30 s and
hundredths under 10 s, read from the playing video's own time (it stops when the video stops and follows seeks). Beside it
is the current segment's name, and in the last 6 s a line saying what comes next: the next pause, the original resuming,
your choice, or the next clip. It reads all of this from the weave file, so it needs nothing per episode.

`grid reactions` writes `reactions/<id>-choose.json` and `avatars/<id>/<slug>.png` in the current folder, and `grid weave`
links them when the file exists. Each rendered room gets a few short comments from the cast's echoes, written by the model
from the room's exact per-turn timeline (`timeline.json`, written by `render`; older renders are re-timed from `pf.txt`
and `pa.txt`). Each comment is anchored to the turn it follows and kept only if any quote in it is word for word; your echo
celebrates moments when someone notices they are an AI, guests' echoes joke that they are AI when they take a strong stand,
the host's echo says why a moment matters. The page labels every comment with who it is from and "echo · AI", fires them
as playback passes, never replays a backlog after a seek, and has a Comments on/off button. Avatars are a cel-shade filter
over each person's picture in the render, so they look like the person; put your own art at `avatars/<id>/<slug>.png` to
use that instead. The file format is plain (`cast` with name, tag, color, avatar; `tracks` keyed by the video key in the
weave, each `{t, who, text}` with `t` in seconds of that video), so you can write or edit reactions by hand, add your own
seats to `cast`, and read the drafts before publishing: they are generated, so read them.
