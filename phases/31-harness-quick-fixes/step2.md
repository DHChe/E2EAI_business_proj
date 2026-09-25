# Step 2: review-round-continuity

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약
- `docs/agents/harness.md` — "phases/{dir}/index.json" 절의 `review{status, end_sha, round, fixes}`, "실행기 › 기동과 책임" 절의 `review` 초기값 설명(`round`는 리뷰 라운드 번호, `fixes`는 완료한 수정 수), "리뷰 관문·수정 루프" 절(수정 예산 `MAX_FIX_ROUNDS - review.fixes`, 관문 확정 때 `fixes`를 0으로 되돌린 뒤의 새 기동만 새 예산을 받는다)
- `scripts/execute.py`
  - `Executor.review_gate()` — 이 step이 고치는 함수. 시작부의 `round_no` 결정 분기
  - `Executor.finish_fix()`, `run_fix()`, `run_reviewer()` — 라운드 번호가 unit 이름(`fix{r}`), 커밋 메시지(`리뷰 r{r} 반영`), 리뷰 원문 파일(`.run/review-r{r}-{claude|grok}.txt`)에 쓰인다
- `scripts/test_execute.py`
  - `FixLoopTests.fixture(reviews=None, blocked=None, push=False)`, `units()`, `seed_resume()` — 가짜 리뷰어의 판정 목록(`passed`·`failed`·`missing`)을 호출 순서대로 준다
  - 기존 테스트 `test_fix2_completed_crash_resume_has_no_new_budget` — 이 step이 단언 한 곳을 바꾼다

## 배경

리뷰가 수정 예산을 다 쓰고 failed로 확정되면 `review.fixes`가 0으로 기록된다. 사람이 원인을 고치고 다시 기동하면 `review.status`가 `failed`이고 `fixes`가 0이라, 지금 코드는 라운드 번호를 `1`부터 다시 센다. `unverifiable`로 끝난 뒤 재기동해도 같다(Issue #31 항목 4, I-11 일부).

영향: `.run/review-r1-*.txt`를 덮어쓰고, "리뷰 r1 반영" 커밋 메시지가 중복되며, index의 `review.round`가 줄어 이력이 흐려진다.

고칠 방향: 새 예산을 받는 기동에서도 라운드 번호는 `review.round + 1`부터 이어 센다. **수정 예산을 다시 열어 주는 정책 자체는 바꾸지 않는다**(그 결정은 Issue #32 몫이다). 바뀌는 것은 번호뿐이다.

## 작업

### `Executor.review_gate()` (`scripts/execute.py`)

- fix 크래시 재개 분기(`self.resume`의 unit이 `fix{r}`)는 지금 그대로 둔다.
- 그 밖의 모든 경우 첫 라운드 번호는 `data["review"]["round"] + 1`이다. 처음 들어올 때 `round`는 0이므로 1이 된다. `status`가 `pending`이든 `failed`든 `unverifiable`이든, `fixes`가 0이든 아니든 같다.
- `fixes_used`(남은 수정 예산 계산)와 관문 확정 때 `fixes`를 0으로 되돌리는 규칙은 바꾸지 않는다.

### 테스트 (`scripts/test_execute.py`의 `FixLoopTests`)

- 기존 `test_fix2_completed_crash_resume_has_no_new_budget`의 마지막 부분("A new invocation after finalized failure receives a fresh two-fix budget.")에서 새 기동의 수정 unit 단언을 `['fix1', 'fix2']`에서 `['fix4', 'fix5']`로 바꾸고, 그 기동이 끝난 뒤 `review.round`가 `6`임을 단언한다. 새 예산(수정 2회)을 받는다는 뜻은 그대로다. 이 테스트의 다른 단언은 바꾸지 않는다.
  - 계산: 앞 기동이 r3에서 failed로 확정(`round=3`, `fixes=0`) → 새 기동은 r4 리뷰 → fix4 → r5 리뷰 → fix5 → r6 리뷰 failed → exit 3.
- 새 테스트 `test_unverifiable_rerun_continues_round` — 가짜 claude가 첫 기동에서 두 번 다 판정 줄 없이 끝나(`missing`) `run()`이 3·`review.status=unverifiable`·`review.round=1`로 끝나고, 다음 기동(새 `Executor`, 앞 기동의 잠금 파일은 닫는다)에서 둘 다 `passed`를 내면 `run()`이 0이고 `review.round`가 `2`다. 첫 기동이 쓴 `.run/review-r1-claude.txt`의 내용이 두 번째 기동 뒤에도 같고, `.run/review-r2-claude.txt`가 있다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
python3 scripts/test_execute.py -k test_fix2_completed_crash_resume_has_no_new_budget
python3 scripts/test_execute.py -k test_unverifiable_rerun_continues_round
python3 scripts/test_execute.py -k test_fix2_crash_resume_preserves_round_budget
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다. 전체 테스트는 3분 가까이 걸린다.
2. 체크리스트:
   - 수정 예산 규칙(`MAX_FIX_ROUNDS - review.fixes`, 관문 확정 때 0으로 되돌림, fix 크래시 재개는 새 예산 없음)이 그대로인가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 실행기가 한다.
   - `phases/31-harness-quick-fixes/.run/step2-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 바꾼 분기와 테스트 이름>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 수정 예산을 다시 열어 주는 조건(`MAX_FIX_ROUNDS`, `fixes`를 0으로 되돌리는 시점, 새 기동이 새 예산을 받는 규칙)을 바꾸지 마라. 이유: 그 정책은 Issue #32에서 정한다. 이 step은 번호만 이어 센다.
- 라운드 번호를 `review.fixes`에서 추론하거나, 남은 예산을 `review.round`에서 추론하지 마라. 이유: 문서가 두 값을 따로 정의한다(`round`는 라운드 번호, `fixes`는 완료한 수정 수).
- fix 크래시 재개 분기(`self.resume`)의 라운드·시도 번호 규칙을 바꾸지 마라. 이유: 기존 재개 테스트가 보장하는 동작이다.
- `.run/review-r*.txt`를 되읽어 라운드 번호를 정하지 마라. 이유: `.run/` 원문은 사람용 기록이고 실행기는 신뢰하지 않는다. 번호의 출처는 phase index의 `review.round`다.
- 기존 테스트를 지우거나 약하게 고치지 마라. 위에서 지정한 단언 한 곳만 바꾼다. 이유: 기존 동작 보장과 앞 step의 AC는 phase 끝까지 참이어야 한다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`, `AGENTS.md`, `docs/`를 수정하지 마라. 이유: 이 step의 범위 밖이다. 문서는 마지막 step이 맞춘다.
- `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 실행기가 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고는 예외).
- 저장소 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
