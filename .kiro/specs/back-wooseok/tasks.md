# Tasks — back-wooseok
- [ ] 1. (T1) 서버 뼈대(devserve 재사용) + `/api/quotes` + `/api/segments` + `/api/source` — R1, R2.  완료: curl 3종이 `mock/` 과 같은 모양. `/web/../.env` → 404
- [ ] 2. (T2) `POST /api/notes`(훅 통과) + `GET /api/notes` — R3.  완료: 성공 1건 + 일부러 실패 1건(없는 k)의 응답을 `board.sh done` 에
- [ ] 3. (T3) `/api/stats`(+hooks) · `/api/history` · `/api/models` · `/api/review` · `approve` — R2, R5
- [ ] 4. (T4) `/api/qa` — R4.  프론트 둘의 `USE_MOCK=false` 전환을 같이 본다
- [ ] 5. (T5) `api/youtube.py` + 캐시 — R6 · `DEMO_TOKEN` · 자동 재시작 루프 · 발표 질문 3개 캐시 데우기
- [ ] 6. (T3 뒤, 여유 순) `/api/source` 에 `quote`·`date` — R9 (5분) → `/api/dashboard` + `/api/transcript/fix` — R8 → `/api/ingest` + 진행률 — R7 (가장 무겁다. 시간이 없으면 서버에 미리 둔 폴더를 고르는 방식으로 줄인다)
