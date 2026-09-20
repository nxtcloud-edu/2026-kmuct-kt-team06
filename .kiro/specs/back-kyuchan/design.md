# Design — back-kyuchan
- 이미 있는 것(실측됨): `hooks/write_page_guard.py`(R01~R11, 21케이스) · `frame_guard.py` · `qa_stop_guard.py` · `tools/align_slides.py` · `stt_grok.py` · `stt_agree.py` · `build_episodic.py` · `quote_search.py` · `hook_metrics.py` · `devserve.py` · `grep_wiki.py`. **다시 만들지 않는다.**
- 새로 만들 것: `pipeline/llm.py` → `pipeline/tools.py`(read_episodic · get_slide_text · read_page · write_page · search_wiki=grep) → `pipeline/orchestrator.py` → `pipeline/critic.py` → `pipeline/linker.py`(코드).
- 툴 루프: 공급자 무관한 직접 루프. 모델 출력의 tool_call 을 파싱 → AgentGuard → 실행 → 결과를 다음 메시지로. 최대 턴 ③20 ④10.
- 주제 단위 컴파일: 강의 노트를 한 번에 쓰지 않는다. `## N.` 주제 하나씩(슬라이드 범위) → 기존 파일에 그 주제를 더한 전체 본문으로 `write_page`. 실패해도 앞 주제는 남는다.
- ③ 프롬프트 = `prompts/common.md` + `03-compile.md` + 견본 `wiki/lectures/L3_그래프_탐색.md`(few-shot) + 해당 구간 episodic + 해당 슬라이드 교본 텍스트.
- 교수님 전사본은 OpenAI 무료 티어로 보내지 않는다(데이터 공유 조건). strong = Anthropic 또는 Gemini.
- 데모 데이터: `raw/L1` = 컴퓨터구조 week_2_2 (구간 15 · 슬라이드 PNG 21 · episodic 통과 ✅). 규찬이 손으로 쓴 Ch03 노트가 비교 대상(정답지 역할).
