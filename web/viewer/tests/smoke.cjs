// Run with PLAYWRIGHT_MODULE pointing to an installed playwright package.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const path = require("node:path");
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1024 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:8000");
  await page
    .getByRole("heading", { name: "L3. 그래프 탐색 — 표현 · BFS · DFS" })
    .waitFor();
  await page.screenshot({
    path: path.join(__dirname, "desktop.png"),
    fullPage: true,
  });
  await page.locator(".v-article .v-concept").first().hover();
  await page.getByRole("tooltip").waitFor();
  await page.mouse.move(5, 5);
  await page
    .locator(".v-article .v-bullet")
    .first()
    .evaluate((node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      node.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    });
  await page.getByRole("button", { name: "↗ 원본 보기", exact: true }).click();
  await page.getByRole("textbox", { name: "구간 필기" }).waitFor();
  await page.evaluate(() => getSelection().removeAllRanges());
  await page
    .locator(".v-player-head")
    .getByRole("button", { name: "×", exact: true })
    .click();
  await page.locator(".v-article .v-anchor").first().click();
  await page
    .getByRole("textbox", { name: "구간 필기" })
    .fill("앵커에 연결된 테스트 필기");
  await page.getByRole("button", { name: "필기 저장", exact: true }).click();
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("motga-notes"))["L3:2"],
    ),
    "앵커에 연결된 테스트 필기",
  );
  await page
    .locator(".v-player-head")
    .getByRole("button", { name: "×", exact: true })
    .click();
  await page.getByRole("button", { name: "▥ 대시보드" }).click();
  await page.locator(".n-ring").first().waitFor();
  assert.equal(await page.locator(".n-ring").count(), 3);
  await page.screenshot({
    path: path.join(__dirname, "dashboard.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "확인 완료", exact: true })
    .first()
    .click();
  assert.equal(await page.locator(".n-review-row").count(), 3);
  await page
    .getByRole("button", { name: "교수님 발언 검색", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Agent 질문" }).fill("시험");
  await page.getByRole("button", { name: "질문 전송", exact: true }).click();
  await page.locator(".n-agent blockquote").first().waitFor();
  assert.equal(await page.locator(".n-agent blockquote").count(), 2);
  await page.getByRole("button", { name: "위키에 묻기", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Agent 질문" })
    .fill("BFS 시간복잡도");
  await page.getByRole("button", { name: "질문 전송", exact: true }).click();
  await page
    .getByText(
      "BFS는 큐를 써서 가까운 정점부터 방문하고, 인접 리스트 기준 시간복잡도는 O(V+E)다.",
      { exact: true },
    )
    .waitFor();
  await page.getByRole("button", { name: "＋ 강의 자료 추가" }).click();
  await page.locator("input[type=file]").setInputFiles({
    name: "lecture.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("테스트 강의 원문\n<script>alert(1)</script>"),
  });
  await page
    .getByRole("textbox", { name: "강의 제목", exact: true })
    .fill("프론트엔드 테스트 강의");
  await page.getByRole("button", { name: "노트 만들기 →" }).click();
  await page.getByRole("heading", { name: "프론트엔드 테스트 강의" }).waitFor();
  assert.equal(await page.locator("main script").count(), 0);
  await page.reload();
  await page
    .getByRole("button", { name: "▤ 프론트엔드 테스트 강의" })
    .waitFor();
  await page.keyboard.press("Control+k");
  await page
    .getByRole("textbox", { name: "노트 검색" })
    .fill("프론트엔드 테스트");
  assert.equal(await page.locator(".v-result").count(), 1);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page
    .getByRole("heading", { name: "L3. 그래프 탐색 — 표현 · BFS · DFS" })
    .waitFor();
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.screenshot({
    path: path.join(__dirname, "mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "☰", exact: true }).click();
  await page.getByRole("button", { name: "▥ 대시보드" }).click();
  await page.locator(".n-ring").first().waitFor();
  assert.deepEqual(errors, []);
  console.log(
    "PASS: navigation, anchors, persisted notes, dashboard, approvals, quote search, QA, file import, XSS text safety, persisted library, search, mobile; no page errors",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
