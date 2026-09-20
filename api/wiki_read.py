#!/usr/bin/env python3
"""위키 페이지 읽기 — 프론트매터·본문·앵커. stats/review 가 공유한다.

wiki/ 는 읽기 전용 산출물(CONTRACT §1). 여기서는 절대 쓰지 않는다.
"""
import re
from pathlib import Path

from api import store

ROOT = store.ROOT
WIKI = ROOT / "wiki"
ANCHOR_IN_TEXT = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)(?:-(\d+))?\]\]")
LINK_LIST = re.compile(r"^links:\s*\[(.*?)\]", re.M)


def parse_page(text: str) -> tuple[dict, str]:
    """--- fm --- body. fm 값은 문자열(list 는 [a, b] 원문 그대로)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, parts[2]


def _list_values(raw: str) -> list[str]:
    """`[a, b, c]` -> ['a','b','c']. 대괄호 없으면 콤마 분리."""
    raw = (raw or "").strip().strip("[]")
    return [x.strip().strip("'\"") for x in raw.split(",") if x.strip()]


def iter_pages():
    """(path_rel, fm, body) — concepts + lectures 페이지."""
    for sub in ("concepts", "lectures"):
        d = WIKI / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                fm, body = parse_page(p.read_text(encoding="utf-8"))
            except OSError:
                continue
            yield p.relative_to(WIKI).as_posix(), fm, body


def page_stats() -> dict:
    """{lectures, pages, approved, draft, grey, links, notes, coverage}."""
    pages = list(iter_pages())
    status_counter = {"approved": 0, "draft": 0, "grey": 0}
    links = 0
    lectures_seen = set()
    for _rel, fm, _body in pages:
        st = fm.get("status", "")
        if st in status_counter:
            status_counter[st] += 1
        links += len(_list_values(fm.get("links", "")))
        for lec in _list_values(fm.get("sources", "")):
            if store.valid_lecture(lec):
                lectures_seen.add(lec)

    notes_count = 0
    notes_dir = WIKI / "notes"
    if notes_dir.is_dir():
        notes_count = sum(1 for _ in notes_dir.rglob("s*.md"))

    covered, total = _coverage(lectures_seen, pages)
    return {
        "lectures": len(lectures_seen),
        "pages": len(pages),
        "approved": status_counter["approved"],
        "draft": status_counter["draft"],
        "grey": status_counter["grey"],
        "links": links,
        "notes": notes_count,
        "coverage": {"covered": covered, "total": total},
    }


def _coverage(lectures: set[str], pages) -> tuple[int, int]:
    """구간 커버리지: 위키 본문 앵커가 가리키는 (lecture,s) 구간 / 전체 구간 수."""
    total = 0
    seg_index = {}
    for lec in lectures:
        segs = store.load_segments(lec) or []
        total += len(segs)
        for g in segs:
            seg_index[(lec, g.get("s"))] = False
    for _rel, _fm, body in pages:
        for m in ANCHOR_IN_TEXT.finditer(body):
            key = (f"L{m.group(1)}", int(m.group(2)))
            if key in seg_index:
                seg_index[key] = True
    covered = sum(1 for v in seg_index.values() if v)
    return covered, total
