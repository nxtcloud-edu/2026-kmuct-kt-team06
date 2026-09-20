#!/usr/bin/env python3
"""비평 집계 (코드, 모델 0회) — api/dashboard.py 가 summary_confidence() 를 부른다.

  from tools.critic import summary_confidence   # -> float(0~1) | None

summary_confidence = 비평 통과율 × 인용 대조 통과율.
- 인용 대조 통과율: 모든 draft/approved 페이지의 🗣 인용 중 전사본과 유사도 통과 비율(pipeline.critic.quote_check 재사용, 항상 코드로 계산 가능).
- 비평 통과율: wiki/.critic.jsonl(④ 모델 비평 결과)에서 grey/재작성으로 안 빠진 문단 비율. 로그가 없으면(=비평 안 돌림) None.
- 둘 중 하나라도 측정 안 됨이면 측정된 쪽만, 둘 다 없으면 None(DESIGN §6 "측정 전"은 회색으로).

무거운 ④ 비평(모델 호출)은 pipeline/critic.py 가 한다. 여기는 그 결과를 읽어 대시보드 숫자만 만든다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CRITIC_LOG = ROOT / "wiki" / ".critic.jsonl"


def _quote_pass_rate():
    """모든 페이지의 🗣 인용 대조 통과율. 인용이 하나도 없으면 None."""
    try:
        from pipeline.critic import quote_check
    except Exception:
        return None
    total, passed = 0, 0
    for sub in ("lectures", "concepts"):
        d = ROOT / "wiki" / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            qc = quote_check(str(p.relative_to(ROOT)))
            total += qc["total"]
            passed += qc["passed"]
    if total == 0:
        return None
    return passed / total


def _critic_pass_rate():
    """④ 모델 비평 결과(.critic.jsonl)에서 통과율. 로그 없으면(=비평 안 돌림) None.
    검토함에 오른 문단(grey/low_confidence/quote_mismatch)을 '반려'로 본다."""
    if not CRITIC_LOG.is_file():
        return None
    rows = [json.loads(l) for l in CRITIC_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        return None
    # 페이지 문단 총수를 알기 어렵다 → 반려 대비 위키 앵커 문단 수를 분모로 근사
    flagged = len({(r.get("slug"), r.get("anchor")) for r in rows})
    total_paras = _count_paragraphs()
    if total_paras == 0:
        return None
    return max(0.0, (total_paras - flagged) / total_paras)


def _count_paragraphs():
    """concepts Current 문단 + lectures 🗣 인용 개수(비평 대상 단위)."""
    ANCHOR = re.compile(r"\[\[L\d+#s\d+@t=\d+\]\]")
    QUOTE = re.compile(r"^>\s*🗣", re.M)
    n = 0
    for sub in ("lectures", "concepts"):
        d = ROOT / "wiki" / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            if "## Current" in text:
                cur = text.split("## Current", 1)[1].split("## History", 1)[0]
                n += sum(1 for para in cur.split("\n\n") if ANCHOR.search(para))
            n += len(QUOTE.findall(text))
    return n


def summary_confidence():
    """비평 통과율 × 인용 대조 통과율. 측정된 것만 곱하고, 둘 다 없으면 None."""
    q = _quote_pass_rate()
    c = _critic_pass_rate()
    vals = [v for v in (q, c) if v is not None]
    if not vals:
        return None
    score = 1.0
    for v in vals:
        score *= v
    return round(score, 3)


if __name__ == "__main__":
    print(json.dumps({
        "summary_confidence": summary_confidence(),
        "quote_pass_rate": _quote_pass_rate(),
        "critic_pass_rate": _critic_pass_rate(),
        "paragraphs": _count_paragraphs(),
    }, ensure_ascii=False, indent=1))
