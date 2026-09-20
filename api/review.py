#!/usr/bin/env python3
"""검토함(F-11) — 사람이 확인할 목록. 전부 기존 데이터에서 계산(PRD §4.8), LLM 없음.

항목 종류(CONTRACT §5):
  low_confidence  구간 confidence 낮은 순 5 (강의당, reviewed 제외) — 문턱값 아님
  grey            status: grey|draft 페이지
  rewritten       history 의 deny -> allow 경로(자기수정으로 통과)
  stt_uncertain   agree < 0.5 문장

approve: 프론트매터 status: 한 줄만 바꾼 본문을 agent:"user" 로 훅에 태운다.
"""
import json
import re

from api import store, wiki_read
from api.hook import run_guard

ROOT = store.ROOT
WIKI = ROOT / "wiki"
HISTORY = WIKI / ".history.jsonl"


def _low_confidence(lectures) -> list:
    """구간 confidence 낮은 순 5(강의당). reviewed:true 제외."""
    out = []
    for lec in sorted(lectures):
        segs = store.load_segments(lec) or []
        scored = []
        for g in segs:
            if g.get("reviewed"):
                continue
            conf = g.get("confidence")
            if conf is None:
                continue
            scored.append((conf, g))
        scored.sort(key=lambda x: x[0])
        for conf, g in scored[:5]:
            s = g.get("s")
            t = store.anchor_second(g) if "t_end" in g else None
            out.append({
                "id": f"seg:{lec}:{g.get('k')}",
                "kind": "low_confidence",
                "lecture": lec,
                "slug": None,
                "anchor": f"{lec}#s{s}@t={t}" if t is not None else None,
                "text": (g.get("ocr") or "")[:120],
                "reason": f"슬라이드 매칭 불확실 (신뢰도 {conf})",
            })
    return out


def _grey_pages() -> list:
    out = []
    for rel, fm, body in wiki_read.iter_pages():
        st = fm.get("status")
        if st not in ("grey", "draft"):
            continue
        m = wiki_read.ANCHOR_IN_TEXT.search(body)
        anchor = f"L{m.group(1)}#s{m.group(2)}@t={m.group(3)}" if m else None
        lecture = None
        srcs = wiki_read._list_values(fm.get("sources", ""))
        if srcs and store.valid_lecture(srcs[0]):
            lecture = srcs[0]
        # 첫 본문 문단(앵커 제거) 미리보기
        preview = ""
        for para in body.split("\n\n"):
            p = para.strip()
            if p and not p.startswith("#"):
                preview = wiki_read.ANCHOR_IN_TEXT.sub("", p).strip()[:120]
                break
        out.append({
            "id": f"page:{rel[:-3]}",  # concepts/dfs
            "kind": "grey",
            "lecture": lecture,
            "slug": rel[:-3],
            "anchor": anchor,
            "text": preview,
            "reason": f"상태 {st} — 사람 확인 필요",
        })
    return out


def _rewritten() -> list:
    """history 에서 같은 path 가 deny 뒤 allow 로 통과한 것."""
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    out, denied_reason = [], {}
    for r in rows:
        path = r.get("path")
        if r.get("verdict") == "deny":
            denied_reason[path] = r.get("reason")
        elif r.get("verdict") == "allow" and path in denied_reason:
            slug = path[len("wiki/"):-3] if path and path.startswith("wiki/") and path.endswith(".md") else path
            out.append({
                "id": f"hist:{slug}",
                "kind": "rewritten",
                "lecture": None,
                "slug": slug,
                "anchor": None,
                "text": "",
                "reason": f"훅 거부 후 재작성됨: {denied_reason.pop(path)}",
            })
    return out


def _stt_uncertain(lectures) -> list:
    """agree < 0.5 문장(CONTRACT §4.1b). transcript 없으면 없음."""
    out = []
    for lec in sorted(lectures):
        for p in store.load_transcript(lec):
            agree = p.get("agree")
            if agree is None or agree >= 0.5 or p.get("reviewed"):
                continue
            out.append({
                "id": f"stt:{lec}:{p.get('t_start')}",
                "kind": "stt_uncertain",
                "lecture": lec,
                "slug": None,
                "anchor": None,
                "text": (p.get("text") or "")[:120],
                "reason": f"전사 일치율 {agree} — 🗣 인용 금지",
            })
    return out


def review_list() -> list:
    lectures = set()
    for _rel, fm, _body in wiki_read.iter_pages():
        for lec in wiki_read._list_values(fm.get("sources", "")):
            if store.valid_lecture(lec):
                lectures.add(lec)
    items = []
    items += _low_confidence(lectures)
    items += _grey_pages()
    items += _rewritten()
    items += _stt_uncertain(lectures)
    return items


def approve(item_id: str):
    """status: 를 approved 로 바꾼다. agent:user 로 훅 통과할 때만 실제로 쓴다.

    id 형태: page:<slug>  (예: page:concepts/dfs) — 프론트매터 status 승인.
    seg:<lec>:<k> — segments.json 의 reviewed:true (구간 항목). 여기서는 page 만 다룬다.
    반환: (ok, payload_or_reason_tuple)
    """
    if not item_id or not item_id.startswith("page:"):
        return False, (400, "BAD_ID", "approve expects a page:<slug> id")
    slug = item_id[len("page:"):]
    path = f"wiki/{slug}.md"
    abs_path = ROOT / path
    if not abs_path.is_file():
        return False, (404, "PAGE_NOT_FOUND", f"no page {slug}")
    old = abs_path.read_text(encoding="utf-8")
    # 프론트매터 status: 한 줄만 approved 로. 본문은 그대로.
    new = re.sub(r"^status:.*$", "status: approved", old, count=1, flags=re.M)
    ok, reason, _rule = run_guard("user", "write_page", path=path, content=new)
    if not ok:
        return False, (422, "WRITE_REJECTED", reason)
    abs_path.write_text(new, encoding="utf-8")
    return True, {"ok": True}
