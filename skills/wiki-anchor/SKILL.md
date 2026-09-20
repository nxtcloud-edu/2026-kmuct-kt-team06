---
name: wiki-anchor
description: 강의 위키의 앵커 규약과 페이지 포맷. 위키 페이지를 읽거나 쓰거나 검증할 때, 슬라이드·타임스탬프를 인용할 때, 프론트매터나 Current/History 섹션을 다룰 때 반드시 먼저 읽는다. 다른 모든 위키 스킬의 공통 규약.
---

# 앵커 규약

형식: `[[L{강의}#s{슬라이드}@t={초}]]`
- 예: `[[L3#s12@t=340]]` = 3강 12번 슬라이드, 영상 340초 지점
- 세 요소 모두 필수. `@t`는 정수 초. 범위가 필요하면 `@t=340-372`.
- 앵커는 반드시 `get_source(L, s)`로 존재를 확인한 뒤 쓴다. 추측 금지.

# 페이지 포맷 (semantic 페이지: wiki/concepts/, wiki/lectures/)

```markdown
---
title: <제목>
type: concept | lecture
sources: [L1, L3]        # 근거가 나온 강의 번호
status: draft | approved | grey
updated: YYYY-MM-DD
links: [[다른-페이지]], ...
---

## Current
지금 우리가 믿는 내용. 한 문단 = 한 주장. 각 문단 끝에 앵커 1개 이상.

## History
- YYYY-MM-DD 앵커 [[L3#s12@t=340]] — 이 앵커가 뒷받침하는 주장 한 줄
```

규칙
- Current의 모든 문장은 History의 어떤 줄에 대응돼야 한다.
- History는 append-only. 기존 줄을 지우지 않는다.
- 한 개념 = 한 페이지. 같은 개념이 다른 강의에도 나오면 새 페이지 대신 History에 앵커를 추가한다.

# episodic 페이지 (wiki/episodic/L{n}.md)

강의별 원시 관찰. 시간순 append-only.
```markdown
## s12 @t=340
문단 텍스트 요약 또는 원문. 앵커 [[L3#s12@t=340]]
```
