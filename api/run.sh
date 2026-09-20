#!/usr/bin/env bash
# 서버 자동 재시작 루프(EC2 데모용). 크래시하면 2초 뒤 되살린다.
#   PORT=8000 DEMO_TOKEN=... YT_API_KEY=... api/run.sh
# 저장소 루트에서 실행해야 한다(python3 -m api.server 가 루트 기준).
set -u
cd "$(dirname "$0")/.." || exit 1   # 저장소 루트로
PORT="${PORT:-8000}"

# 발표 질문 캐시 데우기(키 있을 때만 실제 호출; 실패해도 서버는 뜬다)
python3 -m api.server --warm "$PORT" &
WARM_PID=$!
sleep 0  # --warm 은 warm 후 곧바로 serve 로 들어간다

# --warm 프로세스가 그대로 서버가 된다. 죽으면 되살린다.
while true; do
  wait "$WARM_PID" 2>/dev/null
  echo "[run.sh] server exited, restarting in 2s..." >&2
  sleep 2
  python3 -m api.server "$PORT" &
  WARM_PID=$!
done
