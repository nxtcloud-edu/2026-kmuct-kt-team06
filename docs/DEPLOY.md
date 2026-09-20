# EC2 배포 런북 (#54 ③)

데모용 단일 EC2(m5.large 권장)에 올리는 순서. **실제 접속·scp 는 사람이 한다.**
EC2 안의 셋업은 `tools/deploy_ec2.sh` 한 방으로 끝난다(파괴적 동작 없음: git pull·npm ci·tmux 만).

한 프로세스 원칙: `api/server.py` 하나가 `public/`(Quartz 결과) + 주입 + `/web /raw /mock` + `/api/*` 를 전부 서빙한다.
Quartz 재빌드는 별도 tmux 세션(`build_wiki --watch`)이 `wiki/ → public/` 로 돌린다.

---

## 0-0. 실제 데모 서버 (2026-09-20, EC2 대신)

EC2 는 느려서 폐기했다. 데모는 **stockllm**(OCI 도쿄)에서 돈다: https://motga.193-123-163-215.sslip.io

```bash
# 코드(main) — 서버에 git 인증이 없어 rsync 로 올린다. 데이터·키·빌드 산출물은 제외
rsync -az --delete --exclude .git --exclude site/node_modules --exclude public --exclude wiki --exclude raw \
      --exclude __pycache__ --exclude web/viewer/library.local.json ./ stockllm:motga/
# 데이터(가짜 견본 L3 는 데모에 올리지 않는다)
rsync -az --exclude 'L3*' --exclude notes/L3 --exclude concepts/bfs.md --exclude concepts/dfs.md \
      --exclude concepts/graph-representation.md --exclude signals/exam-graph.md wiki/ stockllm:motga/wiki/
rsync -az --exclude L3 raw/ stockllm:motga/raw/
ssh stockllm 'tmux ls'                      # motga-wiki(build_wiki --watch) · motga-api(api.server 8010)
ssh stockllm 'tmux kill-session -t motga-api; tmux new-session -d -s motga-api "cd ~/motga && while true; do python3 -m api.server 8010; sleep 2; done"'   # api/·pipeline/ 을 바꿨을 때
```
- 필요 패키지: python3.10+, node 22, `poppler-utils`(pdftoppm·pdftotext), `ffmpeg`. Caddy 블록은 `/etc/caddy/Caddyfile` 의 `motga.…sslip.io`(백업 `Caddyfile.bak-motga-0920`).
- `web/` 만 바꿨으면 rsync 후 새로고침이면 된다(정적). 위키가 바뀌면 `--watch` 가 3초 안에 재빌드 + `library.local.json` 재생성.
- 발표 후: tmux 두 세션 종료, Caddy 블록 제거, 서버의 `~/motga/.env` 삭제.

## 0. 사전 (로컬에서, 한 번)

저장소에 **없는** 두 가지를 EC2로 올린다 — 실강의 데이터와 키:

```bash
# 실강의 데이터 (raw/L* 는 .gitignore, 교수님 저작물이라 커밋 안 함)
scp -r raw/L1  ec2-user@<EC2_IP>:~/AWS-MOTGA/raw/

# 키 (.env 는 .gitignore). 표준 이름 OPENAI_API_KEY·ANTHROPIC_API_KEY·GEMINI_API_KEY·XAI_API_KEY
scp .env       ec2-user@<EC2_IP>:~/AWS-MOTGA/.env
```

> `.env` 가 없어도 서버는 뜬다 — LLM/QA 만 stub 로 돌고, 정적·앵커 점프·필기·훅 데모는 정상.

## 1. EC2 최초 준비 (한 번)

```bash
# Node ≥22 (nvm 권장)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
. ~/.nvm/nvm.sh && nvm install 22 && nvm use 22
sudo yum install -y tmux git    # (Amazon Linux) / apt 면 apt-get install -y

git clone <repo-url> ~/AWS-MOTGA        # 이미 있으면 생략
```

## 2. 배포 (매번)

```bash
cd ~/AWS-MOTGA
DEMO_TOKEN=<데모토큰> bash tools/deploy_ec2.sh
```

스크립트가 하는 일:
1. **사전 점검** — Node≥22, python3, tmux, `raw/L1/segments.json` 존재
2. **의존성** — `git pull --ff-only`, `cd site && npm ci`
3. **tmux 세션 2개**
   - `wiki` : `python3 tools/build_wiki.py --watch` (wiki→public, gitignore 우회·grey 숨김)
   - `api`  : `DEMO_TOKEN=… PORT=8000 bash api/run.sh` (크래시 시 자동 재시작)
4. **헬스체크 3개** — `/` · `/api/stats` · `/api/segments/L1`

```
tmux attach -t wiki    # 빌드 로그
tmux attach -t api     # 서버 로그
tmux kill-session -t wiki; tmux kill-session -t api   # 중지
```

## 3. 데모 콘텐츠

발표 전 L1 을 미리 컴파일해 둔다(마지막 주제는 라이브 시연용으로 남긴다):

```bash
LLM_PROVIDER=openai python3 -m pipeline.run L1 \
  --title "RISC-V ISA" --course "컴퓨터구조" --hold-last
```

라이브 시연(발표 중 30초, 남겨 둔 주제 하나를 그 자리에서 컴파일 → 화면에 페이지가 자란다):

```bash
LLM_PROVIDER=openai python3 -m pipeline.run L1 --topic s21-21 --live
```

## 4. 헬스체크 (수동 확인용)

```bash
curl -fsS http://localhost:8000/                    | head -c 80   # 정적(Quartz)
curl -fsS http://localhost:8000/api/stats           | head -c 200  # 집계(페이지·훅·커버리지)
curl -fsS http://localhost:8000/api/segments/L1     | head -c 200  # 구간표(앵커 점프의 근거)
```

셋 다 200 + 본문이 나오면 정상. `/api/qa`·`/api/notes`·`/api/review/*` 는 쓰기·과금 경로라 `X-Demo-Token` 헤더가 필요하다(`DEMO_TOKEN` 설정 시).

## 5. 자주 막히는 곳

- **위키가 안 뜬다(실데이터)**: Quartz 는 `.gitignore` 를 존중해 `wiki/concepts/*·lectures/*` 실데이터를 빼먹는다 → 반드시 `tools/build_wiki.py`(gitignore 없는 임시경로 복사 후 빌드)로 빌드한다. `npx quartz build -d ../wiki` 직접 실행 금지.
- **모델 404**: 모델 이름이 죽으면 `LLM_STRONG`/`LLM_FAST` 환경변수로 살아 있는 id 를 못박는다(예: `LLM_STRONG=gpt-5 LLM_FAST=gpt-5-mini`).
- **키가 안 잡힌다**: `pipeline/llm.py` 가 import 시 저장소 `.env` 를 자동 로드한다(옛 이름도 매핑). 그래도 안 되면 `set -a; . ./.env; set +a` 후 실행.
- **206/Range**: 영상·오디오 앵커 점프는 `devserve.send_bytes()` 의 Range 응답에 의존한다 — 직접 `open()` 서빙 금지.
- **포트**: 80 을 쓰려면 root 권한이 필요하다. 데모는 8000 권장, 필요 시 리버스 프록시.
