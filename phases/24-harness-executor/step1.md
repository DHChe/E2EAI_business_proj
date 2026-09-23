# Step 1: step-spec

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 특히 Step 설계 7원칙(`:86-99`)의 5번 "AC는 실행 가능한 커맨드"와 step 템플릿(`:101-141`)
- `scripts/execute.py` — step 0 산출물. 이 step이 쓰는 것:
  - `HarnessExit(code, message)`, `EXIT_ERROR`
  - `Executor(root, phase_dir, *, push=False)`와 속성 `root`, `phase_dir`, `phase_path`, `index_path`
  - `Executor.git(*args, env=None, check=True, input=None)`, `load_index()`, `prepare()`, `run()`
- `scripts/test_execute.py` — step 0 산출물. `HarnessTestCase`, `make_repo(steps=None, files=None)`, `step_md(n, name, allowed, ac, body="")`, `fake_bin`, `calls`, `make_executor`, 기본 덫(`codex`·`claude`·`grok`·`gh`가 불리면 종료 97)

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 Python 3.10 표준 라이브러리로 만든다. 구현 세션은 Codex가 맡고, phase 끝 리뷰는 Claude와 Grok이 맡는다. step 0이 뼈대(CLI, `Executor`, index 입출력, 잠금, `commit_paths`, 시작 전 검사)를 만들었다.

실행기는 step 파일에서 두 가지를 기계로 읽는다.
- `## 변경 허용 경로` 절: 세션이 바꿔도 되는 경로 목록이다. 한 줄에 경로 하나다.
- `## Acceptance Criteria` 절의 bash 블록: 실행기가 직접 한 줄씩 돌리는 검증 커맨드다.

이 step은 그 파싱과 검증을 만든다. 실행기는 기동할 때마다 **HEAD에 커밋된** step 파일을 전수 검증한다. 위반이 하나라도 있으면 세션도 AC도 실행하지 않고 exit 1이다.

## 작업

### 모듈 수준 (`scripts/execute.py`)

- `class SpecError(ValueError)` — 위반 사유를 메시지로 담는다. 메시지에는 문제가 된 줄을 넣는다.
- `@dataclass(frozen=True) class StepSpec` — 필드는 `step: int`, `name: str`, `text: str`(step 파일 전문), `allowed: tuple[str, ...]`, `ac: tuple[str, ...]`.
- `parse_allowed_paths(text: str) -> list[str]`
  - 절의 범위: 줄 전체가 `## 변경 허용 경로`인 줄의 다음 줄부터, 다음에 `## `로 시작하는 줄 직전(또는 파일 끝)까지다. 절이 없거나 둘 이상이면 `SpecError`.
  - 앞뒤 공백을 뗀 비어 있지 않은 줄 하나가 경로 하나다. 빈 줄은 건너뛴다.
  - 허용하는 형태는 **정확한 파일 경로** 또는 **`/`로 끝나는 디렉토리 접두사** 둘뿐이다.
  - 다음은 `SpecError`로 거부한다.
    - glob 문자 `*`, `?`, `[`
    - 절대 경로(`/`로 시작)
    - `..` 경로 성분
    - `:`로 시작하는 것(git pathspec magic)
    - 정규화되지 않은 표기. 끝의 `/`를 뗀 값이 `posixpath.normpath`와 다르면 거부한다(`./a`, `a//b`, `.` 등).
    - `phases/`와 겹치는 경로. `phases`와 같거나 `phases/`로 시작하면 거부한다. 두 index와 step 파일은 실행기만 다룬다.
  - 경로가 하나도 없으면 `SpecError`.
- `path_allowed(path: str, allowed: Sequence[str]) -> bool` — 항목이 `/`로 끝나면 접두사 일치, 아니면 정확히 일치.
- `parse_ac(text: str) -> list[str]`
  - 절의 범위: 줄 전체가 `## Acceptance Criteria`인 줄부터 다음 `## ` 줄 직전까지다. 없거나 둘 이상이면 `SpecError`.
  - 절 안의 펜스 블록(세 개의 백틱으로 시작하는 줄로 열고 닫는다)이 **정확히 1개**여야 하고, 여는 줄의 언어 표시가 정확히 `bash`여야 한다. 0개, 2개 이상, 다른 언어 표시, 닫히지 않은 블록은 모두 `SpecError`다.
  - 블록 안에서 빈 줄과, 앞 공백을 뗀 뒤 `#`로 시작하는 주석 줄을 뺀다. 남은 **각 줄이 독립 커맨드**다. 커맨드가 0개면 `SpecError`.
  - 줄마다 다음을 검사한다.
    - `\`로 끝나면 거부한다(줄 잇기).
    - `<<`를 포함하면 거부한다(heredoc·herestring).
    - `bash -n -c <줄>`이 0이 아니면 거부한다. if/for/while/함수 같은 여러 줄 구문이 여기서 걸린다.
  - 반환값은 앞뒤 공백을 뗀 커맨드 줄 리스트다.
  - 실행기는 나중에(step 4) 이 줄을 **한 줄씩 따로** `bash -o pipefail -c <줄>`로 돌리고 모든 줄이 종료 0이어야 통과로 본다. 줄 단위 실행이라 `false && true` 같은 줄도 실패로 잡힌다. 여기서는 파싱과 문법 검증만 한다.

### `Executor`에 더할 것

- `load_step_specs() -> list[StepSpec]`
  - phase index의 `steps` 순서대로 `git show HEAD:phases/{phase_dir}/step{N}.md`를 읽는다. **HEAD에 커밋된 파일**을 읽고, 작업 트리 파일은 읽지 않는다.
  - 모든 step을 빠짐없이 검증한다. 위반을 모두 모아서 하나라도 있으면 `HarnessExit(1, <step별 위반 목록>)`을 던진다. HEAD에 파일이 없는 것도 위반이다.
  - 검증이 끝나면 결과를 `self.specs`에 고정하고 돌려준다. 실행 중에는 step 파일을 다시 읽지 않는다.
- `run()`에 끼운다: `prepare()` 바로 다음에 `load_step_specs()`를 부른다. `prepare()`가 사람의 step 파일 수정을 chore로 커밋하므로, 그 뒤의 HEAD를 읽게 된다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. step 0 테스트는 계속 통과해야 한다.

- `test_paths_reject_glob_abs_dotdot_magic` — `src/*.py`, `src/?.py`, `src/[ab].py`, `/etc/passwd`, `../x`, `src/../x`, `:(glob)src`, `./src/a.py`가 각각 `SpecError`다. `src/a.py`와 `src/`는 통과한다.
- `test_paths_reject_phases_overlap` — `phases`, `phases/`, `phases/7-sample/step0.md`, `phases/index.json`이 각각 `SpecError`다.
- `test_ac_exactly_one_bash_block` — AC 절에 블록이 0개일 때, bash 블록이 2개일 때, `sh` 블록 하나뿐일 때, AC 절이 없을 때 각각 `SpecError`다. 정확히 1개면 주석과 빈 줄을 뺀 줄 목록을 돌려준다.
- `test_ac_rejects_multiline_constructs` — `\`로 끝나는 줄, `cat <<EOF`, `if true; then`, `for x in a; do`, `f() {`가 각각 `SpecError`다. `! false`, `false && true`, `false | true`는 문법 검사를 통과한다.
- `test_specs_read_from_head` — 커밋된 step 파일과 다르게 작업 트리 파일의 AC를 고쳐도 `load_step_specs()`는 HEAD 내용을 돌려준다.
- `test_invalid_spec_runs_nothing` — HEAD의 step 파일 하나가 위반이고 다른 step의 AC가 부작용 파일을 만드는(`touch ran.txt`) 저장소에서, `run()`이 1을 돌려주고 가짜 `codex` 호출이 0회이며 `ran.txt`가 생기지 않는다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_paths_reject_glob_abs_dotdot_magic
python3 scripts/test_execute.py -k test_paths_reject_phases_overlap
python3 scripts/test_execute.py -k test_ac_exactly_one_bash_block
python3 scripts/test_execute.py -k test_ac_rejects_multiline_constructs
python3 scripts/test_execute.py -k test_specs_read_from_head
python3 scripts/test_execute.py -k test_invalid_spec_runs_nothing
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - step 0의 이름과 시그니처를 바꾸지 않았는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step1-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 작업 트리의 step 파일을 읽어 spec을 만들지 마라. 이유: 실행기는 HEAD에 커밋된 검증된 지시서만 따른다. 작업 트리 파일은 세션이 바꿀 수 있다.
- 위반이 있는 step을 건너뛰고 나머지를 실행하게 만들지 마라. 이유: 전수 검증이 끝나기 전에는 아무것도 실행하지 않는다.
- AC 줄을 이어 붙여 한 스크립트로 만들거나 `bash -e`로 돌리는 설계를 하지 마라. 이유: `bash -e`는 `false && true`의 실패를 삼킨다.
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
- 다음 step의 기능(세션 실행, 롤백, 시도 판정, AC 실행, 커밋, Issue 반영, 리뷰)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
