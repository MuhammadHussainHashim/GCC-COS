// Tiny DOM helpers. Text always goes in through textContent, so data can never run as HTML.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "style" && typeof v === "object") {
      for (const [prop, val] of Object.entries(v)) { if (prop.startsWith("--")) el.style.setProperty(prop, val); else el.style[prop] = val; }
    }
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "hidden") el.hidden = true;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, String(v));
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

const nf0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function fmtKg(kg, short = false) {
  if (kg === null || kg === undefined || Number.isNaN(kg)) return "—";
  if (Math.abs(kg) >= 1000) return (short ? nf2 : nf2).format(kg / 1000) + " t";
  return (Math.abs(kg) >= 10 ? nf0 : nf1).format(kg) + " kg";
}
export const fmtNum = (n, digits = 2) => (n === null || n === undefined ? "—" : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(n));

export const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage may be blocked; the page works without it */ } },
};

export const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
