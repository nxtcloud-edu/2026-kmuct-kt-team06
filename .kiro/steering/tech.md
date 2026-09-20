---
inclusion: always
---
# 기술 규칙

- **프론트(우리 코드)**: 빌드 없는 순수 JS/CSS. npm 패키지·프레임워크·번들러 금지. 위키 화면은 Quartz 5(`site/`)가 그리고, 우리 JS는 서버가 `</body>` 앞에 주입한다.
  - Quartz는 SPA: 초기화는 **파일 끝 `init()` 1회 + `document.addEventListener('nav', init)`**. `init` 은 여러 번 불려도 안전하게.
  - Quartz는 페이지 이동 때 `<body>` 자식·속성을 갈아엎는다 → 우리 UI 뿌리는 **`<html>` 아래 `#v-root`**, 상태 클래스도 `<html>` 에.
  - 사용자·모델이 쓴 글은 `textContent` 로만. `innerHTML` 금지.
  - `site/quartz/**` 소스 수정 금지. 바꿀 수 있는 건 `site/quartz.config.yaml`.
- **백엔드**: Python 3 표준 라이브러리 우선. 새 패키지 설치 금지. 정적 서빙·Range 는 `tools/devserve.py` 의 `resolve()`·`send_bytes()`·`inject()` 를 import 해서 쓴다(직접 `open()` 하면 `.env` 가 샌다).
- **쓰기 경로는 하나**: `wiki/` 에 쓰는 모든 것(에이전트·필기·승인)은 `hooks/write_page_guard.py` 를 통과한다. 훅을 우회하는 쓰기 코드를 만들지 않는다. 훅을 재구현하지 않는다 — 호출한다.
- **비밀**: 키는 환경변수로만(`X_AI`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TRANSCRIPT_API_KEY`, `DEMO_TOKEN`). 코드·로그·응답·커밋에 넣지 않는다.
- **공개 저장소**: 실제 강의 자료(`raw/L*` — L3 견본 제외), 거기서 나온 `wiki/` 산출물, `private/`, `*.xlsx`, `.env` 는 커밋 대상이 아니다.
- **git**: `git commit`·`git push`·`gh pr` 금지. 끝나면 "📦 커밋 제안"(스테이징 목록 + 제목)만 출력한다. 사람이 커밋한다.
- 실행: `cd site && npm ci && npx quartz build -d ../wiki -o ../public` → `python3 tools/devserve.py 8000`
