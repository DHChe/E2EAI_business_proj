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
3. `phases/{이슈번호}-{slug}/step{N}.md` — step마다 하나. 각 파일에 `## 변경 허용 경로` 절을 둔다.

승인된 phase 파일(두 index와 `step*.md`)을 **한 chore 커밋으로 커밋한다.**
실행기는 HEAD에 커밋된 step 파일만 읽는다. 생성 이후 두 index는 실행기가 관리한다.

그런 다음 Issue 본문 맨 아래에 `Phase: phases/{이슈번호}-{slug}/` 한 줄을 추가한다
(`gh issue edit`). Issue 번호가 없는 작업이면 먼저 Issue를 만들 것을 제안한다.

**타임스탬프 필드(`created_at`, `completed_at`, `failed_at`, `blocked_at`)는
넣지 않는다. 실행기가 기록한다.** `base_commit`과 `review`도 실행기가 초기화한다.
`started_at`은 생성하지 않으며 실행기도 기록하지 않는다.

## E. 실행

저장소 루트에서 `python3 scripts/execute.py <phase_dir>`로 실행한다(`--push`는 선택).
구현은 Codex, 리뷰는 Claude·Grok이며 재시도·롤백·커밋·Issue 결과 반영은 실행기가 맡는다.

| 종료 코드 | 사람이 할 일 |
| --- | --- |
| 0 | 완료 요약과 리뷰 결과를 확인하고 Issue close와 병합을 한다 |
| 1 | 원인을 고치고 `docs/agents/harness.md` 복구 절차에 따라 해당 error step을 pending으로 되돌려 재실행한다. 내부 실패는 marker 진단을 확인한다. 리뷰 기준선 실패는 AC 원인을 해결하며, push만 실패했다면 completed를 유지하고 `--push`로 재실행한다 |
| 2 | blocked 사유를 해결하고 복구 절차에 따라 step 또는 `review.status`를 pending으로 되돌려 재실행한다 |
| 3 | `.run/review-r*` 원문에서 리뷰 실패·unverifiable 사유를 확인하고 해결한 뒤 재실행한다 |

수동 재개 때는 phase index의 해당 오류 필드·시각만 복구 절차대로 지운다.
`phases/index.json`은 사람이 고치지 않는다. close와 병합은 실행기가 하지 않는다.

손 실행은 실행기가 없거나 쓸 수 없을 때만 한다(예: 실행기 자체를 만드는 phase).
이 경우 상태 기록과 커밋은 구현 세션 밖의 사람이 맡는다:

1. `feat-{phase}` 브랜치를 만든다.
2. step 파일을 순서대로 하나씩, 가급적 별도 세션에서 실행한다. 세션은 한 시도와 result 보고만 한다.
3. 각 step이 끝나면 **AC 각 줄을 `bash -o pipefail -c '<줄>'`로 따로 직접 실행**해 모두 종료 0임을 확인한 뒤에만 사람이 index의 status를 completed로 확정한다. AC 없이 completed를 쓰지 않는다.
4. blocked가 나오면 즉시 멈추고 사용자에게 사유를 보고한다. 재시도하지 않는다.

손 실행으로도 phase 전체가 끝나면 `/review`를 돌린다. 통과 후 Issue close와 병합은 사람이 한다.
