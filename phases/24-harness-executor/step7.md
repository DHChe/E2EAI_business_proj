# Step 7: review-gate

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `CONTEXT.md` — 용어집
- `.claude/commands/review.md` — `/review` 명령 본문. Claude 리뷰어는 이 명령을 부르고, Grok 리뷰어는 이 본문을 프롬프트로 받는다
- `docs/agents/harness.md` — 상태 기계(`:66-84`), 실행기 책임(`:143-160`)
- `scripts/execute.py` — 이전 step 산출물. 이 step이 쓰는 것:
  - `HarnessExit`, `EXIT_OK`, `EXIT_ERROR`, `EXIT_REVIEW`, `now_kst()`, `StepSpec`
  - `Executor.run_child(...) -> ChildResult`, `child_env()`, `head()`, `git(...)`, `run_dir`, `root`
  - `Executor.run_ac(lines) -> str | None`, `env_fingerprint()`, `rollback(unit, k, target_sha)`
  - `Executor.load_index()`, `save_index()`, `set_top_status(status)`, `commit_meta(label, extra_paths=())`
  - `Executor.issue_comment(body)`, `run_steps(specs)`
  - `Executor.run()`: 현재 잠금 → 신호 처리기 → 복구 → gh 대기열 → 시작 전 검사 → spec 검증 → step 루프
- `scripts/test_execute.py` — `HarnessTestCase`, `make_repo(steps=None, files=None)`, `step_md`, `fake_bin`, `calls`, `make_executor`, 기본 덫

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만든다. step 6까지 모든 step을 시도·확정하고 Issue에 반영하는 흐름이 생겼다.

이 step은 phase 끝의 **리뷰 관문**을 만든다. 리뷰는 두 모델이 차례로 맡는다. 먼저 Claude, 그다음 Grok이다. 리뷰어는 읽기 전용이어야 한다. 그래서 실행기가 리뷰어 실행 전후로 HEAD와 작업 트리를 검사하고, 어긋나면 되돌린 뒤 그 리뷰어의 판정을 무효(`unverifiable`)로 친다.

사전에 확인된 사실:
- Claude 헤드리스(`claude -p ... --output-format json`)의 결과 문자열은 JSON의 `result` 필드다. 명령 파일에 `$ARGUMENTS`가 없어도 `/cmd a b`의 인자가 전달된다.
- Grok 헤드리스(`grok -p "<prompt>" --permission-mode dontAsk --output-format json`)의 결과 문자열은 JSON의 `text` 필드다.
- **Grok은 저장소의 Bash 가드(`guard-bash.py`)를 실행하지 않는다.** 그래서 Grok 쪽 보호는 셋뿐이다. 사후 검사와 되돌림, env에서 자격 증명 제거, 프롬프트 계약문이다.

phase index에는 실행기 소유의 `review` 객체가 있다. 필드는 `status`(`pending` | `passed` | `failed` | `unverifiable` | `blocked`), `end_sha`, `round`, 그리고 선택 필드 `blocked_reason`이다. step 0이 최초 실행 때 `{"status": "pending", "end_sha": null, "round": 0}`으로 만든다. 없으면 pending으로 본다.

## 작업

### 모듈 수준

- `REVIEW_CONTRACT: str` — 실행기가 모든 리뷰 프롬프트 끝에 붙이는 계약문이다. `review.md`의 문구에 기대지 않는다. **줄바꿈 없는 한 줄** 문자열이고 다음 두 내용을 담는다.
  - "이 리뷰에서 파일을 고치거나 커밋, push, `gh` 쓰기, 외부 게시, 원격 DB 변경을 하지 마라."
  - "출력의 마지막 줄은 정확히 `REVIEW_RESULT: passed` 또는 `REVIEW_RESULT: failed`여야 한다."
- `parse_verdict(text: str) -> str | None` — 마지막 비어 있지 않은 줄을 `strip()`한 값이 `^REVIEW_RESULT: (passed|failed)$`와 정확히 맞으면 `passed`/`failed`, 아니면 None.
- `Executor.__init__`에 `self.review_timeout = 1800`(초)을 더한다.

### 리뷰어

- `Executor.review_argv(reviewer: str, scope: str) -> list[str]` — `reviewer`는 `claude` 또는 `grok`이고 `scope`는 `<base_commit>..<end_sha>`다.
  - claude는 이 argv 그대로다: `claude`, `-p`, `--setting-sources`, `project,local`, `--dangerously-skip-permissions`, `--disallowedTools`, `Edit,Write,MultiEdit,NotebookEdit`, `--strict-mcp-config`, `--output-format`, `json`, `/review {scope} {REVIEW_CONTRACT}`
  - grok은 이 argv 그대로다: `grok`, `-p`, `<프롬프트>`, `--permission-mode`, `dontAsk`, `--output-format`, `json`
  - grok 프롬프트는 `root/.claude/commands/review.md` 본문으로 만든다.
    - 앞머리 YAML frontmatter(`---`로 감싼 첫 블록)를 떼어 낸다.
    - `$ARGUMENTS` 자리를 `scope`로 바꾼다. 본문에 `$ARGUMENTS`가 없으면 끝에 `리뷰 범위: {scope}` 줄을 붙인다.
    - 끝에 `REVIEW_CONTRACT`를 붙인다.
    - `review.md`가 없으면 grok 리뷰어는 `unverifiable`이다.
  - claude에 `--bare`를 절대 넣지 않는다. 넣으면 가드 훅과 프로젝트 설정이 꺼진다.
- `Executor.run_reviewer(reviewer: str, round_no: int, end_sha: str, scope: str) -> str` — 반환값은 `passed` | `failed` | `unverifiable`이다.
  - 실행 한 번은 다음 순서다.
    1. **사전 조건:** `git symbolic-ref -q HEAD`가 `refs/heads/feat-{phase_dir}`이고, HEAD == `end_sha`이고, `git status --porcelain`이 비어 있다. 아니면 실행기 내부 불일치이므로 `HarnessExit(1)`이다.
    2. 실행 전 `env_fingerprint()`를 기록한다.
    3. `run_child(review_argv(...), env=child_env(), timeout=self.review_timeout)`로 실행한다. 새 세션으로 뜨고 timeout 때 그룹이 kill된다.
    4. **사후 조건 — 브랜치:** `git symbolic-ref -q HEAD`가 여전히 `refs/heads/feat-{phase_dir}`인지 먼저 본다. 바뀌었으면(다른 브랜치로 checkout, detached HEAD) `snapshot(f"review-r{round_no}-{reviewer}", 1, end_sha)`로 **스냅샷만 남기고**, reset·clean 없이 `HarnessExit(1)`이다. 다른 브랜치에서 `reset --hard`를 하면 그 브랜치 ref가 옮겨진다. `rollback`의 브랜치 확인(step 3)도 같은 결과를 낸다.
    5. **사후 조건 — 나머지:** HEAD == `end_sha`, porcelain이 비어 있음, `.env` 지문 불변. 하나라도 어긋나면 `rollback(f"review-r{round_no}-{reviewer}", 1, end_sha)`으로 되돌린다(스냅샷 → `reset --hard end_sha` → `clean -fd`). 그 리뷰어는 재시도 없이 `unverifiable`이다.
    6. stdout을 JSON으로 읽어 결과 문자열을 꺼낸다. claude는 `result`, grok은 `text`다. 그 문자열(JSON이 아니면 stdout 원문)을 `run_dir/review-r{round_no}-{reviewer}.txt`에 쓴다.
    7. `parse_verdict`가 판정을 준다.
  - 판정이 없거나 JSON 파싱이 실패하거나 종료 코드가 0이 아니거나 timeout이면 그 리뷰어를 **1회만** 재시도한다. 그래도 안 되면 `unverifiable`이다.

### 관문

- `Executor.run_baseline(specs: list[StepSpec]) -> str | None` — 모든 step의 AC를 step 순서대로 `run_ac`로 돌린다. 첫 실패의 사유를 돌려주고, 전부 통과면 None이다. step AC는 phase 끝까지 참이어야 한다는 규칙을 여기서 확인한다.
- `Executor.review_round(round_no: int, end_sha: str) -> dict[str, str]`
  - `scope = f"{base_commit}..{end_sha}"`. `base_commit`은 phase index의 값이다.
  - claude를 먼저, grok을 나중에 **순차로** `run_reviewer`한다. claude가 되돌림을 당했어도 되돌림이 끝난 뒤 grok을 실행한다.
  - `{"claude": 판정, "grok": 판정}`을 돌려준다.
- `Executor.review_gate(specs: list[StepSpec]) -> int` — 반환값은 종료 코드다.
  - **진입 조건:** 모든 step이 `completed`이고 `review.status`가 `passed`가 아니다. 재실행도 여기부터 들어온다.
  - 진입하면 다음을 차례로 한다.
    1. `end_sha = head()`, `round_no = 1`. 이 값은 결과를 확정할 때까지 메모리에만 둔다. 리뷰 중에는 index를 커밋하지 않는다. 커밋하면 HEAD가 움직여 사전 조건이 깨진다.
    2. 기준선: `run_baseline(specs)`가 실패하면 리뷰어를 부르지 않는다. `set_top_status("error")` → `commit_meta("review baseline error")` → 사유를 `issue_comment`로 단다 → `EXIT_ERROR`.
    3. `verdicts = review_round(round_no, end_sha)`
    4. 판정을 모아 결과를 확정한다. 결과를 index의 `review`에 `{status, end_sha, round}`로 기록하고 chore로 커밋한다.
  - 결과별 처리:
    - **둘 다 `passed`:** `review.status = "passed"`. phase index에 `completed_at`을 넣고 `set_top_status("completed")`. `commit_meta("phase completed")`. Issue에 댓글 셋을 단다. phase 요약(step별 summary) 하나, Claude 리뷰 원문 하나, Grok 리뷰 원문 하나다. `EXIT_OK`를 돌려준다.
    - **하나라도 `unverifiable`:** `review.status = "unverifiable"`. 코드를 건드리지 않는다. `set_top_status("error")` → chore → 두 리뷰 요약을 `issue_comment` → `EXIT_REVIEW`.
    - **그 밖(`failed` 포함):** `review.status = "failed"`. `set_top_status("error")` → chore → 두 리뷰 원문을 `issue_comment` → `EXIT_REVIEW`. 수정 루프는 step 8이 여기에 끼운다.
- `run()`에 연결한다.
  - step 루프 뒤에 `return review_gate(specs)`를 붙인다.
  - 모든 step이 completed이고 `review.status`가 `passed`면(이미 완료된 phase) 관문을 건너뛰고 `EXIT_OK`다. `--push` 처리는 step 8이 한다.
  - 재실행 때 top status가 `error`였다면 시작 전 검사(step 0)가 이미 `pending`으로 되돌린다. `review.status`가 `failed`나 `unverifiable`인 phase를 다시 돌리면 step 루프는 할 일이 없고 관문부터 다시 한다.

### 필수 테스트

아래 이름 그대로 `scripts/test_execute.py`에 넣는다. 관문 테스트용 저장소는 모든 step이 completed이고 `created_at`·`base_commit`이 있으며 AC가 통과하는 상태로 만든다. 가짜 `claude`와 `grok`은 시나리오 환경변수에 따라 판정 줄을 내거나, 빼거나, 커밋·파일 수정·브랜치 전환을 한다. 각 가짜는 불린 시점의 HEAD와 받은 env를 기록한다. `review_gate`를 직접 부르는 테스트는 저장소를 `feat-7-sample` 브랜치에 둔다. 가짜 codex 규약은 step 0 테스트 기반과 같다(`mcp list --json`에 `[]`, 호출 수는 `exec`만 센다). 이전 step 테스트는 계속 통과해야 한다.

- `test_both_passed_completes_phase` — 두 리뷰어가 passed면 `review.status`가 `passed`이고 `end_sha`가 기록된다. top index는 `completed`와 `completed_at`이고 chore 커밋이 생기며 반환값은 0이다. 가짜 `gh`에 댓글 셋이 불린다.
- `test_baseline_ac_failure_errors` — end_sha에서 한 step의 AC가 실패하면 리뷰어 호출이 0회이고 top index가 `error`이며 반환값은 1이다.
- `test_missing_verdict_retry_then_unverifiable` — claude가 판정 줄 없이 두 번 끝나면 claude 호출이 정확히 2회이고 결과는 `unverifiable`, 반환값은 3이다. 첫 번째만 판정이 없고 두 번째가 passed면 그 리뷰어는 passed다.
- `test_reviewer_commit_reverted_unverifiable` — claude가 커밋을 만들면 HEAD가 `end_sha`로 돌아오고 `refs/harness/7-sample/review-r1-claude/` 아래 스냅샷 ref가 생긴다. claude는 `unverifiable`이고, grok은 HEAD == `end_sha`인 상태에서 불린다. 리뷰어가 브랜치를 바꾸면(예: `git checkout -q main`) 결과는 exit 1이고, `main`과 `feat-7-sample` ref가 그대로이며, 스냅샷 ref가 남는다.
- `test_reviewer_edit_reverted_unverifiable` — grok이 추적 파일을 고치고 새 파일을 만들면 둘 다 되돌려지고 porcelain이 비며 grok은 `unverifiable`이다.
- `test_reviewer_argv_and_env` — claude argv가 위 목록과 원소 단위로 같고 `--bare`가 없다. grok argv의 프롬프트에 `review.md` 본문 고유 문자열, `scope`, `REVIEW_RESULT: passed`가 있다. 두 리뷰어의 env에 `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`이 없고, `GH_CONFIG_DIR`는 빈 디렉토리이며, `PYTHONDONTWRITEBYTECODE=1`이다.
- `test_rerun_completed_steps_starts_at_gate` — 모든 step이 completed이고 `review.status`가 `failed`인 index로 `run()`하면 codex `exec` 호출이 0회이고, 두 리뷰어가 passed를 내며, 반환값이 0이다.
- `test_unverifiable_exits_3_no_fix` — claude가 unverifiable이고 grok이 failed면 반환값이 3이다. codex 호출이 0회이고 `fix:` 커밋이 없으며 작업 트리가 깨끗하다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
python3 scripts/test_execute.py -k test_both_passed_completes_phase
python3 scripts/test_execute.py -k test_baseline_ac_failure_errors
python3 scripts/test_execute.py -k test_missing_verdict_retry_then_unverifiable
python3 scripts/test_execute.py -k test_reviewer_commit_reverted_unverifiable
python3 scripts/test_execute.py -k test_reviewer_edit_reverted_unverifiable
python3 scripts/test_execute.py -k test_reviewer_argv_and_env
python3 scripts/test_execute.py -k test_rerun_completed_steps_starts_at_gate
python3 scripts/test_execute.py -k test_unverifiable_exits_3_no_fix
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`와 어긋나지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 이전 step의 이름과 시그니처를 바꾸지 않았는가?
   - 리뷰 중에 index를 커밋하는 코드가 없는가? 리뷰어가 남긴 변경은 모두 스냅샷 뒤 되돌려지는가?
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step7-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 더한 함수와 시그니처>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 두 리뷰어를 병렬로 돌리지 마라. 이유: 앞 리뷰어가 남긴 변경을 되돌린 뒤에 다음 리뷰어를 시작해야 한다.
- 리뷰어가 브랜치를 바꿔 놓은 상태에서 `reset --hard`나 `clean`을 하지 마라. 이유: 옮겨 간 브랜치(예: `main`)의 ref가 `end_sha`로 덮인다. 스냅샷만 남기고 exit 1로 사람에게 넘긴다.
- 리뷰어의 판정을 출력 중간의 문구로 추측하지 마라. 판정은 마지막 비어 있지 않은 줄의 `REVIEW_RESULT: passed|failed`뿐이다. 이유: 계약 밖 출력을 통과로 읽으면 관문이 무력해진다.
- `unverifiable`일 때 수정 세션을 띄우거나 코드를 고치지 마라. 이유: 판정할 수 없는 리뷰로는 무엇을 고칠지 알 수 없다. 사람이 본다.
- 리뷰어에게 원래 env(자격 증명 포함)를 주지 마라. 이유: 특히 Grok은 가드 밖이다. 원격 쓰기를 막는 장치는 자격 증명 제거뿐이다.
- claude를 `--bare`로, codex를 `--ignore-user-config`로 부르는 코드를 만들지 마라. 이유: 두 플래그 모두 저장소의 Bash 가드 훅을 끈다.
- `gh issue close`를 부르지 마라. 이유: close와 병합은 사람이 한다.
- 실제 index에 `git add -A`, `git add --all`, `git add .`을 쓰는 코드를 만들지 마라. 이유: 커밋 범위는 검증된 경로 목록뿐이다. 예외는 작업 트리 밖 임시 index 파일에 대한 `add -A`뿐이다.
- `git push --force`를 비롯한 force 계열 push를 쓰지 마라. 이유: 실행기는 원격 이력을 덮지 않는다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`, `.claude/commands/review.md`를 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다. `review.md`는 step 9가 고친다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 셸에서 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 다음 step의 기능(수정 루프, `--push`, 끝까지 도는 배선 테스트)을 미리 구현하지 마라. 이유: step 경계다. step 8이 그 기능과 테스트를 맡는다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- 이전 step의 테스트를 지우거나 약하게 고치지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
