# Requirements — back-kyuchan (파이프라인 · 훅 · 통합)
기능명세 F-06 · F-07 · F-08 · F-12 · F-14 · F-15 · F-16 — `docs/SPEC.md`. 단계·도구 표는 `hooks/registry.md`.

## R1 LLM 어댑터 — 우석이 기다린다, 가장 먼저
- THE SYSTEM SHALL `pipeline/llm.py` 에 `complete(role, system, messages, tools=None) -> {text, tool_calls, model}` 하나를 두고, `LLM_PROVIDER`(openai|anthropic|gemini) · `LLM_STRONG` · `LLM_FAST` 환경변수로 공급자를 바꾼다.
- IF 공급자가 429 또는 5xx 를 주면 THEN THE SYSTEM SHALL 다음 공급자로 1회 폴백하고 실제 쓴 모델을 결과에 적는다.

## R2 오케스트레이터 (F-08)
- THE SYSTEM SHALL 단계 순서를 코드로 고정한다: ①적재(FrameGuard) → ②`build_episodic` → ③컴파일 → ④비평 → ⑤링커(코드).
- WHEN ③이 `write_page` 를 부르면 THE SYSTEM SHALL `hooks/write_page_guard.py` 에 `agent`·`attempt`·`run` 을 실어 판정받고, allow 일 때만 파일을 쓴다.
- IF 훅이 거부하면 THEN THE SYSTEM SHALL 거부 사유를 모델에 돌려주고 같은 페이지를 최대 3회까지 다시 쓰게 한다.
- IF 3회 모두 거부되면 THEN THE SYSTEM SHALL 그 주제를 건너뛰고 다음 주제로 간다(파이프라인은 멈추지 않는다).
- THE SYSTEM SHALL 에이전트별 허용 툴 Set 밖의 툴콜을 실행하지 않는다(AgentGuard, `hooks/registry.md`).
- THE SYSTEM SHALL `--topic s5-6 --live` 로 주제 하나만 돌릴 수 있다(발표 중 라이브 30초).

## R3 비평 (F-12)
- THE SYSTEM SHALL 문단·인용마다 `{supported, quote_faithful, from_untrusted, evidence}` JSON 을 서로 다른 모델 2개에 1회씩 묻고, 답이 갈리면 8회 표본을 뽑는다.
- THE SYSTEM SHALL 판정을 코드로 한다: `no` 하나라도 → 그 문단 재작성 · `partial`/불일치 → 검토함 · 2회 실패 → `status: grey`.
- THE SYSTEM SHALL 🗣 인용과 앵커 구간 전사본의 문자 유사도를 코드로 계산해 "🗣 N개 중 M개 통과"를 남긴다.

## R4 데이터 준비 (F-07 ✅ · F-14)
- THE SYSTEM SHALL 데모 강의마다 `raw/L{n}/` 에 `segments.json`(FrameGuard allow) · `transcript.json`(+`agree`) · `slides/s{n}.png` 를 둔다.
- THE SYSTEM SHALL 실제 강의 자료와 그 산출물을 커밋 대상에 넣지 않는다.

## R5 통합
- WHEN 1:30 이 되면 THE TEAM SHALL 세 레인의 `USE_MOCK=false` 를 동시에 전환하고, 계약 어긋남은 **고칠 쪽을 팀장이 한 곳만** 정한다.
- WHEN 2:30 이 되면 THE TEAM SHALL `board.sh hold all` 후 새 기능을 넣지 않는다.
