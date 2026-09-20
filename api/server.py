#!/usr/bin/env python3
"""단일 오리진 서버 — public/(주입) · /web /mock /raw · /api/* 를 한 프로세스에서 서빙.

  저장소 루트에서:  python3 -m api.server [port=8000]

정적 서빙은 tools/devserve.py 의 resolve()·send_bytes()·inject() 를 그대로 쓴다(CONTRACT §5.3, §5.4).
직접 open() 하지 않는다 — /web/../.env 로 키 파일이 내려가는 구멍을 막기 위함.
라우팅은 (METHOD, 정규식) -> 함수 표. 오류는 전부 {"error":{"code","message"}}.
"""
import json
import mimetypes
import os
import re
import sys
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# 저장소 루트를 import 경로에 넣어 실행 위치와 무관하게 한다.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.devserve import inject, resolve, send_bytes  # noqa: E402  정적 서빙 재사용
from tools import quote_search  # noqa: E402
from api import store  # noqa: E402
from api import notes as notes_mod  # noqa: E402
from api import stats as stats_mod  # noqa: E402
from api import review as review_mod  # noqa: E402
from api import qa as qa_mod  # noqa: E402
from api import youtube as yt_mod  # noqa: E402
from api import dashboard as dashboard_mod  # noqa: E402
from api import ingest as ingest_mod  # noqa: E402

DEMO_TOKEN = os.environ.get("DEMO_TOKEN")  # 있으면 쓰기·과금 경로에 X-Demo-Token 요구(§5.4)


class ApiError(Exception):
    """HTTP 상태 + 코드로 실패를 표현. 핸들러가 잡아 봉투로 내려보낸다."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


# ── /api 라우트 표 ──────────────────────────────────────────────
# 각 핸들러: (params, query, body) -> (status, obj)
ROUTES: list[tuple[str, re.Pattern, "callable"]] = []


def route(method: str, pattern: str):
    rx = re.compile(f"^{pattern}$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn

    return deco


@route("GET", r"/api/quotes")
def api_quotes(params, query, body):
    """교수 실제 발언 검색 — tools.quote_search.search 그대로. LLM 없음(CONTRACT §5)."""
    q = (query.get("q", [""])[0] or "")[:500]  # 500자 컷(CONTRACT §5.4)
    return 200, quote_search.search(q, raw=str(store.RAW))


@route("GET", r"/api/segments/(?P<lecture>[^/]+)")
def api_segments(params, query, body):
    """{lecture, video, segments}. mock/segments/L3.json 과 같은 모양."""
    lecture = params["lecture"]
    if not store.valid_lecture(lecture):
        raise ApiError(400, "BAD_LECTURE", "lecture must match ^L\\d+$")
    segs = store.load_segments(lecture)
    if segs is None:
        raise ApiError(404, "SEGMENTS_NOT_FOUND", f"no segments for {lecture}")
    return 200, {
        "lecture": lecture,
        "video": store.video_for(lecture, store.segments_video(lecture)),
        "segments": segs,
    }


@route("GET", r"/api/source")
def api_source(params, query, body):
    """앵커 -> 구간. 없으면 404 SOURCE_NOT_FOUND(500 아님, CONTRACT §5.4)."""
    raw_anchor = query.get("anchor", [""])[0]
    parsed = store.parse_anchor(unquote(raw_anchor))
    if not parsed:
        raise ApiError(404, "SOURCE_NOT_FOUND", "anchor missing or malformed")
    lecture, s, t = parsed
    if not store.valid_lecture(lecture):
        raise ApiError(400, "BAD_LECTURE", "lecture must match ^L\\d+$")
    seg = store.find_segment(lecture, s, t)
    if seg is None:
        raise ApiError(404, "SOURCE_NOT_FOUND", f"no segment for {lecture}#s{s}@t={t}")
    return 200, {
        "lecture": lecture,
        "k": seg.get("k"),
        "s": seg.get("s"),
        "t_start": seg.get("t_start"),
        "t_end": seg.get("t_end"),
        "frame": store.frame_url(lecture, seg),
        "slide": store.slide_url(lecture, seg),
        "video": store.video_for(lecture, store.segments_video(lecture)),
        "ocr": seg.get("ocr"),
        "exists": True,
        "quote": store.quote_at(lecture, float(t)),  # R9 — transcript 없으면 null
        "date": store.lecture_date(lecture),
    }


@route("GET", r"/api/notes/(?P<lecture>[^/]+)")
def api_notes_get(params, query, body):
    """[{k,s,text,anchor,frame,updated}] — wiki/notes/L{n}/s{k}.md 에서."""
    lecture = params["lecture"]
    if not store.valid_lecture(lecture):
        raise ApiError(400, "BAD_LECTURE", "lecture must match ^L\\d+$")
    return 200, notes_mod.list_notes(lecture)


@route("POST", r"/api/notes")
def api_notes_post(params, query, body):
    """필기 저장(F-05). 앵커·프레임은 서버가 채우고, 훅 통과 시에만 쓴다.
    요청의 anchor 필드는 무시한다(R3)."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON body required")
    ok, result = notes_mod.save_note(body.get("lecture", ""), body.get("k"), body.get("text", ""))
    if ok:
        return 200, result
    status, code, message = result
    raise ApiError(status, code, message)


@route("POST", r"/api/qa")
def api_qa(params, query, body):
    """위키에 묻기(F-10). 근거 없으면 모델 안 부르고 NO_GROUNDING(200)."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON body required")
    question = body.get("question", "")
    model = body.get("model", "fast")
    context = body.get("context") if isinstance(body.get("context"), dict) else None
    return 200, qa_mod.answer(question, model, context)


@route("GET", r"/api/youtube/search")
def api_youtube(params, query, body):
    """[§5.1] — 교수 채널 먼저. 키 없거나 실패면 []."""
    q = (query.get("q", [""])[0] or "")[:200]
    return 200, yt_mod.search(q)


@route("POST", r"/api/ingest")
def api_ingest(params, query, body):
    """multipart files[] + title + course → {job, lecture}. body 는 파싱된 {files, fields}."""
    if not isinstance(body, dict) or "files" not in body:
        raise ApiError(400, "BAD_REQUEST", "multipart/form-data with files[] required")
    files = body.get("files", [])
    fields = body.get("fields", {})
    ok, result = ingest_mod.create_job(files, fields.get("title", ""), fields.get("course", ""))
    if ok:
        return 200, result
    status, code, message = result
    raise ApiError(status, code, message)


@route("GET", r"/api/dashboard")
def api_dashboard(params, query, body):
    """{overall,stt,summary,measured,confusing,hooks} — DESIGN §6. 측정 전은 null."""
    course = query.get("course", [None])[0] or None
    return 200, dashboard_mod.dashboard(course)


@route("POST", r"/api/transcript/fix")
def api_transcript_fix(params, query, body):
    """{lecture,t_start,text} → 훅(fix_transcript,user) 통과 시 corrections 덧붙이고 agree=1.0."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON body required")
    ok, result = dashboard_mod.fix_transcript(body.get("lecture", ""), body.get("t_start"), body.get("text", ""))
    if ok:
        return 200, result
    status, code, message = result
    raise ApiError(status, code, message)


@route("GET", r"/api/ingest/(?P<job>[^/]+)")
def api_ingest_status(params, query, body):
    """{lecture,stage,percent,detail,error} — 파이프라인 실제 단계."""
    st = ingest_mod.job_status(params["job"])
    if st is None:
        raise ApiError(404, "JOB_NOT_FOUND", f"no job {params['job']}")
    return 200, st


@route("GET", r"/api/stats")
def api_stats(params, query, body):
    """{lectures,pages,approved,draft,grey,links,notes,coverage,hooks}. hooks=hook_metrics.metrics()."""
    return 200, stats_mod.stats()


@route("GET", r"/api/history")
def api_history(params, query, body):
    """[{ts,agent,tool,path,verdict,reason}] 최신순."""
    try:
        limit = int(query.get("limit", ["10"])[0])
    except (ValueError, TypeError):
        limit = 10
    return 200, stats_mod.history(limit)


@route("GET", r"/api/models")
def api_models(params, query, body):
    return 200, stats_mod.models()


@route("GET", r"/api/review")
def api_review(params, query, body):
    """사람이 확인할 목록(F-11). 전부 기존 데이터에서 계산."""
    return 200, review_mod.review_list()


@route("POST", r"/api/review/approve")
def api_review_approve(params, query, body):
    """{id} → status: approved (agent:user 로 훅 통과)."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON body required")
    ok, result = review_mod.approve(body.get("id", ""))
    if ok:
        return 200, result
    status, code, message = result
    raise ApiError(status, code, message)


@route("POST", r"/api/review/hide")
def api_review_hide(params, query, body):
    """{id:'page:<slug>'} → status: grey (삭제 대신 숨기기, #44). 복원은 approve."""
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "JSON body required")
    ok, result = review_mod.hide(body.get("id", ""))
    if ok:
        return 200, result
    status, code, message = result
    raise ApiError(status, code, message)


# ── HTTP 핸들러 ────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "karonton/0.1"

    def _send_json(self, status: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _send_error_obj(self, status: int, code: str, message: str):
        # 500 에 스택트레이스를 싣지 않는다(R1).
        self._send_json(status, {"error": {"code": code, "message": message}})

    # 쓰기·과금 경로 — DEMO_TOKEN 이 설정돼 있으면 X-Demo-Token 일치 필요(§5.4)
    _PROTECTED = {("POST", "/api/notes"), ("POST", "/api/qa"), ("POST", "/api/review/approve"),
                  ("POST", "/api/review/hide"),
                  ("POST", "/api/transcript/fix"), ("POST", "/api/ingest")}

    def _check_token(self, method: str, path: str) -> bool:
        if not DEMO_TOKEN:
            return True
        if (method, path) not in self._PROTECTED:
            return True
        given = self.headers.get("X-Demo-Token") or self._cookie_token()
        return given == DEMO_TOKEN

    def _cookie_token(self):
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "X-Demo-Token":
                return v
        return None

    def _dispatch_api(self, method: str, path: str, query: dict, body) -> bool:
        # 토큰 검사(쓰기·과금 경로)
        if not self._check_token(method, path):
            self._send_error_obj(401, "UNAUTHORIZED", "X-Demo-Token required")
            return True
        # /api/qa 는 IP당 분당 10회
        if (method, path) == ("POST", "/api/qa"):
            ip = self.client_address[0] if self.client_address else "?"
            if not qa_mod.rate_ok(ip):
                self._send_error_obj(429, "RATE_LIMITED", "10 requests per minute")
                return True
        for m, rx, fn in ROUTES:
            if m != method:
                continue
            match = rx.match(path)
            if not match:
                continue
            try:
                status, obj = fn(match.groupdict(), query, body)
                self._send_json(status, obj)
            except ApiError as e:
                self._send_error_obj(e.status, e.code, e.message)
            except Exception:  # 예상 못 한 오류 — 스택은 서버 로그로만
                traceback.print_exc()
                self._send_error_obj(500, "INTERNAL", "internal error")
            return True
        # 경로는 /api 인데 매칭이 없으면 405/404 구분
        if any(rx.match(path) for _, rx, _ in ROUTES):
            self._send_error_obj(405, "METHOD_NOT_ALLOWED", f"{method} not allowed")
        else:
            self._send_error_obj(404, "NOT_FOUND", f"no route for {path}")
        return True

    def _serve_static(self):
        """devserve 규칙으로 정적 파일 서빙(주입·경로 탈출 차단·Range)."""
        parsed = urlparse(self.path)
        f = resolve(unquote(parsed.path))
        if not f:
            # 재빌드 경합: public/ 파일이 잠깐 없을 수 있다 → 0.5초 뒤 1회 재시도(R1/§5.4)
            time.sleep(0.5)
            f = resolve(unquote(parsed.path))
        if not f:
            f, code = ROOT / "public/404.html", 404
        else:
            code = 200
        body = f.read_bytes() if f.is_file() else b"not found"
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype == "text/html":
            body = inject(body)
            ctype += "; charset=utf-8"
        send_bytes(self, code, ctype, body)

    def _read_body(self):
        """POST 본문 파싱. multipart/form-data 면 {files, fields}, 아니면 JSON."""
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None
        if length <= 0 or length > 600 * 1024 * 1024:  # ingest 500MB + 여유
            return None
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "") or ""
        if ctype.startswith("multipart/form-data"):
            return self._parse_multipart(raw, ctype)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _parse_multipart(self, raw: bytes, ctype: str):
        """multipart → {"files":[(filename,bytes)], "fields":{name:value}}. email 파서 사용(표준 라이브러리)."""
        import email
        header = f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode()
        msg = email.message_from_bytes(header + raw)
        if not msg.is_multipart():
            return {"files": [], "fields": {}}
        files, fields = [], {}
        for part in msg.get_payload():
            disp = part.get("Content-Disposition", "") or ""
            name = part.get_param("name", header="Content-Disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files.append((filename, payload))
            elif name:
                try:
                    fields[name] = payload.decode("utf-8", errors="replace")
                except Exception:
                    fields[name] = ""
        return {"files": files, "fields": fields}

    def _handle(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/") or path == "/api":
            query = parse_qs(parsed.query)
            body = self._read_body() if method == "POST" else None
            self._dispatch_api(method, path, query, body)
        else:
            self._serve_static()

    def do_GET(self):
        self._handle("GET")

    do_HEAD = do_GET

    def do_POST(self):
        # POST 라우트는 T2 이후. 지금은 /api 봉투로만 응답.
        self._handle("POST")

    def log_message(self, fmt, *args):  # 조용한 로그(요청 1줄)
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    args = sys.argv[1:]
    # 발표용 질문 캐시 데우기: python3 -m api.server --warm
    if "--warm" in args:
        args.remove("--warm")
        warmed = yt_mod.warm([
            "그래프 탐색 BFS",
            "DFS 깊이 우선 탐색",
            "그래프 인접 리스트 인접 행렬",
        ])
        print(f"warmed {warmed} youtube queries (cache: raw/.ytcache/)")
    port = int(args[0]) if args else 8000
    print(f"http://localhost:{port}  (api/server: public/ 주입 + /web /mock /raw + /api/*)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
