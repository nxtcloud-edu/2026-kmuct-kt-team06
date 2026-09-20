#!/usr/bin/env bash
# EC2 배포 런북 (#54 ③). 실제 EC2 접속·scp 는 사람이 한다 — 이 스크립트는 EC2 안에서 실행한다.
#
#   사람이 로컬에서:
#     scp -r raw/L1  ec2-user@<EC2_IP>:~/AWS-MOTGA/raw/     # 실강의 데이터(저장소에 없음)
#     scp .env       ec2-user@<EC2_IP>:~/AWS-MOTGA/.env     # 키(저장소에 없음)
#   그다음 EC2 안에서:
#     cd ~/AWS-MOTGA && DEMO_TOKEN=<토큰> bash tools/deploy_ec2.sh
#
# 이 스크립트가 하는 일: 사전 점검 → 의존성 → tmux 세션 2개(빌드 watch / API 서버) → 헬스체크.
# 파괴적 동작 없음. git clone/pull·npm ci 만 한다.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
PORT="${PORT:-8000}"
LECTURE="${LECTURE:-L1}"

say() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$1"; exit 1; }
ok() { printf '\033[32m✓ %s\033[0m\n' "$1"; }

# ── 1. 사전 점검 ────────────────────────────────────────────────
say "1. 사전 점검"
command -v node >/dev/null || fail "node 없음 — Node ≥22 설치 필요"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 22 ] || fail "Node $NODE_MAJOR — 22 이상 필요 (nvm install 22)"
ok "Node $(node -v)"
command -v python3 >/dev/null || fail "python3 없음"
ok "$(python3 --version)"
command -v tmux >/dev/null || fail "tmux 없음 (sudo yum install -y tmux)"
ok "tmux 있음"

# 실데이터·키는 저장소에 없다 → scp 로 올라와 있어야 한다
[ -f "raw/$LECTURE/segments.json" ] || fail "raw/$LECTURE/segments.json 없음 — 로컬에서 scp 로 올려라"
ok "raw/$LECTURE 실데이터 있음"
[ -f ".env" ] || printf '\033[33m! .env 없음 — LLM/QA 는 stub 로 돈다(정적·앵커 데모는 됨)\033[0m\n'

# ── 2. 의존성 ──────────────────────────────────────────────────
say "2. 의존성 (git pull + npm ci)"
git pull --ff-only 2>&1 | tail -2 || printf '\033[33m! git pull 생략(수동 확인)\033[0m\n'
( cd site && npm ci 2>&1 | tail -3 ) || fail "npm ci 실패"
ok "site/ 의존성 설치"

# ── 3. tmux 세션 2개 ───────────────────────────────────────────
say "3. tmux 세션 (빌드 watch · API 서버)"
tmux has-session -t wiki 2>/dev/null && tmux kill-session -t wiki
tmux has-session -t api  2>/dev/null && tmux kill-session -t api
# ① Quartz 빌드 watch (wiki → public, gitignore 우회 래퍼)
tmux new-session -d -s wiki "cd '$ROOT' && python3 tools/build_wiki.py --watch 2>&1 | tee /tmp/wiki_watch.log"
ok "tmux 'wiki' — build_wiki --watch"
# ② API 서버 (자동 재시작 루프). DEMO_TOKEN 은 이 스크립트 환경에서 물려준다
tmux new-session -d -s api "cd '$ROOT' && DEMO_TOKEN='${DEMO_TOKEN:-}' PORT='$PORT' bash api/run.sh 2>&1 | tee /tmp/api.log"
ok "tmux 'api' — api/run.sh (port $PORT)"

# ── 4. 헬스체크 (서버가 뜰 때까지 잠깐 대기) ────────────────────
say "4. 헬스체크"
for i in $(seq 1 15); do
  curl -fsS "http://localhost:$PORT/" -o /dev/null 2>/dev/null && break
  sleep 1
done
BASE="http://localhost:$PORT"
check() {
  local name="$1" url="$2"
  if curl -fsS "$url" -o /tmp/hc_out 2>/dev/null; then
    ok "$name  ($(head -c 60 /tmp/hc_out | tr -d '\n'))"
  else
    printf '\033[31m✗ %s — %s 응답 없음\033[0m\n' "$name" "$url"
  fi
}
check "정적(Quartz)   /"                 "$BASE/"
check "집계  /api/stats"                 "$BASE/api/stats"
check "구간표 /api/segments/$LECTURE"     "$BASE/api/segments/$LECTURE"

say "완료"
echo "  로그:   tmux attach -t wiki   /   tmux attach -t api"
echo "  중지:   tmux kill-session -t wiki; tmux kill-session -t api"
echo "  라이브 시연:  LLM_PROVIDER=openai python3 -m pipeline.run $LECTURE --topic s21-21 --live"
