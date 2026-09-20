const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("http://127.0.0.1:8000");
    const folder = (name) => page.getByRole("button", { name, exact: true });
    await folder("알고리즘").waitFor();
    await folder("알고리즘").click();
    assert.equal(await page.locator("#folder-lectures").isVisible(), false);
    assert.equal(await page.locator("#folder-concepts").isVisible(), true);
    await page.reload();
    await folder("알고리즘").waitFor();
    assert.equal(await folder("알고리즘").getAttribute("aria-expanded"), "false");
    await folder("알고리즘").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#folder-lectures").isVisible(), true);

    async function createFolder(parent, name) {
      await folder(`${parent}에 추가`).click();
      await page.getByRole("textbox", { name: "새 폴더 이름" }).fill(name);
      await folder("폴더 만들기").click();
      await folder(name).waitFor();
    }
    await createFolder("알고리즘", "연습 문제");
    await createFolder("연습 문제", "1주차");
    await folder("1주차에 추가").click();
    await folder("파일 추가").click();
    await page.locator('input[type="file"]').setInputFiles({
      name: "exercise.md", mimeType: "text/markdown", buffer: Buffer.from("연습 문제 본문"),
    });
    await page.getByRole("textbox", { name: "강의 제목" }).fill("폴더 테스트 노트");
    await folder("노트 만들기  →").click();
    await page.getByRole("heading", { name: "폴더 테스트 노트", exact: true }).waitFor();
    const leaf = page.locator(".v-folder-section").filter({ has: folder("1주차") }).last();
    assert.equal(await leaf.locator(".v-file").count(), 1);
    await folder("연습 문제").click();
    assert.equal(await folder("1주차").isVisible(), false);
    await page.reload();
    await folder("연습 문제").waitFor();
    assert.equal(await folder("연습 문제").getAttribute("aria-expanded"), "false");
    await folder("연습 문제").click();
    await page.getByRole("button", { name: "▤ 폴더 테스트 노트", exact: true }).click();
    await page.getByRole("heading", { name: "폴더 테스트 노트", exact: true }).waitFor();

    await folder("알고리즘에 추가").click();
    await page.getByRole("textbox", { name: "새 폴더 이름" }).fill("연습 문제");
    await folder("폴더 만들기").click();
    assert.equal(await page.getByRole("dialog").count(), 1);
    assert.equal(await page.getByRole("textbox", { name: "새 폴더 이름" }).evaluate((n) => n.validationMessage), "같은 이름의 폴더가 있습니다.");
    await page.keyboard.press("Escape");
    await folder("＋ 강의 자료 추가").click();
    assert.equal(await page.getByText("추가할 폴더:", { exact: false }).count(), 0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => document.querySelector(".v-app").classList.add("v-menu-open"));
    await folder("개념 노트").click();
    assert.equal(await folder("개념 노트").getAttribute("aria-expanded"), "false");
    assert.deepEqual(errors, []);
    console.log("Folder tests passed: toggle, keyboard, nesting, upload, persistence, validation, mobile.");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
