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


def _snapshot(src: Path, dst: Path):
    """wiki 를 gitignore 없는 임시 경로로 복사. .history.jsonl 등 점 파일은 제외."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))


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
