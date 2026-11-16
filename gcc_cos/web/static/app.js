// GCC household footprint calculator: guided steps, review, and an evidence-backed result.
import { h, fmtKg, fmtNum, store, reduceMotion } from "./dom.js";
import { donut, bars } from "./charts.js";

const STEPS = ["Household", "Home energy", "Transport", "Food", "Products", "Review", "Results"];
const CAT_COLOR = { home: "var(--cat-home)", transport: "var(--cat-transport)", food: "var(--cat-food)", products: "var(--cat-products)" };
const CAT_HEX = { home: "#2f7556", transport: "#c58a2c", food: "#8a5aa8", products: "#3c7fb0" };
const LPG_CYLINDER_KG = 11.8; // OGRA notifies LPG prices per 11.8 kg domestic cylinder
const STATUS_BADGE = { calculated: ["ok", "Calculated"], missing_factor: ["bad", "No factor"], unit_mismatch: ["bad", "Unit not covered"],
  geography_mismatch: ["warn", "Other country only"], year_mismatch: ["warn", "Other year only"], boundary_mismatch: ["bad", "Different boundary"],
  duplicate_factor: ["bad", "Duplicate factors"], not_approved: ["warn", "Not approved yet"], invalid_input: ["bad", "Check entry"] };

let catalog = null;
let uid = Date.now();
const fresh = () => ({
  step: 0, maxStep: 0,
  household: { country: "PAK", year: new Date().getFullYear() - 1, people: "" },
  proxies: { geo: false, year: false },
  home: { electricity: { quantity: "", unit: "kWh", period: "month", skip: false },
          natural_gas: { quantity: "", unit: "cubic metres", period: "month", skip: false },
          lpg: { quantity: "", unit: "cylinders", period: "month", skip: false } },
  transport: [], food: [], products: [],
  skip: { transport: false, food: false, products: false },
  result: null,
});
let state = Object.assign(fresh(), store.get("gcc-calculator", {}));
state.result = null;
const save = () => store.set("gcc-calculator", { ...state, result: null });

const $ = (sel) => document.querySelector(sel);
const api = async (path, body) => {
  const res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!res.ok) {
    let msg = `The server answered ${res.status}.`;
    try { const j = await res.json(); msg = j.error || j.detail || msg; if (j.problems) msg += " " + j.problems.map((p) => `${p.field}: ${p.problem}`).join("; "); } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return res;
};
const showAlert = (text) => { const a = $("#alert"); a.textContent = text; a.hidden = !text; };

// ---------- stepper and navigation ----------
function renderStepper() {
  const ol = $("#stepper");
  ol.replaceChildren(...STEPS.map((name, i) => h("li", {}, h("button", {
    type: "button", "aria-current": i === state.step ? "step" : null, class: i < state.step ? "done" : "",
    disabled: i > state.maxStep || (i === 6 && !state.result), onclick: () => go(i),
  }, h("span", { class: "dot" }, i < state.step ? "✓" : String(i + 1)), name))));
  $("#progress-bar").style.width = (state.step / (STEPS.length - 1) * 100) + "%";
  $("#back").disabled = state.step === 0;
  const next = $("#next");
  next.textContent = state.step === 5 ? "Calculate" : state.step === 6 ? "Start again" : "Next";
  $("#nav-note").textContent = state.step < 5 ? "You can skip anything you don't know and come back later." : state.step === 5 ? "Nothing is sent anywhere except this calculator's own server." : "";
}

function go(step) {
  state.step = Math.max(0, Math.min(step, 6));
  state.maxStep = Math.max(state.maxStep, Math.min(state.step, 5));
  document.querySelectorAll(".step").forEach((s) => { s.hidden = Number(s.dataset.step) !== state.step; });
  renderStepper();
  if (state.step === 5) renderReview();
  if (state.step === 6) renderResults();
  save();
  window.scrollTo({ top: 0, behavior: reduceMotion() ? "auto" : "smooth" });
  const heading = document.querySelector(`.step[data-step="${state.step}"] h1`);
  if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
}

// ---------- step 1: household ----------
async function initHousehold() {
  const years = [];
  for (let y = new Date().getFullYear(); y >= 2018; y--) years.push(y);
  $("#year").replaceChildren(...years.map((y) => h("option", { value: y }, y)));
  $("#year").value = state.household.year;
  $("#people").value = state.household.people;
  $("#proxy-geo").checked = state.proxies.geo;
  $("#proxy-year").checked = state.proxies.year;
  try {
    const { countries } = await (await api("/api/v1/countries")).json();
    $("#country").replaceChildren(...countries.map((c) => h("option", { value: c.iso3 }, c.name + (c.electricity_year ? "" : " (no electricity figure)"))));
    $("#country").value = countries.some((c) => c.iso3 === state.household.country) ? state.household.country : (countries[0] || {}).iso3;
  } catch (e) { showAlert("Could not load the country list. " + e.message); }
  $("#country").addEventListener("change", () => { state.household.country = $("#country").value; dataStatus(); save(); });
  $("#year").addEventListener("change", () => { state.household.year = Number($("#year").value); dataStatus(); save(); });
  $("#people").addEventListener("input", () => { state.household.people = $("#people").value; save(); });
  $("#proxy-geo").addEventListener("change", (e) => { state.proxies.geo = e.target.checked; save(); });
  $("#proxy-year").addEventListener("change", (e) => { state.proxies.year = e.target.checked; save(); });
  dataStatus();
}

async function dataStatus() {
  const body = $("#data-status-body");
  try {
    const d = await (await api(`/api/v1/data-status?country=${encodeURIComponent(state.household.country)}&year=${state.household.year}`)).json();
    body.replaceChildren(...d.activities.map((a) => {
      const badges = [];
      if (a.factor_place === "per product") badges.push(h("span", { class: "badge muted" }, "per product"));
      else if (!a.factor_place) badges.push(h("span", { class: "badge bad" }, "no data"));
      else {
        badges.push(h("span", { class: "badge " + (a.same_place ? "ok" : "warn") }, a.same_place ? "your country" : a.factor_place));
        if (a.same_year !== null) badges.push(h("span", { class: "badge " + (a.same_year ? "ok" : "warn") }, a.same_year ? "your year" : a.factor_year));
      }
      if (a.approved === false) badges.push(h("span", { class: "badge warn" }, "not approved"));
      return h("div", { class: "status-item" }, h("div", {}, h("b", {}, a.label), h("div", { class: "line-meta" }, ...badges)));
    }));
  } catch (e) { body.replaceChildren(h("p", { class: "muted" }, "Could not check the data: " + e.message)); }
}

// ---------- form helpers ----------
const field = (label, control, cls = "") => h("label", { class: "field " + cls }, h("span", { class: "inline-label" }, label), control);
function numberInput(obj, key, attrs = {}) {
  return h("input", { type: "number", min: 0, step: "any", inputmode: "decimal", value: obj[key] ?? "", ...attrs,
    oninput: (e) => { obj[key] = e.target.value; e.target.setAttribute("aria-invalid", e.target.value !== "" && !(Number(e.target.value) >= 0)); save(); } });
}
function selectInput(obj, key, options, labels = {}) {
  const s = h("select", { onchange: (e) => { obj[key] = e.target.value; save(); onSelectChange(e); } },
    ...options.map((o) => h("option", { value: o }, labels[o] || o)));
  s.value = obj[key] ?? options[0];
  obj[key] = s.value;
  return s;
}
let onSelectChange = () => {};
const PERIODS = { year: "a year", month: "a month", week: "a week", day: "a day" };

function card(title, category, help, body, onRemove) {
  const el = document.getElementById("tpl-card").content.firstElementChild.cloneNode(true);
  el.style.setProperty("--cat", CAT_COLOR[category]);
  el.querySelector(".card-title").textContent = title;
  el.querySelector(".card-help").textContent = help || "";
  el.querySelector(".card-body").append(...body);
  const rm = el.querySelector(".remove");
  if (onRemove) rm.addEventListener("click", onRemove); else rm.remove();
  return el;
}

// ---------- step 2: home ----------
function renderHome() {
  const units = catalog.activities;
  const blocks = [
    ["electricity", "Electricity", ["kWh"], "Total kWh on your electricity bills."],
    ["natural_gas", "Natural gas", units.natural_gas.units, units.natural_gas.help],
    ["lpg", "LPG", ["cylinders", ...units.lpg.units], "One domestic cylinder is 11.8 kg (the size OGRA prices). " + units.lpg.help],
  ];
  $("#home-cards").replaceChildren(...blocks.map(([key, title, unitList, help]) => {
    const item = state.home[key];
    const skip = h("label", { class: "skip-line" }, h("input", { type: "checkbox", checked: item.skip, onchange: (e) => { item.skip = e.target.checked; save(); renderHome(); } }), "I don't use this or don't know");
    const c = card(title, "home", help, [
      field("Amount", numberInput(item, "quantity", { disabled: item.skip, "aria-label": `${title} amount` })),
      field("Unit", selectInput(item, "unit", unitList, { cylinders: "cylinders (11.8 kg)" })),
      field("Per", selectInput(item, "period", Object.keys(PERIODS), PERIODS)),
      skip]);
    if (item.skip) c.classList.add("skipped");
    return c;
  }));
}

// ---------- step 3: transport ----------
const TRANSPORT_DEFAULTS = {
  car: { options: { size: "Medium", fuel: "Petrol" }, unit: "km", period: "year" },
  motorbike: { options: { size: "Average" }, unit: "km", period: "year" },
  bus: { options: { type: "Average local bus" }, unit: "passenger-km", period: "year" },
  rail: { options: { type: "National rail" }, unit: "passenger-km", period: "year" },
  flight: { options: { haul: "Short-haul, to/from UK", cabin: "Economy class", rf: "With RF" }, unit: "passenger-km", period: "year", mode: "airports", trips: 1, return_trip: true },
};
function addTransport(kind) {
  const d = structuredClone(TRANSPORT_DEFAULTS[kind]);
  state.transport.push({ uid: ++uid, activity: kind, quantity: "", ...d });
  state.skip.transport = false;
  save(); renderTransport();
}
function airportPicker(entry, key, label) {
  const input = h("input", { type: "search", value: entry[key] || "", placeholder: "City or code, e.g. KHI", autocomplete: "off", "aria-label": label });
  const list = h("ul", { class: "results", role: "listbox" });
  let timer;
  input.addEventListener("input", () => {
    entry[key] = input.value.trim().toUpperCase().slice(0, 3); save();
    clearTimeout(timer);
    if (input.value.trim().length < 2) { list.replaceChildren(); return; }
    timer = setTimeout(async () => {
      try {
        const { airports } = await (await api(`/api/v1/airports?q=${encodeURIComponent(input.value.trim())}`)).json();
        list.replaceChildren(...airports.slice(0, 8).map((a) => h("li", { role: "option", tabindex: 0, onclick: () => { entry[key] = a.iata_code; input.value = a.iata_code; list.replaceChildren(); save(); } },
          h("span", {}, `${a.iata_code} · ${a.name}`), h("span", { class: "sub" }, `${a.municipality || ""} ${a.iso_country}`))));
      } catch { list.replaceChildren(); }
    }, 200);
  });
  return h("div", { class: "field search" }, h("span", { class: "inline-label" }, label), input, list);
}
function renderTransport() {
  const A = catalog.activities;
  $("#transport-cards").replaceChildren(...state.transport.map((t) => {
    const a = A[t.activity];
    const remove = () => { state.transport = state.transport.filter((x) => x.uid !== t.uid); save(); renderTransport(); };
    const body = Object.entries(a.options).map(([opt, values]) => field(opt === "rf" ? "Warming at altitude" : opt[0].toUpperCase() + opt.slice(1),
      selectInput(t.options, opt, values, { "With RF": "Include (with RF)", "Without RF": "Exclude (without RF)" })));
    if (t.activity === "flight") {
      body.push(field("Enter by", selectInput(t, "mode", ["airports", "distance"], { airports: "Airports", distance: "Distance" })));
      if (t.mode === "airports") {
        body.push(airportPicker(t, "from_airport", "From"), airportPicker(t, "to_airport", "To"),
          field("Trips a year", numberInput(t, "trips", { min: 1, step: 1 })),
          h("label", { class: "skip-line" }, h("input", { type: "checkbox", checked: t.return_trip, onchange: (e) => { t.return_trip = e.target.checked; save(); } }), "Return trip (counts both ways)"));
      } else {
        body.push(field("Distance flown (passenger-km)", numberInput(t, "quantity")), field("Per", selectInput(t, "period", Object.keys(PERIODS), PERIODS)));
      }
    } else {
      body.push(field("Distance", numberInput(t, "quantity")), field("Unit", selectInput(t, "unit", a.units)), field("Per", selectInput(t, "period", Object.keys(PERIODS), PERIODS)));
    }
    return card(a.label, "transport", a.help, body, remove);
  }));
  onSelectChange = (e) => { if (e.target.closest("#transport-cards") && e.target.value in { airports: 1, distance: 1 }) renderTransport(); };
  if (!state.transport.length) $("#transport-cards").replaceChildren(h("p", { class: "muted" }, "Nothing added yet. Use the buttons above, or skip this step."));
  syncSkip("transport");
}

// ---------- searches (food and products) ----------
function searchBox(input, list, fetcher, render, pick) {
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { list.replaceChildren(); return; }
    timer = setTimeout(async () => {
      try {
        const items = await fetcher(q);
        list.replaceChildren(...(items.length ? items.map((it) => {
          const li = h("li", { role: "option", tabindex: 0 }, ...render(it));
          const choose = () => { pick(it); list.replaceChildren(); input.value = ""; };
          li.addEventListener("click", choose);
          li.addEventListener("keydown", (e) => { if (e.key === "Enter") choose(); });
          return li;
        }) : [h("li", { class: "muted" }, "No match. Try fewer or other words.")]));
      } catch (e) { list.replaceChildren(h("li", {}, "Search failed: " + e.message)); }
    }, 220);
  });
}
function renderFood() {
  $("#food-cards").replaceChildren(...state.food.map((f) => card(f.name, "food", `${f.name_fr} · ${fmtNum(f.value, 3)} kg CO₂e per kg (AGRIBALYSE, France)`, [
    field("Amount (kg)", numberInput(f, "quantity")), field("Per", selectInput(f, "period", Object.keys(PERIODS), PERIODS))],
  () => { state.food = state.food.filter((x) => x.uid !== f.uid); save(); renderFood(); })));
  syncSkip("food");
}
function renderProducts() {
  $("#product-cards").replaceChildren(...state.products.map((p) => card(p.name, "products",
    `${fmtNum(p.value, 2)} ${p.unit} · ${p.status}${p.status === "not approved" ? " (it will be listed but not counted)" : ""}`, [
      field(`Quantity (${p.declared_unit === "item" ? "items" : p.declared_unit})`, numberInput(p, "quantity", { step: 1 }))],
    () => { state.products = state.products.filter((x) => x.uid !== p.uid); save(); renderProducts(); })));
  syncSkip("products");
}
function syncSkip(cat) {
  const box = document.querySelector(`[data-skip="${cat}"]`);
  if (box) box.checked = state.skip[cat];
}

// ---------- request ----------
function buildRequest() {
  const lines = [];
  const home = state.home;
  const add = (line) => lines.push(line);
  if (!home.electricity.skip && home.electricity.quantity !== "") add({ id: "electricity", activity: "electricity", quantity: Number(home.electricity.quantity), unit: "kWh", period: home.electricity.period });
  if (!home.natural_gas.skip && home.natural_gas.quantity !== "") add({ id: "natural_gas", activity: "natural_gas", quantity: Number(home.natural_gas.quantity), unit: home.natural_gas.unit, period: home.natural_gas.period });
  if (!home.lpg.skip && home.lpg.quantity !== "") {
    const cyl = home.lpg.unit === "cylinders";
    add({ id: "lpg", activity: "lpg", quantity: Number(home.lpg.quantity) * (cyl ? LPG_CYLINDER_KG : 1), unit: cyl ? "kg" : home.lpg.unit, period: home.lpg.period });
  }
  if (!state.skip.transport) for (const t of state.transport) {
    const base = { id: `t${t.uid}`, activity: t.activity, options: t.options, unit: t.unit };
    if (t.activity === "flight" && t.mode === "airports") {
      if (t.from_airport && t.to_airport) add({ ...base, unit: "passenger-km", from_airport: t.from_airport, to_airport: t.to_airport, trips: Number(t.trips) || 1, return_trip: !!t.return_trip });
    } else if (t.quantity !== "") add({ ...base, quantity: Number(t.quantity), period: t.period });
  }
  if (!state.skip.food) for (const f of state.food) if (f.quantity !== "") add({ id: `f${f.uid}`, activity: "food", food_code: f.code, quantity: Number(f.quantity), unit: "kg", period: f.period });
  if (!state.skip.products) for (const p of state.products) if (p.quantity !== "") add({ id: `p${p.uid}`, activity: "product", record_id: p.id, quantity: Number(p.quantity), unit: p.declared_unit === "item" ? "items" : p.declared_unit, period: "year" });
  const skipped = [];
  if (["electricity", "natural_gas", "lpg"].every((k) => home[k].skip)) skipped.push("home");
  for (const c of ["transport", "food", "products"]) if (state.skip[c]) skipped.push(c);
  return { household: { country: state.household.country, year: Number(state.household.year), people: state.household.people ? Number(state.household.people) : null },
    proxies: { other_geography: state.proxies.geo, other_year: state.proxies.year }, skipped, lines };
}

// ---------- step 6: review ----------
function renderReview() {
  const req = buildRequest();
  const section = (title, step, items, skipped) => h("section", { class: "review-section" },
    h("header", {}, h("h2", {}, title), h("button", { class: "link-btn", onclick: () => go(step) }, "Change")),
    skipped ? h("p", { class: "muted" }, "Skipped: not included in the result.") :
      items.length ? h("ul", {}, ...items) : h("p", { class: "muted" }, "Nothing entered: this section will show as not covered."));
  const describe = (l) => {
    if (l.from_airport) return `${l.options.cabin}, ${l.from_airport} → ${l.to_airport}${l.return_trip ? " and back" : ""}, ${l.trips} trip(s) a year`;
    const opts = l.options ? Object.values(l.options).join(", ") + ": " : "";
    return `${opts}${fmtNum(l.quantity, 3)} ${l.unit} ${PERIODS[l.period] || ""}`;
  };
  const byAct = (acts) => req.lines.filter((l) => acts.includes(l.activity));
  const country = $("#country").selectedOptions[0]?.textContent || state.household.country;
  $("#review-body").replaceChildren(
    section("Household", 0, [h("li", {}, `${country}, reporting year ${state.household.year}`), h("li", {}, state.household.people ? `${state.household.people} people` : "Household size not given (no per-person figure)"),
      h("li", {}, `Stand-ins: other countries ${state.proxies.geo ? "allowed" : "not allowed"}; other years ${state.proxies.year ? "allowed" : "not allowed"}`)]),
    section("Home energy", 1, byAct(["electricity", "natural_gas", "lpg"]).map((l) => h("li", {}, `${catalog.activities[l.activity].label}: ${describe(l)}${l.activity === "lpg" && state.home.lpg.unit === "cylinders" ? ` (${fmtNum(Number(state.home.lpg.quantity), 2)} cylinders × 11.8 kg)` : ""}`)), req.skipped.includes("home")),
    section("Transport", 2, byAct(["car", "motorbike", "bus", "rail", "flight"]).map((l) => h("li", {}, `${catalog.activities[l.activity].label}: ${describe(l)}`)), state.skip.transport),
    section("Food", 3, byAct(["food"]).map((l) => h("li", {}, `${state.food.find((f) => `f${f.uid}` === l.id)?.name}: ${describe(l)}`)), state.skip.food),
    section("Products", 4, byAct(["product"]).map((l) => h("li", {}, `${state.products.find((p) => `p${p.uid}` === l.id)?.name}: ${fmtNum(l.quantity, 0)} ${l.unit}`)), state.skip.products));
}

async function calculateNow() {
  const next = $("#next");
  next.disabled = true; next.textContent = "Calculating…";
  showAlert("");
  try {
    state.result = await (await api("/api/v1/calculate", buildRequest())).json();
    state.maxStep = 6;
    go(6);
  } catch (e) { showAlert("The calculation failed. " + e.message); }
  finally { next.disabled = false; renderStepper(); }
}

// ---------- step 7: results ----------
function countUp(el, target, suffix) {
  if (reduceMotion() || !target) { el.textContent = fmtNum(target, target >= 100 ? 0 : 2) + suffix; return; }
  const t0 = performance.now(), dur = 900;
  const tick = (t) => {
    const k = Math.min(1, (t - t0) / dur), v = target * (1 - Math.pow(1 - k, 3));
    el.textContent = fmtNum(v, target >= 100 ? 0 : 2) + suffix;
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
async function download(fmt) {
  try {
    const res = await api(`/api/v1/reports/${fmt}`, buildRequest());
    const url = URL.createObjectURL(await res.blob());
    const a = h("a", { href: url, download: `gcc-footprint-${state.household.country}-${state.household.year}.${fmt}` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (e) { showAlert("Download failed. " + e.message); }
}
function renderResults() {
  const r = state.result;
  const root = $("#results-body");
  if (!r) { root.replaceChildren(h("p", {}, "Calculate first.")); return; }
  const t = r.totals, cov = r.coverage;
  const tonnes = (t.covered_kg_co2e || 0) >= 1000;
  const num = h("span", { class: "hero-num" });
  const pct = cov.entries ? Math.round(cov.calculated / cov.entries * 100) : 0;
  const meter = h("span", {});
  const hero = h("div", { class: "hero" },
    h("div", { class: "hero-main" },
      h("span", { class: "hero-label" }, `Footprint of the activities you entered · ${r.household.year}`),
      h("div", {}, num, h("span", { class: "hero-unit" }, tonnes ? "t CO₂e a year" : "kg CO₂e a year")),
      h("span", { class: "hero-sub" }, t.per_person_kg_co2e !== null ? `${fmtKg(t.per_person_kg_co2e)} CO₂e per person a year (${r.household.people} people)` : "Add the number of people for a per-person figure."),
      h("span", { class: "partial-badge" }, "Partial: not a complete carbon footprint")),
    h("div", { class: "coverage" },
      h("h2", {}, "Coverage"),
      h("div", { class: "meter", role: "img", "aria-label": `${cov.calculated} of ${cov.entries} entries calculated` }, meter),
      h("div", { class: "kpis" },
        h("div", { class: "kpi" }, h("b", {}, `${cov.calculated}/${cov.entries}`), h("span", {}, "entries calculated")),
        h("div", { class: "kpi" }, h("b", {}, String(cov.stand_ins)), h("span", {}, "stand-in factors")),
        h("div", { class: "kpi" }, h("b", {}, String(r.categories.filter((c) => c.status === "calculated").length) + "/4"), h("span", {}, "sections fully covered"))),
      h("p", { class: "hint" }, cov.statement)));
  const notices = h("div", { class: "notice" }, h("strong", {}, "Read before using this number"), h("ul", {}, ...r.notices.map((n) => h("li", {}, n))));
  const cats = r.categories.filter((c) => c.kg_co2e);
  const chartCard = h("div", { class: "chart-card" });
  const barsCard = h("div", { class: "chart-card" });
  const calcLines = r.lines.filter((l) => l.status === "calculated" && l.kg_co2e > 0).sort((a, b) => b.kg_co2e - a.kg_co2e);
  chartCard.append(h("h2", {}, "By section"), cats.length ? donut(cats.map((c) => ({ key: c.category, label: c.label, value: c.kg_co2e, color: CAT_HEX[c.category] })),
    { centerLabel: "kg CO₂e a year", onSelect: (key) => document.getElementById(`lines-${key}`)?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth" }) }) : h("p", { class: "muted" }, "Nothing could be calculated."));
  barsCard.append(h("h2", {}, "Biggest entries"), calcLines.length ? bars(calcLines.slice(0, 12).map((l) => ({ label: l.label, value: l.kg_co2e, color: CAT_HEX[l.category],
    detail: `${l.factor.value} ${l.factor.unit} · ${l.factor.geography} ${l.factor.year}${l.proxy.geography || l.proxy.year ? " · stand-in" : ""}` })), { tooltipHost: barsCard }) : h("p", { class: "muted" }, "Nothing to show."));
  const compare = r.comparison ? (() => {
    const mine = r.comparison.your_covered_t_per_person, avg = r.comparison.ghg_per_person_t, max = Math.max(mine, avg) || 1;
    const row = (label, v, color) => h("div", { class: "compare-row" }, h("span", {}, label), h("span", { class: "bar-track" }, h("span", { class: "bar-fill", style: { background: color, width: (v / max * 100) + "%" } })), h("span", { class: "bar-val" }, fmtNum(v, 2) + " t"));
    return h("div", { class: "chart-card" }, h("h2", {}, "For scale"),
      row(t.per_person_kg_co2e !== null ? "Your entries, per person" : "Your entries", mine, CAT_HEX.home),
      row(`Average person, ${r.comparison.country} (${r.comparison.year})`, avg, "#9aa79f"),
      h("p", { class: "hint" }, r.comparison.note + " Source: " + r.comparison.source));
  })() : null;
  const lineEl = (l) => {
    const [kind, text] = STATUS_BADGE[l.status] || ["muted", l.status];
    const f = l.factor || {};
    const meta = [h("span", { class: "badge " + kind }, text)];
    if (l.proxy.geography) meta.push(h("span", { class: "badge warn" }, `stand-in: ${f.geography} factor`));
    if (l.proxy.year) meta.push(h("span", { class: "badge warn" }, `stand-in: ${f.year} factor`));
    if (f.approval) meta.push(h("span", { class: "badge " + (f.approval.level === "independently_reviewed" ? "ok" : "muted") }, f.approval.level === "independently_reviewed" ? "independently reviewed" : "approved for estimation"));
    if (l.annual_quantity !== undefined) meta.push(h("span", {}, `${fmtNum(l.annual_quantity, 2)} ${l.annual_unit} a year`));
    if (l.distance) meta.push(h("span", {}, `${l.distance.from} → ${l.distance.to}: ${fmtNum(l.distance.great_circle_km, 0)} km great-circle`));
    const ev = f.factor_id ? h("details", { class: "evidence" }, h("summary", {}, "Evidence"), h("dl", {},
      ...[["Factor", f.name], ["Value", f.value !== undefined ? `${f.value} ${f.unit}` : null], ["As published", f.value_original !== undefined ? `${f.value_original} ${f.unit_original}` : null],
        ["Place and year", [f.geography, f.year].filter(Boolean).join(", ")], ["Lifecycle boundary", f.boundary], ["Source", f.source_title], ["Publisher", f.publisher],
        ["Licence", f.license], ["Factor id", f.factor_id], ["Approval", f.approval ? f.approval.text : null], ["Limitations", f.source_limitations]]
        .filter(([, v]) => v).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]),
      ...[["Source link", f.source_url], ["Publisher report", f.publisher_report], ["Page", f.page]].filter(([, v]) => v && /^https:\/\//.test(v))
        .flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, h("a", { href: v, target: "_blank", rel: "noopener noreferrer" }, v))]))) : null;
    return h("article", { class: "line" + (l.status === "calculated" ? "" : " fail"), style: { "--cat": CAT_HEX[l.category] || "var(--line)" } },
      h("div", { class: "line-head" }, h("span", { class: "line-title" }, l.label || l.activity), h("span", { class: "line-kg" }, l.kg_co2e !== null ? fmtKg(l.kg_co2e) + " CO₂e" : "not counted")),
      h("div", { class: "line-meta" }, ...meta), l.status === "calculated" ? null : h("p", { class: "hint" }, l.message), ev);
  };
  const lineGroups = r.categories.map((c) => {
    const own = r.lines.filter((l) => l.category === c.category);
    const status = { calculated: "fully calculated", partial: "partly calculated", not_calculated: "nothing could be calculated", skipped: "skipped", not_answered: "nothing entered" }[c.status];
    return h("section", { id: `lines-${c.category}` }, h("h3", {}, `${c.label} · ${status}${c.kg_co2e ? " · " + fmtKg(c.kg_co2e) : ""}`), own.length ? h("div", { class: "lines" }, ...own.map(lineEl)) : null);
  });
  const invalid = r.lines.filter((l) => !l.category);
  const tips = r.recommendations.length ? h("div", { class: "tips" }, ...r.recommendations.map((tip) => h("article", { class: "tip" },
    h("span", { class: "tip-save" }, `−${fmtKg(tip.saving_kg_co2e)}`), h("b", {}, tip.title), h("p", {}, tip.detail)))) : h("p", { class: "muted" }, "No suggestion could be worked out from your entries and the published data.");
  root.replaceChildren(...[
    h("p", { class: "eyebrow" }, "Results"), h("h1", { id: "h-results" }, "Your footprint, as far as the data reaches"),
    hero, notices,
    h("div", { class: "charts" }, chartCard, barsCard), compare,
    h("h2", { class: "section-title" }, "Ways to cut, from the same data"), tips,
    h("h2", { class: "section-title" }, "Every entry, with its evidence"), ...lineGroups, invalid.length ? h("div", { class: "lines" }, ...invalid.map(lineEl)) : null,
    h("h2", { class: "section-title" }, "By lifecycle boundary"),
    h("ul", { class: "boundary-list" }, ...t.by_boundary.map((b) => h("li", {}, `${b.boundary}: ${fmtKg(b.kg_co2e)}`))),
    h("h2", { class: "section-title" }, "Sources and licences"),
    h("ul", { class: "sources" }, ...r.evidence.map((e) => h("li", {}, h("b", {}, e.title || e.dataset_id), ` · ${e.publisher || ""} · ${e.license || ""} · ${e.approval || ""} `,
      e.url && /^https:\/\//.test(e.url.split(" ")[0]) ? h("a", { href: e.url.split(" ")[0], target: "_blank", rel: "noopener noreferrer" }, "source") : null))),
    h("h2", { class: "section-title" }, "Download"),
    h("div", { class: "downloads" }, h("button", { class: "btn ghost", onclick: () => download("html") }, "Report (HTML)"),
      h("button", { class: "btn ghost", onclick: () => download("csv") }, "Entries (CSV)"), h("button", { class: "btn ghost", onclick: () => download("json") }, "Everything (JSON)"))].filter(Boolean));
  countUp(num, tonnes ? t.covered_kg_co2e / 1000 : t.covered_kg_co2e, "");
  requestAnimationFrame(() => requestAnimationFrame(() => { meter.style.width = pct + "%"; }));
}

// ---------- start ----------
async function start() {
  try {
    catalog = await (await api("/api/v1/catalog")).json();
    const health = await (await api("/api/v1/health")).json();
    const pill = $("#data-pill");
    if (health.status === "ok") pill.textContent = `Read-only data · ${health.approved_datasets.length} approved sources`;
    else { pill.textContent = "No database"; pill.classList.add("bad"); showAlert("The GCC database was not found. Load the data first (see docs/CALCULATOR_APP.md)."); }
  } catch (e) { showAlert("The calculator could not reach its server. " + e.message); return; }
  await initHousehold();
  renderHome(); renderTransport(); renderFood(); renderProducts();
  document.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => addTransport(b.dataset.add)));
  document.querySelectorAll("[data-skip]").forEach((b) => b.addEventListener("change", (e) => { state.skip[b.dataset.skip] = e.target.checked; save(); }));
  searchBox($("#food-search"), $("#food-results"), async (q) => (await (await api(`/api/v1/foods?q=${encodeURIComponent(q)}`)).json()).foods,
    (f) => [h("span", {}, f.name_en, h("br"), h("span", { class: "sub" }, f.name_original)), h("span", { class: "val" }, `${fmtNum(Number(f.value_metric), 2)} kg CO₂e/kg`)],
    (f) => { state.food.push({ uid: ++uid, code: f.product_code, name: f.name_en, name_fr: f.name_original, value: Number(f.value_metric), quantity: "", period: "week" }); state.skip.food = false; save(); renderFood(); });
  searchBox($("#product-search"), $("#product-results"), async (q) => (await (await api(`/api/v1/products?q=${encodeURIComponent(q)}`)).json()).products,
    (p) => [h("span", {}, `${p.manufacturer} · ${p.model_and_variant}`, h("br"), h("span", { class: "sub" }, `${p.type || ""} · ${p.status}${p.lifecycle_module ? " · module " + p.lifecycle_module + " only" : ""}`)),
      h("span", { class: "val" }, `${fmtNum(Number(p.value), 1)} ${p.unit}`)],
    (p) => { state.products.push({ uid: ++uid, id: p.id, name: `${p.manufacturer} ${p.model_and_variant}`, value: Number(p.value), unit: p.unit, declared_unit: p.declared_unit, status: p.status, quantity: "1" }); state.skip.products = false; save(); renderProducts(); });
  $("#back").addEventListener("click", () => go(state.step - 1));
  $("#next").addEventListener("click", () => {
    if (state.step === 5) return calculateNow();
    if (state.step === 6) { state = fresh(); save(); location.reload(); return; }
    if (state.step === 0 && !$("#country").value) { showAlert("Choose a country first."); return; }
    showAlert(""); go(state.step + 1);
  });
  go(Math.min(state.step, 5));
}
start();
