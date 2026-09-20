# lane: front-minsu (민수) — 필기 + 대시보드

**목표**: (1) 영상이 멈춘 그 프레임 **옆에** 필기를 적어 저장한다 — "필기가 강의랑 따로 논다"는 문제를 화면으로 보여주는 곳.
(2) 위키가 **자란다**는 것과 **검증이 실제로 돌았다**는 것을 숫자로 보여주는 대시보드 — 발표 화면 3·4·5.

**소유**: `web/notes/` 만. 계약은 `CONTRACT.md`(§5 API, §6 목, §7 이벤트).
**스택**: 빌드 없는 순수 HTML/CSS/JS. 클래스 접두사 `n-`. 전역 셀렉터 금지.

## 30분 단위

### T1 (0:00–0:30) 필기 패널 단독으로 완성
- `web/notes/notes.js` `notes.css` + 혼자 열어볼 `web/notes/standalone.html`
- 패널 = 프레임 이미지 + 텍스트 입력 + [저장] [건너뛰기] + 그 구간에 이미 있는 필기 목록
- 아직 이벤트 안 붙여도 된다. `standalone.html` 에서 가짜 detail 로 호출해 본다
- **완료 조건**: 프레임 옆에서 글을 쓰고 저장 버튼이 눌린다.

### T2 (0:30–1:00) 이벤트로 뷰어에 붙기
- `document.getElementById('note-slot')` 에 마운트. **뷰어 파일은 한 줄도 고치지 않는다**
- `segment-boundary` 수신 → 패널 열기 (detail: lecture, k, s, t_end, frame)
- 저장 → `POST /api/notes {lecture,k,text}` → 성공하면 `note-saved` 발사
- 건너뛰기 → `notes-closed` 발사
- **목 모드**: `USE_MOCK=true` 면 `localStorage` 에 저장하고 성공 취급 (CONTRACT §8)
- 422 `WRITE_REJECTED` 면 훅이 준 `message` 를 빨간 박스에 **그대로** 보여준다 — 이게 "훅이 진짜 돈다"는 증거 화면이다
- **완료 조건**: 동욱 화면에서 경계 정지 → 내 패널 뜸 → 저장 → 재생 재개. **동욱과 둘이 같이 확인.**

### T3 (1:00–1:30) 대시보드 ①성장 ②반려 로그
- `web/notes/dashboard.html` (독립 페이지)
- `GET /api/stats` → 큰 숫자 카드: 강의 수 · 페이지 수 · 링크 수 · 필기 수 · **approved/draft/grey**
- "강의 1편 → 3편" 성장: 강의 수를 1·2·3 으로 바꿔가며 페이지·링크 수가 느는 막대 (데이터가 없으면 stats 를 강의별로 받아 누적)
- `GET /api/history?limit=10` → 표: 시각 · agent · path · **verdict(ALLOW/REJECTED)** · reason. REJECTED 는 빨강
- **완료 조건**: 두 화면이 목으로 뜬다. 특히 REJECTED 줄이 보인다.

### T4 (1:30–2:00) 커버리지 + 진짜 API
- `stats.coverage` → "시험 범위 커버리지 **N/M**" 도넛 또는 큰 숫자 + 미커버 항목 목록
- `USE_MOCK = false` 전환, 깨지는 것 보고
- **완료 조건**: 목 없이 T2·T3가 된다.

### T5 (2:00–2:30) 발표용 다듬기
- 대시보드 자동 새로고침 5초 (발표 중 숫자가 실제로 오르는 걸 보여준다)
- 내 필기 목록 화면: 강의별 필기 → 클릭하면 뷰어의 그 구간으로 (`?lecture=L3&k=7` 로 링크)
- 빈 상태 문구
- **완료 조건**: 발표에서 대시보드 → 필기 → 뷰어 순서로 끊김 없이 넘어간다.

## 건드리면 안 되는 곳
`web/viewer/` (동욱) · `api/` · `pipeline/` · `hooks/` · `wiki/` · `raw/` · `CONTRACT.md`
`#note-slot` 바깥의 레이아웃은 동욱 것. 슬롯 **안**만 네 것.

## 기다리는 것 / 그동안
`POST /api/notes` 와 `/api/stats` 를 기다리지 않는다 — `mock/` + `localStorage` 로 끝까지 만든다.
1:30 에 다 같이 `USE_MOCK=false`.

## 계약을 바꾸고 싶으면
`board.sh human "..."`. 특히 이벤트 이름·`#note-slot` 규약은 동욱과 같이 쓰는 것이라 혼자 바꾸면 화면이 죽는다.
