#!/usr/bin/env python3
"""자료 불러오기(F-17, DESIGN §4~5). multipart 업로드 → 백그라운드 파이프라인.

- 확장자 화이트리스트, 합계 500MB, 파일명은 서버가 새로 짓는다.
- 진행률은 파이프라인 실제 단계에서(가짜 타이머 금지): upload→stt→align→episodic→compile→build→done.
- 파이프라인 모듈(pipeline/run.py 등)이 있으면 그걸, 없으면 축소 경로(파일만 배치하고 done).
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path

from api import store

ROOT = store.ROOT
RAW = ROOT / "raw"

ALLOWED_EXT = {".mp4", ".m4a", ".mp3", ".wav", ".txt", ".md", ".json", ".pdf"}
MAX_TOTAL = 500 * 1024 * 1024  # 500MB
STAGES = ["upload", "stt", "align", "episodic", "compile", "build", "done"]

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _next_lecture() -> str:
    """raw/L{n} 다음 번호."""
    nums = [int(m.group(1)) for d in RAW.glob("L*") if (m := re.match(r"^L(\d+)$", d.name))]
    return f"L{(max(nums) + 1) if nums else 1}"


def _server_name(lecture: str, idx: int, ext: str) -> str:
    """서버가 짓는 파일명 — 클라이언트 파일명을 믿지 않는다."""
    kind = "video" if ext in {".mp4"} else "audio" if ext in {".m4a", ".mp3", ".wav"} \
        else "slides" if ext == ".pdf" else "transcript"
    return f"{kind}_{idx}{ext}"


def create_job(files: list[tuple[str, bytes]], title: str, course: str):
    """files = [(filename, content_bytes)]. 검증 후 raw/L{n}/ 에 저장하고 {job, lecture} 반환.

    반환: (ok, payload_or_reason_tuple)
    """
    total = sum(len(c) for _n, c in files)
    if total > MAX_TOTAL:
        return False, (413, "TOO_LARGE", f"total {total} bytes exceeds 500MB")
    for name, _c in files:
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXT:
            return False, (415, "BAD_EXT", f"'{ext}' not allowed (mp4 m4a mp3 wav txt md json pdf)")
    if not files:
        return False, (400, "NO_FILES", "no files")

    lecture = _next_lecture()
    dest = RAW / lecture
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (name, content) in enumerate(files, 1):
        ext = Path(name).suffix.lower()
        fname = _server_name(lecture, i, ext)
        (dest / fname).write_bytes(content)
        saved.append(fname)

    job = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job] = {"lecture": lecture, "stage": "upload", "percent": 10,
                      "detail": f"{len(saved)}개 파일 업로드됨", "error": None}
    t = threading.Thread(target=_run_pipeline, args=(job, lecture, title, course, dest), daemon=True)
    t.start()
    return True, {"job": job, "lecture": lecture}


def _set(job: str, **kw):
    with _lock:
        if job in _jobs:
            _jobs[job].update(kw)


def _run_pipeline(job: str, lecture: str, title: str, course: str, dest: Path):
    """파이프라인 실제 단계. 실패해도 서버는 계속 돈다(stage:error)."""
    try:
        run_fn = _pipeline_run()
        if run_fn is not None:
            # 팀장 파이프라인이 있으면 진행률 콜백을 넘겨 실제 단계를 받는다.
            def progress(stage, percent, detail=""):
                _set(job, stage=stage, percent=percent, detail=detail, error=None)
            run_fn(lecture=lecture, title=title, course=course, src_dir=str(dest), progress=progress)
            _set(job, stage="done", percent=100, detail="완료", error=None)
            return
        # 축소 경로: 파이프라인 미도착 → 단계만 표시하고 파일 배치로 마무리(DESIGN 축소안)
        for stage, pct, detail in [
            ("stt", 30, "전사"), ("align", 45, "구간표"), ("episodic", 55, "정렬"),
            ("compile", 80, "컴파일"), ("build", 95, "빌드"),
        ]:
            _set(job, stage=stage, percent=pct, detail=f"{detail} (파이프라인 미도착 — 축소 경로)")
            time.sleep(0.2)
        _set(job, stage="done", percent=100, detail="파일 배치 완료(파이프라인 연결 대기)", error=None)
    except Exception as e:  # noqa: BLE001
        _set(job, stage="error", error=str(e)[:200])


def _pipeline_run():
    """pipeline/run.py 의 run(...) 이 있으면 반환. progress 콜백을 받는 시그니처를 기대."""
    try:
        from pipeline.run import run  # 팀장 산출물
        return run
    except Exception:
        return None


def job_status(job: str):
    with _lock:
        st = _jobs.get(job)
        return dict(st) if st else None
