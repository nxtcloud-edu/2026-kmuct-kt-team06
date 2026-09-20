#!/usr/bin/env python3
"""LLM 어댑터 — 파이프라인 전 단계가 이 하나만 부른다 (R1, back-kyuchan).

    from pipeline.llm import complete
    r = complete("strong", system, messages, tools)
    # r == {"text": str, "tool_calls": [{"id","name","arguments"}...], "model": "실제-쓴-모델"}

역할(role) → 모델:
    "strong" → 환경변수 LLM_STRONG   (③컴파일 등, 없으면 공급자 기본 강모델)
    "fast"   → 환경변수 LLM_FAST     (④비평·⑦QA 등, 없으면 공급자 기본 경량모델)
    그 외 문자열은 모델 id 그대로 취급한다.

공급자(provider):
    LLM_PROVIDER = openai | anthropic | gemini  (기본 openai)
    429/5xx 면 나머지 공급자로 **1회** 폴백하고, 실제 쓴 공급자의 모델을 결과 model 에 적는다.

키는 환경변수로만: OPENAI_API_KEY · ANTHROPIC_API_KEY · GEMINI_API_KEY.
(OpenAI 호환 엔드포인트는 OPENAI_BASE_URL 로 바꿀 수 있다 — x.ai 등 검증·프록시용)
새 패키지 금지 — urllib(표준 라이브러리)만. 코드·로그·응답에 키를 넣지 않는다.

messages: [{"role":"user"|"assistant"|"tool", "content":str, ...}]
    tool 결과는 {"role":"tool", "tool_call_id":str, "content":str}.
tools:  OpenAI function 스키마 리스트 [{"name","description","parameters":{...}}] (또는 {"type":"function","function":{...}}).
        각 공급자 형식으로 이 안에서 변환한다. 호출부는 한 형식(OpenAI)만 안다.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# .env 의 옛 이름 → 표준 환경변수 이름 (값은 같다, #48)
_ALIASES = {
    "Open_AI": "OPENAI_API_KEY", "OPEN_AI": "OPENAI_API_KEY",
    "Claude_AI": "ANTHROPIC_API_KEY", "CLAUDE_AI": "ANTHROPIC_API_KEY",
    "Gemini_AI": "GEMINI_API_KEY", "GEMINI_AI": "GEMINI_API_KEY",
    "X_AI": "XAI_API_KEY",
}


def _load_dotenv():
    """저장소 루트 .env 를 stdlib 만으로 읽어 os.environ 에 **없는 키만** 채운다(#48).
    KEY=VALUE, # 주석·빈 줄·따옴표 처리. 옛 이름은 표준 이름으로 매핑.
    값은 절대 로그·예외 메시지에 찍지 않는다. api.server 도 pipeline.llm 을 import 하니 같이 해결된다.
    """
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.is_file():
        return
    try:
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if not key:
                continue
            for name in {key, _ALIASES.get(key, key)}:
                if name and name not in os.environ:
                    os.environ[name] = val
    except OSError:
        pass  # .env 를 못 읽어도 (환경변수로 직접 준 경우) 계속 간다


_load_dotenv()

TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))

# 공급자별 기본 모델. LLM_STRONG/LLM_FAST 환경변수가 있으면 그게 우선.
# fable 실측(#48/#49): openai gpt-5-mini·anthropic claude-haiku-4-5 정상, gemini 는 3.6 계열.
# 모델 이름은 자주 죽으므로 배포 환경에서는 LLM_STRONG/LLM_FAST 로 못박는 것을 권장한다.
_DEFAULTS = {
    "openai": {"strong": "gpt-5", "fast": "gpt-5-mini"},
    "anthropic": {"strong": "claude-sonnet-5", "fast": "claude-haiku-4-5"},
    "gemini": {"strong": "gemini-3.6-pro", "fast": "gemini-3.6-flash"},
}
_KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


class LLMError(RuntimeError):
    """모든 공급자가 실패했을 때."""


class _Retryable(Exception):
    """429/5xx — 다음 공급자로 폴백 대상."""


def _model_for(provider: str, role: str) -> str:
    if role == "strong":
        return os.environ.get("LLM_STRONG") or _DEFAULTS[provider]["strong"]
    if role == "fast":
        return os.environ.get("LLM_FAST") or _DEFAULTS[provider]["fast"]
    return role  # 명시적 모델 id


def _norm_tools(tools):
    """OpenAI/평면 두 형식 모두 받아 [{name, description, parameters}] 로."""
    out = []
    for t in tools or []:
        fn = t.get("function", t)
        out.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _post(url: str, headers: dict, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read().decode("utf-8", "replace")[:500]
        if code == 429 or 500 <= code < 600:
            raise _Retryable(f"{code}") from None
        raise LLMError(f"HTTP {code}: {body}") from None
    except urllib.error.URLError as e:
        # 연결 실패도 폴백 대상으로 본다
        raise _Retryable(f"conn: {e.reason}") from None


# ---- 공급자별 호출: (system, messages, tools, model) -> {text, tool_calls} ----

def _to_openai_messages(messages):
    """내부 표현 → OpenAI chat 형식.
    - assistant 의 tool_calls {id, name, arguments(dict)} → {id, type:'function', function:{name, arguments: JSON문자열}}
    - tool 결과 {role:'tool', tool_call_id, content} → 그대로 (OpenAI 도 같은 형식)
    OpenAI 는 assistant.tool_calls[].type 과 function.arguments(문자열)를 요구한다(버그 ②: 미변환 시 HTTP 400)."""
    out = []
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            tcs = []
            for c in m["tool_calls"]:
                args = c.get("arguments", {})
                tcs.append({
                    "id": c.get("id", ""),
                    "type": "function",
                    "function": {"name": c["name"],
                                 "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)},
                })
            # content 는 tool_calls 와 함께 올 때 null 허용
            out.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": tcs})
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""),
                        "content": m.get("content", "")})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


def _call_openai(system, messages, tools, model):
    key = os.environ["OPENAI_API_KEY"]
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    msgs = ([{"role": "system", "content": system}] if system else []) + _to_openai_messages(messages)
    payload = {"model": model, "messages": msgs}
    if tools:
        payload["tools"] = [{"type": "function", "function": t} for t in tools]
    d = _post(f"{base}/chat/completions",
              {"Authorization": f"Bearer {key}"}, payload)
    msg = d["choices"][0]["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        f = c["function"]
        args = f.get("arguments") or "{}"
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": c.get("id", ""), "name": f["name"], "arguments": args})
    return {"text": msg.get("content") or "", "tool_calls": calls}


def _call_anthropic(system, messages, tools, model):
    key = os.environ["ANTHROPIC_API_KEY"]
    # OpenAI 형식 messages → Anthropic 형식. tool 결과는 user 의 tool_result 블록으로.
    conv = []
    for m in messages:
        role = m["role"]
        if role == "tool":
            conv.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": m.get("tool_call_id", ""),
                 "content": m.get("content", "")}]})
        elif role == "assistant" and m.get("tool_calls"):
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m["tool_calls"]:
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"],
                               "input": c["arguments"]})
            conv.append({"role": "assistant", "content": blocks})
        else:
            conv.append({"role": role, "content": m.get("content", "")})
    payload = {"model": model, "max_tokens": 4096, "messages": conv}
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = [{"name": t["name"], "description": t["description"],
                             "input_schema": t["parameters"]} for t in tools]
    d = _post("https://api.anthropic.com/v1/messages",
              {"x-api-key": key, "anthropic-version": "2023-06-01"}, payload)
    text, calls = "", []
    for block in d.get("content", []):
        if block["type"] == "text":
            text += block["text"]
        elif block["type"] == "tool_use":
            calls.append({"id": block["id"], "name": block["name"], "arguments": block.get("input", {})})
    return {"text": text, "tool_calls": calls}


def _call_gemini(system, messages, tools, model):
    key = os.environ["GEMINI_API_KEY"]
    contents = []
    for m in messages:
        role = m["role"]
        if role == "assistant":
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for c in m.get("tool_calls") or []:
                parts.append({"functionCall": {"name": c["name"], "args": c["arguments"]}})
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            contents.append({"role": "user", "parts": [
                {"functionResponse": {"name": m.get("name", "tool"),
                                      "response": {"content": m.get("content", "")}}}]})
        else:
            contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})
    payload = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        payload["tools"] = [{"functionDeclarations": [
            {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in tools]}]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    d = _post(url, {}, payload)
    cand = (d.get("candidates") or [{}])[0]
    text, calls = "", []
    for part in cand.get("content", {}).get("parts", []):
        if "text" in part:
            text += part["text"]
        elif "functionCall" in part:
            fc = part["functionCall"]
            calls.append({"id": fc["name"], "name": fc["name"], "arguments": fc.get("args", {})})
    return {"text": text, "tool_calls": calls}


_CALL = {"openai": _call_openai, "anthropic": _call_anthropic, "gemini": _call_gemini}


def _order(primary: str):
    """기본 공급자 → 나머지(키가 있는 것만). 429/5xx 때 1회씩 폴백."""
    seq = [primary] + [p for p in _CALL if p != primary]
    return [p for p in seq if os.environ.get(_KEY_ENV[p])]


def complete(role: str, system: str, messages: list, tools=None) -> dict:
    """단일 진입점. {text, tool_calls, model} 반환. 모든 공급자 실패 시 LLMError."""
    primary = (os.environ.get("LLM_PROVIDER") or "openai").lower()
    if primary not in _CALL:
        raise LLMError(f"알 수 없는 LLM_PROVIDER: {primary}")
    order = _order(primary)
    if not order:
        raise LLMError("키가 설정된 공급자가 없다 (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY)")

    norm = _norm_tools(tools)
    errors = []
    for provider in order:
        model = _model_for(provider, role)
        try:
            out = _CALL[provider](system, messages, norm, model)
            out["model"] = model
            return out
        except _Retryable as e:
            errors.append(f"{provider}({model}): {e}")
            continue
        except LLMError as e:
            errors.append(f"{provider}({model}): {e}")
            continue
    hint = ("\n힌트: 404/400 이면 모델 이름이 죽은 것이다. "
            "LLM_STRONG / LLM_FAST 환경변수로 현재 살아 있는 모델 id 를 못박아라 "
            "(예: LLM_PROVIDER=openai LLM_STRONG=gpt-5.5 LLM_FAST=gpt-5-mini).")
    raise LLMError("모든 공급자 실패 — " + " · ".join(errors) + hint)


if __name__ == "__main__":
    # 스모크 테스트: python3 -m pipeline.llm "질문"
    q = sys.argv[1] if len(sys.argv) > 1 else "한 문장으로 자기소개해줘."
    t0 = time.time()
    r = complete("fast", "짧게 한국어로 답한다.", [{"role": "user", "content": q}])
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print(f"({r['model']}, {time.time()-t0:.1f}s)", file=sys.stderr)
