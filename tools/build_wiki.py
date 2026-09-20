#!/usr/bin/env python3
"""Quartz 빌드 래퍼 (보드 #22/#28, A안).

문제: Quartz 의 glob 은 `gitignore: true` 가 하드코딩돼 있다(site/quartz/util/glob.ts:18, 수정 금지).
그래서 저장소 안의 wiki/ 를 -d 로 주면 .gitignore 가 실데이터 산출물(wiki/concepts/*·lectures/* —
견본 L3/bfs/dfs 만 예외)을 **빌드에서 제외**한다 → EC2 실데이터 배포 때 "위키가 안 뜬다".

해결: wiki/ 를 .gitignore 가 없는 임시 경로로 복사한 뒤 거기서 quartz build 한다.
.gitignore 와 계약 §5.3(devserve resolve/inject/send_bytes)은 건드리지 않는다.

  python3 tools/build_wiki.py                 # 1회 빌드 → public/
  python3 tools/build_wiki.py --watch [초]     # 원본 wiki 변경을 폴링해 재빌드(기본 3초). tmux 에 띄운다

Quartz 의 --watch 는 -d 디렉터리(임시 복사본)를 감시하므로 원본 변경을 못 본다.
그래서 여기서는 원본 wiki 의 mtime 을 폴링해 바뀌면 임시 복사 후 재빌드한다(계약 §5.3 "몇 초 뒤 화면에 나온다").
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
SITE = ROOT / "site"
PUBLIC = ROOT / "public"


def _is_grey(md_path: Path) -> bool:
    """프론트매터가 status: grey 인가(숨김 대상, #45). 프론트매터 블록 안만 본다."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    fm = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    return re.search(r"^status:\s*grey\s*$", fm, re.M) is not None


def _snapshot(src: Path, dst: Path):
    """wiki 를 gitignore 없는 임시 경로로 복사. .history.jsonl 등 점 파일은 제외.
    status: grey 인 concepts/·lectures/ 페이지는 복사하지 않는다(#45) = Quartz 빌드에서 빠짐 = 화면에서 숨김.
    원본 파일과 History 는 그대로 둔다(삭제가 아니라 숨김)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))
    # 복사본에서 grey 페이지만 제거(원본은 안 건드린다)
    hidden = 0
    for sub in ("concepts", "lectures"):
        d = dst / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            if _is_grey(p):
                p.unlink()
                hidden += 1
    if hidden:
        print(f"  (숨김: status:grey {hidden}개 페이지 빌드 제외)", file=sys.stderr)


def build_once():
    tmp = Path(tempfile.mkdtemp(prefix="wiki_build_"))
    tmp_wiki = tmp / "wiki"
    try:
        _snapshot(WIKI, tmp_wiki)
        r = subprocess.run(
            ["npx", "quartz", "build", "-d", str(tmp_wiki), "-o", str(PUBLIC)],
            cwd=SITE, capture_output=True, text=True)
        out = (r.stdout + r.stderr)
        line = next((l for l in out.splitlines() if "Emitted" in l or "input files" in l), out.strip()[:200])
        ok = r.returncode == 0
        print(("✅ " if ok else "❌ ") + line, file=sys.stderr)
        try:  # 프론트 뷰어가 읽는 노트 목록도 같은 시점에 다시 만든다(실패해도 빌드는 성공)
            subprocess.run([sys.executable, str(Path(__file__).with_name("build_library.py"))],
                           cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=30)
        except Exception:
            pass
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mtime(path: Path) -> float:
    """wiki 하위 .md 의 가장 최근 수정 시각(점 파일 제외)."""
    latest = 0.0
    for p in path.rglob("*.md"):
        if any(part.startswith(".") for part in p.relative_to(path).parts):
            continue
        latest = max(latest, p.stat().st_mtime)
    return latest


def watch(interval=3.0):
    print(f"watch: {WIKI} 변경을 {interval}s 마다 확인 → 재빌드 (Ctrl-C 로 종료)", file=sys.stderr)
    build_once()
    last = _mtime(WIKI)
    try:
        while True:
            time.sleep(interval)
            cur = _mtime(WIKI)
            if cur > last:
                last = cur
                build_once()
    except KeyboardInterrupt:
        print("\nwatch 종료", file=sys.stderr)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--watch"]
        watch(float(rest[0]) if rest else 3.0)
    else:
        sys.exit(0 if build_once() else 2)
