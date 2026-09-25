# Step 4: harness-docs-sync

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약. "인용" 절(인용은 원문의 연속 부분문자열로만)
- `docs/PRD.md` — `:5`만 고친다
- `docs/agents/harness.md` — 이 step이 고치는 세 줄(아래 작업 절)과, 다른 문서가 줄 번호로 가리키는 일곱 줄
- `scripts/execute.py` — 앞 step이 바꾼 동작을 확인할 곳
  - `Executor.load_step_specs()` — phase index 모양 검사(step 0)
  - `Executor.run_reviewer()`, `restore_env(..., keep_new=...)`, `restore_env_change(..., keep_new=...)` — 리뷰어 `.env` 복원(step 1)
  - `Executor.review_gate()` — 라운드 번호 이어 세기(step 2)

## 배경

이 phase(`31-harness-quick-fixes`, Issue #31)의 step 0~3이 실행기 동작 세 가지를 바꿨다. 이 step은 규약 문서를 그 동작에 맞추고, 낡은 줄 번호 포인터 하나를 고친다.

1. step 0 — 기동 때 phase index를 검사한다. `steps`가 비었거나, `step`이 0부터 1씩 늘지 않거나, `name`이 겹치거나, `phase`가 디렉토리명과 다르거나, `phases/index.json`에 그 디렉토리 항목이 정확히 하나가 아니거나 `issue`가 그 항목과 다르면 exit 1이다.
2. step 1 — 리뷰어 전후에도 루트 `.env*`를 보관·복원한다. 바뀐 값과 지워진 파일은 되돌리고, 리뷰어가 새로 만든 `.env*`는 지우지 않고 이름을 사유에 남긴다. `.env`를 건드린 리뷰어는 `unverifiable`이다.
3. step 2 — 새 수정 예산을 받는 기동에서도 리뷰 라운드 번호를 `review.round + 1`부터 이어 센다.

`docs/PRD.md:5`는 `docs/agents/harness.md:183`을 가리키지만, 가리키려던 문장("가드레일 주입 — … `docs/PRD.md`를 step 프롬프트에 포함")은 `:186`에 있다. 실행기가 이 PRD를 모든 step 프롬프트에 주입하므로 틀린 포인터가 매번 퍼진다(Issue #31 항목 6, I-13 일부). 줄 번호 대신 절 이름으로 가리키게 고친다.

**줄 번호 제약** — 다른 문서가 이 두 파일을 줄 번호로 가리킨다. 그래서 두 파일 모두 **기존 줄을 제자리에서 고치기만 하고, 줄을 더하거나 빼지 않는다.**

- `docs/agents/harness.md`를 가리키는 줄: `:73`(상태 기계 표의 `blocked` 행), `:96`(7원칙 5번 "AC는 실행 가능한 커맨드"), `:156`(템플릿 금지사항 "변경 허용 경로 밖을 고치지 마라"), `:173`(구현은 Codex), `:186`(가드레일 주입), `:274`(리뷰어 계약문), `:289`(Grok 보호). ADR-0013·0016·0032·0033·0035, `docs/EVAL.md`, `docs/research/eval-plan-comparison.md`가 가리킨다. 전체 324줄을 유지한다.
- `docs/PRD.md`: ADR들이 여러 줄을 가리킨다. 전체 178줄을 유지한다.

## 작업

### `docs/PRD.md:5`

`(`docs/agents/harness.md:183`)`을 `(`docs/agents/harness.md` "기동과 책임" 절의 "가드레일 주입" 항목)`으로 바꾼다. 줄의 나머지 문장은 그대로 둔다.

### `docs/agents/harness.md` (세 줄을 제자리에서)

- `:183`("기동과 책임" 절 6번 항목) — 첫 문장 "HEAD에 커밋된 모든 step 파일의 허용 경로와 AC를 검증해 고정한다." 바로 뒤에 다음 문장을 넣는다: "phase index의 `steps`가 비었거나, `step`이 0부터 1씩 늘지 않거나, `name`이 겹치거나, `phase`가 디렉토리명과 다르거나, `phases/index.json`에 그 디렉토리 항목이 정확히 하나가 아니거나 `issue`가 그 항목과 다른 것도 위반이다." 나머지 문장은 그대로 둔다.
- `:276`("리뷰 관문·수정 루프" 절, "리뷰어 전후 브랜치·HEAD·porcelain·루트 `.env` 및 위 Git 설정 비교·복원 규칙을 적용한다."로 시작하는 줄) — 첫 문장 바로 뒤에 다음 문장을 넣는다: "`.env`는 바뀐 값과 지워진 파일만 보관본으로 되돌리고, 리뷰어가 새로 만든 `.env*`는 지우지 않은 채 이름을 사유에 남기며 그 리뷰어를 unverifiable로 판정한다." 나머지 문장은 그대로 둔다.
- `:285`("그 밖의 failed에서만 수정 루프를 돌린다."로 시작하는 줄) — 줄 끝에 다음 문장을 붙인다: "라운드 번호는 새 예산을 받은 기동에서도 `review.round + 1`부터 이어 센다."

## 변경 허용 경로

docs/PRD.md
docs/agents/harness.md

## Acceptance Criteria

```bash
! grep -qF 'harness.md:183' docs/PRD.md
sed -n 5p docs/PRD.md | grep -qF '(`docs/agents/harness.md` "기동과 책임" 절의 "가드레일 주입" 항목)'
test "$(wc -l < docs/PRD.md)" -eq 178
test "$(wc -l < docs/agents/harness.md)" -eq 324
sed -n 183p docs/agents/harness.md | grep -qF '항목이 정확히 하나가 아니거나 `issue`가 그 항목과 다른 것도 위반이다'
sed -n 276p docs/agents/harness.md | grep -qF '리뷰어가 새로 만든 `.env*`는 지우지 않은 채 이름을 사유에 남기며'
sed -n 285p docs/agents/harness.md | grep -qF '라운드 번호는 새 예산을 받은 기동에서도 `review.round + 1`부터 이어 센다.'
sed -n 73p docs/agents/harness.md | grep -qF '| `blocked`'
sed -n 96p docs/agents/harness.md | grep -qF 'AC는 실행 가능한 커맨드'
sed -n 156p docs/agents/harness.md | grep -qF '변경 허용 경로 밖을 고치지 마라'
sed -n 173p docs/agents/harness.md | grep -qF '구현은 Codex(`codex exec`)'
sed -n 186p docs/agents/harness.md | grep -qF '가드레일 주입'
sed -n 274p docs/agents/harness.md | grep -qF '계약문은 파일 변경·커밋·push'
sed -n 289p docs/agents/harness.md | grep -qF 'Grok은 `guard-bash.py`를 실행하지 않는다'
python3 .claude/hooks/test_guard_bash.py
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - 넣은 문장이 `scripts/execute.py`의 실제 동작과 맞는가? 맞지 않으면 문서를 억지로 맞추지 말고 error로 보고한다.
   - 두 파일의 줄 수가 그대로인가? `git diff --numstat`에서 두 파일 모두 더한 줄 수와 뺀 줄 수가 같아야 한다.
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다.
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 실행기가 한다.
   - `phases/31-harness-quick-fixes/.run/step4-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 고친 줄 번호와 내용>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음: `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 두 파일에 줄을 더하거나 빼지 마라. 이유: ADR과 `docs/EVAL.md`가 두 파일을 줄 번호로 가리킨다. 줄이 밀리면 그 포인터가 모두 틀린다.
- 위에서 지정한 네 곳 말고는 고치지 마라(오타·표현 다듬기 포함). 이유: 요청 범위 밖 변경은 리뷰에서 무관한 변경으로 걸린다.
- `phases/24-harness-executor/`의 step 파일을 고치지 마라. 이유: 완료된 phase의 기록이다.
- 다른 문서의 줄 번호 포인터(ADR, `docs/EVAL.md`, `docs/research/`)를 고치지 마라. 이유: 이 step의 허용 경로 밖이고, 줄 수를 유지하면 그대로 맞다.
- `AGENTS.md`를 고치지 마라. 이유: Issue #31 triage에서 "리뷰어 도중이면 지우지 않고 멈춘다"를 새 파일 규칙으로 읽기로 정해 문장을 그대로 둔다.
- `scripts/`, `.claude/`, `.codex/`, `.gitignore`를 수정하지 마라. 이유: 이 step은 문서만 맞춘다.
- `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 실행기가 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고는 예외).
- 저장소 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
