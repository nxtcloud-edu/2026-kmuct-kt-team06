# lane: front-minsu (민수) — 필기 · LLM 패널 · 대시보드

**목표**: (1) 멈춘 프레임 **옆에서** 필기 저장. (2) 맨 오른쪽 **LLM 패널** — 위키에만 근거해 답하고, 답변 아래 **관련 영상 카드**(교수님 채널 먼저). (3) 발표용 대시보드.
설문 N=96: 요약 AI를 쓴 학생의 **85%가 원본을 다시 열었다.** LLM 패널의 답변마다 붙는 앵커 칩이 그 답이다 — 여기가 발표의 핵심 화면이다.

**소유**: `web/notes/` 만. **읽을 것**: `CONTRACT.md` §5(특히 `/api/qa`, §5.1 영상 카드) · §6 · §7.
**스택**: 빌드 없는 순수 JS/CSS. 접두사 `n-`. 초기화는 **파일 끝에서 `init()` 1회 + `nav` 이벤트**(§7.2) — Quartz는 SPA다.
**띄우기**: `lanes/front-dongwook.md` 의 "0. 띄우기"와 같다. 슬롯이 아직 없으면(동욱 T3 전) `web/notes/standalone.html` 에 `#note-slot` `#chat-slot` 을 직접 두고 개발한다.

## 30분 단위

### T1 (0:00–0:30) LLM 패널 껍데기 (`web/notes/chat.js`)
- `#chat-slot` 에 마운트(없으면 100ms 간격으로 최대 5초 기다린다 — 동욱이 만든다)
- 구조: 위 = 답변 목록(아래에서 위로 쌓임, 최신이 입력창 바로 위) / **맨 아래 고정 입력창** = `＋` · 모델 드롭다운(`GET /api/models`, 목이면 `fast/strong/gemini` 하드코딩) · 전송
- **모드 토글** `위키에 묻기` | `교수님 발언 검색`(PRD §4.9). 발언 검색 = `GET /api/quotes?q=`(목 `mock/quotes.json`) → 인용 카드(“인용문” — L3 6:12 · s6 [재생]), [재생]=`anchor-request`. 추천 칩: 시험·중요·꼭·연습. **LLM이 없어 제일 먼저 완성되는 기능이다 — T1에 같이 끝낸다**
- 전송 → `POST /api/qa` (목: `GET /mock/qa.json`)
- **완료 조건**: standalone 에서 질문 → 목 답변이 입력창 위에 쌓인다.

### T2 (0:30–1:00) 답변 렌더 = 앵커 칩 + 영상 카드
- `answer` 안의 `[[L3#s5@t=330]]` 를 §3 정규식으로 칩으로. 칩 클릭 → `anchor-request {anchor}` 발사(점프는 동욱이 한다)
- `notes[]` → 답변 끝 **"내 필기:"** 블록(칩 아님, 회색 상자)
- `videos[]` → **"관련 영상"** 카드 2~3개. `source:"professor"` 는 맨 앞 + "교수님 채널" 배지. 클릭은 새 탭
- `reason:"NO_GROUNDING"` → "위키에 근거가 없습니다" 상자 + 영상 카드는 그대로 (목 `mock/qa-nogrounding.json` — 질문에 "다익스트라"가 있으면 이걸 읽게)
- `＋` 버튼 → `context-request` 발사 → `context-reply` 받아 입력창 위에 "📎 bfs · L3 5:30" 칩
- **완료 조건**: 근거 있는 답 1개, 근거 없는 답 1개가 다르게 보인다.

### T3 (1:00–1:30) 필기 패널 (`web/notes/notes.js`)
- `#note-slot` 에 마운트. `segment-boundary` 수신 → 프레임(없으면 생략) + 입력 + [저장][건너뛰기] + 그 구간 기존 필기
- 저장 → `POST /api/notes` → `note-saved`. 건너뛰기 → `notes-closed`. 목이면 `localStorage`
- **422 `WRITE_REJECTED` 의 `message` 를 빨간 상자에 그대로** — 훅이 진짜 돈다는 증거 화면
- **완료 조건**: 동욱 화면에서 멈춤 → 패널 → 저장 → 재개. **동욱과 같이 확인.**

### T4 (1:30–2:00) 진짜 API + 대시보드
- `USE_MOCK=false`
- **검토함**(PRD §4.8, 대시보드 맨 위): `GET /api/review`(목 `mock/review.json`) → "검토 필요 N개" + 카드(사유 배지 · 문장 · [원본 보기]=뷰어 탭으로 `?anchor=` 열기 · [승인]=`POST /api/review/approve` 후 카드 제거, 422면 사유 표시). 성장 그래프는 만들지 않는다
- `web/notes/dashboard.html`(독립): `/api/stats` 큰 숫자(페이지·링크·필기·approved/draft/grey·**커버리지 N/M**) + `/api/history` 표(REJECTED 빨강), 5초 자동 새로고침
- **완료 조건**: 패널 두 개가 목 없이 돌고, 대시보드에 REJECTED 줄이 보인다.

### T5 (2:00–2:30) 다듬기
- 답변 로딩 표시(strong 모델은 수십 초), 실패 토스트, 패널 접힘 상태 기억
- 발표 질문 3개를 입력창 placeholder 로 돌려 보여 주기

## 건드리면 안 되는 곳
`web/viewer/` · `site/` · `api/` · `pipeline/` · `hooks/` · `wiki/` · `raw/` · 슬롯 **바깥** 레이아웃(동욱 것)

## 기다리는 것
없다. `mock/` + `localStorage` + `standalone.html`.

## 계약을 바꾸고 싶으면
`board.sh human "..."`. 이벤트·슬롯은 동욱과 같이 쓰는 것이라 혼자 바꾸면 화면이 죽는다.
