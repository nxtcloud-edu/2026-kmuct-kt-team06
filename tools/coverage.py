#!/usr/bin/env python3
"""CoverageCheck (격리형, ③ 종료 후) — 시험 범위 커버리지 N/M. LLM 없음.

  python3 tools/coverage.py [exam]        # 기본: 모든 signals/exam-*.md
  from tools.coverage import coverage     # api/ 의 /api/stats 가 covered/total 을 읽는다

signals/exam-*.md 의 시험 항목(리스트 `- `)마다 grep_wiki 로 위키(concepts·lectures)에
그 개념이 있는지 확인한다. 있으면 covered, 없으면 uncovered.
결과를 wiki/signals/coverage.md 에 쓰고 {covered, total, items:[...]} 를 반환한다.
uncovered 목록은 ③ 컴파일이 우선 재투입할 대상이 된다(발표 포인트: "시험 범위 커버리지 N/M").

signals 는 힌트지 정본이 아니다 — 앵커로 인용하지 않고, 페이지 유무 판단에만 쓴다(WritePolicy R06).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.grep_wiki import grep_wiki  # noqa: E402

ITEM = re.compile(r"^\s*-\s+(.+?)\s*$", re.M)
_norm = lambda s: re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())

# 흔한 조사·의존명사·동사어미 — 토큰 매칭에서 제외(오탐 방지). 개념어가 아니다.
STOP = {"하는", "하기", "되는", "있는", "없는", "같은", "느끼게", "만드는", "지지와",
        "그리고", "또는", "대한", "위한", "통한", "이론", "단계", "방식", "종류",
        "느끼", "구역감"}


def _items(md_text):
    """시험 항목 추출: 리스트 줄에서 `(주관식)` 태그·설명 화살표를 떼고 핵심어만."""
    out = []
    for m in ITEM.finditer(md_text):
        raw = m.group(1)
        # `(주관식) 콜버그 도덕단계`, `수면리듬 -> 렘(REM)수면` → 검색 키워드로 정리
        raw = re.sub(r"\(주관식\)\s*", "", raw)
        raw = raw.split("->")[0].split("→")[0].strip()
        if len(raw) >= 2:
            out.append(raw)
    return out


# 절대경로로 준다 — grep_wiki 는 상대경로를 프로세스 CWD 기준으로 보므로, 서버가 저장소 루트가 아닌 곳에서
# 뜨면 covered 만 0 으로 무너진다(실측: cwd=/ → 0/22).
_WIKI_PATHS = [str(ROOT / "wiki" / "concepts"), str(ROOT / "wiki" / "lectures")]


def _covered(item):
    """항목이 위키에 있나. 전체 문자열 grep, 없으면 의미 있는 핵심 토큰(3자+, 불용어 제외) 매칭."""
    if grep_wiki(re.escape(item), paths=_WIKI_PATHS, max_hits=1):
        return True
    # 흔한 조사·의존명사(STOP)와 짧은 토큰은 오탐이라 제외 — 개념어만 본다
    for tok in re.split(r"[\s,·/]+", item):
        tok = tok.strip("()")
        if len(_norm(tok)) >= 3 and tok not in STOP and \
                grep_wiki(re.escape(tok), paths=_WIKI_PATHS, max_hits=1):
            return True
    return False


def _uncovered_notes(lecture=None):
    """필기가 달렸는데 아직 페이지에 안 쓰인 세그먼트(CoverageCheck 확장, registry ⑨)."""
    notes_dir = ROOT / "wiki" / "notes"
    if not notes_dir.is_dir():
        return []
    out = []
    for note in notes_dir.rglob("*.md"):
        m = re.search(r"^anchor:\s*(L\d+#s\d+@t=\d+)", note.read_text(encoding="utf-8"), re.M)
        if not m:
            continue
        anchor = m.group(1)
        # 그 앵커가 어떤 lectures/concepts 페이지에도 안 쓰였으면 미반영
        if not grep_wiki(re.escape(anchor), paths=_WIKI_PATHS, max_hits=1):
            out.append(anchor)
    return out


def coverage(exam=None, write=True):
    sig_dir = ROOT / "wiki" / "signals"
    files = ([sig_dir / f"exam-{exam}.md"] if exam
             else sorted(sig_dir.glob("exam-*.md"))) if sig_dir.is_dir() else []
    files = [f for f in files if f.is_file()]

    items, covered = [], 0
    for f in files:
        for it in _items(f.read_text(encoding="utf-8")):
            hit = _covered(it)
            items.append({"item": it, "covered": hit, "source": f.name})
            covered += 1 if hit else 0
    total = len(items)
    note_gaps = _uncovered_notes()

    if write and sig_dir.is_dir():
        lines = [f"# 시험 범위 커버리지 — {covered}/{total}\n",
                 "> signals(시험 제보)는 힌트다. 앵커로 인용하지 않는다. ③ 컴파일이 아래 미커버 항목을 우선 재투입한다.\n",
                 "## 미커버 (강의 근거 없음 — 제보만 있음)"]
        miss = [i["item"] for i in items if not i["covered"]]
        lines += [f"- {m}" for m in miss] or ["- (없음 — 전 항목 커버)"]
        if note_gaps:
            lines += ["\n## 필기만 달리고 페이지에 안 쓰인 구간"] + [f"- {a}" for a in note_gaps]
        (sig_dir / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"covered": covered, "total": total,
            "items": items, "note_gaps": note_gaps}


if __name__ == "__main__":
    import json
    r = coverage(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"시험 범위 커버리지: {r['covered']}/{r['total']}")
    for i in r["items"]:
        print(f"  [{'✓' if i['covered'] else ' '}] {i['item']}")
    if r["note_gaps"]:
        print("필기만 달린 구간:", r["note_gaps"])
