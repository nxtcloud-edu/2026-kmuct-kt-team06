#!/usr/bin/env python3
"""페이지 메타 편집 — 지금은 제목 바꾸기(rename) 하나.

검토함(api/review.py)의 approve/hide 와 같은 길을 쓴다: 사용자가 만든 변경을
agent:"user" 로 훅(hooks/write_page_guard.py)에 태우고, allow 일 때만 실제로 쓴다.
훅이 사용자에게 허용하는 것은 프론트매터 status:/title: 두 줄뿐이다(R09).

파일 이름·slug 는 절대 바뀌지 않는다 — 앵커·[[링크]]·public/ 경로가 전부 slug 기준이라
이름을 바꾸면 죽은 링크가 된다. 바뀌는 것은 프론트매터 title: 한 줄뿐이다.

본문 첫 H1('# 옛 제목')은 **일부러 건드리지 않는다.** 훅의 사용자 규칙은 본문이
한 바이트라도 달라지면 거부하므로(R09) H1 까지 바꾸면 rename 자체가 422 가 된다.
H1 정리는 컴파일 에이전트가 그 페이지를 다시 쓸 때 할 일이다.
"""
import json
import re

from api import store
from api.hook import run_guard

ROOT = store.ROOT
WIKI = ROOT / "wiki"

TITLE_CTRL = re.compile(r"[\x00-\x1f\x7f]")
MAX_TITLE = 80


def _check_title(title) -> str | None:
    """훅(check_user_title)과 같은 규칙을 서버 쪽에서 먼저 본다. 반환: 사유 | None."""
    if not isinstance(title, str):
        return "title must be a string"
    if "\n" in title or "\r" in title:
        return "title must be a single line"
    t = title.strip()
    if not 1 <= len(t) <= MAX_TITLE:
        return f"title must be 1-{MAX_TITLE} characters"
    if TITLE_CTRL.search(title):
        return "title must not contain control characters"
    if "[[" in title or "]]" in title:
        return "title must not contain '[[' or ']]'"
    if "<" in title or ">" in title:
        return "title must not contain '<' or '>'"
    return None


def _title_line(title: str) -> str:
    """항상 큰따옴표로. json.dumps 가 '"' 와 '\\' 를 이스케이프한다 — 따옴표 없는 ': ' 는 Quartz 빌드를 깨뜨린다."""
    return "title: " + json.dumps(title, ensure_ascii=False)


def rename(page_id: str, title: str):
    """page:<slug> 의 프론트매터 title: 한 줄만 바꾼다. (ok, payload | (status, code, message))

    성공: {"ok": True, "slug": slug, "title": title}
    실패: 400 BAD_ID / 400 BAD_TITLE / 404 PAGE_NOT_FOUND / 422 WRITE_REJECTED(훅 사유)
    """
    prefix = "page:"
    if not page_id or not isinstance(page_id, str) or not page_id.startswith(prefix):
        return False, (400, "BAD_ID", "expects a page:<slug> id")
    slug = page_id[len(prefix):].strip()
    if (not slug or ".." in slug or slug.startswith("/") or "\\" in slug
            or "\x00" in slug or slug.endswith(".md")):
        return False, (400, "BAD_ID", f"bad slug '{slug}'")

    err = _check_title(title)
    if err:
        return False, (400, "BAD_TITLE", err)
    title = title.strip()

    path = f"wiki/{slug}.md"
    abs_path = ROOT / path
    if not abs_path.is_file():
        return False, (404, "PAGE_NOT_FOUND", f"no page {slug}")

    old = abs_path.read_text(encoding="utf-8")
    if not old.startswith("---") or old.count("---") < 2:
        return False, (422, "WRITE_REJECTED", "REJECTED: page has no frontmatter")
    head, fm, body = old.split("---", 2)

    line = _title_line(title)
    if re.search(r"^title:.*$", fm, re.M):
        new_fm = re.sub(r"^title:.*$", lambda _m: line, fm, count=1, flags=re.M)
    else:  # title: 이 없으면 여는 '---' 바로 다음 줄에 새로 넣는다
        new_fm = "\n" + line + "\n" + fm.lstrip("\n")
    new = head + "---" + new_fm + "---" + body

    ok, reason, _rule = run_guard("user", "write_page", path=path, content=new)
    if not ok:
        return False, (422, "WRITE_REJECTED", reason)
    abs_path.write_text(new, encoding="utf-8")
    return True, {"ok": True, "slug": slug, "title": title}
