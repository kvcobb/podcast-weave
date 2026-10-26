"""One text-in, text-out call to whichever model the person running this has.

Pick a backend with CPC_LLM (default: auto, the first one that is configured):
  claude-cli  the `claude` command (Claude Code; uses your Claude subscription)  model: CPC_MODEL, default claude-opus-5-5
  anthropic   Anthropic API, ANTHROPIC_API_KEY (official `anthropic` SDK)          model: CPC_MODEL, default claude-opus-5-5
  openai      OpenAI API, OPENAI_API_KEY (official `openai` SDK)                   model: CPC_MODEL, required
  xai         xAI (Grok), XAI_API_KEY (via the `openai` SDK at api.x.ai)           model: CPC_MODEL, required
  gemini      Google Gemini, GEMINI_API_KEY (official `google-genai` SDK)          model: CPC_MODEL, required
  codex-cli   the `codex` command (OpenAI Codex CLI; uses your ChatGPT plan)       model: CPC_MODEL, optional
Every call is one system prompt plus one user message and returns plain text. Prompts can be large (a soul-file prompt
carries the whole transcript), so the command-line backends get the prompt on stdin, never as an argument. Soul files are
12-20k characters of output: the Anthropic backend streams with a large output limit; for openai/xai/gemini pick a model
whose output limit is at least ~16k tokens. Name the model (CPC_MODEL) so the on-screen label can name the substrate.
"""
import os, shutil, subprocess, tempfile, threading, time

DEFAULT_CLAUDE = "claude-opus-5-5"
_tl = threading.local()   # per thread, so concurrent calls (ingest uses a thread pool) never mix up their provenance
def last():
    """This thread's last call: backend, configured model, and the model that answered when the backend reports it (else None)."""
    return dict(getattr(_tl, "last", {}))
def _record(**kw): _tl.last = kw


def backend():
    b = os.environ.get("CPC_LLM", "auto")
    if b != "auto":
        return b
    if shutil.which("claude"): return "claude-cli"
    if os.environ.get("ANTHROPIC_API_KEY"): return "anthropic"
    if os.environ.get("OPENAI_API_KEY"): return "openai"
    if os.environ.get("XAI_API_KEY"): return "xai"
    if os.environ.get("GEMINI_API_KEY"): return "gemini"
    if shutil.which("codex"): return "codex-cli"
    raise SystemExit("No model configured. Install Claude Code or Codex, or set one of ANTHROPIC_API_KEY, "
                     "OPENAI_API_KEY, XAI_API_KEY, GEMINI_API_KEY (see AGENTS.md).")


def model_name(b):
    m = os.environ.get("CPC_MODEL")
    if m: return m
    if b in ("claude-cli", "anthropic"): return DEFAULT_CLAUDE
    if b == "codex-cli": return None
    raise SystemExit(f"Set CPC_MODEL to the {b} model you want to use.")


def _claude_cli(prompt, system, model, timeout):
    # prompt on stdin; no project/user settings or MCP servers so your own setup can't leak into the echoes
    cmd = ["claude", "-p", "--model", model, "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config",
           "--disallowedTools", "Bash", "Edit", "Write", "Read", "Grep", "Glob", "WebFetch", "WebSearch", "Agent", "Task"]
    if system:
        sp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); sp.write(system); sp.close()
        cmd += ["--append-system-prompt-file", sp.name] if _supports("--append-system-prompt-file") else ["--append-system-prompt", system]
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=d, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
    _record(backend="claude-cli", configured=model, returned=None)   # plain-text output does not report the model
    return r.stdout.strip()


_flags = None
def _supports(flag):
    global _flags
    if _flags is None:
        _flags = subprocess.run(["claude", "--help"], capture_output=True, text=True).stdout
    return flag in _flags


def _codex_cli(prompt, system, model, timeout):
    # Isolated like _claude_cli: no user config, rules, project docs, shell, patching or web search, read-only sandbox,
    # nothing saved. The JSON event stream is checked: one finished turn, only reasoning and a reply, no tool use.
    full = (f"{system}\n\n" if system else "") + prompt
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.txt")
        cmd = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--json", "--skip-git-repo-check",
               "--sandbox", "read-only", "-c", "project_doc_max_bytes=0", "-c", "features.shell_tool=false",
               "-c", "features.apply_patch_freeform=false", "-c", 'web_search="disabled"', "-o", out] + (["-m", model] if model else []) + ["-"]
        r = subprocess.run(cmd, input=full, capture_output=True, text=True, cwd=d, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"codex exited {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
        import json
        events = [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]
        kinds = [e.get("type") for e in events]
        items = {(e.get("item") or {}).get("type") for e in events if e.get("type") == "item.completed"}
        if kinds.count("turn.completed") != 1 or "turn.failed" in kinds or "error" in kinds:
            raise RuntimeError(f"codex turn did not finish cleanly: {kinds[-4:]}")
        if items - {"agent_message", "reasoning"}:
            raise RuntimeError(f"codex used tools it should not have: {sorted(items - {'agent_message', 'reasoning'})}")
        _record(backend="codex-cli", configured=model, returned=None)   # the event stream does not report the model
        return open(out).read().strip() if os.path.exists(out) else ""


def _anthropic(prompt, system, model, timeout):
    import anthropic
    client = anthropic.Anthropic(timeout=timeout)
    kw = dict(model=model, max_tokens=64000, messages=[{"role": "user", "content": prompt}],
              output_config={"effort": "high"})
    if system: kw["system"] = system
    if model.startswith(("claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")):
        # server-side fallback: if a safety classifier declines, the API re-runs the request on a fallback model
        kw.update(betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
        stream = client.beta.messages.stream(**kw)
    else:
        stream = client.messages.stream(**kw)
    with stream as s:
        msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model declined: {getattr(msg, 'stop_details', None)}")
    got = getattr(msg, "model", None); _record(backend="anthropic", configured=model, returned=got)
    if got and got != model and not os.environ.get("CPC_ALLOW_FALLBACK"):
        # a fallback model answered; a room labelled with the configured model must not contain its words
        raise RuntimeError(f"answered by fallback model {got}, not {model} (set CPC_ALLOW_FALLBACK=1 to accept)")
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def _openai_compat(prompt, system, model, timeout, base_url=None, key_env="OPENAI_API_KEY"):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ[key_env], base_url=base_url, timeout=timeout)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = client.chat.completions.create(model=model, messages=msgs)
    return (r.choices[0].message.content or "").strip()


def _gemini(prompt, system, model, timeout):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    r = client.models.generate_content(model=model, contents=prompt, config=cfg)
    return (r.text or "").strip()


def ask(prompt, system=None, timeout=1500, tries=3):
    """Send one prompt; return the reply text. Retries on an empty reply or a transient error."""
    b = backend(); m = model_name(b); last = None
    for i in range(tries):
        try:
            if b == "claude-cli": out = _claude_cli(prompt, system, m, timeout)
            elif b == "codex-cli": out = _codex_cli(prompt, system, m, timeout)
            elif b == "anthropic": out = _anthropic(prompt, system, m, timeout)
            elif b == "openai": out = _openai_compat(prompt, system, m, timeout)
            elif b == "xai": out = _openai_compat(prompt, system, m, timeout, "https://api.x.ai/v1", "XAI_API_KEY")
            elif b == "gemini": out = _gemini(prompt, system, m, timeout)
            else: raise SystemExit(f"unknown CPC_LLM backend {b!r}")
            if out: return out
            last = RuntimeError("empty reply")
        except (subprocess.TimeoutExpired, RuntimeError, OSError) as e:
            last = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"{b} gave no usable reply after {tries} tries: {last}")


def describe():
    """A reader-facing name for the model hosting the echoes, e.g. 'Claude Opus 5.5' (used in on-screen labels)."""
    b = backend(); m = model_name(b) or {"codex-cli": "OpenAI Codex default model"}.get(b, b)
    import re
    k = re.match(r"claude-(opus|sonnet|haiku|fable)-(\d+)(?:-(\d+))?$", m)
    if k: return f"Claude {k[1].title()} {k[2]}" + (f".{k[3]}" if k[3] else "")
    return m
