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
    "linker":  ["wiki/index.md", "wiki/TAXONOMY.md", "wiki/concepts/", "wiki/lectures/"],
}
AUDIT = pathlib.Path("wiki/.history.jsonl")

def deny(reason): return {"decision": "block", "reason": f"REJECTED: {reason}"}
def sha(s):       return hashlib.sha256(s.encode()).hexdigest()[:12]
def body(c):      return c.split("---", 2)[-1] if c.count("---") >= 2 else c

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"

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
    if tool not in ("write_page", "append_episodic"):
        return {"decision": "allow"}
    path = ev["tool_input"].get("path", "")
    content = ev["tool_input"].get("content", "")

    roots = WRITE_ROOTS.get(agent, [])
    if not any(path.startswith(r) for r in roots):
        return deny(f"{agent} may only write under {roots}, got '{path}'")
    if ".." in path:
        return deny("path escapes wiki/")

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
                old = pathlib.Path(path).read_text() if pathlib.Path(path).exists() else ""
                if body(old).strip() != body(content).strip():
                    return deny("linker may only change frontmatter 'links:'")

    for m in ANCHOR.finditer(content):
        L, s, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not source_exists(L, s, t):
            return deny(f"anchor {m.group(0)}: L{L} slide {s} has no segment at t={t}")

    old = pathlib.Path(path).read_text() if pathlib.Path(path).exists() else ""
    log({"agent": agent, "tool": tool, "path": path, "verdict": "allow",
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
             "path": ev.get("tool_input", {}).get("path"), "verdict": "deny", "reason": out["reason"]})
    print(json.dumps(out, ensure_ascii=False))
