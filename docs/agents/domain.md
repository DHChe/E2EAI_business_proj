# Domain Docs

엔지니어링 스킬이 코드베이스를 탐색할 때 이 저장소의 도메인 문서를 어떻게 읽어야 하는지 정한다.

## 탐색하기 전에 읽을 것

- 저장소 루트의 **`CONTEXT.md`**, 또는
- 저장소 루트에 **`CONTEXT-MAP.md`**가 있으면 그 파일. 컨텍스트별 `CONTEXT.md`를 하나씩 가리킨다. 주제와 관련된 것을 모두 읽는다.
- **`docs/adr/`**: 작업하려는 영역을 다루는 ADR을 읽는다. multi-context 저장소에서는 컨텍스트 범위의 결정이 담긴 `src/<context>/docs/adr/`도 확인한다.

이 파일들이 없으면 **조용히 진행한다**. 없다고 지적하지 말고, 미리 만들자고 제안하지도 않는다. `/domain-modeling` 스킬(`/grill-with-docs`와 `/improve-codebase-architecture`를 통해 호출됨)이 용어나 결정이 실제로 확정될 때 만든다.

## 파일 구조

Single-context 저장소(대부분의 저장소):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context 저장소(루트에 `CONTEXT-MAP.md`가 있는 경우):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 시스템 전체 결정
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 컨텍스트별 결정
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

이 저장소는 **single-context**다.

## 용어집의 어휘를 사용한다

출력에서 도메인 개념을 지칭할 때(이슈 제목, 리팩터링 제안, 가설, 테스트 이름)는 `CONTEXT.md`에 정의된 용어를 쓴다. 용어집이 명시적으로 피하는 동의어로 흘러가지 않는다.

필요한 개념이 아직 용어집에 없다면 그것이 신호다. 프로젝트가 쓰지 않는 말을 만들어내고 있거나(다시 생각한다), 실제로 빈틈이 있는 것이다(`/domain-modeling`에 넘길 메모로 남긴다).

## ADR 충돌을 표시한다

출력이 기존 ADR과 모순되면 조용히 덮어쓰지 말고 명시적으로 드러낸다:

> _ADR-0007(event-sourced orders)과 모순되지만, 다시 논의할 가치가 있다. 이유는…_
