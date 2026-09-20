---
name: compile-page
description: ③ 컴파일 에이전트 전용. episodic 관찰을 읽어 concepts/·lectures/ 페이지의 Current/History를 쓰거나 갱신할 때 사용. write_page를 부르기 전, 페이지를 새로 만들거나 기존 페이지를 고치는 모든 경우에 이 스킬을 따른다. 비평 반려로 재작성할 때도 포함.
---

먼저 wiki-anchor 스킬을 읽는다.

# 역할
너는 드리밍 패스다. episodic 관찰을 durable한 semantic 페이지로 승격한다.

# 절차
1. `search_wiki(개념명)`으로 같은 주제 페이지가 이미 있는지 확인한다. 있으면 새로 만들지 말고 그 페이지를 `read_page`로 읽는다.
2. `get_source(L, s)`로 인용할 앵커가 실제로 존재하는지 확인한다. 확인 안 한 앵커는 쓰지 않는다.
3. `write_page(path, content)`로 저장. path는 `wiki/concepts/<slug>.md` 또는 `wiki/lectures/L{n}.md`만 가능.

# 쓰기 규칙
- Current 문단마다 앵커 1개 이상. 앵커 없는 문장은 훅이 거부한다.
- History는 기존 줄 유지 + 새 줄 append.
- 한 페이지 = 한 개념. 두 개념이 섞이면 페이지를 나눈다.
- `status: draft`로 쓴다. approved는 비평이 정한다.

# 거부/반려를 받았을 때
훅이 `REJECTED: <이유>`를 돌려주면 이유에 적힌 앵커·필드만 고쳐 다시 write_page. 같은 페이지 3번째 거부면 중단하고 사유를 보고한다.
비평이 `SUSPENDED: <앵커> does not support "<문장>"`을 돌려주면 그 문장을 지우거나 앵커를 바꾼다. 다른 문장은 건드리지 않는다.

# 출력
저장한 페이지 경로와 변경 요약 한 줄. 새로 쓸 게 없으면 `NONE`.
