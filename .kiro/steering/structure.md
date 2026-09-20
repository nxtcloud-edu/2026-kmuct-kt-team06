---
inclusion: always
---
# 저장소 구조와 소유

| 경로 | 소유 레인 | 내용 |
|---|---|---|
| `web/viewer/` · `site/quartz.config.yaml` | front-dongwook | 앵커 칩 · 미니 플레이어 · split · 자동 정지 |
| `web/notes/` | front-minsu | LLM 패널(발언 검색 포함) · 필기 · 대시보드·검토함 |
| `api/` | back-wooseok | 단일 서버: `public/` + 주입 + `/api/*` |
| `pipeline/` `hooks/` `tools/` `prompts/` `skills/` `mock/` `docs/` `CONTRACT.md` `lanes/` | back-kyuchan | 파이프라인·훅·계약 |
| `wiki/` `raw/` `public/` | (산출물) | 손으로 고치지 않는다 |

**내 레인 디렉터리 밖에는 한 줄도 쓰지 않는다.** 남의 것을 고쳐야 하면 `board.sh human "..."`.
시작할 때: `board.sh read` → `lanes/<내 레인>.md` → `.kiro/specs/<내 레인>/tasks.md` 순서로 읽고 1번부터.
막히면 3분 안에 `board.sh blocked`. 계약(`CONTRACT.md`)을 바꿔야 하면 코드를 고치기 전에 `board.sh human`.
