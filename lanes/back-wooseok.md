# lane: back-wooseok (우석) — API · 서빙

**목표**: `wiki/*.md` 와 `raw/` 를 프론트가 쓸 수 있는 JSON으로 내보내고, 필기 저장(`POST /api/notes`)을 **WritePolicy 훅을 통과시켜** 받는다.
프론트 둘이 1:30에 `USE_MOCK=false` 로 붙는다. **그 전까지 §5의 8개 엔드포인트가 살아 있는 게 이 레인의 전부다.**

**소유**: `api/` 만. `wiki/` `raw/` `pipeline/` `hooks/` 는 **읽기만**(import 는 해도 되지만 수정 금지).
**스택**: Python 표준 라이브러리 우선. 이미 설치된 것 외에 새 패키지 설치 금지(현장 네트워크에서 시간 날린다).
계약: `CONTRACT.md` §3 앵커 · §4 스키마 · §5 API.

## 30분 단위

### T1 (0:00–0:30) 서버 + 정적 + `/api/pages`
- `api/server.py` — `http.server` 또는 이미 깔린 FastAPI 중 **빠른 쪽**. 판단은 네가.
- 정적: `/` → `web/viewer/index.html`, `/web/**`, `/mock/**`, `/raw/**`
- `GET /api/pages` : `wiki/concepts/*.md` + `wiki/lectures/*.md` 프론트매터 파싱 → 목록
- 프론트매터 파서는 직접 20줄로 쓴다(YAML 패키지 기다리지 말 것). `key: value` 와 `[a, b]` 만 지원하면 충분
- **완료 조건**: 브라우저에서 `/api/pages` 가 커밋된 샘플 페이지들을 JSON으로 뱉는다.

### T2 (0:30–1:00) `/api/pages/{slug}` + `/api/segments` + `/api/source`
- 페이지 본문을 `## Current` / `## History` 로 쪼개고, 문단마다 CONTRACT §3 정규식으로 앵커 배열을 뽑아 `current[]` 로
- `GET /api/segments/{lecture}` : `raw/L{n}/segments.json` 을 `{lecture, video, segments}` 로 감싸기. `video` 는 `api/media.json` 같은 작은 설정 파일에서 읽는다
- `GET /api/source?anchor=...` : **`s` 일치 + `t_start ≤ t ≤ t_end`** 인 구간을 찾아 프레임·슬라이드·영상 URL 로 변환. 없으면 404 `SOURCE_NOT_FOUND`
- **완료 조건**: 동욱이 `USE_MOCK=false` 로 바꿔도 T2 화면이 그대로 된다. 직접 확인해 주고 `board.sh status` 로 알린다.

### T3 (1:00–1:30) `POST /api/notes` — 훅을 통과시키는 게 핵심
- `hooks/write_page_guard.py` 를 **그대로 호출**한다(복붙·재구현 금지). 입력 JSON에 `agent: "user"` 를 실어 준다
- 경로는 `wiki/notes/L{n}/s{k}.md` 패턴만. `anchor` 는 **서버가 segments 에서 채운다**(요청 본문의 anchor 는 무시)
- 프론트매터 `type: note, anchor, frame, trust: user, updated` · 본문 8KB 초과면 거부
- 훅이 거부하면 **422 + 훅이 준 이유 문자열 그대로**. 이유를 예쁘게 다듬지 말 것 — 민수 화면이 이걸 증거로 쓴다
- `GET /api/notes/{lecture}` 도 같이
- **완료 조건**: 저장 성공 1건 + **일부러 실패** 1건(존재하지 않는 t)을 만들어 422 메시지를 캡처해 `board.sh done` 에 붙인다.

### T4 (1:30–2:00) `/api/stats` · `/api/history` + 통합
- `stats`: 페이지 수·status별·링크 수·필기 수·`coverage` (`wiki/signals/coverage.md` 있으면 파싱, 없으면 `{covered:0,total:0}`)
- `history`: `.history.jsonl` 꼬리 N줄 역순
- 프론트 둘의 `USE_MOCK=false` 전환을 **같이 앉아서** 본다. CORS·404 경로 어긋남이 여기서 다 나온다
- **완료 조건**: 프론트 두 화면이 목 없이 돈다.

### T5 (2:00–2:30) `/api/qa` (스트레치) 또는 굳히기
- 여유 있으면 `POST /api/qa`: `tools/grep_wiki.py` 로 검색 → Bedrock Haiku 로 답 + 앵커. 답변에 앵커가 없으면 `hooks/qa_stop_guard.py` 가 막는다
- 여유 없으면 **501 그대로 두고** 대신: 서버 죽었을 때 자동 재시작 스크립트 + 발표용 데이터 다시 로드 확인
- **완료 조건**: 발표 7분 동안 서버가 안 죽는다. 그게 T5의 진짜 목표다.

## 건드리면 안 되는 곳
`web/` (프론트 둘) · `pipeline/` `hooks/` `tools/` (팀장) · `wiki/` `raw/` 의 **내용**
훅이 마음에 안 들어도 고치지 말고 `board.sh blocked` / `board.sh human`.

## 기다리는 것 / 그동안
파이프라인이 만드는 진짜 `wiki/` 를 기다리지 않는다 — 저장소에 **샘플 페이지 3개가 이미 커밋되어 있다**. 그걸 파싱하면 된다.
파이프라인이 페이지를 더 만들면 코드 수정 없이 그냥 늘어나야 한다(디렉터리 스캔).

## 계약을 바꾸고 싶으면
응답 필드를 **빼거나 이름을 바꾸면 프론트 두 개가 동시에 죽는다.** 추가는 자유, 변경·삭제는 `board.sh human`.
