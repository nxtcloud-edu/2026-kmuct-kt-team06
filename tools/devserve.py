#!/usr/bin/env python3
"""개발용 서버 (프론트가 API 없이 0분부터 쓰는 것). 실제 서버는 api/server.py 가 같은 규칙으로 만든다.

  python3 tools/devserve.py [port=8000]

- /            → public/ (Quartz 빌드 결과). HTML 응답에는 INJECT 를 </body> 앞에 끼운다  ← CONTRACT §7.1
- /web /mock /raw → 저장소의 같은 이름 디렉터리
"""
import http.server, mimetypes, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = ("web", "mock", "raw")
mimetypes.add_type("font/woff2", ".woff2")  # 3.10 의 mimetypes 는 woff2 를 모른다 → KaTeX 폰트가 깨진다
mimetypes.add_type("font/woff", ".woff")

INJECT = b"""
<link rel="stylesheet" href="/web/viewer/viewer.css">
<link rel="stylesheet" href="/web/notes/notes.css">
<link rel="stylesheet" href="/web/vendor/katex/katex.min.css">
<script defer src="/web/viewer/viewer.js"></script>
<script defer src="/web/notes/notes.js"></script>
<script defer src="/web/vendor/katex/katex.min.js"></script>
<script defer src="/web/notes/richtext.js"></script>
<script defer src="/web/notes/chat.js"></script>
"""


def inject(html: bytes) -> bytes:
    i = html.rfind(b"</body>")
    return html if i < 0 else html[:i] + INJECT + html[i:]


def resolve(url_path: str) -> Path | None:
    rel = url_path.split("?")[0].split("#")[0].strip("/")
    first = rel.split("/")[0]
    base = ROOT if first in PASS else ROOT / "public"
    jail = (ROOT / first) if first in PASS else (ROOT / "public")   # /web/../.env 처럼 허용 폴더를 딛고 나가는 것을 막는다
    for form in ("NFC", "NFD"):  # 맥에서 만든 한글 파일명(NFD)과 URL(NFC)이 리눅스에서 어긋난다
        p = (base / unicodedata.normalize(form, rel)).resolve()
        if p != jail and jail not in p.parents:
            return None
        if any(part.startswith(".") for part in p.relative_to(ROOT).parts):
            return None  # .env · .git · .ytcache 같은 점 파일은 절대 서빙하지 않는다
        for c in (p, p.parent / (p.name + ".html"), p / "index.html"):
            if c.is_file():
                return c
    return None


def send_bytes(h, code, ctype, body):
    """Range 지원 — 없으면 브라우저가 mp4·m4a 를 **탐색(seek)하지 못한다** = 앵커 점프가 안 된다."""
    total, start, end = len(body), 0, len(body) - 1
    m = re.match(r"bytes=(\d*)-(\d*)$", h.headers.get("Range", "") or "")
    if m and code == 200 and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1)); end = min(int(m.group(2)), end) if m.group(2) else end
        else:
            start = max(total - int(m.group(2)), 0)
        if start > end or start >= total:
            h.send_response(416); h.send_header("Content-Range", f"bytes */{total}"); h.end_headers(); return
        code = 206
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Accept-Ranges", "bytes")
    if code == 206:
        h.send_header("Content-Range", f"bytes {start}-{end}/{total}")
    h.send_header("Content-Length", str(end - start + 1))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    if h.command != "HEAD":
        try:
            h.wfile.write(body[start:end + 1])
        except (BrokenPipeError, ConnectionResetError):
            pass  # 영상 탐색 때 브라우저가 연결을 끊는 건 정상


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import unquote
        f = resolve(unquote(self.path))
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

    do_HEAD = do_GET


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://localhost:{port}  (public/ + 주입, /web /mock /raw)")
    http.server.ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
