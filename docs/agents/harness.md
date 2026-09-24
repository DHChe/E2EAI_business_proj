# Harness

작업을 여러 에이전트 세션에 걸쳐 실행할 때 쓰는 규약. 계획을 데이터로 남기고, 각 step을
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
  중단·재개·리뷰 결과와 phase 완료 때 실행기가 동기화한다. 정상 step 완료마다 댓글을 달지는 않는다.
- `ready-for-agent` 라벨이 붙은 Issue만 phase로 내려보낸다(`docs/agents/triage-labels.md`).
- 실행기는 리뷰 관문까지 진행하고 phase 완료 요약 댓글을 단다. Issue close와 병합은 사람이 한다.

## 디렉토리

```
phases/
├── index.json              ← 전체 phase 현황
└── 12-auth-flow/
    ├── index.json          ← 이 phase의 step 상태 기계
    ├── step0.md            ← 자기완결 지시서
    ├── step1.md
    └── .run/              ← 실행기 산출물(result·marker·로그 등, gitignore)
```

### `phases/index.json`

```json
{
  "phases": [
    { "dir": "12-auth-flow", "issue": 12, "status": "pending" }
  ]
}
```

`phases/index.json`은 phase 등록 뒤 실행기 소유다. `status`는 `pending` | `completed` | `error` | `blocked`. 타임스탬프(`completed_at`,
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
- 실행기가 `created_at`, `base_commit`, `review{status, end_sha, round, fixes, blocked_reason?}`를 기록한다. 생성 시 넣지 않는다. `started_at`은 기록하지 않는다.

## 상태 기계

| 상태        | 의미                                              | 세션 result 보고 → 실행기가 index에 확정 | 실행기 시각 | Issue 반영 |
| ----------- | ------------------------------------------------- | ------------ | -------------- | ----------------------- |
| `pending`   | 미실행                                            | —            | —              | blocked 재개 시 조건부 라벨 복원 |
| `completed` | AC 통과                                           | `summary`    | `completed_at` | phase 리뷰 통과 뒤 요약·리뷰 댓글; close는 사람 |
| `error`     | 시도 소진 또는 재시도할 수 없는 실패               | `error_message` | `failed_at` | 사유 댓글; 라벨 유지 |
| `blocked`   | 사람만 풀 수 있음(API 키, 외부 인증, 수동 설정)   | `blocked_reason` | `blocked_at` | `ready-for-human` |

`error`와 `blocked`를 구분하는 것이 핵심이다. `blocked`는 재시도로 절대 안 풀리므로 즉시
중단해서 3회 헛돌기를 막는다.

`summary`는 step 산출물의 한 줄 요약이고, 실행기가 다음 step 프롬프트에 누적 전달한다.
따라서 다음 step에 실제로 쓸모 있는 것(생성된 파일 경로, 핵심 설계 결정)을 담는다.

### 복구

- **step `error`/`blocked`**: 원인을 해결한 뒤 마지막 비-pending step의 `status`를 `pending`으로 바꾸고 `error_message`·`blocked_reason`·`failed_at`·`blocked_at`을 지워 재실행한다.
- **리뷰 `blocked`**: 사유를 해결한 뒤 `review.status`만 `blocked` → `pending`으로 바꾸고 `review.blocked_reason`을 지워 재실행한다. `phases/index.json`은 고치지 않는다.

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
   종료 코드로 판정되는 커맨드만 쓴다. 실행기가 줄마다 따로 실행해 검증한다.
   리뷰 기준선이 모든 step의 AC를 최종 상태에서 다시 돌리므로, 뒤 step이 뒤집을 조건
   (예: 나중에 추가될 문자열에 대한 `! grep -q`)은 AC로 쓰지 않는다.
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

## 변경 허용 경로

src/example.py
tests/example/

## Acceptance Criteria

bash 블록은 정확히 하나다. 빈 줄과 `#` 주석을 제외한 각 줄을 저장소 루트에서
`bash -o pipefail -c '<줄>'`로 따로 실행한다. 모든 줄이 종료 0이어야 한다.
줄 사이에 변수·작업 디렉토리 상태가 이어지지 않는다. `\`로 끝나는 줄, `<<`가 든 줄,
각 줄이 `bash -n`을 통과하지 못하는 여러 줄 구문은 쓰지 않는다.
AC는 반복 실행해도 되는 격리 자원(세계 격리·replay)을 쓴다.
AC·빌드·테스트가 만드는 파일은 `.gitignore` 대상이며 그 unit의 변경 허용 경로 안이어야 한다.
step AC는 phase 끝까지 참이어야 한다.

```bash
{실행 가능한 한 줄 커맨드. 종료 코드 0이면 통과.}
```

## 검증 절차

1. 위 AC 커맨드를 한 줄씩 따로 실행한다.
2. 체크리스트:
   - `CONTEXT.md` 용어집의 어휘를 썼는가?
   - `docs/adr/`의 결정을 벗어나지 않았는가?
   - `AGENTS.md`의 규칙을 위반하지 않았는가?
3. 한 시도만 하고 `phases/{dir}/.run/step{N}-result.json`에 JSON 객체 하나로 보고한다:
   - 통과 → `{"status": "completed", "summary": "산출물 한 줄 요약"}`
   - 실패 → `{"status": "error", "summary": "진행 요약", "error_message": "구체적 에러"}`
   - 사람만 해결 가능 → `{"status": "blocked", "summary": "진행 요약", "blocked_reason": "사유"}` 후 즉시 중단
   - 두 index를 쓰지 않고 커밋하지 않는다. 재시도·롤백·상태 확정은 실행기가 한다.

## 금지사항

- {X를 하지 마라. 이유: Y}
- 변경 허용 경로 밖을 고치지 마라. 이유: 실행기가 위반으로 판정한다.
- push·gh 쓰기·외부 게시·원격 DB 변경을 하지 마라. 이유: 구현 세션의 책임 밖이다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고와 허용 경로 안 새 산출물은 예외).
- 기존 테스트를 깨뜨리지 마라.
- 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
````

허용 경로 절에는 설명·목록 기호 없이 **한 줄에 경로 하나**를 적는다. 정확한 파일 경로나
`/`로 끝나는 디렉토리 접두사만 허용한다. glob 문자(`*?[`), 절대 경로, `..`,
`:`로 시작하는 pathspec magic, 정규화되지 않은 경로와 `phases/`에 겹치는 경로는 거부한다.
허용 경로와 AC는 각각 비어 있지 않은 절 하나여야 한다. result 파일은 별도 보고 계약이다.

## 실행기

저장소 루트에서 `python3 scripts/execute.py <phase_dir> [--push]`로 실행한다.
`<phase_dir>`는 `24-harness-executor` 같은 디렉토리명이다. 저장소 루트는 호출 cwd의
`git rev-parse --show-toplevel`로 찾으므로, 다른 하위 디렉토리에서 부를 때는 스크립트 경로도 맞춘다.
기획은 Claude(`/harness`), 구현은 Codex(`codex exec`), 리뷰는 Claude와 Grok이 맡는다.
사람은 기획·phase 승인, `blocked` 해소·`error` 복구, Issue close·병합을 맡는다.

### 기동과 책임

1. worktree 잠금 → Git 복원 실패 guard 확인(있으면 다른 git 호출 전 exit 1) → 신호 처리 설치 → marker 복구 → gh 대기열 재시도 → 시작 전 검사와 필요시 라벨 복원 순서다.
2. `feat-{phase}`를 먼저 checkout한다. 없으면 현재 HEAD에서 만든다. 무시되지 않은 변경은 해당 `phases/{dir}/` 안에서만 허용한다.
3. phase index의 변경은 위 복구 절의 step 재개 또는 리뷰 blocked 재개만 허용한다. 코드상 오류·시각 필드를 그대로 두는 것도 허용하지만, 복구할 때는 지운다. 두 종류의 재개를 한 diff에 합치거나 다른 필드를 바꾸지 않는다. `review.fixes`의 누락과 0은 같은 값으로 비교하며 완료한 수정 수는 사람이 바꾸지 않는다.
4. 마지막 비-pending step이 `error`면 exit 1, `blocked`면 exit 2다. `review.status=blocked`도 exit 2다. 허용된 phase 파일 변경은 prepare chore로 커밋한다.
5. 최초 실행(`created_at` 없음)이면 `created_at`·`base_commit`(prepare 커밋 전 HEAD)·기본 `review`를 기록하고 첫 시도 전에 커밋한다. 상위 index의 해당 phase가 `error`/`blocked`면 실행기가 `pending`으로 돌린다.
6. HEAD에 커밋된 모든 step 파일의 허용 경로와 AC를 검증해 고정한다. 하나라도 잘못되면 오류를 모아 exit 1이며, 구현 세션과 AC 본 실행을 시작하지 않는다. 앞선 복구·prepare는 이미 수행됐을 수 있다.
7. completed step을 건너뛰고 pending step 실행 → 리뷰 관문·수정 루프 → 선택 push 순서로 진행한다.

- 가드레일 주입 — `AGENTS.md`, `CONTEXT.md`, `docs/adr/*.md`, `docs/PRD.md`를 step 프롬프트에 포함
- 컨텍스트 누적 — 완료된 step의 `summary`, step 본문, 허용 경로, result 계약, 금지 사항을 stdin 프롬프트로 전달한다. 같은 기동의 재시도에는 직전 실패 사유도 넣는다.
- 상태 소유 — 세션은 result만 쓰고 커밋하지 않는다(샌드박스에서 `.git` 쓰기 불가). phase 등록과 명시된 수동 복구 외에 두 index는 실행기만 쓰며, 시도 중에는 실행기도 index를 쓰지 않는다.

`review` 초기값은 `{"status": "pending", "end_sha": null, "round": 0, "fixes": 0}`이다.
status는 `pending`·`passed`·`failed`·`unverifiable`·`blocked`이며, `end_sha`는 리뷰 대상 HEAD,
`round`는 리뷰 라운드 번호이고 `fixes`는 완료한 수정 수다(기존 index에 없으면 0). 수정 통과·커밋의 chore에서만 1 올리고 관문 확정(passed·수정 예산 소진 failed·unverifiable) 때 0으로 되돌린다. 수정 blocked 때만 `blocked_reason`을 더한다.
리뷰 통과 시 phase index에도 `completed_at`을 기록하고 상위 phase를 `completed`로 확정한다.
시각은 KST ISO 형식이다. `started_at`은 쓰지 않는다.

### 세션 격리와 판정

`codex exec`는 고정 argv, workspace-write 샌드박스, 네트워크 끔으로 실행한다.
코드는 번들 플러그인 중 `browser`·`unified-computer-use`·`computer-use` 세 개를 끄고,
apps·computer_use·browser_use·in_app_browser 기능도 끈다. 모든 번들 플러그인을 일괄 끄는 것은 아니다.
사용자 MCP는 서버별 `-c`로 끄고 목록을 다시 확인한다. 끄지 못하면 세션을 시작하지 않는 fail-closed preflight다.
프로젝트 `.codex/hooks.json`이 같은 `guard-bash.py`를 PreToolUse 훅으로 건다.
`--ignore-user-config`는 이 훅을 끄므로 쓰지 않는다.

세션·AC·리뷰어의 env에서 `GH_TOKEN`·`GITHUB_TOKEN`·`SSH_AUTH_SOCK`을 지우고,
`GH_CONFIG_DIR`는 빈 임시 디렉토리, `PYTHONDONTWRITEBYTECODE=1`로 둔다.
모든 자식은 `ORCA_*`·`BASH_ENV`·`ENV`도 지운다. 기존 `GIT_CONFIG_COUNT` 뒤에 `credential.helper=`를 덧붙인다. gh 호출과 push는 원래 env를 쓴다.
env의 토큰 변수 제거와 credential.helper 비우기. 파일·키체인의 자격 자체는 남는다.
세션은 unit(`step{N}` 또는 `fix{r}`)당 한 시도만 맡아 `.run/<unit>-result.json`으로 보고한다.
실행기는 시도 전에 이전 result를 지운다. 세션이 정상 종료하고 아래 조건이 모두 참이어야 통과한다.

| 판정 | 조건 |
| --- | --- |
| ① | 이번 result가 `completed`이고 비어 있지 않은 문자열 `summary`가 있다 |
| ② | HEAD가 시도 전과 같다 |
| ③ | 변경 경로가 허용 경로 안이다(두 index 수정도 위반) |
| ④ | 루트 바로 아래 `.env`·`.env.*`의 SHA-256이 같다(`.env.example` 제외, 하위 디렉토리는 보지 않음) |
| ⑤ | `git status --porcelain=v1 -z --ignored=matching`의 `!! ` 집합에서 새 항목이 없다. unit 허용 경로 안, `phases/` 아래 `.run/`, `__pycache__/`·`*.pyc`, 도구 상태 `graft/`·`.omc/`와 그 하위는 예외다 |
| ⑥ | AC 각 줄이 모두 종료 0이다 |
| ⑦ | AC 전후 HEAD와 작업 트리 tree SHA가 같다 |

④는 세션 종료 뒤와 AC 뒤 모두 검사한다. 시도·기준선 시작 때 루트 `.env`·`.env.*`(`.env.example` 제외) 중 파일·링크·특수 파일을 메모리에 보관하고(실제 디렉토리는 보관·복원하지 않고 존재만 지문에 넣어, 생기거나 사라지거나 종류가 바뀌면 `수동 복원 필요`로 확정한다) 불일치면 수정·삭제를 복원하고 새 파일은 제거한 뒤 재시도 없이 error로 확정한다. AC 뒤에는 ⑦도 검사한다. ⑤의 무시 경로 기준선은 unit 첫 시도 직전에 한 번만 잡아 marker에 보존하며 재시도·크래시 복구에서도 유지한다. 이전 버전 marker에 기준선이 없으면 재개 첫 시도 직전 값을 쓴다.
자식(세션·AC·기준선 AC·리뷰어) 시작 전에 저장소 공용 config 바이트와 hooks·info의 모든 항목(종류·바이트/링크 대상·권한)을 메모리에 보관한다. config 비교는 저장소 밖 임시 cwd에서 `git config --file <path> --null --list`의 (키, 값) 목록 중 `branch.*`를 뺀 전부로 한다. hooks·info는 링크를 따라가지 않는 내용 해시다. 차이는 다른 git 호출 전에 보관본으로 복원하고 다시 비교한다. 복원 성공 시 시도는 스냅샷·롤백 후 step/fix error와 두 index를 chore 커밋하고 marker를 지워 exit 1, 기준선은 phase error를 커밋해 exit 1이다. 복원 실패면 두 index를 쓰지 않고 기준 해시·사유를 기동 때 계산한 `--git-path harness/{phase}/git-guard.json`에 남겨 exit 1이다. 다음 기동은 잠금 직후 recover·prepare·다른 git 호출 전에 guard 파일을 확인해 멈추며, 설정을 확인·복원한 사람이 그 파일을 지운 뒤 재개한다. 전역 `~/.gitconfig`는 검사 밖이다.
자식 실행 중 SIGTERM·SIGHUP·SIGINT나 실행 예외가 발생해도 메모리 보관본을 먼저 비교·복원한다. 비교·복원 도중에 신호가 와도 비교가 끝날 때(일치, 복원 후 일치, guard 기록)까지는 대기로 남아 종료 전에 다시 비교·복원한다. 다만 SIGKILL과 정전은 프로세스가 정리 코드를 실행할 수 없으므로 이 보장을 제공하지 못한다.
④에서 심볼릭 링크인 `.env`는 링크 자체만 보관하며 대상 내용은 복원하지 않는다. 대상 지문이 바뀌면 `수동 복원 필요`로 확정한다. 새 파일 제거와 디렉토리 변경 사유에는 `.env` 역할 분담 안내(AI는 `.env.example`만, 가상환경은 `.venv`)를 덧붙인다. 사람은 값을 실행 전이나 종료 코드로 끝난 뒤에 채운다. 신호·크래시 뒤라면 재기동해 복구를 끝낸 뒤 채운다(복구는 달라진 `.env`를 error로 확정한다). Git 설정 변경으로 먼저 끝나는 시도·기준선도 이 판정을 거쳐 사유에 덧붙인다.

### 재시도·롤백·커밋

unit당 최대 3회다. 실패한 작업은 먼저 저장소 밖 임시 index로 tree와 스냅샷 커밋을 만들고
`refs/harness/<phase>/<unit>/attempt<k>-<epoch>`에 남긴다(epoch는 나노초). 이 ref는 push하지 않는다.
**스냅샷 뒤에 실행기(`scripts/execute.py`) 프로세스만** `git reset --hard <pre_sha>`와
`git clean -fd`(`-x` 없음)를 실행하고, ⑤와 같은 집합에서 기준선에 없던 허용 경로 안 항목만 지운다(파일은 unlink, 새 디렉토리는 링크를 따라가지 않고 그 아래 삭제). 기존 무시 디렉토리 안에 새로 생긴 파일은 지우지 않는다. 도구 상태 `graft/`·`.omc/`와 하위는 새로 생겨도 절대 지우지 않는다. basename이 `.env` 또는 `.env.`으로 시작하는 항목은 삭제하지 않고 stderr에 경로만 보고하며, 그것 때문에 비지 않은 디렉토리도 남긴다. 허용 경로 밖 무시 파일은 절대 지우지 않는다. 세션과 사람에게는 이 명령이 계속 금지다.
스냅샷 실패면 파괴 명령 없이 exit 1이다. reset 직전 `git symbolic-ref -q HEAD`로
`feat-{phase}`인지 확인하며, 다르면 스냅샷만 남기고 reset 없이 exit 1이다.
롤백 뒤 `git status --porcelain`이 비어 있지 않아도 exit 1이다.
`blocked` 보고는 롤백하고 그 시도를 횟수에 넣지 않으며, index 확정 뒤 exit 2다.
④ 위반은 복원·롤백 뒤 재시도 없이 `error`로 확정한다. 허용 경로 밖 ⑤ 위반도 재시도 없이 error이며 사유는 "허용 경로 밖 새 무시 경로: 수동 정리 필요"와 경로 목록이다.

성공 순서는 검증 → feat 커밋 → marker `feat_done` → index 확정 → 두 index만 chore 커밋 → marker 삭제다.
feat는 검증된 변경 경로만 literal pathspec으로 add하며 변경이 없으면 생략한다.
모든 커밋 전에 `feat-{phase}` 브랜치를 확인하고, 다르면 커밋 없이 exit 1이다.
실제 index에 `git add -A`를 쓰지 않는다. 예외는 스냅샷·AC tree 비교용 임시 index뿐이다.
prepare chore에는 허용된 phase 파일도 포함할 수 있다.

- 구현: `feat: <phase> step{N} <name> (#<issue>)`
- 리뷰 수정: `fix: <phase> 리뷰 r{r} 반영 (#<issue>)`
- 메타데이터: `chore: <phase> <상태> (#<issue>)`

### 잠금·marker·복구

`phases/.run/lock`에 flock을 건다. 같은 worktree의 두 번째 실행기는 phase가 달라도 exit 1이다.
marker는 시도 중이거나 feat와 chore 사이일 때만 존재하고, unit을 확정하는 경로는 chore 뒤 지운다.
신호·내부 실패로 중단되면 복구할 marker를 남길 수 있다.
`git rev-parse --git-path harness/{dir}/attempt.json`에 marker를 두고 필요하면 디렉토리를 만든다. 필드는 `{unit, k, pre_sha, stage, feat_sha, pgid, ignored_before, allowed, env_before, env_dirs}`다. `env_dirs: true`는 `env_before`가 `.env*` 디렉토리 존재를 담는다는 표시다. 이 표시가 없는 이전 버전 marker로 재개할 때는 현재 지문의 디렉토리 항목을 비교에서 뺀다.
Codex 샌드박스는 `.git`을 쓸 수 없다. 기존 `.run/attempt.json`은 읽지 않는다. 프롬프트 생성은 marker 기록 전이며, spawn 전 예외는 marker를 지워 시도를 소모하지 않는다.

| 기동 시 marker | 복구 |
| --- | --- |
| `running`, HEAD = `pre_sha` | 해당 pgid에 codex 프로세스가 있을 때만 남은 그룹을 죽인다. ps 실패·예외면 롤백 없이 exit 1, marker를 유지한다. ④ 해시가 marker의 `env_before`와 다르면 보관 바이트가 없으므로 롤백 뒤 재시도 없이 error를 chore 커밋하고 marker를 지운다(수동 .env 복원 필요). 같거나 이전 marker에 해시가 없으면 롤백·marker 삭제 뒤 k+1로 재개한다. 다음 번호는 메모리에만 있다 |
| `feat_done`, HEAD = `feat_sha` | unit과 completed result·summary를 검증한다. ④ 해시가 다르면 running과 같이 pre_sha로 롤백하고 error를 확정한다. 같으면 chore만 이어서 한다(step 확정 또는 fix의 review pending·fixes 증가 확정) |
| 그 밖 또는 무효 marker/result | 아무것도 건드리지 않고 marker 경로·사유를 출력하며 exit 1 |

SIGINT·SIGTERM·SIGHUP에는 자식 프로세스 그룹을 종료하고 marker를 남긴다.
재기동으로 재개한 첫 시도에는 직전 실패 사유가 전달되지 않는다.
fix 크래시 재개는 `.run/` 원문을 신뢰하지 않고 현재 HEAD에서 해당 라운드를 다시 리뷰한다. 수정 라운드와 k+1은 이어서 세며,
시도 번호를 소진했으면 수정 실패로 확정한다.

### 리뷰 관문·수정 루프

모든 step이 completed이고 `review.status`가 passed가 아니면 진입한다.
매 리뷰 전 `end_sha = HEAD`에서 전 step AC 기준선을 돌린다. 실패면 리뷰 없이 phase error, exit 1이다. ⑦이면 `end_sha`로 스냅샷·롤백한다. 기준선 AC 뒤에도 루트 `.env`와 위 Git 설정 비교·복원 규칙을 적용한다. Git 복원 성공 뒤에는 스냅샷·롤백하고 phase error를 커밋한다.
Claude와 Grok을 순차로 실행한다. Claude는 `/review <base_commit>..<end_sha>`와 계약문,
Grok은 `review.md` 본문(frontmatter 제외)의 `$ARGUMENTS`를 범위로 치환한 것과 계약문을 받는다.
계약문은 파일 변경·커밋·push·gh 쓰기·외부 게시·원격 DB 변경을 금지한다.

리뷰어 전후 브랜치·HEAD·porcelain·루트 `.env` 및 위 Git 설정 비교·복원 규칙을 적용한다. Git 설정 복원 성공이면 `[executor] Git 설정 변경 감지·복원`을 붙이고 그 리뷰어를 unverifiable로 판정한다. 이후 브랜치·HEAD·porcelain 검사와 필요한 스냅샷·롤백을 수행하고 두 index의 error/unverifiable 기록을 chore 커밋해 exit 3이다. 복원 실패는 앞 절의 guard 파일 규칙대로 두 index를 쓰지 않고 exit 1이다.
브랜치가 바뀌면 스냅샷만 남기고 되돌리지 않은 채 exit 1이다.
나머지 변경은 스냅샷 뒤 롤백하고 그 리뷰어를 `unverifiable`로 판정한다.
정상 종료와 올바른 JSON 결과(Claude `result`, Grok `text` 필드), 마지막 비어 있지 않은 줄의
`REVIEW_RESULT: passed` 또는 `REVIEW_RESULT: failed`가 필요하다.
누락·비정상 출력·실행 실패는 한 번 더 시도하고, 그래도 판정할 수 없으면 `unverifiable`이다.
원문은 반환 시 메모리에 보관해 Issue 댓글·수정 프롬프트에 쓴다. `.run/review-r{r}-{claude|grok}.txt`는 사람용 기록으로만 쓰고 되읽지 않는다. 되돌림(스냅샷 ref 포함)·판정 누락·timeout·비정상 종료 사유는 `[executor] ...`로 원문 끝과 stderr에 남기므로 댓글에도 포함된다.

둘 다 passed면 phase completed, 하나라도 unverifiable이면 수정 없이 phase error·exit 3이다.
그 밖의 failed에서만 수정 루프를 돌린다. 최대 2회 수정하며 unit은 `fix{r}`다. 남은 예산은 `MAX_FIX_ROUNDS - review.fixes`이고 `review.round`에서 추론하지 않는다. 수정 blocked를 풀고 재개하면 완료한 수정 수만 소모로 센다. spawn 전 실패와 blocked는 소모하지 않으며 이전 완료분도 지우지 않는다. 관문 확정 때 fixes를 0으로 되돌린 뒤의 새 기동만 새 예산을 받으며, fix 도중 크래시 재개나 fix 완료 뒤 pending 재개는 새 예산을 받지 않는다.
전 step 허용 경로의 합집합과 전 step AC를 쓰고 판정·3회 시도·롤백 규칙은 step과 같다.
수정 통과 → fix 커밋 → 재리뷰다. 2회 수정 뒤에도 failed거나 수정 시도를 소진하면
`review.status=failed`, phase error, exit 3이다. 수정 blocked면 review와 phase를 blocked로 확정하고 exit 2다.
Grok은 `guard-bash.py`를 실행하지 않는다. 보호는 `--deny Write --deny Edit`(Bash는 `git diff`에 필요해 막지 않지만, 스모크에서 셸 경유 파일 생성도 막혔다), 사후 HEAD·트리 검사와 되돌림, env의 토큰 변수 제거와 credential.helper 비우기, 계약문뿐이다. 파일·키체인의 자격 자체는 남는다.

### Issue·push·종료

실행 중 `gh` 쓰기는 실행기만 한다. `ready-for-agent`↔`ready-for-human` remove/add만 하며 다른 라벨은 유지한다.
blocked면 ready-for-human으로 바꾸고 사유 댓글을 단다. blocked phase를 재개할 때 여전히
ready-for-human이고 ready-for-agent가 없으면 라벨을 되돌린다.
step error·기준선 실패·최종 리뷰 실패·unverifiable에는 사유나 리뷰 원문을 댓글로 남긴다.
phase 완료에는 step 요약 댓글과 두 리뷰 댓글을 남긴다. Issue close와 병합은 사람이 한다.
실패한 gh 명령은 최대 3회 시도 뒤 `.run/gh-pending.json`에 쌓아 다음 기동의 시작 전 검사 전에 재시도한다.
phase 결과는 바꾸지 않는다. 대기열은 이 Issue의 comment와 두 라벨 사이의 edit 모양만 허용하고 나머지는 버린다. 모양이 맞는 대기열 본문의 위조는 막지 못하며 영향은 이 Issue의 댓글과 두 라벨에 한정된다.

`--push`는 기본 꺼짐이다. 리뷰 통과 뒤 `git push -u origin feat-{phase}`를 실행하며 force는 쓰지 않는다.
push 실패는 exit 1이고 phase는 completed로 남는다. 완료 phase를 `--push`로 다시 실행하면
기동 검사·step 파일 검증을 거친 뒤 구현과 리뷰를 건너뛰고 push한다.

| 종료 코드 | 의미 |
| --- | --- |
| 0 | 전 step 완료·리뷰 통과, 요청한 push도 성공 |
| 1 | error·내부 실패·push 실패 |
| 2 | blocked |
| 3 | 리뷰 실패·unverifiable(수정 시도 소진 포함) |

### timeout·산출물·한계

세션 1800초, AC 줄당 600초, 리뷰어 1800초, gh 명령당 60초다. MCP 목록 preflight는 호출당 120초다.
`phases/{dir}/.run/`에는 `<unit>-result.json`, `<unit>-last.txt`,
`<unit>-session.jsonl`, `review-r{r}-{claude|grok}.txt`, `gh-pending.json`을 둔다.
worktree 공용 `phases/.run/`에는 `lock`을 둔다. 모두 gitignore 대상이다.
기존 `step{N}-output.json`은 생성하지 않는다.

⑤ 판정과 롤백 삭제는 접힌 무시 경로 집합 하나를 공유한다. 기존 무시 디렉토리 안의 새 파일은 지우지 않는다. 새 허용 경로 안 항목만 실패·blocked 롤백에서 지우되 `.env*`와 도구 상태는 보호한다. 허용 경로 밖 새 항목은 위반을 보고하되 보존한다. 시도 중이거나 크래시 뒤 재기동 전에는 허용 경로 안에 무시 파일을 만들지 마라.
④ 대상 외 기존 무시 파일의 제자리 수정과 루트 밖 `.env` 변경은 감지하지 못한다. 무시 파일은 ⑦의 tree 비교 대상 밖이다.

참고 원본: https://github.com/jha0313/harness_framework (`scripts/execute.py`).
위 책임과 보호 규칙은 원본 구현에 없거나 잘못된 것을 고친 것이다. 원본을 그대로 복사하지 말 것.
