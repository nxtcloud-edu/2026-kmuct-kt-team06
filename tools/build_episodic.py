#!/usr/bin/env python3
"""② 정렬 — 코드로 한다(모델 없음). segments.json + transcript.json → wiki/episodic/L{n}.md

  python3 tools/build_episodic.py L1 [--dry]

구간마다 `## s{s} @t={초}` 블록을 만들고, 그 구간의 전사 문장마다 앵커를 붙인다. 앵커의 t 는 문장 시작 초(구간 안으로 자름).
일치율(agree, PRD §8.9)이 0.5 미만인 문장에는 `🔈?` 를 붙여 ③ 컴파일이 🗣 인용으로 쓰지 못하게 한다.
쓰기는 직접 하지 않는다 — hooks/write_page_guard.py 에 agent=align 으로 태운다(쓰기 경로는 하나).
"""
import json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(lec):
    raw = ROOT / "raw" / lec
    segs = json.loads((raw / "segments.json").read_text(encoding="utf-8"))
    sents = json.loads((raw / "transcript.json").read_text(encoding="utf-8"))
    n = lec[1:]
    out = [f"---\ntitle: {lec} episodic\ntype: episodic\nsources: [{lec}]\nstatus: draft\n---\n"]
    used = 0
    for g in segs:
        lo, hi = math.ceil(g["t_start"]), math.floor(g["t_end"])
        out.append(f"\n## s{g['s']} @t={lo}\n")
        for x in sents:
            if not (g["t_start"] <= x["t_start"] < g["t_end"]):
                continue
            t = min(max(int(x["t_start"]), lo), hi)
            mark = " 🔈?" if (x.get("agree") is not None and x["agree"] < 0.5) else ""
            out.append(f"- {x['text'].strip()}{mark} [[L{n}#s{g['s']}@t={t}]]")
            used += 1
    return "\n".join(out) + "\n", used, len(sents)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lec = sys.argv[1]
    md, used, total = build(lec)
    print(f"{lec}: 문장 {used}/{total}개 배정, {md.count(chr(10) + '## ')}구간", file=sys.stderr)
    if "--dry" in sys.argv:
        print(md[:1200]); sys.exit(0)
    ev = {"tool_name": "append_episodic", "agent": "align", "run": "build_episodic",
          "tool_input": {"path": f"wiki/episodic/{lec}.md", "content": md}}
    r = subprocess.run([sys.executable, str(ROOT / "hooks/write_page_guard.py")], input=json.dumps(ev), capture_output=True, text=True)
    verdict = json.loads(r.stdout)
    print(json.dumps(verdict, ensure_ascii=False))
    if verdict["decision"] == "allow":
        p = ROOT / f"wiki/episodic/{lec}.md"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(md, encoding="utf-8")
    else:
        sys.exit(2)
