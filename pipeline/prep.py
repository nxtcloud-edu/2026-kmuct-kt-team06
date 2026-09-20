#!/usr/bin/env python3
"""① 적재 전처리 — 업로드 원본 → FrameGuard 가 읽을 수 있는 raw/L{n}/ (모델 0회).

  python3 -m pipeline.prep L9 --title "머지소트" --course "알고리즘"
  from pipeline.prep import prep;  ok, msg = prep("L9", "머지소트", "알고리즘", emit=cb)

api/ingest.py 가 업로드를 raw/L{n}/{slides|audio|video|transcript}_{i}.{ext} 로 떨궈 두면,
사람이 손으로 하던 절차를 그대로 자동화한다:
  1) pdftoppm  슬라이드 PDF → raw/L{n}/slides/s1.png …          (FrameGuard 가 쪽마다 요구)
  2) pdftotext 쪽별 텍스트 → raw/L{n}/book.md (`<!-- page N | … -->` 구분, align_slides 입력)
  3) 전사본 확보 — 시각 있는 md 그대로 / json 변환 / 없으면 tools/stt_grok.py
  4) tools/align_slides.py → segments.json + transcript.json, 길이 0 구간은 버리고 k 를 1부터 다시
  5) ffmpeg  녹음/영상 → raw/L{n}/L{n}.mp4 (+faststart — 플레이어가 seek 하려면 인덱스가 앞에 있어야)
  6) raw/media.local.json 에 과목·날짜·영상 종류 덧씌우기 (추적되는 api/media.json 은 건드리지 않는다)

예외를 밖으로 던지지 않는다. 언제나 (ok, 짧은 사유) 를 돌려준다.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 다글로 전사본 머리말. align_slides.read_transcript 의 정규식과 같은 것만 인정한다.
TS_HEAD = re.compile(r"^## (\d+):(\d\d):(\d\d)\s*$", re.M)
# 교본 쪽 구분자. align_slides.read_slides 의 `<!-- page (\d+)[^>]*-->` 가 읽는 형식.
PAGE_MARK = "<!-- page {n} | 원본: {name}#page={n} -->"

MEDIA_EXT = (".mp4", ".m4a", ".mp3", ".wav")
TEXT_EXT = (".md", ".txt", ".json")
OWN = {"book.md", "segments.json", "transcript.json", "stt.json", "transcript_from_json.md"}

T_PDF, T_ALIGN, T_FFMPEG, T_STT = 120, 120, 300, 1500


# ── 잡일 ────────────────────────────────────────────────────────────────────
def _run(cmd, timeout, **kw):
    """(ok, stdout, stderr). 실행 자체가 안 되면 ok=False."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        return r.returncode == 0, r.stdout, (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, "", f"시간 초과({timeout}s): {Path(str(cmd[0])).name}"
    except (OSError, ValueError) as e:
        return False, "", f"{Path(str(cmd[0])).name} 실행 실패: {e}"


def _write_atomic(path: Path, text: str):
    """같은 디렉터리에 임시 파일로 쓰고 os.replace — 반쯤 쓰인 파일을 서버가 읽지 않게."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _num(name: str) -> int:
    m = re.search(r"(\d+)(?!.*\d)", name)
    return int(m.group(1)) if m else 0


def _uploads(d: Path, exts) -> list[Path]:
    """업로드 원본 후보 — 우리가 만든 산출물은 뺀다. 서버가 붙인 번호 순."""
    out = [p for p in d.iterdir()
           if p.is_file() and p.suffix.lower() in exts and p.name not in OWN and not p.name.startswith(".")]
    return sorted(out, key=lambda p: (_num(p.name), p.name))


def _hhmmss(t: float) -> str:
    t = max(int(t), 0)
    return f"## {t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


# ── ① 슬라이드 ──────────────────────────────────────────────────────────────
def _render_slides(pdf: Path, d: Path) -> tuple[int, str]:
    """pdftoppm → slides/s1.png … . (쪽수, 사유). 쪽수 0 이면 실패."""
    sl = d / "slides"
    sl.mkdir(parents=True, exist_ok=True)
    for old in list(sl.glob("p-*.png")) + list(sl.glob("s*.png")):
        old.unlink(missing_ok=True)
    ok, _o, err = _run(["pdftoppm", "-png", "-r", "60", str(pdf), str(sl / "p")], T_PDF)
    pages = sorted(sl.glob("p-*.png"), key=lambda p: _num(p.name))
    if not pages:
        return 0, err or "pdftoppm 이 PNG 를 만들지 못했습니다"
    for i, p in enumerate(pages, 1):          # 쪽 순서대로 s1.png … (FrameGuard 가 찾는 이름)
        p.replace(sl / f"s{i}.png")
    return len(pages), "" if ok else err


def _build_book(pdf: Path, d: Path, pages: int) -> str:
    """쪽별 pdftotext -layout → book.md. align_slides 가 읽는 쪽 구분자를 그대로 쓴다."""
    chunks = []
    for k in range(1, pages + 1):
        ok, txt, _e = _run(["pdftotext", "-f", str(k), "-l", str(k), "-layout", str(pdf), "-"], T_PDF)
        body = (txt if ok else "").replace("\f", "").strip()
        chunks.append(PAGE_MARK.format(n=k, name=pdf.name) + "\n\n" + body + "\n")
    book = d / "book.md"
    _write_atomic(book, "\n".join(chunks))
    return str(book)


# ── ② 전사본 ────────────────────────────────────────────────────────────────
def _json_rows(p: Path):
    """[{t_start,t_end,text}] 모양이면 그 list, 아니면 None."""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, list) or not data:
        return None
    rows = [x for x in data if isinstance(x, dict) and "t_start" in x and "text" in x]
    return rows or None


def _rows_to_md(rows, out: Path) -> Path:
    """문장 단위 json → 다글로 md. 연속 행을 45초 이하 문단으로 묶고 머리말은 첫 행의 t_start."""
    paras = []
    for r in rows:
        try:
            ts = float(r["t_start"])
        except (TypeError, ValueError):
            continue
        text = str(r.get("text") or "").strip()
        if not text:
            continue
        if not paras or ts - paras[-1]["t"] >= 45.0:
            paras.append({"t": ts, "parts": [text]})
        else:
            paras[-1]["parts"].append(text)
    body = "\n".join(_hhmmss(p["t"]) + "\n\n" + " ".join(p["parts"]) + "\n" for p in paras)
    _write_atomic(out, body)
    return out


def _stt(audio: Path, d: Path, emit) -> tuple[Path | None, str]:
    """tools/stt_grok.py 를 하위 프로세스로. 키는 환경변수로만 넘긴다(인자·로그에 남기지 않는다)."""
    script = ROOT / "tools" / "stt_grok.py"
    if not script.is_file():
        return None, "tools/stt_grok.py 가 없습니다"
    env = os.environ.copy()
    if not env.get("X_AI") and env.get("XAI_API_KEY"):
        env["X_AI"] = env["XAI_API_KEY"]        # 서버는 XAI_API_KEY 로 들고 있다
    if not env.get("X_AI"):
        return None, "전사본이 없고 STT 키(X_AI)도 없습니다"
    out = d / "stt.json"
    emit("stt", 15, f"{audio.name} STT 시작 (최대 {T_STT // 60}분)")
    ok, _o, err = _run([sys.executable, str(script), str(audio), str(out)], T_STT, env=env)
    if not ok or not out.is_file():
        return None, "STT 실패: " + (err.splitlines()[-1] if err else "출력 없음")[:120]
    return out, ""


def _transcript(d: Path, emit) -> tuple[Path | None, str]:
    """전사본 md 경로(align_slides 입력)를 정한다. 우선순위: 시각 md → json → (시각 없는 글) 실패 → STT."""
    texts = _uploads(d, TEXT_EXT)
    for p in texts:                                   # 1) 시각이 박힌 md/txt — 그대로 쓴다
        if p.suffix.lower() in (".md", ".txt"):
            try:
                if TS_HEAD.search(p.read_text(encoding="utf-8", errors="replace")):
                    return p, ""
            except OSError:
                continue
    for p in texts:                                   # 2) 문장 단위 json — md 로 바꿔 쓴다
        if p.suffix.lower() == ".json" and (rows := _json_rows(p)):
            return _rows_to_md(rows, d / "transcript_from_json.md"), ""
    if any(p.suffix.lower() in (".md", ".txt") for p in texts):   # 3) 시각 없는 글 — 붙일 데가 없다
        return None, "전사본에 시간 정보(## HH:MM:SS)가 없습니다 — 다글로 md 나 문장 단위 json 이 필요합니다"
    media = _uploads(d, MEDIA_EXT)                    # 4) 녹음이라도 있으면 STT
    if not media:
        return None, "전사본도 녹음도 없습니다"
    out, why = _stt(media[0], d, emit)
    if out is None:
        return None, why
    rows = _json_rows(out)
    if not rows:
        return None, "STT 결과가 비었습니다"
    emit("stt", 25, f"STT 문장 {len(rows)}개")
    return _rows_to_md(rows, d / "transcript_from_json.md"), ""


# ── ③ 구간표 ────────────────────────────────────────────────────────────────
def _fix_segments(path: Path) -> tuple[int, str]:
    """길이 0(t_end<=t_start) 구간은 FrameGuard 가 막는다 → 버리고 k 를 1부터 다시. (구간 수, 사유)"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return 0, f"segments.json 을 읽지 못했습니다: {e}"
    segs = data.get("segments") if isinstance(data, dict) else data
    if not isinstance(segs, list):
        return 0, "segments.json 모양이 예상과 다릅니다"
    kept = []
    for g in segs:
        try:
            if isinstance(g, dict) and float(g["t_end"]) > float(g["t_start"]):
                kept.append(g)
        except (KeyError, TypeError, ValueError):
            continue
    for i, g in enumerate(kept, 1):
        g["k"] = i
    if isinstance(data, dict):
        data["segments"] = kept          # 위쪽 모양(dict/list)은 그대로 둔다
    else:
        data = kept
    _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=1))
    return len(kept), ""


# ── ④ 미디어·메타 ───────────────────────────────────────────────────────────
def _media(d: Path, lecture: str) -> dict | None:
    """업로드 녹음/영상 → raw/L{n}/L{n}.mp4 (인덱스 앞으로). 실패해도 prep 은 계속된다."""
    dest = d / f"{lecture}.mp4"
    src = next((p for p in _uploads(d, MEDIA_EXT) if p.name != dest.name), None)
    if src is None:
        return None
    ext = src.suffix.lower()
    kind = "mp4" if ext == ".mp4" else "audio"
    codec = ["-c", "copy"] if ext in (".mp4", ".m4a") else ["-c:a", "aac", "-b:a", "64k"]
    ok, _o, _e = _run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), *codec,
                       "-movflags", "+faststart", str(dest)], T_FFMPEG)
    if not ok or not dest.is_file():
        dest.unlink(missing_ok=True)
        return None
    return {"kind": kind, "src": f"/raw/{lecture}/{lecture}.mp4"}


def _overlay(root: Path, lecture: str, title: str, course: str, video: dict | None):
    """raw/media.local.json — 추적되는 api/media.json 대신 여기에 덧씌운다(api/store.py 가 합쳐 읽는다)."""
    path = root / "raw" / "media.local.json"
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        cur = cur if isinstance(cur, dict) else {}
    except (OSError, ValueError):
        cur = {}
    entry = dict(cur.get(lecture) if isinstance(cur.get(lecture), dict) else {})
    entry.update({"course": course, "title": title, "date": datetime.date.today().isoformat()})
    if video:
        entry["video"] = video
    cur[lecture] = entry
    _write_atomic(path, json.dumps(cur, ensure_ascii=False, indent=2) + "\n")


# ── 본체 ────────────────────────────────────────────────────────────────────
def prep(lecture, title="", course="", emit=None, root=None) -> tuple[bool, str]:
    """업로드 원본 → segments.json 까지. 예외를 던지지 않고 (ok, 사유) 를 돌려준다."""
    def say(stage, percent, detail=""):
        if emit is None:
            return
        try:
            emit(stage, percent, detail)
        except Exception:      # noqa: BLE001 — 진행률 콜백 때문에 파이프라인이 죽지 않게
            pass

    try:
        base = Path(root) if root else ROOT
        d = base / "raw" / str(lecture)
        segp = d / "segments.json"
        if segp.exists():
            return True, "already prepared"
        if not d.is_dir():
            return False, f"raw/{lecture} 가 없습니다"

        pdfs = _uploads(d, (".pdf",))
        pdf = next((p for p in pdfs if p.name.startswith("slides_")), pdfs[0] if pdfs else None)
        if pdf is None:
            return False, "슬라이드 PDF가 필요합니다"

        say("stt", 10, f"{pdf.name} 슬라이드 렌더")
        pages, why = _render_slides(pdf, d)
        if not pages:
            return False, f"슬라이드 렌더 실패: {why[:120]}"
        book = _build_book(pdf, d, pages)
        say("stt", 12, f"슬라이드 {pages}쪽 · book.md 생성")

        tr, why = _transcript(d, say)
        if tr is None:
            return False, why

        say("align", 25, f"구간 정렬 ({Path(tr).name})")
        ok, out, err = _run([sys.executable, str(ROOT / "tools" / "align_slides.py"), book, str(tr), str(d)], T_ALIGN)
        if not ok:
            return False, "구간 정렬 실패: " + ((err or out).strip().splitlines()[-1] if (err or out).strip() else "?")[:140]
        if not segp.is_file() or not (d / "transcript.json").is_file():
            return False, "구간 정렬이 segments.json / transcript.json 을 남기지 않았습니다"
        n, why = _fix_segments(segp)
        if not n:
            return False, why or "쓸 수 있는 구간이 0개입니다"

        video = _media(d, str(lecture))
        _overlay(base, str(lecture), title, course, video)
        msg = f"슬라이드 {pages}쪽 · 구간 {n}개" + (f" · {video['kind']}" if video else " · 미디어 없음")
        say("align", 30, msg)
        return True, msg
    except Exception as e:      # noqa: BLE001 — 계약: 절대 예외를 올리지 않는다
        return False, f"{type(e).__name__}: {e}"[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lecture")
    ap.add_argument("--title", default="")
    ap.add_argument("--course", default="")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    ok, msg = prep(a.lecture, a.title, a.course,
                   emit=lambda s, p, d="": print(f"[{s:8} {p:3}%] {d}", file=sys.stderr), root=a.root)
    print(json.dumps({"ok": ok, "detail": msg}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
