# Step 3: rollback

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — Bash 안전 가드. 세션과 사람에게 `git reset --hard`, `git clean -f`는 금지다. 이 step은 **실행기 프로세스만** 쓰는 예외를 만든다
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 실행기 책임(`:143-160`), 특히 "재시도 전 롤백"
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `EXIT_ERROR`
  - `Executor` 속성 `root`, `phase_dir`, `run_dir`, `child_pgid`
  - `Executor.git(...)`, `head()`, `changed_paths()`, `acquire_lock()`, `prepare()`, `load_step_specs()`, `run()`
  - `write_json_atomic`, `read_json`
  - `Executor.run_child(argv, *, env, timeout, stdin_text=None, stdout_path=None, on_spawn=None) -> ChildResult`
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `fake_bin`, `calls`, `make_executor`, 기본 덫

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. 지금까지 뼈대(step 0), step 파일 파싱(step 1), Codex 세션 실행(step 2)이 있다.

실패한 시도의 부분 편집은 다음 시도 전에 되돌려야 한다. 안 그러면 3회 누적된 쓰레기 위에서 작업하게 된다. 다만 되돌리기 전에 그 편집을 **반드시 스냅샷으로 남긴다.** 스냅샷이 실패하면 파괴 명령은 절대 실행하지 않는다.

실행기가 도중에 죽을 수도 있다. 그래서 시도 상태를 marker 파일에 남기고, 다음 기동 때 그것을 보고 복구한다. marker와 일치하지 않는 상황이면 아무것도 건드리지 않고 멈춘다.

## 작업

### 작업 트리 밖 임시 index

- `Executor.worktree_tree(base_sha: str) -> str` — 현재 작업 트리(무시 파일 제외)의 tree sha를 실제 index를 건드리지 않고 계산한다.
  1. `tempfile.mkdtemp()`로 **저장소 밖** 임시 디렉토리를 만든다. 그 디렉토리가 `root` 안이면 `HarnessExit(1)`이다(TMPDIR이 저장소 안을 가리키는 경우).
  2. 그 안의 **아직 없는** 파일 경로를 임시 index로 쓴다. 빈 파일을 미리 만들면 git이 손상된 index로 본다.
  3. env에 `GIT_INDEX_FILE=<임시 index>`를 더해 차례로 실행한다: `git read-tree <base_sha>` → `git add -A` → `git write-tree`.
  4. 끝나면(성공이든 실패든) 임시 디렉토리를 지운다.
  - 이 임시 index에 대한 `add -A`는 "실제 index에 `git add -A` 금지" 규칙의 **유일한 명시적 예외**다. 실제 index를 건드리지 않고, 무시 파일은 여기서도 빠진다.

### 스냅샷과 롤백

- `Executor.snapshot(unit: str, k: int, base_sha: str) -> str` — 작업 트리 상태를 커밋 객체로 남기고 ref 이름을 돌려준다.
  1. `tree = worktree_tree(base_sha)`
  2. `git commit-tree <tree> -p <base_sha> -m "harness snapshot {phase_dir} {unit} attempt{k}"`
  3. `git update-ref refs/harness/{phase_dir}/{unit}/attempt{k}-{epoch} <commit> ""`. 끝의 빈 old 값은 "없을 때만 만든다"는 뜻이다. 덮어쓰지 않는다. `epoch`는 `time.time_ns()` 정수다.
  - push하지 않는다. 어느 단계든 실패하면 `HarnessExit(1)`이다.
- `Executor.rollback(unit: str, k: int, target_sha: str) -> str` — 반환값은 스냅샷 ref다.
  1. `ref = snapshot(unit, k, target_sha)`. 여기서 실패하면 **파괴 명령을 하나도 실행하지 않고** `HarnessExit(1)`이다.
  2. **브랜치 확인:** 스냅샷 뒤, reset 직전에 `git symbolic-ref -q HEAD`가 `refs/heads/feat-{phase_dir}`인지 본다. 아니면(다른 브랜치, detached HEAD 포함) 스냅샷만 남기고 reset·clean 없이 `HarnessExit(1)`이다. 다른 브랜치에서 `reset --hard`를 하면 그 브랜치 ref가 `target_sha`로 옮겨진다.
  3. 여기까지 통과한 뒤에만 `git reset --hard <target_sha>`, 이어서 `git clean -fd`를 실행한다. `-x`는 주지 않는다. 무시 파일은 롤백 범위 밖이다.
  4. 사후 조건: `git status --porcelain`이 비어 있지 않으면 `HarnessExit(1)`이다. 예를 들어 `git clean -fd`는 안에 `.git`이 있는 중첩 저장소 디렉토리를 지우지 않는다.
  - `reset --hard`와 `clean`은 이 두 메서드 안에서, 실행기 프로세스만 실행한다. 세션과 사람에게는 여전히 금지다.

### marker

- `Executor.marker_path` (property) — `run_dir/attempt.json`.
- marker 내용: `{"unit": str, "k": int, "pre_sha": str, "stage": "running" | "feat_done", "feat_sha": str | null, "pgid": int | null}`
- `Executor.save_marker(marker: dict) -> None` — `run_dir`가 없으면 만들고, `self.marker`에 둔 뒤 `write_json_atomic`으로 쓴다. 실행 중에는 **메모리 값(`self.marker`)을 기준으로** 다시 쓴다. 파일을 다시 읽지 않는다.
- `Executor.load_marker() -> dict | None` — 파일이 없으면 None. 기동 때(복구)만 읽는다.
- `Executor.clear_marker() -> None` — 파일을 지우고 `self.marker = None`으로 둔다. 파일이 이미 없으면 아무것도 하지 않는다.
- **marker 불변식:** marker는 시도가 진행 중이거나, feat 커밋과 chore 커밋 사이일 때만 존재한다.
  - 파괴 명령과 커밋 전에 기록한다.
  - unit을 끝내는 모든 경로(completed·error·blocked 확정, 시도 소진, 재개 버림)는 그 unit의 chore 커밋 **뒤에** `clear_marker()`를 부른다. 뒤 step이 이 규칙을 따른다.
  - 복구 ①은 롤백이 끝나면 곧바로 marker를 지운다(아래).
- `Executor.__init__`에 `self.marker = None`, `self.resume = None`을 더한다.

### 기동 시 복구

- `Executor.recover() -> None` — marker가 없으면 아무것도 하지 않는다. 있으면 아래 셋 중 하나다.
  - ① `stage == "running"`이고 HEAD == `pre_sha`:
    1. 남은 세션 프로세스를 죽인다. 단, 그 pgid 그룹이 **codex 세션일 때만** 죽인다.
       - `ps -A -o pid=,pgid=,command=`로 전체 프로세스를 읽는다. `-A`가 필요하다. 새 세션으로 떠서 터미널이 없는 그룹은 `-A` 없이 보이지 않는다.
       - pgid가 marker의 `pgid`와 같은 프로세스 가운데, 명령줄을 공백으로 나눈 토큰 중 basename이 `codex` 또는 `codex.js`인 것이 하나라도 있어야 한다. 그때만 `os.killpg(pgid, SIGKILL)`한다.
       - 그런 프로세스가 없거나, `ps`가 실패하거나, pgid가 None·1 이하·`os.getpgrp()`면 kill하지 않는다. `killpg`의 `ProcessLookupError`와 `PermissionError`는 무시한다.
       - 이 규칙은 죽은 세션의 pgid를 다른 무관한 프로세스 그룹이 재사용했을 때 그 그룹을 죽이지 않기 위한 것이다.
    2. `rollback(unit, k, pre_sha)`
    3. 롤백이 성공하면 곧바로 `clear_marker()`를 부른다.
    4. 다음 시도 번호는 메모리에만 둔다: `self.resume = {"unit": unit, "next_k": k + 1}`. 같은 unit을 k+1번째 시도로 이어 간다는 뜻이다. `next_k`가 3을 넘으면 시도 소진이고, 뒤 step이 `error`로 확정한다. marker를 먼저 지우므로, ① 뒤에 시작 전 검사가 exit하더라도 다음 기동이 ③에 막히지 않는다(그때는 시도 번호가 1부터 다시 시작한다).
  - ② `stage == "feat_done"`이고 HEAD == `feat_sha`: chore만 이어서 한다. **이것은 step 5가 넣는다.** 이 step에서는 ③과 똑같이 처리한다.
  - ③ 그 밖(HEAD 불일치, 알 수 없는 stage, marker 파싱 실패): **아무것도 건드리지 않고** `HarnessExit(1)`이다. 메시지에 marker 경로와 사유를 담는다. 롤백도, kill도, marker 삭제도 하지 않는다.

### 신호 처리

- `class HarnessInterrupted(BaseException)` — SIGTERM과 SIGHUP을 이 예외로 바꾼다. SIGINT는 파이썬 기본대로 `KeyboardInterrupt`다.
- `Executor.install_signal_handlers() -> None`는 SIGTERM·SIGHUP 처리기를 설치하고 이전 처리기를 보관한다. `Executor.restore_signal_handlers() -> None`는 원래대로 되돌린다.
- 신호가 오면 예외가 `run_child`의 `try/finally`를 지나며 자식 프로세스 그룹을 kill한다. marker는 **남긴다.**
- `run()`에서 `HarnessInterrupted`와 `KeyboardInterrupt`를 잡아 `EXIT_ERROR`를 돌려준다. `run()`이 끝나면 처리기를 복원한다.

### 기동 순서

`run()`을 다음 순서로 만든다: `acquire_lock()` → `install_signal_handlers()` → `recover()` → `prepare()` → `load_step_specs()`. 복구는 잠금 뒤, 시작 전 검사 전이다. 잠금이 없으면 두 번째 실행기가 살아 있는 시도를 롤백할 수 있다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 신호와 복구 테스트는 자식 프로세스를 `fake_bin`의 가짜 실행 파일로 실제로 띄워 검증한다. 단, 테스트는 프로세스 목록을 **실제 `ps`로 읽지 않는다.** Codex 샌드박스에서는 `ps`가 `operation not permitted`로 막혀서, 실제 `ps`에 기대는 테스트는 세션 안에서 늘 실패한다. 대신 `fake_bin`에 가짜 `ps`를 둔다. 가짜 `ps`는 테스트가 띄운 가짜 codex 그룹의 `pid pgid command` 줄을 출력하고, command의 basename은 `codex`다. "codex가 아닌 그룹은 죽이지 않는다" 경우는 가짜 `ps`가 다른 command를 출력하게 해서 검증한다. kill 자체는 실제로 일어나야 한다. killpg 뒤 그 가짜 codex 프로세스가 사라졌는지 확인한다. git 호출을 관찰해야 하면 PATH 앞에 실제 git으로 넘기는 기록용 `git` 래퍼를 둬도 된다(실제 git 경로는 PATH를 바꾸기 전에 `shutil.which`로 구한다). 이전 step 테스트는 계속 통과해야 한다.

롤백과 복구 테스트의 임시 저장소는 `make_repo` 뒤 `feat-7-sample` 브랜치로 옮겨 둔다. 다른 브랜치에서는 `rollback`이 브랜치 확인에서 멈춘다.

- `test_snapshot_has_new_binary_and_unstaged` — 새 untracked 바이너리 파일과 unstaged 수정이 있는 작업 트리를 `snapshot`하면, ref의 커밋 부모가 base이고 두 파일 내용이 바이트 그대로 들어 있다. 실제 index는 바뀌지 않는다(`git diff --cached`가 비어 있다).
- `test_temp_index_outside_worktree` — 스냅샷 중 `add -A`가 받은 `GIT_INDEX_FILE`이 설정돼 있고 `root` 밖이다. 실제 `.git/index`는 그대로이고 임시 index가 남지 않는다.
- `test_snapshot_failure_no_destructive_cmd` — 스냅샷 단계(예: `update-ref`)를 실패시키면 `rollback`이 `HarnessExit(1)`을 던진다. `reset`이나 `clean`은 호출되지 않고 작업 트리 변경이 그대로 남는다. 또 `main` 브랜치에서 `rollback`하면 스냅샷 ref만 생기고 reset·clean 없이 `HarnessExit(1)`이며 `main` ref와 작업 트리 변경이 그대로다.
- `test_rollback_dirty_postcondition_exits_1` — 작업 트리에 커밋을 하나 가진 중첩 저장소 디렉토리(안에 `.git`이 있음)를 둔다. `rollback`은 `refs/harness/…` 스냅샷 ref를 만든 뒤 reset과 clean을 하지만, `clean -fd`가 중첩 저장소를 지우지 않아 porcelain이 비지 않으므로 `HarnessExit(1)`이다.
- `test_recover_running_rolls_back` — marker가 `stage=running`, HEAD==`pre_sha`이고 pgid가 살아 있는 가짜 `codex` 프로세스 그룹이며 작업 트리가 더럽다. 이때 `recover()`가 그룹을 죽이고, 스냅샷 ref를 남기고, 작업 트리를 깨끗하게 만들고, **롤백 뒤 marker를 지운다.** `resume`은 `{"unit": ..., "next_k": k+1}`이다. 없는 pgid면 kill을 조용히 건너뛴다. codex가 아닌 가짜 프로세스(예: 이름이 `sleeper`)의 그룹이면 죽이지 않는다(롤백은 한다). 살려 둔 프로세스는 테스트가 정리한다.
- `test_recover_moved_head_touches_nothing` — marker의 `pre_sha`와 HEAD가 다르면 `HarnessExit(1)`이고 메시지에 marker 경로가 있다. 더러운 파일, marker, `refs/harness/`가 모두 그대로다.
- `test_signal_kills_group_keeps_marker` — 서브프로세스 드라이버에서 실행기 객체가 `install_signal_handlers()`, `save_marker(...)`를 한 뒤 손자를 띄우는 가짜 실행 파일을 `run_child`로 기다린다. 그 드라이버에 SIGTERM을 보내면 종료 코드가 0이 아니고, 자식과 손자가 사라지고, marker 파일이 내용 그대로 남는다. SIGHUP도 같다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_snapshot_has_new_binary_and_unstaged
python3 scripts/test_execute.py -k test_temp_index_outside_worktree
python3 scripts/test_execute.py -k test_snapshot_failure_no_destructive_cmd
python3 scripts/test_execute.py -k test_rollback_dirty_postcondition_exits_1
python3 scripts/test_execute.py -k test_recover_running_rolls_back
python3 scripts/test_execute.py -k test_recover_moved_head_touches_nothing
python3 scripts/test_execute.py -k test_signal_kills_group_keeps_marker
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 모든 파괴 명령 앞에 성공한 스냅샷이 있는가? 테스트가 임시 저장소에서만 파괴 명령을 돌리는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step3-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 스냅샷이 성공하기 전에 `git reset --hard`나 `git clean`을 실행하지 마라. 이유: 되돌린 편집이 어디에도 남지 않는다.
- 임시 index를 작업 트리 안에 두거나 실제 index에 `git add -A`를 쓰지 마라. 이유: 실제 index를 더럽히고 커밋 범위를 오염시킨다.
- `git clean`에 `-x`를 주지 마라. 이유: `.env` 같은 무시 파일까지 지운다. 무시 파일은 롤백 범위 밖이다.
- 스냅샷 ref를 덮어쓰거나 push하지 마라. 이유: 이전 시도의 흔적을 잃고, 원격에 부작용이 생긴다.
- 복구 ③에서 롤백, kill, marker 삭제 중 어느 것도 하지 마라. 이유: 실행기가 모르는 상태를 건드리면 사람의 작업을 파괴할 수 있다.
- codex 프로세스가 있는지 확인하지 않고 marker의 pgid에 `killpg`를 보내지 마라. 이유: 죽은 세션의 pgid를 무관한 프로세스 그룹이 재사용했을 수 있다. `.run/`은 세션이 쓸 수 있는 곳이라 marker 값도 믿을 수 없다.
- `feat-{phase_dir}`가 아닌 브랜치에서 `reset --hard`를 하지 마라. 이유: 그 브랜치 ref가 옮겨져 사람의 커밋을 잃는다.
- 이 저장소 자체(작업 중인 worktree)에서 `reset --hard`나 `clean`이 돌게 만드는 테스트를 쓰지 마라. 모든 파괴 명령 테스트는 `make_repo`로 만든 임시 저장소에서 돈다. 이유: 세션의 작업물이 사라진다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 셸에서 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가이고 가드가 파괴 명령을 막는다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(시도 판정, AC 실행, 재시도 루프, 커밋, 복구 ②, Issue 반영, 리뷰)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
