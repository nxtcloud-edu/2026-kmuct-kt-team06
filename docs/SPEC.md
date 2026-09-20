# 기능명세서 — 강의 위키 (카론톤 / Kirothon 2026-09-20)

> PRD(`docs/PRD.md`)가 "왜·무엇"이면 이 문서는 **"정확히 어떻게 동작해야 완료인가"**다. 레인 계약은 `CONTRACT.md`, Kiro용 요구사항은 `.kiro/specs/<레인>/`.
> 상태: ✅ 동작 확인(실측) · 🟡 설계·계약 확정, 구현은 현장 · ⬜ 스트레치
> 우선순위: **P0** 없으면 데모 불가 · **P1** 있으면 설득력 · **P2** 시간이 남으면

## 0. 버리는 순서 / 끝까지 지키는 것

시간이 모자라면 **아래부터** 버린다: F-16 → F-17(서버에 미리 둔 폴더 선택으로 축소) → F-15 → F-14 → F-13 → F-12 → F-11 → F-10 → F-09.
**끝까지 지키는 4개**: F-01(발언 검색) · F-02+F-03(클릭·드래그 → 그 초·그 슬라이드) · F-06(훅 거부가 화면에 뜬다) · 설문 85%.
1:30 통합 점검에서 F-02가 안 되면 그 자리에서 F-13 이하를 버린다.

## 1. 기능 목록

| ID | 기능 | 우선 | 레인 | 상태 |
|---|---|---|---|---|
| F-01 | 교수님 발언 검색 (Exact Quote Search) | P0 | 우석·민수 | ✅ 도구 / 🟡 화면 |
| F-02 | 앵커 칩 → 미니 플레이어 점프 | P0 | 동욱 | 🟡 |
| F-03 | 드래그 → `원본 보기` | P0 | 동욱 | 🟡 |
| F-04 | 미니 플레이어 → split + 구간 끝 자동 정지 | P0 | 동욱 | 🟡 |
| F-05 | 필기 저장 (프레임·슬라이드 옆) | P0 | 민수·우석 | ✅ 훅 / 🟡 화면·API |
| F-06 | 쓰기 훅(WritePolicy) + 거부 사유 표시 | P0 | 규찬 | ✅ |
| F-07 | 파이프라인 ①적재 ②정렬 (코드) | P0 | 규찬 | ✅ 실강의 1편 통과 |
| F-08 | 파이프라인 ③컴파일 (강의 노트 + 개념 페이지) | P0 | 규찬 | 🟡 |
| F-09 | 훅 지표 대시보드 | P1 | 민수·우석 | ✅ 집계 / 🟡 화면 |
| F-10 | LLM 패널 — 위키에 묻기 | P1 | 민수·우석 | 🟡 |
| F-11 | 검토함 (Inbox) + 승인 | P1 | 민수·우석·규찬 | ✅ 훅 규칙 / 🟡 |
| F-12 | ④ 비평 (타입 질문 + 모델 불일치) | P1 | 규찬 | 🟡 |
| F-13 | 유튜브 보충 영상 카드·콜아웃 | P1 | 우석·민수 | 🟡 |
| F-14 | 음성 confidence (두 전사본 일치율) 표시 | P1 | 규찬·동욱 | ✅ 도구 / 🟡 화면 |
| F-15 | 개념 Merge Preview | P2 | 규찬·민수 | ⬜ |
| F-17 | 자료 불러오기(폴더 선택 → 만들기 → 진행률) | P1 | 민수·우석·규찬 | 🟡 DESIGN §4~5 |
| F-18 | 대시보드 도넛 3개 + "이 부분이 헷갈려요" 듣기·수정 | P1 | 민수·우석 | ✅ 수정 훅 / 🟡 |
| F-19 | 출처 말풍선(나무위키 각주 스타일) · 교수님 요약 상자 · Agent 말풍선 | P1 | 동욱·민수·우석 | 🟡 DESIGN §1·3 |
| F-16 | 레퍼런스 원문 `[!ref]` 자동 · Grok STT 라이브 | P2 | 규찬 | ✅ 훅·STT 도구 / ⬜ 자동 |

## 2. 기능별 명세

각 항목: **입력 → 처리 → 출력** · 규칙 · **완료 조건(AC)** = 이게 되면 끝.

### F-01 교수님 발언 검색 — P0
- 입력: 검색어(2자 이상, 500자에서 자름). `GET /api/quotes?q=`
- 처리: `tools/quote_search.py search()` — `raw/L*/transcript.json` 에서 검색어가 든 **문장**만. LLM 없음. 구간표로 슬라이드 번호·앵커를 붙인다.
- 출력: `[{lecture, t, s, quote, anchor, agree|null}]` 강의 번호 → 시각 순.
- 화면: LLM 패널 입력창의 모드 토글 `위키에 묻기 | 교수님 발언 검색`. 결과 카드 `“인용문” — L1 10:27 · s6 [재생]`. 추천 칩: 시험·중요·꼭·연습.
- AC1 "시험" 검색 → 실제 발언이 시간순으로 뜬다 (✅ week_2_2: 10:27 s6 1건)
- AC2 [재생] → 미니 플레이어가 그 초로 간다 (`anchor-request`)
- AC3 빈 검색어·1글자 → `[]`, 화면은 추천 칩을 보여 준다
- AC4 `agree < 0.5` 인 문장에는 🔈 경고

### F-02 앵커 칩 → 점프 — P0
- 입력: Quartz가 그린 `<a class="internal">L3 > s5@t=330</a>` (텍스트 `^L(\d+) > s(\d+)@t=(\d+)$`)
- 처리: `nav` 마다 칩 `<button class="v-anchor" data-anchor="L3#s5@t=330">L3 · 5:30</button>` 으로 교체 → 클릭 시 `GET /api/source?anchor=` → 플레이어 seek + 재생, 슬라이드(없으면 프레임) 표시, `anchor-open` 발사.
- AC1 견본 노트의 앵커 10개가 전부 칩이 된다. 탐색기로 다른 페이지에 가도(새로고침 없음) 칩이 된다
- AC2 mp4·m4a·유튜브 세 종류 모두 그 초로 간다 (서버가 Range 206 을 줘야 한다 ✅)
- AC3 **페이지를 옮겨도 재생이 끊기지 않는다** — UI 뿌리는 `<html>` 아래 `#v-root` (CONTRACT §7.3)
- AC4 404 `SOURCE_NOT_FOUND` → 토스트, 화면은 안 죽는다. 같은 칩 연타·메타데이터 로드 전 클릭 안전

### F-03 드래그 → 원본 보기 — P0
- 처리: 선택 영역 위에 `#v-selbtn`. 클릭 → 그 블록(`p`/`li`/`blockquote`)의 첫 칩, 없으면 같은 `h2` 주제 안 바로 앞 칩. LLM 없음.
- AC1 🗣 인용을 드래그 → 교수가 그 말을 한 초 · AC2 💡 줄을 드래그 → 그 주제의 슬라이드 · AC3 주제에 칩이 없으면 버튼이 안 뜬다

### F-04 split + 자동 정지 — P0
- 처리: 미니 플레이어 클릭 → `html.v-split`. 오른쪽 위 = 플레이어·슬라이드, 아래 = `#note-slot`. `t_end` 통과 시 `pause()` + `segment-boundary`. `note-saved`/`notes-closed` → `play()`.
- AC1 재생 → 구간 끝에서 멈춤 → 필기 패널 → 저장 → 이어서 재생 · AC2 "구간 끝에서 멈추기" 끄면 안 멈춘다 · AC3 split 접기/펴기가 재생을 끊지 않는다

### F-05 필기 저장 — P0
- 입력: `POST /api/notes {lecture, k, text}` (헤더 `X-Demo-Token`)
- 처리: 서버가 구간표에서 앵커를 채워 `wiki/notes/L{n}/s{k}.md` 를 만들고 **`write_page_guard.py` 에 `agent:"user"` 로 태운다.** 통과해야 파일이 써진다.
- 출력: `{ok, path, anchor, frame}` · 거부 시 422 `WRITE_REJECTED` + 훅 사유 원문
- AC1 저장 → 다시 열면 그 구간에 필기가 보인다 · AC2 없는 구간·8KB 초과·본문에 앵커 위조·`<script>` → 422 와 사유가 빨간 상자에 **그대로** (✅ 훅 실측) · AC3 같은 구간 재저장은 덮어쓰기(이전 본문은 history) · AC4 글은 `textContent` 로만 그린다

### F-06 쓰기 훅 — P0 ✅
- 규칙 ID: R01 쓰기 루트 밖 · R02 경로 위조 · R03 프론트매터 · R04 앵커·형식 없음 · R05 없는 구간 앵커 · R06 가짜·범위 앵커 · R07 콜아웃 밖 링크 · R08 HTML 삽입 · R09 승인인 척 본문 수정 · R10 크기 · R11 링커 본문 변경
- AC ✅ 훅 21케이스 + 오탐 4케이스 통과. 모든 판정이 `wiki/.history.jsonl` 에 `{ts, agent, tool, path, verdict, rule, reason, attempt, run}` 로 남는다

### F-07 ① 적재 ② 정렬 — P0 ✅ (코드, 모델 0회)
```
PDF ──lecture-md──▶ 교본.md(<!-- page N -->) ──┐
녹음 ─stt_grok / 다글로─▶ transcript.json ─stt_agree─▶ agree ─┤
                                  align_slides.py ◀──────────┘──▶ segments.json
PDF ──pdftoppm──▶ slides/s{n}.png            frame_guard.py(차단) ──▶ build_episodic.py ──WritePolicy──▶ wiki/episodic/L{n}.md
```
- AC ✅ 컴퓨터구조 week_2_2: 슬라이드 21 · 전사 58문단 → 구간 15 · FrameGuard allow · episodic 58문장 전부 앵커 · 1초 미만
- 규칙: 구간표가 FrameGuard 를 못 넘으면 ②로 가지 않는다. 경계 confidence 는 확률이 아니다 — 낮은 순 5개를 검토함에(PRD §8.7)

### F-08 ③ 컴파일 — P0
- 입력: episodic 의 슬라이드 범위 하나(주제). 모델 = strong.
- 출력: 강의 노트의 `## N.` 주제 하나(📄→💡→🗣→🎯) + 개념 페이지 추가분. 전부 `write_page` → 훅.
- 루프: 거부되면 사유만 고쳐 재시도(최대 3회, `attempt` 를 훅에 전달) → 3회 실패 = `blocked`, 다음 주제로.
- AC1 강의 1편에서 주제 3개 이상이 allow · AC2 발표 중 **라이브로 주제 1개**를 돌려 deny → allow 가 대시보드에 올라온다 · AC3 🗣 인용은 전부 episodic 문장에서 온 것(F-12 인용 대조로 확인)

### F-09 훅 지표 대시보드 — P1
- 출처: `tools/hook_metrics.py metrics()` → `/api/stats` 의 `hooks` 필드 (✅ 실제 로그로 확인, `mock/stats.json` 에 같은 모양)
- **보여 줄 숫자**

| 숫자 | 뜻 | 발표에서 하는 말 |
|---|---|---|
| `writes_total / allowed / denied` | 쓰기 시도·통과·거부 | "모델이 쓴 것 중 N%는 훅이 막았습니다" |
| `rescued_after_deny` | 거부됐다가 고쳐서 통과한 페이지 | **"에이전트가 사유를 읽고 스스로 고쳤습니다"** ← 심사 ② |
| `first_pass_rate` · `avg_attempts_to_pass` | 한 번에 통과한 비율 · 평균 시도 | 프롬프트가 나아지면 오른다 |
| `blocked_for_good` | 끝내 못 쓴 시도 | "권한 밖 쓰기·HTML 삽입은 끝까지 막혔습니다" |
| `by_rule[]` | 규칙별 거부 수(막대) | 가장 많이 걸리는 규칙 = 모델이 가장 자주 틀리는 곳 |
| `by_agent{}` | 에이전트별 allow/deny | 쓰기 루트 분리가 실제로 작동 |
| `anchors_written` · `quotes_written` | 위키에 들어간 앵커·🗣 인용 수 | "문장 N개가 원본으로 가는 길을 갖고 있습니다" |
| `last[10]` | 최근 판정 | 실시간 로그 |

- AC1 5초 자동 새로고침 · AC2 deny 줄은 빨강 + 규칙 라벨 · AC3 `verdict` 값은 `allow`/`deny` (표기만 "REJECTED")

### F-10 LLM 패널 — P1
- `POST /api/qa {question, model, context}` → grep + 링크 1홉 근거 → 근거 0이면 모델을 안 부르고 `NO_GROUNDING` → 답변은 QAStop 훅 → `{answer, anchors, notes, unanchored, model, videos}`
- AC1 "BFS 시간복잡도?" → 앵커 칩이 달린 답 · AC2 위키에 없는 질문 → "근거 없음" + 영상 카드 · AC3 답변 속 칩 클릭 → 점프 · AC4 입력창은 맨 아래 고정, 답은 위로 쌓인다 · AC5 IP당 분당 10회, 토큰 없으면 401

### F-11 검토함 — P1
- `GET /api/review` = 구간 confidence 낮은 순 5 · status grey/draft · history 의 deny→allow · 인용 대조 실패 · `stt_uncertain` · (P2) merge
- `POST /api/review/approve {id}` → `agent:"user"` 로 훅 → **`status:` 한 줄만** 변경 (✅ R09 실측)
- AC1 "검토 필요 N개" → [원본 보기] → [승인] → N−1 · AC2 승인 요청에 본문 변경이 섞이면 422

### F-12 ④ 비평 — P1
- 문단·인용마다 `{supported, quote_faithful, from_untrusted, evidence}` JSON. 서로 다른 모델 2개에 1회씩 → 갈리면 8회 표본(PRD §8.8). **판정은 코드**: `no` 하나라도 → 그 문단 재작성 · `partial`/불일치 → 검토함 · 2회 실패 → grey.
- 인용 대조(코드): 🗣 인용 ↔ 앵커 구간 전사본 문자 유사도. 지표 "🗣 N개 중 M개 통과".

### F-13 유튜브 보충 — P1
- `api/youtube.py search(q)` = TranscriptAPI HTTP, 교수 채널 먼저, 캐시 `raw/.ytcache/`. EC2에서 yt-dlp 금지.
- 쓰임 둘: LLM 답변 아래 카드 · 강의 노트의 `> [!youtube]` 콜아웃(교수가 선수 지식을 밖으로 넘긴 🗣 아래에만).
- AC 실패·키 없음 → `[]`, 답변은 그대로 나온다. 콜아웃 밖 유튜브 링크는 R07 로 거부 ✅

### F-14 음성 confidence — P1
- `tools/stt_agree.py` — 두 전사본 일치율 `agree`. **0.5 미만 = 경고 + 🗣 인용 금지 + 검토함, 0.8 미만 = 🔈 표시.** (✅ 1분 실측: 63% 1건이 실제 오인식)

### F-15 Merge Preview — P2 · F-16 레퍼런스·STT 라이브 — P2
- PRD §4.10 · §4.7 · §8.9. 포맷과 훅(R07, status-only)은 이미 들어 있다. 자동화는 시간이 남을 때.

### F-17~19 (9/20 11:32 팀 스케치 반영) — 화면은 `docs/DESIGN.md`, API는 `CONTRACT.md` §5
- F-17 AC: 폴더 선택 → 자료 3종 인식 → [만들기] → 진행 막대가 **실제 단계**를 따라 오른다 → 끝나면 왼쪽 목록에 제목이 생긴다. 실패하면 단계와 이유가 보인다. 업로드는 확장자 화이트리스트·500MB·서버가 파일명 부여.
- F-18 AC: 도넛 3개가 `/api/dashboard` 값으로 그려진다. **측정 전 값은 회색 "측정 전"** (0%로 그리지 않는다). [▷듣기] → 그 초 재생. [수정] → 훅 통과 후 목록에서 빠지고 STT 도넛이 오른다. ✅ `fix_transcript` 훅 6케이스(정상·없는 문장·에이전트 시도·script·id 위조·600자).
- F-19 AC: 🗣·칩에 마우스 → "출처: 16:05 · 09/16 / 교수님 발언 '…'" 말풍선. 위키 링크 미리보기는 Quartz 팝오버(구현 없음).
- 도넛 숫자는 **센 비율**이다(일치율·통과율). 확률처럼 설명하지 않는다 — 정의는 DESIGN §6 표.

## 3. 비기능

| 항목 | 기준 |
|---|---|
| 배포 | EC2 m5.large 1대, 한 프로세스(`api/server.py`) + `quartz build --watch`. git pull |
| 비밀 | 키는 서버 환경변수로만. 정적 서빙은 `devserve.resolve()` 만(점 파일·폴더 탈출 차단 ✅) |
| 공개 저장소 | 실제 강의 자료·그 산출물·설문 원본은 커밋 금지(.gitignore ✅). 견본 L3 만 추적 |
| 권한 | 로그인 없음. `DEMO_TOKEN` 으로 쓰기·과금 경로만 보호 |
| 성능 | 발언 검색·점프·필기 저장 < 1초. LLM 답변은 로딩 표시 |
| 장애 | 유튜브·STT·LLM 이 죽어도 F-01~F-06 은 돈다. 데모 녹화 백업 필수 |
| 정직성 | confidence 류 숫자는 확률처럼 표기하지 않는다(PRD §8.7) |
