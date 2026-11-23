"use strict";
let desktop,
  S = { settings: {}, catalog: [], status: {}, keys: {}, providers: {} };
let currentPage = "chat",
  active,
  panelTab = "general",
  sidebarOverride = null,
  priorBehavior = null;
let panelFocus = "",
  requestNumber = 0,
  pendingRemoval = null;
const chats = [],
  requests = new Map(),
  nodes = new Map();
const matchModel = (a, b) =>
  a && b && a.provider === b.provider && a.id === b.id;
function defaultModel() {
  const cfg = S.settings;
  const chosen = S.catalog.find(
    (m) => m.provider === cfg.defaultProvider && m.id === cfg.defaultModel,
  );
  if (chosen) return chosen;
  const available = S.catalog.filter(
    (m) => S.keys[m.provider] || S.status[m.provider]?.state === "online",
  );
  return (
    available.find((m) => m.provider === cfg.defaultProvider) ||
    available[0] ||
    null
  );
}
function newChat() {
  const c = {
    title: "New chat",
    model: defaultModel(),
    messages: [],
    draft: "",
    editing: null,
    job: null,
    scroll: null,
  };
  chats.unshift(c);
  selectChat(c);
}
function selectChat(c) {
  if (active && currentPage === "chat") active.scroll = $("scroll").scrollTop;
  active = c;
  currentPage = "chat";
  $("chat").hidden = false;
  $("panel").hidden = true;
  if (innerWidth <= 600) sidebarOverride = true;
  updateSidebar();
  updateHeader();
  renderHistory();
  fullMessages();
  $("prompt").value = c.draft;
  composer();
  autosize();
  $("scroll").scrollTop = c.scroll ?? $("scroll").scrollHeight;
  $("prompt").focus();
  scrollInfo();
}
function renderHistory() {
  $("history").replaceChildren(
    ...chats.map((c) => {
      const b = el(
        "button",
        c === active && currentPage === "chat" ? "active" : "",
      );
      b.append(icon("chat"), el("span", "", c.title));
      b.title = c.title;
      b.onclick = () => selectChat(c);
      return b;
    }),
  );
}
function updateHeader() {
  const names = {
    chat: "Chat",
    connections: "API Connections",
    models: "Model Manager",
    settings: "Settings",
  };
  $("pageName").textContent = names[currentPage];
  document
    .querySelectorAll("[data-page]")
    .forEach((b) =>
      b.classList.toggle("active", b.dataset.page === currentPage),
    );
  for (const id of ["pick", "composerModel"])
    $(id).querySelector("span").textContent =
      active?.model?.name || "Select model";
}
function updateSidebar() {
  const behavior = S.settings.sidebar || "auto";
  if (priorBehavior !== behavior) {
    sidebarOverride = null;
    priorBehavior = behavior;
  }
  $("shell").classList.toggle(
    "collapsed",
    sidebarOverride ??
      (behavior === "collapsed" || (behavior === "auto" && innerWidth < 900)),
  );
  document.body.classList.toggle("no-motion", S.settings.motion === false);
}
function toggleSidebar() {
  sidebarOverride = !$("shell").classList.contains("collapsed");
  updateSidebar();
}
function showPage(page, focus = "") {
  if (page === "chat") {
    selectChat(active);
    return;
  }
  if (currentPage === "chat") active.scroll = $("scroll").scrollTop;
  currentPage = page;
  panelFocus = focus;
  if (innerWidth <= 600) sidebarOverride = true;
  updateSidebar();
  $("chat").hidden = true;
  $("panel").hidden = false;
  updateHeader();
  renderHistory();
  drawPanel(false);
  $("panel").scrollTop = 0;
  if (focus)
    requestAnimationFrame(() => $(focus)?.scrollIntoView({ block: "center" }));
}
function autosize() {
  const p = $("prompt");
  p.style.height = "auto";
  p.style.height = Math.min(p.scrollHeight, 150) + "px";
}
function composer() {
  const busy = !!active.job,
    send = $("send");
  send.disabled = !busy && !$("prompt").value.trim();
  send.classList.toggle("stop", busy);
  send.title = busy ? "Stop generation (Esc)" : "Send message";
  send.setAttribute("aria-label", send.title);
  if (send.dataset.mode !== String(busy)) {
    send.replaceChildren(icon(busy ? "stop" : "up"));
    send.dataset.mode = String(busy);
  }
  $("editbar").hidden = active.editing === null;
  $("editbar").querySelector("span").textContent =
    "Editing replaces the replies that follow.";
}
function renameModel(m) {
  const proposed = window.prompt("Display name for " + m.id + " (API ID stays unchanged):", m.name);
  if (proposed === null) return;
  const name = proposed.trim();
  if (!name) { notice("Enter a model display name."); return; }
  if (name.length > 512) { notice("Model name is too long."); return; }
  desktop.saveModel(m.provider, m.id, name);
}
// A single click on the hover trash icon hides a model from MULTI-AI.
// The server persists the hidden ID; the saved manual name is retained for Undo.
function removeModelDirectly(m) {
  pendingRemoval = { provider: m.provider, id: m.id, name: m.name };
  desktop.removeModel(m.provider, m.id);
}
function restoreModelFromPicker(p, mid) {
  desktop.restoreModel(p, mid);
}
function modelDeleteButton(m) {
  const b = button("", () => removeModelDirectly(m), "icon model-delete", "trash");
  b.title = "Remove " + m.name + " (one click; Undo available)";
  b.setAttribute("aria-label", "Remove " + m.name);
  return b;
}
function removedModelsSection() {
  const hidden = (S.settings.hiddenModels || []);
  if (!hidden.length) return null;
  const section = el("details", "removed-models");
  section.append(el("summary", "", "Removed models (" + hidden.length + ") · restore anytime"));
  for (const [p, mid] of hidden) {
    const row = el("div", "removed-model-row");
    row.append(el("span", "removed-model-name", (S.providers[p] || p) + " · " + mid));
    row.append(button("Restore", () => restoreModelFromPicker(p, mid), "subtle"));
    section.append(row);
  }
  return section;
}
function openPicker() {
  drawChoices();
  $("selector").showModal();
  $("searchModels").focus();
}
function drawChoices() {
  const query = $("searchModels").value.trim().toLowerCase(),
    wrap = $("choices");
  wrap.replaceChildren();
  for (const [p, label] of Object.entries(S.providers)) {
    const rows = S.catalog.filter(
      (m) =>
        m.provider === p &&
        (label + " " + m.name + " " + m.id).toLowerCase().includes(query),
    );
    if (!rows.length && query) continue;
    const head = el("div", "choice-group", label);
    head.append(connection(p));
    wrap.append(head);
    for (const m of rows) {
      const b = el(
        "button",
        "choice" + (matchModel(m, active.model) ? " selected" : ""),
      );
      b.title = m.id;
      b.append(badge(p), el("span", "model-name", m.name));
      if (matchModel(m, active.model)) b.append(el("span", "check", "✓"));
      b.onclick = () => {
        active.model = m;
        updateHeader();
        $("selector").close();
        selectChat(active);
      };
      const line = el("div", "choice-line");
      line.append(b);
      const rename = button("Rename", () => renameModel(m), "subtle choice-rename");
      rename.title = "Change display name; keep API model ID";
      line.append(rename, modelDeleteButton(m));
      wrap.append(line);
    }
    if (!rows.length) {
      const b = button(
        "Set up " + label,
        () => {
          $("selector").close();
          showPage("connections", "card-" + p);
        },
        "subtle",
      );
      wrap.append(b);
    }
  }
  const removed = removedModelsSection();
  if (removed && (!query || (S.settings.hiddenModels || []).some(([p, mid]) =>
    ((S.providers[p] || p) + " " + mid).toLowerCase().includes(query)))) {
    if (query) {
      // Keep searches quick, including the restore list, for large catalogs.
      for (const row of removed.querySelectorAll(".removed-model-row"))
        if (!row.textContent.toLowerCase().includes(query)) row.remove();
    }
    wrap.append(removed);
  }
  if (!wrap.children.length)
    wrap.append(el("p", "empty-list", "No matching models."));
}
function scrollInfo() {
  const s = $("scroll");
  $("jump").hidden = !(
    s.scrollHeight - s.clientHeight - s.scrollTop > 80 &&
    active?.messages.length
  );
}
function nearBottom() {
  const s = $("scroll");
  return s.scrollHeight - s.clientHeight - s.scrollTop < 80;
}
function bottom(smooth = false) {
  $("scroll").scrollTo({
    top: $("scroll").scrollHeight,
    behavior: smooth && S.settings.motion !== false ? "smooth" : "instant",
  });
  scrollInfo();
}
function fullMessages() {
  const retained = new Set(active.messages);
  for (const [message, node] of nodes) {
    if (!retained.has(message)) {
      node.remove();
      nodes.delete(message);
    }
  }
  $("welcome").hidden = !!active.messages.length;
  $("messages").hidden = !active.messages.length;
  active.messages.forEach((m, i) => drawMessage(m, i));
}
function editMessage(i) {
  if (active.job) return;
  active.editing = i;
  active.draft = active.messages[i].content;
  $("prompt").value = active.draft;
  composer();
  autosize();
  $("prompt").focus();
}
function drawMessage(m, i) {
  let node = nodes.get(m);
  if (!node) {
    node = el("article", "msg " + m.role);
    const head = el("div", "msg-head");
    if (m.role === "assistant") {
      const logo = el("img");
      logo.src = "../assets/icon.png";
      logo.alt = "";
      head.append(logo);
    } else head.append(el("span", "avatar", "Y"));
    head.append(el("span", "", m.role === "user" ? "You" : m.name));
    node.append(
      head,
      el("div", "body"),
      el("div", "msg-state"),
      el("div", "actions"),
    );
    $("messages").append(node);
    nodes.set(m, node);
  }
  const body = node.querySelector(".body"),
    status = node.querySelector(".msg-state"),
    actions = node.querySelector(".actions");
  if (node.lastContent !== m.content || node.lastState !== m.state) {
    if (m.role === "user") body.textContent = m.content;
    else if (m.content) markdown(body, m.content, m.state !== "streaming");
    else body.replaceChildren();
    node.lastContent = m.content;
    node.lastState = m.state;
  }
  status.className = "msg-state";
  status.textContent = "";
  if (m.state === "streaming" && !m.content) {
    status.classList.add("pending");
    status.textContent = "Generating…";
  }
  if (m.state === "failed") {
    status.classList.add("error");
    status.textContent = m.error;
  }
  if (m.state === "stopped") status.textContent = "Generation stopped.";
  actions.replaceChildren();
  if (m.content && m.state !== "streaming")
    actions.append(button("Copy", () => copy(m.content), "", "copy"));
  if (m.role === "user" && !active.job)
    actions.append(button("Edit", () => editMessage(i), "", "edit"));
  if (
    m.role === "assistant" &&
    !active.job &&
    i === active.messages.length - 1
  ) {
    actions.append(
      button(
        m.state === "failed" ? "Retry" : "Regenerate",
        () => retry(i),
        "",
        "retry",
      ),
    );
  }
}
function ensureModel() {
  if (active.model && S.catalog.some((m) => matchModel(m, active.model)))
    return true;
  openPicker();
  return false;
}
function send() {
  if (active.job) {
    desktop.stop(active.job);
    return;
  }
  const content = $("prompt").value.trim();
  if (!content || !ensureModel()) return;
  if (active.editing !== null) active.messages.splice(active.editing);
  active.editing = null;
  active.messages.push({ role: "user", content });
  active.draft = "";
  $("prompt").value = "";
  autosize();
  startRequest();
}
function retry(i) {
  if (active.job || !ensureModel()) return;
  active.messages.splice(i);
  active.editing = null;
  startRequest();
}
function startRequest() {
  const c = active,
    m = c.model,
    token = "r" + ++requestNumber;
  const history = c.messages
    .filter((row) => row.content && row.state !== "failed")
    .map(({ role, content }) => ({ role, content }));
  const reply = {
    role: "assistant",
    content: "",
    name: m.name,
    state: "streaming",
  };
  c.messages.push(reply);
  c.job = token;
  c.title = c.messages[0].content.replace(/\s+/g, " ").slice(0, 52);
  requests.set(token, { chat: c, reply, timer: null });
  fullMessages();
  renderHistory();
  composer();
  bottom();
  desktop.generate(
    token,
    JSON.stringify({ provider: m.provider, id: m.id, messages: history }),
  );
}
function receive(raw) {
  const e = JSON.parse(raw);
  if (e.type === "state") {
    S = e;
    // Show a one-click Undo only after the backend confirms the removal.
    if (pendingRemoval && (S.settings.hiddenModels || []).some(
      ([p, id]) => p === pendingRemoval.provider && id === pendingRemoval.id)) {
      const removed = pendingRemoval;
      pendingRemoval = null;
      noticeUndo(removed.name + " removed from MULTI-AI.", () => {
        desktop.restoreModel(removed.provider, removed.id);
        notice(removed.name + " restored.");
      });
    }
    $("shell").inert = false;
    if (!active) {
      newChat();
    }
    for (const chat of chats) {
      const updated = S.catalog.find((m) => matchModel(m, chat.model));
      chat.model = updated || defaultModel();
    }
    updateHeader();
    updateSidebar();
    if ($("selector").open) drawChoices();
    if (currentPage !== "chat") drawPanel(true);
    return;
  }
  if (e.type === "notice") {
    pendingRemoval = null;
    notice(e.message);
    return;
  }
  if (e.type === "providerAdded") {
    notice(e.message);
    if (currentPage === "connections") {
      drawPanel(false);
      $("card-" + e.provider)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    return;
  }
  if (e.type === "preferencesSaved") {
    notice("Settings saved.");
    if (currentPage === "settings") drawPanel(false);
    return;
  }
  if (e.type === "modelSaved") {
    notice(e.message);
    if (currentPage === "models") drawPanel(false);
    return;
  }
  const job = requests.get(e.token);
  if (!job) return;
  const { chat, reply } = job;
  function paint() {
    job.timer = null;
    if (active !== chat || currentPage !== "chat") return;
    const follow = nearBottom();
    drawMessage(reply, chat.messages.indexOf(reply));
    if (follow) bottom();
    else scrollInfo();
  }
  if (e.type === "chunk") {
    reply.content += e.text;
    if (!job.timer && active === chat && currentPage === "chat")
      job.timer = setTimeout(
        paint,
        Math.min(350, 70 + reply.content.length / 250),
      );
    return;
  }
  clearTimeout(job.timer);
  reply.state = e.type;
  reply.error = e.message || "";
  chat.job = null;
  requests.delete(e.token);
  paint();
  if (active === chat && currentPage === "chat") {
    const follow = nearBottom();
    // Editing is available again on all preceding user messages.
    chat.messages.forEach((row, i) => {
      if (row.role === "user") drawMessage(row, i);
    });
    composer();
    if (follow) bottom();
    else scrollInfo();
  }
}
$("new").onclick = newChat;
$("pick").onclick = $("composerModel").onclick = openPicker;
$("searchModels").oninput = drawChoices;
$("closePick").onclick = () => $("selector").close();
$("selector").addEventListener("close", () => {
  $("searchModels").value = "";
  // Restore the notification to the normal page when the modal closes.
  document.body.append($("toast"));
});
$("custom").onclick = () => {
  $("selector").close();
  showPage("models", "add-model");
};
$("cloudQuick").onclick = () => showPage("connections");
$("localQuick").onclick = () => showPage("connections", "card-lmstudio");
$("jump").onclick = () => bottom(true);
$("scroll").onscroll = scrollInfo;
$("cancelEdit").onclick = () => {
  active.editing = null;
  active.draft = "";
  $("prompt").value = "";
  autosize();
  composer();
};
$("send").onclick = send;
$("prompt").oninput = () => {
  active.draft = $("prompt").value;
  autosize();
  composer();
};
$("prompt").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!active.job) send();
  }
};
document
  .querySelectorAll("[data-page]")
  .forEach((b) => (b.onclick = () => showPage(b.dataset.page)));
document
  .querySelectorAll(".expand,.collapse")
  .forEach((b) => (b.onclick = toggleSidebar));
window.addEventListener("resize", () => {
  updateSidebar();
  autosize();
  scrollInfo();
});
document.addEventListener("keydown", (e) => {
  if (!active) return;
  if (e.ctrlKey && !e.altKey) {
    const k = e.key.toLowerCase();
    if (["n", "b", "k", ","].includes(k)) {
      e.preventDefault();
      if ($("selector").open) $("selector").close();
      if (k === "n") newChat();
      else if (k === "b") toggleSidebar();
      else if (k === "k") openPicker();
      else showPage("settings");
    }
  } else if (
    e.key === "Escape" &&
    !$("selector").open &&
    active.job &&
    currentPage === "chat"
  )
    desktop.stop(active.job);
});
window.addEventListener("DOMContentLoaded", () => {
  new QWebChannel(qt.webChannelTransport, (ch) => {
    desktop = ch.objects.desktop;
    desktop.event.connect(receive);
    desktop.ready();
  });
});
