#!/usr/bin/env python3
"""wiki/ → web/viewer/suggestions.local.json  (페이지마다 '이런 걸 물어보세요' 3개, 캐시)

  python3 tools/build_suggestions.py --no-llm          # 모델 0회(안전 기본값·테스트)
  python3 tools/build_suggestions.py                   # 바뀐 페이지만 fast 모델 1회씩
  python3 tools/build_suggestions.py --root /tmp/x --limit 3

모양: {"<slug>": {"hash": "<본문 sha1>", "questions": ["…","…","…"], "source": "llm"|"fallback"}}
- 대상: wiki/lectures · wiki/concepts 의 status != grey 페이지 전부.
- 본문 해시가 캐시와 같으면 모델을 부르지 않는다(재사용). 위키에서 사라진 페이지는 캐시에서 뺀다.
- 질문은 **그 페이지 본문만으로 답할 수 있어야** 한다 → 본문과 2글자 이상 토큰을 공유하는지 싸게 검사.
- 모델 실패(키 없음·4xx/5xx·쓰레기 응답)는 예외로 새지 않는다. 전부 결정적 폴백으로 내려간다.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:      # 스크립트로 직접 실행해도 pipeline.llm 을 찾게
    sys.path.insert(0, str(ROOT))
OUT_REL = "web/viewer/suggestions.local.json"

FM = re.compile(r"^---\n(.*?)\n---\n", re.S)
ANCHOR = re.compile(r"\[\[L\d+#s\d+@t=\d+(?:-\d+)?\]\]")
WIKILINK = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]|\[\[([^\]]+)\]\]")
TOKEN = re.compile(r"[0-9A-Za-z가-힣]{2,}")
HEADING = re.compile(r"^## \d+\.\s*(.+)$", re.M)

MAX_Q = 3
MAX_LEN = 40          # 질문 한 개 길이 한도(글자)
BODY_LIMIT = 6000     # 모델에 주는 본문 길이

SYSTEM = (
    "너는 강의 위키의 학습 도우미다. 주어진 한 페이지의 본문만 보고, 학생이 그 페이지를 열었을 때 "
    "바로 눌러 볼 만한 짧은 한국어 질문 3개를 만든다. 규칙: "
    "(1) 반드시 그 본문 안의 내용만으로 답할 수 있는 질문일 것, "
    "(2) 각 질문 40자 이하, "
    "(3) 본문에 나온 용어를 그대로 쓸 것, "
    "(4) 출력은 JSON 문자열 배열 하나뿐. 설명·머리말·코드펜스 금지."
)


def _field(fm: str, key: str, default: str = "") -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else default


def iter_pages(root: Path):
    """(slug, title, kind, body) — grey 는 뺀다. body 는 프론트매터를 뺀 본문."""
    for kind, folder in (("lecture", "lectures"), ("concept", "concepts")):
        d = root / "wiki" / folder
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            m = FM.match(text)
            fm = m.group(1) if m else ""
            if _field(fm, "status", "draft") == "grey":
                continue
            body = text[m.end():] if m else text
            yield f"{folder}/{p.stem}", _field(fm, "title", p.stem), kind, body


def body_hash(body: str) -> str:
    return hashlib.sha1(body.encode("utf-8")).hexdigest()


def clean_body(body: str) -> str:
    """앵커를 떼고 [[a|b]] 는 b 만 남긴다 — 모델이 앵커를 질문에 베끼지 않게."""
    t = ANCHOR.sub("", body)
    t = WIKILINK.sub(lambda m: m.group(2) or m.group(3) or "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _josa(word: str, with_jong: str, without_jong: str) -> str:
    """받침 유무로 조사 고르기. 한글이 아니면(영문·기호) 받침 없는 쪽으로 — 'RISC가 뭐야?'."""
    ch = word.strip()[-1:] if word.strip() else ""
    if ch and "가" <= ch <= "힣":
        return with_jong if (ord(ch) - 0xAC00) % 28 else without_jong
    return without_jong


def _short_title(title: str) -> str:
    """'RISC (Reduced Instruction Set Computer)' → 'RISC'. 꼬리 괄호를 떼 질문을 짧게."""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", (title or "").strip()).strip()
    return s or (title or "").strip()


def fallback_questions(title: str, kind: str, body: str) -> list:
    """모델 없이 만드는 질문. 강의는 '## N.' 주제 제목에서, 개념은 프론트매터 제목에서."""
    out = []
    if kind == "lecture":
        for topic in HEADING.findall(body):
            t = re.sub(r"\s+", " ", ANCHOR.sub("", topic)).strip(" ·-—")
            if not t:
                continue
            q = f"{t}{_josa(t, '이', '가')} 뭐야?"
            if len(q) <= MAX_LEN and q not in out:
                out.append(q)
            if len(out) >= MAX_Q:
                break
    if not out:
        base = _short_title(title)
        for b in (base, base[:22].rstrip(" ·-—(")):  # 그래도 길면 잘라서라도 하나는 낸다
            if not b:
                continue
            qs = [f"{b}{_josa(b, '이', '가')} 뭐야?", f"{b}{_josa(b, '은', '는')} 왜 필요해?",
                  f"{b} 예시를 알려줘"]
            qs = [q for q in qs if len(q) <= MAX_LEN]
            if qs:
                out = qs[:MAX_Q]
                break
    return out[:MAX_Q]


def _tokens(text: str) -> set:
    return {t.lower() for t in TOKEN.findall(text)}


def _answerable(question: str, low_body: str) -> bool:
    """질문의 말이 본문에 하나라도 나오나. 조사가 붙은 '머지소트의' 는 앞 글자부터 줄여 가며 본다."""
    for tok in _tokens(question):
        for n in range(len(tok), 1, -1):
            if tok[:n] in low_body:
                return True
    return False


def parse_questions(text: str, body: str) -> list:
    """모델 응답에서 첫 [ … ] 를 꺼내 방어적으로 고른다. 답할 수 없어 보이는 질문은 버린다."""
    if not text:
        return []
    i, j = text.find("["), text.rfind("]")
    raw = []
    if 0 <= i < j:
        chunk = text[i:j + 1]
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, list):
                raw = parsed
        except (json.JSONDecodeError, ValueError):
            raw = re.findall(r'"((?:[^"\\]|\\.)*)"', chunk)
    out, seen = [], set()
    low_body = body.lower()
    for item in raw:
        if not isinstance(item, str):
            continue
        q = re.sub(r"\s+", " ", item).strip().strip("-•· ").strip()
        if not q or len(q) > MAX_LEN or q in seen:
            continue
        if "[[" in q or "<" in q or ">" in q:
            continue
        if not _answerable(q, low_body):   # 본문과 겹치는 말이 하나도 없으면 답할 수 없다
            continue
        seen.add(q)
        out.append(q)
        if len(out) >= MAX_Q:
            break
    return out


def llm_questions(title: str, body: str) -> list:
    """fast 모델 1회. 실패·쓰레기는 [] 로 돌려보낸다(예외를 밖으로 내지 않는다)."""
    from pipeline.llm import complete  # --no-llm 경로에서는 import 조차 하지 않는다
    prompt = (f"페이지 제목: {title}\n\n본문:\n{clean_body(body)[:BODY_LIMIT]}\n\n"
              "위 본문만으로 답할 수 있는 짧은 한국어 질문 3개를 JSON 배열로만 출력해라.")
    try:
        r = complete("fast", SYSTEM, [{"role": "user", "content": prompt}])
    except Exception:
        return []
    text = r.get("text", "") if isinstance(r, dict) else str(r)
    return parse_questions(text, body)


def load_cache(out_path: Path) -> dict:
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def write_atomic(out_path: Path, data: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(out_path.parent), prefix=".suggestions-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, out_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build(root: Path = ROOT, use_llm: bool = False, limit: int | None = None) -> dict:
    """캐시를 갱신하고 {"data":…, "generated":N, "reused":M, "fallback":K} 를 준다."""
    root = Path(root)
    out_path = root / OUT_REL
    cache = load_cache(out_path)
    data, generated, reused, fallback = {}, 0, 0, 0
    budget = limit if limit is not None else -1

    for slug, title, kind, body in iter_pages(root):
        h = body_hash(body)
        old = cache.get(slug)
        # 모델을 쓸 수 있는 실행에서는 예전에 폴백으로 채운 항목을 모델 질문으로 갈아끼운다(본문이 같아도).
        upgrade = use_llm and isinstance(old, dict) and old.get("source") == "fallback"
        if isinstance(old, dict) and old.get("hash") == h and old.get("questions") and not upgrade:
            data[slug] = {"hash": h, "questions": list(old["questions"])[:MAX_Q],
                          "source": old.get("source", "fallback")}
            reused += 1
            continue
        if budget == 0:  # --limit 를 넘긴 페이지는 이번 판에서 건드리지 않는다
            if isinstance(old, dict) and old.get("questions"):
                data[slug] = old
            continue
        if budget > 0:
            budget -= 1
        qs = llm_questions(title, body) if use_llm else []
        source = "llm"
        if not qs:
            qs = fallback_questions(title, kind, body)
            source = "fallback"
            fallback += 1
        generated += 1
        data[slug] = {"hash": h, "questions": qs, "source": source}

    write_atomic(out_path, data)
    return {"data": data, "generated": generated, "reused": reused, "fallback": fallback,
            "path": out_path}


def main():
    ap = argparse.ArgumentParser(description="페이지별 예상 질문 캐시 생성")
    ap.add_argument("--root", default=str(ROOT), help="저장소 루트(기본: 이 파일 기준)")
    ap.add_argument("--no-llm", action="store_true", help="모델을 부르지 않고 결정적 폴백만")
    ap.add_argument("--limit", type=int, default=None, help="이번 실행에서 새로 만들 페이지 수 한도")
    args = ap.parse_args()
    r = build(Path(args.root), use_llm=not args.no_llm, limit=args.limit)
    print(f"생성 {r['generated']} · 재사용 {r['reused']} · 폴백 {r['fallback']}")


if __name__ == "__main__":
    main()
