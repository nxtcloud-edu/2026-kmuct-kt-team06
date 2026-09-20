#!/usr/bin/env python3
"""PreToolUse 훅. Claude Agent SDK / Kiro 파일 저장 훅 공용.
stdin : {"tool_name", "tool_input": {"path", "content"}, "agent": "compile|align|linker"}
stdout: {"decision": "allow"} | {"decision": "block", "reason": "REJECTED: ..."}
판정 순서 (Aside hasPermission 축소판): deny(경로/형식) -> 앵커 존재 -> allow + 감사로그
"""
import json, re, sys, hashlib, datetime, pathlib

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

def source_exists(L, s, t):
    # TODO: 적재 결과(raw/L{L}/slides.json 등)를 열어 슬라이드 s 존재와 t 구간 확인
    return True

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
        if path.startswith(("wiki/concepts/", "wiki/lectures/")):
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
