# Step 8: fix-loop

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드. `git push --force` 금지
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 상태 기계(`:66-84`), 실행기 책임(`:143-160`)
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `EXIT_OK`, `EXIT_ERROR`, `EXIT_BLOCKED`, `EXIT_REVIEW`, `MAX_ATTEMPTS`, `AttemptOutcome`, `StepSpec`
  - `Executor.attempt_unit(unit, task_text, allowed, ac, *, start_k=1)`, `commit_feat(message, pre_sha)`, `clear_marker()`, `marker`, `resume`, `recover()`, `read_result(unit)`
  - `Executor.review_gate(specs)`, `review_round(round_no, end_sha)`, `run_baseline(specs)`
  - `Executor.load_index()`, `save_index()`, `set_top_status()`, `commit_meta()`, `head()`, `git(...)`
  - `Executor.issue_comment(body)`, `issue_blocked(reason)`
  - `Executor.run()`: 현재 잠금 → 신호 처리기 → 복구 → gh 대기열 → 시작 전 검사 → spec 검증 → step 루프 → 리뷰 관문
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo`, `step_md`, `fake_bin`, `calls`, `make_executor`, 기본 덫, step 4~7의 가짜 codex·claude·grok·gh 시나리오

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. step 7까지 step 실행, 커밋, Issue 반영, 리뷰 관문이 생겼다. 리뷰가 `failed`면 지금은 곧바로 exit 3이다.

이 step은 세 가지를 한다.
- **수정 루프:** 리뷰가 `failed`일 때 Codex 수정 세션으로 고치고 다시 리뷰한다.
- **`--push`:** 리뷰 통과 뒤 브랜치를 push한다.
- **배선 테스트:** 가짜 `codex`·`claude`·`grok`·`gh`로 2-step 샘플 phase를 CLI로 끝까지 돌린다.

## 작업

### 수정 루프

- `MAX_FIX_ROUNDS = 2` — 실행기 **1회 기동당** 수정 라운드 상한이다. 다시 실행하면 예산을 새로 받는다.
- 수정은 `failed`일 때만 돈다. `unverifiable`이면 수정하지 않는다(step 7 그대로 exit 3).
- 라운드 r(1부터)의 unit은 `fix{r}`이다.
- `Executor.run_fix(round_no: int, specs: list[StepSpec], scope: str, *, start_k: int = 1) -> AttemptOutcome`
  - `task_text`에 다음을 담는다.
    - 직전 리뷰 라운드의 두 리뷰 원문: `run_dir/review-r{round_no}-claude.txt`, `run_dir/review-r{round_no}-grok.txt`
    - 리뷰 범위 `scope`
    - 모든 step AC 줄
    - 지시: "리뷰가 지적한 결함만 고친다. 모든 AC가 계속 통과해야 한다."
  - 허용 경로는 모든 step 허용 경로의 합집합이다(중복 제거). AC는 모든 step AC를 step 순서대로 이은 것이다.
  - `attempt_unit(f"fix{round_no}", task_text, allowed, ac, start_k=start_k)`를 그대로 쓴다. 판정 항목, 롤백, 3회 시도, blocked 처리가 step과 같다.
- `review_gate`를 넓힌다. `failed`가 나오면 이렇게 돈다.
  1. 그 라운드 결과를 index `review`에 `{status: "failed", end_sha, round}`로 기록하고 chore로 커밋한다. top status는 아직 바꾸지 않는다.
  2. 이번 기동에서 쓴 수정 라운드가 이미 `MAX_FIX_ROUNDS`면 최종 실패다. `set_top_status("error")` → chore → 두 리뷰 원문을 `issue_comment` → `EXIT_REVIEW`.
  3. 아니면 `outcome = run_fix(r, ...)`. 결과별 처리:
     - `completed`:
       - `commit_feat(f"fix: {phase_dir} 리뷰 r{r} 반영 (#{issue})", outcome.pre_sha)`
       - index `review.status = "pending"`(고쳤고 재리뷰 대기)으로 두고 `commit_meta(f"fix{r} 반영")` → `clear_marker()`
       - `end_sha = head()`로 다시 잡는다 → 기준선 → 다음 리뷰 라운드(`round + 1`)
     - `error`(시도 소진):
       - `review.status = "failed"`, `set_top_status("error")` → chore → `clear_marker()`
       - 두 리뷰 원문과 수정 실패 사유를 `issue_comment` → `EXIT_REVIEW`
     - `blocked`:
       - `review.status = "blocked"`, `review.blocked_reason = outcome.reason`, `set_top_status("blocked")` → chore → `clear_marker()`
       - `issue_blocked(reason)` → `EXIT_BLOCKED`
       - 사람이 풀 때는 `review.status`를 `pending`으로 되돌리고 `blocked_reason`을 지운 뒤 재실행한다. step 0의 시작 전 검사가 이 diff를 허용한다.
- 재실행: 모든 step이 completed이고 `review.status`가 `passed`가 아니면 관문부터 다시 하고, 수정 라운드 예산도 새로 받는다.
- **marker 불변식:** marker는 시도가 진행 중이거나, feat(여기서는 fix) 커밋과 chore 커밋 사이일 때만 존재한다. `fix{r}` unit을 끝내는 모든 경로는 그 chore 커밋 **뒤에** `clear_marker()`를 부른다. completed, error, blocked, 재개 시 시도 소진, 재개 버림이 모두 해당한다. 그래서 수정 루프가 어떤 종료 코드로 끝나든 `.run/attempt.json`이 남지 않는다.

### 복구와 수정 unit

- `recover()` ①은 롤백 뒤 marker를 지우고 `self.resume = {"unit": "fix{r}", "next_k": k+1}`만 메모리에 남긴다(step 3). 그 경우를 처리한다.
  - `review_gate`는 첫 리뷰 라운드를 건너뛴다.
  - 재개 경로의 scope는 수정 루프 1단계에서 index에 기록한 `review.end_sha`로 만든다: `f"{base_commit}..{review.end_sha}"`. 그 값이 리뷰가 실제로 본 커밋이다.
  - `review-r{r}-claude.txt`와 `review-r{r}-grok.txt`가 있으면 `run_fix(r, ..., start_k=next_k)`로 곧바로 이어 간다.
  - **재개 시 시도 소진:** `next_k`가 `MAX_ATTEMPTS`를 넘으면 세션 없이 `error` 처리와 같다. `review.status = "failed"`, `set_top_status("error")` → chore → `clear_marker()` → `issue_comment` → `EXIT_REVIEW`.
  - **재개 버림:** 두 파일 중 하나라도 없으면 `resume`을 버리고 `clear_marker()`를 부른 뒤, 평소대로 관문을 시작한다.
- `recover()` ②를 `fix{r}`에도 넓힌다. `stage == "feat_done"`이고 HEAD == `feat_sha`면 `review.status = "pending"` 기록과 chore만 이어서 하고 `clear_marker()`를 부른다. 그 뒤 기동을 계속하면 관문에서 재리뷰한다.

### `--push`

- `Executor.push_branch() -> int`
  - `git push -u origin feat-{phase_dir}`를 실행한다. force 계열(`--force`, `-f`, `--force-with-lease`, `+` refspec)은 절대 쓰지 않는다.
  - env는 **원래 env**다. push는 자격 증명이 필요하다. 실행기 자신의 git 명령이지 세션·AC·리뷰어가 아니다.
  - 성공하면 `EXIT_OK`다. 실패하면 stderr에 사유를 쓰고 `EXIT_ERROR`다. phase는 `completed` 그대로 둔다. index를 바꾸지 않는다.
- `run()` 마감:
  - `review_gate`가 `EXIT_OK`이고 `self.push`면 `push_branch()`의 값을 돌려준다.
  - 이미 완료된 phase(모든 step completed, `review.status == "passed"`, top `completed`)를 다시 실행하면 세션도 리뷰도 하지 않는다. `--push`면 push만 하고, 아니면 `EXIT_OK`다.

### 최종 `run()` 순서

잠금 → 신호 처리기 → 복구 → gh 대기열 재시도 → 시작 전 검사(blocked 재개면 라벨 복원) → step spec 전수 검증 → step 루프 → 리뷰 관문과 수정 루프 → push.

종료 코드는 넷이다.
- 0: 전 step 완료와 리뷰 통과. `--push`를 줬다면 push까지다
- 1: `error`, 내부 실패, push 실패
- 2: `blocked`
- 3: 리뷰 실패 또는 `unverifiable`

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 이전 step 테스트는 계속 통과해야 한다.

가짜 codex 규약(step 0 테스트 기반과 같다): 가짜 codex는 `mcp list --json` 호출에 `[]`를 내고 종료 0이다. 아래의 codex 호출 수는 모두 `exec` 호출만 센 수다.

`test_e2e_*` 세 개는 `scripts/execute.py`를 **서브프로세스 CLI로** 실행한다. `[sys.executable, <이 파일 옆의 execute.py 절대 경로>, "7-sample"]`를 cwd = 임시 저장소로 돌린다. root가 cwd에서 정해지는지도 여기서 확인된다. 가짜 codex는 `-o` 값(`.run/{unit}-last.txt`)으로 unit을 알아내고, step0이면 `src/alpha.txt`, step1이면 `src/beta.txt`를 만든 뒤 result를 쓴다. push 테스트의 원격은 임시 디렉토리의 `git init --bare` 저장소다(네트워크 없음).

- `test_failed_review_fix_and_rereview` — 1라운드에서 claude가 failed, 2라운드에서 둘 다 passed다. 수정 세션 프롬프트에 두 리뷰 원문이 들어 있다. `fix: 7-sample 리뷰 r1 반영 (#7)` 커밋이 생기고 리뷰어가 각각 2회 불리며 결과는 0이고 `review.status`는 `passed`다.
- `test_two_failed_rounds_exit_3` — 리뷰가 계속 failed면 수정 라운드 2회(`fix1`, `fix2`) 뒤 리뷰 3라운드 끝에 3을 돌려준다. `review.status`가 `failed`, top이 `error`이고, 리뷰 원문을 담은 `issue comment`가 불린다. 끝난 뒤 `.run/attempt.json`이 없다.
- `test_fix_blocked_exits_2` — 수정 세션이 blocked를 쓰면 2를 돌려준다. `review.status`가 `blocked`이고 `blocked_reason`이 있으며, top이 `blocked`이고 라벨 교체 `issue edit`가 불린다. 끝난 뒤 `.run/attempt.json`이 없다. 이어서 사람이 하듯 작업 트리 index의 `review.status`를 `pending`으로 되돌리고 `blocked_reason`을 지운 뒤(시작 전 검사의 (b) diff) `run()`하면, 시작 전 검사를 통과해 리뷰 관문까지 간다(리뷰어가 불린다).
- `test_push_no_force` — `--push`로 끝까지 통과하면 bare 원격에 `feat-7-sample`이 HEAD와 같은 커밋으로 생긴다. push argv는 `push -u origin feat-7-sample`이고 force 계열 인자가 없다.
- `test_push_failure_exits_1` — 원격이 없는 경로를 가리키면 `--push` 실행이 1을 돌려준다. top은 `completed`, `review.status`는 `passed` 그대로다. 이미 완료된 phase를 `--push`로 다시 실행하면 codex·claude·grok 호출 없이 push만 시도한다.
- `test_e2e_passed_exit_0` — CLI 실행이 0으로 끝난다. `feat:` 커밋 2개와 chore 커밋이 있고, 두 step이 completed, `review.status`가 `passed`, top이 `completed`이며, 작업 트리가 깨끗하다.
- `test_e2e_blocked_exit_2` — 가짜 codex가 step1에서 blocked를 쓰면 CLI가 2로 끝난다. step0은 completed, step1은 blocked, top은 blocked이고 라벨 교체가 불린다.
- `test_e2e_unverifiable_exit_3_no_fix_commit` — grok이 판정 줄 없이 두 번 끝나면 CLI가 3으로 끝난다. `git log`에 `fix:` 커밋이 없고 step 이후 codex 호출이 없다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_failed_review_fix_and_rereview
python3 scripts/test_execute.py -k test_two_failed_rounds_exit_3
python3 scripts/test_execute.py -k test_fix_blocked_exits_2
python3 scripts/test_execute.py -k test_push_no_force
python3 scripts/test_execute.py -k test_push_failure_exits_1
python3 scripts/test_execute.py -k test_e2e_passed_exit_0
python3 scripts/test_execute.py -k test_e2e_blocked_exit_2
python3 scripts/test_execute.py -k test_e2e_unverifiable_exit_3_no_fix_commit
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 수정 루프가 `unverifiable`에서 돌지 않는가? push에 force 계열 인자가 없는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가? push 테스트의 원격이 로컬 bare 저장소인가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step8-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수, 최종 run() 순서, 종료 코드>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- `git push --force`, `-f`, `--force-with-lease`, `+` refspec을 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- `--push`를 기본으로 켜지 마라. 이유: push는 사람이 요청할 때만 하는 외부 부작용이다.
- `unverifiable` 판정 뒤에 수정 세션을 띄우지 마라. 이유: 판정할 수 없는 리뷰로는 무엇을 고칠지 알 수 없다.
- 한 기동 안에서 수정 라운드를 2회보다 많이 돌리지 마라. 이유: 무한 루프와 비용 폭주를 막는다.
- 테스트의 push 원격으로 실제 GitHub나 네트워크 URL을 쓰지 마라. 이유: 외부 부작용이다. 로컬 bare 저장소만 쓴다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `gh issue close`를 부르거나 병합하지 마라. 이유: close와 병합은 사람이 한다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 셸에서 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 문서(`docs/`, `.claude/commands/`, `AGENTS.md`)를 고치지 마라. 이유: 문서는 step 9가 고친다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
