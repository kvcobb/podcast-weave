"""Local media for a weave: which file plays each video key, its duration, and audio cuts (cached, never uploaded)."""
import hashlib, json, os, subprocess
from pathlib import Path


def ffdur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try: return float(out)
    except ValueError: return None


class Media:
    """sources.json maps a weave video key (or its YouTube id) to a local file. Keys listed under "fetch" may be
    downloaded with yt-dlp when no local file exists: list only videos you published yourself."""
    def __init__(self, W, sources_path, cache):
        self.W, self.cache = W, Path(cache); self.cache.mkdir(parents=True, exist_ok=True)
        src = json.loads(Path(sources_path).read_text()) if sources_path else {}
        self.files, self.fetch = src.get("files", {}), set(src.get("fetch", []))
        self.ids = {"original": (W["original"] or {}).get("id")}
        for k, v in W.items():
            if isinstance(v, dict) and v.get("id") and k not in ("original",): self.ids[k] = v["id"]
        self.dur = {}

    def path(self, key):
        p = self.files.get(key) or self.files.get(self.ids.get(key) or "")
        if p and Path(p).exists(): return Path(p)
        if key in self.fetch or (self.ids.get(key) in self.fetch):
            yid = self.ids.get(key); out = self.cache / "fetched" / (yid + ".m4a")
            if not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio[ext=m4a]/bestaudio", "-o", str(out),
                                "https://youtu.be/" + yid], check=True)
            return out
        return None

    def duration(self, key):
        if key not in self.dur:
            p = self.path(key); self.dur[key] = ffdur(p) if p else None
        return self.dur[key]

    def cut(self, key, t0, t1):
        """Mono 16 kHz WAV of [t0, t1) of a video key, cached by file identity and range."""
        p = self.path(key)
        if p is None: raise FileNotFoundError("no local media for " + key + " (add it to sources.json)")
        st = p.stat(); h = hashlib.sha1(f"{p}|{st.st_size}|{st.st_mtime_ns}|{t0:.3f}|{t1:.3f}".encode()).hexdigest()[:16]
        out = self.cache / "cuts" / (key + "-" + h + ".wav")
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{max(0, t0):.3f}", "-to", f"{t1:.3f}", "-i", str(p),
                            "-vn", "-ac", "1", "-ar", "16000", str(out)], check=True)
        return out


def concat(wavs, out, bitrate=None, gap=0.0):
    """Join WAV pieces (same format) into out; with a bitrate, encode a compact local listening file."""
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    lst = out.with_suffix(".txt"); sil = None
    if gap > 0:
        sil = out.parent / "gap.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", str(gap), str(sil)], check=True)
    lines = []
    for i, w in enumerate(wavs):
        if i and sil: lines.append(f"file '{sil}'")
        lines.append(f"file '{Path(w).resolve()}'")
    lst.write_text("\n".join(lines) + "\n")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
    cmd += (["-c:a", "libmp3lame", "-b:a", bitrate] if bitrate else ["-c", "copy"]) + [str(out)]
    subprocess.run(cmd, check=True); lst.unlink(); return out


def silences(wav, min_len=1.5, noise="-40dB"):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(wav), "-af", f"silencedetect=n={noise}:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True)
    out, start = [], None
    for ln in r.stderr.splitlines():
        if "silence_start:" in ln: start = float(ln.split("silence_start:")[1].split()[0])
        elif "silence_end:" in ln and start is not None:
            end = float(ln.split("silence_end:")[1].split()[0]); out.append((round(start, 2), round(end, 2))); start = None
    if start is not None: out.append((round(start, 2), None))
    return out
