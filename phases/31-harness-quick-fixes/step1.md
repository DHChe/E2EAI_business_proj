# Step 1: reviewer-env-restore

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 특히 "`.env` 역할 분담" 절. 그 절의 마지막 문장(`AGENTS.md:31-32`, 세션·AC·기준선과 리뷰어 도중의 처리)이 이 step의 기준이다
- `docs/agents/harness.md` — "세션 격리와 판정" 절의 ④ 설명(시도·기준선 시작 때 `.env` 보관·복원)과 "리뷰 관문·수정 루프" 절의 리뷰어 문단
- `scripts/execute.py`
  - `Executor.run_reviewer()` — 이 step이 고치는 함수
  - `.env` 도우미: `env_fingerprint()`, `capture_env()`, `restore_env()`, `restore_env_change()`, `capture_path()`, `restore_path()`
  - 비교용 호출부: `attempt_unit()`과 `run_baseline()`이 `env_fingerprint()`·`capture_env()`를 시작 때 잡고 `restore_env_change()`로 되돌리는 방식
- `scripts/test_execute.py`
  - `ReviewGateTests.fixture()` — 가짜 리뷰어의 `mode`(`env`는 `.env`에 `changed`를 쓴다), `review(ex, reviewer)` 도우미
  - 기존 테스트 `test_reviewer_preconditions_and_env_mutation` — 고치지 않고 계속 통과해야 한다

## 배경

실행기는 구현 세션·AC·리뷰 기준선 AC를 돌리기 전에 루트의 `.env`·`.env.*`(`.env.example` 제외) 중 파일·링크·특수 파일을 메모리에 보관한다. 끝난 뒤 지문이 다르면 보관본으로 되돌린다. 그런데 리뷰어(`run_reviewer`)는 지문(`env_fingerprint`)만 비교하고 보관·복원을 하지 않는다(Issue #31 항목 3, I-10).

재현: `.env`=`original`인 상태에서 가짜 claude 리뷰어가 `.env`를 `changed`로 쓰고 passed를 내면, 리뷰 관문은 exit 3·`unverifiable`로 끝나지만 `.env`는 `changed`로 남는다. 사유 끝에는 "(.env는 수동 확인)"만 붙는다. 다음 기동은 바뀐 값을 새 기준선으로 삼는다.

Issue #31 triage에서 정한 해석: 리뷰어 단계에서도 **바뀐 값과 지워진 파일은 되돌린다**. 리뷰어가 **새로 만든** `.env*` 항목은 지우지 않고 남긴 채 멈추고, 사유에 그 이름을 적는다. `AGENTS.md:31-32`의 리뷰어 도중 규칙(지우지 않고 멈춘다)은 이 새 파일 규칙을 말한다.

## 작업

### `.env` 도우미 (`scripts/execute.py`)

- `restore_env(self, saved: dict, *, keep_new: bool = False) -> None`
  - `keep_new=False`(기본)는 지금과 같다. 현재 항목과 보관본의 합집합을 되돌리므로 보관본에 없던 새 항목은 지운다.
  - `keep_new=True`면 **보관본에 있던 이름만** 되돌린다(수정은 보관 바이트로, 삭제는 다시 만든다). 보관본에 없던 새 이름은 건드리지 않는다.
- `restore_env_change(self, before, saved, regular_reason, context="", *, keep_new: bool = False) -> str | None`
  - `keep_new`를 `restore_env`에 그대로 넘긴다.
  - `keep_new=True`일 때 새 이름이 있으면 사유에 "새 파일 제거" 대신 **남겼다는 사실과 이름 목록**을 적는다(예: `(리뷰어가 만든 새 파일은 지우지 않았다: 사람이 확인 ['.env.local'])`). 디렉토리·링크 판정 문구(`수동 복원 필요`)는 지금과 같되, `keep_new=True`면 그 사유에도 남긴 새 이름 목록을 덧붙인다.
- 기존 호출부(`attempt_unit`, `run_baseline`, `git_env_reason`)의 동작은 바꾸지 않는다. 기본값이 `keep_new=False`이므로 인자를 더하지 않으면 된다.

### `Executor.run_reviewer()`

- 시도마다 리뷰어를 띄우기 전에 `fingerprint = self.env_fingerprint()` 옆에서 `env_saved = self.capture_env()`도 잡는다.
- 리뷰어가 끝난 뒤 순서는 Git 설정 검사(`git_guard_failed`) → **`.env` 비교·복원** → 브랜치·HEAD·porcelain 검사다. Git 설정 검사가 복원 성공(참 반환)으로 끝나도 `.env` 비교·복원은 한다. `git_guard_failed()`가 `HarnessExit`를 던지면(복원 실패) 지금처럼 그대로 전파한다(`attempt_unit`과 같다). 브랜치가 바뀌어 `HarnessExit`로 끝나는 경로에서도 그 전에 `.env`를 되돌린다.
- `.env` 비교·복원은 `restore_env_change(fingerprint, env_saved, "<사유>", "리뷰어", keep_new=True)`로 한다. 돌려받은 사유가 있으면:
  - 그 리뷰어는 `unverifiable`이다(지금처럼 terminal).
  - 사유를 `[executor] ...` 줄로 리뷰 원문 끝과 stderr에 남긴다(기존 `reasons` 목록에 넣으면 된다). 사유에는 되돌린 것과 남긴 새 파일 이름이 드러나야 한다.
- 지금의 "리뷰어가 작업 트리 또는 .env를 바꿔 되돌림: {ref} (.env는 수동 확인)" 문구에서 "(.env는 수동 확인)"을 뺀다. `.env`가 바뀐 경우에도 지금처럼 스냅샷·롤백(`rollback`)을 하고 ref를 사유에 남긴다. `.env` 변경 여부는 복원 **전**에 판정한 값으로 쓴다(복원 뒤 지문은 다시 같아질 수 있다).

### 필수 테스트 (`scripts/test_execute.py`의 `ReviewGateTests`)

아래 이름 그대로 넣는다.

- `test_reviewer_env_restored_new_file_kept` — 루트에 `.env`=`original`, `.env.old`=`old`를 두고, 가짜 `claude`가 `.env`를 `changed`로 덮어쓰고 `.env.old`를 지우고 `.env.local`=`new`를 만든 뒤 `{"result": "Review body\nREVIEW_RESULT: passed"}`를 출력하게 한다(`fake_bin`). `review_gate(ex.load_step_specs())`가 3이고, 그 뒤:
  - `.env`의 바이트가 `original`, `.env.old`가 `old`로 복원돼 있다.
  - `.env.local`이 `new` 그대로 남아 있다.
  - phase index의 `review.status`가 `unverifiable`이다.
  - `.run/review-r1-claude.txt`에 `.env.local`이 적혀 있고 `수동 확인`은 없다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
python3 scripts/test_execute.py -k test_reviewer_env_restored_new_file_kept
python3 scripts/test_execute.py -k test_reviewer_preconditions_and_env_mutation
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다. 전체 테스트는 3분 가까이 걸린다.
2. 체크리스트:
   - `AGENTS.md`의 `.env` 역할 분담 규칙과 맞는가? 리뷰어가 만든 새 `.env*`를 지우지 않는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 세션·AC·기준선의 `.env` 동작(새 파일 제거 포함)이 그대로인가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 실행기가 한다.
   - `phases/31-harness-quick-fixes/.run/step1-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 바꾼 함수·시그니처와 테스트 이름>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 리뷰어가 새로 만든 `.env*` 항목을 지우지 마라. 이유: Issue #31 triage 결정이다. 사람이 누가 왜 만들었는지 확인하기 전에 지우면 되돌릴 수 없다.
- 루트의 실제 `.env*` 디렉토리를 보관하거나 되돌리지 마라. 이유: 기존 규칙대로 디렉토리는 존재만 지문에 넣고 `수동 복원 필요`로 멈춘다.
- `.env` 변경을 복원했다는 이유로 그 리뷰어의 판정을 passed·failed로 인정하지 마라. 이유: 리뷰어가 계약문(파일 변경 금지)을 어겼으므로 `unverifiable`이다.
- 세션·AC·기준선의 `.env` 처리(`attempt_unit`, `run_baseline`, `git_env_reason`)를 바꾸지 마라. 이유: 이 step의 범위는 리뷰어뿐이다.
- 기존 테스트를 지우거나 약하게 고치지 마라. 이유: 기존 동작 보장과 앞 step의 AC는 phase 끝까지 참이어야 한다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`, `AGENTS.md`, `docs/`를 수정하지 마라. 이유: 이 step의 범위 밖이다. 문서는 마지막 step이 맞춘다.
- `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 실행기가 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고는 예외).
- 저장소 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 테스트의 `.env`는 `tempfile`로 만든 저장소 안에만 둔다. 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
