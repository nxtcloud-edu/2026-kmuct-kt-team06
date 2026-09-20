#!/usr/bin/env python3
"""LLM 배선 — pipeline/llm.py 의 complete() 를 쓰되, 아직 없으면 가짜로 배선(design.md).

complete(role, system, messages, tools) -> {text, tool_calls, model}  (팀장 T2 시그니처)

pipeline/llm.py 가 저장소에 들어오면 자동으로 그걸 쓴다. 그 전엔 stub 이
grep_wiki 근거의 첫 앵커를 인용해 답을 만든다 — QAStop 훅을 통과하도록.
"""
from api import store

MODEL_MAP = {"fast": "FAST", "strong": "STRONG", "gemini": "gemini"}


def _real_complete():
    try:
        from pipeline.llm import complete  # 팀장 T2 산출물
        return complete
    except Exception:
        return None


def complete(role, system, messages, tools=None, model="fast"):
    fn = _real_complete()
    if fn is not None:
        try:
            return fn(role=role, system=system, messages=messages, tools=tools)
        except TypeError:
            # 시그니처가 위치인자면
            return fn(role, system, messages, tools)
    return _stub_complete(system, messages, model)


def _stub_complete(system, messages, model):
    """가짜 complete: 마지막 user 메시지 + system 에 담긴 근거에서 첫 앵커를 뽑아 인용.

    system 프롬프트에 근거 문단(앵커 포함)을 넣어 두면 stub 이 그 앵커를 그대로 답에 박아
    QAStop(앵커 필수)을 통과한다. 근거가 없으면 앵커 없는 답 → QAStop 이 막는다(정상).
    """
    user_q = ""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            user_q = m.get("content", "")
            break
    anchors = store.ANCHOR_RE.findall(system or "")  # [(L,s,t), ...]
    if anchors:
        L, s, t = anchors[0]
        text = f"(개발용 응답) 질문 “{user_q[:40]}” 관련 근거를 위키에서 찾았습니다. [[L{L}#s{s}@t={t}]]"
    else:
        text = f"(개발용 응답) 질문 “{user_q[:40]}” 에 대한 근거를 찾지 못했습니다."
    return {"text": text, "tool_calls": [], "model": f"stub-{model}"}
