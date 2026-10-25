"""Text to speech, cloned from a short reference clip of each speaker. Pick with CPC_TTS:

  omnivoice         OmniVoice in this process (k2-fsa/OmniVoice). Runs on an NVIDIA GPU (CUDA), Apple Silicon (MPS), Intel (XPU),
                    or very slowly on CPU. `python -m cpc doctor` does a real test synthesis to tell you if it works here.
                    LICENCE: the code is Apache-2.0, the model WEIGHTS are CC-BY-NC-4.0 (non-commercial). Check that this fits your use.
  omnivoice-server  OmniVoice on another machine you control (a home GPU box or a rented one). On that machine run
                    `python -m cpc serve-tts --port 8810` (this repo; needs torch + omnivoice there), then set
                    CPC_OMNIVOICE_URL=http://that-machine:8810/v1/audio/speech here. The reference clip travels in the request
                    (base64), so the two machines don't share files. There is no hosted per-call OmniVoice API (Oct 2026).
  elevenlabs        ElevenLabs instant voice cloning. ELEVENLABS_API_KEY. Only clone voices you have the right to use (their terms).
Default (auto): omnivoice if it imports and a test clip works, else omnivoice-server if CPC_OMNIVOICE_URL is set, else elevenlabs
if a key is set.
"""
import json, os, re, subprocess
from pathlib import Path

_model = None


def backend():
    b = os.environ.get("CPC_TTS", "auto")
    if b != "auto": return b
    try:
        import omnivoice  # noqa: F401
        return "omnivoice"
    except Exception:
        pass
    if os.environ.get("CPC_OMNIVOICE_URL"): return "omnivoice-server"
    if os.environ.get("ELEVENLABS_API_KEY"): return "elevenlabs"
    raise SystemExit("No text-to-speech available. Run `python -m cpc doctor` for options (see AGENTS.md, Voices).")


def _device():
    import torch
    if torch.cuda.is_available(): return "cuda:0", torch.float16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available(): return "mps", torch.float16
    if hasattr(torch, "xpu") and torch.xpu.is_available(): return "xpu", torch.float16
    return "cpu", torch.float32


def _omni(text, ref, ref_text, out):
    global _model
    import numpy as np, soundfile as sf
    if _model is None:
        from omnivoice import OmniVoice
        dev, dt = _device()
        _model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=dev, dtype=dt)
    a = _model.generate(text=text, ref_audio=str(ref), ref_text=ref_text, num_step=int(os.environ.get("CPC_NUM_STEP", 48)), speed=1.0)
    a = np.asarray(a[0] if isinstance(a, (list, tuple)) else a).astype("float32").reshape(-1)
    sf.write(str(out), a, 24000)


def _omni_server(text, ref, ref_text, out):
    import urllib.request, base64
    body = json.dumps(dict(model="omnivoice", input=text, ref_audio=str(ref), ref_audio_b64=base64.b64encode(Path(ref).read_bytes()).decode(),
                           ref_text=ref_text, num_step=int(os.environ.get("CPC_NUM_STEP", 48)), response_format="wav")).encode()
    req = urllib.request.Request(os.environ["CPC_OMNIVOICE_URL"], data=body, headers={"Content-Type": "application/json"})
    raw = Path(str(out) + ".raw"); raw.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    # servers differ in what they return (wav or mp3); normalise to 24 kHz mono wav
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "24000", "-ac", "1", str(out)], check=True); raw.unlink()


def _eleven_voice(ref, name):
    """One instant clone per reference clip, cached next to the clip."""
    import requests
    cache = Path(str(ref) + ".elevenlabs.json")
    if cache.exists(): return json.loads(cache.read_text())["voice_id"]
    with open(ref, "rb") as f:
        r = requests.post("https://api.elevenlabs.io/v1/voices/add", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                          data={"name": f"cpc-{name}", "description": "AI echo voice for a disclosed podcast continuation"},
                          files={"files": (Path(ref).name, f, "audio/wav")}, timeout=120)
    r.raise_for_status(); vid = r.json()["voice_id"]; cache.write_text(json.dumps({"voice_id": vid})); return vid


def _eleven(text, ref, ref_text, out, name):
    import requests
    vid = _eleven_voice(ref, name)
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                      json={"text": text, "model_id": os.environ.get("CPC_ELEVEN_MODEL", "eleven_multilingual_v2")}, timeout=300)
    r.raise_for_status(); mp3 = str(out) + ".mp3"; Path(mp3).write_bytes(r.content)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ar", "24000", "-ac", "1", str(out)], check=True)


def chunks(text, n=420):
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(cur) + len(s) > n and cur: parts.append(cur); cur = s
        else: cur = (cur + " " + s).strip()
    return parts + ([cur] if cur else [])


def serve(port=8810):
    """A tiny OmniVoice speech server for running the voices on another machine (POST /v1/audio/speech, JSON with input,
    ref_audio_b64 (or a local ref_audio path), ref_text, num_step) -> audio/wav."""
    import base64, tempfile
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                j = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with tempfile.TemporaryDirectory() as d:
                    ref = Path(d) / "ref.wav"
                    ref.write_bytes(base64.b64decode(j["ref_audio_b64"])) if j.get("ref_audio_b64") else ref.write_bytes(Path(j["ref_audio"]).read_bytes())
                    os.environ["CPC_NUM_STEP"] = str(j.get("num_step", 48)); out = Path(d) / "o.wav"; _omni(j["input"], ref, j.get("ref_text", ""), out)
                    data = out.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
    print(f"OmniVoice speech server on :{port} (POST /v1/audio/speech)"); ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


def speak(text, ref, ref_text, out, name="voice"):
    """Synthesize text in the voice of ref (wav) into out (wav, 24 kHz mono). Long text is split at sentences and joined."""
    out = Path(out)
    if out.exists() and out.stat().st_size > 2000: return out
    b = backend(); pieces = []
    for i, p in enumerate(chunks(text)):
        po = out.with_suffix(f".{i}.wav")
        for attempt in range(4):
            try:
                if b == "omnivoice": _omni(p, ref, ref_text, po)
                elif b == "omnivoice-server": _omni_server(p, ref, ref_text, po)
                elif b == "elevenlabs": _eleven(p, ref, ref_text, po, name)
                else: raise SystemExit(f"unknown CPC_TTS {b!r}")
                if po.exists() and po.stat().st_size > 1500: pieces.append(po); break
            except SystemExit: raise
            except Exception as e:
                print(f"tts retry {attempt+1} ({b}): {e}", flush=True)
                import time; time.sleep(6 * (attempt + 1))   # a cold server can take ~25 s to load the model
        else:
            raise RuntimeError(f"tts failed for: {p[:80]}")
    lst = out.with_suffix(".txt"); lst.write_text("".join(f"file '{x.resolve()}'\n" for x in pieces))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", str(out)], check=True)
    return out
