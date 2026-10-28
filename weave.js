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
  let R = null, rKey = "", rLast = -1, evN = 0, evKey = "";
  let W, player, idx = 0, loadedAt = 0, started = false, tries = 0, waitingTap = false, ccOff = false, node = null, choosing = false, shown = false, gIdx = -1;
  let IX = null, ix = null, ixFired = false, hist = [], restoring = false, wantPlay = false;   // the stop-the-clock interruption and the in-page Back history

  function vid(step) { return W[step.video].id; }
  function playingId() {
    let d = null; try { d = player.getVideoData(); } catch (e) {}
    if (d && d.video_id) return d.video_id;
    try { return new URL(player.getVideoUrl()).searchParams.get("v"); } catch (e) { return null; }
  }
  function note(text) { const n = $("#note"); if (!n) return; n.textContent = text || ""; n.hidden = !text; }
  function load(i, autoplay, at) {
    idx = i; const st = W.steps[i]; if (!st) return;
    const opts = { videoId: vid(st), startSeconds: at != null ? at : st.start };
    if (st.end != null) opts.endSeconds = st.end;
    loadedAt = Date.now(); ccOff = false; wantPlay = !!autoplay;
    autoplay ? player.loadVideoById(opts) : player.cueVideoById(opts);
  }
  function next() {
    if (choosing || ix) return;
    if (idx + 1 < W.steps.length) { remember(); tries = 0; load(idx + 1, true); return; }
    if (W.graph && node) nodeEnd();
  }
  // Branching weaves (W.graph): each node plays a few segments, then either moves on or offers at most three choices.
  // A choice is a real tap, which also lets phones start the next video.
  function enter(id, autoplay, i, at) {
    node = W.graph[id]; choosing = false; shown = false; $("#choices").hidden = true;
    gIdx = node.guide ? node.seq.indexOf(node.guide.seg) : -1;
    W.steps = node.seq.map(k => W.segs[k]); tries = 0; load(i || 0, autoplay, at);
  }
  function nodeId() { return node ? Object.keys(W.graph).find(x => W.graph[x] === node) : null; }
  // In-page Back (K tg:16468): the steps actually visited, with the media time each was left at, so Back returns to
  // what was playing before a choice or a map jump. The browser's own back button would leave the page.
  function here() {
    const st = W.steps && W.steps[idx]; if (!st) return null;
    let t = st.start || 0; try { if (playingId() === vid(st)) t = player.getCurrentTime(); } catch (e) {}
    if (st.end != null && t > st.end - 2) t = Math.max(st.start || 0, st.end - 10);   // left at its end: come back ten seconds before it
    return { node: nodeId(), idx, t, seg: W.graph ? node.seq[idx] : idx };
  }
  function remember(given) { if (restoring || !W.steps) return; const h = given || here(); if (!h) return; const top = hist[hist.length - 1];
    if (!top || top.node !== h.node || top.idx !== h.idx || Math.abs(top.t - h.t) > 3) hist.push(h); if (hist.length > 60) hist.shift(); backState(); }
  function back() {
    if (ix) endClock(false);
    const h = hist.pop(); backState(); if (!h) return;
    restoring = true;
    if (h.node === "plain" && PL) plainGo(h.seg, h.t, true);
    else if (W.graph) enter(h.node, true, h.idx, h.t); else load(h.idx, true, h.t);
    restoring = false;
  }
  function backState() { const b = $("#back"); if (b) b.disabled = !hist.length; }
  function nodeEnd() {
    if (node.next) { remember(); enter(node.next, true); return; }
    if (!node.choices || !node.choices.length) return;   // the end: nothing to choose
    choosing = true; try { player.pauseVideo(); } catch (e) {}
    if (!shown) showChoices(); else $("#choices").classList.remove("guiding");
    light(1e9);
  }
  // The choice room (ui 2): preview cards in the explainer's look. While a guide segment plays, Harmony and Joscha name
  // each choice and its card lights; any card can be tapped at any time (a tap is also what lets phones start the video).
  const MODEL = { O: "Opus", S: "Sol" };
  function strip(c) {
    const d = document.createElement("div"); d.className = "strip";
    (c.strip || []).forEach((m, i) => {
      const t = (W.spots || [])[i] || "pause " + (i + 1);   // the pause times come from the weave file, never assumed
      const s = document.createElement("span");
      s.className = "dot " + (m === "O" ? "o" : m === "S" ? "s" : m === "?" ? "q" : "x");
      const mod = W.models && W.models[m];   // grids with named models carry their own colours
      if (mod) s.innerHTML = '<i style="background:' + mod.color + '"></i>';
      s.title = t + (mod ? " on " + mod.name : m === "O" || m === "S" ? " on " + MODEL[m] : m === "?" ? " (you choose)" : "");
      s.innerHTML = (mod ? s.innerHTML : "<i></i>") + "<small>" + t + "</small>"; d.appendChild(s);
    });
    if (c.notes) { const n = document.createElement("em"); n.className = "notes " + c.notes; n.textContent = c.notes === "w" ? "with notes" : "no notes"; d.appendChild(n); }
    return d;
  }
  function accent(c) {
    if (c.kind === "with" || c.kind === "without") return c.kind;
    const ms = (c.strip || []).filter(m => m === "O" || m === "S"); return c.kind === "finish" ? "fin" : (ms.length ? ms[ms.length - 1].toLowerCase() : "fin");
  }
  function showChoices() {
    shown = true; const box = $("#choices"); box.innerHTML = ""; box.className = W.ui === 2 ? "v2" : "";
    if (W.ui === 2 && node.guide && !choosing) box.classList.add("guiding");   // the guide's map stays visible above the cards
    if (W.ui === 2 && node.label) { const h = document.createElement("h2"); h.textContent = node.label; box.appendChild(h); }
    if (node.prompt) { const p = document.createElement("p"); p.textContent = node.prompt; box.appendChild(p); }
    const grid = document.createElement("div"); grid.className = "cards"; box.appendChild(grid);
    node.choices.forEach(c => {
      const b = document.createElement("button"); b.type = "button"; b.dataset.kind = c.kind || "";
      if (W.ui === 2) {
        b.className = "card a-" + accent(c);
        const lastM = (c.strip || []).filter(m => W.models && W.models[m]).pop(); if (lastM && !c.notes) b.style.setProperty("--acc", W.models[lastM].color);
        if (c.thumb) { const im = document.createElement("img"); im.alt = ""; im.loading = "lazy"; im.src = c.thumb.includes("/") ? base + c.thumb : "https://i.ytimg.com/vi/" + c.thumb + "/mqdefault.jpg"; b.appendChild(im); }
        const body = document.createElement("div"); body.className = "body";
        const t = document.createElement("b"); t.textContent = c.label; body.appendChild(t);
        if (c.desc) { const d = document.createElement("span"); d.textContent = c.desc; body.appendChild(d); }
        body.appendChild(strip(c)); b.appendChild(body);
      } else b.textContent = c.label;
      b.onclick = () => { remember(); enter(c.next, true); }; grid.appendChild(b);
    });
    if (W.ui === 2) { const s = document.createElement("div"); s.className = "speaker"; s.hidden = true; box.appendChild(s); }
    box.hidden = false;
  }
  function light(t) {   // cards named up to time t in the guide are lit; the one named most recently glows
    if (!node || !node.guide || W.ui !== 2) return;
    const cues = node.guide.cues || {}; let last = -1;
    Object.values(cues).forEach(x => { if (x <= t && x > last) last = x; });
    document.querySelectorAll("#choices .card").forEach(b => {
      const k = b.dataset.kind, x = cues[k] != null ? cues[k] : (k.startsWith("next") ? cues[k] : null);
      b.classList.toggle("lit", x != null && x <= t); b.classList.toggle("now", x != null && x === last && t < 1e8);
    });
    const sp = $("#choices .speaker"); if (!sp) return;
    const who = (node.guide.speakers || []).find(r => r[0] <= t && t < r[1]);
    sp.hidden = !who; if (who) {     // narrators come from the weave file; Harmony and Joscha are this repo's own AI seats
      const nm = (W.narrators && W.narrators[who[2]]) || { harmony: "Harmony · AI seat", joscha: "Joscha · AI seat" }[who[2]] || who[2];
      sp.className = "speaker " + who[2]; sp.textContent = nm;
      const av = R && R.cast && R.cast[who[2]] && R.cast[who[2]].avatar;   // the cast's cartoon avatar, when the weave has one
      if (av) { const im = document.createElement("img"); im.alt = ""; im.src = base + av; sp.prepend(im); sp.classList.add("av"); }
    }
  }
  // Live countdown to the next pause or resume (K tg:16453). It reads the media time of the verified playing video, so it
  // stops when the video stops (pause, buffering, the wrong video still loading) and follows seeks and playback speed.
  // Whole seconds above 30, tenths in the last 30, hundredths in the last 10; nothing while a choice waits on the viewer.
  const HANDS = ["👍", "👌", "🤙", "🤘"];
  const SOON = { pause: "next pause soon", resume: "original resumes soon", choice: "your choice soon", next: "next clip soon", end: "ends soon" };
  function upcoming() {   // what happens when the current step ends, from the weave data
    let nx = W.steps[idx + 1];
    if (!nx && W.graph && node && node.next && W.graph[node.next]) nx = W.segs[W.graph[node.next].seq[0]];
    const choice = !nx && W.graph && node && node.choices && node.choices.length;
    if (W.steps[idx].video === "original") return nx || choice ? "pause" : "end";
    return nx ? (nx.video === "original" ? "resume" : "next") : choice ? "choice" : "end";
  }
  function fmtClock(r) {
    const m = Math.floor(r / 60), sec = Math.floor(r % 60), pad = String(sec).padStart(2, "0");
    if (r > 30) return m + ":" + pad;
    if (r > 10) return m + ":" + pad + "." + Math.floor((r % 1) * 10);
    return m + ":" + pad + "." + String(Math.floor((r % 1) * 100)).padStart(2, "0");
  }
  function clockFrame() {
    requestAnimationFrame(clockFrame);
    const bar = $("#bar"); if (!bar || !player || !player.getCurrentTime || !W || !W.steps) return;
    mapHead(); plainFrame(); if (ix) return;   // during the interruption the clock holds its last value
    const st = W.steps[idx], clock = $("#clock"), soon = $("#soon"), now = $("#nowline");
    let r = null, state = -1;
    if (st && !choosing && Date.now() - loadedAt > 800 && playingId() === vid(st)) {
      const t = player.getCurrentTime(); state = player.getPlayerState();
      const end = st.end != null ? st.end : player.getDuration();
      if (end > 0 && t >= (st.start || 0) - 1 && state !== YT.PlayerState.CUED && state !== -1) r = Math.max(0, (end - t) / (player.getPlaybackRate() || 1));
    }
    bar.classList.toggle("live", r != null);
    if (r == null) { clock.textContent = "–:––"; soon.classList.remove("on"); now.classList.remove("off"); return; }
    clock.textContent = fmtClock(r);
    const k = (node ? Object.keys(W.graph).find(x => W.graph[x] === node) : "") + "/" + idx;
    if (k !== evKey) { evKey = k; evN++; now.textContent = (st.label || "").split(";")[0]; }
    const on = r <= 6 && state === YT.PlayerState.PLAYING, kind = upcoming();
    if (on) soon.textContent = "… " + SOON[kind] + " " + HANDS[evN % HANDS.length];
    soon.classList.toggle("on", on); now.classList.toggle("off", on);
  }
  // Reactions (K tg:16453): short scripted comments from the cast, keyed to a video and a time in that video, so the same
  // track serves every route. They fire as playback passes them; a seek or a switch never replays a backlog.
  function reactTick(st, t, playing) {
    if (!R || !R.tracks) return;
    if (st.video !== rKey) { rKey = st.video; rLast = t; $("#feed").innerHTML = ""; return; }
    if (t < rLast - 0.5 || t - rLast > 2) { rLast = t; $("#feed").innerHTML = ""; return; }   // a seek (even while paused or buffering): clear the feed and start from here
    if (!playing) { rLast = t; return; }
    (R.tracks[st.video] || []).forEach(x => { if (x.t > rLast && x.t <= t && x.t >= (st.start || 0) && (st.end == null || x.t <= st.end)) react(Object.assign({ video: st.video }, x)); });
    rLast = t;
  }
  function react(x) {
    const c = (R.cast || {})[x.who] || { name: x.who }, f = $("#feed"); if (!f || f.hidden) return;
    const d = document.createElement("div"); d.className = "rx"; d.style.setProperty("--who", c.color || "#9cc4ff");
    const av = byHost(c.avatar_by_host, x.video || rKey, c.avatar);   // the comment's own room decides the lens colour
    if (av) { const im = document.createElement("img"); im.alt = ""; im.src = base + av; d.appendChild(im); }
    const b = document.createElement("div"), h = document.createElement("b"), tag = document.createElement("small"), p = document.createElement("p");
    h.textContent = c.name; tag.textContent = c.tag || ""; p.textContent = x.text; b.append(h, tag, p); d.appendChild(b);
    f.appendChild(d); while (f.children.length > 3) f.firstChild.remove();
    setTimeout(() => d.classList.add("out"), 11000); setTimeout(() => d.remove(), 12000);
  }
  function buildBar() {
    const bar = document.createElement("div"); bar.id = "bar";
    bar.innerHTML = '<span id="clock" title="Time to the next pause or resume">–:––</span><span class="txt"><span id="nowline"></span><span id="soon"></span></span>';
    const f = document.createElement("div"); f.id = "feed"; f.setAttribute("aria-live", "off");
    document.body.append(bar, f);
    if (W.graph && !plainOn()) {
      const bk = document.createElement("button"); bk.id = "back"; bk.type = "button"; bk.textContent = "‹ Back"; bk.disabled = true;
      bk.title = "Back to what was playing before your last choice or jump"; bk.onclick = back; bar.insertBefore(bk, bar.firstChild);
    }
    if (R && R.tracks) {
      const b = document.createElement("button"); b.id = "feedtoggle"; b.type = "button";
      let off = true; try { off = localStorage.getItem("weave-feed") !== "on"; } catch (e) {}   // off by default (K tg:16637); the viewer can turn them on
      const set = () => { f.hidden = off; b.textContent = off ? "Comments off" : "Comments on"; b.setAttribute("aria-pressed", String(!off)); };
      b.onclick = () => { off = !off; try { localStorage.setItem("weave-feed", off ? "off" : "on"); } catch (e) {} set(); }; set(); bar.appendChild(b);
    }
    requestAnimationFrame(clockFrame);
  }
  function tick() {
    if (!player || !player.getCurrentTime) return;
    const st = W.steps[idx]; if (!st) return;
    const pid = playingId(), t = player.getCurrentTime(), state = player.getPlayerState();
    if (debug) $("#dbg").textContent = `step ${idx + 1}/${W.steps.length}  want ${vid(st)}  have ${pid}  t ${Number(t || 0).toFixed(1)}  state ${state}  tries ${tries}`;
    if (ix) return;   // stopped clock: the room waits; the interruption drives itself
    if (Date.now() - loadedAt < 1500) return;
    if (pid !== vid(st)) {
      // The switch didn't take. Retry once; after that, cue the right video so the next tap on play continues the weave.
      // A tap before the first play (Chapters, a map jump) counts too: the real player drops a load made while it is still cueing.
      if ((started || wantPlay) && !waitingTap && Date.now() - loadedAt > 3000) {
        if (tries < 1) { tries++; load(idx, true); }
        else { waitingTap = true; load(idx, false); note("Tap play to continue"); }
      }
      return;
    }
    if (waitingTap && state === YT.PlayerState.PLAYING) { waitingTap = false; note(""); }
    if (ix) return;   // the stop-the-clock interruption freezes reactions, choices and step changes
    if (IX && !ixFired && W.graph && node && node.seq[idx] === IX.seg && state === YT.PlayerState.PLAYING && t >= IX.at && t < IX.at + 5) { stopClock(t); return; }
    reactTick(st, t, state === YT.PlayerState.PLAYING);
    if (W.graph && node && node.guide && idx === gIdx) { if (!shown && state === YT.PlayerState.PLAYING) showChoices(); light(t); }
    if (st.end != null && t >= st.end - 0.15 && state !== YT.PlayerState.PAUSED) next();
  }
  function onState(e) {
    // Subtitles off by default each time a video starts; the viewer can still turn them on with the CC button.
    if (e.data === YT.PlayerState.PLAYING && !ccOff) { ccOff = true; try { player.unloadModule("captions"); player.unloadModule("cc"); } catch (err) {} }
    if (e.data === YT.PlayerState.PLAYING && !started) { started = true; document.body.classList.add("started"); }
    if (e.data === YT.PlayerState.PLAYING && ix && !ix.yt) { try { player.pauseVideo(); } catch (err) {} return; }
    if (ix) return;   // the clock stays stopped until the echo finishes
    if (e.data === YT.PlayerState.ENDED && Date.now() - loadedAt > 1500 && playingId() === vid(W.steps[idx])) next();
  }

  // Which company hosts the echoes in a video (K tg:16482): Kurtis's lenses are orange on Anthropic, blue on anything else.
  function hostOf(key) {
    const t = ((W.segs && W.segs[key] && W.segs[key].label) || "") + " " + ((W[key] && W[key].title) || "");
    return /OpenAI|\bSol\b|GPT|Astra|Gemini|Grok/i.test(t) ? "other" : "anthropic";
  }
  function byHost(m, key, dflt) { return (m && (m[hostOf(key)] || m.anthropic)) || dflt; }
  // Stop the clock: a frozen-room video preserves the picture while reusing the playback grant. Kurtis's
  // AI echo (named as an echo, in his cloned voice) points at the "?" button and says what is behind it, then the room
  // resumes from the exact frame it stopped on. How often it plays is set by the interrupt file's "freq" ("every",
  // "first" for the first visit only, "off"), or ?interrupt=every|first|off on the page URL.
  function ixFreq() { return q.get("interrupt") || (IX && IX.freq) || "every"; }
  function stopClock(t) {
    if (ix) return;
    ixFired = true; if (ixFreq() === "first") { try { localStorage.setItem("weave-ix-" + id, "1"); } catch (e) {} }
    ix = { video: playingId(), t, idx, node: nodeId(), line: -1 };
    try { player.pauseVideo(); } catch (e) {}
    document.body.classList.add("ix");
    const o = document.createElement("div"); o.id = "stopclock"; o.setAttribute("role", "dialog"); o.setAttribute("aria-label", IX.name + ", an AI echo, explains the What is this button");
    o.innerHTML = '<div class="who"><img alt=""><div><b></b><small></small></div></div><p class="line" aria-live="polite"></p><div class="row"><button type="button" class="hear" hidden>🔊 Tap to hear</button><button type="button" class="skip">Skip ›</button></div><div class="hand" aria-hidden="true">👆</div>';
    if (IX.pointer) { o.classList.add("pt"); const k = document.createElement("img"); k.className = "kpt"; k.alt = ""; k.src = base + byHost(IX.pointer.img_by_host, IX.seg, IX.pointer.img); k.onload = aimHand; o.appendChild(k); o.querySelector(".hand").remove(); }   // his own cartoon hand does the pointing (K tg:16471)
    o.querySelector("img").src = base + byHost(IX.avatar_by_host, IX.seg, IX.avatar); o.querySelector("b").textContent = IX.name; o.querySelector("small").textContent = IX.tag;
    document.body.appendChild(o); aimHand(); window.addEventListener("resize", aimHand);
    o.querySelector(".skip").onclick = () => endClock(true);
    const show = sec => {   // captions and the pointing moment follow the voice's own clock
      let k = -1; IX.lines.forEach((l, i) => { if (l.t <= sec) k = i; });
      if (k !== ix.line) { ix.line = k; o.querySelector(".line").textContent = k >= 0 ? IX.lines[k].text : ""; if (IX.pointer) o.classList.toggle("pointing", k >= (IX.pointer.from || 0)); }
    };
    if (IX.youtube) {
      // Reuse the already-playing iframe on iOS. This clip holds the room's stop frame,
      // not a second portrait, so the overlay still has just one pointing character.
      const active = ix, h = o.querySelector(".hear");
      active.yt = true; active.t0 = Date.now();
      const playClip = () => {
        if (ix !== active) return;
        try {
          if (playingId() !== IX.youtube) { ccOff = false; player.loadVideoById({ videoId: IX.youtube, startSeconds: 0 }); }
          else player.playVideo();
        } catch (e) { h.hidden = false; }
      };
      h.onclick = playClip;
      playClip();
      active.timer = setInterval(() => {
        if (ix !== active) return;
        let sec = 0, st = -1, matched = false;
        try { matched = playingId() === IX.youtube; if (matched) { sec = player.getCurrentTime(); st = player.getPlayerState(); } } catch (e) {}
        show(sec);
        if (matched && (st === YT.PlayerState.ENDED || (sec >= IX.dur - 0.25 && st === YT.PlayerState.PLAYING))) { endClock(true); return; }
        h.hidden = !(Date.now() - active.t0 > 3500 && st !== YT.PlayerState.PLAYING && sec < 0.5);
      }, 100);
      return;
    }
    // A voice-only audio element leaves the room frame intact. A second video in the main
    // player produced the duplicate "ghost" portrait K saw on his tablet (tg:16625).
    const active = ix, a = new Audio(base + IX.audio), h = o.querySelector(".hear");
    active.audio = a;
    const hear = () => {
      if (ix !== active) return;
      h.hidden = false;
      h.textContent = a.error ? "Retry audio" : "🔊 Tap to hear";
    };
    const playVoice = () => {
      if (ix !== active) return;
      h.hidden = true;
      if (a.error) a.load();
      Promise.resolve(a.play()).then(() => {
        if (ix !== active) a.pause();   // Skip/help/navigation may have won the race
      }).catch(hear);
    };
    h.onclick = playVoice;
    a.onplaying = () => { if (ix === active) h.hidden = true; else a.pause(); };
    a.onerror = hear;
    a.onended = () => { if (ix === active) endClock(true); };
    playVoice();
    active.timer = setInterval(() => {
      if (ix !== active) return;
      show(a.currentTime || 0);   // never dismiss an unheard invitation on a wall-clock timer
    }, 100);
  }
  function aimHand() {   // the hand points at wherever the ? button really is, at any screen size
    const o = $("#stopclock"), b = $("#whatis"); if (!o || !b) return;
    const k = o.querySelector(".kpt");
    if (k) {   // place the cartoon so the point where his gaze and finger lines meet sits on the button (K tg:16472)
      const r = b.getBoundingClientRect(), W0 = innerWidth, H0 = innerHeight, ar = (k.naturalWidth || 886) / (k.naturalHeight || 720);
      const [mx, my] = IX.pointer.meet, bx = r.left + r.width / 2, by = r.top + r.height / 2, band = $("#map") || $("#plain"), mapH = (band ? band.offsetHeight + 12 : 12);
      const h = Math.max(120, Math.min((H0 - mapH - 12 - by) / (1 - my), W0 * 0.98 / ar, 640)), w = h * ar;
      k.style.width = w + "px"; k.style.height = h + "px"; k.style.left = (bx - mx * w) + "px"; k.style.top = (by - my * h) + "px";
      return;
    }
    const h = o.querySelector(".hand"), img = o.querySelector(".who img"), r = b.getBoundingClientRect(), p = img.getBoundingClientRect();
    const size = Math.max(64, Math.min(p.width, 0.32 * innerWidth, 0.3 * innerHeight)); h.style.fontSize = size + "px";
    const hx = Math.min(innerWidth - size * 0.7, p.right + size * 0.15), hy = Math.max(r.bottom + size * 0.6, p.top - size * 0.1);   // beside the portrait, below the button
    h.style.left = hx + "px"; h.style.top = hy + "px";
    const ang = Math.atan2((r.top + r.height / 2) - hy, (r.left + r.width / 2) - hx) * 180 / Math.PI + 90;   // 👆 points up at 0 degrees
    h.style.transform = "translate(-50%, -50%) rotate(" + ang.toFixed(1) + "deg)";
  }
  function endClock(play) {
    if (!ix) return; const s = ix; ix = null;
    clearInterval(s.timer); try { if (s.audio) { s.audio.onended = s.audio.onplaying = s.audio.onerror = null; s.audio.pause(); } } catch (e) {}
    window.removeEventListener("resize", aimHand); const o = $("#stopclock"); if (o) { o.classList.add("leaving"); setTimeout(() => o.remove(), 700); } document.body.classList.remove("ix");   // the invitation fades out; the room picture was never replaced
    rLast = s.t; rKey = W.steps[idx].video;   // the feed carries on from the stopped second; nothing already shown fires again
    if (s.yt) { load(idx, !!play, s.t); return; }   // cue asynchronously; saved time remains in application state
    if (!play) return;
    if (playingId() === s.video) { try { if (Math.abs(player.getCurrentTime() - s.t) > 0.5) player.seekTo(s.t, true); player.playVideo(); } catch (e) {} }
    else load(idx, true, s.t);
  }

  // The weave map (K tg:16469): a thin bar under the player, laid out like a transit map on the original's own time
  // scale. The original runs along the top line; each pause room drops from its moment in the original and runs to its
  // own length at the same scale, one lane per version. Tap or hover a branch for its name; tap again (or click) to play it.
  let MAP = null;
  function segNode(seg) {   // where a segment can be played from: the current node if it holds it, otherwise the first that does
    if (node && node.seq.includes(seg)) return nodeId();
    return Object.keys(W.graph).find(k => W.graph[k].seq.includes(seg));
  }
  function origDur() { let d = W.original.duration || 0; try { if (playingId() === W.original.id && player.getDuration() > 0) d = player.getDuration(); } catch (e) {} return d; }
  function buildMap() {
    if (!W.graph || !W.segs) return;
    // Rooms are found from the weave's own graph, not from their names (Joscha QA): walk every route from the start,
    // carrying where the original was stopped; each other segment sits at that moment, one lane per segment there.
    const origs = Object.keys(W.segs).filter(k => W.segs[k].video === "original").sort((a, b) => W.segs[a].start - W.segs[b].start);
    if (!origs.length) return;
    const at = {}, order = [], seen = new Set(), queue = [[W.start, origs.length ? W.segs[origs[0]].start : 0]];
    while (queue.length) {
      const [id, c0] = queue.shift(), key = id + "@" + c0; if (seen.has(key) || !W.graph[id]) continue; seen.add(key);
      let c = c0; const n = W.graph[id];
      n.seq.forEach(k => { const g = W.segs[k]; if (!g) return;
        if (g.video === "original") { c = g.end != null ? g.end : c; return; }
        if (g.end == null || at[k] != null) return; at[k] = c; order.push(k); });
      [n.next, ...(n.choices || []).map(x => x.next)].filter(Boolean).forEach(nx => queue.push([nx, c]));
    }
    if (!order.length) return;
    const bySpot = {}; order.forEach(k => (bySpot[at[k]] = bySpot[at[k]] || []).push(k));
    const lanes = Math.max(...Object.values(bySpot).map(a => a.length));
    const el = document.createElement("div"); el.id = "map"; el.style.setProperty("--lanes", lanes);
    el.innerHTML = '<div class="tip"><span class="hint">Tap a line to see what plays there</span><span class="what" hidden></span><button type="button" hidden>▶ Play</button></div><div class="rail"></div><div class="head"></div>';
    document.body.appendChild(el); document.body.classList.add("hasmap");
    MAP = { el, items: [], bySpot, origs, lanes, pick: null };
    const add = (seg, kind, lane, label, t0, len, at0) => {
      const b = document.createElement("button"); b.type = "button"; b.className = "br " + kind; b.dataset.seg = seg; b.style.setProperty("--lane", lane);
      b.setAttribute("aria-label", label); b.innerHTML = "<i></i>"; el.appendChild(b); MAP.items.push({ b, seg, t0, len, at: at0, label, lane });
      b.onpointerenter = e => { if (e.pointerType === "mouse") tipFor(b, false); };
      b.onpointerleave = e => { if (e.pointerType === "mouse" && MAP.pick !== b) tipIdle(); };
      b.onclick = e => { if (e.pointerType === "mouse" || e.detail === 0 || MAP.pick === b) mapGo(b); else tipFor(b, true); };
    };
    const kindOf = k => { const t = ((W.segs[k] && W.segs[k].label) || "") + " " + ((W[W.segs[k].video] && W[W.segs[k].video].title) || "");
      return (/OpenAI|\bSol\b|GPT|Astra|Gemini|Grok/i.test(t) ? "s" : /Claude|Opus|Fable|Sonnet|Anthropic/i.test(t) ? "o" : "h") + (/without/i.test(t) ? " nn" : ""); };
    origs.forEach(k => { const g = W.segs[k]; add(k, "orig", 0, (g.label || "Original").replace(/;.*/, ""), g.start, (g.end || W.original.duration) - g.start, null); });
    // K tg:16491: the map is a bus map. One continuous red bar is the original at its true scale (YouTube's progress bar,
    // filled to where the original has played); every insert point drops a line with an arrow, and the rooms sprout
    // from it as stacked branches at their true length. Only rooms are drawn (house clips between them are left off).
    Object.keys(bySpot).forEach(sp => { let i = 0; bySpot[sp].forEach(k => { const g = W.segs[k], kd = kindOf(k); if (kd[0] === "h") return;
      add(k, "room " + kd, ++i, (g.label || k).split(";")[0], +sp, g.end - (g.start || 0), g.start || 0); }); MAP.drop = Math.max(MAP.drop || 0, i);
      const m = document.createElement("div"); m.className = "ins"; m.dataset.t = sp; m.style.setProperty("--n", i); el.appendChild(m); });
    el.style.setProperty("--lanes", MAP.drop || 1);
    const red = document.createElement("button"); red.type = "button"; red.className = "br red"; red.innerHTML = '<i></i><b class="fill"></b>'; el.insertBefore(red, el.querySelector(".head"));
    const ri = { b: red, seg: origs[0], t0: 0, len: W.original.duration, at: W.segs[origs[0]].start, label: "", lane: 0, red: true }; MAP.items.push(ri); MAP.red = ri;
    MAP.origT = W.segs[origs[0]].start;
    red.onpointerenter = null;
    red.onclick = e => {   // tap anywhere on the original: it plays from that moment
      const r = red.getBoundingClientRect(), t = Math.max(0, Math.min(MAP.dur || W.original.duration, (e.clientX - r.left) / r.width * (MAP.dur || W.original.duration)));
      const k = origs.find(x => W.segs[x].start <= t && (W.segs[x].end == null || t < W.segs[x].end)) || origs[0];
      ri.seg = k; ri.at = Math.round(t); ri.label = "Original at " + Math.floor(t / 60) + ":" + String(Math.floor(t % 60)).padStart(2, "0");
      if (e.pointerType === "mouse" || e.detail === 0 || MAP.pick === red) mapGo(red); else tipFor(red, true);
    };
    layMap(); window.addEventListener("resize", layMap);
    el.querySelector(".tip button").onclick = () => { if (MAP.pick) mapGo(MAP.pick); };
    requestAnimationFrame(() => el.classList.add("in"));
  }
  function layMap() {   // positions from the original's duration (the player's own number once the original has loaded)
    if (!MAP) return; document.documentElement.style.setProperty("--map-h", (MAP.el.offsetHeight + 6) + "px");
    const d = origDur(); if (!d) return; MAP.dur = d;
    // one scale for everything, wide enough that the last room fits: lengths stay true relative to the original (K tg:16491)
    const span = Math.max(d, ...MAP.items.filter(i => !i.red).map(i => i.t0 + i.len)) * 1.01; MAP.span = span;
    const x = t => (t / span * 100).toFixed(3) + "%";
    MAP.items.forEach(it => { it.b.style.left = x(it.t0); it.b.style.width = it.red ? x(d) : "calc(" + (it.len / span * 100).toFixed(3) + "% + 2px)"; });
    MAP.el.querySelectorAll(".ins").forEach(m => { m.style.left = x(+m.dataset.t); });
  }
  function tipIdle() { if (!MAP) return; const t = MAP.el.querySelector(".tip"); MAP.pick = null; MAP.items.forEach(i => i.b.classList.remove("pick"));
    t.querySelector(".hint").hidden = false; t.querySelector(".what").hidden = true; t.querySelector("button").hidden = true; }
  function tipFor(b, sticky) {
    const it = MAP.items.find(i => i.b === b), tip = $("#map .tip"); MAP.pick = sticky ? b : null;
    MAP.items.forEach(i => i.b.classList.toggle("pick", sticky && i.b === b));
    tip.querySelector(".hint").hidden = true; const w = tip.querySelector(".what"); w.hidden = false; w.textContent = it.label; tip.querySelector("button").hidden = !sticky;
  }
  function mapGo(b) {
    // During the interruption the player holds the interruption video, and the room comes back by an async cue,
    // so read the room's place from the stopped clock before clearing it, never from the player (Joscha QA of 4aabf1f).
    let was = null; if (ix) { was = here(); if (was) was.t = ix.t; endClock(false); }
    const it = MAP.items.find(i => i.b === b); tipIdle(); b.classList.remove("pick");
    const k = segNode(it.seg); if (!k) return;
    remember(was); const n = W.graph[k]; enter(k, true, n.seq.indexOf(it.seg), it.at != null ? it.at : W.segs[it.seg].start);
  }
  function mapHead() {   // the playhead: on the top line in the original, on its lane inside a room
    if (ix) return;
    if (!MAP || !W.steps || !MAP.dur) { if (MAP && !MAP.dur) layMap(); return; }
    const st = W.steps[idx], seg = node && node.seq[idx], it = MAP.items.find(i => i.seg === seg), hd = MAP.el.querySelector(".head");
    MAP.items.forEach(i => i.b.classList.toggle("on", i === it && !i.red));
    if (!it) { hd.hidden = true; return; }
    let t = st.start || 0; try { if (playingId() === vid(st)) t = player.getCurrentTime(); } catch (e) {}
    MAP.origT = it.lane === 0 ? t : it.t0;   // the red fill shows how far the original has played, and waits at the insert point during a room
    MAP.red.b.querySelector(".fill").style.width = (Math.min(1, MAP.origT / MAP.dur) * 100).toFixed(3) + "%";   // fill is relative to the red bar itself
    const pos = it.lane === 0 ? t : it.t0 + t;
    hd.hidden = false; hd.style.left = (Math.min(1, pos / (MAP.span || MAP.dur)) * 100).toFixed(3) + "%"; hd.style.setProperty("--lane", it.lane);
  }

  // Plain navigation (K tg:16509): the episode as one line a thumb can follow. The original plays in order, one room
  // plays at each pause (the viewer's choice of model, or none), and the row under the player says what is playing now,
  // what plays next, and what else was made at this pause. A Chapters list shows everything and plays any of it.
  // It runs as one node ("plain") in the same player, so Back, the stop-the-clock interruption and the feed work as before.
  // ?nav=paths brings back the routes-and-cards page.
  let PL = null;
  function plainOn() { return !!(W && W.graph && W.segs && window.WEAVE_NAV === "plain" && q.get("nav") !== "paths"); }
  const MODELS = /\b(Opus|Sonnet|Haiku|Fable|Sol|Astra|Gemini|Grok|GPT[-\w.]*)\b/i;
  function mm(sec) { sec = Math.max(0, Math.floor(sec || 0));   // floor, so 1232.55 s reads 20:32 as in the weave file
    return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }
  function segLen(k) { const g = W.segs[k]; return g && g.end != null ? g.end - (g.start || 0) : null; }
  function buildPlain() {
    // Where each segment sits in the original comes from the weave's own graph (the same walk the old map used).
    const origs = Object.keys(W.segs).filter(k => W.segs[k].video === "original").sort((a, b) => W.segs[a].start - W.segs[b].start);
    if (!origs.length) return;
    const guides = new Set(Object.values(W.graph).map(n => n.guide && n.guide.seg).filter(Boolean));
    const at = {}, seen = new Set(), queue = [[W.start, W.segs[origs[0]].start]];
    while (queue.length) {
      const [nid, c0] = queue.shift(), key = nid + "@" + c0; if (seen.has(key) || !W.graph[nid]) continue; seen.add(key);
      let c = c0; const n = W.graph[nid];
      n.seq.forEach(k => { const g = W.segs[k]; if (!g) return; if (g.video === "original") { c = g.end != null ? g.end : c; return; } if (at[k] == null) at[k] = c; });
      [n.next, ...(n.choices || []).map(x => x.next)].filter(Boolean).forEach(nx => queue.push([nx, c]));
    }
    const spots = origs.map(k => W.segs[k].end).filter(e => e != null);
    // A room that no route card leads to can still join the line: its segment says where it pauses ("at", original seconds).
    Object.keys(W.segs).forEach(k => { const a = W.segs[k].at; if (a != null && at[k] == null) at[k] = a; });
    const rooms = {}, comps = {}, models = [];
    Object.keys(at).forEach(k => {
      const g = W.segs[k], sp = at[k]; if (!spots.includes(sp) || g.end == null || guides.has(k) || /describe the choices/i.test(g.label || "")) return;
      // a shared room ("always"): plays on every model's line (the four-way at Matt's close); not a model choice of its own
      if (g.always) { (rooms[sp] = rooms[sp] || []).push({ seg: k, model: g.room || "Shared", notes: true, always: true }); return; }
      const m = ((g.label || "").match(MODELS) || [])[1];
      if (m && /^Pause/i.test(g.label || "")) {
        const name = m.charAt(0).toUpperCase() + m.slice(1);
        (rooms[sp] = rooms[sp] || []).push({ seg: k, model: name, notes: !/without/i.test(g.label) });
        if (!models.includes(name)) models.push(name);
      } else (comps[sp] = comps[sp] || []).push(k);
    });
    const endNode = Object.values(W.graph).find(n => n.seq.includes(origs[origs.length - 1]) && !n.choices?.length);
    const cards = Object.keys(W.segs).filter(k => /^End card/i.test(W.segs[k].label || ""));
    let pref = models[0] || "original"; try { const p = localStorage.getItem("weave-pref-" + id); if (p && (p === "original" || models.includes(p))) pref = p; } catch (e) {}
    PL = { origs, spots, rooms, comps, models, cards, pref, pins: {}, extras: new Set(), line: [] };
    W.graph.plain = { seq: [] }; plainLine();
    const el = document.createElement("div"); el.id = "plain";
    el.innerHTML = '<div class="row">' +
      '<button type="button" id="back" disabled title="Back to what was playing before your last jump">◀ Back</button>' +
      '<div class="now"><span class="k">Now</span><b class="t"></b><span class="left"></span><span class="prog"><i></i></span></div>' +
      '<div class="next"><span class="k">Next</span><span class="t"></span><button type="button" class="chg">change</button></div>' +
      '<button type="button" class="chap" aria-haspopup="dialog">☰ Chapters</button></div>' +
      '<div class="pick" hidden><span class="k">Play at the next pause:</span><span class="chips"></span></div>' +
      '<div class="also" hidden><span class="k">Also at this pause:</span><span class="chips"></span></div>';
    document.body.appendChild(el); document.body.classList.add("hasmap", "plain");
    el.querySelector("#back").onclick = back;
    el.querySelector(".chap").onclick = () => chapters(false);
    el.querySelector(".chg").onclick = () => upNext();
    const sheet = document.createElement("div"); sheet.id = "chapters"; sheet.hidden = true; sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-label", "Chapters");
    sheet.innerHTML = '<div class="panel"><div class="hd"><b>Chapters</b><button type="button" class="x" aria-label="Close">✕</button></div>' +
      '<div class="pref"><span>At each pause play:</span><span class="opts"></span>' +
      '<small class="note">Starts at the next pause. The room playing now keeps playing.</small>' +
      '<small class="key"><i class="dot anthropic"></i>Claude (Anthropic) <i class="dot other"></i>OpenAI or another lab <i class="dot house"></i>Harmony &amp; Joscha, the house AI seats</small></div><ol class="list"></ol></div>';
    document.body.appendChild(sheet);
    sheet.onclick = e => { if (e.target === sheet) closeChapters(); };
    sheet.querySelector(".x").onclick = closeChapters;
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !sheet.hidden) closeChapters(); });
    const fit = () => document.documentElement.style.setProperty("--map-h", (el.offsetHeight + 6) + "px");
    fit(); window.addEventListener("resize", fit); new ResizeObserver(fit).observe(el);
  }
  function upNext() {   // the pause we are heading to: choose which room plays there, without leaving what is playing
    const el = $("#plain"), box = el.querySelector(".pick"), chips = box.querySelector(".chips");
    if (!box.hidden) { box.hidden = true; return; }
    const seg = W.graph.plain.seq[idx], sp = W.segs[seg].end; if (W.segs[seg].video !== "original" || sp == null) return;
    chips.textContent = ""; const cur = pickRoom(sp);
    [...(PL.rooms[sp] || []).map(r => r.seg), null].forEach(k => {
      const b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.setAttribute("aria-pressed", String(k === cur));
      if (k) { b.append(dot(k), roomName(roomOf(k)[1]) + " · " + mm(segLen(k))); } else b.append("No room, keep watching");
      b.onclick = () => { if (k) PL.pins[sp] = k; else PL.pins[sp] = "none"; plKey = ""; plainLine(); box.hidden = true; };
      chips.appendChild(b);
    });
    box.hidden = false; const f = chips.querySelector('[aria-pressed="true"]') || chips.firstChild; if (f) f.focus();
  }
  function roomName(r) { return r.model + " room" + (r.notes ? "" : " · without house notes"); }
  function roomOf(seg) { for (const sp of PL.spots) { const r = (PL.rooms[sp] || []).find(x => x.seg === seg); if (r) return [sp, r]; } return [null, null]; }
  function spotOf(seg) { const [sp] = roomOf(seg); if (sp != null) return sp; return PL.spots.find(s => (PL.comps[s] || []).includes(seg)); }
  function pickRoom(sp) {   // the room that plays at a pause: a pinned one, else the preferred model (with the house notes when there are two)
    if (PL.pins[sp]) return PL.pins[sp] === "none" ? null : PL.pins[sp];
    const rs = PL.rooms[sp] || []; if (PL.pref === "original" || !rs.length) return null;
    const shared = rs.find(x => x.always); if (shared) return shared.seg;
    // no room on that model here (Fable and Astra stop at 40:33): fall back to the same lab's room
    const lab = m => /^(Opus|Sonnet|Haiku|Fable)$/.test(m) ? "anthropic" : "other";
    const mine = rs.filter(r => r.model === PL.pref), kin = rs.filter(r => lab(r.model) === lab(PL.pref));
    const r = mine.find(x => x.notes) || mine[0] || kin.find(x => x.notes) || kin[0] || rs.find(x => x.notes) || rs[0];
    return r ? r.seg : null;
  }
  function plainLine() {   // rebuild the line; the step that is playing keeps its place and its media time
    const line = [];
    PL.origs.forEach((o, i) => {
      line.push(o); const sp = W.segs[o].end; if (sp == null) return;
      const r = pickRoom(sp); if (r) line.push(r);
      (PL.comps[sp] || []).forEach(c => { if (PL.extras.has(c)) line.push(c); });
    });
    const last = line[line.length - 1], r45 = pickRoom(PL.spots[PL.spots.length - 1]);
    // the end card of the last room on the line that has one (a shared four-way at the very end has none of its own here)
    const owner = [...line].reverse().find(k => PL.cards.some(c => W.segs[c].video === W.segs[k].video));
    const card = r45 && owner ? PL.cards.find(c => W.segs[c].video === W.segs[owner].video) : null;   // no room with an end card on the line: no end card
    if (card && W.segs[last].end == null) line.push(card);
    PL.line = line;
    const cur = node === W.graph.plain && W.steps ? W.graph.plain.seq[idx] : null;
    W.graph.plain.seq = line;
    if (cur && node === W.graph.plain) { W.steps = line.map(k => W.segs[k]); const i = line.indexOf(cur); if (i >= 0) idx = i; }
    if ($("#chapters") && !$("#chapters").hidden) fillChapters();
  }
  function plainGo(seg, t, autoplay) {   // play one segment of the line (making it part of the line first if it was not)
    const sp = spotOf(seg);
    PL.pins = {}; PL.extras.clear();   // a one-off pick is for that pause only; later pauses follow the viewer's choice
    if (sp != null) { if (roomOf(seg)[1]) PL.pins[sp] = seg; else PL.extras.add(seg); }
    plainLine(); const i = PL.line.indexOf(seg); if (i < 0) return;
    enter("plain", autoplay, i, t != null ? t : W.segs[seg].start);
  }
  function plainPick(seg) {   // a tap in Chapters or on a chip: remember where we were (the stopped clock if interrupted), then go
    let was = null; if (ix) { was = here(); if (was) was.t = ix.t; endClock(false); }
    remember(was); closeChapters(); plainGo(seg, null, true);
  }
  function plainPref(p) {
    PL.pref = p; try { localStorage.setItem("weave-pref-" + id, p); } catch (e) {}
    const cur = node === W.graph.plain ? W.graph.plain.seq[idx] : null, [csp, r] = cur ? roomOf(cur) : [null, null];
    PL.pins = {}; if (r) PL.pins[csp] = cur;   // the room playing now stays; later pauses follow the new choice
    plKey = ""; plainLine(); fillChapters();
  }
  function label(seg) {
    const g = W.segs[seg]; const [sp, r] = roomOf(seg);
    if (r) return "Pause at " + mm(sp) + " · " + roomName(r);
    if (g.video === "original") return "Original episode · " + mm(g.start) + (g.end != null ? "–" + mm(g.end) : " to the end");
    if (/^End card/i.test(g.label || "")) return "End card";
    return (g.label || seg).split(";")[0];
  }
  function dot(seg) {   // ivory ring = the original; orange/blue = a room on an Anthropic / other model; violet = the house's own clips
    const s = document.createElement("i"); s.className = "dot " + (W.segs[seg].video === "original" ? "orig" : W.segs[seg].always ? "house" : roomOf(seg)[1] ? hostOf(seg) : "house");   /* shared four-way spans both labs: house dot */ s.setAttribute("aria-hidden", "true"); return s; }
  let plKey = "";
  function plainFrame() {
    const el = $("#plain"); if (!el || !PL || node !== W.graph.plain || !W.steps) return;
    if (ix) return;
    const seg = W.graph.plain.seq[idx], st = W.steps[idx]; if (!st) return;
    let t = st.start || 0, playing = false; try { if (playingId() === vid(st)) { t = player.getCurrentTime(); playing = true; } } catch (e) {}
    let end = st.end; if (end == null) { try { if (playing) end = player.getDuration(); } catch (e) {} }
    const len = end != null ? end - (st.start || 0) : 0, pos = Math.max(0, t - (st.start || 0)), rem = end != null ? Math.max(0, end - t) : null;
    el.querySelector(".now .prog i").style.width = (len > 0 ? Math.min(100, pos / len * 100) : 0).toFixed(2) + "%";
    const orig = W.segs[seg].video === "original", od = W.original.duration || origDur();   // the episode's own length, never the current video's
    el.querySelector(".now .left").textContent = !playing ? "" : orig ? mm(t) + " / " + mm(od) + " in episode" : rem != null ? mm(rem) + " left" : "";
    const nx = W.graph.plain.seq[idx + 1], key = seg + "|" + nx + "|" + PL.pref + "|" + hist.length;
    const nt = el.querySelector(".next .t"), inTxt = nx && rem != null && playing ? " · in " + mm(rem) : "";
    if (key === plKey) { const tn = nt.querySelector(".in"); if (tn) tn.textContent = inTxt; return; }
    if (plKey.split("|")[0] !== seg) el.querySelector(".pick").hidden = true; plKey = key;
    const nowT = el.querySelector(".now .t"); nowT.textContent = ""; nowT.append(dot(seg), label(seg));
    nt.textContent = "";
    if (nx) nt.append(dot(nx), label(nx)); else nt.append("The end");
    const towardPause = W.segs[seg].video === "original" && W.segs[seg].end != null;
    el.querySelector(".chg").hidden = !towardPause;
    if (towardPause && W.segs[nx] && W.segs[nx].video === "original") { nt.textContent = ""; nt.append(dot(nx), "No room at " + mm(W.segs[seg].end) + ", the original carries on"); }
    { const s = document.createElement("span"); s.className = "in"; s.textContent = inTxt; nt.appendChild(s); }
    const bk = el.querySelector("#back"), top = hist[hist.length - 1];   // Back says where it goes
    if (top && top.node === "plain") { const [, r] = roomOf(top.seg); const to = r ? roomName(r) : W.segs[top.seg].video === "original" ? "Original " + mm(top.t) : "previous clip";
      bk.innerHTML = "◀ Back<small></small>"; bk.querySelector("small").textContent = to; bk.setAttribute("aria-label", "Back to " + to); }
    else { bk.textContent = "◀ Back"; bk.removeAttribute("aria-label"); }
    const sp = spotOf(seg), also = el.querySelector(".also"), chips = also.querySelector(".chips"); chips.textContent = "";
    if (sp != null && W.segs[seg].video !== "original") {
      [...(PL.rooms[sp] || []).map(r => r.seg), ...(PL.comps[sp] || [])].filter(k => k !== seg).forEach(k => {
        const b = document.createElement("button"); b.type = "button"; b.className = "chip";
        const [, r] = roomOf(k), n = r ? roomName(r) : (W.segs[k].label || k).split(";")[0].replace(/^Harmony and Joscha on /, "Harmony & Joscha on ");
        b.append(dot(k), n + " · " + mm(segLen(k))); b.onclick = () => plainPick(k); chips.appendChild(b);
      });
      also.hidden = !chips.children.length;
    } else also.hidden = true;
  }
  function chapters(prefFirst) {
    const sh = $("#chapters"); fillChapters(); sh.hidden = false;
    const f = prefFirst ? sh.querySelector(".opts button") : (sh.querySelector('.list [aria-current="true"]') || sh.querySelector(".x"));
    if (f) { f.focus({ preventScroll: true }); f.scrollIntoView({ block: "center" }); }
  }
  function closeChapters() { const sh = $("#chapters"); if (sh && !sh.hidden) { sh.hidden = true; const c = $("#plain .chap"); if (c) c.focus({ preventScroll: true }); } }
  function fillChapters() {
    const sh = $("#chapters"); if (!sh || !PL) return;
    const opts = sh.querySelector(".opts"); opts.textContent = "";
    [...PL.models, "original"].forEach(m => {
      const b = document.createElement("button"); b.type = "button"; b.setAttribute("aria-pressed", String(PL.pref === m));
      b.textContent = m === "original" ? "Original only" : m; b.onclick = () => plainPref(m); opts.appendChild(b);
    });
    const list = sh.querySelector(".list"); list.textContent = ""; const cur = node === W.graph.plain ? W.graph.plain.seq[idx] : null;
    const item = (seg, text, sub) => {
      const li = document.createElement("li"), b = document.createElement("button"); b.type = "button"; b.className = "ch";
      b.append(dot(seg)); const t = document.createElement("span"); t.className = "t"; t.textContent = text; b.appendChild(t);
      if (sub) { const s = document.createElement("small"); s.textContent = sub; b.appendChild(s); }
      if (seg === cur) { b.setAttribute("aria-current", "true"); li.classList.add("cur"); }
      b.onclick = () => plainPick(seg); li.appendChild(b); return li;
    };
    PL.origs.forEach(o => {
      const g = W.segs[o]; list.appendChild(item(o, "Original episode", mm(g.start) + (g.end != null ? "–" + mm(g.end) : " to the end")));
      const sp = g.end; if (sp == null || (!PL.rooms[sp] && !PL.comps[sp])) return;
      const li = document.createElement("li"); li.className = "pause"; const h = document.createElement("div"); h.className = "ph"; h.textContent = "⏸ Pause at " + mm(sp); li.appendChild(h);
      const ul = document.createElement("ul"); const pick = pickRoom(sp);
      (PL.rooms[sp] || []).forEach(r => ul.appendChild(item(r.seg, roomName(r), mm(segLen(r.seg)) + (r.seg === pick ? " · plays" : ""))));
      (PL.comps[sp] || []).forEach(c => ul.appendChild(item(c, (W.segs[c].label || c).split(";")[0].replace(/^Harmony and Joscha on /, "Harmony & Joscha on "), mm(segLen(c)))));
      if ((PL.rooms[sp] || []).some(r => !r.notes)) { const n = document.createElement("small"); n.className = "pn"; n.textContent = "House notes: notes from Harmony and Joscha that some rooms read before they started."; li.appendChild(n); }
      li.appendChild(ul); list.appendChild(li);
    });
    const card = PL.line.find(k => PL.cards.includes(k)); if (card) list.appendChild(item(card, "End card", ""));
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
      if (ix) endClock(false);   // the interruption pointed here: it has done its job, the room stays paused where it stopped
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
      if (W.paths && W.paths.length && !plainOn()) {   // other routes through the same woven grid (a route is what plays, not what each pause read)
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
      const ixFile = W.graph ? fetch(base + "interrupts/" + encodeURIComponent(id) + ".json").then(r => r.ok ? r.json() : null).catch(() => null) : Promise.resolve(null);
      return Promise.all([W.reactions ? fetch(base + W.reactions).then(r => r.ok ? r.json() : null).catch(() => null) : null, ixFile]).then(([rx, ixc]) => {
        R = rx; IX = ixc && ixc.lines && ixc.audio ? ixc : null;
        if (IX) { const f = ixFreq(); let seen = false; try { seen = localStorage.getItem("weave-ix-" + id) === "1"; } catch (e) {} ixFired = f === "off" || (f === "first" && seen); }
        buildBar(); if (plainOn()) buildPlain(); else buildMap(); start();
      });
    }).catch(err => { $("#about").innerHTML = "<b>" + err.message + "</b>"; });
    function start() {
      player = new YT.Player("player", {
        width: "100%", height: "100%",
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1, controls: 1, cc_load_policy: 0, origin: location.origin },
        events: { onReady: () => { if (W.graph) { const c = document.createElement("div"); c.id = "choices"; c.hidden = true; document.body.appendChild(c); if (PL) plainGo(PL.line[0], null, false); else enter(W.start, false); } else load(0, false); }, onStateChange: onState }
      });
      setInterval(tick, 200);
      window.__weave = { player: () => player, step: () => idx, node: () => node, skip: () => { if (W.graph && node) { idx = W.steps.length - 1; nodeEnd(); } }, go: id => enter(id, true), jump: i => load(i, true),
                         upcoming: () => upcoming(), fmt: r => fmtClock(r),   // test aids: end the node, enter a node, jump to a step, read the event label, format a countdown
                         hist: () => hist.slice(), back: () => back(), ix: () => ix && { t: ix.t, video: ix.video, line: ix.line }, ixFired: () => ixFired,
                         stopClock: () => stopClock(player.getCurrentTime()), endClock: () => endClock(true), map: () => MAP && MAP.items.map(i => i.seg), mapGo: seg => { const it = MAP && MAP.items.find(i => i.seg === seg); if (it) mapGo(it.b); },
                         plain: () => PL && { seq: W.graph.plain.seq.slice(), pref: PL.pref, pins: Object.assign({}, PL.pins), extras: [...PL.extras] }, chapter: seg => plainPick(seg), setPref: p => plainPref(p) };
    }
  };
})();
