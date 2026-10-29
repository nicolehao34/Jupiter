/**
 * Headed Playwright walkthrough for README demo (~75s). Run while screen recording.
 */
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";

async function pause(ms) {
  await new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const browser = await chromium.launch({
    headless: false,
    slowMo: 100,
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  await page.goto(`${BASE}/#/agent`, { waitUntil: "networkidle" });
  await pause(2500);

  const runBtn = page.getByRole("button", { name: /Run campaign/i });
  await runBtn.click();
  await page.getByText(/Stop reason|human checkpoint|Running plan/i).first().waitFor({ timeout: 120000 });
  await pause(2000);
  await page.mouse.wheel(0, 400);
  await pause(1500);
  await page.mouse.wheel(0, 500);
  await pause(2000);

  await page.locator('a.tab[href="#/plan"]').first().click();
  await pause(3500);
  await page.locator('a.tab[href="#/agent"]').first().click();
  await pause(1500);

  const cont = page.getByRole("button", { name: /Continue campaign/i });
  if (await cont.isEnabled()) {
    await cont.click();
    await pause(8000);
  }
  await page.mouse.wheel(0, 300);
  await pause(1500);

  await page.locator('a.tab[href="#/review"]').first().click();
  await pause(3500);
  await page.locator('a.tab[href="#/agent"]').first().click();
  await pause(2500);

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
