// Small dependency-free SVG charts: an interactive donut and horizontal bars.
import { h, fmtKg } from "./dom.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
};

function arc(cx, cy, r, inner, start, end) {
  const large = end - start > Math.PI ? 1 : 0;
  const p = (radius, a) => [cx + radius * Math.sin(a), cy - radius * Math.cos(a)];
  const [x1, y1] = p(r, start), [x2, y2] = p(r, end), [x3, y3] = p(inner, end), [x4, y4] = p(inner, start);
  return `M${x1} ${y1}A${r} ${r} 0 ${large} 1 ${x2} ${y2}L${x3} ${y3}A${inner} ${inner} 0 ${large} 0 ${x4} ${y4}Z`;
}

export function donut(items, { centerLabel = "kg CO₂e", onSelect } = {}) {
  const total = items.reduce((s, d) => s + d.value, 0);
  const box = svg("svg", { viewBox: "0 0 200 200", class: "donut", role: "img",
    "aria-label": "Share of the covered total by category: " + items.map((d) => `${d.label} ${Math.round(d.value / total * 100)}%`).join(", ") });
  const legend = h("ul", { class: "legend" });
  const center = svg("text", { x: 100, y: 98, "text-anchor": "middle", class: "center-num" });
  const sub = svg("text", { x: 100, y: 118, "text-anchor": "middle", class: "center-sub" });
  const reset = () => { center.textContent = fmtKg(total, true); sub.textContent = centerLabel; };
  reset();
  let start = 0;
  const parts = [];
  items.forEach((d, i) => {
    const angle = total > 0 ? (d.value / total) * Math.PI * 2 : 0;
    const end = start + Math.max(angle - (items.length > 1 ? 0.02 : 0), 0.001);
    const path = svg("path", { d: arc(100, 100, 92, 62, start, end), fill: d.color, tabindex: 0, role: "button",
      "aria-label": `${d.label}: ${fmtKg(d.value)}` });
    const item = h("li", { tabindex: 0 },
      h("span", { class: "name" }, h("span", { class: "sw", style: { background: d.color } }), d.label),
      h("span", { class: "val" }, `${fmtKg(d.value)} · ${total ? Math.round(d.value / total * 100) : 0}%`));
    const focus = (on) => {
      path.classList.toggle("active", on); item.classList.toggle("active", on);
      if (on) { center.textContent = fmtKg(d.value, true); sub.textContent = d.label; } else reset();
    };
    for (const el of [path, item]) {
      el.addEventListener("mouseenter", () => focus(true));
      el.addEventListener("mouseleave", () => focus(false));
      el.addEventListener("focus", () => focus(true));
      el.addEventListener("blur", () => focus(false));
      el.addEventListener("click", () => onSelect && onSelect(d.key));
    }
    parts.push(path);
    legend.appendChild(item);
    start += angle;
  });
  parts.forEach((p) => box.appendChild(p));
  box.append(center, sub);
  return h("div", { class: "donut-wrap" }, box, legend);
}

export function bars(items, { tooltipHost } = {}) {
  const max = Math.max(...items.map((d) => d.value), 0) || 1;
  const wrap = h("div", { class: "bars", role: "list" });
  const tip = h("div", { class: "tooltip", hidden: true });
  if (tooltipHost) tooltipHost.appendChild(tip);
  items.forEach((d) => {
    const fill = h("span", { class: "bar-fill", style: { background: d.color } });
    const row = h("div", { class: "bar-row", role: "listitem", tabindex: 0, "aria-label": `${d.label}: ${fmtKg(d.value)}` },
      h("span", { class: "bar-label", title: d.label }, d.label),
      h("span", { class: "bar-track" }, fill),
      h("span", { class: "bar-val" }, fmtKg(d.value)));
    const show = (e) => {
      if (!tooltipHost) return;
      tip.replaceChildren(h("b", {}, d.label), h("br"), `${fmtKg(d.value)} a year`, h("br"), d.detail || "");
      tip.hidden = false;
      const host = tooltipHost.getBoundingClientRect(), r = row.getBoundingClientRect();
      tip.style.left = Math.min(Math.max(8, (e && e.clientX ? e.clientX : r.left + 40) - host.left + 12), host.width - 250) + "px";
      tip.style.top = (r.bottom - host.top + 6) + "px";
    };
    row.addEventListener("mousemove", show);
    row.addEventListener("focus", show);
    row.addEventListener("mouseleave", () => { tip.hidden = true; });
    row.addEventListener("blur", () => { tip.hidden = true; });
    wrap.appendChild(row);
    requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = (d.value / max * 100) + "%"; }));
  });
  return wrap;
}
