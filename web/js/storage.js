/* Simple localStorage-backed config with sensible defaults. */
(function () {
  "use strict";

  const KEY = "jarvis.config";
  const DEFAULT = {
    url: location.origin,
    apiKey: "",
    speak: true,
    speechRate: 1.0,
    voice: "auto",
    wakeWord: false,
    name: "",
    address: "sir",
    humor: 2,
    verbosity: "concise",
    sessionId: "",
  };

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return { ...DEFAULT };
      return { ...DEFAULT, ...JSON.parse(raw) };
    } catch (_) {
      return { ...DEFAULT };
    }
  }

  function save(cfg) {
    try {
      localStorage.setItem(KEY, JSON.stringify(cfg));
    } catch (_) {}
  }

  function update(patch) {
    const current = load();
    const next = { ...current, ...patch };
    save(next);
    return next;
  }

  window.JarvisConfig = { load, save, update };
})();
