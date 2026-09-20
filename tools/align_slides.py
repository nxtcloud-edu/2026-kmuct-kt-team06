#!/usr/bin/env python3
"""녹음+슬라이드 강의의 구간표 초안 (PRD §8.5 ①). 영상이 없어 장면 분할을 못 쓸 때.

  python3 tools/align_slides.py <교본.md> <다글로 전사본.md> <out_dir> [--duration 초] [--review]

입력  교본  = lecture-md 스킬 출력 (`<!-- page N | ... -->` 로 슬라이드 구분)
      전사본 = 다글로 md (`## HH:MM:SS` 문단)
출력  <out_dir>/segments.json (kind:"slide", final_frame:null) + transcript.json
방법  슬라이드 고유 단어(TF-IDF)가 전사 문단에 나오는 점수표 → "슬라이드는 앞으로만 넘어간다"는
      단조 제약 아래 점수 합이 최대인 분할(동적계획법). 모델 호출 없음. 애매한 경계는 --review 로 표시.
"""
import json, math, re, sys
from collections import Counter
from pathlib import Path

TOK = re.compile(r"[A-Za-z][A-Za-z0-9\-']+|[가-힣]{2,}|\d+")
STOP = set("the of and to in is for on with that this are as be by an it 그리고 그래서 이렇게 있습니다 합니다 하는 되는 이제 우리 여기 그런 이런 것을 것이 수업 시간".split())
# 다글로는 영어 용어를 한글로 받아 적는 일이 잦다 → 슬라이드의 영어 단어에 한글 표기를 덧붙여 준다
KO = {"instruction": "인스트럭션", "register": "레지스터", "memory": "메모리", "operand": "오퍼랜드", "immediate": "이미디어트",
      "compile": "컴파일", "stack": "스택", "heap": "힙", "byte": "바이트", "endian": "엔디안", "signed": "사인드",
      "unsigned": "언사인드", "complement": "보수", "extension": "익스텐션", "arithmetic": "산술", "address": "주소",
      "design": "디자인", "principle": "원칙", "constant": "상수", "binary": "이진", "negation": "부호", "array": "배열"}


def toks(text):
    out = []
    for w in TOK.findall(text):
        w = w.lower()
        if w in STOP:
            continue
        out.append(w)
        if w in KO:
            out.append(KO[w])
        if w.endswith("s") and w[:-1] in KO:
            out.append(KO[w[:-1]])
    return out


def read_slides(path):
    parts = re.split(r"<!-- page (\d+)[^>]*-->", Path(path).read_text(encoding="utf-8"))
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def read_transcript(path):
    parts = re.split(r"^## (\d+):(\d\d):(\d\d)\s*$", Path(path).read_text(encoding="utf-8"), flags=re.M)
    out = []
    for i in range(1, len(parts), 4):
        h, m, s = (int(x) for x in parts[i:i + 3])
        text = parts[i + 3].strip()
        if text:
            out.append({"t_start": float(h * 3600 + m * 60 + s), "text": text})
    return out


def align(slides, paras):
    n, w = len(slides), len(paras)
    stoks = [Counter(toks(t)) for _, t in slides]
    df = Counter(k for c in stoks for k in c)
    idf = {k: math.log((n + 1) / (v + 0.5)) for k, v in df.items()}
    ptoks = [Counter(toks(p["text"])) for p in paras]
    score = [[sum(min(pc[k], 3) * idf[k] * (1 + math.log(sc[k])) for k in pc if k in sc) for pc in ptoks] for sc in stoks]
    pre = [[0.0] * (w + 1) for _ in range(n)]
    for i in range(n):
        for j in range(w):
            pre[i][j + 1] = pre[i][j] + score[i][j]
    NEG = -1e18
    best = [[NEG] * (w + 1) for _ in range(n + 1)]
    back = [[0] * (w + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(1, n + 1):
        for b in range(w + 1):
            for a in range(b + 1):  # 슬라이드 i 가 문단 [a, b) 를 덮는다. a==b 면 그 슬라이드는 말 없이 지나감
                if best[i - 1][a] == NEG:
                    continue
                v = best[i - 1][a] + pre[i - 1][b] - pre[i - 1][a] - (0.4 if a == b else 0.0)
                if v > best[i][b]:
                    best[i][b], back[i][b] = v, a
    cuts, b = [], w
    for i in range(n, 0, -1):
        a = back[i][b]
        cuts.append((i - 1, a, b))
        b = a
    return list(reversed(cuts)), score


CUE = re.compile(r"다음\s*슬라이드로|다음\s*장으로|넘어가서|넘어가겠|넘어가도록|다음으로")


def refine(segs, paras):
    """문단(약 50초) 단위 경계를 단서 표현("다음 슬라이드로 넘어가서") 위치로 당긴다. 문단 안 시각은 글자 위치로 보간."""
    by_start = {p["t_start"]: p for p in paras}
    by_end = {p["t_end"]: p for p in paras}
    moved = 0
    for a, b in zip(segs, segs[1:]):
        prev_p, next_p = by_end.get(a["t_end"]), by_start.get(b["t_start"])
        for p, pick, lo, hi in ((prev_p, -1, 0.0, 1.0), (next_p, 0, 0.0, 0.6)):
            if not p:
                continue
            hits = [m.start() / max(len(p["text"]), 1) for m in CUE.finditer(p["text"])]
            hits = [h for h in hits if lo <= h <= hi]
            if hits:
                t = round(p["t_start"] + hits[pick] * (p["t_end"] - p["t_start"]), 1)
                if a["t_start"] + 30 < t < b["t_end"]:  # 직전 전환의 단서를 다시 잡지 않게
                    a["t_end"] = b["t_start"] = t
                    b["cue"] = True
                    moved += 1
                break
    return moved


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        sys.exit(__doc__)
    slides, paras = read_slides(args[0]), read_transcript(args[1])
    out = Path(args[2]); out.mkdir(parents=True, exist_ok=True)
    dur = float(sys.argv[sys.argv.index("--duration") + 1]) if "--duration" in sys.argv else paras[-1]["t_start"] + 60
    for p, nxt in zip(paras, paras[1:] + [{"t_start": dur}]):
        p["t_end"] = nxt["t_start"]
    cuts, score = align(slides, paras)
    segs, k = [], 0
    for i, a, b in cuts:
        if a == b:
            continue
        k += 1
        own = sum(score[i][a:b]) / (b - a)
        rival = max((sum(score[x][a:b]) / (b - a) for x in range(len(slides)) if x != i), default=0)
        segs.append({"k": k, "kind": "slide", "s": slides[i][0], "t_start": paras[a]["t_start"], "t_end": paras[b - 1]["t_end"],
                     "final_frame": None, "ocr": "", "ocr_engine": "lecture-md",
                     "confidence": round(own / (own + rival + 1e-9), 2)})
    moved = refine(segs, paras)
    (out / "segments.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "transcript.json").write_text(json.dumps(paras, ensure_ascii=False, indent=1), encoding="utf-8")
    skipped = [slides[i][0] for i, a, b in cuts if a == b]
    print(f"단서 표현으로 당긴 경계 {moved}개 · ", end="")
    print(f"슬라이드 {len(slides)}장 · 전사 문단 {len(paras)}개 → 구간 {len(segs)}개 · 말 없이 지나간 슬라이드 {skipped}")
    if "--review" in sys.argv:
        for g in segs:
            first = next((p["text"] for p in paras if p["t_start"] <= g["t_start"] < p["t_end"]), "")
            if g.get("cue"):
                m = CUE.search(first); first = "…" + first[m.start():] if m else first
            flag = "  ⚠️ 검수" if g["confidence"] < 0.55 else ""
            m0, m1 = divmod(int(g["t_start"]), 60), divmod(int(g["t_end"]), 60)
            print(f"s{g['s']:>2} {m0[0]:02d}:{m0[1]:02d}–{m1[0]:02d}:{m1[1]:02d} conf={g['confidence']:.2f}{flag} | {first[:70]}")


if __name__ == "__main__":
    main()
