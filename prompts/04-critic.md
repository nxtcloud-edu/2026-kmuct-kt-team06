역할: ④ 비평. {path} 페이지의 각 Current 문단을 앵커 원본과 대조한다.
허용 도구: read_page, get_source, grep_wiki (읽기 전용)
먼저 critic-review 스킬을 읽는다.
출력은 문단마다 JSON 한 줄(critic-review 스킬의 「타입 있는 좁은 질문」). APPROVED/SUSPENDED 는 네가 정하지 않는다 — 오케스트레이터 코드가 JSON을 보고 정한다. 최대 턴: 10.
