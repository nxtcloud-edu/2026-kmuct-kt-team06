#!/usr/bin/env python3
"""위키에 묻기(F-10). 위키 밖 지식으로 답하지 않는다(CONTRACT §5.2).

흐름:
  1) grep_wiki + 링크 1홉으로 근거 문단을 모은다.
  2) 근거 0개면 모델을 부르지 않고 {answer:null, reason:"NO_GROUNDING", videos}.
  3) 답변을 qa_stop_guard.py 에 태운다. 앵커 없으면 1회 재생성, 그래도 없으면 NO_GROUNDING.
  4) notes[] 는 코드로(답변 앵커와 같은 구간의 필기) 붙인다 — 모델이 아니라.
  5) IP당 분당 10회, 질문 500자 컷.
"""
import json
import re
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from api import store, wiki_read
from api.llm_adapter import complete

ROOT = store.ROOT
QA_STOP = ROOT / "hooks" / "qa_stop_guard.py"
ANCHOR_TEXT = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)(?:-(\d+))?\]\]")

# ── 레이트리밋: IP당 분당 10회 ─────────────────────────────────
_hits: dict[str, deque] = defaultdict(deque)
RATE_LIMIT = 10
WINDOW = 60.0


def rate_ok(ip: str) -> bool:
    now = time.time()
    dq = _hits[ip]
    while dq and now - dq[0] > WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return False
    dq.append(now)
    return True


def _grep(pattern: str):
    try:
        from tools.grep_wiki import grep_wiki
        return grep_wiki(pattern, max_hits=20)
    except Exception:
        return []


def _gather_grounding(question: str, context: dict | None):
    """근거 문단 + 앵커. context.slug 페이지를 먼저, 그다음 키워드 grep + 링크 1홉."""
    pages: dict[str, tuple] = {}  # slug -> (fm, body)
    for rel, fm, body in wiki_read.iter_pages():
        pages[rel[:-3]] = (fm, body)  # concepts/dfs

    picked: list[str] = []  # slug 순서 유지
    ctx_slug = (context or {}).get("slug")
    if ctx_slug and ctx_slug in pages:
        picked.append(ctx_slug)

    # 키워드 grep — 질문의 단어 중 2자 이상
    words = [w for w in re.split(r"\s+", question) if len(w) >= 2][:6]
    for w in words:
        for h in _grep(re.escape(w)):
            slug = _slug_of(h.get("path", ""))
            if slug and slug in pages and slug not in picked:
                picked.append(slug)

    # 링크 1홉: 고른 페이지의 links: 에 있는 concept 도 근거로
    hop = []
    for slug in picked:
        fm, _ = pages[slug]
        for link in wiki_read._list_values(fm.get("links", "")):
            cand = f"concepts/{link}"
            if cand in pages and cand not in picked and cand not in hop:
                hop.append(cand)
    picked += hop

    grounds = []
    for slug in picked:
        fm, body = pages[slug]
        for para in body.split("\n\n"):
            if ANCHOR_TEXT.search(para):
                grounds.append({"slug": slug, "text": para.strip()})
    return grounds


def _slug_of(path: str) -> str | None:
    p = path.replace("\\", "/")
    for marker in ("wiki/",):
        if marker in p:
            p = p.split(marker, 1)[1]
    if p.endswith(".md"):
        p = p[:-3]
    return p or None


def _qa_stop(final_text: str) -> bool:
    """qa_stop_guard.py 에 태운다. 앵커 있으면 allow."""
    try:
        proc = subprocess.run(
            [sys.executable, str(QA_STOP)],
            input=json.dumps({"final_text": final_text}, ensure_ascii=False),
            capture_output=True, text=True, cwd=str(ROOT), timeout=10,
        )
        out = (proc.stdout or "").strip().splitlines()
        if not out:
            return False
        return json.loads(out[-1]).get("decision") == "allow"
    except Exception:
        return bool(ANCHOR_TEXT.search(final_text))  # 훅 못 부르면 앵커 유무로


def _notes_for(anchors: list[str]) -> list:
    """답변 앵커와 같은 구간의 필기(코드로 붙인다, 모델 아님)."""
    from api import notes as notes_mod
    out, seen = [], set()
    for a in anchors:
        m = ANCHOR_TEXT.search(a)
        if not m:
            continue
        lecture, s = f"L{m.group(1)}", int(m.group(2))
        for n in notes_mod.list_notes(lecture):
            if n.get("s") == s and n.get("anchor") not in seen:
                out.append({"anchor": n.get("anchor"), "text": n.get("text")})
                seen.add(n.get("anchor"))
    return out


def _videos(question: str):
    """질문 키워드로 유튜브 검색(교수 채널 먼저). 실패하면 []. T5 에서 실제 구현."""
    try:
        from api.youtube import search as yt_search
        return yt_search(question)
    except Exception:
        return []


def answer(question: str, model: str = "fast", context: dict | None = None) -> dict:
    question = (question or "")[:500]  # 500자 컷
    videos = _videos(question)

    grounds = _gather_grounding(question, context)
    if not grounds:
        return {
            "answer": None, "anchors": [], "notes": [],
            "unanchored": [question] if question else [],
            "model": model, "reason": "NO_GROUNDING",
            "message": "위키에 근거가 없습니다. 아직 이 내용을 다룬 강의가 들어오지 않았습니다.",
            "videos": videos,
        }

    system = (
        "너는 위키 안 근거로만 답한다. 아래 근거 문단의 앵커 [[L#s@t]] 를 반드시 인용하라.\n\n"
        + "\n\n".join(g["text"] for g in grounds[:8])
    )
    messages = [{"role": "user", "content": question}]

    text = ""
    result = None
    for _attempt in range(2):  # 앵커 없으면 1회 재생성
        try:
            result = complete("qa", system, messages, model=model)
        except Exception as e:  # LLM 실패(키 없음·429·5xx·모델 404) → 서버는 죽지 않는다
            return {
                "answer": None, "anchors": [], "notes": [],
                "unanchored": [question] if question else [],
                "model": model, "reason": "LLM_ERROR",
                "message": f"모델 호출 실패: {str(e)[:120]}",
                "videos": videos,
            }
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        if _qa_stop(text):
            break
    else:
        # 재생성해도 앵커 없음 → NO_GROUNDING
        return {
            "answer": None, "anchors": [], "notes": [],
            "unanchored": [question] if question else [],
            "model": model, "reason": "NO_GROUNDING",
            "message": "근거 앵커를 찾지 못했습니다.",
            "videos": videos,
        }

    anchors = [f"[[L{L}#s{s}@t={t}]]" for L, s, t, _ in ANCHOR_TEXT.findall(text)]
    return {
        "answer": text,
        "anchors": anchors,
        "notes": _notes_for(anchors),
        "unanchored": [],
        "model": result.get("model", model) if isinstance(result, dict) else model,
        "videos": videos,
    }
