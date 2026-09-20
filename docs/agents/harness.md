# Harness

작업을 여러 Claude 세션에 걸쳐 실행할 때 쓰는 규약. 계획을 데이터로 남기고, 각 step을
독립 세션에서 그대로 실행 가능한 자기완결 지시서로 만든다.

워크플로우 진입점은 `/harness`, 검수는 `/review`다.

## 작업 단위: Issue와 phase

| 층   | 저장소                            | 담는 것                         | 독자     |
| ---- | --------------------------------- | ------------------------------- | -------- |
| WHAT | GitHub Issue                      | 스펙, 논의, triage 라벨, 승인   | 사람     |
| HOW  | `phases/{이슈번호}-{slug}/`       | step 지시서, 실행 상태          | 에이전트 |

- **Issue 하나가 phase 하나로 내려온다.** 디렉토리명은 `{이슈번호}-{kebab-slug}` (예: `12-auth-flow`).
- Issue 본문 맨 아래에 `Phase: phases/12-auth-flow/` 한 줄을 남겨 양방향으로 찾을 수 있게 한다.
- **상태의 단일 출처는 `phases/{dir}/index.json`이다.** Issue 라벨은 사람이 읽는 요약이고,
  phase 경계에서만 동기화한다. step이 끝날 때마다 Issue를 건드리지 않는다.
- `ready-for-agent` 라벨이 붙은 Issue만 phase로 내려보낸다(`docs/agents/triage-labels.md`).
- phase 완료 시 `gh issue close <n> --comment "<phase 요약>"`.

## 디렉토리

```
phases/
├── index.json              ← 전체 phase 현황
└── 12-auth-flow/
    ├── index.json          ← 이 phase의 step 상태 기계
    ├── step0.md            ← 자기완결 지시서
    ├── step1.md
    └── step{N}-output.json ← 실행기가 남기는 원시 로그 (gitignore)
```

### `phases/index.json`

```json
{
  "phases": [
    { "dir": "12-auth-flow", "issue": 12, "status": "pending" }
  ]
}
```

`status`는 `pending` | `completed` | `error` | `blocked`. 타임스탬프(`completed_at`,
`failed_at`, `blocked_at`)는 실행기가 상태 전이 시 자동 기록한다. 손으로 넣지 않는다.

### `phases/{dir}/index.json`

```json
{
  "project": "<프로젝트명>",
  "phase": "12-auth-flow",
  "issue": 12,
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" },
    { "step": 1, "name": "core-types", "status": "pending" }
  ]
}
```

- `steps[].step`: 0부터 시작하는 순번.
- `steps[].name`: kebab-case slug. 해당 step의 핵심 모듈을 한두 단어로.
- `steps[].status`: 생성 시 전부 `"pending"`.
- `created_at`, `started_at`은 실행기가 기록한다. 손으로 넣지 않는다.

## 상태 기계

| 상태        | 의미                                              | 세션이 기록  | 실행기가 기록  | Issue 라벨 동기화       |
| ----------- | ------------------------------------------------- | ------------ | -------------- | ----------------------- |
| `pending`   | 미실행                                            | —            | `started_at`   | —                       |
| `completed` | AC 통과                                           | `summary`    | `completed_at` | phase 전부 완료 시 close |
| `error`     | 3회 시도 후에도 AC 실패. 재시도로 풀 수 있음      | `error_message` | `failed_at` | —                       |
| `blocked`   | 사람만 풀 수 있음(API 키, 외부 인증, 수동 설정)   | `blocked_reason` | `blocked_at` | `needs-info` 또는 `ready-for-human` |

`error`와 `blocked`를 구분하는 것이 핵심이다. `blocked`는 재시도로 절대 안 풀리므로 즉시
중단해서 3회 헛돌기를 막는다.

`summary`는 step 산출물의 한 줄 요약이고, 실행기가 다음 step 프롬프트에 누적 전달한다.
따라서 다음 step에 실제로 쓸모 있는 것(생성된 파일 경로, 핵심 설계 결정)을 담는다.

### 복구

- **`error`**: 원인을 고친 뒤 `status`를 `"pending"`으로 되돌리고 `error_message`를 지우고 재실행.
- **`blocked`**: `blocked_reason`의 사유를 해결한 뒤 같은 방식으로 재실행.

## Step 설계 7원칙

1. **Scope 최소화** — 한 step은 한 레이어 또는 한 모듈만 다룬다. 여러 모듈을 동시에
   고쳐야 하면 step을 쪼갠다.
2. **자기완결성** — 각 step 파일은 **독립된 세션**에서 실행된다. "앞서 논의한 대로" 같은
   외부 참조는 금지. 필요한 정보는 전부 파일 안에 적는다.
3. **사전 준비 강제** — 읽어야 할 문서 경로와 이전 step이 만든 파일 경로를 명시한다.
   세션이 코드를 읽고 맥락을 잡은 뒤 작업하게 만든다.
4. **시그니처 수준 지시** — 함수/타입의 인터페이스만 제시하고 내부 구현은 맡긴다. 단
   설계 의도에서 벗어나면 안 되는 것(멱등성, 보안, 데이터 무결성)은 명시적으로 박는다.
5. **AC는 실행 가능한 커맨드** — "동작해야 한다" 같은 서술 금지. 셸에서 그대로 돌아가고
   종료 코드로 판정되는 커맨드만 쓴다. 실행기가 이 블록을 직접 실행해 검증한다.
6. **금지사항은 구체적으로** — "조심해라" 대신 `X를 하지 마라. 이유: Y` 형식.
7. **네이밍** — step name은 kebab-case slug.

## `step{N}.md` 템플릿

````markdown
# Step {N}: {이름}

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `/CONTEXT.md`
- `/docs/adr/` 중 이 작업과 관련된 ADR
- `/AGENTS.md`
- {이전 step이 생성/수정한 파일 경로}

## 작업

{구체적인 구현 지시. 파일 경로와 시그니처 포함. 구현체는 맡기되 핵심 규칙은 박아넣는다.}

## Acceptance Criteria

```bash
{실행 가능한 커맨드. 종료 코드 0이면 통과.}
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 체크리스트:
   - `CONTEXT.md` 용어집의 어휘를 썼는가?
   - `docs/adr/`의 결정을 벗어나지 않았는가?
   - `AGENTS.md`의 규칙을 위반하지 않았는가?
3. `phases/{dir}/index.json`의 해당 step을 갱신한다:
   - 통과 → `"status": "completed"` + `"summary": "산출물 한 줄 요약"`
   - 3회 시도 후에도 실패 → `"status": "error"` + `"error_message": "<구체적 에러>"`
   - 사람 개입 필요 → `"status": "blocked"` + `"blocked_reason": "<사유>"` 후 즉시 중단

## 금지사항

- {X를 하지 마라. 이유: Y}
- 기존 테스트를 깨뜨리지 마라.
````

## 실행기

`scripts/execute.py`는 **기술 스택 확정 후** 도입한다. 그때까지 phase는 손으로 실행한다.

실행기가 책임질 것(도입 시점에 이 목록을 AC로 쓴다):

- `feat-{phase}` 브랜치 생성/checkout
- 가드레일 주입 — `AGENTS.md`, `CONTEXT.md`, `docs/adr/*.md`, `docs/PRD.md`를 step 프롬프트에 포함
- 컨텍스트 누적 — 완료된 step의 `summary`를 다음 프롬프트에 전달
- **AC 직접 실행** — `step{N}.md`의 AC 블록을 실행기가 직접 돌려서 세션의 `completed`
  선언을 검증한다. 실패하면 기각한다. 세션의 자기신고를 그대로 믿지 않는다.
- **재시도 전 롤백** — 실패한 시도의 부분 편집을 마지막 커밋으로 되돌린 뒤 재시도한다.
  안 그러면 3회 누적된 쓰레기 위에서 작업하게 된다.
- 2단계 커밋 — 코드(`feat`)와 메타데이터(`chore`)를 분리 커밋
- 커밋 범위는 경로 화이트리스트로 제한한다. `git add -A`를 쓰지 않는다.

포팅 기준 구현: https://github.com/jha0313/harness_framework (`scripts/execute.py`).
위 6개 항목은 그 구현에 없거나 잘못된 것을 고친 것이다. 그대로 복사하지 말 것.
