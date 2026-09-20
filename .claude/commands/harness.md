---
description: Issue를 자기완결 step 지시서로 내려 phase를 설계한다
---

`docs/agents/harness.md`의 규약에 따라 작업을 진행하라. 아래 순서를 지킨다.

## A. 탐색

읽는다:

- `/CONTEXT.md` (또는 `/CONTEXT-MAP.md`) — 도메인 용어집. 없으면 조용히 넘어간다.
- `/docs/adr/` — 작업 영역을 다루는 ADR
- `/docs/PRD.md` — 제품 범위와 MVP 제외 사항
- `/AGENTS.md` — 저장소 규약

대상 Issue가 있으면 `gh issue view <n> --comments`로 스펙과 논의를 전부 읽는다.

넓은 탐색이 필요하면 Explore 에이전트를 병렬로 쓴다.

## B. 논의

구체화하거나 기술적으로 결정해야 할 것이 있으면 **먼저 사용자에게 제시한다.** 혼자 고르고
넘어가지 않는다. 해석이 여러 가지면 전부 내놓는다.

결정이 아키텍처에 영향을 주면 `docs/adr/`에 ADR로 남길 것을 제안한다. 기존 ADR과 모순되면
조용히 덮지 말고 명시적으로 드러낸다.

## C. Step 설계

사용자가 계획 작성을 지시하면 `docs/agents/harness.md`의 **Step 설계 7원칙**에 따라
초안을 작성해 피드백을 요청한다. 특히:

- 각 step은 독립 세션에서 실행된다. 외부 참조 금지.
- AC는 셸에서 그대로 돌고 종료 코드로 판정되는 커맨드여야 한다.
- 금지사항은 `X를 하지 마라. 이유: Y` 형식으로.

## D. 파일 생성

사용자가 승인하면 생성한다. 스키마는 `docs/agents/harness.md`를 따른다.

1. `phases/index.json` — 없으면 만들고, 있으면 `phases` 배열에 항목 추가
2. `phases/{이슈번호}-{slug}/index.json` — step 상태 기계
3. `phases/{이슈번호}-{slug}/step{N}.md` — step마다 하나

그런 다음 Issue 본문 맨 아래에 `Phase: phases/{이슈번호}-{slug}/` 한 줄을 추가한다
(`gh issue edit`). Issue 번호가 없는 작업이면 먼저 Issue를 만들 것을 제안한다.

**타임스탬프 필드(`created_at`, `started_at`, `completed_at`, `failed_at`, `blocked_at`)는
넣지 않는다. 실행기가 기록한다.**

## E. 실행

기술 스택 확정 전까지 `scripts/execute.py`는 없다. phase를 손으로 실행한다:

1. `feat-{phase}` 브랜치를 만든다.
2. step 파일을 순서대로 하나씩, 가급적 별도 세션에서 실행한다.
3. 각 step이 끝나면 **AC 커맨드를 직접 돌려서** 통과를 확인한 뒤에만
   `index.json`의 status를 `completed`로 바꾼다. AC를 안 돌리고 completed를 쓰지 않는다.
4. `blocked`가 나오면 즉시 멈추고 사용자에게 사유를 보고한다. 재시도하지 않는다.
5. phase 전체가 끝나면 `/review`를 돌리고, 통과하면
   `gh issue close <n> --comment "<phase 요약>"`.
