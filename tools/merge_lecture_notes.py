#!/usr/bin/env python3
"""강의당 노트 1개로 합치는 결정론적 정리 도구 (LLM 없음, 표준 라이브러리만).

컴파일 에이전트가 주제마다 한 번씩 불려서 `wiki/lectures/L{n}_<제목>.md` 가
강의 하나당 여러 개로 쪼개졌다. 이 도구는 그 조각들을 슬라이드 순서로 이어붙여
강의당 한 장으로 되돌린다. **본문은 한 바이트도 고치지 않는다** — 바꾸는 것은
`## N.` 번호와 문서 머리(프론트매터 · H1 · 소스/읽는 법/목차 줄)뿐이다.

쓰기는 파이프라인과 똑같이 훅을 통과한다(pipeline/tools.py 의 write_page 패턴).
훅 모듈의 ROOT 가 `__file__` 로 고정돼 있어 --root 를 먹일 수 없으므로,
`<root>/hooks/write_page_guard.py` 를 **서브프로세스**로 태우고 allow 일 때만 쓴다.
그래서 테스트가 임시 루트를 쓰면 감사로그도 임시 루트의 wiki/.history.jsonl 로 간다.

    python3 tools/merge_lecture_notes.py                 # 드라이런(기본)
    python3 tools/merge_lecture_notes.py --apply
    python3 tools/merge_lecture_notes.py --lecture L1 L2 --root /tmp/x --apply
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# hooks/write_page_guard.py 의 ANCHOR 와 같은 정규식(범위 앵커 포함)
ANCHOR = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)(?:-(\d+))?\]\]")
QUOTE = re.compile(r"^> 🗣", re.M)
H2NUM = re.compile(r"^## (\d+)\.[ \t]*(.*)$")
SLIDE_HEAD = re.compile(r"^### 📄[^\n(]*\(([^)]*)\)", re.M)
WIKILINK = re.compile(r"\[\[[^\]]+\]\]")
LECTURE_FILE = re.compile(r"^(L\d+)_")

READING_LINE = "> 읽는 법: 주제마다 📄 슬라이드 → 💡 설명 → 🗣 교수님 말 → 🎯 포인트"

# api/media.json 에 title 키가 없을 때 쓰는 붙박이 제목
FALLBACK_TITLES = {
    "L1": "RISC-V ISA",
    "L2": "RISC-V 명령어 포맷",
    "L4": "머지소트와 퀵소트",
    "L5": "메모리와 캐시",
}
DEFAULT_TITLE = "강의 노트"
SKIP_LECTURES = {"L3"}          # 손으로 만든 견본. 건드리지 않는다
BIG = 10 ** 9


# ---------- 파싱 ----------

def split_front_matter(text):
    """(fm dict, 키 순서, 본문) — 값은 한 줄짜리만 다룬다(이 위키의 프론트매터 형식)."""
    if not text.startswith("---"):
        return {}, [], text
    chunks = text.split("---", 2)
    if len(chunks) < 3:
        return {}, [], text
    fm, order = {}, []
    for line in chunks[1].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):[ \t]?(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
            order.append(m.group(1))
    return fm, order, chunks[2]


def body_of(content):
    """훅의 body() 와 같은 계산 — 프론트매터를 뺀 나머지."""
    return content.split("---", 2)[-1] if content.count("---") >= 2 else content


def parse_links(value):
    value = (value or "").strip()
    if value in ("", "[]"):
        return []
    items = WIKILINK.findall(value)
    if items:
        return items
    inner = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    return [x.strip() for x in inner.split(",") if x.strip()]


def render_links(items):
    if not items:
        return "[]"
    if all(x.startswith("[[") for x in items):
        return ", ".join(items)
    return "[" + ", ".join(items) + "]"


def slides_in(paren_text):
    """'s5~6' · 's19, 21' · 's11~11' · 's15' → [5,6] / [19,21] / ... (등장 순서)."""
    return [int(n) for n in re.findall(r"\d+", paren_text or "")]


def parse_source_line(line):
    """'> 소스: L1 s9~s10 · 관련: [[..]]' → (슬라이드 번호들, 관련 링크들)."""
    if not line:
        return [], []
    rest = line.lstrip(">").strip()
    rest = re.sub(r"^소스:\s*", "", rest)
    left, related = rest, []
    m = re.search(r"·\s*관련:\s*(.*)$", rest)
    if m:
        left = rest[: m.start()]
        related = WIKILINK.findall(m.group(1))
    left = re.sub(r"\bL\d+\b", " ", left)          # 'L1 s5~6' 의 강의 id 는 슬라이드가 아니다
    return [int(n) for n in re.findall(r"\d+", left)], related


def dedupe(seq):
    out, seen = [], set()
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


class Section:
    """한 주제(`## N. ...`). raw 는 제목 줄까지 포함한 원문 그대로."""

    def __init__(self, part, raw, order_in_part):
        self.part = part
        self.raw = raw
        self.order_in_part = order_in_part
        head = raw.splitlines()[0]
        m = H2NUM.match(head)
        self.title = (m.group(2) if m else head[3:]).strip()
        self.anchors = ANCHOR.findall(raw)
        self.quotes = len(QUOTE.findall(raw))
        sm = SLIDE_HEAD.search(raw)
        self.head_slides = slides_in(sm.group(1)) if sm else []
        self.anchor_slides = sorted({int(m2.group(2)) for m2 in ANCHOR.finditer(raw)})
        ts = [int(m2.group(3)) for m2 in ANCHOR.finditer(raw)]
        self.min_t = min(ts) if ts else BIG

    @property
    def slides(self):
        return sorted(set(self.head_slides) | set(self.anchor_slides))

    def first_slide(self):
        """① 섹션의 '### 📄 슬라이드 (sA~B)' → ② 파일의 '> 소스: L1 sA~B' → ③ 앵커의 최소 s."""
        if self.head_slides:
            return self.head_slides[0]
        if self.part.source_slides:
            return self.part.source_slides[0]
        if self.anchor_slides:
            return self.anchor_slides[0]
        return BIG

    def renumbered(self, n):
        lines = self.raw.splitlines()
        m = H2NUM.match(lines[0])
        if m:
            lines[0] = "## %d.%s" % (n, lines[0][m.end(1) + 1:])
        return "\n".join(lines)


class Part:
    def __init__(self, path, rel, text):
        self.path = path
        self.rel = rel                     # 루트 기준 상대경로 (wiki/lectures/xxx.md)
        self.text = text
        self.slug = path.stem
        self.fm, self.fm_order, body = split_front_matter(text)
        self.links = parse_links(self.fm.get("links"))
        self.status = (self.fm.get("status") or "").strip()
        self.sources = [s.strip() for s in
                        (self.fm.get("sources") or "").strip("[]").split(",") if s.strip()]
        lines = body.splitlines()
        self.h1 = next((l for l in lines if l.startswith("# ")), "")
        src_line = next((l for l in lines if l.startswith("> 소스")), "")
        self.source_slides, self.related = parse_source_line(src_line)
        self.sections = []
        idx = [i for i, l in enumerate(lines) if l.startswith("## ")]
        for k, start in enumerate(idx):
            end = idx[k + 1] if k + 1 < len(idx) else len(lines)
            chunk = lines[start:end]
            while chunk and not chunk[-1].strip():
                chunk.pop()
            self.sections.append(Section(self, "\n".join(chunk), k))
        self.anchors = len(ANCHOR.findall(text))
        self.quotes = len(QUOTE.findall(text))


# ---------- 메타데이터 ----------

def lecture_meta(root, lid):
    """raw/media.local.json → api/media.json 순서로 title·course 를 찾는다."""
    title, course = None, None
    for rel in ("raw/media.local.json", "api/media.json"):
        p = root / rel
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        entry = data.get(lid) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            if title is None and entry.get("title"):
                title = str(entry["title"]).strip()
            if course is None and entry.get("course"):
                course = str(entry["course"]).strip()
        if title:
            break
    if not title:
        title = FALLBACK_TITLES.get(lid, DEFAULT_TITLE)
    return title, (course or "")


def sanitize(name):
    for ch in '/\\:*?"<>|':
        name = name.replace(ch, "")
    return re.sub(r"\s+", "_", name.strip()).strip("_") or "강의_노트"


def yaml_quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def merge_status(statuses):
    uniq = set(statuses)
    if uniq == {"approved"}:
        return "approved"
    if uniq == {"grey"}:
        return "grey"
    return "draft"


# ---------- 조립 ----------

def build_merged(lid, title, course, parts, ordered, today):
    sources = dedupe([lid] + [s for p in parts for s in p.sources])
    links = dedupe([l for p in parts for l in p.links])
    related = dedupe([r for p in parts for r in p.related])
    slides = sorted({s for sec in ordered for s in sec.slides})
    span = "%s s%d~%d" % (lid, slides[0], slides[-1]) if slides else lid

    head = ["---",
            "title: %s" % yaml_quote("%s. %s" % (lid, title)),
            "type: lecture",
            "sources: [%s]" % ", ".join(sources),
            "status: %s" % merge_status([p.status for p in parts]),
            "updated: %s" % today,
            "links: %s" % render_links(links),
            "---",
            "",
            "# %s. %s" % (lid, title)]
    source_line = "> 소스: " + span
    if course:
        source_line += " · 과목: " + course
    if related:
        source_line += " · 관련: " + " · ".join(related)
    head.append(source_line)
    head.append(READING_LINE)
    head.append("> 목차: " + " · ".join("%d. %s" % (i, s.title) for i, s in enumerate(ordered, 1)))
    body = [sec.renumbered(i) for i, sec in enumerate(ordered, 1)]
    return "\n".join(head) + "\n\n" + "\n\n".join(body) + "\n"


# ---------- 훅(쓰기 관문) ----------

def run_guard(root, agent, rel_path, content, run_id):
    """<root>/hooks/write_page_guard.py 를 서브프로세스로 태운다. 절대 실제 저장소의 훅이 아니다."""
    hook = (root / "hooks" / "write_page_guard.py").resolve()
    if not hook.is_file():
        return {"decision": "block", "reason": "REJECTED: hook not found at %s" % hook}
    if root.resolve() not in hook.parents:
        return {"decision": "block", "reason": "REJECTED: hook outside --root (%s)" % hook}
    ev = {"tool_name": "write_page", "agent": agent, "attempt": 1, "run": run_id,
          "tool_input": {"path": rel_path, "content": content}}
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(ev, ensure_ascii=False),
                          capture_output=True, text=True, cwd=str(root))
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return {"decision": "block",
                "reason": "REJECTED: hook error: %s" % ((proc.stderr or proc.stdout).strip()[:300] or "no output")}


# ---------- 인바운드 링크 ----------

def link_targets(root):
    out = []
    idx = root / "wiki" / "index.md"
    if idx.is_file():
        out.append(idx)
    cdir = root / "wiki" / "concepts"
    if cdir.is_dir():
        out.extend(sorted(cdir.glob("*.md")))
    return out


def rewrite_links(text, old_slugs, new_slug):
    hits, out = [], text
    for old in old_slugs:
        if old == new_slug:
            continue
        pat = re.compile(r"\[\[lectures/" + re.escape(old) + r"(\|[^\]]*)?\]\]")
        for m in pat.finditer(out):
            hits.append(m.group(0))
        out = pat.sub(lambda m: "[[lectures/%s%s]]" % (new_slug, m.group(1) or ""), out)
    return out, hits


def agent_for(rel_path, old_text, new_text):
    """개념 페이지: 프론트매터만 바뀌면 linker(R11 허용), 본문이 바뀌면 compile.
    wiki/index.md 는 linker 만 쓰기 루트를 가진다."""
    if rel_path == "wiki/index.md":
        return "linker"
    if body_of(old_text).strip() == body_of(new_text).strip():
        return "linker"
    return "compile"


# ---------- 강의 하나 처리 ----------

def process_lecture(root, lid, files, apply, run_id, today, log):
    parts = []
    for p in files:
        parts.append(Part(p, "wiki/lectures/" + p.name, p.read_text(encoding="utf-8")))

    empty = [p for p in parts if not p.sections]
    if empty:
        log("  ✖ 건너뜀: '## N.' 주제가 없는 파일 — " + ", ".join(p.path.name for p in empty))
        return False

    sections = [s for p in parts for s in p.sections]
    order = sorted(range(len(sections)),
                   key=lambda i: (sections[i].first_slide(), sections[i].min_t,
                                  parts.index(sections[i].part), sections[i].order_in_part))
    ordered = [sections[i] for i in order]

    title, course = lecture_meta(root, lid)
    new_slug = "%s_%s" % (lid, sanitize(title))
    rel_new = "wiki/lectures/%s.md" % new_slug
    merged = build_merged(lid, title, course, parts, ordered, today)

    a_before = sum(p.anchors for p in parts)
    a_after = len(ANCHOR.findall(merged))
    q_before = sum(p.quotes for p in parts)
    q_after = len(QUOTE.findall(merged))

    log("  파트 %d개 → 주제 %d개, 최종 순서:" % (len(parts), len(ordered)))
    for i, sec in enumerate(ordered, 1):
        sl = sec.slides
        rng = ("s%d~%d" % (sl[0], sl[-1])) if len(sl) > 1 else ("s%d" % sl[0] if sl else "s?")
        log("    %2d. [%-7s] %s  ← %s" % (i, rng, sec.title, sec.part.path.name))
    log("  파트 파일: " + ", ".join(dedupe([s.part.path.name for s in ordered])))
    log("  병합 대상: %s" % rel_new)
    log("  앵커 %d → %d %s · 🗣 인용 %d → %d %s"
        % (a_before, a_after, "✓" if a_before == a_after else "✗",
           q_before, q_after, "✓" if q_before == q_after else "✗"))

    if a_before != a_after or q_before != q_after:
        log("  ✖ 중단: 앵커/인용 수가 보존되지 않았다. 이 강의는 손대지 않는다.")
        return False

    # 이미 병합된 상태인가 (멱등)
    single = len(parts) == 1 and parts[0].rel == rel_new
    if single and parts[0].text == merged:
        log("  = 이미 병합됨 — 변경 없음(no-op)")
        return True

    verdict = run_guard(root, "compile", rel_new, merged, run_id)
    log("  훅 판정(compile → %s): %s%s" % (rel_new, verdict.get("decision"),
                                          "" if verdict.get("decision") == "allow"
                                          else "  " + str(verdict.get("reason", ""))))
    if verdict.get("decision") != "allow":
        log("  ✖ 훅이 막았다 — 이 강의는 손대지 않는다.")
        return False

    old_slugs = [p.slug for p in parts]
    stale = []
    for tgt in link_targets(root):
        old_text = tgt.read_text(encoding="utf-8")
        new_text, hits = rewrite_links(old_text, old_slugs, new_slug)
        if hits:
            stale.append((tgt, old_text, new_text, hits))
    if stale:
        log("  인바운드 링크:")
        for tgt, _o, _n, hits in stale:
            log("    %s → %s" % (tgt.relative_to(root), ", ".join(dedupe(hits))))
    else:
        log("  인바운드 링크: 없음")

    if not apply:
        log("  (드라이런 — 쓰지 않음)")
        return True

    # 1) 파트를 백업으로 옮기고 2) 병합본을 마지막에 쓴다(이름이 겹칠 수 있다)
    backup = root / "wiki" / ".merged-backup" / run_id
    backup.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        for p in parts:
            dest = backup / p.path.name
            shutil.move(str(p.path), str(dest))
            moved.append((dest, p.path))
        target = root / rel_new
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(merged, encoding="utf-8")
    except Exception as exc:                                   # noqa: BLE001 — 되돌리고 보고한다
        for dest, orig in moved:
            if dest.exists() and not orig.exists():
                shutil.move(str(dest), str(orig))
        if (root / rel_new).exists() and rel_new not in [p.rel for p in parts]:
            (root / rel_new).unlink()
        log("  ✖ 쓰기 실패 — 파트를 되돌렸다: %s" % exc)
        return False
    log("  ✔ 썼다: %s  (백업: wiki/.merged-backup/%s/ %d개)" % (rel_new, run_id, len(moved)))

    for tgt, old_text, new_text, hits in stale:
        rel = str(tgt.relative_to(root))
        agent = agent_for(rel, old_text, new_text)
        v = run_guard(root, agent, rel, new_text, run_id)
        if v.get("decision") == "allow":
            tgt.write_text(new_text, encoding="utf-8")
            log("  ✔ 링크 갱신(%s): %s (%d곳)" % (agent, rel, len(hits)))
        else:
            log("  ⚠ 링크 갱신 거부(%s): %s — %s  (원문 유지, 수동 확인 필요)"
                % (agent, rel, v.get("reason", "")))
    return True


# ---------- main ----------

def collect(root, only):
    ldir = root / "wiki" / "lectures"
    groups = {}
    if not ldir.is_dir():
        return groups
    for p in sorted(ldir.glob("*.md")):
        m = LECTURE_FILE.match(p.name)
        if m:
            groups.setdefault(m.group(1), []).append(p)
    if only:
        groups = {k: v for k, v in groups.items() if k in only}
    return groups


def main(argv=None):
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="강의 노트 조각을 강의당 한 장으로 합친다(결정론적).")
    ap.add_argument("--root", default=str(here), help="저장소 루트 (기본: %s)" % here)
    ap.add_argument("--lecture", nargs="+", default=None, metavar="Ln",
                    help="이 강의만 처리 (예: --lecture L1 L2). 없으면 파트가 2개 이상인 강의 전부")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(기본은 드라이런)")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not (root / "wiki" / "lectures").is_dir():
        print("루트에 wiki/lectures 가 없다: %s" % root, file=sys.stderr)
        return 2
    if not (root / "hooks" / "write_page_guard.py").is_file():
        print("루트에 hooks/write_page_guard.py 가 없다(훅 없이는 쓰지 않는다): %s" % root, file=sys.stderr)
        return 2

    only = None
    if args.lecture:
        only = {x.upper() for x in args.lecture}
        bad = [x for x in only if not re.fullmatch(r"L\d+", x)]
        if bad:
            print("강의 id 형식이 아니다: %s" % ", ".join(bad), file=sys.stderr)
            return 2

    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    today = datetime.date.today().isoformat()
    groups = collect(root, only)

    lines = []
    log = lines.append
    log("루트: %s" % root)
    log("모드: %s" % ("APPLY(실제 쓰기)" if args.apply else "DRY-RUN(계획만)"))
    log("")

    done = failed = skipped = 0
    for lid in sorted(groups, key=lambda x: int(x[1:])):
        files = groups[lid]
        named = bool(only and lid in only)
        log("━━ %s  (%s)" % (lid, ", ".join(f.name for f in files)))
        if lid in SKIP_LECTURES and not named:
            log("  – 견본/수작업 강의라 건너뜀")
            skipped += 1
            log("")
            continue
        if len(files) < 2 and not named:
            log("  – 파일이 1개뿐 — 이미 병합됨(no-op)")
            skipped += 1
            log("")
            continue
        ok = process_lecture(root, lid, files, args.apply, run_id, today, log)
        done += 1 if ok else 0
        failed += 0 if ok else 1
        log("")

    log("요약: 처리 %d · 실패 %d · 건너뜀 %d" % (done, failed, skipped))
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
