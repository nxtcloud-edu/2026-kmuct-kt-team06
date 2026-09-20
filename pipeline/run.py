#!/usr/bin/env python3
"""파이프라인 실행 진입점 (R6, F-08).

  python3 -m pipeline.run L1 --title "RISC-V ISA" --course "컴퓨터구조"   # ①~⑤ 끝까지
  python3 -m pipeline.run L1 --topic s5-6                                # 주제 하나만(③)
  python3 -m pipeline.run L1 --topic s5-6 --live                         # 발표 중 라이브 30초

단계 순서를 코드로 고정한다:
  ① 적재    : FrameGuard(raw/L{n}/segments.json) — 통과 못 하면 멈춘다
  ② 정렬    : tools/build_episodic.py — wiki/episodic/L{n}.md
  ③ 컴파일  : orchestrator.run_compile_topic — 주제마다, deny→allow 훅 루프
  ④ 비평    : pipeline/critic.py (있으면)
  ⑤ 링커    : (코드, P2) — 지금은 생략

on_progress 는 stdout 에 [stage percent%] detail 로 찍는다. 서버의 /api/ingest 가 이걸 읽는다.
"""
import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import orchestrator as O  # noqa: E402


def progress(stage, percent, detail):
    print(f"[{stage:8} {percent:3}%] {detail}", file=sys.stderr)


def stage_frameguard(lecture):
    r = subprocess.run([sys.executable, str(ROOT / "hooks/frame_guard.py"), f"raw/{lecture}"],
                       capture_output=True, text=True)
    out = json.loads(r.stdout) if r.stdout.strip() else {"decision": "block", "reason": r.stderr}
    return out


def stage_episodic(lecture):
    r = subprocess.run([sys.executable, str(ROOT / "tools/build_episodic.py"), lecture],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "").strip()


def stage_critic(lecture):
    critic = ROOT / "pipeline" / "critic.py"
    if not critic.is_file():
        return None
    r = subprocess.run([sys.executable, str(critic), lecture], capture_output=True, text=True)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lecture")
    ap.add_argument("--title", default="")
    ap.add_argument("--course", default="")
    ap.add_argument("--topic", default=None, help="s5-6 처럼 주제 하나만 ③ 실행")
    ap.add_argument("--live", action="store_true", help="발표용: 주제 하나만 빠르게")
    args = ap.parse_args()
    lecture, run = args.lecture, uuid.uuid4().hex[:8]

    # ③ 주제 하나만
    if args.topic or args.live:
        rng = O.parse_topic(args.topic) if args.topic else (O.topics_from_episodic(lecture) or [(0, 0)])[0]
        if not rng:
            sys.exit("--topic s5-6 형식으로")
        progress("compile", 0, f"라이브 주제 {rng[0]}-{rng[1]} 시작 (run {run})")
        res = O.run_compile_topic(lecture, rng[0], rng[1], run, progress)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    # 전체 ①~⑤
    progress("upload", 5, f"{lecture} '{args.title}' 시작 (run {run})")

    fg = stage_frameguard(lecture)
    progress("align", 10, f"FrameGuard: {fg['decision']}")
    if fg["decision"] != "allow":
        progress("error", 10, fg.get("reason", "FrameGuard block"))
        sys.exit(2)

    ok, msg = stage_episodic(lecture)
    progress("episodic", 30, msg or "episodic 생성")
    if not ok:
        progress("error", 30, "build_episodic 실패")
        sys.exit(2)

    topics = O.topics_from_episodic(lecture)
    results = []
    for i, (s_from, s_to) in enumerate(topics):
        pct = 30 + int(60 * (i + 1) / max(len(topics), 1))
        progress("compile", pct, f"주제 s{s_from}-{s_to} ({i+1}/{len(topics)})")
        res = O.run_compile_topic(lecture, s_from, s_to, run, progress)
        results.append(res)

    crit = stage_critic(lecture)
    progress("compile", 92, "비평 " + ("완료" if crit else "생략(critic.py 없음)"))

    # ⑤ CoverageCheck (격리형) — signals 항목 grep → coverage.md
    try:
        from tools.coverage import coverage
        cov = coverage(write=True)
        progress("compile", 96, f"커버리지 {cov['covered']}/{cov['total']}")
    except Exception as e:
        progress("compile", 96, f"커버리지 계산 생략: {e}")

    allowed = sum(1 for r in results for p in r["pages"] if p["verdict"] == "allow")
    progress("done", 100, f"주제 {len(topics)}개 · allow 페이지 {allowed}개 · run {run}")
    print(json.dumps({"lecture": lecture, "run": run, "topics": results, "allowed_pages": allowed},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
