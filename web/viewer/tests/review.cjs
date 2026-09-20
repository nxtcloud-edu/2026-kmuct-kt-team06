const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const button = (name) => page.getByRole("button", { name, exact: true });
    await page.goto("http://127.0.0.1:8000");
    await page.locator(".v-article .v-anchor").first().click();
    await button("노트와 영상 나란히 보기").click();
    await page.waitForFunction(() => document.querySelector(".v-split"));
    assert.equal(await page.evaluate(() => document.fullscreenElement), null);
    assert.equal(await page.locator(".v-media-empty").count(), 0);
    assert.equal(await page.locator(".n-chat-disclaimer").count(), 0);
    await button("작은 플레이어로 돌아가기").click();
    assert.equal(await page.locator(".v-split").count(), 0);
    await page.locator(".v-player-head").getByRole("button", { name: "×", exact: true }).click();
    await page.locator(".v-article .v-anchor").first().click();
    await button("노트와 영상 나란히 보기").click();
    assert.equal(await page.locator(".v-split").count(), 1);
    await page.keyboard.press("Escape");
    assert.equal(await page.locator(".v-split").count(), 0);
    await page.locator(".v-player-head").getByRole("button", { name: "×", exact: true }).click();

    // An actual WAV tests the media path and bounded playback without relying on missing demo media.
    const wav = Buffer.alloc(44 + 8000 * 2 * 3);
    wav.write("RIFF"); wav.writeUInt32LE(wav.length - 8, 4);
    wav.write("WAVEfmt ", 8); wav.writeUInt32LE(16, 16);
    wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
    wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
    wav.write("data", 36); wav.writeUInt32LE(wav.length - 44, 40);
    const item = { id: "stt-test", kind: "stt_uncertain", lecture: "L3", anchor: "L3#s1@t=0", text: "큐에 너을 때 방문 표시", reason: "전사 확인 필요" };
    await page.route("**/mock/review.json", (r) => r.fulfill({ json: [item] }));
    await page.route("**/mock/segments/L3.json", (r) => r.fulfill({ json: {
      video: { kind: "audio", src: "/review-test.wav" },
      segments: [{ s: 1, t_start: 0, t_end: 1.2 }],
    } }));
    await page.route("**/review-test.wav", (r) => r.fulfill({ contentType: "audio/wav", body: wav }));
    await button("▥ 대시보드").click();
    await page.getByRole("heading", { name: "이 부분이 헷갈려요!", exact: true }).waitFor();
    const card = page.locator(".n-transcript-card");
    const input = card.getByRole("textbox");
    await card.getByRole("button", { name: "정정", exact: true }).click();
    assert.match(await card.locator(".n-error").innerText(), /입력/);
    await input.fill("큐에 넣을 때 방문 표시");
    await card.getByRole("button", { name: "정정", exact: true }).click();
    assert.match(await card.locator(".n-correction-status").innerText(), /저장됨/);
    await page.reload();
    await button("▥ 대시보드").click();
    await input.waitFor();
    assert.equal(await input.inputValue(), "큐에 넣을 때 방문 표시");
    await card.locator(".n-transcript-play").click();
    await page.waitForFunction(() => document.querySelector(".n-transcript-play")?.getAttribute("aria-pressed") === "true");
    await page.waitForFunction(() => document.querySelector(".n-transcript-play")?.getAttribute("aria-pressed") === "false");
    assert.equal(await card.locator(".n-error").innerText(), "");

    const colors = () => page.evaluate(() => [".v-app", ".v-sidebar", ".n-transcript-card", ".n-correction-input"].map((s) => {
      const style = getComputedStyle(document.querySelector(s));
      return [style.color, style.backgroundColor, style.backgroundImage, style.colorScheme];
    }));
    await page.emulateMedia({ colorScheme: "light" });
    const light = await colors();
    await page.emulateMedia({ colorScheme: "dark" });
    assert.deepEqual(await colors(), light);
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({ path: "web/viewer/tests/review-desktop.png" });
    await page.setViewportSize({ width: 390, height: 844 });
    await button("Agent ◫").click();
    await card.scrollIntoViewIfNeeded();
    const bounds = await card.boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= 390);
    await page.screenshot({ path: "web/viewer/tests/review-mobile.png" });
    await input.fill("재수정 문장");
    await page.evaluate(() => {
      window.originalSetItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, value) {
        if (key === "motga-transcript-corrections") throw new Error("quota");
        return window.originalSetItem.call(this, key, value);
      };
    });
    await card.getByRole("button", { name: "정정", exact: true }).click();
    assert.match(await card.locator(".n-error").innerText(), /저장하지 못/);
    assert.equal(await input.inputValue(), "재수정 문장");
    await page.evaluate(() => { Storage.prototype.setItem = window.originalSetItem; });
    await card.getByRole("button", { name: "정정", exact: true }).click();
    assert.match(await card.locator(".n-correction-status").innerText(), /저장됨/);
    await page.route("**/review-test.wav", (r) => r.fulfill({ status: 404, body: "missing" }));
    await card.locator(".n-transcript-play").click();
    await page.waitForFunction(() => document.querySelector(".n-transcript-card .n-error")?.textContent.includes("불러올 수 없습니다"));
    assert.equal(await card.locator(".n-transcript-play").isEnabled(), true);
    assert.deepEqual(errors, []);
    console.log("Review tests passed: fullscreen, fallback, removed notices, correction persistence, actual audio and stop boundary, fixed theme, mobile.");
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
