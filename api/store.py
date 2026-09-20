#!/usr/bin/env python3
"""데이터 읽기 계층 — 구간표·전사본·미디어 설정. 경로는 전부 저장소 루트 기준 절대경로.

- 산출물(raw/, wiki/)은 읽기만 한다(CONTRACT §1). 파일 mtime 캐시로 재빌드 경합을 흡수한다.
- 앵커 규약은 CONTRACT §3. 유효 앵커 = segments.json 에 s 가 같고 t_start<=t<=t_end 인 행이 있는 것.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"

# CONTRACT §3 — 전 레인 공용, 절대 불변. 이 정규식만 쓴다.
ANCHOR_RE = re.compile(r"L(\d+)#s(\d+)@t=(\d+)")
LECTURE_RE = re.compile(r"^L\d+$")  # 경로 조립에 쓰이므로 엄격히

# (path -> (mtime, parsed)) mtime 캐시. 재빌드로 파일이 잠깐 사라지면 마지막 값을 지운다.
_cache: dict[str, tuple[float, object]] = {}


def _read_json(path: Path):
    """mtime 캐시 JSON 읽기. 없으면 None."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        _cache.pop(key, None)
        return None
    hit = _cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    _cache[key] = (mtime, data)
    return data


def valid_lecture(lecture: str) -> bool:
    return bool(lecture and LECTURE_RE.match(lecture))


def parse_anchor(anchor: str):
    """앵커 문자열 -> (lecture, s, t) 또는 None. URL 디코드는 호출자가 한다."""
    if not anchor:
        return None
    m = ANCHOR_RE.search(anchor)
    if not m:
        return None
    return f"L{m.group(1)}", int(m.group(2)), int(m.group(3))


def load_segments(lecture: str) -> list | None:
    """raw/L{n}/segments.json (list). 없으면 None."""
    if not valid_lecture(lecture):
        return None
    data = _read_json(RAW / lecture / "segments.json")
    return data if isinstance(data, list) else None


def load_transcript(lecture: str) -> list:
    """raw/L{n}/transcript.json (list). 파이프라인 산출물 — 없으면 []."""
    if not valid_lecture(lecture):
        return []
    data = _read_json(RAW / lecture / "transcript.json")
    return data if isinstance(data, list) else []


# api/media.json — 강의별 영상 소스·채널·날짜. segments.json 에도 video 가 있지만
# 녹음만 있는 강의(kind:"audio")나 유튜브 강의는 여기서 덮어쓴다(design.md).
_MEDIA_PATH = ROOT / "api" / "media.json"


def media_config() -> dict:
    data = _read_json(_MEDIA_PATH)
    return data if isinstance(data, dict) else {}


def video_for(lecture: str, segments_video: dict | None) -> dict:
    """영상 소스: media.json 우선, 없으면 segments.json 의 video, 그것도 없으면 mp4 기본 경로."""
    cfg = media_config().get(lecture, {})
    if isinstance(cfg.get("video"), dict):
        return cfg["video"]
    if isinstance(segments_video, dict):
        return segments_video
    return {"kind": "mp4", "src": f"/raw/{lecture}/{lecture}.mp4"}


def lecture_date(lecture: str) -> str | None:
    """강의 날짜(출처 말풍선용). media.json 에 있으면 준다."""
    d = media_config().get(lecture, {}).get("date")
    return d if isinstance(d, str) else None


def frame_url(lecture: str, seg: dict) -> str | None:
    ff = seg.get("final_frame")
    return f"/raw/{lecture}/{ff}" if ff else None


def slide_url(lecture: str, seg: dict) -> str | None:
    """슬라이드가 있으면 /raw/L{n}/slides/s{s}.png (CONTRACT §4.1). 파일이 실제로 있을 때만."""
    s = seg.get("s")
    if s is None:
        return None
    p = RAW / lecture / "slides" / f"s{s}.png"
    return f"/raw/{lecture}/slides/s{s}.png" if p.is_file() else None


def quote_at(lecture: str, t: float, limit: int = 120) -> str | None:
    """그 초가 속한 전사 문장(최대 limit자). transcript 없으면 None (CONTRACT §5 quote)."""
    for p in load_transcript(lecture):
        try:
            if p["t_start"] <= t <= p["t_end"]:
                text = (p.get("text") or "").strip()
                return text[:limit] if text else None
        except (KeyError, TypeError):
            continue
    return None


def find_segment(lecture: str, s: int, t: float) -> dict | None:
    """s 가 같고 t_start<=t<=t_end 인 구간(CONTRACT §3 유효 앵커)."""
    segs = load_segments(lecture)
    if not segs:
        return None
    for g in segs:
        try:
            if g.get("s") == s and g["t_start"] <= t <= g["t_end"]:
                return g
        except (KeyError, TypeError):
            continue
    return None


def find_segment_by_k(lecture: str, k: int) -> dict | None:
    """k 로 구간을 찾는다(필기 저장 — 프론트가 k 를 준다)."""
    segs = load_segments(lecture)
    if not segs:
        return None
    for g in segs:
        if g.get("k") == k:
            return g
    return None


def anchor_second(seg: dict) -> int:
    """필기 앵커의 초(CONTRACT §5.4): t = int(t_end), 단 t < t_start 면 ceil(t_start)."""
    t = int(seg["t_end"])
    if t < seg["t_start"]:
        t = math.ceil(seg["t_start"])
    return t


def segments_video(lecture: str) -> dict | None:
    """mock/segments/L3.json 처럼 segments 파일에 붙은 video 를 찾는다.
    raw 의 segments.json 은 순수 list 라 video 가 없다 → media/기본으로 채운다."""
    data = _read_json(RAW / lecture / "segments.json")
    if isinstance(data, dict):
        return data.get("video")
    return None
