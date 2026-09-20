#!/usr/bin/env python3
"""PreToolUse 훅. Claude Agent SDK / Kiro 파일 저장 훅 공용.
stdin : {"tool_name", "tool_input": {"path", "content"}, "agent": "compile|align|linker"}
stdout: {"decision": "allow"} | {"decision": "block", "reason": "REJECTED: ..."}
판정 순서 (Aside hasPermission 축소판): deny(경로/형식) -> 앵커 존재 -> allow + 감사로그
"""
import sys, json, re, hashlib, datetime, pathlib

ANCHOR = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)(?:-(\d+))?\]\]")
WRITE_ROOTS = {
    "compile": ["wiki/concepts/", "wiki/lectures/"],
    "align":   ["wiki/episodic/"],
    "user":    ["wiki/notes/", "wiki/concepts/", "wiki/lectures/"],   # notes 는 쓰기, 나머지는 status 한 줄만(아래)
    "signal-ingest": ["wiki/signals/"],
    "linker":  ["wiki/index.md", "wiki/TAXONOMY.md", "wiki/concepts/", "wiki/lectures/"],
}
ROOT = pathlib.Path(__file__).resolve().parent.parent   # cwd 가 어디든 같은 파일을 본다
AUDIT = ROOT / "wiki/.history.jsonl"

# 거부 사유 → 규칙 ID. 대시보드 집계(tools/hook_metrics.py)의 축. 문구를 바꾸면 여기 패턴도 같이 바꾼다
RULES = [
    ("R01_write_root",   r"may only write under",                 "쓰기 루트 밖"),
    ("R02_path_escape",  r"path escapes|note path must be",       "경로 위조"),
    ("R04_no_anchor",    r"without anchor|has no anchor|no '### 📄|needs numbered sections|needs '## Current'", "앵커·형식 없음"),
    ("R05_dead_anchor",  r"has no segment|points to no segment",  "없는 구간을 가리키는 앵커"),
    ("R06_fake_anchor",  r"not a source anchor|cannot contain source anchors|range anchors", "가짜·범위 앵커"),
    ("R07_external_link", r"outside '> \[!",                     "콜아웃 밖 외부 링크"),
    ("R08_unsafe_html",  r"raw HTML",                             "HTML·스크립트 삽입"),
    ("R09_status_only",  r"may only change frontmatter",          "승인인 척 본문 수정"),
    ("R03_frontmatter",  r"frontmatter",                          "프론트매터 누락"),
    ("R10_size",         r"larger than",                          "크기 초과"),
    ("R11_linker_body",  r"linker may only",                      "링커의 본문 변경"),
]

def rule_of(reason):
    for rid, pat, _ in RULES:
        if re.search(pat, reason):
            return rid
    return "R99_other"

def deny(reason): return {"decision": "block", "reason": f"REJECTED: {reason}", "rule": rule_of(reason)}
def sha(s):       return hashlib.sha256(s.encode()).hexdigest()[:12]
def body(c):      return c.split("---", 2)[-1] if c.count("---") >= 2 else c

RAW = ROOT / "raw"

def source_exists(L, s, t):
    """앵커가 raw/L{L}/segments.json 의 실제 구간(s 일치 + t_start<=t<=t_end)을 가리키나."""
    root = RAW / f"L{L}"
    if not (root / "segments.json").exists():
        return False
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from frame_guard import source_exists as _exists
    return _exists(root, s, t)

YOUTUBE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+")
EXTERNAL = re.compile(r"https?://\S+")
UNSAFE = re.compile(r"<\s*(script|iframe|object|embed|style|link|meta)\b|<[^>]*\bon\w+\s*=|\]\(\s*javascript:", re.I)
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)   # 코드 블록 안의 <object>, onload= 는 글자일 뿐이다
RANGE = re.compile(r"\[\[L\d+#s\d+@t=\d+-\d+\]\]")
NOTE_PATH = re.compile(r"^wiki/notes/L\d+/s\d+\.md$")
FAKE_ANCHOR = re.compile(r"\[\[(?:note|signal):")

def check_lecture(content):
    """강의 노트 포맷(📄 슬라이드 → 💡 설명 → 🗣 교수님 말 → 🎯 포인트). skills/wiki-anchor 참고."""
    text = body(content)
    sections = re.split(r"\n(?=## )", text)
    numbered = [x for x in sections if re.match(r"## \d+\.", x)]
    if not numbered:
        return "lecture page needs numbered sections '## 1. ...'"
    for sec in numbered:
        title = sec.splitlines()[0][:40]
        if "### 📄" not in sec:
            return f"section '{title}' has no '### 📄 슬라이드' block"
        slide = re.split(r"\n### |\n> ", sec.split("### 📄", 1)[1], 1)[0]
        if not ANCHOR.search(slide):
            return f"section '{title}': 📄 슬라이드 block has no anchor"
    # 🗣 인용은 한 블록(연속된 '>' 줄)마다 앵커가 있어야 한다 = 교수가 실제로 그 초에 한 말
    block = []
    for line in text.splitlines() + [""]:
        if line.startswith(">"):
            block.append(line)
            continue
        joined = "\n".join(block)
        if block and block[0].lstrip("> ").startswith("🗣") and not ANCHOR.search(joined):
            return f"🗣 quote without anchor: '{joined.strip()[:60]}'"
        if YOUTUBE.search(joined) and "[!youtube]" not in joined:
            return "youtube link outside '> [!youtube]' callout"
        if EXTERNAL.search(YOUTUBE.sub("", joined)) and "[!ref]" not in joined:
            return "external link outside '> [!ref]' callout"
        block = []
    outside = "\n".join(l for l in text.splitlines() if not l.startswith(">"))
    if EXTERNAL.search(YOUTUBE.sub("", outside)):
        return "external link outside '> [!ref]' callout (레퍼런스 원문은 정본이 아니다)"
    if YOUTUBE.search(outside):
        return "youtube link outside '> [!youtube]' callout (보충 영상은 정본이 아니다)"
    return None

def check(ev):
    agent, tool = ev.get("agent", ""), ev.get("tool_name")
    if tool not in ("write_page", "append_episodic", "save_note"):
        return {"decision": "allow"}
    path = ev["tool_input"].get("path", "")
    content = ev["tool_input"].get("content", "")

    roots = WRITE_ROOTS.get(agent, [])
    if not any(path.startswith(r) for r in roots):
        return deny(f"{agent} may only write under {roots}, got '{path}'")
    if ".." in path or path.startswith("/") or "\\" in path or "\x00" in path:
        return deny("path escapes wiki/")
    if UNSAFE.search(CODE.sub("", content)):
        return deny("raw HTML/script is not allowed in wiki content")
    if RANGE.search(content):
        return deny("range anchors (@t=340-372) are not supported; use a single second")
    old_text = (ROOT / path).read_text(encoding="utf-8") if (ROOT / path).is_file() else ""

    if agent == "user":
        if path.startswith("wiki/notes/"):
            if not NOTE_PATH.match(path):
                return deny("note path must be wiki/notes/L{n}/s{k}.md")
            if len(content.encode()) > 8192:
                return deny("note larger than 8KB")
            m = re.search(r"^anchor:\s*L(\d+)#s(\d+)@t=(\d+)\s*$", content, re.M)
            if not m or not source_exists(int(m.group(1)), int(m.group(2)), int(m.group(3))):
                return deny("note anchor missing or points to no segment")
            if ANCHOR.search(body(content)):
                return deny("notes cannot contain source anchors")
        else:  # 검토함 승인: 프론트매터 status 한 줄만 바꿀 수 있다
            strip = lambda c: re.sub(r"^status:.*$", "status:", c, flags=re.M)
            if not old_text or strip(old_text) != strip(content):
                return deny("user may only change frontmatter 'status:' on wiki pages")
        log({"agent": agent, "tool": tool, "path": path, "verdict": "allow",
             "beforeSha": sha(old_text), "afterSha": sha(content), "beforeContent": old_text, "afterContent": content})
        return {"decision": "allow"}

    if tool == "write_page":
        if not content.startswith("---"):
            return deny("missing frontmatter")
        fm = content.split("---", 2)[1]
        for key in ("title:", "type:", "status:", "sources:"):
            if key not in fm:
                return deny(f"frontmatter missing '{key}'")
        if FAKE_ANCHOR.search(content):
            return deny("[[note:]] / [[signal:]] is not a source anchor")
        if path.startswith("wiki/lectures/"):
            err = check_lecture(content)
            if err:
                return deny(err)
        elif path.startswith("wiki/concepts/"):
            if "## Current" not in content or "## History" not in content:
                return deny("page needs '## Current' and '## History'")
            current = content.split("## Current", 1)[1].split("## History", 1)[0]
            for para in [p for p in current.split("\n\n") if p.strip()]:
                if not ANCHOR.search(para):
                    return deny(f"paragraph without anchor: '{para.strip()[:60]}'")
            if agent == "linker":
                old = old_text
                if body(old).strip() != body(content).strip():
                    return deny("linker may only change frontmatter 'links:'")

    for m in ANCHOR.finditer(content):
        L, s, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not source_exists(L, s, t):
            return deny(f"anchor {m.group(0)}: L{L} slide {s} has no segment at t={t}")

    old = old_text
    log({"agent": agent, "tool": tool, "path": path, "verdict": "allow", "attempt": ev.get("attempt", 1), "run": ev.get("run"),
         "anchors": len(ANCHOR.findall(content)), "quotes": len(re.findall(r"^> 🗣", content, re.M)),
         "beforeSha": sha(old), "afterSha": sha(content),
         "beforeContent": old, "afterContent": content})
    return {"decision": "allow"}

def log(rec):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **rec}
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    ev = json.load(sys.stdin)
    out = check(ev)
    if out["decision"] == "block":
        log({"agent": ev.get("agent"), "tool": ev.get("tool_name"),
             "path": ev.get("tool_input", {}).get("path"), "verdict": "deny", "rule": out.get("rule"),
             "reason": out["reason"], "lecture": (re.search(r"L(\d+)", ev.get("tool_input", {}).get("path", "") or "") or [None, None])[1],
             "attempt": ev.get("attempt", 1), "run": ev.get("run")})
    print(json.dumps(out, ensure_ascii=False))
