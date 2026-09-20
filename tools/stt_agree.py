#!/usr/bin/env python3
"""음성 confidence = 두 전사본의 일치율 (PRD §8.9). LLM 없음.

  python3 tools/stt_agree.py <기준 transcript.json> <비교 transcript.json> [--write]

기준(보통 Grok, 문장 단위)의 문장마다, 비교(보통 다글로)의 같은 시간대 글과 글자 단위 공통 비율을 `agree` 로 붙인다.
"""
import difflib, json, re, sys
from pathlib import Path

norm = lambda s: re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def agree(base, other, pad=20.0):
    for s in base:
        near = norm(" ".join(p["text"] for p in other if p["t_end"] > s["t_start"] - pad and p["t_start"] < s["t_end"] + pad))
        q = norm(s["text"])
        if len(q) < 6 or not near:
            s["agree"] = None
            continue
        blocks = difflib.SequenceMatcher(None, near, q, autojunk=False).get_matching_blocks()
        s["agree"] = round(sum(b.size for b in blocks if b.size >= 2) / len(q), 2)
    return base


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    base, other = (json.loads(Path(a).read_text(encoding="utf-8")) for a in args[:2])
    out = agree(base, other)
    for s in out:
        a = s["agree"]
        flag = "" if a is None or a >= 0.8 else ("  🔈 표시" if a >= 0.5 else "  🔈 경고(인용 금지)")
        print(f"{int(s['t_start'])//60:02d}:{int(s['t_start'])%60:02d} {'  - ' if a is None else f'{a:4.0%}'}{flag}  {s['text'][:60]}")
    if "--write" in sys.argv:
        Path(args[0]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
