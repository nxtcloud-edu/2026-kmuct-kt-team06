# Lecki (MOTGA) — 강의 위키

> 2026 국민대학교 캠퍼스타운 AI VIBE CODING 해커톤(Kirothon, 2026-09-20) · 06팀 카론톤
> **데모: https://motga.193-123-163-215.sslip.io**

강의 녹음과 슬라이드 PDF를 올리면, **모든 문장에 출처가 붙은 위키**가 만들어진다.
문장 옆의 출처 칩을 누르면 **그 슬라이드와 녹음의 그 초**가 열려 재생된다.

```
"머지 소트의 점화식은 T(n) = 2T(n/2) + O(n) 이다."  ↗ L4 · 10:56
                                                     └ 누르면 슬라이드 5 + 녹음 10분 56초
```

## 왜 만들었나

대학생 96명 설문: 요약 AI를 써 본 75명 중 **64명(85%)이 요약을 읽고도 원본 녹음·슬라이드를 다시 열었다.**
이유는 교수님의 정확한 표현을 확인하려고, 요약이 틀렸을까 봐, 앞뒤 맥락이 안 보여서.
요약을 더 잘 만드는 대신 **요약과 원본 사이에 길을 놓았다.**

## 핵심 기능

| | 무엇 | 어떻게 |
|---|---|---|
| **출처 점프** | 위키·채팅 답변의 모든 문장 끝에 `[[L1#s5@t=376]]` 앵커 → 슬라이드 + 녹음의 그 초 | 앵커의 초는 코드가 확정한다. 모델은 옮겨 적기만 한다 |
| **교수님 발언 검색** | "시험"을 치면 교수님이 실제로 그 말을 한 지점이 뜬다 | 전사본 문자열 검색. LLM 호출 0회, 1~2ms |
| **위키에 묻기** | 위키 안의 근거로만 답한다. 수식은 LaTeX 로 렌더 | 근거가 없으면 모델을 부르지 않는다. 답이 **근거에 없는 출처를 인용하면 코드가 폐기**한다 |
| **검토함** | 기계가 자신 없는 것만 사람에게: 슬라이드 매칭이 애매한 구간, AI가 한 번 거부당한 페이지, 두 모델의 판단이 갈린 문단 | [원본 보기] → [승인] |
| **업로드 → 자동 컴파일** | PDF + (전사본 또는 녹음)을 올리면 단계별 진행 표시와 함께 노트가 자란다 | 강의 1편 약 30분. 전사본이 없으면 STT 부터 |
| 필기 · 숨기기 · 제목 수정 | 사람의 쓰기도 AI와 **같은 검사(훅)를 통과**하고 기록에 남는다 | 사용자는 상태·제목 줄만 바꿀 수 있다. 본문은 1바이트도 못 바꾼다 |

## AI 파이프라인

**순서는 코드가 쥐고, 모델은 두 군데서만 부른다. 모델이 파일을 쓰려는 순간마다 훅이 막아서 검사한다.**

```
업로드 → ①적재 → [입력 검사] → ②정렬 → ③컴파일 ⇄ [쓰기 훅] → ④비평 → 빌드 → 예상 질문
          코드       훅 1         코드      모델        훅 2       모델+코드   코드      모델(캐시)

질문 → 근거 문단 선택(코드) → 답변(모델) → [출력 검사: 훅 3]
```

| 단계 | 하는 일 | 파일 |
|---|---|---|
| ① 적재 | PDF → 슬라이드 PNG·쪽별 텍스트 / 전사본이 없으면 Grok STT / 슬라이드↔전사본을 **단조 제약 동적계획법**으로 맞춤(TF-IDF 점수표, 모델 0회) / 녹음을 faststart 로 재포장 | `pipeline/prep.py` `tools/align_slides.py` |
| 훅 1 입력 검사 | 구간표에 길이 0·겹침·역순이 있으면 파이프라인을 멈춘다 | `hooks/frame_guard.py` |
| ② 정렬 | 전사 문장을 구간에 붙여 **앵커의 초를 확정**. 음성 인식이 불확실한 문장은 인용 금지 표시 | `tools/build_episodic.py` |
| ③ 컴파일 | 주제마다 에이전트 루프(도구 7개, 최대 20턴). 에이전트는 주제 섹션만 쓰고 **노트 조립은 코드가** 한다 | `pipeline/orchestrator.py` |
| 훅 2 쓰기 검사 | 규칙 11개(R01~R11): 허용 폴더·경로 탈출·HTML 삽입·📄/🗣 에 앵커 필수·**앵커가 구간표에 실제로 있는 슬라이드·초인지** … 거부하면 사유를 에이전트에게 돌려주고 3회까지 재작성 | `hooks/write_page_guard.py` |
| ④ 비평 | 🗣 인용은 코드가 문자 유사도로 대조. 문단은 **서로 다른 공급자 2개**에 "이 구간에 근거가 있나 yes/no/partial" — 갈리면 8회 반복해 분포로 본다. **판정은 코드** | `pipeline/critic.py` |
| 훅 3 출력 검사 | 채팅 답변의 앵커 ⊂ 제공한 근거 문단의 앵커. 아니면 무엇이 틀렸는지 알려 1회 재생성, 그래도 아니면 폐기 | `api/qa.py` `hooks/qa_stop_guard.py` |

설계 원칙
1. **코드가 워크플로를 소유한다** — 단계 순서·재시도 횟수·임계값·승인/반려는 전부 코드.
2. **모델은 좁은 판단만** — 글쓰기와 "근거 있나 yes/no/partial". 모델에게 확신도(0~1)를 묻지 않는다. 그 숫자는 보정되지 않는다.
3. **실패가 나오면 프롬프트가 아니라 규칙을 늘리거나 코드로 옮긴다** — 당일 세 번(제목의 콜론이 사이트 빌드를 깬 것 → 훅 규칙, 에이전트가 긴 노트를 통째로 다시 쓰지 못한 것 → 코드 조립, 채팅이 출처를 지어낸 것 → 출력 검사).

음성 인식의 불확실성은 **서로 다른 두 STT 엔진의 전사 일치율**로 본다(`tools/stt_agree.py`, 모델 0회). 같은 엔진을 두 번 돌리는 것은 검증이 아니다 — 실측: 다른 엔진이 의심한 131문장 중 같은 엔진 재실행은 6개만 잡았다(같은 곳에서 똑같이 틀린다). 일치율은 "정확도"가 아니라 **사람이 먼저 볼 순서**로만 쓴다.

## 실행

Python 3.10+ (외부 패키지 없음), Node 22(위키 빌드), `poppler-utils`, `ffmpeg`.

```bash
git clone https://github.com/nxtcloud-edu/2026-kmuct-kt-team06.git && cd 2026-kmuct-kt-team06
(cd site && npm ci)                          # Quartz — 최초 1회

python3 tools/build_wiki.py --watch &        # wiki/ → public/ (변경 3초 안에 재빌드 + 뷰어 목록 재생성)
python3 -m api.server 8000                   # 화면 + /api/* 를 한 오리진에서
# → http://localhost:8000
```

- **LLM 키**: 저장소 루트의 `.env`(gitignore)에 `OPENAI_API_KEY` `ANTHROPIC_API_KEY` `GEMINI_API_KEY` `XAI_API_KEY`(STT). `pipeline/llm.py` 가 자동으로 읽고, 한 공급자가 실패하면 다음으로 넘어간다. 키가 없어도 화면·출처 점프·발언 검색·필기는 동작한다(질의응답만 "모델 호출 실패"로 응답).
- **데이터**: 저장소에는 가짜 견본 강의 L3 만 들어 있다. **실제 강의 자료와 그 산출물은 커밋하지 않는다**(`raw/L*`, `wiki/lectures`·`wiki/concepts` 실데이터, `*.local.json` 전부 gitignore).
- 강의를 넣는 법: 화면의 **＋ 강의 자료 추가**, 또는
  ```bash
  python3 -m pipeline.run L8 --title "강의 제목" --course "과목"      # raw/L8/ 에 파일을 둔 뒤
  python3 -m pipeline.run L8 --topic s5-6 --live                     # 주제 하나만
  ```
- 배포: [`docs/DEPLOY.md`](docs/DEPLOY.md). 프론트만 볼 때: 화면 왼쪽 아래 ⚙ 에서 "샘플 데이터"를 켜면 API 없이 `mock/` 으로 돈다(기본은 꺼짐).

## 기술 스택

| | |
|---|---|
| 프론트 | 바닐라 JS SPA(빌드 도구 없음) · KaTeX 로컬 번들 · `innerHTML` 0건(전사·필기·모델 출력은 전부 textContent) |
| 백엔드 | Python 표준 라이브러리만(`http.server`). 한 프로세스가 정적 파일 + API 18경로. Range 응답·경로 탈출 차단·multipart |
| 저장 | DB 없음. 마크다운 + JSON 파일이 곧 데이터, 감사 기록은 `wiki/.history.jsonl` |
| 위키 렌더 | Quartz 4 |
| STT | xAI Grok STT(단어별 시각) · 다글로 |
| LLM | OpenAI · Anthropic · Gemini 어댑터(SDK 없이 HTTP 직접), 도구 호출 통일, 공급자 폴백 |
| 문서 처리 | poppler(`pdftoppm` `pdftotext`) · ffmpeg |
| 개발 | **Kiro** 4레인(spec·steering·PreToolUse/AgentStop 훅) + 팀 상황판([kirothon-board](https://github.com/PROVE1352/kirothon-board)) + Claude Code(계획·검토·통합) |

## 당일 실측 (2026-09-20)

- 실제 강의 6편(컴퓨터구조 3 · 알고리즘 2 · 시스템소프트웨어 1) → 강의 노트 6개(주제 33개) · 개념 페이지 24개 · 앵커 615개 · 교수 인용 90개
- 첫 4편 컴파일: 쓰기 53회 중 훅 거부 7회, **7회 모두 에이전트가 사유를 받아 고쳐서 통과**, 끝내 막힘 0
- 🗣 인용 대조 23/23 · 발언 검색 1~2ms · 질의응답 3~5초 · 컴파일은 주제당 3~4분
- 슬라이드 경계 오차 중앙값 16초(표본 7개) — 자신 없는 경계는 검토함으로
- 재현 명령과 상세: [`docs/DEMO-NUMBERS.md`](docs/DEMO-NUMBERS.md)

**아직 아닌 것** — 표본이 작고 사람이 만든 정답 세트와 비교한 적은 없다. 두 강의에 걸쳐 같은 개념 페이지가 자란 사례(`sources: [L1, L2]`)는 아직 0건이다(구조만 있다). 업로드 경로는 STT 가 한 벌이라 전사 일치율이 나오지 않는다. 링커 단계(⑤)는 생략했다.

## 저장소 구조

```
api/        HTTP 서버와 경로별 모듈(qa · ingest · review · pages · notes · dashboard …)
pipeline/   prep(적재) · orchestrator(컴파일 루프) · critic(비평) · llm(공급자 어댑터) · run(진입점)
hooks/      write_page_guard · frame_guard · qa_stop_guard
tools/      align_slides · build_episodic · stt_grok · stt_agree · quote_search · build_wiki · build_library
            build_suggestions · merge_lecture_notes · coverage · hook_metrics
prompts/ skills/   에이전트 시스템 프롬프트와 스킬(필요할 때 읽는 절차서)
web/        viewer(뷰어·업로드·휴지통) · notes(필기·대시보드·채팅·서식) · vendor/katex
wiki/ raw/  데이터(견본 L3 만 커밋)      mock/  API 없이 화면을 띄우는 고정 응답
site/       Quartz                      lanes/ .kiro/  레인별 작업 지시와 Kiro spec·steering
```

## 문서

| | |
|---|---|
| [`docs/AS-BUILT-0920.md`](docs/AS-BUILT-0920.md) | **실제로 만들어진 것** — 설계와 달라진 곳, 당일 터진 것과 고친 것 |
| [`docs/API-frontend.md`](docs/API-frontend.md) | API 경로·요청·응답·오류 코드 |
| [`CONTRACT.md`](CONTRACT.md) | 레인 간 계약: 앵커 규약, API 스키마, 프론트 이벤트 |
| [`docs/PRD.md`](docs/PRD.md) · [`docs/SPEC.md`](docs/SPEC.md) · [`docs/DESIGN.md`](docs/DESIGN.md) | 문제 정의·기능 명세·화면 설계 |
| [`docs/claude6-harness.md`](docs/claude6-harness.md) | 에이전트 하네스 설계(훅·쓰기 정책·신뢰 경계) |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) · [`docs/DEMO-NUMBERS.md`](docs/DEMO-NUMBERS.md) | 배포 절차 · 발표 숫자와 재현 명령 |

## 팀

| 레인 | 담당 | 영역 |
|---|---|---|
| `back-kyuchan` | 경규찬(팀장) | `pipeline/` `hooks/` `tools/` `prompts/` `skills/` · 통합·배포 |
| `back-wooseok` | 우석 | `api/` |
| `front-dongwook` · `front-minsu` | 동욱 · 민수 | `web/viewer/` `web/notes/` |

개발 중 규칙: Kiro 는 `git commit`/`push` 를 하지 못한다(PreToolUse 훅으로 차단) — 커밋 제안만 하고 사람이 커밋한다. 레인 밖 결정은 상황판의 `human` 요청으로 올려 팀장이 승인한다. 제품의 훅 설계와 같은 원칙이다.
