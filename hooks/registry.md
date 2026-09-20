# 훅 레지스트리 (고정 순서)

| 순서 | 훅 | 이벤트 | 타입 | 동작 |
|---|---|---|---|---|
| 1 | SkillsInject | 세션 시작 | 격리 | 에이전트 프롬프트에 skill 인덱스 주입 |
| 2 | AgentGuard | PreToolUse | 차단 | 에이전트별 허용 툴 Set 밖이면 block |
| 3 | WritePolicy | PreToolUse(write_page, append_episodic) | 차단 | write_page_guard.py |
| 4 | QAStop | Stop(qa) | 차단 | qa_stop_guard.py |
| 5 | CriticDispatch | PostToolUse(write_page, agent=compile) | 격리 | status:draft 페이지를 ④ 큐에 push |
| 6 | AuditLog | PostToolUse | 격리 | .history.jsonl (guard 안에 포함) |

차단 = 예외가 툴콜 거부로 모델에 전달. 격리 = 실패해도 로그만 남기고 계속.

허용 툴 Set
- align:   get_slide_text, get_paragraph, append_episodic
- compile: search_wiki, read_page, get_source, write_page
- critic:  read_page, get_source, grep_wiki
- linker:  read_page, write_page
- qa:      grep_wiki, search_wiki, read_page, get_source

grep_wiki는 읽기 전용이라 WritePolicy 대상이 아니다. 구현: tools/grep_wiki.py
