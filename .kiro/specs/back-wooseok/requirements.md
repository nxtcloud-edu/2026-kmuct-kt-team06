# Requirements — back-wooseok (서버 · API)
기능명세 F-01 · F-05 · F-09 · F-10 · F-11 · F-13 — `docs/SPEC.md`. 계약 `CONTRACT.md` §3 §4 §5(특히 5.2~5.4).

## R1 단일 서버
- THE SYSTEM SHALL 한 프로세스에서 `public/`(HTML에는 주입) · `/web` `/mock` `/raw` · `/api/*` 를 같은 오리진으로 서빙한다.
- THE SYSTEM SHALL 정적 파일을 `tools/devserve.py` 의 `resolve()`·`send_bytes()`·`inject()` 로만 서빙한다(점 파일·폴더 탈출 차단, Range 206).
- IF 환경변수 `DEMO_TOKEN` 이 있으면 THEN THE SYSTEM SHALL `POST /api/notes`·`/api/qa`·`/api/review/approve` 에서 `X-Demo-Token` 이 다르면 401 을 준다.
- THE SYSTEM SHALL 모든 오류를 `{"error":{"code","message"}}` 로 준다. 500 에 스택트레이스를 싣지 않는다.

## R2 읽기 API
- WHEN `GET /api/quotes?q=` 를 받으면 THE SYSTEM SHALL `tools.quote_search.search(q)` 결과를 준다.
- WHEN `GET /api/source?anchor=` 를 받으면 THE SYSTEM SHALL `s` 가 같고 `t_start ≤ t ≤ t_end` 인 구간을 찾아 `{lecture,k,s,t_start,t_end,frame|null,slide|null,video,ocr,exists}` 를 주고, 없으면 404 `SOURCE_NOT_FOUND` 를 준다.
- THE SYSTEM SHALL `lecture` 값으로 `^L\d+$` 만 받는다.
- THE SYSTEM SHALL `/api/segments/{lecture}` · `/api/notes/{lecture}` · `/api/stats`(+`hooks` = `tools.hook_metrics.metrics()`) · `/api/history?limit=` · `/api/models` 를 CONTRACT §5 모양으로 준다.

## R3 필기 저장 (F-05)
- WHEN `POST /api/notes {lecture,k,text}` 를 받으면 THE SYSTEM SHALL 구간표에서 앵커(`t=int(t_end)`, `t<t_start` 면 올림)와 프레임/슬라이드를 채운 노트를 만들어 **`hooks/write_page_guard.py` 에 `agent:"user"`, `tool_name:"save_note"` 로 태우고**, allow 일 때만 파일을 쓴다.
- IF 훅이 거부하면 THEN THE SYSTEM SHALL 422 `WRITE_REJECTED` 와 훅의 `reason` 원문을 준다.
- THE SYSTEM SHALL 요청 본문의 `anchor` 필드를 무시한다.

## R4 위키에 묻기 (F-10)
- WHEN `POST /api/qa` 를 받으면 THE SYSTEM SHALL `tools/grep_wiki.py` + 링크 1홉으로 근거 문단을 모은다.
- IF 근거가 0개면 THEN THE SYSTEM SHALL 모델을 부르지 않고 `{answer:null, reason:"NO_GROUNDING", videos}` 를 준다.
- THE SYSTEM SHALL 답변을 `hooks/qa_stop_guard.py` 에 태우고, 앵커가 없으면 1회 재생성 후에도 없으면 `NO_GROUNDING` 을 준다.
- THE SYSTEM SHALL `notes[]` 를 모델이 아니라 코드로(답변 앵커와 같은 구간의 필기) 붙인다.
- THE SYSTEM SHALL IP당 분당 10회로 제한하고 질문을 500자에서 자른다.

## R5 검토함 (F-11)
- WHEN `GET /api/review` 를 받으면 THE SYSTEM SHALL 구간 confidence 낮은 순 5(`reviewed` 제외) · `status: grey|draft` 페이지 · history 의 deny→allow 경로 · `agree<0.5` 문장을 CONTRACT §5 모양으로 준다.
- WHEN `POST /api/review/approve {id}` 를 받으면 THE SYSTEM SHALL `status:` 한 줄만 바꾼 본문을 `agent:"user"` 로 훅에 태운다(구간 항목은 `segments.json` 의 `reviewed:true`).

## R6 유튜브 보충 (F-13)
- THE SYSTEM SHALL `api/youtube.py search(q)` 에서 TranscriptAPI 를 HTTP 로 부르고(교수 채널 먼저), 응답을 `raw/.ytcache/<sha1>.json` 에 캐시한다.
- IF 키가 없거나 호출이 실패하면 THEN THE SYSTEM SHALL `[]` 를 돌려주고 QA 응답은 정상으로 준다.

## R7 자료 불러오기 (F-17, `docs/DESIGN.md` §4~5)
- WHEN `POST /api/ingest` 로 파일들과 `title`·`course` 를 받으면 THE SYSTEM SHALL 확장자 화이트리스트(mp4 m4a mp3 wav txt md json pdf)와 합계 500MB 를 검사하고, **서버가 지은 파일명**으로 `raw/L{n}/` 에 저장한 뒤 `{job, lecture}` 를 즉시 돌려준다.
- THE SYSTEM SHALL 파이프라인을 백그라운드 스레드로 돌리고 `GET /api/ingest/{job}` 에서 실제 단계(`upload→stt→align→episodic→compile→build→done`)와 percent 를 준다.
- IF 어느 단계가 실패하면 THEN THE SYSTEM SHALL `stage:"error"` 와 사람이 읽을 `error` 를 주고 서버는 계속 돈다.
- IF 전사본 파일이 없으면 THEN THE SYSTEM SHALL `tools/stt_grok.py` 로 전사한다. 슬라이드 교본은 EC2에 lecture-md 가 없으므로 `pdftotext -f k -l k` 로 `<!-- page k -->` 구분 md 를 만든다.

## R8 대시보드 수치 · 전사 수정 (F-18)
- WHEN `GET /api/dashboard?course=` 를 받으면 THE SYSTEM SHALL `{overall, stt, summary, measured, confusing[], hooks}` 를 준다. `stt` = `agree` 의 문장 길이 가중 평균(수정된 문장은 1.0), `summary` = 비평 통과율 × 인용 대조 통과율, `overall` = 둘의 조화평균. 측정 전 값은 `null`.
- WHEN `POST /api/transcript/fix {lecture,t_start,text}` 를 받으면 THE SYSTEM SHALL `tool_name:"fix_transcript"`, `agent:"user"` 로 훅에 태우고, allow 면 `raw/L{n}/corrections.jsonl` 에 덧붙이고 그 문장의 `agree`=1.0·`reviewed`=true 로 갱신한다. 원문은 지우지 않는다.

## R9 출처 말풍선 (F-19)
- THE SYSTEM SHALL `/api/source` 응답에 `quote`(그 초가 속한 전사 문장, 120자에서 자름)와 `date` 를 싣는다.
