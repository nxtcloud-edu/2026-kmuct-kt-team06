#!/usr/bin/env python3
"""grep_wiki(pattern, paths, max_hits) — 위키 전체 정확 문자열/정규식 검색. 읽기 전용.
rg 있으면 rg, 없으면 Python re. 페이지당 최대 3줄, 전체 max_hits.
반환: [{"path", "line", "text"}]  /  모델용 문자열은 format_hits()
"""
import json, os, re, shutil, subprocess, sys

DEFAULT_PATHS = ["wiki/concepts", "wiki/lectures", "wiki/episodic"]

def grep_wiki(pattern, paths=None, max_hits=20, per_file=3, ignore_case=True):
    paths = [p for p in (paths or DEFAULT_PATHS) if os.path.exists(p)]
    hits = []
    if shutil.which("rg"):
        cmd = ["rg", "-n", "--no-heading", "--max-count", str(per_file), "-g", "*.md"]
        if ignore_case: cmd.append("-i")
        cmd += ["-e", pattern] + paths
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        for ln in out.splitlines():
            p, n, t = ln.split(":", 2)
            hits.append({"path": p, "line": int(n), "text": t.strip()})
    else:
        rx = re.compile(pattern, re.I if ignore_case else 0)
        for root in paths:
            for d, _, fs in os.walk(root):
                for f in sorted(fs):
                    if not f.endswith(".md"): continue
                    fp, cnt = os.path.join(d, f), 0
                    with open(fp, encoding="utf-8", errors="ignore") as fh:
                        for i, ln in enumerate(fh, 1):
                            if rx.search(ln):
                                hits.append({"path": fp, "line": i, "text": ln.strip()}); cnt += 1
                                if cnt >= per_file: break
    return hits[:max_hits]

def format_hits(hits):
    if not hits: return "No matches in wiki/."
    return "\n".join(f"{h['path']}:{h['line']} — {h['text'][:160]}" for h in hits)

if __name__ == "__main__":
    a = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(format_hits(grep_wiki(a["pattern"], a.get("paths"), a.get("max_hits", 20))))
