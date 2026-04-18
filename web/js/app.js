/* Jarvis PWA — main application controller.
 *
 * Wires together storage, API, voice, and UI. State is kept minimal:
 * a single session id (created on first send), a running WebSocket,
 * a Speaker for TTS, and the set of DOM nodes we touch most often.
 */
(function () {
  "use strict";

  const { load, update } = window.JarvisConfig;
  const { Speaker, Recognizer, WakeWord } = window.JarvisVoice;

  let cfg = load();
  let api = new window.JarvisAPI(cfg);
  let sock = null;
  let sessionId = cfg.sessionId || "";
  let activeTurn = false;
  let speaker = null;
  let wake = null;

  const $ = (id) => document.getElementById(id);
  const chat = $("chat");
  const input = $("composer-input");
  const sendBtn = $("send-btn");
  const micBtn = $("mic-btn");
  const interruptBtn = $("interrupt-btn");
  const dot = $("connection-dot");
  const connText = $("connection-text");
  const approvalBanner = $("approval-banner");

  // Settings elements
  const settingsBtn = $("settings-btn");
  const settingsPanel = $("settings-panel");
  const settingsClose = $("settings-close");

  init();

  function init() {
    speaker = new Speaker();
    speaker.setRate((cfg.speechRate || 180) / 180);
    populateSettings();
    bindSettings();
    bindChrome();
    connect();
    loadHistory();
    registerServiceWorker();
    if (cfg.wakeWord) startWakeWord();
  }

  function connect() {
    if (sock) { sock.close(); sock = null; }
    if (!cfg.apiKey) { setStatus("err", "set API key in settings"); return; }
    setStatus("busy", "connecting…");
    sock = new window.JarvisSocket(api, {
      ready: () => setStatus("ok", "online"),
      close: () => setStatus("err", "disconnected"),
      error: () => setStatus("err", "error"),
      session: (m) => { sessionId = m.id; update({ sessionId }); },
      token: (m) => { appendToken(m.text || (m.data && m.data.text) || ""); },
      tool_call_start: (m) => appendSystem(`→ ${m.name}(${shortArgs(m.arguments)})`),
      tool_call_end: (m) => appendSystem(`${m.ok ? "✓" : "✗"} ${m.name}${m.error ? ": " + m.error : ""}`),
      approval_request: (m) => showApproval(m),
      approval_resolved: (m) => {
        hideApproval(m.tool);
        appendSystem(`approval for ${m.tool}: ${m.approved ? "granted" : "denied"} (${m.reason || ""})`);
      },
      message: (m) => {
        if (m.role === "tool") appendToolMessage(m.name, m.content);
      },
      error: (m) => appendSystem(`⚠ ${m.message || "error"}`),
      done: () => finishTurn(),
      scheduler_fired: (m) => {
        pushNotification(m.title || "Reminder", m.message || "");
        appendSystem(`⏰ ${m.title}: ${m.message || ""}`);
      },
      dispatch_stdout: (m) => appendSystem(`⟶ ${m.line || ""}`),
      dispatch_state: (m) => appendSystem(`claude-code: ${m.state}`),
    });
    sock.connect();
  }

  async function loadHistory() {
    if (!sessionId) return;
    try {
      const { messages } = await api.listMessages(sessionId);
      chat.innerHTML = "";
      for (const m of messages) appendMessage(m.role, m.content, { toolName: m.name });
    } catch (_) {
      // Session probably gone; reset.
      sessionId = "";
      update({ sessionId: "" });
    }
  }

  function bindChrome() {
    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
      autosize();
    });
    input.addEventListener("input", autosize);
    micBtn.addEventListener("click", toggleMic);
    interruptBtn.addEventListener("click", interrupt);
    settingsBtn.addEventListener("click", openSettings);
    settingsClose.addEventListener("click", closeSettings);
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  }

  async function send() {
    const text = (input.value || "").trim();
    if (!text || activeTurn) return;
    appendMessage("user", text);
    input.value = "";
    autosize();
    activeTurn = true;
    interruptBtn.classList.remove("hidden");
    sendBtn.classList.add("hidden");
    createAssistantBubble();
    sock.send({ type: "chat", message: text, session_id: sessionId });
  }

  async function interrupt() {
    if (!activeTurn) return;
    sock.send({ type: "interrupt" });
    if (speaker) speaker.stop();
    appendSystem("interrupted by user");
  }

  function finishTurn() {
    activeTurn = false;
    interruptBtn.classList.add("hidden");
    sendBtn.classList.remove("hidden");
    if (cfg.speak && lastAssistantText) {
      const text = lastAssistantText;
      lastAssistantText = "";
      speaker.setRate((cfg.speechRate || 180) / 180);
      if (cfg.voice && cfg.voice !== "auto") speaker.setVoice(cfg.voice);
      speaker.speak(text).catch(() => {});
    }
  }

  let lastAssistantBubble = null;
  let lastAssistantText = "";

  function createAssistantBubble() {
    lastAssistantBubble = appendMessage("assistant", "");
    lastAssistantText = "";
  }

  function appendToken(text) {
    if (!text) return;
    if (!lastAssistantBubble) createAssistantBubble();
    const body = lastAssistantBubble.querySelector(".msg-body");
    body.textContent += text;
    lastAssistantText += text;
    scrollToBottom();
  }

  function appendMessage(role, content, opts = {}) {
    const tpl = document.getElementById("message-template");
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.classList.add(role);
    node.querySelector(".role").textContent = opts.toolName ? `tool · ${opts.toolName}` : role;
    node.querySelector("time").textContent = timeString(new Date());
    node.querySelector(".msg-body").textContent = content;
    chat.appendChild(node);
    scrollToBottom();
    return node;
  }

  function appendToolMessage(name, content) {
    appendMessage("tool", content, { toolName: name });
  }

  function appendSystem(text) {
    appendMessage("system", text);
  }

  function scrollToBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  function setStatus(kind, text) {
    dot.className = "dot " + kind;
    connText.textContent = text;
  }

  function shortArgs(args) {
    if (!args) return "";
    let s;
    try { s = JSON.stringify(args); } catch { s = String(args); }
    return s.length > 80 ? s.slice(0, 80) + "…" : s;
  }

  function timeString(d) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // ---------------- voice ----------------
  let listening = false;
  let recognizer = null;

  function toggleMic() {
    if (listening) return stopListening();
    startListening();
  }

  function startListening() {
    recognizer = new Recognizer();
    if (!recognizer.supported) {
      appendSystem("speech recognition not supported on this browser");
      return;
    }
    if (activeTurn && speaker) { speaker.stop(); sock.send({ type: "interrupt" }); }
    micBtn.classList.add("listening");
    micBtn.setAttribute("aria-pressed", "true");
    listening = true;
    recognizer.on("partial", (text) => { input.value = text; autosize(); });
    recognizer.on("final", (text) => {
      stopListening();
      input.value = text;
      autosize();
      if (text) send();
    });
    recognizer.on("error", (e) => {
      stopListening();
      appendSystem("speech error: " + (e && e.error ? e.error : "unknown"));
    });
    try { recognizer.start(); } catch (exc) { stopListening(); }
  }

  function stopListening() {
    if (!listening) return;
    listening = false;
    micBtn.classList.remove("listening");
    micBtn.setAttribute("aria-pressed", "false");
    if (recognizer) recognizer.stop();
  }

  function startWakeWord() {
    if (wake) wake.stop();
    wake = new WakeWord("jarvis");
    if (!wake.supported) return;
    wake.start(() => {
      if (!listening) startListening();
    });
  }

  // ---------------- approvals ----------------
  const pendingApprovals = new Map();

  function showApproval(assessment) {
    const tpl = document.getElementById("approval-template");
    const card = tpl.content.firstElementChild.cloneNode(true);
    card.querySelector(".tool").textContent = assessment.tool;
    card.querySelector(".args").textContent = JSON.stringify(assessment.arguments, null, 2);
    card.querySelector(".rationale").textContent = assessment.rationale || "";
    const risk = card.querySelector(".risk");
    risk.textContent = assessment.overall;
    risk.className = "risk " + assessment.overall;

    // We don't know the approval id here unless the server attached one;
    // the `approvals` topic on the bus ships the `id`. Pair via a timed
    // lookup on the pending list.
    let approvalId = null;
    api.fetch = api.fetch || (async () => {});
    fetchPendingApproval(assessment.tool).then((id) => { approvalId = id; });

    const resolve = (decision) => {
      if (!approvalId) {
        fetchPendingApproval(assessment.tool).then((id) => {
          approvalId = id;
          if (id) api.resolveApproval(id, decision);
        });
      } else {
        api.resolveApproval(approvalId, decision);
      }
      card.remove();
      if (!approvalBanner.querySelector(".approval-card")) approvalBanner.classList.add("hidden");
    };

    card.querySelector(".approve").addEventListener("click", () => resolve("approved_once"));
    card.querySelector(".approve-session").addEventListener("click", () => resolve("approved_session"));
    card.querySelector(".approve-always").addEventListener("click", () => resolve("approved_always"));
    card.querySelector(".deny").addEventListener("click", () => resolve("denied"));

    approvalBanner.appendChild(card);
    approvalBanner.classList.remove("hidden");
    pendingApprovals.set(assessment.tool, card);
  }

  function hideApproval(tool) {
    const card = pendingApprovals.get(tool);
    if (card) {
      card.remove();
      pendingApprovals.delete(tool);
    }
    if (!approvalBanner.querySelector(".approval-card")) approvalBanner.classList.add("hidden");
  }

  async function fetchPendingApproval(tool) {
    try {
      const r = await fetch(`${api.baseUrl}/v1/approvals/pending`, { headers: api.headers });
      if (!r.ok) return null;
      const data = await r.json();
      const hit = (data.pending || []).find((p) => p.assessment && p.assessment.tool === tool);
      return hit ? hit.id : null;
    } catch (_) {
      return null;
    }
  }

  // ---------------- settings ----------------
  function openSettings() {
    settingsPanel.classList.remove("hidden");
    loadJobs();
    populateVoices();
  }
  function closeSettings() {
    settingsPanel.classList.add("hidden");
  }

  function populateSettings() {
    $("cfg-url").value = cfg.url || location.origin;
    $("cfg-key").value = cfg.apiKey || "";
    $("cfg-name").value = cfg.name || "";
    $("cfg-address").value = cfg.address || "sir";
    $("cfg-humor").value = cfg.humor ?? 2;
    $("cfg-humor-val").textContent = cfg.humor ?? 2;
    $("cfg-verbosity").value = cfg.verbosity || "concise";
    $("cfg-rate").value = cfg.speechRate || 180;
    $("cfg-rate-val").textContent = cfg.speechRate || 180;
    $("cfg-speak").checked = cfg.speak !== false;
    $("cfg-wake").checked = !!cfg.wakeWord;
    $("cfg-humor").addEventListener("input", (e) => $("cfg-humor-val").textContent = e.target.value);
    $("cfg-rate").addEventListener("input", (e) => $("cfg-rate-val").textContent = e.target.value);
  }

  function populateVoices() {
    const sel = $("cfg-voice");
    sel.innerHTML = "<option value='auto'>auto</option>";
    const voices = speaker.listVoices();
    for (const v of voices) {
      const opt = document.createElement("option");
      opt.value = v.name;
      opt.textContent = `${v.name} (${v.lang})`;
      if (cfg.voice === v.name) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => {
      cfg = update({ voice: sel.value });
      speaker.setVoice(sel.value);
    });
  }

  function bindSettings() {
    $("settings-save").addEventListener("click", async () => {
      cfg = update({
        url: $("cfg-url").value.trim() || location.origin,
        apiKey: $("cfg-key").value.trim(),
        name: $("cfg-name").value.trim(),
        address: $("cfg-address").value.trim() || "sir",
        humor: Number($("cfg-humor").value),
        verbosity: $("cfg-verbosity").value,
        speechRate: Number($("cfg-rate").value),
        speak: $("cfg-speak").checked,
        wakeWord: $("cfg-wake").checked,
      });
      api = new window.JarvisAPI(cfg);
      try {
        await api.patchProfile({
          name: cfg.name,
          preferred_address: cfg.address,
          humor_level: cfg.humor,
          verbosity: cfg.verbosity,
          speech_rate: cfg.speechRate,
        });
        $("settings-status").textContent = "Saved.";
      } catch (exc) {
        $("settings-status").textContent = "Saved locally (server patch failed: " + exc.message + ")";
      }
      if (cfg.wakeWord) startWakeWord(); else if (wake) wake.stop();
      connect();
      closeSettings();
    });

    $("settings-test").addEventListener("click", async () => {
      cfg = update({
        url: $("cfg-url").value.trim() || location.origin,
        apiKey: $("cfg-key").value.trim(),
      });
      api = new window.JarvisAPI(cfg);
      try {
        const info = await api.runtimeInfo();
        $("settings-status").textContent = `OK — ${info.llm.provider}/${info.llm.model}`;
      } catch (exc) {
        $("settings-status").textContent = "Error: " + exc.message;
      }
    });
  }

  async function loadJobs() {
    const list = $("jobs-list");
    list.innerHTML = "<p class='muted'>loading…</p>";
    try {
      const jobs = await api.listJobs();
      list.innerHTML = "";
      if (!jobs.length) {
        list.innerHTML = "<p class='muted'>No scheduled jobs yet.</p>";
        return;
      }
      for (const j of jobs) {
        const node = document.createElement("div");
        node.className = "job";
        const when = j.cron ? `cron: ${j.cron}` : j.every_seconds ? `every ${j.every_seconds}s` : j.at_timestamp ? new Date(j.at_timestamp * 1000).toLocaleString() : "";
        node.innerHTML = `
          <div>
            <div><strong>${escape(j.title)}</strong> <span class="muted">(${j.kind})</span></div>
            <div class="when">${escape(when)}</div>
          </div>
          <button data-id="${j.id}">✕</button>
        `;
        node.querySelector("button").addEventListener("click", async (e) => {
          await api.deleteJob(e.target.dataset.id);
          loadJobs();
        });
        list.appendChild(node);
      }
    } catch (exc) {
      list.innerHTML = `<p class='muted'>Error loading jobs: ${escape(exc.message)}</p>`;
    }
  }

  function escape(s) {
    return (s || "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
  }

  async function pushNotification(title, body) {
    try {
      if (!("Notification" in window)) return;
      if (Notification.permission === "default") {
        await Notification.requestPermission();
      }
      if (Notification.permission === "granted") {
        new Notification(title, { body });
      }
    } catch (_) {}
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch (exc) {
      console.warn("sw registration failed", exc);
    }
  }

  // populate voices again once they're available (Chrome lazy-loads them)
  if ("speechSynthesis" in window) {
    window.speechSynthesis.addEventListener?.("voiceschanged", populateVoices);
  }
})();
