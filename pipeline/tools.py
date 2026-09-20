#!/usr/bin/env python3
"""③컴파일·④비평·⑦QA 에이전트가 부르는 도구들 (R2). 전부 읽기 전용 — 쓰기는 write_page 하나뿐.

쓰기 경로는 하나다: write_page 는 파일을 직접 열지 않고 hooks/write_page_guard.py 를
**서브프로세스**로 태운다(build_episodic.py 와 같은 패턴). 그래야 훅의 감사로그
(allow/deny · rule · reason · attempt · run)가 wiki/.history.jsonl 에 그대로 남는다.
훅을 재구현하지 않는다 — 호출한다.

도구 스키마(OpenAI function 형식)는 SPECS 에 있고, 오케스트레이터가 에이전트별로
허용된 것만 골라 LLM 에 넘긴다(AgentGuard). dispatch(name, args, ctx) 로 실행한다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "write_page_guard.py"

sys.path.insert(0, str(ROOT))
from tools.grep_wiki import grep_wiki, format_hits  # noqa: E402

ANCHOR = re.compile(r"\[\[L(\d+)#s(\d+)@t=(\d+)\]\]")
SEC = re.compile(r"\n## (s\d+ @t=\d+)\n")


# ---------- 읽기 도구 ----------

def read_episodic(lecture, s_from=None, s_to=None):
    """wiki/episodic/L{n}.md 의 구간들. s_from~s_to(슬라이드 번호) 로 좁힐 수 있다."""
    p = ROOT / f"wiki/episodic/{lecture}.md"
    if not p.is_file():
        return f"no episodic for {lecture}"
    text = p.read_text(encoding="utf-8")
    if s_from is None:
        return text
    # `## s{S} @t=` 헤더로 나눠 s_from<=S<=s_to 인 블록만
    out, keep = [], False
    for line in text.splitlines():
        m = re.match(r"## s(\d+) @t=", line)
        if m:
            S = int(m.group(1))
            keep = (s_from <= S <= (s_to if s_to is not None else s_from))
        if keep:
            out.append(line)
    return "\n".join(out) if out else f"{lecture}: s{s_from}~{s_to} 구간 없음"


def get_slide_text(lecture, s):
    """그 슬라이드의 OCR 텍스트(segments.json 의 ocr). 본문에 옮기지 않고 배정 힌트로만."""
    p = ROOT / f"raw/{lecture}/segments.json"
    if not p.is_file():
        return ""
    for g in json.loads(p.read_text(encoding="utf-8")):
        if g.get("s") == int(s):
            return g.get("ocr", "") or "(ocr 없음)"
    return f"{lecture} s{s} 구간 없음"


def read_page(path):
    """이미 있는 위키 페이지 원문(없으면 빈 문자열 — 개념 페이지 신규/추가 판단용)."""
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def search_wiki(pattern, max_hits=20):
    """위키 전문 검색(정확 문자열/정규식). 기존 개념 페이지를 찾을 때."""
    return format_hits(grep_wiki(pattern, max_hits=max_hits))


def youtube_search(q):
    """보충 영상 검색. 우석의 api/youtube.py 가 있으면 재사용, 없으면 [](콜아웃 생략)."""
    try:
        sys.path.insert(0, str(ROOT / "api"))
        import youtube  # type: ignore
        return json.dumps(youtube.search(q)[:3], ensure_ascii=False)
    except Exception:
        return "[]"  # 없으면 콜아웃을 생략한다(계약: 실패해도 본문은 나온다)


def resolve_reference(text):
    """교수가 '찾아보라'고 넘긴 선수 지식 → 유튜브 후보. youtube_search 얇은 래퍼."""
    return youtube_search(text)


# ---------- 쓰기 도구 (훅을 통과한 것만) ----------

def write_page(path, content, agent, attempt=1, run=None):
    """파일을 직접 열지 않는다. 훅에 태워 allow 면 그때만 쓴다.
    반환: {"decision","reason"?,"rule"?} — deny 면 reason 을 모델에 돌려준다."""
    ev = {"tool_name": "write_page", "agent": agent, "attempt": attempt, "run": run,
          "tool_input": {"path": path, "content": content}}
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(ev),
                       capture_output=True, text=True)
    try:
        verdict = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"decision": "block", "reason": f"REJECTED: hook error: {r.stderr[:200]}", "rule": "R99_other"}
    if verdict.get("decision") == "allow":
        fp = ROOT / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    return verdict


# ---------- dispatch: 오케스트레이터가 tool_call 을 실행 ----------

READ_TOOLS = {
    "read_episodic": lambda a, ctx: read_episodic(a.get("lecture", ctx.get("lecture")),
                                                  a.get("s_from"), a.get("s_to")),
    "get_slide_text": lambda a, ctx: get_slide_text(a.get("lecture", ctx.get("lecture")), a["s"]),
    "read_page": lambda a, ctx: read_page(a["path"]),
    "search_wiki": lambda a, ctx: search_wiki(a["pattern"], a.get("max_hits", 20)),
    "get_source": lambda a, ctx: read_page(a.get("path", "")) or json.dumps(_source(a.get("anchor", "")), ensure_ascii=False),
    "grep_wiki": lambda a, ctx: search_wiki(a["pattern"], a.get("max_hits", 20)),
    "youtube_search": lambda a, ctx: youtube_search(a.get("q", "")),
    "resolve_reference": lambda a, ctx: resolve_reference(a.get("text", "")),
}


def _source(anchor):
    m = re.match(r"L(\d+)#s(\d+)@t=(\d+)", anchor or "")
    if not m:
        return {"exists": False}
    L, s, t = m.group(1), int(m.group(2)), int(m.group(3))
    p = ROOT / f"raw/L{L}/segments.json"
    if not p.is_file():
        return {"exists": False}
    for g in json.loads(p.read_text(encoding="utf-8")):
        if g["s"] == s and g["t_start"] <= t <= g["t_end"]:
            return {"exists": True, "s": s, "t_start": g["t_start"], "t_end": g["t_end"], "ocr": g.get("ocr", "")}
    return {"exists": False}


def dispatch(name, args, ctx):
    """읽기 도구를 실행해 문자열을 돌려준다. write_page 는 오케스트레이터가 직접 부른다(로그·재시도 때문)."""
    if name in READ_TOOLS:
        try:
            return READ_TOOLS[name](args, ctx)
        except Exception as e:
            return f"tool error ({name}): {e}"
    return f"unknown or non-read tool: {name}"


# 도구 스키마 (OpenAI function). 오케스트레이터가 에이전트 허용 셋으로 필터한다.
SPECS = {
    "read_episodic": {"name": "read_episodic", "description": "episodic 노트의 구간(슬라이드+앵커 달린 문장)을 읽는다.",
                      "parameters": {"type": "object", "properties": {
                          "lecture": {"type": "string"}, "s_from": {"type": "integer"}, "s_to": {"type": "integer"}}}},
    "get_slide_text": {"name": "get_slide_text", "description": "슬라이드 OCR 텍스트(배정 힌트, 본문에 옮기지 않음).",
                       "parameters": {"type": "object", "properties": {
                           "lecture": {"type": "string"}, "s": {"type": "integer"}}, "required": ["s"]}},
    "read_page": {"name": "read_page", "description": "기존 위키 페이지 원문(없으면 빈 문자열).",
                  "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    "search_wiki": {"name": "search_wiki", "description": "위키 전문 검색.",
                    "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
    "get_source": {"name": "get_source", "description": "앵커가 가리키는 구간의 전사·OCR(비평·QA용).",
                   "parameters": {"type": "object", "properties": {"anchor": {"type": "string"}}, "required": ["anchor"]}},
    "grep_wiki": {"name": "grep_wiki", "description": "위키 전문 검색(QA·비평용).",
                  "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
    "youtube_search": {"name": "youtube_search", "description": "보충 영상 검색(콜아웃 안에만 쓴다).",
                       "parameters": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}},
    "resolve_reference": {"name": "resolve_reference", "description": "교수가 넘긴 선수 지식 → 영상 후보.",
                          "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    "write_page": {"name": "write_page", "description": "위키 페이지를 쓴다. 훅을 통과해야 실제로 써진다. 거부되면 사유만 고쳐 다시.",
                   "parameters": {"type": "object", "properties": {
                       "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
}


def specs_for(tool_names):
    return [SPECS[t] for t in tool_names if t in SPECS]


if __name__ == "__main__":
    # 스모크: 도구가 실제 데이터를 읽는지
    print("read_episodic L1 s5:")
    print(read_episodic("L1", 5, 5)[:400])
    print("\nget_slide_text L1 s5:", get_slide_text("L1", 5)[:80])
