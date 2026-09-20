# CONTRACT — 카론톤 / Kirothon 2026-09-20

**이 파일이 레인 사이의 유일한 약속이다.** 여기 적힌 경로·이름·스키마는 현장에서 바꾸지 않는다.
바꿔야 하면 코드를 먼저 고치지 말고 `board.sh human "CONTRACT §N 변경: A(그대로) / B(이렇게)"` 로 멈춰서 팀장 승인을 받는다.

설계 정본: `docs/claude6-harness.md` (v1.1) · 현장 할 일 메모: `docs/PLAN.md`

---

## 1. 레인과 소유 디렉터리

한 레인 = 한 Kiro가 소유하는 디렉터리. **남의 디렉터리에는 한 줄도 쓰지 않는다.**

| 레인 | 담당 | 소유(쓰기 허용) | 읽기만 |
|---|---|---|---|
| `front-dongwook` | 동욱 | `web/viewer/` · `site/quartz.config.yaml` (Quartz 설정·테마) | `mock/`, `raw/`, `public/` |
| `front-minsu` | 민수 | `web/notes/` | `mock/`, `raw/` |
| `back-wooseok` | 우석 | `api/` | `wiki/`, `raw/`, `hooks/`, `tools/`, `public/` |
| `back-kyuchan` | 규찬(팀장) | `pipeline/` `hooks/` `tools/` `prompts/` `skills/` `mock/` `CONTRACT.md` `lanes/` `docs/` | 전부 |

- `wiki/`, `raw/` 는 **산출물**이다. 사람이 손으로 고치지 않는다(파이프라인과 API만 쓴다).
- `site/` = Quartz 5 (MIT). **`site/quartz/` 내부 소스는 아무도 고치지 않는다.** 바꿀 수 있는 건 `site/quartz.config.yaml` 뿐(동욱).
- `public/` = Quartz 빌드 결과. gitignore. 손대지 않는다.
- 루트 파일(`README.md`, `.gitignore`)은 팀장만.

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
**위키 본문·페이지 목록·검색·백링크·그래프는 Quartz가 그린다 → 페이지 API는 없다.**

| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/api/segments/{lecture}` | `{lecture, video:{kind:"mp4"\|"youtube", src}, segments:[...§4.1]}` |
| GET | `/api/source?anchor=L3%23s7%40t%3D340` | `{lecture:"L3", k, s, t_start, t_end, frame:"/raw/L3/seg_7_final.jpg"\|null, slide:"..."\|null, video:{kind,src}, ocr, exists:true}` · 없으면 404 `SOURCE_NOT_FOUND` |
| GET | `/api/notes/{lecture}` | `[{k, s, text, anchor, frame, updated}]` |
| POST | `/api/notes` | 요청 `{lecture:"L3", k:7, text:"..."}` → `{ok:true, path, anchor, frame}` · WritePolicy 거부 시 **422** `{"error":{"code":"WRITE_REJECTED","message":"<훅이 준 이유 그대로>"}}` |
| GET | `/api/stats` | `{lectures, pages, approved, draft, grey, links, notes, coverage:{covered, total}}` |
| GET | `/api/history?limit=10` | `[{ts, agent, tool, path, verdict, reason}]` (최신순) |
| POST | `/api/qa` | 요청 `{question, model:"fast"\|"strong"\|"gemini", context:{slug, anchor\|null}}` → `{answer, anchors:[str], notes:[{anchor,text}], unanchored:[str], model, videos:[§5.1]}` · 위키에 근거 없으면 **200** `{answer:null, reason:"NO_GROUNDING", message, videos:[...]}` |
| GET | `/api/youtube/search?q=` | `[§5.1]` — 교수 채널 결과 먼저, 그다음 일반 검색 |
| GET | `/api/models` | `[{id:"fast", label:"빠름 · gpt-5.4-nano"}, ...]` — LLM 패널 드롭다운용 |

### 5.1 영상 카드
`{videoId, title, channel, duration, thumbnail, url, source:"professor"|"search"}`
**보충 추천일 뿐이다. 위키에 넣지 않는다. 앵커가 될 수 없다.** 교수 채널 id는 `api/media.json` 의 `professorChannel`.

### 5.2 `/api/qa` 규칙 (LLM 패널 = 위키 한정)
1. `tools/grep_wiki.py` + 링크 1홉으로 위키에서 근거를 찾는다. **위키 밖 지식으로 답하지 않는다.**
2. 답변은 `hooks/qa_stop_guard.py` 를 통과해야 한다(앵커 없는 답변 → 재생성 1회 → 그래도 없으면 `NO_GROUNDING`).
3. 어느 경우든 `videos` 는 채운다(질문 키워드로 `/api/youtube/search` 와 같은 함수 호출). 실패하면 `[]`.
4. 유튜브 호출은 **TranscriptAPI HTTP**(EC2는 yt-dlp가 막힌다). 응답은 `raw/.ytcache/<sha1(q)>.json` 에 캐시 — 크레딧 100개뿐이다.

### 5.3 서빙 (api/server.py 가 전부 한다, 같은 오리진)
- `/` → `public/` (Quartz 결과). **HTML 응답에는 §7.1 의 주입 블록을 `</body>` 앞에 끼운다.** 구현은 `tools/devserve.py` 의 `inject()`·`resolve()` 를 import 해서 그대로 쓴다.
- `/web/**` `/raw/**` `/mock/**` → 저장소의 같은 디렉터리
- Quartz 재빌드는 별도 프로세스: `cd site && npx quartz build -d ../wiki -o ../public --watch` (팀장이 띄운다). 파이프라인이 `wiki/` 에 쓰면 몇 초 뒤 화면에 나온다.

**프론트는 401/403/500을 토스트로 띄우고 죽지 않는다.**

## 6. 목(mock) — 프론트는 0분부터 시작한다

```bash
cd site && npm ci && npx quartz build -d ../wiki -o ../public && cd ..
python3 tools/devserve.py 8000        # http://localhost:8000
```
`tools/devserve.py` 가 `public/` 에 **§7.1 주입**까지 해서 띄운다 → API 서버 없이 네 JS가 Quartz 화면 위에서 돈다.

프론트 JS 맨 위에 이 두 줄만 두고, API가 살면 `false` 로 바꾼다:
```js
const USE_MOCK = true;
const API = (p) => USE_MOCK ? `/mock${p.replace('/api','').split('?')[0]}.json` : p;
```
목 파일: `mock/segments/L3.json` `mock/source.json` `mock/notes/L3.json` `mock/stats.json` `mock/history.json` `mock/qa.json` `mock/qa-nogrounding.json`
POST는 목이 없다 → `USE_MOCK` 이면 필기는 `localStorage`, QA는 `mock/qa.json` 을 GET.

## 7. 화면 — Quartz 위에 얹는다

**Quartz가 그리는 것**(우리는 안 만든다): 위키 본문, 왼쪽 탐색기, 검색, 백링크, 그래프, 다크 모드.
**우리가 얹는 것**: 앵커 칩 · 미니 플레이어 → split · 필기 · LLM 패널.

```
평소                                          미니 플레이어를 누르면 (split)
┌────────┬──────────────────┬──┬────────┐    ┌────────┬──────────┬───────────┬────────┐
│Quartz  │ 위키 본문         │▣ │ LLM    │    │Quartz  │ 위키 본문 │ 영상·프레임 │ LLM    │
│탐색기   │ 문장 [L3·s5·5:30]│미니│ 답변 ↑ │    │탐색기   │          │───────────│ 답변 ↑ │
│        │                  │   │ [입력] │    │        │          │ 필기       │ [입력] │
└────────┴──────────────────┴──┴────────┘    └────────┴──────────┴───────────┴────────┘
```
- **미니 플레이어**: 오른쪽 위에 작게 떠 있다(Aside의 PiP처럼). 앵커를 누르면 거기서 그 초가 재생된다. **미니 플레이어를 누르면 split** 으로 펼쳐져 위=영상·프레임, 아래=필기. 다시 접을 수 있다.
- **LLM 패널**: 맨 오른쪽, 접을 수 있다. 입력창은 **맨 아래 고정**, 답변은 **위로 쌓인다**. 입력창 = `＋`(지금 페이지·구간 첨부) · 모델 드롭다운 · 전송. 답변 아래 **"관련 영상" 카드**(§5.1, 교수 채널 먼저).

### 7.1 주입 (서버가 모든 HTML의 `</body>` 앞에 넣는다 — 순서 고정)
```html
<link rel="stylesheet" href="/web/viewer/viewer.css">
<link rel="stylesheet" href="/web/notes/notes.css">
<script defer src="/web/viewer/viewer.js"></script>
<script defer src="/web/notes/notes.js"></script>
<script defer src="/web/notes/chat.js"></script>
```

### 7.2 Quartz와 같이 살기 (✅ 9/20 실측)
- Quartz는 SPA다. 페이지를 옮길 때 새로고침이 없다 → **초기화는 전부 `document.addEventListener('nav', init)` 안에서.** `DOMContentLoaded` 에만 걸면 두 번째 페이지부터 죽는다. `nav` 는 첫 로드에도 발생하지만(spa.inline.ts:198) 우리 스크립트는 `defer` 라 그걸 놓칠 수 있다 → **파일 끝에서 `init()` 을 한 번 직접 부르고, `nav` 에도 건다.**
- `init` 은 **여러 번 불린다** → 슬롯·플레이어는 "없으면 만든다"로. 중복 생성 금지.
- Quartz는 우리 앵커 `[[L3#s5@t=330]]` 를 위키링크로 오해해서 이렇게 렌더링한다:
  `<a class="internal ..." href="../lectures/l3#s5t330">L3 > s5@t=330</a>`
  → `viewer.js` 가 `nav` 마다 본문의 `a.internal` 중 **텍스트가 `^L(\d+) > s(\d+)@t=(\d+)$`** 인 것을 찾아 `<button class="v-anchor" data-anchor="L3#s5@t=330">` 칩으로 **바꿔치기**한다. 이게 앵커의 DOM 규약이다.
- 페이지 `status` 배지(draft/grey)는 Quartz가 안 그린다 → P2. 시간이 남으면 viewer 가 얹는다.

### 7.3 슬롯 (동욱이 만들고, 민수가 채운다)
`viewer.js` 가 `nav` 때 `document.body` 에 없으면 만든다. **안쪽 DOM은 민수 것.**
```html
<aside id="note-slot"></aside>   <!-- split 아래쪽 -->
<aside id="chat-slot"></aside>   <!-- 맨 오른쪽 열 -->
```

### 7.4 이벤트 (서로의 파일을 import 하지 않는다. `window` 이벤트로만)
| 이벤트 | 쏘는 쪽 → 받는 쪽 | detail |
|---|---|---|
| `segment-boundary` | viewer → notes | `{lecture, k, s, t_end, frame}` — 구간 끝에서 멈춤. split 이 닫혀 있으면 viewer 가 먼저 연다 |
| `anchor-open` | viewer → (notes, chat) | `{lecture, s, t, anchor}` |
| `anchor-request` | chat → viewer | `{anchor:"L3#s5@t=330"}` — 답변 속 칩을 눌렀다. viewer 가 점프한다 |
| `note-saved` / `notes-closed` | notes → viewer | `{lecture, k}` — 재생 재개 |
| `context-request` → `context-reply` | chat → viewer → chat | reply `{slug, anchor\|null}` — `＋` 버튼이 지금 보는 곳을 묻는다 |

**CSS**: 동욱 `v-`, 민수 `n-`. 전역 태그 셀렉터 금지. Quartz 클래스(`.center`, `.sidebar` 등)를 덮어쓸 때는 `body.v-split .center{}` 처럼 **자기 body 클래스 아래에서만**.
**대시보드**는 독립 페이지 `web/notes/dashboard.html` (Quartz 밖, 발표용).

## 8. 대기 관계 (기다리는 사람이 없게)

| 레인 | 남을 기다리는 것 | 그동안 쓰는 것 |
|---|---|---|
| front-dongwook | API(`/api/source`, `/api/segments`) | `tools/devserve.py` + `mock/` |
| front-minsu | API(`/api/notes`, `/api/qa`, `/api/stats`) | `tools/devserve.py` + `mock/` + `localStorage` |
| back-wooseok | 파이프라인의 `wiki/` 산출물 | 저장소에 **커밋된 `wiki/` 샘플**과 `raw/L3/` 로 출발 |
| back-kyuchan | 없음 | — |

**합류 시각**: 1:30 에 `USE_MOCK=false` 로 동시에 전환하고 팀장이 통합 점검한다. 그 전엔 아무도 남을 기다리지 않는다.

## 9. 절대 하지 않는 것

- 남의 디렉터리 수정 · `wiki/` `raw/` 손수정 · `CONTRACT.md` 무단 수정
- `git commit` / `push` (사람이 한다) · 라이브러리 추가(우리 프론트 코드는 **빌드 없는 순수 JS/CSS** — Quartz만 빌드한다) · `site/quartz/` 소스 수정
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
