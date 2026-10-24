// Podcast Weave player: one YouTube player that plays the original episode and a companion "segments" video in turn,
// following the steps in weaves/<originalId>.json. Pause, resume and volume are YouTube's own controls.
(function () {
  const id = (window.WEAVE_ID || new URLSearchParams(location.search).get("v") || location.pathname.split("/").filter(Boolean).pop() || "").trim();
  const base = window.WEAVE_BASE || "../";
  const $ = s => document.querySelector(s);
  let W, player, idx = 0, loadedAt = 0, started = false;

  function vid(step) { return W[step.video].id; }
  function load(i, autoplay) {
    idx = i; const st = W.steps[i]; if (!st) return;
    const opts = { videoId: vid(st), startSeconds: st.start };
    if (st.end != null) opts.endSeconds = st.end;
    loadedAt = Date.now();
    autoplay ? player.loadVideoById(opts) : player.cueVideoById(opts);
  }
  function next() { if (idx + 1 < W.steps.length) load(idx + 1, true); }
  function tick() {
    if (!player || !player.getCurrentTime || Date.now() - loadedAt < 1500) return;
    const st = W.steps[idx]; const data = player.getVideoData ? player.getVideoData() : null;
    if (!st || !data || data.video_id !== vid(st)) return;
    const t = player.getCurrentTime();
    if (st.end != null && t >= st.end - 0.15 && player.getPlayerState() !== YT.PlayerState.PAUSED) next();
  }
  function onState(e) {
    if (e.data === YT.PlayerState.PLAYING && !started) { started = true; document.body.classList.add("started"); }
    if (e.data === YT.PlayerState.ENDED && Date.now() - loadedAt > 1500) next();
  }
  window.onYouTubeIframeAPIReady = function () {
    fetch(base + "weaves/" + encodeURIComponent(id) + ".json").then(r => { if (!r.ok) throw new Error("No weave for " + id); return r.json(); }).then(w => {
      W = w;
      $("#orig").href = "https://www.youtube.com/watch?v=" + W.original.id;
      $("#orig").textContent = W.original.title + " (" + W.original.channel + ")";
      document.title = W.original.title + " · Podcast Weave";
      player = new YT.Player("player", {
        width: "100%", height: "100%",
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1, controls: 1, origin: location.origin },
        events: { onReady: () => load(0, false), onStateChange: onState }
      });
      setInterval(tick, 200);
    }).catch(err => { $("#about").innerHTML = "<b>" + err.message + "</b>"; });
  };
})();
