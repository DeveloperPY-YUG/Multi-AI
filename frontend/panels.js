"use strict";
function field(title, node, id) {
  const label = el("label", "field", title);
  node.id = id;
  label.htmlFor = id;
  label.append(node);
  return label;
}
function input(value = "", type = "text") {
  const n = el("input");
  n.type = type;
  n.value = value;
  n.autocomplete = "off";
  return n;
}
function select(options, value) {
  const n = el("select");
  for (const [id, label] of options) {
    const o = el("option", "", label);
    o.value = id;
    n.append(o);
  }
  n.value = value;
  return n;
}
function group(title) {
  const box = el("div", "group");
  if (title) box.append(el("h3", "", title));
  return box;
}
function panelIntro(target, title, summary) {
  target.append(el("h2", "", title), el("p", "intro", summary));
}
function drawPanel(preserve) {
  const target = $("panel"),
    oldValues = new Map(),
    focus = document.activeElement,
    focusId = focus.id;
  const position = target.scrollTop,
    selectionStart =
      focus.tagName === "TEXTAREA" || focus.type === "text"
        ? focus.selectionStart
        : null;
  if (preserve)
    for (const n of target.querySelectorAll("input,select,textarea")) {
      oldValues.set(n.id, n.type === "checkbox" ? n.checked : n.value);
    }
  const content = el("div", "panel-inner");
  content.append(
    button("Back to chat", () => selectChat(active), "subtle back", "back"),
  );
  if (currentPage === "connections") connections(content);
  if (currentPage === "models") modelsPanel(content);
  if (currentPage === "settings") settingsPanel(content);
  target.replaceChildren(content);
  if (preserve) {
    for (const [id, value] of oldValues) {
      const n = $(id);
      if (!n) continue;
      if (n.type === "checkbox") n.checked = value;
      else n.value = value;
      if (id === "default-provider") updateDefaults();
    }
    if ($(focusId)) {
      const n = $(focusId);
      n.focus({ preventScroll: true });
      if (selectionStart !== null)
        n.setSelectionRange(selectionStart, selectionStart);
    }
    target.scrollTop = position;
  }
}
const providerPresets = [
  ["custom-cloud", "Custom cloud API (OpenAI-compatible)"],
  ["custom-local", "Custom local API (OpenAI-compatible)"],
  ["groq", "Groq"],
  ["google", "Google AI Studio / Gemini"],
  ["anthropic", "Anthropic Claude"],
  ["qwen", "Qwen (Alibaba Model Studio)"],
  ["xai", "xAI (Grok)"],
  ["lmstudio", "LM Studio"],
  ["ollama", "Ollama"],
];
const presetUrls = {
  groq: "https://api.groq.com/openai/v1",
  google: "https://generativelanguage.googleapis.com/v1beta",
  anthropic: "https://api.anthropic.com/v1",
  xai: "https://api.x.ai/v1",
  lmstudio: "http://127.0.0.1:1234/v1",
  ollama: "http://127.0.0.1:11434",
};
function addProviderForm(target) {
  const box = group("+ Add AI provider");
  box.id = "add-provider";
  box.append(el("p", "fine", "Add or remove connections here, without changing the project files. Groq is supported directly; custom cloud APIs must be OpenAI-compatible."));
  const form = el("form");
  const available = providerPresets.filter(([id]) => id.startsWith("custom-") || !S.providers[id]);
  const choose = select(available, available[0][0]);
  const name = input();
  const url = input("", "url");
  url.maxLength = 2048;
  const details = el("p", "fine");
  const refresh = () => {
    const id = choose.value;
    const custom = id.startsWith("custom-");
    const needsAddress = custom || id === "qwen";
    name.value = "";
    name.placeholder = custom ? "Provider name (required)" : "Optional display name";
    name.required = custom;
    url.value = needsAddress ? "" : (presetUrls[id] || "");
    url.placeholder = id === "custom-local" ? "http://127.0.0.1:1234/v1"
      : id === "qwen" ? "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
      : "https://api.example.com/v1";
    url.disabled = !needsAddress;
    url.required = needsAddress;
    details.textContent = id === "custom-local" ? "Connect to a server on this computer. No API key required."
      : id === "qwen" ? "Enter the compatible-mode endpoint for your Qwen account and region."
      : id === "custom-cloud" ? "Use an HTTPS endpoint supporting /models and /chat/completions."
      : "This preset uses its official API endpoint.";
  };
  choose.onchange = refresh;
  refresh();
  const grid = el("div", "grid2");
  grid.append(field("Provider type", choose, "provider-template"), field("Display name", name, "provider-name"));
  const save = button("Add provider", null, "primary", "plus");
  save.type = "submit";
  form.onsubmit = (e) => {
    e.preventDefault();
    desktop.addProvider(choose.value, name.value.trim(), url.value.trim());
  };
  form.append(grid, field("API base URL", url, "provider-url"), details, save);
  box.append(form);
  target.append(box);
}
function endpointRow(p) {
  const row = el("div", "endpoint"),
    url = input(S.settings.endpoints[p] || "", "url");
  url.maxLength = 2048;
  if (p === "qwen") url.placeholder = "https://your-provider.example/v1";
  row.append(
    field("API base URL", url, "url-" + p),
    button("Save", () => desktop.saveEndpoint(p, url.value.trim())),
  );
  return row;
}
function probeButton(p) {
  const b = button(
    S.status[p]?.state === "checking" ? "Checking…" : "Test & refresh",
    () => desktop.probe(p),
    "outline", "retry",
  );
  b.disabled = S.status[p]?.state === "checking" || !S.settings.endpoints[p];
  return b;
}
function feedback(p) {
  return el("p", "fine", S.status[p]?.message ||
    (!S.settings.endpoints[p] ? "Enter an API base URL first." :
    S.keys[p] ? "Key securely saved in Windows Credential Manager." :
    S.providerInfo[p]?.local ? "No API key needed for local models." : "Add an API key to connect."));
}
function providerCard(p) {
  const info = S.providerInfo[p],
    box = group(), head = el("div", "group-head");
  box.id = "card-" + p;
  head.append(badge(p), el("h3", "", S.providers[p]), connection(p));
  box.append(head);
  if (info.editable) box.append(endpointRow(p));
  const row = el("div", "button-row");
  if (!info.local) {
    const edit = button(S.keys[p] ? "Manage key" : "Add API key", () => desktop.editKey(p), "primary");
    edit.disabled = !S.settings.endpoints[p];
    row.append(edit);
  }
  row.append(probeButton(p));
  if (!info.local && S.keys[p])
    row.append(button("Delete key", () => desktop.deleteKey(p), "subtle"));
  row.append(button("Remove provider", () => desktop.removeProvider(p), "subtle remove-provider", "trash"));
  box.append(feedback(p), row);
  return box;
}
function connections(target) {
  panelIntro(target, "API Connections", "Manage providers while MULTI-AI is running. Changes are remembered; chats are not.");
  addProviderForm(target);
  const cloud = S.settings.providers.filter((p) => !p.local).map((p) => p.id);
  const local = S.settings.providers.filter((p) => p.local).map((p) => p.id);
  if (cloud.length) target.append(el("h3", "provider-heading", "Cloud providers"));
  for (const p of cloud) target.append(providerCard(p));
  if (local.length) target.append(el("h3", "provider-heading", "Local AI"));
  for (const p of local) target.append(providerCard(p));
}
function modelsPanel(target) {
  panelIntro(
    target,
    "Model Manager",
    "Hover over any model and click the trash icon to remove it immediately. Restore models anytime.",
  );
  const add = group("Add custom model");
  add.id = "add-model";
  const form = el("form"),
    fields = el("div", "grid2"),
    p = select(Object.entries(S.providers), S.settings.defaultProvider);
  const mid = input(),
    name = input();
  mid.required = true;
  mid.maxLength = name.maxLength = 512;
  mid.placeholder = "Exact API identifier";
  name.placeholder = "Optional";
  fields.append(
    field("Provider", p, "new-provider"),
    field("Display name", name, "new-name"),
  );
  const save = button("Save model", null, "primary", "plus");
  save.type = "submit";
  form.onsubmit = (e) => {
    e.preventDefault();
    desktop.saveModel(p.value, mid.value.trim(), name.value.trim());
  };
  form.append(fields, field("Model ID", mid, "new-id"), save);
  add.append(form);
  target.append(add);
  const removed = removedModelsSection();
  if (removed) {
    removed.classList.add("group");
    target.append(removed);
  }
  for (const [provider, label] of Object.entries(S.providers)) {
    const box = group(),
      head = el("div", "group-head");
    head.append(badge(provider), el("h3", "", label), probeButton(provider));
    box.append(head);
    const items = S.catalog.filter((m) => m.provider === provider);
    if (!items.length)
      box.append(
        el("p", "fine", S.status[provider]?.message || "No models listed yet."),
      );
    for (const m of items) {
      const row = el("div", "model-row"),
        info = el("div");
      info.append(
        el("b", "", m.name),
        el(
          "small",
          "",
          m.id + " · " + (m.discovered ? "Listed by provider" : "Manual ID"),
        ),
      );
      row.append(
        info,
        button(
          "Use",
          () => {
            active.model = m;
            selectChat(active);
          },
          "outline",
        ),
      );
      row.append(button("Rename", () => renameModel(m), "subtle"));
      if (!m.saved)
        row.append(button("Save", () => desktop.saveModel(provider, m.id, m.name), "subtle"));
      // Both provider-discovered and manually saved models can be removed.
      row.append(modelDeleteButton(m));
      box.append(row);
    }
    target.append(box);
  }
}
function defaultRows(provider) {
  return [
    ["", "First available model"],
    ...S.catalog
      .filter((m) => m.provider === provider)
      .map((m) => [m.id, m.name]),
  ];
}
function updateDefaults() {
  const n = $("default-model"),
    p = $("default-provider");
  if (!n || !p) return;
  const old = n.value;
  n.replaceChildren(...Array.from(select(defaultRows(p.value), "").options));
  n.value = Array.from(n.options).some((o) => o.value === old) ? old : "";
}
function settingsPanel(target) {
  panelIntro(
    target,
    "Settings",
    "Personalize your workspace and generation defaults.",
  );
  const tabs = el("div", "tabs");
  for (const [id, name] of [
    ["general", "General"],
    ["ai", "AI settings"],
    ["about", "About"],
  ]) {
    tabs.append(
      button(
        name,
        () => {
          panelTab = id;
          drawPanel(false);
        },
        id === panelTab ? "active" : "",
      ),
    );
  }
  target.append(tabs);
  if (panelTab === "about") {
    const box = group(),
      img = el("img", "about-logo");
    img.src = "../assets/icon.png";
    img.alt = "MULTI-AI logo";
    box.classList.add("about");
    box.append(
      img,
      el("h2", "", "MULTI-AI"),
      el("p", "fine", "Version 1.0.0"),
      el("p", "", "Premium Multi-Model AI Desktop Application"),
      el("p", "maker", "MADE BY YUG"),
    );
    target.append(box);
    return;
  }
  const cfg = S.settings,
    form = el("form"),
    box = group(),
    values = {};
  if (panelTab === "general") {
    box.append(el("h3", "", "Appearance"));
    const scale = select(
      [80, 90, 100, 110, 125].map((v) => [String(v), v + "%"]),
      String(cfg.scale),
    );
    const sidebar = select(
      [
        ["auto", "Adapt to window width"],
        ["expanded", "Expanded"],
        ["collapsed", "Collapsed"],
      ],
      cfg.sidebar,
    );
    const theme = el("p", "fine", "Theme · Dark"),
      motion = input("", "checkbox");
    motion.checked = cfg.motion;
    motion.id = "motion";
    const toggle = el("label", "toggle");
    toggle.append(motion, document.createTextNode("Enable animations"));
    box.append(
      theme,
      field("UI scale", scale, "scale"),
      field("Sidebar on launch", sidebar, "sidebar-setting"),
      toggle,
    );
    form.onsubmit = (e) => {
      e.preventDefault();
      desktop.savePreferences(
        JSON.stringify({
          ...cfg,
          scale: Number(scale.value),
          sidebar: sidebar.value,
          motion: motion.checked,
        }),
      );
    };
  } else {
    box.append(el("h3", "", "Generation defaults"));
    const p = select(Object.entries(S.providers), cfg.defaultProvider),
      model = select(defaultRows(cfg.defaultProvider), cfg.defaultModel);
    p.onchange = updateDefaults;
    const sys = el("textarea");
    sys.value = cfg.system;
    sys.maxLength = 32000;
    sys.rows = 4;
    const temp = input(cfg.temperature ?? "", "number");
    temp.step = "0.1";
    temp.min = "0";
    temp.max = "1";
    temp.placeholder = "Provider default";
    const tokens = input(cfg.tokens, "number");
    tokens.min = 1;
    tokens.max = 131072;
    tokens.required = true;
    const timeout = input(cfg.timeout, "number");
    timeout.min = 5;
    timeout.max = 1800;
    timeout.required = true;
    const row = el("div", "grid2");
    row.append(
      field("Default provider", p, "default-provider"),
      field("Default model", model, "default-model"),
    );
    const nums = el("div", "grid2");
    nums.append(
      field("Temperature (if supported)", temp, "temperature"),
      field("Maximum output tokens", tokens, "tokens"),
    );
    box.append(
      row,
      field("System prompt", sys, "system"),
      nums,
      field("Network inactivity timeout (seconds)", timeout, "timeout"),
    );
    form.onsubmit = (e) => {
      e.preventDefault();
      Object.assign(values, {
        defaultProvider: p.value,
        defaultModel: model.value,
        system: sys.value,
        temperature: temp.value === "" ? null : Number(temp.value),
        tokens: Number(tokens.value),
        timeout: Number(timeout.value),
      });
      desktop.savePreferences(JSON.stringify({ ...cfg, ...values }));
    };
  }
  const save = button("Save settings", null, "primary");
  save.type = "submit";
  form.append(box, save);
  target.append(form);
}
