#!/usr/bin/env python3
"""개발용 서버 (프론트가 API 없이 0분부터 쓰는 것). 실제 서버는 api/server.py 가 같은 규칙으로 만든다.

  python3 tools/devserve.py [port=8000]

- /            → public/ (Quartz 빌드 결과). HTML 응답에는 INJECT 를 </body> 앞에 끼운다  ← CONTRACT §7.1
- /web /mock /raw → 저장소의 같은 이름 디렉터리
"""
import http.server, mimetypes, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = ("web", "mock", "raw")
INJECT = b"""
<link rel="stylesheet" href="/web/viewer/viewer.css">
<link rel="stylesheet" href="/web/notes/notes.css">
<script defer src="/web/viewer/viewer.js"></script>
<script defer src="/web/notes/notes.js"></script>
<script defer src="/web/notes/chat.js"></script>
"""


def inject(html: bytes) -> bytes:
    i = html.rfind(b"</body>")
    return html if i < 0 else html[:i] + INJECT + html[i:]


def resolve(url_path: str) -> Path | None:
    rel = url_path.split("?")[0].split("#")[0].strip("/")
    base = ROOT if rel.split("/")[0] in PASS else ROOT / "public"
    p = (base / rel).resolve()
    if not str(p).startswith(str(ROOT)):
        return None
    for c in (p, p.with_suffix(".html"), p / "index.html"):
        if c.is_file():
            return c
    return None


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
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://localhost:{port}  (public/ + 주입, /web /mock /raw)")
    http.server.ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
