# Step 2: session-runner

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 실행기 책임(`:143-160`), 특히 "가드레일 주입"과 "컨텍스트 누적"
- `.codex/hooks.json` — Codex 세션에서도 `.claude/hooks/guard-bash.py`가 PreToolUse 훅으로 발동하게 하는 프로젝트 설정. 이 step은 이 파일을 읽기만 한다
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `EXIT_ERROR`
  - `Executor(root, phase_dir, *, push=False)`와 속성 `root`, `phase_dir`, `run_dir`, `index_path`
  - `Executor.child_env(*, strip_orca=False)`, `load_index()`, `git(...)`
  - `StepSpec(step, name, text, allowed, ac)`
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `step_md`, `fake_bin`, `calls`, `make_executor`, 기본 덫

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. 구현 세션은 Codex(`codex exec`)가 맡는다. step 0이 뼈대를, step 1이 step 파일 파싱(`StepSpec`)을 만들었다.

이 step은 구현 세션 하나를 띄우는 부분을 만든다. 들어가는 것은 네 가지다. 검증된 고정 argv, 사용자 MCP 서버를 끄는 가변 인자, 끄지 못했으면 세션을 띄우지 않는 fail-closed preflight, 그리고 프롬프트 조립이다. 자식 프로세스 대기와 timeout, 프로세스 그룹 kill도 여기서 만든다.

사전에 실측으로 확인된 사실(codex-cli 0.155.1):
- 저장소의 `.codex/hooks.json`을 두고 `--dangerously-bypass-hook-trust`로 `codex exec`를 띄우면 `guard-bash.py`가 무수정으로 발동한다.
- `--ignore-user-config`를 주면 프로젝트 훅이 발동하지 않는다. 그래서 사용자 설정은 유지하고 이 플래그는 쓰지 않는다.
- workspace-write 샌드박스에서 `.git`은 쓰기 불가다. 세션은 커밋할 수 없다.
- `-c 'mcp_servers={}'`는 병합될 뿐 서버를 끄지 못한다. 서버 이름에 따옴표를 붙이면(`mcp_servers."x"`) 기존 서버가 아니라 새 키가 생긴다.
- `codex mcp list --json`의 각 항목에는 `name`, `enabled`, `transport.type`이 있다.
- stdio 서버는 `command="true"`와 `enabled=false`를 함께 줘야 꺼진다. streamable_http 서버는 `enabled=false`만 준다. url 서버에 `command`를 주면 설정 에러다.
- 아래 고정 argv와 서버별 인자를 쓰면 exec 세션에서 호출 가능한 MCP가 없고, 가드는 발동하며, stdin 프롬프트도 전달된다.

## 작업

### 자식 프로세스 실행

- `@dataclass class ChildResult` — 필드는 `returncode: int | None`, `timed_out: bool`, `stdout: str`, `stderr: str`.
- `Executor.run_child(argv: list[str], *, env: dict[str, str], timeout: float, stdin_text: str | None = None, stdout_path: Path | None = None, on_spawn: Callable[[int], None] | None = None) -> ChildResult`
  - cwd는 `root`다. `start_new_session=True`로 띄워 자식이 새 프로세스 그룹의 리더가 되게 한다(pgid == pid).
  - 띄운 직후 `on_spawn(pid)`를 부른다. step 4가 이것으로 marker에 pgid를 기록한다.
  - 기다리는 동안 `self.child_pgid`에 pgid를 둔다. step 3의 신호 처리기가 이 값을 쓴다.
  - `stdin_text`가 있으면 stdin으로 쓰고 닫는다. 없으면 stdin은 DEVNULL이다.
  - stdout과 stderr는 캡처한다. `stdout_path`가 있으면 stdout을 그 파일에도 남긴다. 파이프 교착이 생기지 않게 한다(`communicate` 또는 파일로 받기).
  - timeout이 지나면 그룹 전체에 SIGTERM을 보내고, 잠시 뒤에도 남아 있으면 SIGKILL을 보낸다. `timed_out=True`다.
  - 대기 전체를 `try/finally`로 감싼다. finally에서 그룹이 남아 있으면 `os.killpg`로 정리하고 `self.child_pgid = None`으로 둔다. 리더가 정상 종료했어도 그룹에 남은 손자 프로세스까지 정리한다는 뜻이다.
  - **안전 규칙:** pgid가 None이거나 1 이하이거나 `os.getpgrp()`(실행기 자신의 그룹)와 같으면 `killpg`를 부르지 않는다. `killpg`의 `ProcessLookupError`와 `PermissionError`는 둘 다 무시한다(finally에서도 마찬가지다).
- `Executor.__init__`에 `self.session_timeout = 1800`(초)과 `self.child_pgid = None`을 더한다. 테스트는 인스턴스 값을 줄여 쓴다.

### Codex argv

- 모듈 상수 `CODEX_CONFIG_FLAGS: list[str]` — 아래 argv 원소를 이 순서 그대로 담는다. 셸 인용이 아니라 **argv 원소**다. 큰따옴표는 값의 일부다.
  - `-c`, `plugins."browser@openai-bundled".enabled=false`
  - `-c`, `plugins."unified-computer-use@openai-bundled".enabled=false`
  - `-c`, `plugins."computer-use@openai-bundled".enabled=false`
  - `--disable`, `apps`, `--disable`, `computer_use`, `--disable`, `browser_use`, `--disable`, `in_app_browser`
  - `-c`, `sandbox_workspace_write.network_access=false`
- `codex_mcp_overrides(servers: list[dict]) -> list[str]` (모듈 함수)
  - 서버마다 현재 `enabled` 값과 무관하게 끄는 인자를 만든다.
  - 서버 이름은 TOML bare key(`^[A-Za-z0-9_-]+$`)여야 한다. 아니면 `HarnessExit(1)`이다. 따옴표로 감싸면 새 키가 생겨 서버를 끄지 못하므로, 그런 이름은 끌 방법이 없는 것으로 보고 실패로 닫는다.
  - `transport.type`이 `stdio`면 `-c`, `mcp_servers.<name>.command="true"`, `-c`, `mcp_servers.<name>.enabled=false`를 붙인다.
  - 그 밖(`streamable_http` 등)이면 `-c`, `mcp_servers.<name>.enabled=false`만 붙인다.
- `Executor.codex_preflight() -> list[str]` — 세션을 띄울 때마다 부른다. 반환값은 서버별 override 인자다.
  1. `codex mcp list --json`을 돌려 서버 목록(JSON 배열)을 읽는다.
  2. `codex_mcp_overrides`로 override 인자를 만든다.
  3. `codex <CODEX_CONFIG_FLAGS> <overrides> mcp list --json`을 돌린다.
  4. 셋 중 하나라도 해당하면 세션을 띄우지 않고 `HarnessExit(1)`이다: 명령이 0이 아닌 코드로 끝났다, 출력이 JSON 배열이 아니다, 항목 중 `enabled`가 true인 것이 하나라도 있다. 1의 실패도 똑같이 exit 1이다.
  - 두 명령 모두 env는 `child_env(strip_orca=True)`이고 timeout은 120초다.
- `Executor.codex_argv(overrides: list[str], last_path: Path) -> list[str]` — 이 순서 그대로 만든다.
  - `codex`, `exec`
  - `CODEX_CONFIG_FLAGS`, 이어서 `overrides`
  - `-s`, `workspace-write`, `--dangerously-bypass-hook-trust`, `--ephemeral`
  - `-C`, `<root>`, `--json`, `-o`, `<last_path>`
  - 마지막 원소 `-`: 프롬프트를 stdin으로 준다는 뜻이다.
  - 다음은 절대 넣지 않는다: `--ignore-user-config`, `--dangerously-bypass-approvals-and-sandbox`, `danger-full-access`, `--full-auto`.

### 프롬프트와 세션

- `Executor.result_path(unit: str) -> Path` — `run_dir/{unit}-result.json`. unit은 `step{N}` 또는 `fix{r}`다.
- `Executor.build_prompt(unit: str, task_text: str, allowed: Sequence[str], failure: str | None = None) -> str` — 다음을 모두 담는다.
  1. 역할: "너는 이 저장소의 구현 세션이다. 이 세션은 시도 하나다. 작업하고 AC를 직접 돌려 본 뒤 결과를 한 번 보고하고 끝낸다."
  2. 가드레일 문서 전문: `AGENTS.md`, `CONTEXT.md`, `docs/adr/*.md`(파일 이름순 전부), `docs/PRD.md`. 문서마다 경로 머리글을 단다. 없는 파일은 조용히 건너뛴다.
  3. 완료된 step의 요약: phase index에서 status가 `completed`인 step마다 `step{N} {name}: {summary}` 한 줄.
  4. 작업 본문: `task_text`. step unit이면 HEAD의 step 파일 전문이다.
  5. 변경 허용 경로 목록(`allowed`).
  6. result 계약: 결과를 `phases/{phase_dir}/.run/{unit}-result.json`에 JSON 객체 하나로 쓴다. 필드는 `status`(`completed` | `error` | `blocked`), `summary`, 그리고 상태에 따라 `error_message`나 `blocked_reason`이다. `blocked`는 사람만 풀 수 있는 사유(자격 증명, 외부 인증, 수동 설정)에만 쓴다.
  7. 금지:
     - `phases/` 아래 두 index를 쓰지 마라.
     - 커밋하지 마라.
     - push, `gh` 쓰기, 외부 게시, 원격 DB 변경을 하지 마라.
     - 허용 경로 밖을 바꾸지 마라.
  8. `failure`가 있으면 "직전 시도 실패 사유" 절로 넣는다. 없으면 그 절이 없다.
- `Executor.run_codex(unit: str, prompt: str, *, on_spawn: Callable[[int], None] | None = None) -> ChildResult`
  1. `overrides = codex_preflight()`. 실패하면 여기서 `HarnessExit(1)`이고 세션은 뜨지 않는다.
  2. `argv = codex_argv(overrides, run_dir / f"{unit}-last.txt")`
  3. `run_child(argv, env=child_env(strip_orca=True), timeout=self.session_timeout, stdin_text=prompt, stdout_path=run_dir / f"{unit}-session.jsonl", on_spawn=on_spawn)`
  - `run_dir`가 없으면 만든다. 이 파일들은 모두 `phases/**/.run/` 아래라서 gitignore 대상이다.
- 이 step은 세션을 띄우는 부분만 만든다. result 판정, 재시도, 롤백은 뒤 step의 몫이다. `run()`에는 아직 연결하지 않는다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 가짜 `codex`는 `fake_bin`으로 만들고, 받은 argv·stdin·env를 파일로 남기게 한다. 이전 step 테스트는 계속 통과해야 한다.

가짜 codex 규약(step 0 테스트 기반과 같다): 테스트가 따로 정하지 않는 한 가짜 codex는 `mcp list --json` 호출에 `[]`를 내고 종료 0이다. codex 호출 횟수는 `exec` 호출만 센다.

- `test_codex_argv_verified_flags_no_forbidden` — `run_codex`가 띄운 exec argv가 `codex exec`로 시작하고, `CODEX_CONFIG_FLAGS`를 순서 그대로 담고, `-s workspace-write`, `--dangerously-bypass-hook-trust`, `--ephemeral`, `-C <root>`, `--json`, `-o <run_dir/unit-last.txt>`를 담고, `-`로 끝난다. 금지 플래그 넷이 없고 stdin이 프롬프트와 같다.
- `test_mcp_overrides_by_transport` — stdio 서버는 `command="true"`와 `enabled=false` 두 쌍을, streamable_http 서버는 `enabled=false` 한 쌍만 받는다. `a.b`나 `"x"`처럼 bare key가 아닌 이름은 `HarnessExit(1)`이다.
- `test_preflight_fails_closed` — preflight 목록에 `enabled: true`가 남은 경우, preflight 명령이 0이 아닌 코드로 끝난 경우, 출력이 JSON이 아닌 경우, 최초 목록 명령이 실패한 경우 각각 `HarnessExit(1)`이고 `exec` 호출이 0회다. preflight argv는 `mcp list --json` 앞에 같은 config 플래그와 override를 담는다.
- `test_prompt_contents` — 프롬프트에 네 가드레일 문서의 고유 문자열, completed step의 summary, `task_text`, 허용 경로, `.run/{unit}-result.json` 경로와 status 값 셋, push·`gh` 금지 문구가 있다. `failure`는 줬을 때만 들어 있다.
- `test_session_timeout_kills_group` — 가짜 codex가 손자 프로세스를 띄우고(pid를 파일에 남김) 오래 잠든다. `session_timeout`을 1초로 두면 `timed_out`이 True이고, 몇 초 안에 자식과 손자가 모두 사라진다. 사라졌는지는 짧게 폴링해서 확인한다.
- `test_session_env_strips_orca_and_tokens` — `os.environ`에 `ORCA_TEST`, `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`을 두고 세션을 띄우면, 가짜 codex가 받은 env에는 넷 다 없다. `GH_CONFIG_DIR`는 빈 디렉토리이고 `PYTHONDONTWRITEBYTECODE=1`이다. `mcp list` 호출도 같은 env다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_codex_argv_verified_flags_no_forbidden
python3 scripts/test_execute.py -k test_mcp_overrides_by_transport
python3 scripts/test_execute.py -k test_preflight_fails_closed
python3 scripts/test_execute.py -k test_prompt_contents
python3 scripts/test_execute.py -k test_session_timeout_kills_group
python3 scripts/test_execute.py -k test_session_env_strips_orca_and_tokens
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step2-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- `--ignore-user-config`를 넣지 마라. 이유: 프로젝트 `.codex/hooks.json` 가드 훅이 꺼진다.
- MCP를 `-c 'mcp_servers={}'`나 따옴표 붙인 서버 이름으로 끄려고 하지 마라. 이유: 전자는 병합될 뿐이고 후자는 새 키를 만들어 실제 서버가 켜진 채 남는다.
- preflight가 실패하거나 켜진 서버가 남았는데 세션을 띄우지 마라. 이유: fail-closed다. 끄지 못한 MCP는 샌드박스 밖 부작용 통로다.
- `killpg`를 pgid 1 이하나 실행기 자신의 그룹에 보내지 마라. 이유: 실행기와 무관한 프로세스를 죽인다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`(step 3)뿐이다.
- claude를 `--bare`로 부르는 코드를 만들지 마라. 이유: 가드 훅이 꺼진다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(스냅샷·롤백, marker, 시도 판정, AC 실행, 커밋, Issue 반영, 리뷰)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
