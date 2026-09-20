#!/usr/bin/env python3
"""집계 API — /api/stats · /api/history · /api/models. 전부 기존 데이터에서 계산, LLM 없음."""
import json

from api import store, wiki_read
from tools import hook_metrics

ROOT = store.ROOT
HISTORY = ROOT / "wiki" / ".history.jsonl"

MODELS = [
    {"id": "fast", "label": "빠름 · gpt-5.4-nano"},
    {"id": "strong", "label": "정확 · gpt-5.4"},
    {"id": "gemini", "label": "제미나이 · gemini-2.5-pro"},
]


def stats() -> dict:
    """{lectures,pages,approved,draft,grey,links,notes,coverage,hooks}.

    팀장이 tools/stats.py 를 커밋하면(board #back-kyuchan: "payload = from tools.stats import stats")
    그걸 정본으로 쓴다. 아직 없으면 위키에서 직접 계산 + hook_metrics 로 채운다(§8 아무도 안 기다림).
    """
    try:
        from tools.stats import stats as _team_stats  # 팀장 산출물
        payload = _team_stats()
        if isinstance(payload, dict) and "hooks" in payload:
            return payload
        if isinstance(payload, dict):  # hooks 만 빠졌으면 붙여 준다
            payload.setdefault("hooks", hook_metrics.metrics())
            return payload
    except Exception:
        pass
    s = wiki_read.page_stats()
    s["hooks"] = hook_metrics.metrics()  # hooks = tools.hook_metrics.metrics() 그대로(CONTRACT §5)
    return s


def history(limit: int = 10) -> list:
    """[{ts, agent, tool, path, verdict, reason}] 최신순(CONTRACT §5)."""
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append({
            "ts": r.get("ts"),
            "agent": r.get("agent"),
            "tool": r.get("tool"),
            "path": r.get("path"),
            "verdict": r.get("verdict"),  # allow|deny (화면 표기만 REJECTED)
            "reason": r.get("reason"),
        })
    rows.reverse()  # 최신순
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def models() -> list:
    return MODELS
