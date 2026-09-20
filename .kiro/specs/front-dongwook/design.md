# Design — front-dongwook
> ⏸ **시각 디자인(레이아웃·색·모양)은 팀에서 그리는 중 — 확정 전.** 아래에서 유효한 것은 동작·이벤트·슬롯·마운트 규칙뿐이다. 디자인이 오면 CSS와 DOM 모양은 그쪽을 따른다. **백엔드 두 레인이 먼저 출발한다.**
- 파일: `web/viewer/viewer.js` · `viewer.css` (+ `site/quartz.config.yaml`). 서버가 모든 HTML에 주입한다(CONTRACT §7.1) → import/번들 없음, 전역 오염 금지(IIFE 하나).
- 구조: `#v-root`(html 직속, fixed) ⊃ `#v-mini`(플레이어) · `#v-pane`(split: 위 미디어, 아래 `#note-slot`) · `#chat-slot`(맨 오른쪽 열) · `#v-selbtn` · `#v-toast`
- 상태: `state = {segments:{L3:[…]}, current:{lecture,k}, autopause:true}` — 모듈 변수. 구간표는 강의당 1회 fetch 후 캐시.
- 미디어 어댑터 3종(`mp4`/`audio`/`youtube`)이 같은 인터페이스 `{seek(t), play(), pause(), now()}` 를 갖는다. 유튜브는 IFrame API + 250ms 폴링.
- Quartz 레이아웃 좁히기: `html.v-split body{margin-right:…}` · `html.v-chat-open body{…}`. Quartz 클래스를 직접 덮어쓰지 않는다.
- 목: `const USE_MOCK=true; const API=p=>USE_MOCK?`/mock${p.replace('/api','').split('?')[0]}.json`:p;` — 1:30 에 false.
- **첫 확인 항목**: `#v-root` 를 `<html>` 에 붙였을 때 페이지 이동 후에도 남는가(소스로만 확인됨, 브라우저 실측은 T2 첫 5분).
