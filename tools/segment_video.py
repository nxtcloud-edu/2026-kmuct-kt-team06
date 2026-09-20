#!/usr/bin/env python3
"""mp4 -> raw/L{n}/segments.json + seg_{k}_final.jpg

장면이 갑자기 바뀌는 지점을 경계로 잡고, 경계 '직전' 프레임을 그 구간의 마지막 필기 상태로 저장한다.
의존: ffmpeg, ffprobe (그 외 파이썬 패키지 없음). 선택: tesseract(--ocr).

  python3 tools/segment_video.py L3.mp4 --lecture L3 --out raw --th 0.30          # 슬라이드 강의
  python3 tools/segment_video.py L3.mp4 --lecture L3 --out raw --th 0.20 --ocr    # 판서 강의
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

BACKOFF = 0.5      # 경계 t에서 이만큼 앞 프레임을 저장
MIN_GAP = 3.0      # 이보다 촘촘한 경계는 합친다 (손·포인터 흔들림)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(video):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)])
    return float(r.stdout.strip())


def boundaries(video, th):
    r = run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"select='gt(scene,{th})',showinfo",
             "-an", "-f", "null", "-"])
    ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    merged = []
    for t in ts:
        if t < MIN_GAP:
            continue
        if merged and t - merged[-1] < MIN_GAP:
            merged[-1] = t          # 연속 변화는 마지막 시점을 경계로
        else:
            merged.append(t)
    return merged


def grab(video, t, dst):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(t, 0):.3f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(dst)])
    return dst.exists()


def ink_score(path):
    """잉크 픽셀 수. Pillow 없이 ffmpeg로 320x180 회색 원시 프레임을 받아 계산한다."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                        "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    px = r.stdout
    if not px:
        return 0
    mean = sum(px) / len(px)
    # 배경이 밝으면(화이트보드·슬라이드) 어두운 픽셀이 잉크, 어두우면(칠판) 밝은 픽셀이 잉크
    return sum(1 for p in px if (p < mean - 40 if mean > 110 else p > mean + 40))


def best_frame(video, t_end, dst, tmp, window=5.0, n=8):
    """경계 전 window초에서 n장을 뽑아 잉크가 가장 많은 프레임을 고른다 (교수가 가린 프레임 회피)."""
    cands = []
    for i in range(n):
        t = t_end - BACKOFF - window * i / n
        f = tmp / f"c{i}.jpg"
        if t > 0 and grab(video, t, f):
            cands.append((ink_score(f), f))
    if not cands:
        return False
    shutil.copy(max(cands)[1], dst)
    return True


def ocr(path, lang):
    r = run(["tesseract", str(path), "-", "-l", lang, "--psm", "6"])
    return " ".join(r.stdout.split())[:2000] if r.returncode == 0 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--lecture", required=True)
    ap.add_argument("--out", default="raw"); ap.add_argument("--th", type=float, default=0.30)
    ap.add_argument("--kind", choices=["slide", "board"], default="board")
    ap.add_argument("--ocr", action="store_true"); ap.add_argument("--lang", default="kor+eng")
    ap.add_argument("--best-frame", action="store_true")
    a = ap.parse_args()

    video = Path(a.video); out = Path(a.out) / a.lecture; out.mkdir(parents=True, exist_ok=True)
    tmp = out / ".tmp"; tmp.mkdir(exist_ok=True)
    end = duration(video)
    cuts = boundaries(video, a.th) + [end]

    segs, t0 = [], 0.0
    for k, t1 in enumerate(cuts, 1):
        name = f"seg_{k}_final.jpg"
        ok = (a.best_frame and best_frame(video, t1, out / name, tmp)) or grab(video, t1 - BACKOFF, out / name)
        if not ok:
            print(f"[warn] frame grab failed at k={k} t={t1:.1f}", file=sys.stderr)
        seg = {"k": k, "kind": a.kind, "s": k, "t_start": round(t0, 1), "t_end": round(t1, 1),
               "final_frame": name, "ocr": "", "ocr_engine": None}
        if a.ocr and ok and shutil.which("tesseract"):
            seg["ocr"], seg["ocr_engine"] = ocr(out / name, a.lang), "tesseract"
        segs.append(seg); t0 = t1
    shutil.rmtree(tmp, ignore_errors=True)
    (out / "segments.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.lecture}: {len(segs)} segments, th={a.th}, duration={end:.1f}s -> {out/'segments.json'}")


if __name__ == "__main__":
    main()
