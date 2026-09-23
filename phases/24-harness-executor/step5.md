# Step 5: scoped-commit

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 스키마(`:34-64`), 상태 기계(`:66-84`), 실행기 책임(`:143-160`), 특히 "2단계 커밋"과 "커밋 범위는 경로 화이트리스트"
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `EXIT_ERROR`, `EXIT_BLOCKED`, `now_kst()`, `StepSpec`, `MAX_ATTEMPTS`, `AttemptOutcome`
  - `Executor.commit_paths(paths, message) -> str`, `commit_meta(label, extra_paths=()) -> str | None`
  - `Executor.changed_paths()`, `head()`, `load_index()`, `save_index()`, `set_top_status(status)`, `issue`
  - `Executor.attempt_unit(unit, task_text, allowed, ac, *, start_k=1) -> AttemptOutcome`
  - `Executor.save_marker()`, `load_marker()`, `clear_marker()`, `marker`, `resume`, `recover()`, `read_result(unit)`
  - `Executor.run()`: 현재 잠금 → 신호 처리기 → 복구 → 시작 전 검사 → spec 검증
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `step_md`, `fake_bin`, `calls`, `make_executor`, 기본 덫, step 4의 가짜 codex 시나리오

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. step 4까지 unit 하나의 시도 루프가 생겼다. 루프는 통과, error, blocked 가운데 하나를 돌려주지만 아직 아무것도 커밋하지 않는다.

이 step은 결과를 **2단계 커밋**으로 확정하고 step들을 차례로 도는 루프를 `run()`에 연결한다. 2단계는 코드(`feat`)와 메타데이터(`chore`)다. 순서는 다음과 같다.

검증 → `feat` 커밋(변경이 없으면 생략하고 `feat_sha = pre_sha`) → marker `feat_done` → index 확정 → 두 index만 `chore` 커밋 → marker 삭제

커밋 메시지 형식:
- `feat: {phase_dir} step{N} {name} (#{issue})`
- `chore: {phase_dir} <상태> (#{issue})` — `commit_meta`가 만든다

## 작업

### 커밋과 확정

- `Executor.commit_feat(message: str, pre_sha: str) -> str` — 반환값은 `feat_sha`다.
  - HEAD가 `pre_sha`와 다르면 `HarnessExit(1)`이다.
  - `changed_paths()`가 비어 있지 않으면 `commit_paths(changed, message)`로 커밋한다. 비어 있으면 커밋을 생략하고 `feat_sha = pre_sha`다.
  - 그다음 `save_marker({**self.marker, "stage": "feat_done", "feat_sha": feat_sha})`.
  - 커밋이 실패하면 `commit_paths`가 `HarnessExit(1)`을 던진다. marker는 `stage=running` 그대로 **남는다.** 다음 기동 때 복구 ①이 그 시도를 롤백하고 이어 간다.
- `Executor.confirm_step(step: int, status: str, text: str) -> None` — `status`는 `completed` | `error` | `blocked`다. `text`는 상태에 따라 summary, error_message, blocked_reason이다.
  - phase index의 그 step에 다음을 기록한다. 다른 상태의 키(`summary`/`error_message`/`blocked_reason`과 짝 타임스탬프)는 지운다.
    - `completed`: `summary`와 `completed_at`
    - `error`: `error_message`와 `failed_at`
    - `blocked`: `blocked_reason`과 `blocked_at`
    - 타임스탬프는 `now_kst()`다.
  - `error`나 `blocked`면 `set_top_status(status)`로 top index도 같은 상태로 둔다.
  - `commit_meta(f"step{step} {status}")`로 chore 커밋을 한다. 두 index 말고는 커밋하지 않는다.
  - 그 뒤 `clear_marker()`.
- **marker 불변식:** marker는 시도가 진행 중이거나, feat 커밋과 chore 커밋 사이일 때만 존재한다.
  - step unit을 끝내는 모든 경로는 그 chore 커밋 **뒤에** `clear_marker()`를 부른다. completed, error, blocked, 재개 시 시도 소진(`start_k`가 `MAX_ATTEMPTS`를 넘은 error) 모두 `confirm_step` 안에서 부른다.
  - 커밋 실패로 멈추는 경우만 marker를 남긴다. 그 시도는 아직 끝나지 않았기 때문이다.
- `commit_paths`와 `commit_meta`는 HEAD가 `feat-{phase_dir}` 브랜치가 아니면 커밋 없이 `HarnessExit(1)`을 던진다(step 0). 이 step의 모든 커밋은 그 브랜치 위에서 일어난다.

### step 루프

- `Executor.run_steps(specs: list[StepSpec]) -> None` — `specs` 순서대로 돈다.
  - index에서 `completed`인 step은 건너뛴다.
  - `pending`인 step은 `unit = f"step{N}"`이다. `self.resume`가 이 unit을 가리키면 `start_k = resume["next_k"]`로 이어 가고 `resume`을 지운다. 아니면 `start_k = 1`이다.
  - `outcome = attempt_unit(unit, spec.text, spec.allowed, spec.ac, start_k=start_k)`
  - 결과별 처리:
    - `completed`: `commit_feat(f"feat: {phase_dir} step{N} {name} (#{issue})", outcome.pre_sha)` → `confirm_step(N, "completed", outcome.summary)` → 다음 step
    - `error`: `confirm_step(N, "error", outcome.reason)` → `HarnessExit(1)`
    - `blocked`: `confirm_step(N, "blocked", outcome.reason)` → `HarnessExit(2)`
- `run()`에 연결한다: `load_step_specs()` 다음에 `run_steps(specs)`를 부르고, 끝까지 가면 `EXIT_OK`를 돌려준다. 리뷰 관문은 step 7이 뒤에 붙인다.

### 복구 ②

- `recover()`의 ② 분기를 구현한다. step 3에서는 ③처럼 멈추게 해 뒀다.
- ②는 marker가 `stage == "feat_done"`이고 HEAD == `feat_sha`인 경우다. unit이 `step{N}`이면 다음을 한다.
  1. `read_result(unit)`에서 summary를 읽는다. result 파일은 다음 시도 시작 때만 지워지므로 남아 있다.
  2. `confirm_step(N, "completed", summary)`로 chore만 이어서 한다. 롤백도 세션도 하지 않는다.
- result가 없거나 무효면 ③(아무것도 건드리지 않고 `HarnessExit(1)`)이다.
- unit이 `fix{r}`인 ②는 step 8이 넣는다. 그때까지는 ③이다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 가짜 codex는 unit별 시나리오로 파일을 바꾸고 result를 쓴다. 이전 step 테스트는 계속 통과해야 한다.

가짜 codex 규약(step 0 테스트 기반과 같다): 가짜 codex는 `mcp list --json` 호출에 `[]`를 내고 종료 0이다. codex 호출 횟수는 `exec` 호출만 센다. `run()`을 거치지 않고 `recover()` 등을 직접 부르는 테스트는 저장소를 먼저 `feat-7-sample` 브랜치로 옮긴다.

- `test_feat_commit_exact_paths_with_decoy` — 세션이 허용 경로 파일 하나를 바꾸고, 곁에 무시 파일이 있다. 세션이 만든 `src/__pycache__/x.pyc`와 `.run/` 산출물, 그리고 시도 전부터 있던(세션이 바꾸지 않은) `.env`다. 이때 feat 커밋의 파일 목록은 바뀐 허용 경로 하나뿐이고, 메시지는 `feat: 7-sample step0 alpha (#7)`이다.
- `test_delete_and_rename_committed` — 세션이 허용 디렉토리 안의 추적 파일을 지우고 다른 파일의 이름을 바꾸면, feat 커밋에 삭제와 rename 양쪽 경로가 모두 들어간다(`--no-renames`로 보면 D와 A).
- `test_no_change_skips_feat` — 세션이 파일을 바꾸지 않고 completed를 쓰면 feat 커밋 없이 chore 커밋 하나만 생긴다.
- `test_chore_only_index_files` — step 확정 chore 커밋이 바꾼 파일은 `phases/7-sample/index.json`뿐이다. error나 blocked 확정이면 `phases/index.json`이 더해진다. 메시지는 `chore: 7-sample`로 시작한다.
- `test_recover_feat_done_chore_only` — feat 커밋이 끝났고 marker가 `feat_done`(HEAD == `feat_sha`)이며 result 파일이 남아 있다. 이때 `recover()`는 codex를 부르지 않고 그 step을 result의 summary로 completed 확정하고 chore를 커밋하고 marker를 지운다.
- `test_commit_failure_exits_1_keeps_marker` — 임시 저장소의 `.git/hooks/pre-commit`이 1로 끝나서 feat 커밋이 실패하면 `run()`이 1을 돌려주고, marker(`stage=running`)가 남고, 새 커밋이 없다.
- `test_error_blocked_confirmed_by_chore` — 세 번 실패하면 `run()`이 1을 돌려준다(codex `exec` 호출 3회). step에 `error_message`와 `failed_at`, top index에 `error`와 `failed_at`이 기록되고 chore로 커밋되며 marker가 없다. blocked면 `run()`이 2이고 `blocked_reason`·`blocked_at`과 top `blocked`가 같은 방식으로 확정된다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_feat_commit_exact_paths_with_decoy
python3 scripts/test_execute.py -k test_delete_and_rename_committed
python3 scripts/test_execute.py -k test_no_change_skips_feat
python3 scripts/test_execute.py -k test_chore_only_index_files
python3 scripts/test_execute.py -k test_recover_feat_done_chore_only
python3 scripts/test_execute.py -k test_commit_failure_exits_1_keeps_marker
python3 scripts/test_execute.py -k test_error_blocked_confirmed_by_chore
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 모든 커밋이 `commit_paths`를 거치는가? chore 커밋이 두 index 말고 아무것도 담지 않는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step5-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- marker를 chore 커밋 전에 지우지 마라. 이유: feat 커밋 뒤 죽으면 복구할 근거가 사라진다.
- feat 커밋과 index 변경을 한 커밋에 섞지 마라. 이유: 코드와 메타데이터는 따로 커밋한다. 복구 ②가 이 경계에 기댄다.
- 커밋이 실패했을 때 작업 트리를 롤백하거나 marker를 지우지 마라. 이유: 다음 기동의 복구가 marker로 이어 간다.
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
- 다음 step의 기능(Issue 라벨·댓글, 리뷰 관문, 수정 루프, push)을 미리 구현하지 마라. 이유: step 경계다. 뒤 step이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
