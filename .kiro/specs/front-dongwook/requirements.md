# Requirements — front-dongwook (뷰어)
기능명세 F-02 · F-03 · F-04 · F-14(표시) — `docs/SPEC.md`. 계약 `CONTRACT.md` §3 §5 §6 §7.

## R1 앵커 칩 (F-02)
- WHEN Quartz의 `nav` 이벤트가 발생하면 THE SYSTEM SHALL 본문의 `a.internal` 중 텍스트가 `^L(\d+) > s(\d+)@t=(\d+)$` 인 것을 `<button class="v-anchor" data-anchor="L3#s5@t=330">` 으로 교체한다.
- WHEN 스크립트가 처음 로드되면 THE SYSTEM SHALL `nav` 를 기다리지 않고 `init()` 을 한 번 실행한다.
- IF `init()` 이 같은 페이지에서 다시 불리면 THEN THE SYSTEM SHALL 칩·플레이어·슬롯을 중복 생성하지 않는다.
- THE SYSTEM SHALL `[[note:` `[[signal:` 형태를 칩으로 만들지 않는다.

## R2 점프 (F-02)
- WHEN 사용자가 칩을 누르면 THE SYSTEM SHALL `GET /api/source?anchor=` 의 `video` 로 플레이어를 그 초로 옮겨 재생하고, `slide` 가 있으면 슬라이드를, 없으면 `frame` 을 보여 준다.
- THE SYSTEM SHALL `video.kind` 가 `mp4`·`audio`·`youtube` 인 세 경우를 모두 처리한다.
- WHEN `anchor-request` 이벤트를 받으면 THE SYSTEM SHALL 칩 클릭과 같은 점프를 한다.
- WHEN 점프가 끝나면 THE SYSTEM SHALL `anchor-open {lecture,s,t,anchor}` 을 발사한다.
- IF 메타데이터가 아직 로드되지 않았으면 THEN THE SYSTEM SHALL `loadedmetadata` 뒤에 seek 한다.
- IF `/api/source` 가 404 면 THEN THE SYSTEM SHALL 토스트를 띄우고 계속 동작한다.

## R3 살아남는 UI (CONTRACT §7.3)
- THE SYSTEM SHALL 우리 UI의 뿌리 `#v-root` 를 `document.documentElement` 에 붙이고, 상태 클래스를 `<html>` 에 둔다.
- WHILE 미디어가 재생 중일 때 WHEN 사용자가 다른 위키 페이지로 이동하면 THE SYSTEM SHALL 재생을 끊지 않는다.

## R4 드래그 → 원본 보기 (F-03)
- WHEN 사용자가 본문 글자를 선택하면 THE SYSTEM SHALL 선택 영역 위에 `원본 보기` 버튼을 띄운다.
- WHEN 그 버튼을 누르면 THE SYSTEM SHALL 선택이 속한 `p`/`li`/`blockquote` 의 첫 칩으로, 없으면 같은 `h2` 주제 안에서 바로 앞 칩으로 점프한다.
- IF 그 주제에 칩이 하나도 없으면 THEN THE SYSTEM SHALL 버튼을 띄우지 않는다.

## R5 split · 자동 정지 (F-04)
- WHEN 사용자가 미니 플레이어를 누르면 THE SYSTEM SHALL `html.v-split` 로 전환해 위=플레이어·슬라이드, 아래=`<aside id="note-slot">` 을 보여 준다.
- THE SYSTEM SHALL `<aside id="note-slot">` 과 `<aside id="chat-slot">` 을 `#v-root` 안에 만들고 그 안쪽 DOM은 건드리지 않는다.
- WHILE "구간 끝에서 멈추기"가 켜져 있을 때 WHEN 재생 위치가 현재 구간의 `t_end` 를 지나면 THE SYSTEM SHALL 일시정지하고 `segment-boundary {lecture,k,s,t_end,frame}` 을 발사한다.
- WHEN `note-saved` 또는 `notes-closed` 를 받으면 THE SYSTEM SHALL 재생을 이어 간다.
- WHEN `context-request` 를 받으면 THE SYSTEM SHALL `context-reply {slug, anchor|null}` 로 답한다.

## R6 음성 불확실 표시 (F-14, 여유 시)
- IF 점프한 문장의 `agree` 가 0.5 미만이면 THEN THE SYSTEM SHALL "음성 인식이 불확실합니다 — 원본을 들어 보세요"를 플레이어 아래에 표시한다.
