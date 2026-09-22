# Step 0: phase-state

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집. 이 step은 도구 코드라 도메인 용어를 거의 쓰지 않는다
- `docs/agents/harness.md` — phase·step 규약. 특히 스키마(`:34-64`), 상태 기계와 복구(`:66-84`), 실행기 책임(`:143-160`)
- `docs/agents/triage-labels.md` — Issue 라벨 문자열
- `docs/adr/0015-typescript-web-stage-sse-no-unverified-answer-text.md` — 제품 스택은 TypeScript다. 이 실행기는 제품 코드가 아니라 저장소 도구라서 Python 3.10 표준 라이브러리로 쓴다
- `.gitignore` — `phases/**/.run/`, `__pycache__/`, `*.pyc`, `.env`, `.env.*`는 이미 무시된다
- `phases/index.json`, `phases/24-harness-executor/index.json` — 실행기가 다룰 실제 index

이 step이 phase의 첫 step이다. `scripts/`는 아직 없다.

## 배경

이 phase(`24-harness-executor`, GitHub Issue #24)는 `scripts/execute.py`를 만든다. phase의 step을 사람 개입 없이 끝까지 실행하는 실행기다.
사람은 세 곳만 맡는다. 앞단은 기획과 phase 승인, 중간은 `blocked` 해소와 `error` 복구, 뒷단은 Issue close와 병합이다.
구현 세션은 Codex(`codex exec`)가 맡고, phase 끝 리뷰는 Claude와 Grok이 맡는다.

step 0~8이 실행기를 한 모듈씩 쌓고, step 9가 문서를 고친다. 뒤 step은 이 step이 정한 이름과 시그니처를 그대로 쓴다. **이름을 바꾸지 마라.**

이 step은 뼈대를 만든다. CLI, `Executor`, index 입출력, 잠금, 커밋 원시 함수, 자식 프로세스 env 정리, 시작 전 검사를 만들고, 뒤 step 전부가 쓸 테스트 기반을 만든다.

## 작업

### 공통 규칙

- Python 3.10 표준 라이브러리만 쓴다.
- 외부 명령은 항상 argv 리스트로 `subprocess`에 준다. `shell=True`를 쓰지 않는다.
- 저장소 루트 `root`는 **인자로만** 받는다. `__file__`에서 유도하지 않는다. CLI는 cwd에서 `git rev-parse --show-toplevel`로 구한다.

### `scripts/execute.py` — 모듈 수준

- 종료 코드 상수는 넷이다.
  - `EXIT_OK = 0`: 전 step 완료와 리뷰 통과(그리고 요청됐다면 push)
  - `EXIT_ERROR = 1`: `error`, 내부 실패, push 실패
  - `EXIT_BLOCKED = 2`: `blocked`
  - `EXIT_REVIEW = 3`: 리뷰 실패 또는 리뷰 판정 불가(`unverifiable`)
- `class HarnessExit(Exception)` — `HarnessExit(code: int, message: str)`. 속성 `.code`, `.message`. 실행을 멈출 때 던지고, `run()`이 잡아 메시지를 stderr에 찍은 뒤 `code`를 돌려준다.
- `now_kst() -> str` — KST(UTC+9) ISO 8601 초 단위. 예: `2026-09-22T16:44:00+09:00`.
- `read_json(path: Path) -> dict`
- `write_json_atomic(path: Path, data: dict) -> None`
  - 같은 디렉토리의 임시 파일에 UTF-8로 쓴다(`ensure_ascii=False`, 들여쓰기 2, 끝 개행).
  - flush와 fsync 뒤 `os.replace`로 바꿔 끼운다.
  - 도중에 실패하면 임시 파일을 지우고 예외를 다시 던진다. 기존 파일은 그대로 남아야 한다.
- `repo_root(cwd: Path) -> Path` — `cwd`에서 `git rev-parse --show-toplevel`을 돌린다.
- `main(argv: list[str] | None = None) -> int`
  - argparse로 위치 인자 `phase_dir`(예: `24-harness-executor`)와 선택 플래그 `--push`(기본 꺼짐)를 받는다.
  - `root = repo_root(Path.cwd())`. `root/phases/{phase_dir}/index.json`이 없으면 1을 돌려준다.
  - `Executor(root, phase_dir, push=...).run()`의 값을 돌려준다.
  - 파일 끝에 `if __name__ == "__main__": sys.exit(main())`.

### `class Executor`

생성자는 `Executor(root: Path, phase_dir: str, *, push: bool = False)`다. 생성자는 부작용 없이 속성만 둔다.

- 속성: `root`, `phase_dir`, `push`
- 경로 속성:
  - `phase_path` = `root/phases/{phase_dir}`
  - `index_path` = `phase_path/index.json`
  - `top_index_path` = `root/phases/index.json`
  - `run_dir` = `phase_path/.run`
  - `lock_path` = `root/phases/.run/lock`. worktree 단위 잠금이라 phase 디렉토리 밖에 둔다. `.gitignore`의 `phases/**/.run/`에 걸린다
- `branch` = `feat-{phase_dir}`

메서드와 속성:

- `issue` (property) `-> int` — phase index의 `issue`.
- `git(*args: str, env: dict[str, str] | None = None, check: bool = True, input: bytes | None = None) -> subprocess.CompletedProcess`
  - cwd는 `root`이고 출력은 캡처한다.
  - `check=True`에서 종료 코드가 0이 아니면 `HarnessExit(1, <명령과 stderr>)`.
  - 실행기 자신의 git 명령은 원래 env를 쓴다. `child_env`는 쓰지 않는다.
- `head() -> str` — HEAD 커밋 sha.
- `changed_paths() -> list[str]`
  - `git status --porcelain=v1 -z --untracked-files=all`을 파싱한다.
  - staged, unstaged, untracked, 삭제를 모두 담는다. rename·copy는 **양쪽 경로**를 다 담는다.
  - 무시 파일은 담지 않는다.
- index 입출력: `load_index() -> dict`, `save_index(data: dict) -> None`, `load_top_index() -> dict`, `save_top_index(data: dict) -> None`. 쓰기는 전부 `write_json_atomic`이다.
- `set_top_status(status: str) -> None`
  - top index의 `phases`에서 `dir == phase_dir`인 항목의 `status`를 바꾸고 저장한다.
  - `completed`면 `completed_at`, `error`면 `failed_at`, `blocked`면 `blocked_at`을 `now_kst()`로 둔다. 나머지 두 타임스탬프 키는 지운다.
  - `pending`이면 세 키를 모두 지운다.
  - 항목이 없으면 `HarnessExit(1)`.
- `child_env(*, strip_orca: bool = False) -> dict[str, str]` — 세션·AC·리뷰어처럼 실행기가 띄우는 자식 프로세스용 env다.
  - `os.environ`의 복사본에서 `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`을 지운다.
  - `GH_CONFIG_DIR`는 이 Executor가 처음 부를 때 한 번 만드는 **빈 임시 디렉토리**(저장소 밖)로 둔다.
  - `PYTHONDONTWRITEBYTECODE=1`을 둔다.
  - `strip_orca=True`면 `ORCA_`로 시작하는 변수도 지운다(Codex 세션용). 기본값에서는 남긴다.
  - `gh` 래퍼(step 6)와 실행기 자신의 git 명령은 이 env를 쓰지 않는다.
- `acquire_lock() -> None`
  - `lock_path`의 디렉토리(`root/phases/.run/`)를 만들고 `lock_path`를 열어 `fcntl.flock(fd, LOCK_EX | LOCK_NB)`을 건다.
  - 잠금은 phase가 아니라 **worktree 단위**다. 한 worktree에서는 phase_dir가 달라도 실행기가 하나만 돈다. 실행기는 브랜치를 checkout하고 reset하므로 같은 작업 트리를 두 실행기가 나눠 쓸 수 없다.
  - 실패하면 `HarnessExit(1, "다른 실행기가 이 worktree에서 실행 중이다")`.
  - fd는 프로세스가 끝날 때까지 들고 있는다. 죽은 프로세스의 잠금은 커널이 푼다. lock 파일은 지우지 않는다.
- `commit_paths(paths: Iterable[str], message: str) -> str` — 검증된 경로만 커밋하는 원시 함수다. 뒤 step의 모든 커밋이 이것을 거친다.
  0. **브랜치 확인:** `git symbolic-ref -q HEAD`가 `refs/heads/feat-{phase_dir}`가 아니면(다른 브랜치, detached HEAD 포함) index도 건드리지 않고 커밋 없이 `HarnessExit(1)`이다.
  1. `paths`가 비었으면 `ValueError`.
  2. env에 `GIT_LITERAL_PATHSPECS=1`을 더해 `git add -- <paths>`를 한다. 삭제된 경로도 이것으로 stage된다.
  3. `git diff --cached --name-only -z --no-renames`의 경로 집합이 `paths` 집합과 **정확히** 같은지 확인한다. rename을 양쪽 경로로 보려고 `--no-renames`를 준다.
  4. 다르면 `git reset -q`로 index를 HEAD로 되돌린다. 이것은 작업 트리를 건드리지 않는 mixed reset이다. 커밋하지 않고 `HarnessExit(1)`을 던진다.
  5. 같으면 `git commit -q -m <message>`를 한다. 실패하면 `HarnessExit(1)`. 성공하면 새 HEAD sha를 돌려준다.
  - 실제 index에 `git add -A`, `git add --all`, `git add .`을 절대 쓰지 않는다.
- `commit_meta(label: str, extra_paths: Iterable[str] = ()) -> str | None`
  - `{index_path, top_index_path} ∪ extra_paths` 가운데 `changed_paths()`에 있는 것만 `commit_paths`로 커밋한다. 경로는 root 기준 상대 경로다.
  - 메시지는 `chore: {phase_dir} {label} (#{issue})`.
  - 바뀐 것이 없으면 커밋하지 않고 None을 돌려준다.
- `prepare() -> str | None` — 시작 전 검사다. 아래 순서를 지킨다.
  1. `feat-{phase_dir}`를 **먼저** checkout한다. 없으면 현재 HEAD에서 만든다(`git checkout -b`). 이미 그 브랜치면 그대로 둔다. checkout이 실패하면(충돌 등) `HarnessExit(1)`.
  2. `changed_paths()`가 전부 `phases/{phase_dir}/` 아래여야 한다. 무시되지 않는 파일이면 step*.md 수정과 새 파일도 허용한다. 하나라도 밖이면 `HarnessExit(1)`이다. `phases/index.json` 변경도 밖으로 친다.
  3. `index.json`이 바뀌었으면 HEAD의 것(`git show HEAD:phases/{phase_dir}/index.json`)과 작업 트리의 것을 JSON으로 비교한다. 아래 둘 중 하나와 정확히 맞을 때만 허용하고, 그 밖이면 `HarnessExit(1)`이다. JSON 파싱 실패도 exit 1이다.
     - (a) HEAD 기준 **마지막 비-pending step**의 status가 `error` 또는 `blocked`다. 작업 트리에서는 그 step의 status만 `pending`으로 바뀌었다. 그 step의 `error_message`·`blocked_reason`·`failed_at`·`blocked_at` 가운데 일부가 지워졌을 수 있다. 다른 키, 다른 step, 최상위 키는 같다.
     - (b) HEAD의 `review.status`가 `blocked`다. 작업 트리에서는 `review.status`만 `pending`으로 바뀌었고, `review.blocked_reason`이 지워졌을 수 있다. 나머지는 같다.
  4. 작업 트리 index로 멈춤 상태를 본다.
     - 마지막 비-pending step이 `error`면 `HarnessExit(1)`, `blocked`면 `HarnessExit(2)`.
     - `review.status`가 `blocked`여도 `HarnessExit(2)`.
     - 여기서 멈출 때는 아무것도 커밋하지 않고 top index도 건드리지 않는다. top index는 종료 코드에 맞는 `error`/`blocked`로 남는다.
  5. 최초 실행이면(`created_at`이 없음) 세 필드를 넣어 저장한다.
     - `created_at` = `now_kst()`
     - `base_commit` = 지금 HEAD. 1의 checkout 뒤, 이 chore 커밋 전의 HEAD다.
     - `review`가 없으면 `{"status": "pending", "end_sha": null, "round": 0}`
  6. top index에서 이 phase의 status가 `error` 또는 `blocked`면 `set_top_status("pending")`.
  7. 2에서 허용된 변경과 5·6의 변경을 `commit_meta` **한 번**(chore 커밋 하나)으로 커밋한다. 이 커밋은 첫 시도 전에 끝나 있어야 한다.
  - 반환값은 6에서 되돌린 이전 top status(`"error"` 또는 `"blocked"`)다. 되돌리지 않았으면 None이다. step 6이 blocked 재개 때 Issue 라벨을 되돌리는 데 쓴다.
- `run() -> int`
  - 이 step에서는 `acquire_lock()` → `prepare()` → `EXIT_OK` 순서다.
  - `HarnessExit`를 잡아 메시지를 stderr에 쓰고 `code`를 돌려준다.
  - 뒤 step이 이 사이에 단계를 끼운다. 최종 순서는 잠금 → 신호 처리기 → marker 복구 → gh 대기열 재시도 → 시작 전 검사 → step spec 검증 → step 실행 → 리뷰 관문 → push다.

### `scripts/test_execute.py` — 테스트 기반

모든 뒤 step이 이 기반을 쓴다.

- 맨 위에서 `sys.dont_write_bytecode = True`로 두고, 이 파일이 있는 디렉토리를 `sys.path` 앞에 넣은 뒤 `import execute`.
- 상수는 `PHASE = "7-sample"`, `ISSUE = 7`.
- `step_md(n: int, name: str, allowed: list[str], ac: list[str], body: str = "") -> str` — 최소 step 파일 텍스트를 만든다.
  - 제목 `# Step {n}: {name}`
  - `## 작업` 절(`body`)
  - `## 변경 허용 경로` 절: 한 줄에 경로 하나
  - `## Acceptance Criteria` 절: bash 펜스 블록 하나에 `ac`를 한 줄씩
- `class HarnessTestCase(unittest.TestCase)`
  - setUp에서 저장소 **밖**에 임시 디렉토리를 만든다(`tempfile.mkdtemp`). addCleanup으로 지운다.
  - `unittest.mock.patch.dict(os.environ)`로 env를 격리한다.
    - `HOME`, `GH_CONFIG_DIR`, `CODEX_HOME`은 각각 임시 디렉토리로 둔다.
    - `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`을 지운다.
    - `PYTHONDONTWRITEBYTECODE=1`, `GIT_CONFIG_NOSYSTEM=1`, git 작성자·커미터 이름·이메일 env를 둔다.
    - `PATH`는 가짜 bin 디렉토리를 원래 PATH 앞에 붙인 것이다.
  - **기본 덫:** setUp에서 `codex`, `claude`, `grok`, `gh` 네 이름의 가짜를 설치한다. 불리면 argv를 호출 로그에 남기고 종료 코드 97로 끝난다. PATH 뒤에 실제 CLI가 있어도 절대 닿지 않게 하는 장치다. 테스트는 필요한 이름만 덮어쓴다.
  - `fake_bin(name: str, source: str) -> Path` — 가짜 bin 디렉토리에 실행 파일을 쓴다. 셔뱅은 `#!{sys.executable}`인 Python 스크립트다. 가짜의 시나리오는 환경변수로 주입한다.
  - `calls(name: str) -> list[list[str]]` — 그 가짜의 호출 argv 목록이다. 호출 로그는 JSON 줄로 둔다.
  - **가짜 codex 규약**(뒤 step의 모든 테스트가 따른다):
    - 테스트가 설치하는 가짜 `codex`는 따로 정하지 않는 한 `mcp list --json` 호출(argv에 `mcp`가 있는 호출)에 `[]`를 내고 종료 0이다. 그래야 세션 전 preflight를 통과한다.
    - codex 호출 횟수를 단언할 때는 `exec` 호출(argv에 `exec`가 있는 호출)만 센다. `mcp list` 호출은 세지 않는다.
  - `make_repo(steps: list[dict] | None = None, files: dict[str, str] | None = None) -> Path` — 임시 git 저장소를 만들고 root를 돌려준다.
    - `git init`, 브랜치 `main`.
    - `.gitignore`: 실제 저장소와 같은 규칙(`.env`, `.env.*`, `!.env.example`, `__pycache__/`, `*.pyc`, `phases/**/.run/`)에 테스트용 `*.log`를 더한다.
    - 가드레일 문서 `AGENTS.md`, `CONTEXT.md`, `docs/adr/0001-sample.md`, `docs/PRD.md`. 각각 짧은 고유 문자열을 담는다.
    - `src/keep.txt`
    - `phases/index.json` = `{"phases": [{"dir": PHASE, "issue": ISSUE, "status": "pending"}]}`
    - `phases/{PHASE}/index.json`: project·phase·issue, steps 전부 pending
    - `phases/{PHASE}/step{N}.md` (`step_md`로 만든다)
    - `files`로 받은 추가 파일
    - 전부 첫 커밋에 넣는다.
    - `steps` 기본값은 둘이다.
      - `{"name": "alpha", "allowed": ["src/"], "ac": ["test -f src/alpha.txt"]}`
      - `{"name": "beta", "allowed": ["src/"], "ac": ["test -f src/beta.txt"]}`
  - `make_executor(root: Path, **kw) -> execute.Executor`
  - 뒤 step은 이 헬퍼에 키워드 인자를 더해 넓혀도 된다. 기존 호출은 그대로 동작해야 한다.
- 파일 끝 main은 `unittest.main(exit=False)`로 돌린다. 실패가 있거나 **실행된 테스트가 0개면 종료 코드 1**이다.
  - Python 3.10 unittest는 `-k`가 아무것에도 맞지 않으면 0개를 실행하고 종료 0을 낸다. 이 규칙이 AC의 `-k` 줄이 거짓으로 통과하는 것을 막는다.
- 테스트는 검사하려는 메서드를 직접 부른다. 뒤 step이 `run()`에 단계를 더해도 이 step의 테스트가 깨지지 않게 하기 위해서다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 각 테스트가 잡아야 할 실패 시나리오를 함께 적었다. 더 많은 테스트를 써도 된다.

- `test_zero_tests_exit_1` — 이 테스트 파일을 `-k __no_such_test__`로 서브프로세스 실행하면 종료 코드가 1이다. 0개 실행이 통과로 보고되는 것을 막는지 본다.
- `test_index_write_atomic` — `os.replace`를 patch해 예외를 내면 `write_json_atomic`이 예외를 다시 던지고, 원본 `index.json`이 바이트 그대로이며, 같은 디렉토리에 임시 파일이 남지 않는다.
- `test_lock_rejects_second_run` — 다른 프로세스가 `phases/.run/lock`을 쥔 동안 `acquire_lock()`이 `HarnessExit(1)`을 던진다. 다른 `phase_dir`로 만든 `Executor`도 똑같이 거부된다. 그 프로세스가 끝나면 다시 잡힌다.
- `test_checkout_before_meta_commit` — `main`에서 사람이 index를 되돌려 둔 상태로 `prepare()`를 부르면 chore 커밋이 `feat-7-sample`에 생기고 `main` ref는 그대로다.
- `test_meta_diff_allows_pending_reset_only` — (a) 마지막 error step을 pending으로 되돌리고 `error_message`·`failed_at`을 지운 diff와 (b) `review.status` blocked→pending diff가 각각 허용되고 chore로 커밋된다.
- `test_meta_diff_rejects_other_edits` — 다른 step의 status·name·summary 수정, completed step을 pending으로 되돌림, `phases/index.json` 수정이 각각 `HarnessExit(1)`이고 새 커밋이 없다.
- `test_dirty_outside_phase_dir_exits_1` — phase 디렉토리 밖의 추적 파일 수정이나 새 파일이 있으면 `HarnessExit(1)`이고 새 커밋이 없다.
- `test_base_commit_committed_before_attempt` — 최초 `prepare()` 뒤 HEAD 커밋의 index에 `created_at`, `base_commit`(prepare 직전 HEAD), `review`가 있고 작업 트리가 깨끗하다. 두 번째 `prepare()`는 값을 바꾸지 않고 커밋도 만들지 않는다.
- `test_last_error_exits_1_blocked_exits_2` — 마지막 비-pending step이 error면 1, blocked면 2, `review.status`가 blocked면 2다. 이때 top index는 pending으로 바뀌지 않는다.
- `test_commit_paths_rejects_unexpected_cached` — `feat-7-sample` 브랜치에서 미끼 파일이 미리 stage돼 있으면 `commit_paths`가 커밋하지 않고, index를 HEAD로 되돌리고, `HarnessExit(1)`을 던진다. `main` 브랜치에서 부르면 index를 건드리지 않고 커밋 없이 `HarnessExit(1)`이다.
- `test_child_env_sanitized` — 토큰 셋이 빠지고, `GH_CONFIG_DIR`가 원래 값과 다른 존재하는 빈 디렉토리이고, `PYTHONDONTWRITEBYTECODE=1`이다. `ORCA_*`는 `strip_orca=True`일 때만 빠진다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_zero_tests_exit_1
python3 scripts/test_execute.py -k test_index_write_atomic
python3 scripts/test_execute.py -k test_lock_rejects_second_run
python3 scripts/test_execute.py -k test_checkout_before_meta_commit
python3 scripts/test_execute.py -k test_meta_diff_allows_pending_reset_only
python3 scripts/test_execute.py -k test_meta_diff_rejects_other_edits
python3 scripts/test_execute.py -k test_dirty_outside_phase_dir_exits_1
python3 scripts/test_execute.py -k test_base_commit_committed_before_attempt
python3 scripts/test_execute.py -k test_last_error_exits_1_blocked_exits_2
python3 scripts/test_execute.py -k test_commit_paths_rejects_unexpected_cached
python3 scripts/test_execute.py -k test_child_env_sanitized
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이 파일이 정한 이름과 시그니처를 그대로 썼는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step0-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 만든 파일과 뒤 step이 쓸 핵심 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`(step 3)뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(step 파일 파싱, 세션 실행, 롤백, 시도 판정, Issue 반영, 리뷰)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 기존 테스트를 깨뜨리지 마라.
