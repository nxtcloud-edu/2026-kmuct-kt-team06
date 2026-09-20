# CONTRACT — 카론톤 / Kirothon 2026-09-20

**이 파일이 레인 사이의 유일한 약속이다.** 여기 적힌 경로·이름·스키마는 현장에서 바꾸지 않는다.
바꿔야 하면 코드를 먼저 고치지 말고 `board.sh human "CONTRACT §N 변경: A(그대로) / B(이렇게)"` 로 멈춰서 팀장 승인을 받는다.

설계 정본: `docs/claude6-harness.md` (v1.1) · 현장 할 일 메모: `docs/PLAN.md`

---

## 1. 레인과 소유 디렉터리

한 레인 = 한 Kiro가 소유하는 디렉터리. **남의 디렉터리에는 한 줄도 쓰지 않는다.**

| 레인 | 담당 | 소유(쓰기 허용) | 읽기만 |
|---|---|---|---|
| `front-dongwook` | 동욱 | `web/viewer/` | `mock/`, `raw/`, `CONTRACT.md` |
| `front-minsu` | 민수 | `web/notes/` | `mock/`, `raw/`, `CONTRACT.md` |
| `back-wooseok` | 우석 | `api/` | `wiki/`, `raw/`, `pipeline/`, `CONTRACT.md` |
| `back-kyuchan` | 규찬(팀장) | `pipeline/` `hooks/` `tools/` `prompts/` `skills/` `mock/` `CONTRACT.md` `lanes/` | 전부 |

- `wiki/`, `raw/` 는 **산출물**이다. 사람이 손으로 고치지 않는다(파이프라인과 API만 쓴다).
- `docs/` 는 읽기 전용(설계 정본).
- 루트 파일(`README.md`, `.gitignore`, `requirements.txt`)은 팀장만.

## 2. 커밋 규칙

- **Kiro는 `git commit` / `git push` / `gh pr` 를 못 한다**(훅이 막음). Kiro는 "📦 커밋 제안"만 출력하고, 사람이 직접 커밋한다.
- 커밋 메시지: `<레인>: 한 줄` (예: `front-viewer: 앵커 클릭 → 영상 점프`)
- **자기 소유 디렉터리 밖 파일이 스테이징에 올라오면 커밋하지 말고 팀장에게 말한다.**
- 30분마다 한 번은 커밋·푸시한다. 3시간짜리라 merge 지옥이 나면 끝이다.

## 3. 앵커 규약 (전 레인 공용, 절대 불변)

```
[[L3#s7@t=340]]
  L3  = 강의 번호        s7 = 슬라이드 번호 또는 판서 구간 번호        t=340 = 초(정수)
```

파싱 정규식 — 프론트·백엔드 모두 **이것만** 쓴다:

```
\[\[L(\d+)#s(\d+)@t=(\d+)\]\]
```

- `[[note:...]]`, `[[signal:...]]` 는 **앵커가 아니다.** 화면에 링크로 만들지 않는다. 훅이 거부한다.
- 유효 앵커 = `raw/L{n}/segments.json` 에 `s` 가 같고 `t_start ≤ t ≤ t_end` 인 행이 있는 것.

## 4. 데이터 스키마 (읽기 전용, 이미 확정됨)

### 4.1 `raw/L{n}/segments.json`
```json
[{"k": 7, "kind": "board", "s": 7, "t_start": 312.0, "t_end": 340.4,
  "final_frame": "seg_7_final.jpg", "ocr": "BFS: queue 사용, O(V+E)", "ocr_engine": "tesseract"}]
```
`final_frame` 의 실제 URL = `/raw/L{n}/{final_frame}` · 슬라이드 있으면 `/raw/L{n}/slides/s{s}.png`

### 4.2 위키 페이지 (`wiki/concepts/<slug>.md`, `wiki/lectures/L{n}.md`)
프론트매터 `title, type, sources, status(draft|approved|grey), links` + `## Current` + `## History`.
`Current` 의 한 문단 = 한 주장 + 앵커 1개 이상.

### 4.3 필기 (`wiki/notes/L{n}/s{k}.md`)
프론트매터 `type: note, anchor, frame, trust: user, updated` · 본문 8KB 이하.
**앵커는 사용자가 입력하지 않는다. 서버가 세그먼트에서 채운다.**

## 5. API 계약 (back-wooseok 가 구현, 프론트는 이것만 부른다)

베이스: 같은 오리진 `/api`. 실패는 HTTP 상태 + `{"error":{"code":"...","message":"..."}}`.

| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/api/pages` | `[{slug, path, title, type, status, links:[slug], updated}]` |
| GET | `/api/pages/{slug}` | `{slug, title, type, status, links, current:[{id, text, anchors:[str]}], history:[{text, anchors}], md}` |
| GET | `/api/segments/{lecture}` | `segments.json` 원본 배열 + `{lecture, video: {kind:"mp4"\|"youtube", src}}` 를 감싼 `{lecture, video, segments:[...]}` |
| GET | `/api/source?anchor=L3%23s7%40t%3D340` | `{lecture:"L3", k, s, t_start, t_end, frame:"/raw/L3/seg_7_final.jpg", slide:"/raw/L3/slides/s7.png"\|null, video:{kind,src}, ocr, exists:true}` · 없으면 404 `SOURCE_NOT_FOUND` |
| GET | `/api/notes/{lecture}` | `[{k, s, text, anchor, frame, updated}]` |
| POST | `/api/notes` | 요청 `{lecture:"L3", k:7, text:"..."}` → `{ok:true, path, anchor, frame}` · WritePolicy 거부 시 **422** `{"error":{"code":"WRITE_REJECTED","message":"<훅이 준 이유 그대로>"}}` |
| GET | `/api/stats` | `{lectures, pages, approved, draft, grey, links, notes, coverage:{covered, total}}` |
| GET | `/api/history?limit=10` | `[{ts, agent, tool, path, verdict, reason}]` (최신순, `.history.jsonl` 꼬리) |
| POST | `/api/qa` | 요청 `{question}` → `{answer, anchors:[str], notes:[{anchor,text}], unanchored:[str]}` *(⑦, 스트레치 — 없으면 501)* |

정적 서빙: `/raw/**` (프레임·슬라이드·mp4), `/` → `web/viewer/index.html`.

**프론트는 401/403/500을 화면에 토스트로 띄우고 죽지 않는다.** API가 아직 없으면 §6 목으로 붙는다.

## 6. 목(mock) — 프론트는 0분부터 시작한다

`mock/` 아래에 §5와 **경로·스키마가 같은** 정적 JSON이 들어 있다(팀장이 채워 둠).

프론트 코드 맨 위에 이 한 줄만 두고, API가 살면 `false` 로 바꾼다:

```js
const USE_MOCK = true;
const API = (p) => USE_MOCK ? `/mock${p.replace('/api','')}.json` : p;
```

목 파일: `mock/pages.json` `mock/pages/<slug>.json` `mock/segments/L3.json` `mock/source.json` `mock/notes/L3.json` `mock/stats.json` `mock/history.json`
데모 강의는 `L3` 하나로 고정. 프레임 이미지는 `raw/L3/` 의 진짜 파일을 쓴다.

## 7. 프론트 두 레인의 경계 (동욱 ↔ 민수)

한 화면에 둘이 들어가므로 **이벤트로만 붙는다. 서로의 파일을 import 하지 않는다.**

- `web/viewer/` = 위키 본문 렌더 + 앵커 클릭 + 영상 플레이어 + 경계 자동 정지
- `web/notes/` = 필기 패널 + 대시보드(성장·반려 로그·커버리지)

**뷰어 → 노트 (동욱이 쏘고, 민수가 받는다)**
```js
window.dispatchEvent(new CustomEvent('segment-boundary', {
  detail: { lecture: 'L3', k: 7, s: 7, t_end: 340.4, frame: '/raw/L3/seg_7_final.jpg' }
}));
window.dispatchEvent(new CustomEvent('anchor-open', { detail: { lecture, s, t, anchor } }));
```
**노트 → 뷰어 (민수가 쏘고, 동욱이 받는다)**
```js
window.dispatchEvent(new CustomEvent('note-saved',  { detail: { lecture, k } }));  // 뷰어는 재생 재개
window.dispatchEvent(new CustomEvent('notes-closed', { detail: { lecture, k } }));  // 저장 안 하고 닫음 → 재생 재개
```
**마운트 지점**: 뷰어 `index.html` 안에 `<aside id="note-slot"></aside>` 가 비어 있다. 민수의 `web/notes/notes.js` 가 `document.getElementById('note-slot')` 에 자기 UI를 그린다. 동욱은 이 요소의 내부를 건드리지 않는다.
**대시보드**는 독립 페이지 `web/notes/dashboard.html` (뷰어와 무관, 발표용 화면 3·4·5).
**CSS 충돌 방지**: 동욱 클래스 접두사 `v-`, 민수 `n-`. 전역 태그 셀렉터(`body{}`, `a{}`) 금지.

## 8. 대기 관계 (기다리는 사람이 없게)

| 레인 | 남을 기다리는 것 | 그동안 쓰는 것 |
|---|---|---|
| front-dongwook | API(`/api/pages`, `/api/source`) | `mock/` (0분부터 완성품 만들 수 있음) |
| front-minsu | API(`POST /api/notes`, `/api/stats`) | `mock/` + 저장은 `localStorage` 폴백 |
| back-wooseok | 파이프라인의 `wiki/` 산출물 | 저장소에 **커밋된 `wiki/` 샘플 3페이지**를 그대로 파싱 |
| back-kyuchan | 없음 | — |

**합류 시각**: 1:30 에 `USE_MOCK=false` 로 동시에 전환하고 팀장이 통합 점검한다. 그 전엔 아무도 남을 기다리지 않는다.

## 9. 절대 하지 않는 것

- 남의 디렉터리 수정 · `wiki/` `raw/` 손수정 · `CONTRACT.md` 무단 수정
- `git commit` / `push` (사람이 한다) · 라이브러리 추가(프론트는 **빌드 없는 순수 HTML/CSS/JS**, 백엔드는 표준 라이브러리 + 이미 있는 것)
- 앵커 없는 문장을 `## Current` 에 쓰기 · `notes/` `signals/` 를 앵커로 인용하기
- 동작하는 것보다 예쁘게 만드는 것 — **심사는 동작 100%를 안 본다. 설계와 화면을 본다.**

## 10. 막히면

```
board.sh status "한 일 / 다음"     30분마다
board.sh done "끝낸 것"            태스크 끝날 때마다
board.sh blocked "막힌 것"         3분 헤맸으면 바로
board.sh human "A로 갈까 B로 갈까"  계약을 바꿔야 할 때 (레인 정지 → 팀장 승인)
```
같은 오류가 3번째면 `~/.kiro/skills/adviser/ask.sh "질문"` (Fable 자문, 읽기 전용).
