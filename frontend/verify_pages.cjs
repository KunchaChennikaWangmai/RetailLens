/* Drive Retail Lens in headless Chrome: click each sidebar tab, wait for
 * data, record console errors, and screenshot every page. */
const { chromium } = require("playwright-core");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = "http://localhost:5173";
const TABS = ["home", "analytics", "inventory", "employees", "customers", "profitability", "data", "chat"];

(async () => {
    const browser = await chromium.launch({
        executablePath: CHROME,
        headless: true,
        args: ["--no-sandbox"],
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const consoleErrors = [];
    page.on("console", (m) => {
        if (m.type() === "error") consoleErrors.push(m.text().slice(0, 300));
    });
    page.on("pageerror", (e) => consoleErrors.push("PAGEERROR: " + String(e).slice(0, 300)));
    page.on("requestfailed", (r) =>
        consoleErrors.push(`REQFAIL ${r.method()} ${r.url()} :: ${r.failure()?.errorText}`)
    );

    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);

    for (const tab of TABS) {
        consoleErrors.length = 0;
        const t0 = Date.now();
        await page.click(`a[href="#${tab}"]`);
        if (tab === "chat") {
            await page.waitForTimeout(500);
        } else {
            // Wait until the page stops loading (spinner gone or error shown).
            try {
                await page.waitForFunction(
                    () => {
                        const main = document.querySelector("main");
                        if (!main) return false;
                        const text = main.textContent || "";
                        return !text.includes("Loading") || text.includes("Could not load");
                    },
                    { timeout: 60000, polling: 250 }
                );
            } catch {
                /* timeout — will be reported as STILL_LOADING */
            }
        }
        const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
        const bodyText = (await page.textContent("main")) || "";
        const marker = bodyText.includes("₹")
            ? "HAS_DATA(₹)"
            : bodyText.includes("Could not load")
              ? "ERROR_STATE"
              : bodyText.includes("Loading")
                ? "STILL_LOADING"
                : "NO_MONEY_MARKER";
        await page.screenshot({ path: `/tmp/rl_${tab}.png` });
        console.log(`[${tab}] ${marker} after ${elapsed}s | text-snippet: ${bodyText.replace(/\s+/g, " ").slice(0, 160)}`);
        if (consoleErrors.length) console.log(`[${tab}] console: ${consoleErrors.join(" || ")}`);
    }
    await browser.close();
})().catch((e) => {
    console.error("SCRIPT FAILED:", e);
    process.exit(1);
});