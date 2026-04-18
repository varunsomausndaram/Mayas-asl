/* HTTP + WebSocket client for the Jarvis backend. */
(function () {
  "use strict";

  class JarvisAPI {
    constructor(cfg) {
      this.baseUrl = (cfg.url || location.origin).replace(/\/$/, "");
      this.apiKey = cfg.apiKey || "";
    }

    get headers() {
      return {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      };
    }

    async health() {
      const r = await fetch(`${this.baseUrl}/healthz`);
      if (!r.ok) throw new Error(`healthz ${r.status}`);
      return r.json();
    }

    async runtimeInfo() {
      const r = await fetch(`${this.baseUrl}/v1/runtime/info`, { headers: this.headers });
      if (!r.ok) throw new Error(`runtime/info ${r.status}`);
      return r.json();
    }

    async createSession(title = "pwa") {
      const r = await fetch(`${this.baseUrl}/v1/sessions`, {
        method: "POST", headers: this.headers, body: JSON.stringify({ title }),
      });
      if (!r.ok) throw new Error(`sessions ${r.status}`);
      return r.json();
    }

    async listMessages(sessionId) {
      const r = await fetch(`${this.baseUrl}/v1/sessions/${sessionId}/messages`, { headers: this.headers });
      if (!r.ok) throw new Error(`messages ${r.status}`);
      return r.json();
    }

    async chat(message, sessionId) {
      const r = await fetch(`${this.baseUrl}/v1/chat`, {
        method: "POST", headers: this.headers,
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      if (!r.ok) throw new Error(`chat ${r.status}`);
      return r.json();
    }

    async interrupt(sessionId) {
      await fetch(`${this.baseUrl}/v1/chat/${sessionId}/interrupt`, {
        method: "POST", headers: this.headers,
      });
    }

    async listJobs() {
      const r = await fetch(`${this.baseUrl}/v1/scheduler/jobs`, { headers: this.headers });
      if (!r.ok) throw new Error(`jobs ${r.status}`);
      return (await r.json()).jobs || [];
    }

    async deleteJob(id) {
      await fetch(`${this.baseUrl}/v1/scheduler/jobs/${id}`, {
        method: "DELETE", headers: this.headers,
      });
    }

    async patchProfile(patch) {
      const r = await fetch(`${this.baseUrl}/v1/profile`, {
        method: "PATCH", headers: this.headers, body: JSON.stringify(patch),
      });
      if (!r.ok) throw new Error(`profile ${r.status}`);
      return r.json();
    }

    async resolveApproval(id, decision) {
      const r = await fetch(`${this.baseUrl}/v1/approvals/${id}`, {
        method: "POST", headers: this.headers, body: JSON.stringify({ decision }),
      });
      if (!r.ok) throw new Error(`approvals ${r.status}`);
      return r.json();
    }

    wsUrl() {
      const u = new URL(this.baseUrl);
      u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
      u.pathname = "/v1/ws";
      return u.toString();
    }
  }

  window.JarvisAPI = JarvisAPI;

  class JarvisSocket {
    constructor(api, handlers) {
      this.api = api;
      this.handlers = handlers || {};
      this.ws = null;
      this._retry = 0;
      this._stop = false;
      this._pingTimer = null;
    }

    connect() {
      this._stop = false;
      this._open();
    }

    _open() {
      try {
        this.ws = new WebSocket(this.api.wsUrl());
      } catch (exc) {
        this._scheduleRetry();
        return;
      }

      this.ws.onopen = () => {
        this._retry = 0;
        this.ws.send(JSON.stringify({ type: "auth", api_key: this.api.apiKey }));
        this._pingTimer = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: "ping", ts: Date.now() }));
          }
        }, 25000);
      };

      this.ws.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch { return; }
        this._emit(data.type || data.kind, data);
      };

      this.ws.onclose = () => {
        if (this._pingTimer) clearInterval(this._pingTimer);
        this._pingTimer = null;
        this._emit("close", {});
        if (!this._stop) this._scheduleRetry();
      };

      this.ws.onerror = () => {
        this._emit("error", {});
      };
    }

    _scheduleRetry() {
      const delay = Math.min(1000 * Math.pow(2, this._retry++), 15000);
      setTimeout(() => { if (!this._stop) this._open(); }, delay);
    }

    send(obj) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(obj));
      }
    }

    close() {
      this._stop = true;
      if (this._pingTimer) clearInterval(this._pingTimer);
      if (this.ws) this.ws.close();
    }

    _emit(type, data) {
      const fn = this.handlers[type] || this.handlers["*"];
      if (fn) fn(data);
    }
  }

  window.JarvisSocket = JarvisSocket;
})();
