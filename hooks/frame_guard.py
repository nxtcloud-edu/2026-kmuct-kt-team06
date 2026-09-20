#!/usr/bin/env python3
"""FrameGuard (차단형, ① 단계 종료): segments.json이 앵커의 근거로 쓸 수 있는 상태인지 검사.
통과 못 하면 그 강의는 ②로 넘어가지 않는다.  python3 hooks/frame_guard.py raw/L3
stdout: {"decision": "allow"|"block", "reason": "..."}   (exit 0 / 2)
"""
import json, sys
from pathlib import Path

REQUIRED = {"k": int, "kind": str, "s": int, "t_start": (int, float), "t_end": (int, float), "final_frame": (str, type(None))}


def check(root: Path):
    p = root / "segments.json"
    if not p.exists():
        return [f"{p} 없음. tools/segment_video.py를 먼저 실행."]
    segs = json.loads(p.read_text(encoding="utf-8"))
    if not segs:
        return ["세그먼트 0개. --th 값을 낮춰 다시 분할 (판서 강의는 0.15~0.25)."]
    errs, prev_end = [], None   # 첫 구간은 0초가 아니어도 된다(녹음 앞 무음)
    for i, s in enumerate(segs):
        for key, typ in REQUIRED.items():
            if not isinstance(s.get(key), typ):
                errs.append(f"[{i}] '{key}' 누락 또는 타입 오류"); break
        else:
            if s["kind"] not in ("slide", "board"):
                errs.append(f"[{i}] kind는 slide|board")
            if not s["t_start"] < s["t_end"]:
                errs.append(f"[{i}] t_start({s['t_start']}) >= t_end({s['t_end']})")
            if prev_end is not None and abs(s["t_start"] - prev_end) > 0.11:
                errs.append(f"[{i}] 구간이 이어지지 않음: 앞 구간 끝 {prev_end}, 시작 {s['t_start']} (겹침·빈틈)")
            if s["final_frame"] is None:   # 녹음+PDF 강의: 프레임 대신 슬라이드 PNG 가 화면에 뜬다
                if s["kind"] != "slide" or not (root / "slides" / f"s{s['s']}.png").exists():
                    errs.append(f"[{i}] final_frame 이 없으면 slides/s{s['s']}.png 가 있어야 한다 (pdftoppm -png -r 80)")
            elif not (root / s["final_frame"]).exists():
                errs.append(f"[{i}] 프레임 파일 없음: {s['final_frame']}")
            prev_end = s["t_end"]
    return errs


def source_exists(root: Path, s: int, t: float) -> bool:
    """write_page_guard.py의 스텁을 채우는 함수: 앵커 [[L#s@t]]가 실제 구간을 가리키나."""
    segs = json.loads((root / "segments.json").read_text(encoding="utf-8"))
    return any(x["s"] == s and x["t_start"] <= t <= x["t_end"] for x in segs)


if __name__ == "__main__":
    errs = check(Path(sys.argv[1]))
    print(json.dumps({"decision": "block" if errs else "allow",
                      "reason": "REJECTED: " + " / ".join(errs[:5]) if errs else "ok"}, ensure_ascii=False))
    sys.exit(2 if errs else 0)
