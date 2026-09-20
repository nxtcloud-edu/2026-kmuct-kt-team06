#!/usr/bin/env python3
"""녹음 → 문장 단위 transcript.json (Grok STT, CONTRACT §4.1b).   ✅ 2026-09-20 실측

  X_AI=... python3 tools/stt_grok.py <audio> <out/transcript.json> [--offset 초] [--chunk 600]

POST https://api.x.ai/v1/stt  (multipart: file, language=ko) → {text, language, duration, words:[{text,start,end}]}
단어마다 시각이 온다 → 문장부호(. ? !)에서 끊어 [{t_start, t_end, text}] 로 묶는다. 긴 파일은 --chunk 초씩 잘라 보낸다(ffmpeg).
키는 환경변수 X_AI 로만. 출력에 넣지 않는다.
"""
import json, os, subprocess, sys, tempfile, urllib.request, uuid
from pathlib import Path

URL = "https://api.x.ai/v1/stt"


def post(path: Path) -> dict:
    key = os.environ.get("X_AI") or sys.exit("환경변수 X_AI 없음")
    b = "----stt" + uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nko\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: audio/mpeg\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(URL, data=body, headers={"Authorization": f"Bearer {key}", "User-Agent": "curl/8.7.1",
                                                          "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def sentences(words, offset):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w["text"].rstrip().endswith((".", "?", "!")) or len(cur) >= 40:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return [{"t_start": round(s[0]["start"] + offset, 2), "t_end": round(s[-1]["end"] + offset, 2),
             "text": " ".join(x["text"] for x in s)} for s in out]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    opt = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    src, out, base, chunk = Path(args[0]), Path(args[1]), opt("--offset", 0.0), opt("--chunk", 600.0)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]))
    result, t = [], 0.0
    with tempfile.TemporaryDirectory() as td:
        while t < dur:
            part = Path(td) / f"part_{int(t)}.mp3"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-t", str(chunk), "-i", str(src),
                            "-ac", "1", "-ar", "16000", "-b:a", "48k", str(part)], check=True)
            d = post(part)
            result += sentences(d.get("words", []), base + t)
            print(f"  {int(t)}s~ : 단어 {len(d.get('words', []))}개", file=sys.stderr)
            t += chunk
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"문장 {len(result)}개 → {out}")


if __name__ == "__main__":
    main()
