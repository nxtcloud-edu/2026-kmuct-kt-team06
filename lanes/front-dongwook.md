# lane: front-dongwook (동욱) — 뷰어

**목표**: 위키 문장을 클릭하면 그 말이 나온 **슬라이드/판서 프레임과 영상의 그 초**로 점프한다. 영상은 구간 끝에서 스스로 멈춘다.
이게 발표 화면 1번·2번이다. 여기서 심사가 갈린다.

**소유**: `web/viewer/` 만. 다른 곳은 읽기만. 계약은 `CONTRACT.md`(§3 앵커, §5 API, §6 목, §7 이벤트).
**스택**: 빌드 없는 순수 HTML/CSS/JS. `npm`·번들러·프레임워크 금지. 클래스 접두사 `v-`.

## 30분 단위

### T1 (0:00–0:30) 뼈대 + 목으로 페이지 그리기
- `web/viewer/index.html` `viewer.css` `viewer.js`
- `const USE_MOCK = true` (CONTRACT §6 그대로)
- `/mock/pages.json` → 왼쪽 페이지 목록, `/mock/pages/<slug>.json` → 본문 `## Current` 문단 렌더
- 프론트매터 `status` 를 배지로: `approved` 초록 · `draft` 회색 · `grey` 빗금 + "검증 안 됨"
- **완료 조건**: 브라우저에서 페이지 하나가 보이고, 문단마다 앵커 `[[L3#s7@t=340]]` 가 파란 칩으로 보인다.

### T2 (0:30–1:00) 앵커 클릭 → 프레임 + 영상 점프
- 앵커 파싱은 CONTRACT §3 정규식만. `[[note:` `[[signal:` 은 링크로 만들지 않는다(그냥 회색 텍스트).
- 클릭 → `GET /api/source?anchor=...` (목: `/mock/source.json`) → 오른쪽에 `frame` 이미지 + 아래 영상 `currentTime = t`
- mp4면 `<video>`, 유튜브면 IFrame API `seekTo(t, true)`
- `window.dispatchEvent(new CustomEvent('anchor-open', {detail:{lecture,s,t,anchor}}))`
- **완료 조건**: 문장 클릭 → 프레임 뜨고 영상이 그 초로 간다. 3개 문장으로 시연 성공.

### T3 (1:00–1:30) 구간 끝에서 자동 정지 → 노트 슬롯 열기
- `GET /api/segments/L3` (목 `/mock/segments/L3.json`) 로 구간표를 들고 있는다
- mp4 `timeupdate` / 유튜브 `getCurrentTime()` 250ms 폴링 → `t_end` 를 지나면 `pause()`
- `segment-boundary` 이벤트 발사 (CONTRACT §7 스키마 그대로). `<aside id="note-slot">` 안은 **절대 건드리지 않는다**
- `note-saved` / `notes-closed` 를 받으면 `play()`
- 설정 체크박스 "구간 끝에서 멈추기" (기본 켬)
- **완료 조건**: 재생 → 경계에서 멈춤 → 민수 패널이 뜸 → 저장하면 이어서 재생. **민수와 둘이 같이 확인한다.**

### T4 (1:30–2:00) 진짜 API로 전환 + 역방향
- `USE_MOCK = false`. 깨지는 것 목록을 `board.sh status` 로 보고
- 역방향: 필기가 있는 구간은 영상 타임라인에 노란 마커, 클릭하면 그 구간으로
- **완료 조건**: 목 없이 T2·T3가 그대로 된다.

### T5 (2:00–2:30) 발표용 다듬기
- 강의 L1/L2/L3 전환 드롭다운
- 키보드: `←/→` 구간 이동, `space` 재생/정지
- 빈 상태·에러 토스트(§5) — 데모 중 흰 화면이 제일 위험하다
- **완료 조건**: 7분 발표 동선을 혼자 클릭으로 완주.

## 건드리면 안 되는 곳
`web/notes/` · `api/` · `pipeline/` · `hooks/` · `wiki/` · `raw/` · `CONTRACT.md`
`#note-slot` 의 **내부 DOM**(민수 것). 바깥 위치·크기만 네 CSS.

## 기다리는 것 / 그동안
API를 기다리지 않는다. `mock/` 이 §5와 같은 모양이라 0분부터 완성품을 만들 수 있다.
1:30 에 다 같이 `USE_MOCK=false`.

## 계약을 바꾸고 싶으면
직접 고치지 말고 `board.sh human "CONTRACT §7 이벤트 이름 바꾸자: A(그대로)/B(...)"`.
