#!/usr/bin/env python3
"""WritePolicy 훅 다리 — hooks/write_page_guard.py 를 subprocess 로 호출만 한다.

훅 로직을 여기서 재구현하지 않는다(CONTRACT §1, tasks 지시). 서버는 판정만 받아서
allow 일 때만 실제 파일을 쓴다. 훅은 판정 + 감사로그(wiki/.history.jsonl)만 한다.

  ok, reason, rule = run_guard("user", "save_note", "wiki/notes/L3/s5.md", content)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "hooks" / "write_page_guard.py"


def run_guard(agent: str, tool: str, path: str = "", content: str = "",
              tool_input: dict | None = None, extra: dict | None = None):
    """훅에 이벤트를 태우고 (ok: bool, reason: str, rule: str|None) 를 준다.

    - path/content 를 주면 tool_input={path,content} 로 감싼다.
    - fix_transcript 처럼 다른 모양이면 tool_input 을 직접 넘긴다.
    - 훅 실행 자체가 실패하면 default deny (ok=False).
    """
    ti = tool_input if tool_input is not None else {"path": path, "content": content}
    event = {"agent": agent, "tool_name": tool, "tool_input": ti}
    if extra:
        event.update(extra)
    try:
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps(event, ensure_ascii=False),
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"hook execution failed: {e}", "R99_other"

    if proc.returncode != 0:
        return False, f"hook error: {(proc.stderr or '').strip()[:200]}", "R99_other"

    # 훅은 마지막 줄에 JSON 판정을 낸다.
    out = (proc.stdout or "").strip().splitlines()
    if not out:
        return False, "hook produced no decision", "R99_other"
    try:
        decision = json.loads(out[-1])
    except json.JSONDecodeError:
        return False, f"hook decision unparseable: {out[-1][:200]}", "R99_other"

    if decision.get("decision") == "allow":
        return True, "", None
    return False, decision.get("reason", "REJECTED"), decision.get("rule")
