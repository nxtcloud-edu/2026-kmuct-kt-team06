const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const path = require("node:path");
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.addInitScript(() => localStorage.setItem("motga-mock", "false"));
    const wav = Buffer.alloc(44 + 8000 * 2 * 5);
    wav.write("RIFF"); wav.writeUInt32LE(wav.length - 8, 4); wav.write("WAVEfmt ", 8);
    wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
    wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write("data", 36); wav.writeUInt32LE(wav.length - 44, 40);
    await page.route("**/split.wav", r => r.fulfill({ contentType: "audio/wav", body: wav }));
    const video = { kind: "mp4", src: "/split.wav" };
    await page.route("**/api/segments/L3", r => r.fulfill({ json: {
      video, segments: [{ s: 1, k: 1, t_start: 0, t_end: 5, final_frame: "seg_1_final.jpg" }],
    } }));
    await page.route("**/api/source?*", r => r.fulfill({ json: { video, frame: "/raw/L3/seg_1_final.jpg" } }));
    await page.route("**/raw/L3/transcript.json", r => r.fulfill({ json: [
      { t_start: 0, t_end: 2, text: "첫 번째 전사 문장" },
      { t_start: 2, t_end: 5, text: "두 번째 전사 문장" },
    ] }));
    await page.goto("http://127.0.0.1:8000/?anchor=L3%23s1%40t%3D0");
    const split = page.getByRole("button", { name: "노트와 영상 나란히 보기", exact: true });
    await split.click();
    await page.getByRole("button", { name: "0:02 두 번째 전사 문장" }).waitFor();
    const main = await page.locator(".v-main").boundingBox();
    const pane = await page.locator("#v-pane").boundingBox();
    const top = await page.locator(".v-topbar").boundingBox();
    assert.ok(main.x + main.width <= pane.x + 1);
    assert.ok(pane.y >= top.y + top.height);
    assert.equal(await page.evaluate(() => document.fullscreenElement), null);
    await page.waitForFunction(() => document.querySelector("#v-media video")?.readyState > 0);
    await page.getByRole("button", { name: "0:02 두 번째 전사 문장" }).click();
    await page.waitForFunction(() => document.querySelector("video").currentTime >= 2);
    assert.match(await page.locator('.v-transcript-row[aria-current="true"]').innerText(), /두 번째/);
    await page.screenshot({ path: path.join(__dirname, "split-desktop.png") });
    await page.getByRole("button", { name: "작은 플레이어로 돌아가기" }).click();
    assert.equal(await page.locator(".v-transcript").isVisible(), false);
    await split.click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Agent ◫", exact: true }).click();
    const mobileMain = await page.locator(".v-main").boundingBox();
    const mobilePane = await page.locator("#v-pane").boundingBox();
    assert.ok(mobilePane.y >= mobileMain.y + mobileMain.height - 1);
    assert.ok(mobilePane.x + mobilePane.width <= 390);
    await page.screenshot({ path: path.join(__dirname, "split-mobile.png") });
    await page.locator(".v-player-head").getByRole("button", { name: "×", exact: true }).click();
    assert.equal(await page.locator(".v-split").count(), 0);
    assert.equal(await page.locator("#v-pane").isVisible(), false);
    assert.deepEqual(errors, []);
    console.log("PASS: split layout, transcript, media seek/highlight, PiP return, close, mobile; no page errors");
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
