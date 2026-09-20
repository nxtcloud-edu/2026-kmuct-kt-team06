# API 정리 (프론트용) — 2026-09-20, origin/wooseok 기준

**실행**: 저장소 루트에서 `python3 -m api.server 8000` → 정적(`/web` `/mock` `/raw` `public/`)과 `/api/*`가 **같은 오리진**. CORS 없음, fetch는 상대경로 `/api/...`.
**받는 법**: API는 아직 `origin/wooseok` 브랜치에만 있다 → `git fetch && git merge origin/wooseok` (사람이 직접).
**목 → 실서버**: 응답 모양은 `mock/*.json`과 같다. `USE_MOCK=false`로 바꾸면 끝.
**오류 봉투(전 경로 공통)**: `{"error":{"code":"...","message":"..."}}` — `res.ok`가 아니면 `error.code`로 분기.
**쓰기 경로 토큰**: 서버에 `DEMO_TOKEN`이 설정돼 있으면 POST 5종(notes·qa·review/approve·transcript/fix·ingest)에 헤더 `X-Demo-Token` 필요(없으면 401 `UNAUTHORIZED`).

## 읽기 (GET)
| 경로 | 응답 | 비고 |
|---|---|---|
| `/api/segments/{L3}` | `{lecture, video, segments:[{k,s,t_start,t_end,ocr,...}]}` | 400 `BAD_LECTURE`(형식 `^L\d+$`), 404 `SEGMENTS_NOT_FOUND` |
| `/api/source?anchor=L3%23s5@t=330` | `{lecture,k,s,t_start,t_end,frame,slide,video,ocr,exists,quote,date}` | **앵커 클릭 → 점프용.** `#`은 `%23`으로 인코딩. 없으면 404 `SOURCE_NOT_FOUND`(500 아님). `quote`는 전사 없으면 null |
| `/api/quotes?q=큐에 넣을 때` | `[{lecture,t,s,quote,anchor}]` | 교수 실제 발언 검색. LLM 안 씀, 즉시. q 500자 컷 |
| `/api/notes/{L3}` | `[{k,s,text,anchor,frame,updated}]` | 구간별 필기 |
| `/api/youtube/search?q=` | `[...]` | 교수 채널 먼저. 키 없거나 실패면 `[]`(에러 아님) |
| `/api/ingest/{job}` | `{lecture,stage,percent,detail,error}` | 업로드 진행률 폴링(1초). stage: stt→align→episodic→compile→build→`done`/`error`. 404 `JOB_NOT_FOUND` |
| `/api/stats` | `{lectures,pages,approved,draft,grey,links,notes,coverage,hooks}` | 상단 숫자 카드 |
| `/api/history?limit=10` | `[{ts,agent,tool,path,verdict,reason}]` 최신순 | **반려 로그 화면.** verdict `deny`→`allow` 흐름이 핵심 |
| `/api/models` | 모델 목록 | QA 모델 선택 |
| `/api/review` | `[{id,kind,lecture,slug,anchor,text,reason}]` | kind: `low_confidence`·`grey`·(deny 후 재작성)·`stt_uncertain` |
| `/api/dashboard?course=` | `{overall,stt,summary,measured,confusing,hooks}` | **측정 전 값은 null** → "측정 전"으로 표시 |

## 쓰기 (POST, JSON)
| 경로 | 요청 | 응답 |
|---|---|---|
| `/api/notes` | `{lecture:"L3", k:5, text:"..."}` | `{ok:true,path,anchor,frame}`. **anchor는 보내도 무시 — 서버가 구간표에서 채운다.** 400 `BAD_REQUEST`, 404 `SEGMENT_NOT_FOUND`, **422 `WRITE_REJECTED`**(훅 거부 — `message`를 그대로 사용자에게 보여줄 것) |
| `/api/qa` | `{question, model:"fast"\|"strong", context?:{...}}` | 성공: `{answer, anchors:[...], notes:[{anchor,text}], unanchored:[], model, videos}` · 근거 없음(**200**): `{answer:null, reason:"NO_GROUNDING", message, videos, ...}` → `answer===null`이면 `message` 표시. IP당 분당 10회 초과 429 `RATE_LIMITED` |
| `/api/review/approve` | `{id:"page:concepts/dfs"}` | 승인 결과. id는 `/api/review`의 `id` 그대로 |
| `/api/transcript/fix` | `{lecture, t_start, text}` | 전사 교정 저장 |
| `/api/ingest` | **multipart/form-data**: `files[]` + `title` + `course` | `{job, lecture}`. 허용 확장자 mp4 m4a mp3 wav txt md json pdf(415 `BAD_EXT`), 합계 500MB(413 `TOO_LARGE`), 400 `NO_FILES` |

## 프론트에서 자주 틀리는 것
1. 앵커를 쿼리에 넣을 때 `encodeURIComponent` 필수(`#`이 잘린다).
2. `/api/qa`의 "근거 없음"은 **에러가 아니라 200**이다. `res.ok`만 보고 성공 처리하면 빈 답이 뜬다.
3. 필기 저장 422는 버그가 아니라 제품 기능(훅이 막은 것)이다. 빨간 에러 말고 "저장 거부: <사유>"로.
4. 답변·위키 본문의 `[[L3#s5@t=330]]`는 글자 그대로 오는 앵커 → 정규식으로 찾아 클릭 요소로 바꾸고, 클릭 시 `/api/source`.
5. 글은 `textContent`로 넣는다(`innerHTML` 금지 — 전사·필기는 신뢰 못 하는 입력).
