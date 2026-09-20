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

## 음성 인식 신뢰도 (STT confidence = `agree`) — 2026-09-20 13:45 추가
**정의**: 모델이 말하는 확신도가 아니다. 같은 녹음을 **두 STT(다글로 × Grok)**로 전사해, 문장/문단마다 글자 단위로 얼마나 겹치는지를 0~1로 잰 값(`tools/stt_agree.py`, LLM 0회). 둘이 다르게 받아 적은 곳 = 잘못 들었을 가능성이 높은 곳.
**문턱**: `agree < 0.5` = 경고 · 🗣 인용 금지 · 검토함 카드 / `0.5 ≤ agree < 0.8` = 🔈 표시만 / `null` = 측정 전(6자 미만이거나 비교 전사본 없음).
**데이터 위치**: `raw/L{n}/transcript.json` 각 행의 `agree` 필드. L1은 13:45에 채움(문단 58개 전부 측정, 길이 가중 평균 0.86, 최저 0.56, 0.8 미만 15개, 0.5 미만 0개).

| 어디서 받나 | 모양 | 프론트가 할 일 |
|---|---|---|
| `GET /api/dashboard` | `stt`: agree의 **문장 길이 가중 평균**(사람이 고친 문장은 1.0). 전사본에 agree가 하나도 없으면 `null` · `measured.stt`: true/false · `confusing`: `[{lecture,t_start,t_end,text,agree,anchor}]` agree 낮은 순 | `stt===null`이면 "측정 전". 숫자는 **확률처럼 쓰지 말 것** — "전사 일치율 86%"라고 표기. `confusing` 카드의 [재생]=`anchor` 로 점프 |
| `GET /api/review` | `kind:"stt_uncertain"` 카드: `{id:"stt:L1:<t_start>", text, reason:"전사 일치율 0.42 — 🗣 인용 금지", anchor:null}` — `agree<0.5` 이고 아직 안 고친 문장만 | 카드에 [고치기] → 아래 fix |
| `POST /api/transcript/fix` | 요청 `{lecture, t_start, text}` → `{ok:true}`. 훅(`fix_transcript`, user) 통과 시 `raw/L{n}/corrections.jsonl`에 덧붙이고 그 문장은 `reviewed` = 점수 1.0. 400 `BAD_LECTURE`·`BAD_REQUEST`, 422 `WRITE_REJECTED` | 저장 후 dashboard·review 다시 불러 숫자·카드 갱신 |
| 위키 본문 | 컴파일 단계가 `agree<0.5` 문장을 🗣 인용으로 쓰지 않는다(episodic에 `🔈?` 표시) | 없음 |
| `GET /api/quotes` | ⚠️ SPEC(F-01 AC4)은 `agree\|null` 을 같이 주라고 하지만 **현재 코드는 안 준다**(`tools/quote_search.py`에 agree 없음) | 지금은 🔈 표시 못 함. 필요하면 백엔드에 요청 |

**알려진 한계(발표에서 그대로 말할 것)**: 불일치의 상당수는 오인식이 아니라 **영어 전문용어 표기 차이**다(한쪽은 "Make the common case fast", 다른 쪽은 "메이크 더 커먼 케이스 패스트"). 그래서 이 값은 "틀렸다"가 아니라 **"사람이 먼저 볼 순서"**로만 쓴다.

## 변경 기록 (09-20 오후) — 실서버에서 확인한 것
- `GET /api/quotes` 결과에 **`agree`**(전사 일치율, 없으면 `null`)와 **`course`** 추가. `agree===null` 은 "측정 전"이지 "낮음"이 아니다. `agree<0.5` 일 때만 🔈.
- `GET /api/source` 의 `video` 는 **`null` 일 수 있다**(녹음 파일이 없는 강의) → 플레이어를 만들지 말고 안내문 + 슬라이드·발언만. 있으면 `{kind:"audio"|"mp4"|"youtube", src}`. 재생 위치는 `src#t=<초>` + `loadedmetadata`/`canplay` 에서 한 번 더 확인(한 번만 seek 하면 0초부터 트는 브라우저가 있다).
- **숨기기/복원은 서버 상태**: `POST /api/review/hide {id:"page:<slug>"}` → `status: grey`, `POST /api/review/approve` 로 복원. 뷰어는 목록의 `status==="grey"` 를 숨김·휴지통으로 취급한다(다른 브라우저에서도 같게 보인다).
- 뷰어의 페이지 목록 = `/web/viewer/library.local.json`(서버가 위키로 생성: `{title,status,type,slug,course,body}`), 없으면 `/web/viewer/library.json`(견본).
- 샘플(mock) 모드는 기본 **꺼짐**. API 없이 화면만 만들 때 설정(⚙)에서 켠다.
- 🚧 `POST /api/ingest`: 슬라이드 **PDF 필수** + (타임스탬프 전사본 `.md`/`.json` **또는** 녹음·영상 — 없으면 서버가 Grok STT). `multipart/form-data` 는 `fetch` 에 `FormData` 를 그대로 넘기고 Content-Type 을 직접 넣지 않는다. 진행: `GET /api/ingest/{job}` 의 `stage`(upload→stt→align→episodic→compile→build→done|error)·`percent`·`detail`. 강의 1편 10~20분.
