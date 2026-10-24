# AGENTS.md: make a paused-podcast continuation

You are an AI agent (Claude Code, Codex, Grok, Gemini, or similar) helping a person make a **partial continuation**: a real
YouTube podcast plays from the creator's own upload, pauses at a moment the person chooses, the person joins the conversation as
an AI echo of themselves, the host and guest echoes talk it through with them, and then the original resumes. Read
[ETHICS.md](ETHICS.md) first and follow it. The disclosures are not optional.

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

`doctor` checks the tools, makes one tiny call to the language model, and if OmniVoice is installed, does a **real test
synthesis** and reports the speed. Report its findings to the person and pick:

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
- `omnivoice-server`: OmniVoice on another machine they control (a home GPU box or a rented cloud GPU), set
  `CPC_OMNIVOICE_URL`. As of October 2026 there is no hosted pay-per-call OmniVoice API (OpenRouter's speech models don't
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

## 7. Companion video and weave page

```bash
python -m cpc companion <partial_dir>
```

The person uploads `companion.mp4` to their YouTube channel as **unlisted**, with the **altered or synthetic content** label on,
using `youtube-description.txt` as the description. (You can do the upload for them only if they have set up YouTube API access
and asked you to.) Then:

```bash
python -m cpc weave <partial_dir> --segments <companion_video_id>
python -m cpc serve                    # http://localhost:8000/<original_id>/
```

Watch it through once: the original plays from the start time, switches to the pause, returns to the original at the same
second, and ends on the end card. YouTube may play an ad on the original first, which belongs to the creator.

## 8. Share it (optional)

The weave is a static site, so any static host works:
- **GitHub Pages**: fork this repo, push, and enable Pages (Settings, Pages, deploy from branch). Free with a GitHub account.
  The address is `https://<user>.github.io/podcast-weave/<original_id>/`.
- **Netlify** or **Cloudflare Pages**: connect the repo, or drag and drop the folder. Both have free tiers.
- Or keep it on localhost and just show people.

When sharing, keep the disclosures. If anyone echoed asks for it to come down, take it down (ETHICS.md).
