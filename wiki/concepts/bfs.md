---
title: 너비 우선 탐색 (BFS)
type: concept
sources: [L3]
status: approved
links: [dfs, graph-representation]
updated: 2026-09-20T09:00:00
---

## Current

BFS는 큐를 써서 시작 정점에서 가까운 정점부터 차례로 방문한다. [[L3#s5@t=330]]

인접 리스트로 구현하면 모든 정점과 간선을 한 번씩 보므로 시간복잡도는 O(V+E)다. [[L3#s5@t=338]] [[L3#s3@t=250]]

간선 가중치가 모두 같은 그래프에서 BFS가 찾은 경로는 최단경로다. [[L3#s6@t=400]]

## History

- 교수는 BFS를 "물결이 퍼지는 것"에 비유했다. [[L3#s5@t=320]]
- 방문 표시는 큐에 넣을 때 하지, 꺼낼 때 하면 중복이 생긴다고 강조했다. [[L3#s6@t=372]]
