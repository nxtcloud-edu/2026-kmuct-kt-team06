# 시스템 프롬프트

에이전트별 시스템 프롬프트 = `common.md` + 해당 에이전트 파일.
스킬은 본문을 통째로 넣지 말고 `<skills_instructions>`에 name: path 인덱스만 주입하고 read_file로 읽게 한다(Aside 방식, 토큰 절약).
