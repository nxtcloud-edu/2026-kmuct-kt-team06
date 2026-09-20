# Design — front-minsu
> ⏸ **시각 디자인(레이아웃·색·모양)은 팀에서 그리는 중 — 확정 전.** 아래에서 유효한 것은 동작·이벤트·슬롯·마운트 규칙뿐이다. 디자인이 오면 CSS와 DOM 모양은 그쪽을 따른다. **백엔드 두 레인이 먼저 출발한다.**
- 파일: `web/notes/chat.js`(LLM 패널·발언 검색) · `notes.js`(필기) · `notes.css` · `dashboard.html`(+`dashboard.js`, 독립 페이지) · `standalone.html`(슬롯이 생기기 전 개발용)
- 마운트: `#chat-slot` · `#note-slot` 은 동욱이 `#v-root` 안에 만든다. 없으면 100ms 간격 최대 5초 대기. 슬롯 **안쪽**만 내 것. 슬롯이 `<html>` 쪽에 있어 페이지 이동에도 패널 상태(대화·입력)가 유지된다.
- 초기화: 파일 끝 `init()` 1회 + `nav`. 슬롯 내용이 이미 있으면 다시 그리지 않는다.
- 모드 토글 상태·접힘 상태는 `localStorage`(try/catch).
- 대시보드 숫자의 뜻·발표 멘트는 `docs/SPEC.md` F-09 표. 실제 모양은 `mock/stats.json` 의 `hooks`(진짜 훅 로그에서 뽑은 것).
- 목: `USE_MOCK` — POST 는 목이 없으므로 필기=`localStorage`, QA=`GET /mock/qa.json`(질문에 "다익스트라"가 있으면 `qa-nogrounding.json`), 검색=`/mock/quotes.json`, 검토함=`/mock/review.json`.
