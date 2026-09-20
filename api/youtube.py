#!/usr/bin/env python3
"""유튜브 보충 영상(F-13). TranscriptAPI 를 HTTP 로 부른다(EC2는 yt-dlp 가 막힌다, CONTRACT §5.2).

- 교수 채널(api/media.json 의 professorChannel) 결과를 먼저, 그다음 일반 검색.
- 응답을 raw/.ytcache/<sha1(q)>.json 에 캐시(크레딧 100개뿐).
- 키가 없거나 호출 실패면 [] (QA 응답은 정상으로 나가야 한다, R6).
- 새 라이브러리 금지(§9) → urllib 만 쓴다.

영상 카드(§5.1): {videoId,title,channel,duration,thumbnail,url,source:"professor"|"search"}
"""
import hashlib
import json
import os
import urllib.parse
import urllib.request

from api import store

ROOT = store.ROOT
CACHE_DIR = ROOT / "raw" / ".ytcache"

# TranscriptAPI (또는 호환) 엔드포인트·키는 환경변수로. 없으면 검색 안 함.
YT_API_BASE = os.environ.get("YT_API_BASE", "https://www.searchapi.io/api/v1/search")
YT_API_KEY = os.environ.get("YT_API_KEY")
YT_TIMEOUT = float(os.environ.get("YT_TIMEOUT", "8"))


def _cache_path(q: str):
    h = hashlib.sha1(q.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _read_cache(q: str):
    p = _cache_path(q)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _write_cache(q: str, data):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(q).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _professor_channel():
    ch = store.media_config().get("professorChannel")
    return ch if isinstance(ch, str) and ch.startswith("UC") else None


def _http_search(query: str, channel_id: str | None):
    """HTTP GET → 영상 목록. 실패하면 예외를 올린다(호출자가 [] 로 흡수)."""
    params = {"engine": "youtube", "q": query, "api_key": YT_API_KEY}
    if channel_id:
        params["channel_id"] = channel_id
    url = f"{YT_API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=YT_TIMEOUT) as resp:  # noqa: S310 (검증된 https 엔드포인트)
        return json.loads(resp.read().decode("utf-8"))


def _to_cards(raw: dict, source: str) -> list:
    """엔드포인트 응답 → §5.1 카드. 필드명이 조금 달라도 최대한 흡수."""
    items = raw.get("videos") or raw.get("video_results") or raw.get("items") or []
    cards = []
    for it in items:
        vid = it.get("videoId") or it.get("id") or it.get("video_id") or ""
        if not vid:
            continue
        cards.append({
            "videoId": vid,
            "title": it.get("title", ""),
            "channel": (it.get("channel") or {}).get("title") if isinstance(it.get("channel"), dict) else it.get("channel", ""),
            "duration": it.get("duration") or it.get("length", ""),
            "thumbnail": it.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
            "url": it.get("url") or f"https://www.youtube.com/watch?v={vid}",
            "source": source,
        })
    return cards


def search(q: str) -> list:
    """교수 채널 먼저, 그다음 일반 검색. 캐시·실패 흡수 → 항상 list."""
    q = (q or "").strip()[:200]
    if not q:
        return []
    cached = _read_cache(q)
    if cached is not None:
        return cached
    if not YT_API_KEY:
        return []  # 키 없으면 검색 안 함(R6). 캐시에는 안 남긴다.

    cards = []
    ch = _professor_channel()
    try:
        if ch:
            cards += _to_cards(_http_search(q, ch), "professor")
        cards += _to_cards(_http_search(q, None), "search")
    except Exception:
        return []  # 호출 실패 → [] (QA 는 정상, R6)

    # videoId 중복 제거(교수 결과 우선)
    seen, uniq = set(), []
    for c in cards:
        if c["videoId"] in seen:
            continue
        seen.add(c["videoId"])
        uniq.append(c)
    _write_cache(q, uniq)
    return uniq


def warm(queries: list[str]):
    """발표용 질문 캐시 데우기. 이미 있으면 건너뛴다."""
    done = 0
    for q in queries:
        if _read_cache(q) is None and YT_API_KEY:
            search(q)
            done += 1
    return done
