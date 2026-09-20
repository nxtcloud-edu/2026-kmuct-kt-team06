# AWS-MOTGA — 강의 위키 (카론톤 / Kirothon 2026-09-20)

전사본 + 슬라이드/판서 프레임 + 영상이 **앵커로 묶인 위키**로 쌓인다.
위키 문장을 클릭하면 그 말이 나온 프레임과 영상의 그 초로 점프하고, 영상은 구간 끝에서 멈춰 그 자리에서 필기를 받는다.

## 먼저 읽을 것 (순서대로)

1. **`CONTRACT.md`** — 레인 소유 디렉터리 · 앵커 규약 · API 스키마 · 프론트 이벤트. **여기 적힌 건 현장에서 안 바꾼다.**
2. **`lanes/<내 레인>.md`** — 내 목표 · 30분 단위 태스크 · 완료 조건 · 건드리면 안 되는 곳
3. `docs/claude6-harness.md` (설계 정본 v1.1) · `docs/PLAN.md` (현장 할 일 메모)

## 레인

| 레인 | 담당 | 소유 |
|---|---|---|
| `front-dongwook` | 동욱 | `web/viewer/` |
| `front-minsu` | 민수 | `web/notes/` |
| `back-wooseok` | 우석 | `api/` |
| `back-kyuchan` | 규찬(팀장) | `pipeline/` `hooks/` `tools/` `prompts/` `skills/` `mock/` |

## 시작

```bash
git pull
cd ~/kirothon-board && git pull && ./setup.sh <레인> <팀토큰> ~/AWS-MOTGA
~/.kiro/skills/board/board.sh doctor ~/AWS-MOTGA
```
그다음 Kiro에 **"상황판 읽고 시작해"**.

## 이미 들어 있는 것 (다시 만들지 말 것)

- `hooks/` WritePolicy·QAStop·FrameGuard — 검증됨
- `tools/grep_wiki.py` `tools/segment_video.py` — 검증됨
- `skills/` 6개 · `prompts/` 7개 — 문구 수정만 필요 (`docs/PLAN.md` 표)
- `mock/` — 프론트가 API 없이 0분부터 출발하는 고정 픽스처
- `wiki/` 샘플 4페이지 + 필기 2건, `raw/L3/` 구간표 8개 + 프레임 — **프레임은 자리표시자**(진짜 영상 처리하면 교체)

## 규칙 두 개

- Kiro는 `git commit`/`push` 를 못 한다. "📦 커밋 제안"만 하고 **사람이 커밋한다.**
- 막히거나 계약을 바꿔야 하면 `board.sh blocked` / `board.sh human` → #orchestra 에서 팀장이 ✅/❌.
