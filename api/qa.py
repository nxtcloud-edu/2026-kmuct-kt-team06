#!/usr/bin/env python3
"""위키에 묻기(F-10). 위키 밖 지식으로 답하지 않는다(CONTRACT §5.2).

흐름:
  1) grep_wiki + 링크 1홉으로 근거 문단을 모은다.
  2) 근거 0개면 모델을 부르지 않고 {answer:null, reason:"NO_GROUNDING", videos}.
  3) 답변을 qa_stop_guard.py 에 태운다. 앵커 없으면 1회 재생성, 그래도 없으면 NO_GROUNDING.
  4) notes[] 는 코드로(답변 앵커와 같은 구간의 필기) 붙인다 — 모델이 아니라.
  5) IP당 분당 10회, 질문 500자 컷.
"""
import json
import re
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from api import store, wiki_read
from api.llm_adapter import complete

ROOT = store.ROOT
QA_STOP = ROOT / "hooks" / "qa_stop_guard.py"
ANCHOR_TEXT = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)(?:-(\d+))?\]\]")

# ── 레이트리밋: IP당 분당 10회 ─────────────────────────────────
_hits: dict[str, deque] = defaultdict(deque)
RATE_LIMIT = 10
WINDOW = 60.0


def rate_ok(ip: str) -> bool:
    now = time.time()
    dq = _hits[ip]
    while dq and now - dq[0] > WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return False
    dq.append(now)
    return True


def _grep(pattern: str):
    try:
        from tools.grep_wiki import grep_wiki
        return grep_wiki(pattern, max_hits=20)
    except Exception:
        return []


_STOP = set("어떻게 무엇 뭐야 뭔가 뭐가 왜 언제 어디 어느 알려줘 설명해줘 설명 해줘 구해 구하는 대해 관해 차이 차이가 달라 다른 그리고 그러면 "
            "있어 없어 인가 인지 하는 되는 이란 란 은 는 이 가 을 를 의 에 로 와 과 도".split())
_JOSA = ("으로부터", "에서는", "이라는", "으로", "에서", "에게", "이란", "라는", "보다", "처럼", "까지", "부터",
         "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만", "란")


def _terms(question: str) -> list[str]:
    """질문에서 검색어를 뽑는다. 한국어 조사는 뒤에서 떼어 본다("머지소트의" → "머지소트")."""
    out = []
    for w in re.split(r"[\s,.?!·/()\[\]\"']+", question):
        w = w.strip()
        if len(w) < 2 or w in _STOP:
            continue
        cands = [w]
        for j in _JOSA:
            if w.endswith(j) and len(w) - len(j) >= 2:
                cands.append(w[: -len(j)])
        for c in cands:
            if c not in _STOP and c not in out:
                out.append(c)
    return out[:12]


def _gather_grounding(question: str, context: dict | None):
    """근거 문단을 **문단 단위 점수**로 고른다(2026-09-20: 페이지 순서대로 앞 8문단만 주던 탓에
    질문과 무관한 문단이 근거로 가고 모델이 없는 앵커를 지어냈다).
    점수 = 질문 검색어가 그 문단에 나온 수(긴 검색어 가중) + 같은 페이지 제목 일치 + 지금 보고 있는 페이지 가산점."""
    pages: dict[str, tuple] = {}
    for rel, fm, body in wiki_read.iter_pages():
        if str(fm.get("status", "")).strip() == "grey":
            continue  # 숨긴 페이지는 근거로 쓰지 않는다
        pages[rel[:-3]] = (fm, body)

    terms = _terms(question)
    ctx_slug = (context or {}).get("slug")
    squash = lambda x: re.sub(r"\s+", "", x.lower())   # "머지 소트"·"시간 복잡도" 같은 띄어쓰기 차이를 무시
    paras = []
    for slug, (fm, body) in pages.items():
        title = squash(str(fm.get("title", "")))
        for para in body.split("\n\n"):
            if ANCHOR_TEXT.search(para):
                paras.append((slug, title, para.strip(), squash(ANCHOR_TEXT.sub("", para))))
    # 흔한 말("시간복잡도")보다 드문 말("머지소트")이 더 무겁다 — 문단 빈도의 역수(IDF)
    import math
    n = max(len(paras), 1)
    weight = {}
    for t in terms:
        k = squash(t)
        df = sum(1 for _s, _t, _p, low in paras if k in low)
        weight[k] = math.log(1 + n / (1 + df)) if df else 0.0
    scored = []
    for slug, title, para, low in paras:
        score = sum(w for k, w in weight.items() if k in low)
        score += 0.5 * sum(w for k, w in weight.items() if w and k in title)
        if score <= 0:
            continue
        if slug == ctx_slug:
            score *= 1.15
        scored.append((round(score, 3), slug, para))
    scored.sort(key=lambda x: -x[0])
    grounds, seen = [], set()
    for score, slug, para in scored:
        if para in seen:
            continue
        seen.add(para)
        grounds.append({"slug": slug, "text": para, "score": score})
        if len(grounds) >= 10:
            break
    return grounds


def _slug_of(path: str) -> str | None:
    p = path.replace("\\", "/")
    for marker in ("wiki/",):
        if marker in p:
            p = p.split(marker, 1)[1]
    if p.endswith(".md"):
        p = p[:-3]
    return p or None


def _qa_stop(final_text: str) -> bool:
    """qa_stop_guard.py 에 태운다. 앵커 있으면 allow."""
    try:
        proc = subprocess.run(
            [sys.executable, str(QA_STOP)],
            input=json.dumps({"final_text": final_text}, ensure_ascii=False),
            capture_output=True, text=True, cwd=str(ROOT), timeout=10,
        )
        out = (proc.stdout or "").strip().splitlines()
        if not out:
            return False
        return json.loads(out[-1]).get("decision") == "allow"
    except Exception:
        return bool(ANCHOR_TEXT.search(final_text))  # 훅 못 부르면 앵커 유무로


def _notes_for(anchors: list[str]) -> list:
    """답변 앵커와 같은 구간의 필기(코드로 붙인다, 모델 아님)."""
    from api import notes as notes_mod
    out, seen = [], set()
    for a in anchors:
        m = ANCHOR_TEXT.search(a)
        if not m:
            continue
        lecture, s = f"L{m.group(1)}", int(m.group(2))
        for n in notes_mod.list_notes(lecture):
            if n.get("s") == s and n.get("anchor") not in seen:
                out.append({"anchor": n.get("anchor"), "text": n.get("text")})
                seen.add(n.get("anchor"))
    return out


def _videos(question: str):
    """질문 키워드로 유튜브 검색(교수 채널 먼저). 실패하면 []. T5 에서 실제 구현."""
    try:
        from api.youtube import search as yt_search
        return yt_search(question)
    except Exception:
        return []


def _system_prompt(grounds) -> str:
    """prompts/07-qa.md 의 규칙 + 근거 문단. 이 경로는 도구 없는 단발 호출이라 도구·스킬 줄은 뺀다."""
    try:
        rules = (ROOT / "prompts" / "07-qa.md").read_text(encoding="utf-8")
    except OSError:
        rules = "역할: 위키에 묻기. <grounding> 의 문단만 근거로 답한다."
    keep = [l for l in rules.splitlines()
            if not l.startswith(("허용 도구", "먼저 qa-answer")) and "<grounding>" not in l]
    body = "\n\n".join(f"[{g['slug']}]\n{g['text']}" for g in grounds)
    return ("\n".join(keep).strip() +
            "\n- <grounding> 에 없는 내용은 아는 것이라도 쓰지 않는다. 근거가 질문에 답하지 못하면 정확히 NO_GROUNDING 만 출력한다."
            "\n- 앵커는 <grounding> 에 있는 것만, 글자 하나 바꾸지 않고 복사한다. 새 앵커를 만들면 답변 전체가 폐기된다."
            f"\n\n<grounding>\n{body}\n</grounding>")


def answer(question: str, model: str = "fast", context: dict | None = None) -> dict:
    question = (question or "")[:500]  # 500자 컷
    videos = _videos(question)

    grounds = _gather_grounding(question, context)
    if not grounds:
        return {
            "answer": None, "anchors": [], "notes": [],
            "unanchored": [question] if question else [],
            "model": model, "reason": "NO_GROUNDING",
            "message": "위키에 근거가 없습니다. 아직 이 내용을 다룬 강의가 들어오지 않았습니다.",
            "videos": videos,
        }

    allowed = {m.group(0) for g in grounds for m in ANCHOR_TEXT.finditer(g["text"])}
    system = _system_prompt(grounds)
    messages = [{"role": "user", "content": question}]

    text = ""
    result = None
    problem = "근거 앵커를 찾지 못했습니다."
    for _attempt in range(2):  # 앵커가 없거나 근거에 없는 앵커를 쓰면 1회 재생성
        try:
            result = complete("qa", system, messages, model=model)
        except Exception as e:  # LLM 실패(키 없음·429·5xx·모델 404) → 서버는 죽지 않는다
            return {
                "answer": None, "anchors": [], "notes": [],
                "unanchored": [question] if question else [],
                "model": model, "reason": "LLM_ERROR",
                "message": f"모델 호출 실패: {str(e)[:120]}",
                "videos": videos,
            }
        text = (result.get("text", "") if isinstance(result, dict) else str(result)).strip()
        if text == "NO_GROUNDING":
            problem = "위키의 근거만으로는 답할 수 없는 질문입니다."
            break
        used = {m.group(0) for m in ANCHOR_TEXT.finditer(text)}
        bogus = sorted(used - allowed)
        if used and not bogus and _qa_stop(text):
            problem = None
            break
        # 재생성 지시: 무엇이 틀렸는지 코드가 알려 준다(정책은 코드)
        if bogus:
            problem = "답변이 근거에 없는 출처를 인용해 폐기했습니다."
            fix = ("다음 앵커는 <grounding> 에 없다: " + ", ".join(bogus[:6]) +
                   ". <grounding> 에 실제로 있는 앵커만 글자 그대로 복사해서 다시 답하라. 근거로 답할 수 없으면 NO_GROUNDING 만 출력하라.")
        else:
            problem = "근거 앵커를 찾지 못했습니다."
            fix = "모든 문장 끝에 <grounding> 의 앵커를 그대로 붙여 다시 답하라. 근거로 답할 수 없으면 NO_GROUNDING 만 출력하라."
        messages = [{"role": "user", "content": question},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": fix}]
    if problem:
        return {
            "answer": None, "anchors": [], "notes": [],
            "unanchored": [question] if question else [],
            "model": model, "reason": "NO_GROUNDING",
            "message": problem,
            "videos": videos,
        }

    anchors = [f"[[L{L}#s{s}@t={t}]]" for L, s, t, _ in ANCHOR_TEXT.findall(text)]
    return {
        "answer": text,
        "anchors": anchors,
        "notes": _notes_for(anchors),
        "unanchored": [],
        "model": result.get("model", model) if isinstance(result, dict) else model,
        "videos": videos,
    }
