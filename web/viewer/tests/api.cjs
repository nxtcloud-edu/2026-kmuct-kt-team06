const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem("motga-mock", "false"));
  const segments = [
    { k: 1, s: 1, t_start: 0, t_end: 0.5, final_frame: "seg_1_final.jpg" },
    { k: 2, s: 2, t_start: 0.5, t_end: 1.5, final_frame: "seg_2_final.jpg" },
  ];
  const video = { kind: "audio", src: "/test.wav" };
  const wav = Buffer.alloc(44 + 8000 * 2 * 3);
  wav.write("RIFF");
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(8000, 24);
  wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(wav.length - 44, 40);
  await page.route("**/test.wav", (route) =>
    route.fulfill({ contentType: "audio/wav", body: wav }),
  );
  await page.route("**/api/**", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let data = {};
    if (url.pathname === "/api/segments/L3")
      data = { lecture: "L3", segments, video };
    else if (url.pathname === "/api/source")
      data = { video, frame: "/raw/L3/seg_1_final.jpg" };
    else if (url.pathname === "/api/notes/L3") data = [];
    else if (url.pathname === "/api/notes" && request.method() === "POST")
      return route.fulfill({
        status: 422,
        json: {
          error: {
            code: "WRITE_REJECTED",
            message: "REJECTED: test policy rejection",
          },
        },
      });
    else if (url.pathname === "/api/qa")
      return route.fulfill({
        status: 401,
        json: { error: { message: "로그인이 필요합니다" } },
      });
    else if (url.pathname === "/api/stats")
      return route.fulfill({
        status: 500,
        json: { error: { message: "통계 서버 오류" } },
      });
    else data = [];
    return route.fulfill({ json: data });
  });
  await page.goto("http://localhost:8000");
  await page.locator(".v-article").waitFor();
  await page.evaluate(() =>
    Motga.emit("anchor-request", { anchor: "L3#s1@t=0" }),
  );
  await page.locator("audio").waitFor();
  await page.locator("audio").evaluate(async (player) => {
    player.muted = true;
    await player.play();
  });
  await page.waitForFunction(
    () =>
      document.querySelector("audio").paused &&
      document.querySelector("audio").currentTime >= 0.5,
  );
  await page
    .getByRole("textbox", { name: "구간 필기" })
    .fill("거부되어도 이 필기는 유지되어야 함");
  await page.getByRole("button", { name: "필기 저장", exact: true }).click();
  await page
    .getByText("REJECTED: test policy rejection", { exact: true })
    .waitFor();
  assert.equal(
    await page.getByRole("textbox", { name: "구간 필기" }).inputValue(),
    "거부되어도 이 필기는 유지되어야 함",
  );
  await page.getByRole("button", { name: "건너뛰기", exact: true }).click();
  await page.waitForFunction(
    () =>
      document.querySelector("audio").paused &&
      document.querySelector("audio").currentTime >= 1.5,
  );
  await page
    .getByRole("heading", { name: "나의 필기 · 슬라이드 2", exact: true })
    .waitFor();
  await page
    .locator(".v-player-head")
    .getByRole("button", { name: "×", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Agent 질문" }).fill("BFS 알려줘");
  await page.getByRole("button", { name: "질문 전송", exact: true }).click();
  await page.getByText("로그인이 필요합니다", { exact: true }).waitFor();
  assert.equal(
    await page.getByRole("textbox", { name: "Agent 질문" }).inputValue(),
    "BFS 알려줘",
  );
  await page.getByRole("button", { name: "▥ 대시보드" }).click();
  await page.getByText("통계 서버 오류", { exact: false }).waitFor();
  await page.getByRole("button", { name: "다시 시도", exact: true }).waitFor();
  assert.deepEqual(errors, []);
  console.log(
    "PASS: real audio boundaries and resume into next segment; 422 note preservation; 401 question preservation; 500 dashboard retry; no page errors",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
