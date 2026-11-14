"use strict";

// This provider never contacts a model, hosted judge, or arbitrary target.
module.exports = class LocalSecurityLab {
  id() { return "p091-deterministic-local-api"; }
  async callApi(prompt, context) {
    const base = new URL(process.env.P091_BASE_URL || "http://127.0.0.1:8000");
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname) || base.protocol !== "http:" || base.username || base.password || base.pathname !== "/") {
      return { error: "P091_BASE_URL must be the HTTP root of an owned loopback lab." };
    }
    const request = async (path, body, token) => {
      const response = await fetch(new URL(path, base), {
        method: "POST", redirect: "error", signal: AbortSignal.timeout(10000),
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`Local API ${path} returned ${response.status}`);
      return response.json();
    };
    try {
      const login = await request("/lab/login", { user_id: context.vars.user_id || "nw-employee" });
      const result = await request("/chat", { question: prompt }, login.access_token);
      // Bearer tokens and login responses are deliberately not returned to the evaluator.
      return { output: JSON.stringify(result), metadata: { mode: "extractive", model: "none", sampleCount: 1, synthetic: true } };
    } catch (error) { return { error: error.message }; }
  }
};
