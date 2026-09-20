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


def run(lecture, title="", course="", src_dir=None, progress=None, on_progress=None, hold_last=False):
    """전체 파이프라인 ①~⑤를 함수로 실행한다(서버 없이도). api/ingest.py 가 이걸 부른다.

    progress(stage, percent, detail="") — 계약 §5 /api/ingest 의 stage 이름
    (upload·stt·align·episodic·compile·build·done·error)에 맞춰 부른다.
    src_dir 은 업로드 파일이 이미 배치된 raw/L{n}/ (여기서는 존재만 전제, 재배치 안 함).
    hold_last=True 면 마지막 주제 하나를 컴파일하지 않고 남긴다(발표 라이브 시연용, #54).
    반환: {lecture, run, topics:[...], allowed_pages, coverage, held}
    """
    cb = progress or on_progress or (lambda *a: None)

    def emit(stage, percent, detail=""):
        try:
            cb(stage, percent, detail)
        except TypeError:
            cb(stage, percent)  # detail 없는 콜백도 허용

    run_id = uuid.uuid4().hex[:8]
    emit("upload", 5, f"{lecture} '{title}' 시작 (run {run_id})")

    fg = stage_frameguard(lecture)
    emit("align", 10, f"FrameGuard: {fg['decision']}")
    if fg["decision"] != "allow":
        emit("error", 10, fg.get("reason", "FrameGuard block"))
        return {"lecture": lecture, "run": run_id, "topics": [], "allowed_pages": 0,
                "error": fg.get("reason", "FrameGuard block")}

    ok, msg = stage_episodic(lecture)
    emit("episodic", 30, msg or "episodic 생성")
    if not ok:
        emit("error", 30, "build_episodic 실패")
        return {"lecture": lecture, "run": run_id, "topics": [], "allowed_pages": 0,
                "error": "build_episodic 실패"}

    all_topics = O.topics_from_episodic(lecture)
    held = None
    topics = all_topics
    if hold_last and len(all_topics) > 1:
        held = all_topics[-1]
        topics = all_topics[:-1]
        emit("compile", 30, f"라이브 시연용으로 마지막 주제 s{held[0]}-{held[1]} 는 남긴다")
    results = []
    for i, (s_from, s_to) in enumerate(topics):
        pct = 30 + int(50 * (i + 1) / max(len(topics), 1))
        emit("compile", pct, f"주제 s{s_from}-{s_to} ({i+1}/{len(topics)})")
        results.append(O.run_compile_topic(lecture, s_from, s_to, run_id, emit))

    crit = stage_critic(lecture)
    emit("compile", 88, "비평 " + ("완료" if crit else "생략(critic.py 없음)"))

    cov = {"covered": 0, "total": 0}
    try:
        from tools.coverage import coverage
        cov = coverage(write=True)
        emit("compile", 92, f"커버리지 {cov['covered']}/{cov['total']}")
    except Exception as e:
        emit("compile", 92, f"커버리지 계산 생략: {e}")

    # ⑤ 빌드 — wiki → public (gitignore 우회 래퍼)
    try:
        from tools.build_wiki import build_once
        emit("build", 95, "Quartz 빌드")
        build_once()
    except Exception as e:
        emit("build", 95, f"빌드 생략: {e}")

    allowed = sum(1 for r in results for p in r["pages"] if p["verdict"] == "allow")
    held_msg = f" · 남긴 주제 s{held[0]}-{held[1]}" if held else ""
    emit("done", 100, f"주제 {len(topics)}개 · allow 페이지 {allowed}개{held_msg} · run {run_id}")
    return {"lecture": lecture, "run": run_id, "topics": results,
            "allowed_pages": allowed, "coverage": cov,
            "held": (f"s{held[0]}-{held[1]}" if held else None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lecture")
    ap.add_argument("--title", default="")
    ap.add_argument("--course", default="")
    ap.add_argument("--topic", default=None, help="s5-6 처럼 주제 하나만 ③ 실행")
    ap.add_argument("--live", action="store_true", help="발표용: 주제 하나만 빠르게")
    ap.add_argument("--hold-last", action="store_true", help="마지막 주제 하나는 남긴다(라이브 시연용)")
    args = ap.parse_args()

    # ③ 주제 하나만
    if args.topic or args.live:
        run_id = uuid.uuid4().hex[:8]
        rng = O.parse_topic(args.topic) if args.topic else (O.topics_from_episodic(args.lecture) or [(0, 0)])[0]
        if not rng:
            sys.exit("--topic s5-6 형식으로")
        progress("compile", 0, f"라이브 주제 {rng[0]}-{rng[1]} 시작 (run {run_id})")
        res = O.run_compile_topic(args.lecture, rng[0], rng[1], run_id, progress)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return

    # 전체 ①~⑤
    res = run(args.lecture, args.title, args.course, progress=progress, hold_last=args.hold_last)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
