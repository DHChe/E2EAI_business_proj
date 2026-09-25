# Step 0: phase-index-check

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약과 Bash 안전 가드
- `docs/agents/harness.md` — "phases/{dir}/index.json" 절(스키마: `steps[].step`은 0부터 시작하는 순번, `name`은 kebab-case slug)과 "실행기 › 기동과 책임" 절의 6번 항목
- `scripts/execute.py`
  - `Executor.load_step_specs()` — 이 step이 고치는 함수
  - `Executor.run()` — `prepare()` 다음에 `load_step_specs()`를 부르고, 그 뒤에 `run_steps()`와 `review_gate()`를 부른다
  - `Executor.load_index()`, `load_top_index()`, `set_top_status()`, `HarnessExit`, `EXIT_ERROR`
- `scripts/test_execute.py`
  - `HarnessTestCase.make_repo(steps=None, files=None)` — `files`로 두 index 내용을 덮어쓸 수 있다
  - `HarnessTestCase.make_executor`, `fake_bin`, `calls`, 상수 `PHASE`(`7-sample`)·`ISSUE`(`7`)
  - 기본 덫: `setUp`이 `codex`·`claude`·`grok`·`gh`를 "불리면 종료 97" 가짜로 깔고, 호출을 `calls(name)`으로 기록한다
  - `StepSpecTests` 클래스 — 이 step의 테스트를 넣을 곳

## 배경

실행기(`scripts/execute.py`)는 phase의 step을 무인으로 돌리고 리뷰 관문까지 간다. 지금은 phase index의 `steps`가 빈 배열이어도 막지 않는다. `all([])`이 참이라 step을 하나도 돌리지 않고 곧장 리뷰 관문으로 가서, 리뷰어가 passed를 내면 phase가 `completed`로 끝난다(Issue #31 항목 2, 통합 목록 I-9).

재현: `make_repo(steps=[], files={'.claude/commands/review.md': 'Review.\n'})`에서 가짜 `claude`·`grok`이 `REVIEW_RESULT: passed`를 내면 `run()`이 0을 돌려주고, `review.status=passed`, 상위 phase `completed`로 끝난다.

## 작업

### `Executor.load_step_specs()` (`scripts/execute.py`)

step 파일을 읽기 전에 phase index 자체의 모양을 검사한다. 위반은 기존 step 파일 위반과 **같은 오류 목록에 모아** 하나라도 있으면 `HarnessExit(EXIT_ERROR, ...)`를 던진다. 메시지에는 위반마다 무엇이 잘못됐는지(기대값과 실제값)를 적는다.

검사할 것:

1. `steps`가 비어 있지 않은 list다.
2. `steps`의 `step` 값이 목록 순서대로 정확히 `0, 1, 2, …, len(steps)-1`이다(0부터 시작, 빠짐·중복·역순 없음).
3. `name`이 서로 겹치지 않는다.
4. phase index의 `phase`가 실행기의 `phase_dir`(디렉토리명)과 같다.
5. `phases/index.json`의 `phases`에 `dir`이 `phase_dir`인 항목이 **정확히 하나** 있고, 그 항목의 `issue`가 phase index의 `issue`와 같다.

`steps` 모양이 틀리면(1~3 위반) step 파일 읽기는 건너뛰어도 된다. 4·5 위반만 있으면 step 파일 위반도 함께 모아 보고한다.

지켜야 할 것:

- 검사는 `run()`에서 `run_steps()`와 `review_gate()`보다 **먼저** 끝나야 한다. 위반이면 구현 세션(`codex`)도, AC도, 리뷰어(`claude`·`grok`)도 부르지 않는다. 지금 `run()`의 호출 순서(`prepare()` → `load_step_specs()` → `run_steps()`)를 그대로 쓰면 된다. `prepare()`가 먼저 기록·커밋하는 것은 허용한다(기존 문서가 "앞선 복구·prepare는 이미 수행됐을 수 있다"고 적는다).
- 완료된 phase를 `--push`로 다시 돌리는 경로도 같은 검사를 거친다. 따로 우회로를 만들지 않는다.
- 기존 `load_step_specs()`의 규칙(HEAD에 커밋된 step 파일만 읽음, 오류 전수 수집, `self.specs` 고정)은 바꾸지 않는다.

### 필수 테스트 (`scripts/test_execute.py`의 `StepSpecTests`)

아래 이름 그대로 넣는다.

- `test_phase_index_rejects_empty_steps` — `make_repo(steps=[], files={'.claude/commands/review.md': 'Review.\n'})`로 만든 저장소에서(이 파일이 없으면 Grok 인자 생성이 OSError로 끝나 지금 코드도 exit 3이라 결함이 재현되지 않는다) 가짜 `claude`·`grok`이 `REVIEW_RESULT: passed` JSON을 내도록 깐다(`fake_bin`; Claude는 `{"result": ...}`, Grok은 `{"text": ...}`). `run()`이 1을 돌려주고, `calls('codex')`·`calls('claude')`·`calls('grok')`에 세션·리뷰 호출이 없고, phase index의 `review.status`가 `passed`가 아니며, 상위 phase `status`가 `completed`가 아니다.
- `test_phase_index_rejects_inconsistent_fields` — `subTest`로 아래 여섯 경우를 각각 새 저장소에서 확인한다. 모두 `run()`이 1이고 `self.calls('codex')`·`self.calls('claude')`·`self.calls('grok')`가 모두 `[]`이며(`codex mcp list` preflight 호출도 없어야 한다. 지금 코드도 preflight 실패로 exit 1이 나므로 반환값만으로는 구분되지 않는다), 오류 메시지(표준 오류 또는 `HarnessExit.message`)에 위반 종류가 드러난다.
  - `step` 번호가 `[0, 2]`
  - `step` 번호가 `[1]`
  - 두 step의 `name`이 같다
  - phase index의 `phase`가 `other-phase`
  - phase index의 `issue`가 `99`(상위 index 항목은 `7`)
  - `phases/index.json`에 `dir`이 `PHASE`인 항목이 없다

두 index는 `make_repo(files={...})`로 덮어써서 만든다. step 파일은 index와 맞든 안 맞든 필요한 만큼만 만든다.

## 변경 허용 경로

scripts/execute.py
scripts/test_execute.py

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 scripts/test_execute.py -k test_phase_index_rejects_empty_steps
python3 scripts/test_execute.py -k test_phase_index_rejects_inconsistent_fields
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다. 전체 테스트는 3분 가까이 걸린다.
2. 체크리스트:
   - `AGENTS.md`의 규칙을 어기지 않았는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 두 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - 테스트가 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 실행기가 한다.
   - `phases/31-harness-quick-fixes/.run/step0-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 바꾼 함수, 더한 검사와 테스트 이름>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- 빈 phase를 "할 일 없음"으로 보고 0으로 끝내게 만들지 마라. 이유: step 0개는 기획 실수이고, 리뷰만 돌아 완료로 기록되는 것이 이번 결함이다.
- 위반이 있는 phase에서 일부 step만 실행하게 만들지 마라. 이유: 전수 검증이 끝나기 전에는 아무것도 실행하지 않는다.
- step 이름의 kebab-case 형식 검사를 더하지 마라. 이유: 이번 범위는 Issue #31이 정한 네 가지(개수, 번호, 이름 중복, phase·issue 일치)뿐이다.
- 리뷰 관문, 리뷰어, AC 실행(`review_gate`, `run_reviewer`, `run_ac`, `run_baseline`)을 고치지 마라. 이유: 뒤 step이 맡는다.
- 기존 테스트를 지우거나 약하게 고치지 마라. 기존 fixture가 새 검사에 걸리면 fixture를 올바른 index로 고친다. 이유: 기존 147개 테스트는 계속 같은 동작을 보장해야 한다.
- `unittest.skip`, `skipIf`, `expectedFailure`, 빈 테스트, TODO 분기를 남기지 마라. 이유: 가짜 완료다.
- AC와 테스트에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- pip 의존성을 추가하지 마라. 이유: 표준 라이브러리만 쓴다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`, `docs/`를 수정하지 마라. 이유: 이 step의 범위 밖이다. 문서는 마지막 step이 맞춘다.
- `phases/31-harness-quick-fixes/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 실행기가 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 테스트용 임시 파일은 `tempfile`로 저장소 밖에 만든다. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 무시 파일을 고치지 마라. 이유: 롤백으로 복원되지 않는다(result 보고는 예외).
- 루트에 `.env`·`.env.*` 실제 값 파일이나 그 이름의 디렉토리를 만들지 마라(`.env.example`만, 가상환경은 `.venv`). 이유: 실제 값은 사람이 채우고, 실행기는 이 이름들을 보호 대상으로 보고 재시도 없이 멈춘다.
