#!/usr/bin/env python3
"""Exact Quote Search — 위키 요약이 아니라 교수가 **실제로 한 말**만, 시간순으로. LLM 없음. (PRD §4.9)

  python3 tools/quote_search.py <검색어> [raw 디렉터리=raw]
  from tools.quote_search import search   # api/ 에서 import

raw/L*/transcript.json(문장·문단) 을 훑어 검색어가 든 **문장**을 뽑고, segments.json 으로 슬라이드 번호를 붙인다.
문단 단위 전사(다글로)는 문단 안 글자 위치로 시각을 보간한다. 결과의 anchor 는 그대로 점프에 쓴다.
"""
import json, re, sys
from pathlib import Path

SENT = re.compile(r"[^.?!]+[.?!]?")


def search(q, raw="raw", limit=50):
    q = (q or "").strip()
    if len(q) < 2:  # 빈 검색어는 모든 문장에 걸린다
        return []
    out = []
    for d in sorted(Path(raw).glob("L*")):
        tp, sp = d / "transcript.json", d / "segments.json"
        if not tp.exists():
            continue
        segs = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else []
        for p in json.loads(tp.read_text(encoding="utf-8")):
            text, span = p["text"], p["t_end"] - p["t_start"]
            for m in SENT.finditer(text):
                sent = m.group(0).strip()
                if q.lower() not in sent.lower() or len(sent) < 4:
                    continue
                t = p["t_start"] + span * m.start() / max(len(text), 1)
                seg = next((g for g in segs if g["t_start"] <= t <= g["t_end"]), None)
                out.append({"lecture": d.name, "t": round(t, 1), "s": seg["s"] if seg else None, "quote": sent,
                            "anchor": f"{d.name}#s{seg['s']}@t={int(t)}" if seg else None})
    out.sort(key=lambda x: (int(re.sub(r"\D", "", x["lecture"]) or 0), x["t"]))
    return out[:limit]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for r in search(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "raw"):
        m, s = divmod(int(r["t"]), 60)
        print(f"{r['lecture']} {m:02d}:{s:02d} s{r['s']}  “{r['quote'][:110]}”")
