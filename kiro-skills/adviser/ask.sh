#!/bin/bash
# adviser: Kiro 에이전트가 막혔을 때 Fable(Claude Code 헤드리스)에게 자문을 구한다.
# 사용: ask.sh "질문"        또는   echo "질문" | ask.sh
#       ADVISER_FILES="hooks/write_page_guard.py PLAN.md" ask.sh "질문"   # 꼭 읽었으면 하는 파일
# 자문역은 읽기 전용(Read·Grep·Glob)이다. 파일을 고치지 않는다. 고치는 건 Kiro가 한다.
set -euo pipefail
Q="${*:-$(cat)}"
[ -z "$Q" ] && { echo "질문이 비었습니다" >&2; exit 64; }
MODEL="${ADVISER_MODEL:-claude-fable-5-1}"
LOG_DIR="${ADVISER_LOG_DIR:-.adviser}"; mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d-%H%M%S)

ROLE='너는 자문역이다. 실행자는 다른 에이전트(Kiro)이고 너는 파일을 고치지 않는다.
- 현재 폴더의 코드를 Read·Grep·Glob으로 직접 확인하고 답한다. 추측으로 답하지 않는다.
- 설계 정본이 있으면 먼저 읽는다: claude6-harness.md, PLAN.md, hooks/registry.md.
- 답 형식: ① 결론 한 줄 ② 근거(파일:줄) ③ Kiro가 그대로 실행할 다음 단계 1~5개 ④ 하지 말 것.
- 범위를 넓히지 않는다. 질문받은 것만. 600자 안팎.'

PROMPT="$Q"
[ -n "${ADVISER_FILES:-}" ] && PROMPT="$PROMPT

먼저 읽을 파일: $ADVISER_FILES"

# CLAUDECODE가 남아 있으면 중첩 실행을 거부하므로 지운다.
OUT=$(env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p "$PROMPT" \
  --model "$MODEL" --effort high \
  --tools "Read,Grep,Glob" \
  --append-system-prompt "$ROLE" \
  --output-format text 2>"$LOG_DIR/$TS.err") || { echo "adviser 호출 실패: $(tail -3 "$LOG_DIR/$TS.err")" >&2; exit 1; }

printf '## %s\n\n**Q.** %s\n\n%s\n\n---\n' "$TS" "$Q" "$OUT" >> "$LOG_DIR/log.md"
echo "$OUT"
