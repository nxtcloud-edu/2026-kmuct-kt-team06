# Requirements — front-minsu (LLM 패널 · 필기 · 대시보드)
기능명세 F-01 · F-05 · F-09 · F-10 · F-11 · F-13(카드) — `docs/SPEC.md`. 계약 `CONTRACT.md` §5 §6 §7.

## R1 교수님 발언 검색 (F-01) — 가장 먼저
- WHEN 사용자가 `교수님 발언 검색` 모드에서 2자 이상을 입력해 전송하면 THE SYSTEM SHALL `GET /api/quotes?q=` 결과를 시간순 카드(`“인용문” — L1 10:27 · s6 [재생]`)로 보여 준다.
- WHEN [재생]을 누르면 THE SYSTEM SHALL `anchor-request {anchor}` 를 발사한다.
- IF 검색어가 2자 미만이면 THEN THE SYSTEM SHALL 요청을 보내지 않고 추천 칩(시험·중요·꼭·연습)을 보여 준다.
- IF 카드의 `agree` 가 0.5 미만이면 THEN THE SYSTEM SHALL 🔈 경고를 붙인다.

## R2 위키에 묻기 (F-10)
- WHEN 사용자가 질문을 전송하면 THE SYSTEM SHALL `POST /api/qa {question, model, context}` 를 보내고 로딩을 표시하며 전송 버튼을 비활성화한다.
- THE SYSTEM SHALL 입력창을 패널 맨 아래에 고정하고 답변을 그 위로 쌓는다.
- THE SYSTEM SHALL 답변 속 `[[L3#s5@t=330]]` 를 칩으로 그리고, 칩 클릭 시 `anchor-request` 를 발사한다.
- IF 응답이 `reason:"NO_GROUNDING"` 이면 THEN THE SYSTEM SHALL "위키에 근거가 없습니다" 상자를 보여 준다.
- THE SYSTEM SHALL `notes[]` 를 답변 끝 "내 필기:" 블록으로, `videos[]` 를 "관련 영상" 카드로(교수님 채널 먼저) 그린다. 빈 배열은 아무것도 그리지 않는다.
- WHEN `＋` 를 누르면 THE SYSTEM SHALL `context-request` 를 발사하고 `context-reply` 를 첨부 칩으로 표시한다.

## R3 필기 (F-05)
- WHEN `segment-boundary` 를 받으면 THE SYSTEM SHALL `#note-slot` 에 슬라이드/프레임 · 입력창 · [저장][건너뛰기] · 그 구간의 기존 필기를 보여 준다.
- WHEN [저장]을 누르면 THE SYSTEM SHALL `POST /api/notes {lecture,k,text}` 후 성공 시 `note-saved` 를 발사한다.
- IF 응답이 422 `WRITE_REJECTED` 면 THEN THE SYSTEM SHALL `error.message` 를 **글자 그대로** 빨간 상자에 보여 주고 입력 내용을 유지한다.
- IF 입력이 비었거나 8KB 를 넘으면 THEN THE SYSTEM SHALL 보내기 전에 막는다.
- THE SYSTEM SHALL 모든 사용자·모델 글을 `textContent` 로 넣는다.

## R4 대시보드 · 검토함 (F-09 · F-11)
- THE SYSTEM SHALL `web/notes/dashboard.html` 에서 `/api/stats` 의 `hooks` 를 5초마다 갱신해 보여 준다: 시도·통과·거부 · **거부 후 재작성 통과** · 한 번에 통과 비율 · 끝내 막힌 시도 · 규칙별 막대 · 에이전트별 · 앵커·인용 수 · 최근 10줄(deny 빨강).
- THE SYSTEM SHALL 맨 위에 "검토 필요 N개"와 카드(사유 배지 · 문장 · [원본 보기] · [승인])를 보여 준다.
- WHEN [승인]을 누르면 THE SYSTEM SHALL `POST /api/review/approve {id}` 후 카드를 지우고 N을 줄인다. 422 면 사유를 보여 준다.
- THE SYSTEM SHALL confidence 류 숫자를 확률처럼 표기하지 않는다("⚠ 먼저 확인" 배지).
