# Tasks — back-kyuchan
- [ ] 0. (시작 전) EC2: Node ≥22 · `cd site && npm ci` · `npx quartz build -d ../wiki -o ../public --watch`(tmux) · 키·`DEMO_TOKEN` 환경변수 · 실제 `raw/L1` 은 scp · 팀원 IP `board.sh allow` · 레인 4개 `board.sh order`
- [ ] 1. (T1 앞 20분) `pipeline/llm.py` — R1.  한 공급자만 되어도 **먼저 공유**(우석 T4 가 기다린다)
- [ ] 2. (T1~T2) `pipeline/tools.py` + `orchestrator.py` 뼈대: 주제 하나를 ③으로 돌려 훅까지 — R2.  완료: `wiki/.history.jsonl` 에 deny→allow 한 에피소드
- [ ] 3. (T3) 강의 1편 주제 3개 이상 컴파일 → Quartz 화면에 뜨는지 · `--live` 옵션
- [ ] 4. (T4) 🔴 통합 점검(코딩보다 우선) — R5
- [ ] 5. (T4~T5) `critic.py`(2모델 불일치 + 인용 대조) — R3 · 검토함 재료 확인
- [ ] 6. (T5) 발표 숫자 모으기: `python3 tools/hook_metrics.py` · 인용 대조 M/N · 경계 오차 · 설문 85%
- [ ] 7. (T6) `board.sh hold all` · 리허설 2회 · 데모 녹화 백업
