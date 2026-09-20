---
name: link-index
description: ⑤ 링커·인덱스 에이전트 전용. approved 페이지들 사이에 [[링크]]를 걸고 wiki/index.md를 갱신할 때 사용. 페이지 간 연결, 중복 개념 병합 판단, 인덱스 누락 확인 작업이면 이 스킬을 따른다.
---

먼저 wiki-anchor 스킬을 읽는다.

# 역할
페이지 본문은 건드리지 않는다. 프론트매터 `links:` 필드와 `wiki/index.md`만 쓴다.

# 절차
1. `read_page("wiki/index.md")`와 approved 페이지들을 읽는다.
2. 페이지 A의 Current에서 페이지 B의 제목/개념이 언급되면 A의 `links:`에 B를 추가한다. 양방향으로.
3. 같은 개념이 두 페이지로 갈라져 있으면 병합하지 말고 `wiki/TAXONOMY.md`에 `- 중복 후보: A, B — 이유` 한 줄을 append한다. 병합은 사람이 결정한다.
4. index.md에 모든 approved 페이지가 있는지 확인하고 없는 것을 추가한다. 형식: `- [[slug]] — 제목 (sources: L1, L3)`

# 금지
- Current/History 수정
- 새 concepts 페이지 생성
- grey 페이지를 index에 올리기

# 출력
추가한 링크 수, index 추가 수, TAXONOMY 메모 수를 한 줄로.
