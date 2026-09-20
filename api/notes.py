#!/usr/bin/env python3
"""필기(F-05) — wiki/notes/L{n}/s{k}.md 읽기/쓰기.

- 앵커는 사용자가 입력하지 않는다. 서버가 구간표에서 채운다(CONTRACT §4.3, §5.4).
- 저장은 반드시 WritePolicy 훅(agent:"user", tool_name:"save_note")을 통과할 때만.
  훅은 판정만 하고 파일은 쓰지 않는다 → allow 면 여기서 쓴다.
- 본문에는 앵커를 넣지 않는다(훅 R: notes cannot contain source anchors). 앵커는 프론트매터에만.
"""
import datetime
from pathlib import Path

from api import store
from api.hook import run_guard

ROOT = store.ROOT
NOTES = ROOT / "wiki" / "notes"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """--- fm --- body 를 (dict, body) 로. 20줄 파서: `key: value` 만."""
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
    return fm, parts[2].lstrip("\n")


def list_notes(lecture: str) -> list:
    """GET /api/notes/{lecture} — [{k,s,text,anchor,frame,updated}] (CONTRACT §5)."""
    if not store.valid_lecture(lecture):
        return []
    d = NOTES / lecture
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("s*.md")):
        try:
            fm, body = _parse_frontmatter(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        seg = store.find_segment_by_k(lecture, _k_from_name(p.name))
        out.append({
            "k": _k_from_name(p.name),
            "s": seg.get("s") if seg else None,
            "text": body.strip(),
            "anchor": fm.get("anchor"),
            "frame": fm.get("frame"),
            "updated": fm.get("updated"),
        })
    out.sort(key=lambda n: (n["k"] if isinstance(n["k"], int) else 1 << 30))
    return out


def _k_from_name(name: str) -> int | None:
    stem = name[:-3] if name.endswith(".md") else name  # s5.md -> s5
    if stem.startswith("s") and stem[1:].isdigit():
        return int(stem[1:])
    return None


def _compose(lecture: str, seg: dict, text: str) -> tuple[str, str, str, str]:
    """(path, content, anchor, frame) — 앵커/프레임을 서버가 채운다."""
    s = seg["s"]
    t = store.anchor_second(seg)
    anchor = f"{lecture}#s{s}@t={t}"
    frame = store.frame_url(lecture, seg) or ""
    path = f"wiki/notes/{lecture}/s{seg['k']}.md"
    updated = datetime.datetime.now().isoformat(timespec="seconds")
    fm = (
        "---\n"
        "type: note\n"
        f"anchor: {anchor}\n"
        f"frame: {frame}\n"
        "trust: user\n"
        f"updated: {updated}\n"
        "---\n"
    )
    return path, fm + text.strip() + "\n", anchor, frame


def save_note(lecture: str, k: int, text: str):
    """POST /api/notes → (ok, payload_or_reason).

    ok=True  → {"ok":True, "path", "anchor", "frame"}
    ok=False → (status, code, reason) 튜플로 호출자가 봉투를 만든다.
    """
    if not store.valid_lecture(lecture):
        return False, (400, "BAD_LECTURE", "lecture must match ^L\\d+$")
    if not isinstance(k, int):
        return False, (400, "BAD_REQUEST", "k must be an integer")
    if not isinstance(text, str) or not text.strip():
        return False, (400, "BAD_REQUEST", "text is required")

    seg = store.find_segment_by_k(lecture, k)
    if seg is None:
        return False, (404, "SEGMENT_NOT_FOUND", f"no segment k={k} in {lecture}")

    path, content, anchor, frame = _compose(lecture, seg, text)

    ok, reason, _rule = run_guard("user", "save_note", path=path, content=content)
    if not ok:
        # 훅 거부 → 422 WRITE_REJECTED + 훅 사유 원문(R3)
        return False, (422, "WRITE_REJECTED", reason)

    # allow 일 때만 파일을 쓴다(같은 (lecture,k) 면 덮어쓴다 — 이전은 history 에 남음).
    abs_path = ROOT / path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    return True, {"ok": True, "path": path, "anchor": anchor, "frame": frame}
