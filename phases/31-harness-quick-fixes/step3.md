# Step 3: ac-tree-flag

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약
- `docs/agents/harness.md` — "세션 격리와 판정" 절의 판정 표(⑥ AC 각 줄 종료 0, ⑦ AC 전후 HEAD와 작업 트리 tree SHA가 같다)와 "리뷰 관문·수정 루프" 절 첫 문단(기준선이 실패면 phase error, ⑦이면 `end_sha`로 스냅샷·롤백)
- `scripts/execute.py`
  - `Executor.run_ac()` — 이 step이 반환 모양을 바꾸는 함수
  - 호출부 둘: `Executor.attempt_unit()`, `Executor.run_baseline()`
  - `Executor.rollback()`, `snapshot()` — 롤백은 `refs/harness/<phase>/<unit>/…` 스냅샷 ref를 남긴다
- `scripts/test_execute.py`
  - `run_ac`를 직접 부르는 기존 테스트(파일에서 `run_ac(`를 검색하라)
  - `ReviewGateTests.fixture(scenarios=None, ac=None, review='pending')` — `ac`로 단일 step의 AC 줄을 준다. 기존 `test_baseline_ac_failure_errors`, `test_baseline_env_and_tree_mutation`이 기준선 동작을 보장한다

## 배경

리뷰 기준선(`run_baseline`)은 `if failure and "⑦" in failure`로 롤백 여부를 정한다. 그런데 `failure` 문자열에는 실패한 AC 출력의 끝 2000자가 들어간다. 그래서 작업 트리를 바꾸지 않은 AC라도 출력에 `⑦` 문자가 있으면 롤백이 불린다(Issue #31 항목 5, I-15 일부). 롤백은 스냅샷 ref를 남기고 `git reset --hard`·`git clean -fd`를 부르는 파괴 경로라, 문자열 우연으로 불리면 안 된다.

고칠 방향: `run_ac`가 트리 변경 여부를 사유 문자열과 **따로** 돌려주고, 기준선은 그 값으로만 롤백한다.

## 작업

### `Executor.run_ac()` (`scripts/execute.py`)

- 시그니처를 `run_ac(self, lines: Sequence[str]) -> tuple[str | None, bool]`로 바꾼다. 첫 값은 지금과 같은 사유 문자열(없으면 `None`), 둘째 값 `mutated`는 AC 전후 HEAD 또는 작업 트리 tree SHA가 달라졌으면 `True`다.
- 사유 문자열의 내용은 지금과 같다. 트리가 바뀌면 지금처럼 `⑦ AC가 작업 트리를 바꿨다 …` 문구가 들어간다(구현 세션 재시도 프롬프트와 Issue 댓글에 쓰인다).
- Git 설정 변경으로 일찍 돌아가는 경로(`④ Git 설정 변경 감지·복원`)는 `("④ Git 설정 변경 감지·복원", False)`를 돌려준다. 이 경로의 롤백은 지금처럼 호출부가 한다. 여기서 `False`는 "바뀌지 않았다"가 아니라 "재지 않았다"는 뜻이며, 두 호출부 모두 ④ 경로에서 무조건 롤백하므로 문제가 없다.

### 호출부

- `attempt_unit()` — 사유 문자열만 쓴다. 동작은 바꾸지 않는다.
- `run_baseline()` — 롤백 조건을 `"⑦" in failure`에서 **`mutated`가 참일 때**로 바꾼다. 나머지(Git 설정·`.env` 처리, 반환 사유)는 바꾸지 않는다.

### 테스트 (`scripts/test_execute.py`)

- `run_ac`를 직접 부르는 기존 테스트는 새 반환 모양에 맞춰 풀어 쓴다. 단언의 뜻(사유가 없음, `timeout` 포함, `⑦` 포함 등)은 그대로 두고, 트리를 바꾸는 줄(`git commit --allow-empty …`)에는 `mutated`가 참이라는 단언을 더한다.
- 새 테스트 `test_baseline_seventh_in_output_keeps_tree` (`ReviewGateTests`) — `fixture(ac=["echo '⑦ AC가 작업 트리를 바꿨다 (HEAD 또는 tree 변경)'; false"])`(출력에 ⑦ 문구 전체가 있고 종료 1, 트리는 안 바꿈. 문자열 비교로는 실제 트리 변경과 구분할 수 없게 일부러 같은 문구를 쓴다)에서 `review_gate(ex.load_step_specs())`가 1이고, `ex.rollback`이 한 번도 불리지 않으며(`mock.patch.object(ex, 'rollback', wraps=ex.rollback)` 등), `git for-each-ref refs/harness/` 출력이 비어 있다. 상위 phase `status`는 `error`다.
- 기존 `test_baseline_env_and_tree_mutation`(트리를 실제로 바꾸면 롤백·스냅샷 ref가 남는다)은 고치지 않고 계속 통과해야 한다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
python3 scripts/test_execute.py -k test_baseline_seventh_in_output_keeps_tree
python3 scripts/test_execute.py -k test_baseline_env_and_tree_mutation
python3 scripts/test_execute.py -k test_ac_tree_change_fails
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다. 전체 테스트는 3분 가까이 걸린다.
2. 체크리스트:
   - 기준선의 ⑦ 롤백 판정이 `mutated`만 보는가? (`④ Git` 조기 반환을 가리는 `failure.startswith("④ Git")` 검사는 이번 범위 밖이라 그대로 둔다)
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 실행기가 한다.
   - `phases/31-harness-quick-fixes/.run/step3-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 바꾼 시그니처와 호출부, 테스트 이름>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 사유 문자열에서 `⑦` 문구를 빼거나 바꾸지 마라. 이유: 구현 세션의 재시도 프롬프트와 Issue 댓글이 이 문구로 원인을 알린다. 바뀌는 것은 롤백 판정의 근거뿐이다.
- AC 출력을 잘라 내거나 걸러서 `⑦`을 지우는 방식으로 고치지 마라. 이유: 판정과 사람용 문구를 분리하는 것이 목적이다.
- `attempt_unit()`의 판정·롤백 순서를 바꾸지 마라. 이유: 이 step의 범위는 기준선 롤백 조건뿐이다.
- Git 설정·`.env` 비교·복원 규칙을 바꾸지 마라. 이유: 기존 테스트가 보장하는 보호 규칙이다.
- 기존 테스트를 지우거나 약하게 고치지 마라. 반환 모양에 맞춘 풀어 쓰기만 한다. 이유: 기존 동작 보장과 앞 step의 AC는 phase 끝까지 참이어야 한다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`, `AGENTS.md`, `docs/`를 수정하지 마라. 이유: 이 step의 범위 밖이다.
- `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 실행기가 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고는 예외).
- 저장소 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
