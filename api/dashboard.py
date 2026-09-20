#!/usr/bin/env python3
"""대시보드 수치(F-18, DESIGN §6) + 전사 수정. 전부 코드 계산, LLM 없음.

- stt      = agree 의 문장 길이 가중 평균(수정된 문장은 1.0). 측정 전이면 null.
- summary  = 비평 통과율 × 인용 대조 통과율. 비평 안 돌렸으면 null.
- overall  = 둘의 조화평균. 하나라도 null 이면 null.
- confusing = agree 낮은 순 문장(stt_uncertain).
- hooks    = hook_metrics.metrics().
"""
import json

from api import store, wiki_read
from api.hook import run_guard
from tools import hook_metrics

ROOT = store.ROOT
WIKI = ROOT / "wiki"


def _lectures_for(course: str | None) -> list[str]:
    """course 필터. 프론트매터 course: 로 묶는다(없으면 sources 의 강의 전부)."""
    lectures = set()
    for _rel, fm, _body in wiki_read.iter_pages():
        pg_course = fm.get("course")
        if course and pg_course != course:
            continue
        for lec in wiki_read._list_values(fm.get("sources", "")):
            if store.valid_lecture(lec):
                lectures.add(lec)
    # 페이지가 없어도 raw/L* 는 본다
    if not lectures and not course:
        for d in sorted((ROOT / "raw").glob("L*")):
            if store.valid_lecture(d.name):
                lectures.add(d.name)
    return sorted(lectures)


def _stt_score(lectures) -> float | None:
    """agree 문장 길이 가중 평균. reviewed=true 문장은 1.0. agree 필드가 하나도 없으면 None(측정 전)."""
    num = den = 0.0
    seen_any = False
    for lec in lectures:
        for p in store.load_transcript(lec):
            agree = p.get("agree")
            if agree is None and not p.get("reviewed"):
                continue
            seen_any = True
            weight = max(len((p.get("text") or "")), 1)
            score = 1.0 if p.get("reviewed") else float(agree)
            num += score * weight
            den += weight
    if not seen_any or den == 0:
        return None
    return round(num / den, 2)


def _summary_score() -> float | None:
    """비평 통과율 × 인용 대조 통과율. critic 결과(.history 또는 tools)가 없으면 None."""
    try:
        from tools.critic import summary_confidence  # 팀장 산출물(있으면)
        v = summary_confidence()
        return round(float(v), 2) if v is not None else None
    except Exception:
        return None  # 비평 아직 안 돌림 → 측정 전


def _harmonic(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(2 * a * b / (a + b), 2)


def _confusing(lectures) -> list:
    """agree 낮은 순 문장 — DESIGN §6 '이 부분이 헷갈려요'."""
    rows = []
    for lec in lectures:
        segs = store.load_segments(lec) or []
        for p in store.load_transcript(lec):
            agree = p.get("agree")
            if agree is None or p.get("reviewed"):
                continue
            t0 = p.get("t_start", 0)
            seg = next((g for g in segs if g["t_start"] <= t0 <= g["t_end"]), None)
            s = seg.get("s") if seg else None
            anchor = f"{lec}#s{s}@t={int(t0)}" if s is not None else None
            rows.append({
                "lecture": lec,
                "t_start": p.get("t_start"),
                "t_end": p.get("t_end"),
                "text": (p.get("text") or "")[:120],
                "agree": agree,
                "anchor": anchor,
            })
    rows.sort(key=lambda r: r["agree"])
    return rows[:20]


def dashboard(course: str | None = None) -> dict:
    lectures = _lectures_for(course)
    stt = _stt_score(lectures)
    summary = _summary_score()
    return {
        "overall": _harmonic(stt, summary),
        "stt": stt,
        "summary": summary,
        "measured": {"stt": stt is not None, "summary": summary is not None},
        "confusing": _confusing(lectures),
        "hooks": hook_metrics.metrics(),
    }


def fix_transcript(lecture: str, t_start, text: str):
    """전사 수정(F-18). 훅(fix_transcript, agent:user) 통과 시에만 corrections.jsonl 에 덧붙이고
    그 문장 agree=1.0, reviewed=true 로 갱신. 원문은 지우지 않는다.

    반환: (ok, payload_or_reason_tuple)
    """
    if not store.valid_lecture(lecture):
        return False, (400, "BAD_LECTURE", "lecture must match ^L\\d+$")
    if t_start is None:
        return False, (400, "BAD_REQUEST", "t_start required")
    if not isinstance(text, str) or not text.strip():
        return False, (400, "BAD_REQUEST", "text required")

    ok, reason, _rule = run_guard(
        "user", "fix_transcript",
        tool_input={"lecture": lecture, "t_start": t_start, "text": text},
    )
    if not ok:
        return False, (422, "WRITE_REJECTED", reason)

    # 훅 allow → corrections.jsonl 덧붙이기 + transcript agree/reviewed 갱신
    corr = ROOT / "raw" / lecture / "corrections.jsonl"
    corr.parent.mkdir(parents=True, exist_ok=True)
    import datetime
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "t_start": float(t_start), "text": text.strip()}
    with corr.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    _mark_reviewed(lecture, float(t_start), text.strip())
    return True, {"ok": True}


def _mark_reviewed(lecture: str, t_start: float, text: str):
    """transcript.json 에서 그 문장의 agree=1.0, reviewed=true. text 도 수정본으로. 원문은 corrections 에 남음."""
    tp = ROOT / "raw" / lecture / "transcript.json"
    if not tp.is_file():
        return
    try:
        rows = json.loads(tp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    changed = False
    for r in rows:
        if abs(r.get("t_start", -1) - t_start) < 0.05:
            r["agree"] = 1.0
            r["reviewed"] = True
            r["text"] = text
            changed = True
            break
    if changed:
        tp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        store._cache.pop(str(tp), None)  # mtime 캐시 무효화
