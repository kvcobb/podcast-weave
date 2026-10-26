// Podcast Weave player: one YouTube player that plays the original episode and companion videos in turn (any key in the
// weave JSON with an id can be a step video: "segments", or extras like "interlude" and "explainer"),
// following the steps in weaves/<originalId>.json. Pause, resume and volume are YouTube's own controls.
// Phones can refuse a scripted video switch, so every switch is checked: retry once, then cue the right video
// and ask for one tap. Add ?debug=1 to the page URL to see the player's state on screen.
(function () {
  const q = new URLSearchParams(location.search);
  const id = (window.WEAVE_ID || q.get("v") || location.pathname.split("/").filter(Boolean).pop() || "").trim();
  const base = window.WEAVE_BASE || "../";
  const debug = q.has("debug");
  const $ = s => document.querySelector(s);
  let W, player, idx = 0, loadedAt = 0, started = false, tries = 0, waitingTap = false, ccOff = false, node = null, choosing = false;

  function vid(step) { return W[step.video].id; }
  function playingId() {
    let d = null; try { d = player.getVideoData(); } catch (e) {}
    if (d && d.video_id) return d.video_id;
    try { return new URL(player.getVideoUrl()).searchParams.get("v"); } catch (e) { return null; }
  }
  function note(text) { const n = $("#note"); if (!n) return; n.textContent = text || ""; n.hidden = !text; }
  function load(i, autoplay) {
    idx = i; const st = W.steps[i]; if (!st) return;
    const opts = { videoId: vid(st), startSeconds: st.start };
    if (st.end != null) opts.endSeconds = st.end;
    loadedAt = Date.now(); ccOff = false;
    autoplay ? player.loadVideoById(opts) : player.cueVideoById(opts);
  }
  function next() {
    if (choosing) return;
    if (idx + 1 < W.steps.length) { tries = 0; load(idx + 1, true); return; }
    if (W.graph && node) nodeEnd();
  }
  // Branching weaves (W.graph): each node plays a few segments, then either moves on or offers at most three choices.
  // A choice is a real tap, which also lets phones start the next video.
  function enter(id, autoplay) {
    node = W.graph[id]; choosing = false; $("#choices").hidden = true;
    W.steps = node.seq.map(k => W.segs[k]); tries = 0; load(0, autoplay);
  }
  function nodeEnd() {
    if (node.next) { enter(node.next, true); return; }
    if (!node.choices) return;
    choosing = true; try { player.pauseVideo(); } catch (e) {}
    const box = $("#choices"); box.innerHTML = "";
    if (node.prompt) { const p = document.createElement("p"); p.textContent = node.prompt; box.appendChild(p); }
    node.choices.forEach(c => {
      const b = document.createElement("button"); b.type = "button"; b.textContent = c.label;
      b.onclick = () => enter(c.next, true); box.appendChild(b);
    });
    box.hidden = false;
  }
  function tick() {
    if (!player || !player.getCurrentTime) return;
    const st = W.steps[idx]; if (!st) return;
    const pid = playingId(), t = player.getCurrentTime(), state = player.getPlayerState();
    if (debug) $("#dbg").textContent = `step ${idx + 1}/${W.steps.length}  want ${vid(st)}  have ${pid}  t ${t.toFixed(1)}  state ${state}  tries ${tries}`;
    if (Date.now() - loadedAt < 1500) return;
    if (pid !== vid(st)) {
      // The switch didn't take. Retry once; after that, cue the right video so the next tap on play continues the weave.
      if (started && !waitingTap && Date.now() - loadedAt > 3000) {
        if (tries < 1) { tries++; load(idx, true); }
        else { waitingTap = true; load(idx, false); note("Tap play to continue"); }
      }
      return;
    }
    if (waitingTap && state === YT.PlayerState.PLAYING) { waitingTap = false; note(""); }
    if (st.end != null && t >= st.end - 0.15 && state !== YT.PlayerState.PAUSED) next();
  }
  function onState(e) {
    // Subtitles off by default each time a video starts; the viewer can still turn them on with the CC button.
    if (e.data === YT.PlayerState.PLAYING && !ccOff) { ccOff = true; try { player.unloadModule("captions"); player.unloadModule("cc"); } catch (err) {} }
    if (e.data === YT.PlayerState.PLAYING && !started) { started = true; document.body.classList.add("started"); }
    if (e.data === YT.PlayerState.ENDED && Date.now() - loadedAt > 1500 && playingId() === vid(W.steps[idx])) next();
  }

  // "What is this? / Make your own": plays the explainer (id in ../explainer.json once published) and links the repo.
  const REPO = "https://github.com/kvcobb/podcast-weave";
  function whatIsThis() {
    const b = document.createElement("button"); b.id = "whatis"; b.type = "button"; b.textContent = "?"; b.setAttribute("aria-label", "What is this? Click here to find out more, or make your own"); b.dataset.tip = "Click here for more information about what this is and how to make one for yourself";
    const ov = document.createElement("div"); ov.id = "explain"; ov.hidden = true;
    ov.innerHTML = '<div class="frame"></div><div class="row"><a href="' + REPO + '" target="_blank" rel="noopener">Make your own (GitHub)</a><button type="button">Close</button></div>';
    document.body.append(b, ov);
    let vid = null;
    fetch(base + "explainer.json").then(r => r.ok ? r.json() : null).then(j => { vid = j && j.youtube; }).catch(() => {});
    b.onclick = () => {
      if (!vid) { window.open(REPO, "_blank", "noopener"); return; }
      try { player.pauseVideo(); } catch (e) {}
      ov.querySelector(".frame").innerHTML = '<iframe src="https://www.youtube.com/embed/' + vid + '?autoplay=1&rel=0&playsinline=1" allow="autoplay; encrypted-media; fullscreen" allowfullscreen title="What this is, and how to make one"></iframe>';
      ov.hidden = false;
    };
    ov.querySelector("button").onclick = () => { ov.hidden = true; ov.querySelector(".frame").innerHTML = ""; };
  }
  window.onYouTubeIframeAPIReady = function () {
    whatIsThis();
    fetch(base + "weaves/" + encodeURIComponent(id) + ".json").then(r => { if (!r.ok) throw new Error("No weave for " + id); return r.json(); }).then(w => {
      W = w;
      $("#orig").href = "https://www.youtube.com/watch?v=" + W.original.id;
      $("#orig").textContent = W.original.title + " (" + W.original.channel + ")";
      document.title = W.original.title + " · Podcast Weave";
      if (W.paths && W.paths.length) {   // other routes through the same woven grid (a route is what plays, not what each pause read)
        const v = document.createElement("div"); v.id = "versions";
        v.append("Versions: ");
        W.paths.forEach((p, i) => {
          if (i) v.append(" · ");
          if (p.id === id) { const b = document.createElement("b"); b.textContent = p.label; v.append(b); }
          else { const a = document.createElement("a"); a.href = base + p.id + "/"; a.textContent = p.label; v.append(a); }
        });
        $("#about").appendChild(v);
      }
      if (debug) { const d = document.createElement("div"); d.id = "dbg"; document.body.appendChild(d); }
      player = new YT.Player("player", {
        width: "100%", height: "100%",
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1, controls: 1, cc_load_policy: 0, origin: location.origin },
        events: { onReady: () => { if (W.graph) { const c = document.createElement("div"); c.id = "choices"; c.hidden = true; document.body.appendChild(c); enter(W.start, false); } else load(0, false); }, onStateChange: onState }
      });
      setInterval(tick, 200);
      window.__weave = { player: () => player, step: () => idx, node: () => node, skip: () => { if (W.graph && node) { idx = W.steps.length - 1; nodeEnd(); } } };   // skip: test aid (ends the current node)
    }).catch(err => { $("#about").innerHTML = "<b>" + err.message + "</b>"; });
  };
})();
