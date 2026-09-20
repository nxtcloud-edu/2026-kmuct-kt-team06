#!/usr/bin/env python3
"""발표 숫자 종합 = CONTRACT §5 /api/stats payload. LLM 없음.

  python3 tools/stats.py
  from tools.stats import stats     # api/ 의 GET /api/stats 가 이걸 그대로 반환한다

  {lectures, pages, approved, draft, grey, links, notes, coverage:{covered,total}, hooks:{…}}

- hooks     = tools.hook_metrics.metrics() 그대로 (거부·재작성 통과·규칙별·에이전트별·앵커 수)
- coverage  = tools.coverage.coverage() 의 {covered, total}
- 페이지 통계 = wiki/concepts·lectures 의 프론트매터 status 를 세서 (approved/draft/grey)
페이지 파싱을 한 곳(여기)에서만 해서 프론트·API 가 같은 숫자를 본다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.hook_metrics import metrics as hook_metrics  # noqa: E402
from tools.coverage import coverage as coverage_calc    # noqa: E402

STATUS = re.compile(r"^status:\s*(\w+)", re.M)
LINK = re.compile(r"\[\[(?:concepts|lectures)/[^\]]+\]\]|\blinks:\s*\[([^\]]+)\]")


def _page_stats():
    concepts = ROOT / "wiki" / "concepts"
    lectures = ROOT / "wiki" / "lectures"
    pages, approved, draft, grey, links = 0, 0, 0, 0, 0
    lecture_ids = set()
    for d in (concepts, lectures):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            pages += 1
            m = STATUS.search(text)
            st = m.group(1) if m else "draft"
            approved += st == "approved"
            draft += st == "draft"
            grey += st == "grey"
            for sm in re.finditer(r"sources:\s*\[([^\]]*)\]", text):
                lecture_ids.update(re.findall(r"L\d+", sm.group(1)))
            # links: 프론트매터 links + 본문 [[concepts/..]] 위키링크
            fm = re.search(r"^links:\s*\[([^\]]*)\]", text, re.M)
            if fm and fm.group(1).strip():
                links += len([x for x in fm.group(1).split(",") if x.strip()])
    return {"lectures": len(lecture_ids), "pages": pages,
            "approved": approved, "draft": draft, "grey": grey, "links": links}


def _notes_count():
    d = ROOT / "wiki" / "notes"
    return sum(1 for _ in d.rglob("*.md")) if d.is_dir() else 0


def stats():
    ps = _page_stats()
    cov = coverage_calc(write=False)
    return {
        **ps,
        "notes": _notes_count(),
        "coverage": {"covered": cov["covered"], "total": cov["total"]},
        "hooks": hook_metrics(),
    }


if __name__ == "__main__":
    import json
    s = stats()
    print(json.dumps(s, ensure_ascii=False, indent=1))
    h = s["hooks"]
    print("\n=== 발표 숫자 요약 ===", file=sys.stderr)
    print(f"강의 {s['lectures']} · 페이지 {s['pages']}(승인 {s['approved']}/초안 {s['draft']}/보류 {s['grey']}) · 링크 {s['links']} · 필기 {s['notes']}", file=sys.stderr)
    print(f"쓰기 {h['writes_total']}건: 통과 {h['allowed']} · 거부 {h['denied']} · 거부후 자기수정 통과 {h['rescued_after_deny']} · 끝내 막힘 {h['blocked_for_good']}", file=sys.stderr)
    print(f"시험 범위 커버리지 {s['coverage']['covered']}/{s['coverage']['total']} (전체 시험 신호 합산)", file=sys.stderr)
    # 시험(과목)별 커버리지 — 섞으면 오해라 나눠서 보여 준다
    sig_dir = ROOT / "wiki" / "signals"
    for f in sorted(sig_dir.glob("exam-*.md")) if sig_dir.is_dir() else []:
        exam = f.stem.replace("exam-", "")
        c = coverage_calc(exam, write=False)
        print(f"  · {exam}: {c['covered']}/{c['total']}", file=sys.stderr)
    print(f"위키에 들어간 앵커 {h['anchors_written']} · 🗣 인용 {h['quotes_written']}", file=sys.stderr)
