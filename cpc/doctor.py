"""`python -m cpc doctor`: what this machine can do, tested for real (a tiny model call and a real voice synthesis), with advice."""
import os, shutil, sys, time
from . import llm


def _ok(m): print(f"  ok    {m}")
def _no(m): print(f"  MISSING {m}")
def _hint(m): print(f"        -> {m}")


def doctor(skip_llm=False, skip_tts=False):
    print("Tools")
    for t, how in [("ffmpeg", "install ffmpeg (brew install ffmpeg / apt install ffmpeg / winget install ffmpeg)"),
                   ("yt-dlp", "pip install yt-dlp")]:
        (_ok(t) if shutil.which(t) else (_no(t), _hint(how)))
    for mod, pkg in [("youtube_transcript_api", "youtube-transcript-api"), ("faster_whisper", "faster-whisper"), ("PIL", "pillow"),
                     ("numpy", "numpy"), ("soundfile", "soundfile")]:
        try: __import__(mod); _ok(pkg)
        except Exception: _no(pkg); _hint(f"pip install {pkg}")
    print("Language model")
    try:
        b = llm.backend(); print(f"  using {llm.describe()}")
        if not skip_llm:
            t = time.time(); out = llm.ask("Reply with exactly: ready", timeout=180, tries=1)
            (_ok(f"reply '{out[:20]}' in {time.time()-t:.0f} s") if out else _no("empty reply"))
    except SystemExit as e:
        _no(str(e))
    except Exception as e:
        _no(f"call failed: {e}"); _hint("check the key / login for that backend, or set CPC_LLM to another one (AGENTS.md)")
    print("Voices")
    try:
        import torch
        dev = "cuda" if torch.cuda.is_available() else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() \
            else "xpu" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu"
        extra = f", {torch.cuda.get_device_name(0)}, {torch.cuda.get_device_properties(0).total_memory/1e9:.0f} GB" if dev == "cuda" else ""
        print(f"  torch {torch.__version__}, device {dev}{extra}")
    except Exception:
        dev = None; print("  torch not installed (needed for local OmniVoice)")
    try:
        import omnivoice  # noqa
        if skip_tts: _ok("omnivoice imports (test synthesis skipped)")
        else:
            import numpy as np, soundfile as sf
            from omnivoice import OmniVoice
            from .tts import _device
            d, dt = _device(); t = time.time(); m = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=d, dtype=dt); load = time.time() - t
            t = time.time(); a = m.generate(text="This is a short test of the voice on this machine.", instruct="male, moderate pitch", num_step=32)
            a = np.asarray(a[0] if isinstance(a, (list, tuple)) else a).reshape(-1); secs = len(a) / 24000; gen = time.time() - t
            sf.write("doctor-voice-test.wav", a.astype("float32"), 24000)
            rtf = gen / max(secs, 0.1)
            _ok(f"OmniVoice on {d}: model load {load:.0f} s, {secs:.1f} s of speech in {gen:.1f} s (x{rtf:.2f} real time) -> doctor-voice-test.wav")
            if rtf > 3: _hint("this is slow here; a 10-minute pause would take a long time. Consider a GPU box (CPC_OMNIVOICE_URL) or ElevenLabs.")
    except ImportError:
        print("  OmniVoice not installed. Options:")
        _hint("local: pip install omnivoice (needs PyTorch; NVIDIA CUDA, Apple MPS or Intel XPU recommended). Weights are CC-BY-NC-4.0 (non-commercial).")
        _hint("remote: run OmniVoice on a GPU machine you control and set CPC_OMNIVOICE_URL (no hosted per-call OmniVoice API exists as of Oct 2026)")
        _hint("hosted alternative: ElevenLabs instant voice cloning, set ELEVENLABS_API_KEY and CPC_TTS=elevenlabs")
    except Exception as e:
        _no(f"OmniVoice failed here: {e}")
        _hint("set CPC_OMNIVOICE_URL to a GPU machine running it, or use ElevenLabs (CPC_TTS=elevenlabs)")
    if os.environ.get("CPC_OMNIVOICE_URL"): print(f"  remote OmniVoice configured: {os.environ['CPC_OMNIVOICE_URL']}")
    if os.environ.get("ELEVENLABS_API_KEY"): print("  ElevenLabs key present")
    print(f"Python {sys.version.split()[0]}. Work folder: {os.environ.get('CPC_WORK', os.path.join(os.getcwd(), 'work'))}")
