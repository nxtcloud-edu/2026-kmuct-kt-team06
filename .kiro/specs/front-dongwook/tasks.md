# Tasks — front-dongwook  (각 30분. 끝날 때마다 `board.sh done`, 📦 커밋 제안 출력)
- [ ] 0. 띄우기: `cd site && npm ci && npx quartz build -d ../wiki -o ../public` → `python3 tools/devserve.py 8000` → `/lectures/l3_그래프_탐색` 확인
- [ ] 1. (T1) `viewer.js` 뼈대: IIFE · `init()` 직접 1회 + `nav` 리스너 · `#v-root` 를 `<html>` 에 · 앵커 칩 교체 — R1, R3
  - 완료: 견본 노트 앵커 10개가 칩. 탐색기로 다른 페이지에 가도 칩
- [ ] 2. (T2) **먼저 5분: 페이지 이동 후 `#v-root` 가 남는지 확인** → 미니 플레이어 + 미디어 어댑터 3종 + `/api/source`(목) 점프 + 슬라이드 표시 + `anchor-open`/`anchor-request` — R2
  - 완료: 칩 3개 연속 클릭 → 3번 점프. 페이지를 옮겨도 재생 유지
- [ ] 3. (T2) 드래그 → `원본 보기` — R4
- [ ] 4. (T3) split + 슬롯 2개 + 구간 끝 자동 정지 + `segment-boundary` / `note-saved` / `notes-closed` — R5.  **민수와 같이 확인**
- [ ] 5. (T4) `USE_MOCK=false` 전환 · `context-request` 응답 · 필기 있는 구간 노란 마커
- [ ] 6. (T5) 옵시디언풍 다크 테마(`site/quartz.config.yaml`) · Quartz 오른쪽 사이드바가 채팅과 겹치면 끄기 · 에러 토스트 · R6
