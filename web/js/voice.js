/* Browser voice I/O: Web Speech API for STT + SpeechSynthesis for TTS.
 *
 * We keep the TTS utterance split into short sentences so barge-in loses
 * minimal context — if the user taps the mic while Jarvis is speaking,
 * we cancel the current utterance, push the queue to the session history
 * (so we can resume if asked), and start capturing speech.
 */
(function () {
  "use strict";

  const SENTENCE_RE = /(?<=[.!?])\s+|(?<=[:;])\s+|\n+/g;

  function splitForSpeech(text) {
    const cleaned = text
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    return cleaned
      .split(SENTENCE_RE)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  class Speaker {
    constructor() {
      this.synth = window.speechSynthesis;
      this.queue = [];
      this.current = null;
      this.voiceName = "auto";
      this.rate = 1.0;
      this.interrupted = false;
      this._history = [];
    }

    get available() { return !!this.synth; }

    listVoices() {
      return this.synth ? this.synth.getVoices() : [];
    }

    setVoice(name) { this.voiceName = name; }
    setRate(r) { this.rate = r; }

    async speak(text, { onChunk, interruptSignal } = {}) {
      if (!this.available || !text) return 0;
      this.interrupted = false;
      const chunks = splitForSpeech(text);
      const voices = this.listVoices();
      const voice = voices.find((v) => v.name === this.voiceName) || voices.find((v) => /UK|Daniel|British/i.test(v.name)) || null;
      let played = 0;
      for (let i = 0; i < chunks.length; i++) {
        if (this.interrupted || (interruptSignal && interruptSignal.aborted)) break;
        await new Promise((resolve) => {
          const u = new SpeechSynthesisUtterance(chunks[i]);
          if (voice) u.voice = voice;
          u.rate = this.rate;
          u.onend = () => resolve();
          u.onerror = () => resolve();
          this.current = u;
          onChunk && onChunk({ index: i, total: chunks.length, text: chunks[i] });
          this.synth.speak(u);
        });
        played = i + 1;
      }
      this._history.push({ text, chunksPlayed: played, total: chunks.length });
      return played;
    }

    stop() {
      this.interrupted = true;
      if (this.synth) this.synth.cancel();
    }

    lastInterrupted() {
      for (let i = this._history.length - 1; i >= 0; i--) {
        const h = this._history[i];
        if (h.chunksPlayed < h.total) return h;
      }
      return null;
    }
  }

  class Recognizer {
    constructor(lang = "en-US") {
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.supported = !!Ctor;
      if (!this.supported) return;
      this.rec = new Ctor();
      this.rec.lang = lang;
      this.rec.interimResults = true;
      this.rec.continuous = false;
      this._handlers = {};
    }

    on(evt, fn) { this._handlers[evt] = fn; return this; }

    start() {
      if (!this.supported) throw new Error("SpeechRecognition not supported");
      this._final = "";
      this.rec.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) this._final += r[0].transcript;
          else interim += r[0].transcript;
        }
        if (this._handlers.partial) this._handlers.partial(this._final + interim);
      };
      this.rec.onend = () => {
        if (this._handlers.final) this._handlers.final((this._final || "").trim());
      };
      this.rec.onerror = (e) => {
        if (this._handlers.error) this._handlers.error(e);
      };
      this.rec.start();
    }

    stop() {
      try { this.rec.stop(); } catch (_) {}
    }
  }

  /* Very lightweight wake-word detector built on SpeechRecognition.
   * When enabled, it runs continuously, catches the phrase "jarvis",
   * and fires onWake(). Recognition is cheap enough to run when the PWA
   * is in foreground; drop it the moment the user sends a manual turn. */
  class WakeWord {
    constructor(word = "jarvis") {
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.supported = !!Ctor;
      this.word = word.toLowerCase();
      if (!this.supported) return;
      this.rec = new Ctor();
      this.rec.lang = "en-US";
      this.rec.continuous = true;
      this.rec.interimResults = true;
      this.active = false;
    }

    start(onWake) {
      if (!this.supported) return;
      this.active = true;
      this.rec.onresult = (e) => {
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const heard = e.results[i][0].transcript.toLowerCase();
          if (heard.includes(this.word)) {
            this.stop();
            onWake && onWake();
            return;
          }
        }
      };
      this.rec.onend = () => { if (this.active) { try { this.rec.start(); } catch (_) {} } };
      try { this.rec.start(); } catch (_) {}
    }

    stop() {
      this.active = false;
      try { this.rec.stop(); } catch (_) {}
    }
  }

  window.JarvisVoice = { Speaker, Recognizer, WakeWord, splitForSpeech };
})();
