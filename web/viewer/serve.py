"""Run the standalone frontend: python web/viewer/serve.py [8000]."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.devserve import H, inject, send_bytes
from http.server import ThreadingHTTPServer


def build_library():
    pages = []
    for folder in ("lectures", "concepts"):
        for path in sorted((ROOT / "wiki" / folder).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            def field(name, default):
                match = re.search(rf"^{name}:\s*(.+)$", text, re.M)
                return match.group(1).strip() if match else default
            pages.append({"title": field("title", path.stem),
                          "status": field("status", "draft"),
                          "type": field("type", "concept"),
                          "slug": f"{folder}/{path.stem}", "body": text})
    (ROOT / "web/viewer/library.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")


class FrontendHandler(H):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = (ROOT / "web/viewer/index.html").read_bytes()
            send_bytes(self, 200, "text/html; charset=utf-8", inject(body))
        else:
            super().do_GET()

    do_HEAD = do_GET


if __name__ == "__main__":
    build_library()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"MOTGA frontend: http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), FrontendHandler).serve_forever()
