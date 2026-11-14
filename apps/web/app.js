"use strict";

// Tokens remain in this page's memory. Source text is always inserted as text.
let token = null;
let config = null;
let identity = null;
// Every response belongs to the session that initiated it. A network response
// can finish after logout or after another tenant has signed in.
let sessionEpoch = 0;
class StaleSessionError extends Error {}
const currentSession = (epoch) => epoch === sessionEpoch;
function requireSession(epoch) {
  if (!currentSession(epoch)) throw new StaleSessionError("Discarded response from an ended session");
}
function reportError(error, epoch) {
  if (currentSession(epoch) && !(error instanceof StaleSessionError)) status(error.message, true);
}
const byId = (id) => document.getElementById(id);
const text = (tag, value, className) => {
  const element = document.createElement(tag);
  element.textContent = String(value ?? "");
  if (className) element.className = className;
  return element;
};
function status(message, error = false) {
  byId("status").textContent = message;
  byId("status").classList.toggle("error", error);
}
async function api(path, options = {}, epoch = sessionEpoch) {
  requireSession(epoch);
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    credentials: "omit",
    redirect: "error",
  });
  requireSession(epoch);
  const data = await response.json().catch(() => ({}));
  requireSession(epoch);
  if (!response.ok) {
    if (response.status === 401 && token) {
      resetSession();
      status("Session expired. Sign in again.", true);
      throw new StaleSessionError("Session ended");
    }
    throw new Error(typeof data.detail === "string" ? data.detail : `Request unavailable (${response.status}).`);
  }
  return data;
}
function clearContent() {
  byId("documents").replaceChildren(text("p", "Your permitted sources will appear here.", "empty-state"));
  byId("document-count").textContent = "0";
  byId("answer").hidden = true;
  byId("answer-text").textContent = "";
  byId("citations").replaceChildren();
  byId("preview").hidden = true;
  byId("preview-title").textContent = "";
  byId("preview-body").textContent = "";
  byId("history").replaceChildren(text("p", "No history loaded.", "empty-state"));
  byId("metrics").replaceChildren(text("dt", "Sync and policy state"), text("dd", "Sign in to inspect"));
}
function resetSession() {
  sessionEpoch += 1;
  token = null;
  identity = null;
  for (const id of ["question", "search", "admin-document", "admin-user"]) byId(id).value = "";
  clearContent();
  byId("identity").hidden = true;
  byId("identity").replaceChildren();
  byId("login-form").hidden = false;
  byId("logout-button").hidden = true;
  byId("logout-button").disabled = false;
  byId("login-button").disabled = false;
  byId("admin-panel").hidden = true;
  byId("session-state").textContent = "No active session";
  for (const id of ["ask-button", "search-button", "refresh-button"]) byId(id).disabled = true;
}
function identityView(me) {
  identity = me;
  const list = byId("identity");
  list.replaceChildren();
  const properties = { Identity: me.sub, Tenant: me.tenant, Groups: (me.groups || []).join(", ") || "None", Scopes: Array.isArray(me.scopes) ? me.scopes.join(", ") : me.scopes, Role: me.admin ? "Tenant administrator" : me.actor_type };
  for (const [key, value] of Object.entries(properties)) list.append(text("dt", key), text("dd", value));
  list.hidden = false;
  byId("login-form").hidden = true;
  byId("logout-button").hidden = false;
  byId("admin-panel").hidden = !me.admin;
  byId("session-state").textContent = `${me.tenant} · ${me.actor_type}`;
  for (const id of ["ask-button", "search-button", "refresh-button"]) byId(id).disabled = false;
}
async function previewDocument(id, version) {
  const epoch = sessionEpoch;
  try {
    const document = await api(version ? `/citations/${encodeURIComponent(id)}/${encodeURIComponent(version)}` : `/documents/${encodeURIComponent(id)}`, {}, epoch);
    requireSession(epoch);
    byId("preview-title").textContent = document.title;
    byId("preview-body").textContent = document.body ?? document.quote ?? document.text ?? "No preview content.";
    byId("preview").hidden = false;
    byId("admin-document").value = id;
    byId("preview").scrollIntoView({ behavior: "smooth", block: "nearest" });
    status("Source access verified for this request.");
  } catch (error) {
    if (!currentSession(epoch)) return;
    byId("preview").hidden = true;
    byId("preview-body").textContent = "";
    reportError(error, epoch);
  }
}
function renderDocuments(documents) {
  byId("document-count").textContent = String(documents.length);
  byId("documents").replaceChildren();
  if (!documents.length) byId("documents").append(text("p", "No accessible matching sources.", "empty-state"));
  for (const document of documents) {
    const card = text("article", "", "document-card");
    const button = text("button", document.title);
    button.type = "button";
    button.addEventListener("click", () => previewDocument(document.id));
    const meta = text("div", "", "document-meta");
    meta.append(text("span", `SOURCE VERSION ${document.version}`), text("span", "ACCESS CHECKED"));
    card.append(button, text("p", document.snippet || "Open to inspect this source."), meta);
    byId("documents").append(card);
  }
}
function renderAnswer(answer) {
  byId("answer-text").textContent = answer.answer;
  byId("citations").replaceChildren();
  for (const [index, citation] of (answer.citations || []).entries()) {
    const entry = text("div", "", "citation");
    const button = text("button", `[${index + 1}] ${citation.title} · version ${citation.version}`);
    button.type = "button";
    button.addEventListener("click", () => previewDocument(citation.document_id, citation.version));
    entry.append(button, text("blockquote", citation.quote));
    byId("citations").append(entry);
  }
  byId("answer").hidden = false;
}
async function loadDashboard(epoch = sessionEpoch) {
  const data = await api("/dashboard", {}, epoch);
  requireSession(epoch);
  byId("metrics").replaceChildren();
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === "object" && value !== null) continue;
    byId("metrics").append(text("dt", key.replaceAll("_", " ")), text("dd", value));
  }
}
async function loadHistory(epoch = sessionEpoch) {
  const data = await api("/history", {}, epoch);
  requireSession(epoch);
  byId("history").replaceChildren();
  if (!(data.messages || []).length) byId("history").append(text("p", "No accessible questions yet.", "empty-state"));
  for (const message of (data.messages || []).slice(-4).reverse()) {
    const entry = text("div", "", "history-item");
    const button = text("button", message.question || message.answer?.slice(0, 80) || `Response ${message.id}`);
    button.type = "button";
    button.addEventListener("click", async () => {
      const historyEpoch = sessionEpoch;
      byId("answer").hidden = true;
      try {
        const answer = await api(`/history/${encodeURIComponent(message.id)}`, {}, historyEpoch);
        requireSession(historyEpoch);
        renderAnswer(answer);
        status("Saved response revalidated against current access.");
      } catch (error) { reportError(error, historyEpoch); }
    });
    entry.append(button);
    byId("history").append(entry);
  }
}
async function refresh(epoch = sessionEpoch) {
  requireSession(epoch);
  // Clear visible content first: a failed access recheck must not retain stale text.
  clearContent();
  const documents = await api("/documents", {}, epoch);
  requireSession(epoch);
  renderDocuments(documents.documents || []);
  await loadDashboard(epoch);
  await loadHistory(epoch);
}
async function completeLogin(accessToken, epoch = sessionEpoch) {
  requireSession(epoch);
  token = accessToken;
  try {
    const me = await api("/auth/me", {}, epoch);
    requireSession(epoch);
    identityView(me);
    await refresh(epoch);
    requireSession(epoch);
    status("Session ready. You can search only the sources you currently have permission to read.");
  } catch (error) {
    if (currentSession(epoch)) { resetSession(); status("Sign-in could not complete. Try again.", true); }
    throw error;
  }
}
const base64url = (bytes) => btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
async function startOidc(epoch = sessionEpoch) {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = base64url(crypto.getRandomValues(new Uint8Array(24)));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
  requireSession(epoch);
  sessionStorage.setItem("p091-pkce", JSON.stringify({ verifier, state, created: Date.now() }));
  const url = new URL(`${config.oidc_issuer}/protocol/openid-connect/auth`);
  const redirectUri = config.redirect_uri || `${location.origin}/`;
  url.search = new URLSearchParams({ client_id: config.oidc_client_id || "p091-web", redirect_uri: redirectUri, response_type: "code", scope: "openid read admin", state, code_challenge: challenge, code_challenge_method: "S256" });
  location.assign(url);
}
async function finishOidc() {
  const epoch = sessionEpoch;
  const params = new URLSearchParams(location.search);
  if (!params.has("code") && !params.has("error")) return;
  const pending = JSON.parse(sessionStorage.getItem("p091-pkce") || "null");
  sessionStorage.removeItem("p091-pkce");
  history.replaceState(null, "", "/");
  if (params.has("error")) throw new Error("Identity provider did not complete sign-in.");
  if (!pending || pending.state !== params.get("state") || Date.now() - pending.created > 300000) throw new Error("Sign-in state is invalid or expired.");
  const response = await fetch(`${config.oidc_issuer}/protocol/openid-connect/token`, {
    method: "POST", credentials: "omit", redirect: "error", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "authorization_code", client_id: config.oidc_client_id || "p091-web", redirect_uri: config.redirect_uri || `${location.origin}/`, code: params.get("code"), code_verifier: pending.verifier }),
  });
  requireSession(epoch);
  if (!response.ok) throw new Error("Identity provider token exchange failed.");
  const result = await response.json();
  requireSession(epoch);
  await completeLogin(result.access_token, epoch);
}
byId("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const epoch = sessionEpoch;
  byId("login-button").disabled = true;
  try {
    if (config.mode === "live") { await startOidc(epoch); return; }
    const data = await api("/lab/login", { method: "POST", body: JSON.stringify({ user_id: byId("user-select").value }) }, epoch);
    requireSession(epoch);
    await completeLogin(data.access_token, epoch);
  } catch (error) { reportError(error, epoch); }
  finally { if (currentSession(epoch)) byId("login-button").disabled = false; }
});
byId("logout-button").addEventListener("click", async () => {
  const epoch = sessionEpoch;
  byId("logout-button").disabled = true;
  try { await api("/auth/logout", { method: "POST" }, epoch); }
  catch (error) { reportError(error, epoch); }
  finally { if (currentSession(epoch)) {
    resetSession();
    status("Signed out of this application.");
    if (config.mode === "live" && config.logout_url) location.assign(config.logout_url);
  } }
});
byId("ask-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const epoch = sessionEpoch;
  byId("ask-button").disabled = true;
  byId("answer").hidden = true;
  byId("answer-text").textContent = "";
  byId("citations").replaceChildren();
  status("Retrieving accessible sources and checking citations…");
  try {
    const answer = await api("/chat", { method: "POST", body: JSON.stringify({ question: byId("question").value }) }, epoch);
    requireSession(epoch);
    renderAnswer(answer);
    status("Response complete. Source text is quoted as data.");
    await loadHistory(epoch);
    await loadDashboard(epoch);
  } catch (error) { reportError(error, epoch); }
  finally { if (currentSession(epoch)) byId("ask-button").disabled = !token; }
});
byId("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const epoch = sessionEpoch;
  byId("documents").replaceChildren();
  try {
    const data = byId("search").value.trim() ? await api("/search", { method: "POST", body: JSON.stringify({ query: byId("search").value }) }, epoch) : await api("/documents", {}, epoch);
    requireSession(epoch);
    renderDocuments(data.documents || []);
    status("Search complete. Every returned source passed its current access check.");
  } catch (error) { reportError(error, epoch); }
});
byId("refresh-button").addEventListener("click", async () => {
  const epoch = sessionEpoch;
  try { await refresh(epoch); requireSession(epoch); status("Sources and history revalidated."); }
  catch (error) { reportError(error, epoch); }
});
byId("close-preview").addEventListener("click", () => { byId("preview").hidden = true; byId("preview-body").textContent = ""; });
byId("admin-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const epoch = sessionEpoch;
  const action = byId("admin-action").value;
  const id = encodeURIComponent(byId("admin-document").value.trim());
  if (action === "delete" && !window.confirm("Delete this synthetic lab document?")) return;
  try {
    await api(`/admin/documents/${id}${action === "delete" ? "" : `/${action}`}`, { method: action === "delete" ? "DELETE" : "POST", ...(["share", "unshare"].includes(action) ? { body: JSON.stringify({ user_id: byId("admin-user").value.trim() }) } : {}) }, epoch);
    await refresh(epoch);
    requireSession(epoch);
    status(`Lab ${action} completed. Current access was rechecked.`);
  } catch (error) { reportError(error, epoch); }
});
(async () => {
  const epoch = sessionEpoch;
  try {
    config = await api("/config", {}, epoch);
    requireSession(epoch);
    byId("mode-badge").textContent = config.mode === "live" ? "LIVE SERVICES · SYNTHETIC DATA" : "OFFLINE · SYNTHETIC DATA";
    if (config.mode === "live") {
      byId("user-select").hidden = true;
      byId("login-form").querySelector("label").textContent = "Human identity via Keycloak";
      byId("login-button").textContent = "Sign in with Keycloak";
      status("Sign in through the local identity provider to begin.");
      await finishOidc();
    }
  } catch (error) { if (currentSession(epoch)) { reportError(error, epoch); byId("login-button").disabled = true; } }
})();
