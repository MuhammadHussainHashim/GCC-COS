// End-to-end UI check of the GCC calculator. Usage: node tests/ui/calculator_flow.js http://127.0.0.1:8765 [screenshot-dir]
const { chromium } = require("playwright");
const base = process.argv[2];
const shots = process.argv[3];
const fail = (msg) => { console.error("UI FAIL: " + msg); process.exit(1); };
(async () => {
  const browser = await chromium.launch();
  const errors = [];
  for (const [w, label] of [[1280, "desktop"], [390, "phone"]]) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error" && !/fonts\.(googleapis|gstatic)/.test(m.text())) errors.push(m.text()); });
    await page.goto(base + "/");
    await page.waitForSelector("#country option", { state: "attached" });
    await page.selectOption("#country", "PAK");
    await page.selectOption("#year", "2025");
    await page.fill("#people", "4");
    await page.waitForSelector("#data-status-body .status-item");
    await page.check("#proxy-geo", { force: true });
    await page.check("#proxy-year", { force: true });
    if (shots) await page.screenshot({ path: `${shots}/1-household-${label}.png`, fullPage: true });
    await page.click("#next");
    // Home energy
    const amounts = page.locator("#home-cards input[type=number]");
    await amounts.nth(0).fill("250");
    await amounts.nth(2).fill("2");
    await page.locator("#home-cards .skip-line input").nth(1).check();
    if (shots) await page.screenshot({ path: `${shots}/2-home-${label}.png`, fullPage: true });
    await page.click("#next");
    // Transport: a car and a flight by airports
    await page.click("[data-add=car]");
    await page.locator("#transport-cards input[type=number]").first().fill("8000");
    await page.click("[data-add=flight]");
    const flight = page.locator("#transport-cards .card").nth(1);
    await flight.locator("select").nth(0).selectOption("Long-haul, to/from UK");
    await flight.locator("select").nth(1).selectOption("Business class");
    const from = flight.locator("input[type=search]").nth(0);
    await from.fill("KHI");
    await flight.locator(".results li").first().click();
    await flight.locator("input[type=search]").nth(1).fill("LHR");
    await flight.locator(".results li").first().click();
    if (shots) await page.screenshot({ path: `${shots}/3-transport-${label}.png`, fullPage: true });
    await page.click("#next");
    // Food
    await page.fill("#food-search", "rice");
    await page.locator("#food-results li").first().click();
    await page.locator("#food-cards input[type=number]").first().fill("2");
    await page.click("#next");
    // Products
    await page.fill("#product-search", "macbook air m1 256");
    await page.locator("#product-results li").first().click();
    if (shots) await page.screenshot({ path: `${shots}/5-products-${label}.png`, fullPage: true });
    await page.click("#next");
    // Review, go back to correct the car, then calculate
    const review = await page.locator("#review-body").innerText();
    if (!/8,?000 km a year/.test(review)) fail("review does not show the car distance: " + review);
    await page.locator(".review-section").nth(2).locator(".link-btn").click();
    await page.locator("#transport-cards input[type=number]").first().fill("9000");
    for (let i = 0; i < 3; i++) await page.click("#next");
    if (!/9,?000 km a year/.test(await page.locator("#review-body").innerText())) fail("correction not kept");
    if (shots) await page.screenshot({ path: `${shots}/6-review-${label}.png`, fullPage: true });
    await page.click("#next");
    await page.waitForSelector(".hero-num");
    await page.waitForTimeout(1200);
    const text = await page.locator("#results-body").innerText();
    for (const must of ["Partial: not a complete carbon footprint", "Coverage", "Every entry, with its evidence", "Sources and licences", "per person", "stand-in"]) {
      if (!text.includes(must)) fail(`results miss "${must}"`);
    }
    if (/(^|\n)(null|undefined)(\n|$)/.test(text)) fail("a stray null or undefined is shown");
    if (await page.locator(".donut path").count() < 2) fail("donut chart missing");
    if (await page.locator(".bar-row").count() < 3) fail("bar chart missing");
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    if (width > w + 1) fail(`page scrolls sideways at ${w}px (${width})`);
    if (shots) await page.screenshot({ path: `${shots}/7-results-${label}.png`, fullPage: true });
    const download = page.waitForEvent("download");
    await page.click("text=Entries (CSV)");
    const file = await download;
    if (!/gcc-footprint-PAK-2025\.csv/.test(file.suggestedFilename())) fail("unexpected download name " + file.suggestedFilename());
    console.log(`${label}: results ok, ${await page.locator(".line").count()} entries shown`);
    await page.close();
  }
  await browser.close();
  if (errors.length) fail("browser errors: " + errors.join(" | "));
  console.log("UI OK");
})().catch((e) => fail(String(e)));
