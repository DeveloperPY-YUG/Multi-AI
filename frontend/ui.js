"use strict";
const $ = (id) => document.getElementById(id);
const marks = {
  xai: "𝕏",
  groq: "G",
  google: "✦",
  anthropic: "A",
  qwen: "Q",
  lmstudio: "L",
  ollama: "O",
};
const paths = {
  panel: "M3 5h18v14H3z M9 5v14",
  plus: "M12 5v14 M5 12h14",
  layers: "m3 8 9-5 9 5-9 5z M3 12l9 5 9-5 M3 16l9 5 9-5",
  plug: "m8 3 3 3m2-8 M14 5l3 3 M5 10l9-7 M7 8l6 6-3 3a4 4 0 0 1-6-6l3-3 M4 17l-2 3",
  settings: "M4 6h7m5 0h4M4 12h2m5 0h9M4 18h9m5 0h2 M11 3v6m-5 0v6m7 0v6",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  clock: "M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0 M12 7v5l3 2",
  chevron: "m7 10 5 5 5-5",
  arrow: "M6 17 17 6 M7 6h10v10",
  cpu: "M6 6h12v12H6z M9 9h6v6H9z M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3",
  down: "M12 4v15m-6-6 6 6 6-6",
  up: "M12 20V5m-6 6 6-6 6 6",
  x: "m6 6 12 12M18 6 6 18",
  stop: "M7 7h10v10H7z",
  chat: "M4 4h16v13H9l-5 4z",
  copy: "M8 8h12v13H8z M5 16H3V3h12v2",
  edit: "m4 15 11-11 5 5L9 20l-6 1z M13 6l5 5",
  retry: "M3 11a9 9 0 1 1 3 8 M3 4v7h7",
  check: "m4 12 5 5L20 6",
  trash: "M4 6h16 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7m4-7v7",
  back: "M20 12H4m6-6-6 6 6 6",
};
function el(tag, cls = "", text = "") {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
}
function icon(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg"),
    line = document.createElementNS(ns, "path");
  for (const [k, v] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
    class: "ico",
  }))
    svg.setAttribute(k, v);
  line.setAttribute("d", paths[name]);
  svg.append(line);
  return svg;
}
function button(label, fn, cls = "outline", symbol = "") {
  const b = el("button", cls);
  b.type = "button";
  if (symbol) b.append(icon(symbol));
  b.append(document.createTextNode(label));
  b.onclick = fn;
  return b;
}
function badge(p) {
  return el("span", "badge " + p, marks[p] || (S.providers[p] || "AI").charAt(0).toUpperCase());
}
function connection(p) {
  const state = S.status[p]?.state || "idle";
  const text = {
    idle: S.keys[p] ? "Key saved" : "Unchecked",
    online: "Connected",
    checking: "Checking",
    error: "Check needed",
  }[state];
  return el("span", "status " + state, text);
}
let toastTimer;
function showToast(msg, action = null) {
  const box = $("toast");
  // A showModal() dialog sits in the browser top layer. Place Undo inside it
  // so the button is clickable even while the model selector stays open.
  const selector = $("selector");
  if (selector?.open) selector.append(box);
  else document.body.append(box);
  box.replaceChildren(el("span", "", msg));
  if (action) {
    const undo = button("Undo", () => {
      clearTimeout(toastTimer);
      action();
    }, "toast-undo");
    undo.setAttribute("aria-label", "Undo removing this model");
    box.append(undo);
  }
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.hidden = true), action ? 8000 : 4000);
}
function notice(msg) { showToast(msg); }
function noticeUndo(msg, onUndo) { showToast(msg, onUndo); }
function copy(text) {
  desktop.copyText(text);
  notice("Copied to clipboard.");
}
function escapeText(text) {
  return text.replace(
    /[&<>]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c],
  );
}
marked.use({
  renderer: {
    html(token) {
      return escapeText(token.text);
    },
    image(token) {
      return escapeText(token.text || "Image");
    },
  },
});
function markdown(target, text, finished) {
  let parsed;
  try {
    parsed = marked.parse(text, { gfm: true, async: false });
  } catch {
    target.textContent = text;
    return;
  }
  const fragment = DOMPurify.sanitize(parsed, {
    RETURN_DOM_FRAGMENT: true,
    ALLOWED_TAGS: [
      "p",
      "strong",
      "em",
      "del",
      "code",
      "pre",
      "ul",
      "ol",
      "li",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "a",
      "br",
      "hr",
      "blockquote",
    ],
    ALLOWED_ATTR: ["href", "class", "start"],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
  });
  for (const a of fragment.querySelectorAll("a")) {
    if (!/^https?:\/\//i.test(a.getAttribute("href") || ""))
      a.removeAttribute("href");
    a.setAttribute("rel", "noreferrer noopener");
  }
  for (const code of fragment.querySelectorAll("pre > code")) {
    const raw = code.textContent,
      lang = code.className.match(/language-([\w+#.-]+)/)?.[1] || "text";
    if (finished && raw.length < 150000 && hljs.getLanguage(lang)) {
      code.className = "language-" + lang;
      hljs.highlightElement(code);
    }
    const bar = el("div", "codebar");
    bar.append(
      el("span", "", lang),
      button("Copy code", () => copy(raw), "", "copy"),
    );
    code.parentNode.prepend(bar);
  }
  target.replaceChildren(fragment);
}
document
  .querySelectorAll("[data-icon]")
  .forEach((n) => n.append(icon(n.dataset.icon)));
