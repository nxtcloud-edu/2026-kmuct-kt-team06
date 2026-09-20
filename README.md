# AWS-MOTGA — 강의 위키 (카론톤 / Kirothon 2026-09-20)

2026년 국민대학교 캠퍼스타운 키로톤 06팀 MOTGA 레포지토리입니다.

전사본 + 슬라이드/판서 프레임 + 영상이 **앵커로 묶인 위키**로 쌓인다.
위키 문장을 클릭하면 그 말이 나온 프레임과 영상의 그 초로 점프하고, 영상은 구간 끝에서 멈춰 그 자리에서 필기를 받는다.

## 프론트엔드 실행 방법

**Python 3.10 이상**이 필요합니다. 화면 실행에는 Node.js 설치, 별도 Python 패키지 설치, Quartz 빌드가 필요하지 않습니다.

저장소를 처음 내려받는 경우:

```bash
git clone --branch feature/week2-brainstorm https://github.com/nxtcloud-edu/2026-kmuct-kt-team06.git
cd 2026-kmuct-kt-team06
```

저장소 루트에서 개발 서버를 실행합니다:

```bash
python web/viewer/serve.py 8000
```

- 접속: **http://localhost:8000**
- macOS/Linux에서 `python` 명령이 없으면 `python3`를 사용합니다.
- Windows에서 `python` 명령이 없으면 `py web/viewer/serve.py 8000`으로 실행합니다.
- 8000번 포트를 사용 중이면 마지막 숫자를 `8001` 등으로 변경하고 같은 포트로 접속합니다.
- 서버를 종료하려면 실행한 터미널에서 `Ctrl+C`를 누릅니다.

서버 시작 시 `wiki/lectures/`와 `wiki/concepts/`의 마크다운을 읽어 프론트엔드의 `web/viewer/library.json`을 갱신합니다. 위키 파일을 수정했다면 서버를 다시 시작하고 브라우저를 새로고침합니다.

### 화면 사용 방법

1. 왼쪽 라이브러리에서 강의 또는 개념 노트를 선택합니다. `Ctrl/Cmd+K`로 제목과 본문을 검색할 수 있습니다.
2. 본문의 시간 칩을 누르거나 문장을 선택한 뒤 **원본 보기**를 눌러 해당 프레임과 필기를 엽니다.
3. **강의 자료 추가**에서 영상·음성·PDF·TXT·MD 파일을 선택하거나 끌어다 놓고 제목을 입력해 로컬 노트를 만듭니다.
4. **대시보드**에서 근거 커버리지, 검증 기록, 검토할 문장을 확인합니다.
5. 오른쪽 **Agent**에서 위키 질문 또는 교수님 발언 검색을 사용합니다. `Enter`는 전송, `Shift+Enter`는 줄바꿈입니다.

### 샘플 모드와 실제 API

- 기본 화면은 저장소의 `mock/` 데이터를 사용하는 **샘플 모드**입니다. 샘플 QA는 BFS 관련 질문에 고정 응답을 제공합니다.
- 필기, 검토 상태, 가져온 텍스트는 현재 브라우저의 `localStorage`에 저장됩니다. 영상·PDF 파일은 현재 탭에서만 열 수 있으며 새로고침 후 다시 선택해야 합니다.
- 자료 추가는 브라우저에서 파일을 읽는 기능입니다. 실제 AI 전사·요약 생성이나 서버 업로드를 수행하지 않습니다.
- 샘플 강의 영상은 포함되어 있지 않아 원본 칩은 샘플 프레임을 표시합니다.
- 실제 API를 사용하려면 `CONTRACT.md`의 `/api` 경로를 제공하는 서버를 같은 오리진에 연결하고, 왼쪽 하단 프로필 설정에서 **샘플 데이터 모드**를 끕니다. 현재 개발 서버는 API를 구현하지 않습니다.

### 브라우저 테스트

테스트에는 **Node.js 18 이상과 Google Chrome**이 필요합니다. 위 개발 서버를 8000번 포트로 실행한 상태에서 별도 터미널을 엽니다.

```bash
cd web/viewer/tests
npm install
npm test
```

Windows PowerShell에서 실행 정책 때문에 `npm`이 차단되면 `npm.cmd install`, `npm.cmd test`를 사용합니다.

- `smoke.cjs`: 화면 이동, 검색, 원본 이동, 필기 저장, 파일 추가, QA, 검토 승인, 모바일 화면 검증
- `api.cjs`: 테스트용 API 응답 및 실제 WAV 재생으로 구간 정지·재개, 401/422/500 오류 처리 검증
- 스크린샷: `web/viewer/tests/desktop.png`, `dashboard.png`, `mobile.png`

실제 백엔드 통합 테스트와는 구분됩니다. 상세 구현과 제한 사항은 [프론트엔드 README](web/viewer/README.md)를 참고하세요.

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
