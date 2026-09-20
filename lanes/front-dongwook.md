# lane: front-dongwook (동욱) — 앵커 · 미니 플레이어 · split

**목표**: Quartz가 그린 위키 위에서, 문장 끝 앵커를 누르면 **오른쪽 위 미니 플레이어가 그 초로 점프**한다. 미니 플레이어를 누르면 **split** 으로 펼쳐지고, 영상은 구간 끝에서 스스로 멈춘다. 발표 화면 1·2번.

**소유**: `web/viewer/` + `site/quartz.config.yaml`. **`site/quartz/` 소스는 절대 안 고친다.**
**읽을 것**: `CONTRACT.md` §3 앵커 · §5 API · §6 목 · **§7 전부(특히 7.2 Quartz와 같이 살기)**.
**스택**: 빌드 없는 순수 JS/CSS. 클래스 접두사 `v-`. 위키 렌더·탐색기·검색은 Quartz가 이미 한다 — 다시 만들지 마라.

## 0. 띄우기 (5분)
```bash
cd site && npm ci && npx quartz build -d ../wiki -o ../public && cd ..
python3 tools/devserve.py 8000
```
`http://localhost:8000/concepts/bfs` 가 뜨면 된 것. `web/viewer/viewer.js` 는 이미 모든 페이지에 주입된다(아직 파일이 없어서 404일 뿐).

## 30분 단위

### T1 (0:00–0:30) 앵커 칩
- `web/viewer/viewer.js` `viewer.css`. `const USE_MOCK = true` (§6)
- `init()` 을 만들고 **파일 끝에서 한 번 호출 + `document.addEventListener('nav', init)`** (§7.2). `init` 은 여러 번 불려도 안전하게
- 본문의 `a.internal` 중 텍스트가 `^L(\d+) > s(\d+)@t=(\d+)$` → `<button class="v-anchor" data-anchor="L3#s5@t=330">` 로 교체. 칩 글자는 `L3 · 5:30`
- **완료 조건**: bfs 페이지에서 앵커 5개가 칩으로 보이고, 탐색기로 dfs 로 넘어가도(새로고침 없이) 칩이 된다.

### T2 (0:30–1:00) 미니 플레이어 + 점프
- 오른쪽 위 고정 미니 플레이어 `#v-mini` (없으면 만든다). 칩 클릭 → `GET /api/source?anchor=` (목 `/mock/source.json`) → `video.kind` 가 mp4면 `<video>.currentTime=t`, youtube면 IFrame API `seekTo(t,true)` + 재생. `frame` 이 있으면 플레이어 아래 썸네일로
- **드래그 → `원본 보기`**(CONTRACT §7.2b): `selectionchange`/`mouseup` 에서 선택 영역 위에 작은 버튼 `#v-selbtn` 을 띄우고, 클릭하면 그 문단의 첫 `.v-anchor` 로 점프. 칩 없는 문단이면 안 띄운다
- 점프 시 `slide` 가 있으면 슬라이드 이미지, 없으면 `frame`. `video.kind:"audio"` 면 `<audio>` + 슬라이드 크게
- `anchor-open` 발사. `anchor-request` 수신(민수 채팅 패널이 쏜다) → 같은 점프
- 페이지를 옮겨도 미니 플레이어는 **살아 있어야** 한다(재생 끊기지 않게 body 직속)
- **완료 조건**: 칩 3개 + **드래그 1번**으로 영상(또는 녹음)이 점프하고 슬라이드가 같이 뜬다.

### T3 (1:00–1:30) split + 구간 끝 자동 정지
- 미니 플레이어 클릭 → `body.classList.add('v-split')`: Quartz `.center` 를 좁히고 오른쪽에 `#v-pane`(위=플레이어·프레임, 아래=`<aside id="note-slot">`). 접기 버튼
- `<aside id="chat-slot">` 도 여기서 만든다(맨 오른쪽 열, 접기 가능). **두 슬롯의 안쪽은 건드리지 않는다**
- `/api/segments/L3` 구간표 → mp4 `timeupdate` / 유튜브 250ms 폴링 → `t_end` 통과 시 `pause()` + (닫혀 있으면 split 열고) `segment-boundary` 발사
- `note-saved`/`notes-closed` → `play()`. "구간 끝에서 멈추기" 토글(기본 켬)
- **완료 조건**: 재생 → 멈춤 → 민수 패널 뜸 → 저장 → 재개. **민수와 같이 확인.**

### T4 (1:30–2:00) 진짜 API + `context-request`
- `USE_MOCK=false`. `context-request` 를 받으면 `context-reply {slug, anchor}` 로 지금 페이지·마지막 앵커를 답한다
- 필기 있는 구간은 타임라인에 노란 마커

### T5 (2:00–2:30) 다듬기
- `site/quartz.config.yaml` 색·폰트를 옵시디언풍 다크로(기본 다크 모드). Quartz 오른쪽 사이드바(TOC·그래프)가 LLM 패널과 겹치면 config 에서 끈다
- 좁은 화면에서 split·채팅 접힘 기본값, 에러 토스트
- **완료 조건**: 발표 동선을 클릭만으로 완주.

## 건드리면 안 되는 곳
`site/quartz/**` · `web/notes/` · `api/` · `pipeline/` · `hooks/` · `wiki/` · `raw/` · `public/` · 두 슬롯의 **안쪽 DOM**

## 기다리는 것
없다. `devserve.py` + `mock/` 으로 끝까지 간다. 1:30 에 다 같이 `USE_MOCK=false`.

## 계약을 바꾸고 싶으면
`board.sh human "CONTRACT §7.4 이벤트 ...: A(그대로)/B(...)"`.
