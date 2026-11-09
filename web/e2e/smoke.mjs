import { spawn } from "node:child_process";
import { chromium } from "playwright";

const PORT = 8137;
const server = spawn(
  "python",
  ["-m", "http.server", String(PORT), "--directory", "."],
  { cwd: process.cwd(), stdio: "ignore" }
);
await new Promise((resolve) => setTimeout(resolve, 1200));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});
page.on("pageerror", (error) => errors.push(String(error)));

async function visit(path, action) {
  await page.goto(`http://127.0.0.1:${PORT}/${path}`, {
    waitUntil: "networkidle",
  });
  if (action) await action(page);
  await page.waitForTimeout(200);
  if (errors.length) {
    throw new Error(`${path}: ${errors.join(" | ")}`);
  }
}

await visit("index.html", async (p) => {
  if (await p.isChecked("#demographic-swing")) {
    throw new Error("demographic swing should default off");
  }
  if (await p.locator("#range-YENI").count()) {
    throw new Error("2023 view should not show YENI");
  }
  await p.selectOption("#election-year", "2028");
  if (!(await p.locator("#range-YENI").count()) || !(await p.locator("#range-A").count())) {
    throw new Error("2028 view is missing new parties");
  }
  await p.selectOption("#election-year", "2023");
  const shares = async () =>
    (await p.locator("#party-table").innerText()).match(/\d+,\d+%/g)?.join("|");
  const beforeSwing = await shares();
  await p.check("#demographic-swing");
  if ((await shares()) !== beforeSwing) {
    throw new Error("demographic swing changed national party shares");
  }
  await p.uncheck("#demographic-swing");
  await p.selectOption("#election-year", "2028");
  if (!(await p.textContent("#election-note"))?.includes("2028")) {
    throw new Error("2028 scenario note missing");
  }
  if (await p.isDisabled("#apply-polls")) {
    throw new Error("2028 polls should enable the apply button");
  }
  await p.click("#apply-polls");
  await p.waitForTimeout(200);
  const applied = await p.locator("#party-table").innerText();
  if (!applied.includes("YENİ") || !applied.includes("\nA\n")) {
    throw new Error("2028 poll average did not populate new parties");
  }
  if ((await p.locator("#map .seat-badge").count()) === 0) {
    throw new Error("map seat badges missing");
  }
  if ((await p.locator("#hemicycle path").count()) < 600) {
    throw new Error("hemicycle triangles missing");
  }
  if ((await p.locator("#seat-cartogram path").count()) < 600) {
    throw new Error("seat cartogram missing");
  }
  await p.check("#demographic-swing");
  if (await p.isChecked("#kurdish-swing")) {
    throw new Error("kurdish support should default off");
  }
  await p.check("#kurdish-swing");
  await p.locator("#map .province-path").first().click();
  await p.waitForFunction(
    () => document.querySelector("#map-breadcrumb")?.textContent?.includes("/"),
    null,
    { timeout: 3000 }
  );
  await p.waitForFunction(
    () =>
      [...document.querySelectorAll("#map .ilce-path")].some(
        (element) => getComputedStyle(element).display !== "none"
      ),
    null,
    { timeout: 3000 }
  );
  if (!(await p.locator("#map-back").isVisible())) {
    throw new Error("province drilldown back button missing");
  }
  await p.click("#map-back");
  await p.waitForTimeout(800);
  if ((await p.textContent("#map-breadcrumb"))?.trim() !== "Türkiye") {
    throw new Error("province drilldown did not reset");
  }
});

await visit("president.html", async (p) => {
  await p.selectOption("#election-year", "2028");
  if (!(await p.textContent("#election-note"))?.includes("2028")) {
    throw new Error("president 2028 scenario note missing");
  }
  if ((await p.locator("#candidate-controls .candidate-row").count()) < 5) {
    throw new Error("president 2028 candidate registry missing");
  }
  await p.waitForTimeout(300);
  if (await p.isDisabled("#apply-polls")) {
    throw new Error("president 2028 apply button is disabled");
  }
  await p.click("#apply-polls");
  await p.waitForTimeout(300);
  const presidentBars = await p.locator("#first-bars").innerText();
  if (!presidentBars.includes("Erdo")) {
    throw new Error(`president 2028 poll average did not render: ${presidentBars.slice(0, 120)}`);
  }
});

await visit("polls.html", async (p) => {
  const subtext = (await p.locator(".poll-sub").first().innerText()).toLowerCase();
  if (!subtext.includes("düz.")) {
    throw new Error("adjusted poll subtext missing");
  }
  if ((await p.locator(".poll-cell.winner").count()) === 0) {
    throw new Error("poll winner highlight missing");
  }
  await p.selectOption("#election-year", "2028");
  if (!(await p.textContent("#election-note"))?.includes("2028")) {
    throw new Error("polls 2028 scenario note missing");
  }
});

await visit("demographics.html", async () => {
  await page.waitForSelector("#scatter path, #demo-map path", {
    timeout: 5000,
  });
  if ((await page.evaluate(() => document.body.dataset.view)) !== "simple") {
    throw new Error("simple correlation view missing");
  }
  if (!(await page.locator("#plain-summary").isVisible())) {
    throw new Error("plain summary missing");
  }
  await page.click("#view-expert");
  await page.waitForTimeout(100);
  if ((await page.evaluate(() => document.body.dataset.view)) !== "expert") {
    throw new Error("expert correlation view missing");
  }
  const expertStats = (await page.locator("#corr-stats").innerText()).toUpperCase();
  if (!expertStats.includes("PEARSON")) {
    throw new Error("expert statistics missing");
  }
  await page.click("#view-simple");
});

await browser.close();
server.kill();
console.log("e2e smoke passed");
