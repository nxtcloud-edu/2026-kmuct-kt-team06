#!/usr/bin/env python3
"""훅 로그(wiki/.history.jsonl) → 대시보드 숫자. LLM 없음.   python3 tools/hook_metrics.py [history 경로]

from tools.hook_metrics import metrics   # api/ 의 /api/stats 가 그대로 쓴다
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = {"R01_write_root": "쓰기 루트 밖", "R02_path_escape": "경로 위조", "R03_frontmatter": "프론트매터 누락",
         "R04_no_anchor": "앵커·형식 없음", "R05_dead_anchor": "없는 구간 앵커", "R06_fake_anchor": "가짜·범위 앵커",
         "R07_external_link": "콜아웃 밖 링크", "R08_unsafe_html": "HTML 삽입", "R09_status_only": "승인인 척 본문 수정",
         "R10_size": "크기 초과", "R11_linker_body": "링커 본문 변경", "R99_other": "기타"}


def metrics(path=None):
    path = Path(path) if path else ROOT / "wiki/.history.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []
    allow = [r for r in rows if r["verdict"] == "allow"]
    deny = [r for r in rows if r["verdict"] == "deny"]
    # 에피소드 = 같은 (에이전트, 경로)에 대한 연속 시도. allow 가 나오면 닫힌다
    seq = defaultdict(list)
    for r in rows:
        seq[(r.get("agent"), r.get("path"))].append(r["verdict"])
    episodes = []
    for v in seq.values():
        cur = 0
        for x in v:
            cur += 1
            if x == "allow":
                episodes.append(("pass", cur)); cur = 0
        if cur:
            episodes.append(("blocked", cur))
    passed = [n for k, n in episodes if k == "pass"]
    first_pass = sum(1 for n in passed if n == 1)
    rescued = sum(1 for n in passed if n > 1)      # 거부됐다가 고쳐서 통과 = 자기수정 루프가 실제로 돈 증거
    never = sum(1 for k, _ in episodes if k == "blocked")   # 끝내 못 쓴 시도 = 훅이 막아 낸 것
    written, tries = passed, passed
    by_rule = Counter(r.get("rule") or "R99_other" for r in deny)
    return {
        "writes_total": len(rows), "allowed": len(allow), "denied": len(deny),
        "deny_rate": round(len(deny) / len(rows), 3) if rows else 0,
        "pages_written": len(written), "first_pass": first_pass, "rescued_after_deny": rescued, "blocked_for_good": never,
        "first_pass_rate": round(first_pass / len(written), 3) if written else 0,
        "avg_attempts_to_pass": round(sum(tries) / len(tries), 2) if tries else 0,
        "by_rule": [{"rule": k, "label": LABEL.get(k, k), "count": v} for k, v in by_rule.most_common()],
        "by_agent": {a: dict(Counter(r["verdict"] for r in rows if r.get("agent") == a)) for a in sorted({r.get("agent") or "?" for r in rows})},
        "anchors_written": sum(r.get("anchors", 0) for r in allow), "quotes_written": sum(r.get("quotes", 0) for r in allow),
        "last": [{k: r.get(k) for k in ("ts", "agent", "path", "verdict", "rule", "reason")} for r in rows[-10:]][::-1],
    }


if __name__ == "__main__":
    print(json.dumps(metrics(sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False, indent=1))
