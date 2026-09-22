# Step 6: issue-sync

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약. Issue는 `gh` CLI로 다룬다
- `CONTEXT.md` — 용어집
- `docs/agents/issue-tracker.md` — `gh issue comment`, `gh issue edit --add-label/--remove-label` 사용법
- `docs/agents/triage-labels.md` — 라벨 문자열 `ready-for-agent`, `ready-for-human`
- `docs/agents/harness.md` — Issue와 phase의 관계(`:8-20`), 상태 기계(`:66-84`)
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `Executor.issue`, `run_dir`, `root`
  - `write_json_atomic`, `read_json`
  - `Executor.prepare() -> str | None`: 이 phase의 top status를 `error`/`blocked`에서 `pending`으로 되돌렸으면 이전 값을 돌려준다
  - `Executor.confirm_step(step, status, text)`, `run_steps(specs)`
  - `Executor.run()`: 현재 잠금 → 신호 처리기 → 복구 → 시작 전 검사 → spec 검증 → step 루프
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `fake_bin`, `calls`, `make_executor`, 기본 덫(가짜 `gh`는 기본으로 종료 97)

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. step 5까지 step을 시도하고 결과를 커밋으로 확정하는 흐름이 생겼다.

이 step은 결과를 GitHub Issue에 반영한다. 원칙은 다섯이다.
- 상태의 단일 출처는 index다. Issue 라벨은 사람이 읽는 요약이다.
- `gh`는 실행기만 쓴다. 대상 번호는 phase index의 `issue`다.
- `gh` 실패는 phase 결과(index, 종료 코드)를 바꾸지 않는다.
- 라벨은 `ready-for-agent`와 `ready-for-human` 사이의 remove/add만 한다. 다른 라벨은 그대로 둔다.
- close와 병합은 사람이 한다.

## 작업

### `gh` 래퍼

- `GH_ATTEMPTS = 3` (모듈 상수), `Executor.__init__`에 `self.gh_timeout = 60`(초)을 더한다.
- `Executor.gh(*args: str) -> bool` — `["gh", *args]`를 실행한다.
  - env는 **원래 env**(`os.environ` 복사본)다. `child_env`를 쓰지 않는다. `gh` 래퍼만 자격 증명을 쓴다. cwd는 `root`다.
  - 명령마다 timeout은 `self.gh_timeout`이다. timeout이나 0이 아닌 종료는 실패다. 최대 `GH_ATTEMPTS`번(첫 시도 포함) 시도하고, 시도 사이 대기는 1초 이하다.
  - 끝내 실패하면 그 argv 전체(`"gh"`로 시작하는 리스트)를 `run_dir/gh-pending.json`에 **덧붙이고**, 실패를 stderr에 출력하고, False를 돌려준다. `gh-pending.json`은 argv 리스트의 JSON 배열이고 `write_json_atomic`처럼 원자적으로 쓴다. `run_dir`가 없으면 만든다.
  - 예외를 던지지 않는다. 성공하면 True다.
- `Executor.retry_gh_pending() -> None`
  - `run_dir`(`.run/`)은 세션이 쓸 수 있는 곳이다. 그래서 대기열 내용을 믿지 않는다. 실행기가 만드는 **두 모양만** 실행한다. `<issue>`는 `str(self.issue)`와 정확히 같아야 한다.
    - `["gh", "issue", "comment", <issue>, "--body", <문자열>]`
    - `["gh", "issue", "edit", <issue>, "--remove-label", a, "--add-label", b]`. 단 `{a, b}` = `{"ready-for-agent", "ready-for-human"}`
  - 이 두 모양이 아닌 항목(다른 명령, 다른 Issue 번호, 다른 라벨, 문자열이 아닌 원소, 리스트가 아닌 값)은 실행하지 않는다. 대기열에서 빼고 경고를 stderr에 출력한다. 파일이 JSON 배열이 아니면 전부 버리고 경고한다.
  - 허용된 argv를 순서대로 같은 방식(최대 `GH_ATTEMPTS`번)으로 다시 실행한다.
  - 성공한 것은 빼고 실패한 것만 남긴다. 다 성공하면 파일을 지운다. 다시 실패한 argv가 대기열에 중복으로 쌓이면 안 된다.

### Issue 동작

- `Executor.issue_comment(body: str) -> None` — `gh issue comment <issue> --body <body>`. 본문이 60000자를 넘으면 잘라서 끝에 잘림 표시를 단다.
- `Executor.issue_blocked(reason: str) -> None`
  - `gh issue edit <issue> --remove-label ready-for-agent --add-label ready-for-human`
  - 이어서 사유를 담은 `issue_comment`.
- `Executor.issue_resume() -> None` — blocked에서 재개할 때 부른다.
  - `gh issue view <issue> --json labels`로 현재 라벨을 읽는다. 원래 env이고 timeout은 `self.gh_timeout`이다.
  - `ready-for-human`이 **여전히** 있고 `ready-for-agent`가 없을 때만 `gh issue edit <issue> --remove-label ready-for-human --add-label ready-for-agent`를 `gh()`로 실행한다. 사람이 라벨을 이미 바꿨으면 아무것도 하지 않는다.
  - `view`가 실패하면 조건을 확인할 수 없으므로 복원을 건너뛰고 경고만 출력한다. 이 조건부 동작은 대기열에 넣지 않는다.

### 연결

- `run()`의 기동 순서: 잠금 → 신호 처리기 → 복구 → **`retry_gh_pending()`** → `prepare()` → spec 검증 → step 루프. 대기열 재시도는 반드시 시작 전 검사 **전**이다. 시작 전 검사가 exit 1·2로 멈춰도 대기열은 처리된다.
- `prepare()`가 `"blocked"`를 돌려주면(사람이 blocked를 풀고 재개했으면) 곧바로 `issue_resume()`을 부른다.
- step 확정과 연결한다.
  - blocked: `confirm_step(N, "blocked", reason)`의 chore 커밋 **뒤에** `issue_blocked(reason)`을 부른다. 그다음 `HarnessExit(2)`다.
  - error: chore 커밋 뒤에 step 번호와 `error_message`를 담은 `issue_comment`를 단다. 그다음 `HarnessExit(1)`이다.
- 리뷰 결과 댓글(리뷰 실패, 판정 불가, phase 완료)은 step 7·8이 이 메서드들로 단다.
- 어떤 `gh` 실패도 index, 커밋, 종료 코드를 바꾸지 않는다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 가짜 `gh`는 argv를 기록하고, 시나리오 환경변수에 따라 성공·실패하거나 `issue view --json labels`에 정해진 JSON(예: `{"labels": [{"name": "ready-for-human"}, {"name": "bug"}]}`)을 낸다. 가짜 codex 규약은 step 0 테스트 기반과 같다(`mcp list --json`에 `[]`, 호출 수는 `exec`만 센다). 이전 step 테스트는 계속 통과해야 한다.

- `test_blocked_swaps_labels_and_comments` — step이 blocked로 확정되면 `issue edit 7 --remove-label ready-for-agent --add-label ready-for-human`이 정확히 한 번 불리고, 사유가 담긴 `issue comment 7 --body ...`가 불린다. 어떤 호출에도 다른 라벨 인자(`--label`, 다른 라벨 이름)가 없다.
- `test_resume_restores_label_if_still_human` — 라벨이 `ready-for-human`과 `bug`면 `issue_resume()`이 human을 빼고 agent를 넣는다. 라벨이 `ready-for-agent`거나 `needs-info`뿐이면 `edit`를 부르지 않는다.
- `test_gh_failure_saved_and_retried` — `gh`가 계속 실패하면 명령마다 3번 시도한 뒤 argv가 `gh-pending.json`에 남는다. 다음 `run()`에서 `gh`가 성공하면 시작 전 검사가 exit 2로 멈추는 상황에서도 그 argv가 다시 실행되고 대기열이 빈다. 대기열에 끼워 넣은 다른 argv(예: `["gh", "issue", "close", "7"]`, 다른 Issue 번호의 comment, `ready-for-agent`/`ready-for-human`이 아닌 라벨의 edit)는 호출되지 않고 대기열에서 빠진다.
- `test_gh_partial_success` — 대기열에 argv가 둘이고 하나만 성공하면, 대기열에는 실패한 하나만 남는다(중복 없음).
- `test_gh_failure_keeps_phase_result` — blocked 처리 중 `gh`가 모두 실패해도 `run()`은 2이고 index는 blocked다. error 처리 중 실패해도 `run()`은 1이다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_blocked_swaps_labels_and_comments
python3 scripts/test_execute.py -k test_resume_restores_label_if_still_human
python3 scripts/test_execute.py -k test_gh_failure_saved_and_retried
python3 scripts/test_execute.py -k test_gh_partial_success
python3 scripts/test_execute.py -k test_gh_failure_keeps_phase_result
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 라벨 조작이 `ready-for-agent`와 `ready-for-human`의 remove/add뿐인가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step6-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- `gh issue close`를 부르거나 PR을 병합하는 코드를 만들지 마라. 이유: close와 병합은 사람이 한다.
- `gh issue edit --label`처럼 라벨 집합을 통째로 바꾸거나 다른 라벨을 건드리지 마라. 이유: 사람이 붙인 라벨을 지운다. remove/add는 두 라벨 사이에서만 한다.
- `gh` 실패로 index, 커밋, 종료 코드를 바꾸지 마라. 이유: Issue는 요약일 뿐이고 상태의 단일 출처는 index다.
- `gh-pending.json`의 항목을 모양 검사 없이 실행하지 마라. 이유: `.run/`은 세션이 쓸 수 있고, 대기열은 원래 env(자격 증명)로 실행된다. 검사하지 않으면 세션이 실행기의 자격 증명으로 임의의 `gh` 명령을 돌릴 수 있다.
- `gh` 밖의 자식 프로세스(세션·AC·리뷰어)에 원래 env를 주지 마라. 이유: 자격 증명은 `gh` 래퍼에만 필요하다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다. 이 저장소의 실제 Issue #24에 댓글이나 라벨이 붙으면 안 된다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 셸에서 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(리뷰 관문, 리뷰 댓글, 수정 루프, push)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
