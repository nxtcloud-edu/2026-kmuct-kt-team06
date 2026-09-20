# Design — back-wooseok
- `api/server.py`: `http.server.ThreadingHTTPServer`. `from tools.devserve import inject, resolve, send_bytes` (저장소 루트에서 실행: `python3 -m api.server` 또는 `sys.path` 에 루트 추가). 라우팅은 `(METHOD, 정규식) → 함수` 표.
- `api/store.py`: 구간표·전사본·프론트매터 읽기(직접 짠 20줄 파서: `key: value`, `[a, b]`). 파일 mtime 캐시.
- `api/hook.py`: `run_guard(agent, tool, path, content) -> (ok, reason, rule)` — `subprocess` 로 `hooks/write_page_guard.py` 호출. **훅 로직을 복사하지 않는다.**
- `api/qa.py` · `api/youtube.py` · `api/review.py`. LLM 은 `pipeline/llm.py complete()` (팀장 T2). 그 전엔 가짜 `complete` 로 배선.
- 설정 `api/media.json`: `{ "L1": {"video": {"kind":"audio","src":"/raw/L1/audio.m4a"}}, "professorChannel": "UC…" }`
- 실행 위치와 무관해야 한다: 경로는 전부 저장소 루트 기준 절대 경로.
- 재빌드 경합: `public/` 파일이 잠깐 없으면 0.5초 뒤 1회 재시도.
