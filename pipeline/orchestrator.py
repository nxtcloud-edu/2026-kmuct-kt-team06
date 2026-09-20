#!/usr/bin/env python3
"""오케스트레이터 (F-08, R2·R6) — 단계 순서를 코드로 고정하고, ③컴파일의 툴콜 루프를 돈다.

단계: ①적재(FrameGuard) → ②build_episodic → ③컴파일(모델) → ④비평(critic.py) → ⑤링커(코드)
이 파일은 ③의 「에이전트 루프」를 소유한다:
  - LLM 이 tool_call 을 내면 AgentGuard(허용 툴 Set)로 거른 뒤 dispatch 로 실행
  - write_page 는 훅(write_page_guard.py)에 agent·attempt·run 을 실어 판정 → allow 일 때만 파일이 써진다
  - 훅이 거부하면 사유를 모델에 돌려주고 같은 페이지를 최대 3회 재작성 → 3회 실패면 그 주제 skip(멈추지 않는다)
  - on_progress(stage, percent, detail) 콜백(R6) — 단계 전환과 주제 하나가 끝날 때마다

모델 호출은 pipeline.llm.complete 하나만 쓴다. 키가 없으면 그 주제는 llm_error 로 표시하고
파이프라인은 계속 간다(default deny 대신 default skip). 훅·도구는 재구현하지 않는다 — 호출한다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import tools as T           # noqa: E402
from pipeline.llm import complete, LLMError  # noqa: E402

# AgentGuard: hooks/registry.md 「허용 툴 Set」과 동일해야 한다
AGENT_TOOLS = {
    "align":   {"append_episodic"},
    "compile": {"read_episodic", "get_slide_text", "read_page", "search_wiki",
                "write_page", "youtube_search", "resolve_reference"},
    "critic":  {"read_page", "get_source", "grep_wiki"},
    "qa":      {"grep_wiki", "read_page", "get_source"},
}
MAX_TURNS = {"compile": 20, "critic": 10, "qa": 8}
MAX_ATTEMPTS = 3  # write_page 재작성 한도


def _noop(stage, percent, detail):
    pass


def _system_prompt(role_file):
    common = (ROOT / "prompts" / "common.md").read_text(encoding="utf-8")
    role = (ROOT / "prompts" / role_file).read_text(encoding="utf-8")
    # 스킬 인덱스(name: path) 주입 자리를 실제 목록으로 채운다
    skills = ROOT / "skills"
    idx = "\n".join(f"- {d.name}: skills/{d.name}/SKILL.md"
                    for d in sorted(skills.iterdir())) if skills.is_dir() else ""
    common = common.replace("{skill_index}", idx).replace("{TAXONOMY.md}", "(없음)")
    return common + "\n\n---\n\n" + role


def lecture_note_path(lecture, title=""):
    """강의 1편 = 노트 1개. 경로는 코드가 정한다(에이전트가 주제마다 제목을 새로 지어 파일이 쪼개지던 문제, 2026-09-20).
    같은 강의의 기존 노트가 하나 있으면 그 파일을 계속 쓴다(제목이 바뀌어도 새 파일을 만들지 않는다)."""
    import re as _re
    d = T.ROOT / "wiki" / "lectures" if hasattr(T, "ROOT") else ROOT / "wiki" / "lectures"
    existing = sorted(d.glob(f"{lecture}_*.md")) if d.is_dir() else []
    if len(existing) == 1:
        return f"wiki/lectures/{existing[0].name}"
    name = _re.sub(r'[/\\:*?"<>|]', "", (title or "강의 노트").strip())
    name = _re.sub(r"\s+", "_", name) or "강의_노트"
    return f"wiki/lectures/{lecture}_{name}.md"


def run_compile_topic(lecture, s_from, s_to, run, on_progress=_noop, title="", course=""):
    """③ 한 주제(슬라이드 범위)를 컴파일한다. write_page 의 deny→allow 를 관리.
    반환: {"topic", "pages":[{path, attempts, verdict}], "status": "done|skipped|llm_error"}"""
    agent = "compile"
    allowed = AGENT_TOOLS[agent]
    topic = f"s{s_from}-{s_to}"
    system = _system_prompt("03-compile.md")

    episodic = T.read_episodic(lecture, s_from, s_to)
    if episodic.startswith("no episodic") or "구간 없음" in episodic:
        on_progress("compile", 0, f"{topic}: episodic 없음")
        return {"topic": topic, "pages": [], "status": "skipped"}

    note_path = lecture_note_path(lecture, title)
    note_title = f"{lecture}. {title}" if title else f"{lecture}. 강의 노트"
    user = (f"강의 {lecture} 의 슬라이드 {s_from}~{s_to} 를 컴파일한다. "
            f"episodic 은 read_episodic 으로 읽어라(lecture={lecture}, s_from={s_from}, s_to={s_to}). "
            f"**이 강의의 노트 파일은 정확히 `{note_path}` 하나다. 다른 이름의 강의 노트 파일을 만들지 마라.** "
            f"먼저 read_page 로 그 파일을 읽어라. 있으면: 기존 내용(프론트매터·기존 '## N.' 주제들)을 한 글자도 바꾸지 말고 "
            f"그대로 둔 채, 맨 끝에 다음 번호의 '## N.' 주제 하나를 **추가한 전체 파일**을 write_page 로 써라. "
            f"없으면: 프론트매터(title: \"{note_title}\" — 반드시 큰따옴표, type: lecture, sources: [{lecture}], status: draft)와 "
            f"'# {note_title}', '> 소스: …'·'> 읽는 법: …' 두 줄, 그리고 '## 1.' 주제로 새로 만든다. "
            f"필요하면 개념 페이지 wiki/concepts/<slug>.md 도 write_page 로 써라(이미 있으면 새로 만들지 말고 그 페이지에 추가). "
            f"앵커는 episodic 에 적힌 것만 옮긴다.")
    messages = [{"role": "user", "content": user}]
    specs = T.specs_for(sorted(allowed))

    # write_page 재작성 상태: path -> attempt 카운트
    attempts = {}
    pages = []
    blocked_paths = set()
    nudged = False  # 툴콜 없이 끝나려 할 때 write_page 를 한 번만 재촉

    for turn in range(MAX_TURNS[agent]):
        try:
            r = complete("strong", system, messages, specs)
        except LLMError as e:
            on_progress("compile", 0, f"{topic}: LLM 없음 — {str(e)[:60]}")
            return {"topic": topic, "pages": pages, "status": "llm_error", "error": str(e)}

        calls = r.get("tool_calls") or []
        if not calls:
            # 툴콜 없이 텍스트만 → 아직 이 주제에서 write_page 를 한 번도 안 했으면 한 번 재촉.
            # (claude 처럼 read 후 다음 턴에 write 하는 모델이 조기 종료되는 것을 막는다.)
            wrote_any = any(p["verdict"] == "allow" for p in pages)
            if not wrote_any and not nudged:
                nudged = True
                messages.append({"role": "assistant", "content": r.get("text", "")})
                messages.append({"role": "user", "content":
                    "아직 write_page 를 부르지 않았다. 지금까지 읽은 episodic 을 근거로 "
                    "강의 노트(wiki/lectures/) 와 개념 페이지(wiki/concepts/) 를 write_page 로 저장하라. "
                    "앵커는 episodic 에 있는 것만 쓴다. 저장할 게 없으면 NONE."})
                continue
            break

        # assistant 턴을 대화에 기록
        messages.append({"role": "assistant", "content": r.get("text", ""), "tool_calls": calls})

        for c in calls:
            name, args, cid = c["name"], c.get("arguments", {}), c.get("id", "")
            # AgentGuard: 허용 툴 밖이면 실행하지 않고 그 사실을 모델에 돌려준다
            if name not in allowed:
                messages.append({"role": "tool", "tool_call_id": cid, "name": name,
                                 "content": f"BLOCKED by AgentGuard: '{name}' is not allowed for {agent}."})
                continue

            if name == "write_page":
                path = args.get("path", "")
                if path in blocked_paths:
                    messages.append({"role": "tool", "tool_call_id": cid, "name": name,
                                     "content": f"{path} 는 3회 거부되어 건너뛴다. 다른 주제로."})
                    continue
                attempts[path] = attempts.get(path, 0) + 1
                verdict = T.write_page(path, args.get("content", ""), agent,
                                       attempt=attempts[path], run=run)
                if verdict.get("decision") == "allow":
                    pages.append({"path": path, "attempts": attempts[path], "verdict": "allow"})
                    messages.append({"role": "tool", "tool_call_id": cid, "name": name,
                                     "content": f"allow: {path} 저장됨 (attempt {attempts[path]})."})
                else:
                    reason = verdict.get("reason", "REJECTED")
                    if attempts[path] >= MAX_ATTEMPTS:
                        blocked_paths.add(path)
                        pages.append({"path": path, "attempts": attempts[path], "verdict": "blocked"})
                        messages.append({"role": "tool", "tool_call_id": cid, "name": name,
                                         "content": f"{reason}\n3회 거부됨 → 이 주제는 건너뛴다."})
                    else:
                        # 거부 사유를 그대로 모델에 돌려준다 → 사유에 적힌 곳만 고쳐 다시 write_page
                        messages.append({"role": "tool", "tool_call_id": cid, "name": name,
                                         "content": f"{reason}\n사유에 적힌 곳만 고쳐 같은 path 로 다시 write_page (attempt {attempts[path]+1}/{MAX_ATTEMPTS})."})
            else:
                out = T.dispatch(name, args, {"lecture": lecture})
                messages.append({"role": "tool", "tool_call_id": cid, "name": name, "content": str(out)[:6000]})

        # 이 주제에서 allow 가 하나라도 나왔고 더 쓸 게 없으면 종료 조건은 모델의 다음 턴이 판단
        if pages and all(p["path"] in blocked_paths or p["verdict"] == "allow" for p in pages):
            # 모델이 계속 쓰려 하면 루프가 이어진다. allow 가 있으면 진행률만 갱신
            on_progress("compile", 100, f"{topic}: {sum(1 for p in pages if p['verdict']=='allow')}개 페이지")

    status = "done" if any(p["verdict"] == "allow" for p in pages) else ("skipped" if blocked_paths else "done")
    on_progress("compile", 100, f"{topic}: {status}")
    return {"topic": topic, "pages": pages, "status": status}


def parse_topic(spec):
    """'s5-6' | 's5' | '5-6' → (5, 6)."""
    nums = [int(x) for x in re.findall(r"\d+", spec or "")]
    if not nums:
        return None
    return (nums[0], nums[-1])


def topics_from_episodic(lecture):
    """episodic 의 `## s{S} @t=` 헤더에서 슬라이드 번호를 뽑아 연속 범위로 묶는다."""
    p = ROOT / f"wiki/episodic/{lecture}.md"
    if not p.is_file():
        return []
    slides = [int(m.group(1)) for m in re.finditer(r"## s(\d+) @t=", p.read_text(encoding="utf-8"))]
    # 인접한 슬라이드를 2개씩 주제로 (견본 노트가 s2~3, s5~6 식으로 묶는 방식)
    topics, i = [], 0
    while i < len(slides):
        s_from = slides[i]
        s_to = slides[i + 1] if i + 1 < len(slides) else slides[i]
        topics.append((s_from, s_to))
        i += 2
    return topics
