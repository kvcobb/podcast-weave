# Podcast Weave

Watch a real YouTube podcast episode with AI-generated "pause" segments woven in. One YouTube player plays the creator's original upload, switches to a companion segments video at chosen moments, then returns to the original at the same second. Nothing from the original is copied or re-uploaded; its views and ads stay with its creator.

Live: https://kvcobb.github.io/podcast-weave/

## How a weave is described

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

Times are seconds. `end: null` plays that video to its end. Copy `nnYHg0gcWug/index.html` into a folder named after your original's ID and change `WEAVE_ID`.

## Making the segments video

- Pick pause points where a sentence has just ended; freeze the original's frame at that second so the cut in and out looks like a pause.
- Put a keyframe at the start of every segment (for example `ffmpeg -force_key_frames "0,38.2,635.3"`), because YouTube starts playback at the nearest keyframe.
- Disclose on screen in every pause that the voices are AI echoes, not the real people, and turn on YouTube's altered or synthetic content label.

## Takedowns

If you are one of the people echoed in a weave and want it removed, open an issue and it comes down.
