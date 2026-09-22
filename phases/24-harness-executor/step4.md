# Step 4: attempt-loop

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 상태 기계(`:66-84`), 7원칙 5번 "AC는 실행 가능한 커맨드"(`:96-97`), 실행기 책임(`:143-160`), 특히 "AC 직접 실행"과 "재시도 전 롤백"
- `.gitignore` — 무시 규칙. 시도 판정에서 새 무시 경로를 감지할 때 기준이 된다
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `StepSpec`, `path_allowed(path, allowed)`
  - `Executor.head()`, `changed_paths()`, `child_env(*, strip_orca=False)`, `git(...)`
  - `Executor.run_child(...) -> ChildResult(returncode, timed_out, stdout, stderr)`
  - `Executor.build_prompt(unit, task_text, allowed, failure=None)`, `run_codex(unit, prompt, *, on_spawn=None)`, `result_path(unit)`
  - `Executor.worktree_tree(base_sha)`, `rollback(unit, k, target_sha)`
  - `Executor.save_marker(marker)`, `marker`(메모리 값), `resume`
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `step_md`, `fake_bin`, `calls`, `make_executor`, 기본 덫

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. 지금까지 뼈대(step 0), step 파일 파싱(step 1), Codex 세션 실행(step 2), 스냅샷·롤백·marker·복구(step 3)가 있다.

이 step은 unit 하나(step 또는 리뷰 수정 라운드)의 **시도 루프**를 만든다. 세션은 시도 하나만 하고 result 파일로 보고한다. 재시도는 실행기가 소유한다. 실행기는 세션의 자기신고를 믿지 않고 직접 판정한다. 판정의 핵심은 AC를 직접 실행하는 것이다.

시도 중에는 실행기도 index를 쓰지 않는다. 그러므로 시도 중 index 변경은 곧 세션의 조작이고 위반이다.

## 작업

### 모듈 수준

- `MAX_ATTEMPTS = 3`
- `@dataclass class AttemptOutcome` — 필드는 넷이다.
  - `status: str`: `completed` | `error` | `blocked`
  - `summary: str | None = None`, `reason: str | None = None`
  - `attempts: int = 0`: 계수한 시도 수. `blocked` 시도는 세지 않는다
  - `pre_sha: str = ""`: 통과한 시도의 시작 HEAD

### 판정 재료

- `Executor.env_fingerprint() -> dict[str, str]`
  - **저장소 루트 바로 아래**에서 이름이 `.env`이거나 `.env.`로 시작하는 파일의 이름과 sha256이다. `.env.example`은 뺀다.
  - 하위 디렉토리로 재귀하지 않는다. 중첩된 worktree나 큰 무시 디렉토리를 훑지 않기 위해서다.
  - 파일이 새로 생기거나 사라져도 지문이 달라진다.
- `Executor.ignored_paths() -> set[str]` — `git status --porcelain=v1 -z --ignored=matching`에서 `!!` 항목의 경로 집합이다.
- `Executor.read_result(unit: str) -> dict | None` — `result_path(unit)`를 읽는다. 없거나, JSON이 아니거나, 객체가 아니거나, `status`가 셋 중 하나가 아니면 None이다.
- `Executor.__init__`에 `self.ac_timeout = 600`(줄당 초)을 더한다.

### AC 실행

- `Executor.run_ac(lines: Sequence[str]) -> str | None` — 통과면 None이고, 실패면 사유 문자열이다.
  1. 실행 전 `head()`와 `worktree_tree(head)`를 기록한다.
  2. **줄마다 따로** `bash -o pipefail -c <줄>`로 실행한다. cwd는 `root`, env는 `child_env()`, timeout은 `self.ac_timeout`이다. `run_child`를 쓰므로 새 세션으로 뜨고 timeout 때 그룹이 kill된다.
  3. 모든 줄이 종료 0이어야 한다. 실패한 줄은 줄 원문, 종료 코드(또는 timeout), 출력 끝부분(stdout+stderr 마지막 약 2000자)을 사유에 담는다.
  4. 실행 후 HEAD와 작업 트리 tree sha가 실행 전과 같아야 한다. 다르면 "AC가 작업 트리를 바꿨다"는 사유로 실패다. AC가 만드는 파일은 `.gitignore` 대상이어야 한다는 뜻이다.
  - 여러 줄을 이어 붙이거나 `bash -e` 스크립트로 돌리지 않는다. `bash -e`는 `false && true`의 실패를 삼킨다.

### 시도 루프

- `Executor.attempt_unit(unit: str, task_text: str, allowed: Sequence[str], ac: Sequence[str], *, start_k: int = 1) -> AttemptOutcome`
- k = `start_k`부터 `MAX_ATTEMPTS`까지 시도마다 아래를 한다.
  1. **준비**
     - `changed_paths()`가 비어 있어야 한다. 아니면 `HarnessExit(1)`이다(시도 전 작업 트리가 더럽다).
     - `pre_sha = head()`
     - 이 unit의 result 파일을 **지운다.** 이전 시도나 이전 실행의 result를 이번 결과로 오인하지 않기 위해서다.
     - `env_before = env_fingerprint()`, `ignored_before = ignored_paths()`
     - `save_marker({"unit": unit, "k": k, "pre_sha": pre_sha, "stage": "running", "feat_sha": None, "pgid": None})`
  2. **세션**
     - `prompt = build_prompt(unit, task_text, allowed, failure=<직전 실패 사유 또는 None>)`
     - `run_codex(unit, prompt, on_spawn=<marker의 pgid를 기록하고 save_marker하는 함수>)`
     - `on_spawn`이 불리기 전에(preflight 실패 등) `run_codex`가 `HarnessExit`를 던지면, 세션은 뜨지 않았고 작업 트리도 그대로다. `clear_marker()`를 부른 뒤 그 예외를 다시 던진다. 환경 문제가 시도 횟수를 먹지 않게 하기 위해서다.
     - 세션이 끝나면 **곧바로** `save_marker(self.marker)`로 메모리 값을 파일에 다시 쓴다. `.run/`은 세션이 쓸 수 있는 곳이므로 세션이 marker 파일을 바꿨을 수 있다. 실행기는 메모리 값만 믿는다.
  3. **판정.** 아래 순서로 본다. 먼저 걸리는 것이 사유다.
     - ④ `.env` 지문이 `env_before`와 다르다: `rollback(unit, k, pre_sha)` 뒤 **재시도 없이** `AttemptOutcome("error", reason=..., attempts=k)`를 돌려준다. 무시 파일은 롤백으로 되돌릴 수 없어서다.
     - 세션이 timeout이거나 종료 코드가 0이 아니다: 실패한 시도.
     - result가 없거나 무효다(`read_result`가 None): 실패한 시도.
     - result `status`가 `blocked`다: `rollback(unit, k, pre_sha)` 뒤 `AttemptOutcome("blocked", reason=<blocked_reason>, attempts=k-1)`을 돌려준다. **시도 횟수에 넣지 않고** 루프를 끝낸다.
     - result `status`가 `error`다: 실패한 시도. 사유는 `error_message`다.
     - ① `status`가 `completed`인데 `summary`가 비었다: 실패한 시도.
     - ② HEAD ≠ `pre_sha`다(세션이 커밋했다): 실패한 시도.
     - ③ `changed_paths()`에 `path_allowed`를 통과하지 못하는 경로가 있다: 실패한 시도. rename은 양쪽 경로를 다 본다. 허용 경로는 `phases/`와 겹칠 수 없으므로(step 1 검증), 세션의 index 수정은 여기서 걸린다.
     - ⑤ `ignored_paths() - ignored_before`에 예외 밖 경로가 있다: 실패한 시도. 예외는 `phases/` 아래 `.run/` 경로, `__pycache__` 성분을 가진 경로, `.pyc`로 끝나는 경로다.
     - ⑥⑦ `run_ac(ac)`가 사유를 돌려준다: 실패한 시도.
     - 모두 통과: `AttemptOutcome("completed", summary=..., attempts=k, pre_sha=pre_sha)`를 돌려준다. 롤백하지 않는다. marker도 `stage=running` 그대로 둔다. 커밋은 step 5가 한다.
  4. **실패한 시도:** `rollback(unit, k, pre_sha)`. 사유(판정 항목 이름과 AC 출력 끝부분)를 다음 시도의 `failure`로 넘긴다.
- `MAX_ATTEMPTS`번 모두 실패하면 `AttemptOutcome("error", reason=<마지막 사유>, attempts=MAX_ATTEMPTS)`를 돌려준다. `start_k`가 이미 `MAX_ATTEMPTS`를 넘으면 세션 없이 곧바로 error다(사유: 재개 시 시도 소진).
- 시도 번호 k는 marker에만 둔다. **시도 중에는 index를 쓰지 않는다.**
- **marker 불변식:** marker는 시도가 진행 중이거나, feat 커밋과 chore 커밋 사이일 때만 존재한다.
  - `attempt_unit`이 completed·error·blocked를 돌려줄 때 marker(`stage=running`)는 남아 있다.
  - 호출자(step 5·8)가 그 unit의 chore 커밋 **뒤에** `clear_marker()`를 부른다.
  - `start_k`가 이미 `MAX_ATTEMPTS`를 넘어 세션 없이 error를 돌려줄 때도 호출자가 chore 뒤에 `clear_marker()`를 부른다.
- 이 step은 루프만 만든다. 결과를 커밋하거나 index에 확정하는 일, `run()`에 연결하는 일은 step 5가 한다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 가짜 `codex`는 시나리오 환경변수와 호출 횟수(임시 파일 카운터)에 따라 파일을 바꾸고 result를 쓴다. result 경로는 argv의 `-o` 값(`.run/{unit}-last.txt`)이나 프롬프트에서 얻는다. 시도 루프는 `attempt_unit`을 직접 불러 검증한다. 이전 step 테스트는 계속 통과해야 한다.

가짜 codex 규약(step 0 테스트 기반과 같다): 가짜 codex는 `mcp list --json` 호출에 `[]`를 내고 종료 0이다. 아래의 "codex 호출 N회"는 모두 `exec` 호출만 센 수다.

테스트 저장소는 `make_repo` 뒤 `feat-7-sample` 브랜치로 옮겨 둔다. 다른 브랜치에서는 롤백이 브랜치 확인에서 멈춘다(step 3).

- `test_stale_result_deleted` — 시도 전에 이전 `completed` result 파일이 남아 있고 가짜 codex가 아무것도 쓰지 않으면, 그 시도는 실패("result 없음")로 판정되고 completed가 되지 않는다.
- `test_ac_and_list_failure_fails` — AC에 `false && true` 줄이나 `false | true` 줄이 있으면 세션이 completed를 써도 시도가 실패한다.
- `test_change_outside_allowed_fails` — 세션이 허용 경로 밖 추적 파일(예: `AGENTS.md`)을 고치고 completed를 쓰면 실패하고, 그 파일이 롤백으로 원래대로 돌아온다.
- `test_session_index_edit_fails` — 세션이 `phases/7-sample/index.json`을 고치면 실패하고, index가 원래대로 돌아온다.
- `test_ac_tree_change_fails` — AC 줄이 무시되지 않는 파일을 만들면(예: `touch src/new.txt`) 종료 코드가 0이어도 시도가 실패한다.
- `test_env_change_errors_without_retry` — 세션이 `.env`를 바꾸면 결과가 `error`이고 codex 호출이 1회뿐이다. 사유에 `.env`가 있다.
- `test_new_ignored_outside_run_fails` — 세션이 새 무시 파일 `build.log`를 만들면 실패다. `.run/` 아래나 `__pycache__/`·`*.pyc`만 새로 생기면 통과한다.
- `test_blocked_rolls_back_uncounted` — 1회차 error, 2회차 blocked면 결과가 `blocked`이고 `attempts == 1`이다. 작업 트리는 깨끗하고 2회차 스냅샷 ref가 있으며 codex 호출은 2회다.
- `test_third_failure_error` — 세 번 모두 실패하면 결과가 `error`, `attempts == 3`, codex 호출 3회, 스냅샷 ref 3개이고 작업 트리가 깨끗하다.
- `test_retry_prompt_has_reason` — 1회차 AC가 고유 문자열(예: `MARKER-42`)을 출력하며 실패하면, 2회차 세션 stdin 프롬프트에 그 문자열과 실패한 판정 항목이 들어 있다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_stale_result_deleted
python3 scripts/test_execute.py -k test_ac_and_list_failure_fails
python3 scripts/test_execute.py -k test_change_outside_allowed_fails
python3 scripts/test_execute.py -k test_session_index_edit_fails
python3 scripts/test_execute.py -k test_ac_tree_change_fails
python3 scripts/test_execute.py -k test_env_change_errors_without_retry
python3 scripts/test_execute.py -k test_new_ignored_outside_run_fails
python3 scripts/test_execute.py -k test_blocked_rolls_back_uncounted
python3 scripts/test_execute.py -k test_third_failure_error
python3 scripts/test_execute.py -k test_retry_prompt_has_reason
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 시도 중에 index를 쓰는 코드가 없는가? 실패한 시도는 전부 롤백되는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step4-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 세션의 `completed` 신고만 보고 통과시키지 마라. 이유: 실행기는 자기신고를 믿지 않는다. 판정 항목 전부와 AC 직접 실행이 통과 조건이다.
- 시도 중(세션 시작부터 판정 끝까지)에 index를 쓰지 마라. 이유: 시도 중 index 변경을 세션의 조작으로 판정하려면 실행기도 쓰지 않아야 한다.
- `.env` 변경을 재시도하지 마라. 이유: 무시 파일은 롤백으로 되돌릴 수 없다. 사람이 봐야 한다.
- 이전 result 파일을 지우지 않고 시도를 시작하지 마라. 이유: 이전 `completed`를 이번 결과로 오인한다.
- AC 줄을 `bash -e`로 묶어 돌리지 마라. 이유: `false && true`의 실패를 삼킨다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 셸에서 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(feat·chore 커밋, index 확정, 복구 ②, Issue 반영, 리뷰)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
