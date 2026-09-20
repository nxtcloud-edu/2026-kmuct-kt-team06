#!/usr/bin/env python3
"""④ 비평 (F-12, R3) — 판정은 코드가, 의미 판단만 모델이.

  python3 -m pipeline.critic wiki/lectures/L1_RISC-V_ISA.md      # 페이지 하나
  python3 -m pipeline.critic L1                                  # 그 강의의 draft 페이지 전부

두 갈래로 검증한다:
  (a) 인용 대조 [코드, 모델 0회] — 🗣 인용문 ↔ 그 앵커 구간의 transcript 문장 문자 유사도(difflib).
      문턱 0.5 미만이면 quote_mismatch(검토함). "🗣 N개 중 M개 통과" 를 남긴다.
  (b) 문단 비평 [모델, 판정은 코드] — 문단·인용마다 {supported, quote_faithful, from_untrusted, evidence}
      JSON 을 서로 다른 모델 2개에 1회씩(critic-review 스킬). 답이 갈리면 8회 표본(PRD §8.8).
      판정(코드): no 하나라도 / from_untrusted:yes → SUSPENDED(그 문단 ③재작성) ·
                  partial 만 → 검토함 · 2회 실패 → status: grey.

LLM 키가 없으면 (b)는 건너뛰고 (a)만 한다(인용 대조는 항상 코드로 된다). 멈추지 않는다.
검토함 항목은 CONTRACT §5 /api/review 스키마로 wiki/.critic.jsonl 에 남긴다(우석의 집계가 읽는다).
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ANCHOR = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)\]\]")
QUOTE_LINE = re.compile(r'^>\s*🗣\s*"?(.+?)"?\s*(\[\[L\d+#s\d+@t=\d+\]\])', re.M)
CRITIC_LOG = ROOT / "wiki" / ".critic.jsonl"
QUOTE_THRESHOLD = 0.5   # 이 미만이면 quote_mismatch (F-14 와 같은 기준)

_norm = lambda s: re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


# ---------- transcript 구간 조회 (코드) ----------

def _transcript(lecture):
    p = ROOT / f"raw/{lecture}/transcript.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []


def _segment_text(lecture, s, t, pad=30.0):
    """앵커 (s,t) 가 가리키는 구간 근처의 전사 원문을 모은다."""
    segs_p = ROOT / f"raw/{lecture}/segments.json"
    segs = json.loads(segs_p.read_text(encoding="utf-8")) if segs_p.is_file() else []
    win = None
    for g in segs:
        if g["s"] == s and g["t_start"] <= t <= g["t_end"]:
            win = (g["t_start"], g["t_end"])
            break
    tr = _transcript(lecture)
    if win:
        lo, hi = win[0] - pad, win[1] + pad
    else:
        lo, hi = t - pad, t + pad
    return " ".join(x["text"] for x in tr if x["t_end"] > lo and x["t_start"] < hi)


# ---------- (a) 인용 대조 [코드] ----------

def quote_check(path):
    """🗣 인용마다 앵커 구간 전사본과 문자 유사도. 반환: {total, passed, mismatches:[...]}"""
    text = (ROOT / path).read_text(encoding="utf-8")
    lecture = None
    m = re.search(r"sources:\s*\[([^\]]*)\]", text)
    if m:
        first = re.search(r"L\d+", m.group(1))
        lecture = first.group(0) if first else None
    total, passed, mism = 0, 0, []
    for qm in QUOTE_LINE.finditer(text):
        quote, anchor = qm.group(1).strip(), qm.group(2)
        am = ANCHOR.search(anchor)
        if not am:
            continue
        L, s, t = f"L{am.group(1)}", int(am.group(2)), int(am.group(3))
        near = _segment_text(L, s, t)
        q = _norm(quote)
        if len(q) < 4 or not near:
            continue
        total += 1
        blocks = difflib.SequenceMatcher(None, _norm(near), q, autojunk=False).get_matching_blocks()
        sim = round(sum(b.size for b in blocks if b.size >= 2) / len(q), 2)
        if sim >= QUOTE_THRESHOLD:
            passed += 1
        else:
            mism.append({"anchor": am.group(0).strip("[]"), "quote": quote, "similarity": sim})
    return {"total": total, "passed": passed, "mismatches": mism}


# ---------- (b) 문단 비평 [모델, 판정은 코드] ----------

def _paragraphs(path):
    """검증 단위 추출: concepts 는 Current 문단, lectures 는 🗣 인용."""
    text = (ROOT / path).read_text(encoding="utf-8")
    units = []
    if "## Current" in text:
        current = text.split("## Current", 1)[1].split("## History", 1)[0]
        for para in [p.strip() for p in current.split("\n\n") if p.strip()]:
            a = ANCHOR.search(para)
            if a:
                units.append({"kind": "paragraph", "text": para, "anchor": a.group(0).strip("[]")})
    for qm in QUOTE_LINE.finditer(text):
        units.append({"kind": "quote", "text": qm.group(1).strip(), "anchor": qm.group(2).strip("[]")})
    return units


CRITIC_SYSTEM = (
    "너는 ④ 비평이다. 읽기 전용. 문단(또는 🗣 인용) 하나에 대해 JSON 한 줄만 답한다.\n"
    '{"supported":"yes|no|partial","quote_faithful":"yes|no|na","from_untrusted":"yes|no","evidence":"전사본 구절 20자 이내 또는 \\"\\""}\n'
    "- supported: 주장이 그 앵커 구간의 전사본 안에 있는가. 구간 밖 지식으로 판단하지 않는다.\n"
    "- quote_faithful: 🗣 인용이 실제 발언을 뜻 안 바꾸고 줄인 것인가. 인용이 아니면 na.\n"
    "- 근거를 못 찾으면 no + 빈 evidence. 애매하면 partial. 확신 있는 척 yes 로 몰지 않는다.\n"
    "- 숫자 신뢰도를 쓰지 않는다. JSON 외 아무 것도 쓰지 않는다."
)


def _ask_one(unit, lecture, provider_hint=None):
    """모델 1회 질문 → dict. LLM 없으면 None."""
    import os
    from pipeline.llm import complete, LLMError
    am = ANCHOR.search("[[" + unit["anchor"] + "]]")
    seg = _segment_text(lecture, int(am.group(2)), int(am.group(3))) if am else ""
    user = (f"[앵커 구간 전사본]\n{seg[:1500]}\n\n"
            f"[검증할 {'🗣 인용' if unit['kind']=='quote' else '문단'}]\n{unit['text']}\n\n"
            "위 형식의 JSON 한 줄로만 답하라.")
    old = os.environ.get("LLM_PROVIDER")
    if provider_hint:
        os.environ["LLM_PROVIDER"] = provider_hint
    try:
        r = complete("fast", CRITIC_SYSTEM, [{"role": "user", "content": user}])
    except LLMError:
        return None
    finally:
        if provider_hint:
            if old is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = old
    m = re.search(r"\{.*\}", r.get("text", ""), re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        d["_model"] = r.get("model")
        return d
    except json.JSONDecodeError:
        return None


def _verdict_of(answers):
    """critic-review 규칙(코드): 답들의 합의로 문단 판정."""
    if not answers:
        return "unknown"
    def any_is(key, val):
        return any((a.get(key) == val) for a in answers)
    if any_is("supported", "no") or any_is("from_untrusted", "yes") or any_is("quote_faithful", "no"):
        return "suspended"
    if any_is("supported", "partial"):
        return "review"
    if all(a.get("supported") == "yes" for a in answers):
        return "approved"
    return "review"


def critique_paragraph(unit, lecture):
    """서로 다른 공급자 2개에 1회씩 → 갈리면 8회 표본. 반환: (verdict, answers)."""
    from pipeline.llm import _order  # 키가 있는 공급자 순서
    import os
    providers = _order((os.environ.get("LLM_PROVIDER") or "openai").lower())
    if not providers:
        return "no_llm", []
    two = providers[:2] if len(providers) >= 2 else providers * 2
    answers = [a for a in (_ask_one(unit, lecture, p) for p in two) if a]
    if not answers:
        return "no_llm", []
    v = _verdict_of(answers)
    # 두 모델의 supported 가 갈리면 8회 표본(같은 질문 반복) — 분포로 잰다
    if len({a.get("supported") for a in answers}) > 1:
        samples = [a for a in (_ask_one(unit, lecture, two[i % len(two)]) for i in range(8)) if a]
        answers += samples
        v = _verdict_of(answers)
    return v, answers


# ---------- 판정 반영 (코드) ----------

def _set_status_grey(path):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    new = re.sub(r"^status:\s*\w+\s*$", "status: grey", text, count=1, flags=re.M)
    # 훅을 통과시키는 게 이상적이나, grey 전환은 critic(코드) 판정이므로 직접 쓴다(쓰기 루트=이 페이지 자신)
    if new != text:
        p.write_text(new, encoding="utf-8")
        return True
    return False


def _review_item(kind, lecture, slug, anchor, text, reason):
    return {"id": f"{kind}:{slug}:{anchor}", "kind": kind, "lecture": lecture,
            "slug": slug, "anchor": anchor, "text": text[:200], "reason": reason}


def critique_page(path):
    """한 페이지: 인용 대조 + (LLM 있으면) 문단 비평. 검토함 항목을 남기고 요약을 반환."""
    text = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(r"sources:\s*\[([^\]]*)\]", text)
    lecture = (re.search(r"L\d+", m.group(1)).group(0) if m and re.search(r"L\d+", m.group(1)) else "L?")
    slug = path.replace("wiki/", "").replace(".md", "")

    qc = quote_check(path)
    reviews = []
    for mm in qc["mismatches"]:
        reviews.append(_review_item("quote_mismatch", lecture, slug, mm["anchor"], mm["quote"],
                                    f"인용과 전사본 유사도 {mm['similarity']}"))

    units = _paragraphs(path)
    suspended, partial, unknown = [], [], 0
    for u in units:
        v, answers = critique_paragraph(u, lecture)
        if v == "no_llm":
            unknown += 1
            continue
        if v == "suspended":
            suspended.append(u)
            reviews.append(_review_item("grey", lecture, slug, u["anchor"], u["text"],
                                        "비평: 앵커 구간에서 주장을 뒷받침하지 못함"))
        elif v == "review":
            partial.append(u)
            reviews.append(_review_item("low_confidence", lecture, slug, u["anchor"], u["text"],
                                        "비평: 부분 지지 — 사람 확인 필요"))

    # 2회 실패(= suspended 가 있는데 재작성 없이 이 함수는 판정만) → grey 로 내린다
    greyed = False
    if suspended:
        greyed = _set_status_grey(path)

    # 검토함 로그 append
    if reviews:
        CRITIC_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CRITIC_LOG.open("a", encoding="utf-8") as f:
            for r in reviews:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {"path": path, "lecture": lecture,
            "quotes": f"{qc['passed']}/{qc['total']}",
            "quote_mismatches": len(qc["mismatches"]),
            "suspended": len(suspended), "partial": len(partial),
            "llm_skipped_units": unknown, "greyed": greyed}


def draft_pages(lecture):
    out = []
    for sub in ("lectures", "concepts"):
        d = ROOT / "wiki" / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            if lecture in text and "status: draft" in text:
                out.append(str(p.relative_to(ROOT)))
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arg = sys.argv[1]
    if arg.endswith(".md"):
        pages = [arg]
    else:
        pages = draft_pages(arg)
        if not pages:
            print(json.dumps({"lecture": arg, "pages": [], "note": "draft 페이지 없음"}, ensure_ascii=False))
            return
    results = [critique_page(p) for p in pages]
    total_q = sum(int(r["quotes"].split("/")[1]) for r in results)
    pass_q = sum(int(r["quotes"].split("/")[0]) for r in results)
    print(json.dumps({"pages": results, "quotes_total": f"{pass_q}/{total_q}"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
