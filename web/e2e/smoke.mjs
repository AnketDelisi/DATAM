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
  await p.selectOption("#election-year", "2028");
  if (!(await p.textContent("#election-note"))?.includes("2028")) {
    throw new Error("2028 scenario note missing");
  }
  if (!(await p.isDisabled("#apply-polls"))) {
    throw new Error("empty 2028 polls should disable the apply button");
  }
  await p.check("#demographic-swing");
  if (await p.isChecked("#kurdish-swing")) {
    throw new Error("kurdish support should default off");
  }
  await p.check("#kurdish-swing");
  await p.locator("#map .province-path").first().click();
  await p.waitForTimeout(800);
  if (!(await p.textContent("#map-breadcrumb"))?.includes("/")) {
    throw new Error("province drilldown breadcrumb missing");
  }
  if (!(await p.locator("#map-back").isVisible())) {
    throw new Error("province drilldown back button missing");
  }
  if ((await p.locator("#map .ilce-path:visible").count()) === 0) {
    throw new Error("province drilldown has no visible ilçe paths");
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
