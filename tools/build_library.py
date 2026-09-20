#!/usr/bin/env python3
"""wiki/ → web/viewer/library.local.json  (프론트 뷰어가 읽는 노트 목록. 코드, 모델 0회)

  python3 tools/build_library.py            # 한 번
  (tools/build_wiki.py 가 빌드할 때마다 같이 부른다)

뷰어(web/viewer/viewer.js)는 [{title,status,type,slug,body}] 목록을 그린다. 먼저 library.local.json 을 찾고,
없으면 저장소에 커밋된 견본 library.json(L3 4쪽)으로 돌아간다.
- status: grey 는 뺀다(숨기기 = build_wiki 와 같은 규칙).
- 실강의 산출물이 들어가므로 library.local.json 은 .gitignore 다(배포 서버·로컬에서만 생성).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web/viewer/library.local.json"
FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _field(fm: str, key: str, default: str = "") -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else default


def _courses() -> dict:
    try:
        cfg = json.loads((ROOT / "api/media.json").read_text(encoding="utf-8"))
        return {k: v.get("course") for k, v in cfg.items() if isinstance(v, dict) and v.get("course")}
    except Exception:
        return {}


def build() -> list:
    pages = []
    courses = _courses()
    for kind, folder in (("lecture", "lectures"), ("concept", "concepts")):
        for p in sorted((ROOT / "wiki" / folder).glob("*.md")):
            body = p.read_text(encoding="utf-8")
            m = FM.match(body)
            fm = m.group(1) if m else ""
            status = _field(fm, "status", "draft")
            if status == "grey":
                continue
            pages.append({
                "title": _field(fm, "title", p.stem),
                "status": status,
                "type": _field(fm, "type", kind),
                "slug": f"{folder}/{p.stem}",
                "course": courses.get((re.match(r"L\d+", p.stem) or [""])[0]) if kind == "lecture" else None,
                "body": body,
            })
    return pages


if __name__ == "__main__":
    pages = build()
    if not pages:
        sys.exit("wiki/ 에 페이지가 없다 — 아무것도 쓰지 않는다")
    OUT.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"library.local.json: {len(pages)}쪽 "
          f"(강의 {sum(p['type']=='lecture' for p in pages)} · 개념 {sum(p['type']=='concept' for p in pages)})")
