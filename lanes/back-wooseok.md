# lane: back-wooseok (우석) — 서버 · API · QA

**목표**: EC2(m5.large) 한 대에서 **한 프로세스, 한 오리진**으로 전부 서빙한다 — Quartz 결과(`public/`) + 우리 JS 주입 + `/api/*`. 필기 저장은 **WritePolicy 훅을 통과**시키고, LLM 패널의 `/api/qa` 는 **위키에만 근거해** 답한다.

**소유**: `api/` 만. `hooks/` `tools/` 는 **import 해서 쓰되 수정 금지**.
**읽을 것**: `CONTRACT.md` §3 · §4 · **§5 전부(5.2 QA 규칙, 5.3 서빙)**.
**스택**: Python 표준 라이브러리 우선. LLM 호출은 팀장의 `pipeline/llm.py`(T2 이후 생김) — 그 전엔 가짜 답으로 배선만.
**키**: `OPENAI_API_KEY` `GEMINI_API_KEY` `ANTHROPIC_API_KEY` `TRANSCRIPT_API_KEY` 는 **환경변수로만.** 코드·저장소·로그·응답에 넣지 않는다.

## 30분 단위

### T1 (0:00–0:30) 서버 뼈대 = devserve + /api
- `api/server.py`: `from tools.devserve import inject, resolve` 로 정적·주입은 **그대로 재사용**(§5.3). 거기에 `/api/*` 라우팅만 얹는다
- `GET /api/segments/{lecture}` : `raw/L{n}/segments.json` + `api/media.json` 의 `video` → `{lecture, video, segments}`
- `GET /api/source?anchor=` : §3 정규식 → **`s` 일치 + `t_start ≤ t ≤ t_end`** → 프레임·영상 URL. 없으면 404 `SOURCE_NOT_FOUND`
- `GET /api/quotes?q=` : `from tools.quote_search import search` 한 줄(이미 실측된 도구). **T1에 같이 연다 — 민수가 제일 먼저 붙는다**
- **완료 조건**: `curl '/api/source?anchor=L3%23s5%40t%3D330'` 가 `mock/source.json` 과 같은 모양을 뱉는다. 동욱에게 `board.sh status` 로 알린다.

### T2 (0:30–1:00) 필기 — 훅을 통과시키는 게 핵심
- `POST /api/notes` : `hooks/write_page_guard.py` 를 **그대로 호출**(재구현 금지), 입력에 `agent:"user"`. 경로 `wiki/notes/L{n}/s{k}.md` 만. `anchor` 는 **서버가 segments 에서 채운다**(요청의 anchor 무시). 8KB 초과 거부
- 거부되면 **422 + 훅이 준 이유 문자열 그대로** (다듬지 말 것 — 민수 화면의 증거)
- `GET /api/notes/{lecture}`
- **완료 조건**: 성공 1건 + 일부러 실패 1건(없는 k)의 응답을 `board.sh done` 에 붙인다.

### T3 (1:00–1:30) stats · history · models
- `stats`: `wiki/concepts` `wiki/lectures` 프론트매터 스캔(파서는 직접 20줄: `key: value`, `[a, b]`) → 페이지·status별·링크·필기 수 + `wiki/signals/coverage.md` 있으면 `coverage`
- `history`: `wiki/.history.jsonl` 꼬리 N줄 역순
- `review`(PRD §4.8): `segments.json` confidence<0.55 · 프론트매터 status grey/draft · `.history.jsonl` 에서 REJECTED 뒤 allow 된 path → 목록. `approve` 는 `agent:"user"` 로 `write_page_guard.py` 에 태워 `status: approved` 한 줄만 바꾼다
- `models`: `[{id:"fast",label},{id:"strong",label},{id:"gemini",label}]` — 라벨은 환경변수 `LLM_FAST` 등에서
- **완료 조건**: 민수 대시보드가 `USE_MOCK=false` 로 뜬다.

### T4 (1:30–2:00) `/api/qa` — 위키 한정 (§5.2)
1. `tools/grep_wiki.py` 로 질문 키워드 검색 + 걸린 페이지의 `links` 1홉 → 근거 문단 모음
2. 근거가 0개면 LLM을 **부르지 않고** `NO_GROUNDING`
3. `pipeline/llm.py complete(role=model, ...)` — 시스템 프롬프트 = `prompts/common.md` + `prompts/07-qa.md`. 근거 문단만 준다
4. 답변을 `hooks/qa_stop_guard.py` 에 태운다. 앵커 없으면 재생성 1회 → 그래도 없으면 `NO_GROUNDING`
5. `notes[]` = 답변 앵커와 같은 구간의 `wiki/notes/` (LLM에 주지 않고 코드로 붙인다)
- Gemini 가 429면 `fast` 로 자동 폴백, 응답 `model` 에 실제 쓴 것을 적는다
- **완료 조건**: "BFS 시간복잡도?" → 앵커 달린 답. "다익스트라?" → `NO_GROUNDING`.

### T5 (2:00–2:30) 유튜브 보충 추천 + 굳히기
- `api/youtube.py search(q)` : TranscriptAPI HTTP(문서 https://transcriptapi.com/docs/). **EC2에서 yt-dlp는 막힌다 — 쓰지 마라.** ① `professorChannel` 안에서 검색 ② 일반 검색 → §5.1 카드, professor 먼저, 합쳐 3개
- **모든 응답을 `raw/.ytcache/<sha1(q)>.json` 에 캐시**(크레딧 100개). 실패·키 없음 → `[]` (QA는 죽지 않는다)
- `/api/qa` 의 `videos` 와 `GET /api/youtube/search` 가 같은 함수를 쓴다
- 발표 질문 3개를 미리 한 번씩 던져 캐시를 데워 둔다. 서버 자동 재시작(`while true; do python3 api/server.py; sleep 1; done`)
- **완료 조건**: 발표 7분 동안 서버가 안 죽는다.

## 건드리면 안 되는 곳
`web/` · `site/` · `pipeline/` `hooks/` `tools/` 의 **내용** · `wiki/` `raw/` 손수정(API 경유 쓰기만)

## 기다리는 것
`pipeline/llm.py`(팀장 T2). 그 전까지 T4는 가짜 `complete()` 로 배선. 진짜 `wiki/` 도 기다리지 않는다 — 샘플이 커밋돼 있다.

## 계약을 바꾸고 싶으면
응답 필드를 **빼거나 이름을 바꾸면 프론트 두 개가 동시에 죽는다.** 추가는 자유, 변경·삭제는 `board.sh human`.
