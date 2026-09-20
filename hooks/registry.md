# 훅 레지스트리 (고정 순서) — 2026-09-20 개정

| 순서 | 훅 | 이벤트 | 타입 | 상태 | 동작 |
|---|---|---|---|---|---|
| 1 | SkillsInject | 에이전트 시작 | 격리 | ⬜ | 프롬프트에 skill 인덱스(name: path)만 주입 |
| 2 | ContextInject | ③⑦ 호출 직전 | 격리 | ⬜ | signals·notes 를 `<untrusted_context>` 로 감싸 주입 |
| 3 | AgentGuard | PreToolUse | 차단 | ⬜ | 아래 「허용 툴 Set」 밖이면 block |
| 4 | **WritePolicy** | PreToolUse(write_page, append_episodic, save_note) | 차단 | ✅ 실측 | `write_page_guard.py` — 쓰기 루트·프론트매터·강의 노트 포맷·앵커 존재·가짜 앵커·콜아웃 밖 링크·HTML·status-only 승인. 거부마다 **규칙 ID(R01~R11)** |
| 5 | QAStop | Stop(qa) | 차단 | ✅ | `qa_stop_guard.py` — 앵커 없는 답변 거부 |
| 6 | **FrameGuard** | ① 종료 | 차단 | ✅ 실측 | `frame_guard.py` — 구간표 스키마·겹침·빈틈·프레임 또는 슬라이드 PNG 존재. 통과 못 하면 ②로 못 간다 |
| 7 | CriticDispatch | PostToolUse(write_page, agent=compile) | 격리 | ⬜ | draft 페이지를 ④ 큐에 |
| 8 | **AuditLog** | 모든 판정 | 격리 | ✅ 실측 | `wiki/.history.jsonl` — allow/deny, rule, reason, attempt, run, anchors, quotes, 전후 본문·해시. 집계 `tools/hook_metrics.py` |
| 9 | CoverageCheck | ③ 종료 | 격리 | ✅ | `tools/coverage.py` — signals 항목 grep → `signals/coverage.md` + covered/total. 필기만 달린 구간도 목록에 |

차단 = 거부 사유가 모델에게 돌아가 그 부분만 다시 쓴다. 격리 = 실패해도 로그만 남기고 계속. **default deny.**
오케스트레이터는 훅을 부를 때 `agent`, `attempt`(1부터), `run`(실행 id) 을 실어 보낸다 → 대시보드의 "거부 후 재작성 통과" 숫자가 여기서 나온다.

## 단계별 모델 사용 (2026-09-20: ②⑤는 코드로 내렸다)
| 단계 | 누가 | 도구 |
|---|---|---|
| ① 적재 | **코드** | lecture-md(교본) · `stt_grok.py`/다글로 → transcript.json · `stt_agree.py` · `align_slides.py` → segments.json · pdftoppm → slides/ · FrameGuard |
| ② 정렬 | **코드** | `build_episodic.py` — 구간마다 문장+앵커. agent=align 으로 WritePolicy 통과 |
| ③ 컴파일 | 모델(strong) | read_episodic, get_slide_text, read_page, write_page, youtube_search, resolve_reference |
| ④ 비평 | 모델(fast, 2종) | read_page, get_source — 문단별 타입 질문 JSON. 판정은 코드 |
| ④b 인용 대조 | **코드** | 🗣 인용 ↔ 그 구간 전사본 문자 유사도 |
| ⑤ 링커·인덱스 | **코드** | 본문의 `[[concepts/…]]` 를 모아 `links:` 와 `index.md` 갱신 |
| ⑦ 질의응답 | 모델(fast) | grep_wiki, read_page, get_source → QAStop |
| 발언 검색 · 검토함 · 지표 | **코드** | `quote_search.py` · review 집계 · `hook_metrics.py` · `coverage.py` · `stats.py`(=/api/stats payload) |

## 허용 툴 Set (AgentGuard)
- align:   append_episodic
- compile: read_episodic, get_slide_text, read_page, search_wiki, write_page, youtube_search, resolve_reference
- critic:  read_page, get_source, grep_wiki
- qa:      grep_wiki, read_page, get_source
- user:    save_note, approve(status 한 줄)
- signal-ingest: write_page(wiki/signals/ 만)
