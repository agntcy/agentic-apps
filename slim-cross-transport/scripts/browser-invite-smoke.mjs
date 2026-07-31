/**
 * Two-browser-tab smoke: browser-a moderates, browser-b must accept invite.
 */
import { chromium } from "playwright";

const URL = process.env.SMOKE_URL ?? "http://127.0.0.1:5173/";
const SECRET = "test-shared-secret-value-0123456789abcdef";
const MLS = process.env.SMOKE_MLS === "1";
const INVITEES = (process.env.SMOKE_INVITEES ?? "org/default/browser-b")
  .split(",")
  .map((name) => name.trim())
  .filter(Boolean);

const browser = await chromium.launch({ headless: true });
const ctxA = await browser.newContext();
const ctxB = await browser.newContext();
const pageA = await ctxA.newPage();
const pageB = await ctxB.newPage();
if (process.env.SMOKE_DEBUG === "1") {
  pageA.on("console", (message) => console.log(`[browser-a:${message.type()}] ${message.text()}`));
  pageB.on("console", (message) => console.log(`[browser-b:${message.type()}] ${message.text()}`));
  pageA.on("pageerror", (error) => console.log(`[browser-a:error] ${error.stack ?? error}`));
  pageB.on("pageerror", (error) => console.log(`[browser-b:error] ${error.stack ?? error}`));
}

async function waitWasm(page) {
  await page.goto(URL, { waitUntil: "networkidle", timeout: 30_000 });
  await page.waitForFunction(
    () => document.getElementById("wasm-status")?.textContent?.includes("WASM ready"),
    { timeout: 60_000 },
  );
}

async function connect(page, { mode, localName }) {
  await page.locator("#mode").selectOption(mode);
  await page.fill("#local-name", localName);
  await page.fill("#secret", SECRET);
  await page.click("#connect");
  await page.waitForFunction(
    () => document.getElementById("conn-status")?.textContent?.includes("Connected"),
    { timeout: 30_000 },
  );
}

try {
  await waitWasm(pageA);
  await waitWasm(pageB);

  await connect(pageB, { mode: "participant", localName: "org/default/browser-b" });
  await connect(pageA, { mode: "moderator", localName: "org/default/browser-a" });
  await pageA.waitForTimeout(500);

  await pageA.locator("#mls-enabled").setChecked(MLS);
  await pageA.fill("#channel", "org/default/room-1");
  await pageA.fill("#invitees", INVITEES.join("\n"));

  await pageA.click("#create-session");
  try {
    await pageA.waitForFunction(
      (invitees) => {
        const log = document.getElementById("log")?.textContent ?? "";
        return invitees.every(
          (name) => log.includes(`${name} joined`) || log.includes(`${name} did not join`),
        );
      },
      INVITEES,
      { timeout: 120_000 },
    );
  } catch {
    console.log("=== browser-a log (moderator wait failed) ===");
    console.log(await pageA.locator("#log").textContent());
    console.log("=== browser-b log (moderator wait failed) ===");
    console.log(await pageB.locator("#log").textContent());
    throw new Error("moderator invite did not finish");
  }

  try {
    await pageB.waitForFunction(
      () => {
        const count = document.getElementById("session-count")?.textContent ?? "0";
        return Number(count) > 0;
      },
      { timeout: 60_000 },
    );
  } catch {
    console.log("=== browser-a log (session wait failed) ===");
    console.log(await pageA.locator("#log").textContent());
    console.log("=== browser-b log (session wait failed) ===");
    console.log(await pageB.locator("#log").textContent());
    throw new Error("browser-b never received session card");
  }

  const logA = await pageA.locator("#log").textContent();
  const logB = await pageB.locator("#log").textContent();
  console.log("=== browser-a log ===");
  console.log(logA);
  console.log("=== browser-b log ===");
  console.log(logB);

  for (const invitee of INVITEES) {
    if (!logA.includes(`${invitee} joined`)) {
      console.error(`FAIL: moderator did not confirm ${invitee} joined`);
      process.exit(1);
    }
  }
  if (
    INVITEES.includes("org/default/browser-b") &&
    !logB.includes("accepted from a moderator")
  ) {
    console.error("FAIL: browser-b did not accept session");
    process.exit(1);
  }
  console.log("BROWSER INVITE SMOKE PASSED");
} catch (error) {
  console.error("BROWSER INVITE SMOKE ERROR:", error);
  process.exit(1);
} finally {
  await browser.close();
}
