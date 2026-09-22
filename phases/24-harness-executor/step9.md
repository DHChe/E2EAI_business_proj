# Step 9: harness-docs

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `AGENTS.md` — 저장소 규약. `### Bash 안전 가드` 절을 고친다. `<!-- graft:start -->`~`<!-- graft:end -->` 블록은 도구가 관리하므로 건드리지 않는다
- `CONTEXT.md` — 용어집
- `docs/agents/harness.md` — 전체. 이 step이 가장 많이 고치는 파일이다
- `.claude/commands/harness.md`, `.claude/commands/review.md`
- `docs/PRD.md` — `:5`만 고친다
- `docs/agents/triage-labels.md`, `docs/agents/issue-tracker.md` — 라벨과 `gh` 사용법
- `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:55`, `docs/adr/0016-record-and-replay-model-calls.md:12` — `docs/agents/harness.md:73`과 `:96`을 가리키는 포인터. ADR은 이 step에서 고칠 수 없다
- `.codex/hooks.json`, `.gitignore`
- `scripts/execute.py`, `scripts/test_execute.py` — step 0~8의 산출물인 완성된 실행기와 테스트. 문서는 **이 코드의 실제 동작**을 적는다

## 배경

이 phase(`24-harness-executor`, Issue #24)는 phase의 step을 무인으로 끝까지 돌리는 실행기 `scripts/execute.py`를 만들었다(step 0~8). 사람은 세 곳만 맡는다. 앞단은 기획과 phase 승인, 중간은 `blocked` 해소와 `error` 복구, 뒷단은 Issue close와 병합이다.

그런데 문서는 아직 "실행기는 기술 스택 확정 후 도입하고 그때까지 손으로 실행한다"고 적고 있다. 이 step은 문서 다섯 개를 실행기에 맞춘다. 코드는 고치지 않는다.

## 작업

### 먼저: 줄 번호 고정 조건

다른 문서가 줄 번호로 가리키는 곳이 있다. 이 step은 그 문서들을 고칠 수 없으므로, 가리켜지는 줄이 제자리에 있어야 한다.

- `docs/agents/harness.md:73`은 상태 기계 표의 `blocked` 행이다(ADR-0016 `:12`가 가리킨다). 작업 뒤에도 73번째 줄이 `` | `blocked` ``로 시작하는 그 행이어야 한다. 의미 칸("사람만 풀 수 있음(API 키, 외부 인증, 수동 설정)")은 그대로 둔다.
- `docs/agents/harness.md:96`은 7원칙 5번 "**AC는 실행 가능한 커맨드**"의 첫 줄이다(ADR-0013 `:55`, ADR-0016 `:12`가 가리킨다). 작업 뒤에도 96번째 줄에 `AC는 실행 가능한 커맨드`가 있어야 한다.
- 따라서 `harness.md`는 1~72줄 구간과 74~95줄 구간에서 **줄 수의 순증감이 0**이어야 한다. 이 구간의 수정은 기존 줄을 제자리에서 바꾸는 방식으로 한다. 늘어나는 설명은 97줄 이후(템플릿과 실행기 절)에 둔다.
  - 예: 디렉토리 그림은 `step{N}-output.json` 줄을 `.run/` 줄로 바꾼다.
  - 예: 스키마 필드는 `:64` 한 줄을 고쳐 담는다.
- `docs/PRD.md`는 ADR-0012·0013·0014·0015가 `:45`, `:131`, `:141`, `:154`, `:160`, `:161`, `:172`, `:173`을 가리킨다. `:5` 한 줄만 제자리에서 고치고 **전체 줄 수 178을 유지**한다.
- 작업 전후로 `sed -n 73p docs/agents/harness.md`, `sed -n 96p docs/agents/harness.md`, `wc -l docs/PRD.md`를 확인한다.

### 실행기 사실 (문서의 근거)

아래는 step 0~8이 구현한 설계다. 문서를 쓰기 전에 `scripts/execute.py`에서 하나씩 확인한다. 코드와 이 목록이 다르면 문서는 **코드 동작**을 적고, 차이를 result의 `summary`에 적는다.

1. **실행과 역할**
   - 저장소 안에서 `python3 scripts/execute.py <phase_dir> [--push]`로 실행한다. 저장소 루트는 cwd의 `git rev-parse --show-toplevel`이다.
   - 모델 역할: 기획은 Claude(`/harness`), 구현은 Codex(`codex exec`), 리뷰는 Claude와 Grok이다.
2. **기동 순서:** 잠금 → marker 복구 → gh 대기열 재시도 → 시작 전 검사 → step 파일 전수 검증(HEAD 기준) → step 실행 → 리뷰 관문과 수정 루프 → (`--push`면) push.
3. **시작 전 검사**
   - `feat-{phase}` 브랜치를 먼저 checkout한다(없으면 현재 HEAD에서 만든다).
   - 작업 트리 변경은 `phases/{dir}/` 아래 무시되지 않는 파일만 허용한다. 그중 `index.json`의 diff는 둘만 허용한다.
     - (a) 마지막 `error`/`blocked` step을 `pending`으로 되돌리고 그 step의 `error_message`·`blocked_reason`·`failed_at`·`blocked_at`을 지운 것
     - (b) `review.status`를 `blocked`에서 `pending`으로 되돌리고 `review.blocked_reason`을 지운 것
   - 허용된 변경은 chore로 커밋한다.
   - 최초 실행이면 `created_at`, `base_commit`, `review`를 기록하고 첫 시도 전에 커밋한다.
   - `phases/index.json`은 실행기 소유다. 진행할 때 이 phase가 `error`/`blocked`면 `pending`으로 되돌린다.
   - 마지막 비-pending step이 `error`면 exit 1, `blocked`면 exit 2다. `review.status`가 `blocked`여도 exit 2다.
4. **step 파일 형식(실행기가 기계로 읽는다)**
   - `## 변경 허용 경로` 절: 한 줄에 경로 하나. 정확한 파일 경로 또는 `/`로 끝나는 디렉토리 접두사만 허용한다. glob 문자(`*?[`), 절대 경로, `..`, `:`로 시작하는 pathspec magic, `phases/`와 겹치는 경로는 거부한다.
   - `## Acceptance Criteria` 절: bash 블록이 정확히 1개다. 빈 줄과 `#` 주석을 뺀 각 줄이 독립 커맨드이고, `bash -o pipefail -c <줄>`로 줄마다 따로 실행해 모두 종료 0이어야 한다. `\`로 끝나는 줄, `<<`가 든 줄, `bash -n`을 통과하지 못하는 여러 줄 구문은 거부한다.
   - 위반이 하나라도 있으면 아무것도 실행하지 않고 exit 1이다.
5. **세션**
   - `codex exec`를 고정 argv로 띄운다. workspace-write 샌드박스, 네트워크 끔, 번들 플러그인·apps 끔이다.
   - 사용자 MCP 서버는 서버별 `-c`로 끄고, 끄지 못했으면 세션을 띄우지 않는다(fail-closed preflight).
   - 가드는 프로젝트 `.codex/hooks.json`이 `guard-bash.py`를 PreToolUse 훅으로 거는 것이다. `--ignore-user-config`를 주면 이 훅이 꺼지므로 쓰지 않는다.
   - 프롬프트는 stdin으로 준다. 담는 것은 가드레일 문서(`AGENTS.md`, `CONTEXT.md`, `docs/adr/*.md`, `docs/PRD.md`), 완료된 step의 summary, step 파일, 허용 경로, result 계약, 금지 사항, 재시도면 직전 실패 사유다.
6. **세션 보고**
   - 세션은 시도 하나만 하고 `phases/{dir}/.run/<unit>-result.json`에 보고한다. 필드는 `status`(`completed`|`error`|`blocked`), `summary`, `error_message` 또는 `blocked_reason`이다. unit은 `step{N}` 또는 `fix{r}`다.
   - 세션은 index를 쓰지 않고 커밋하지 않는다(샌드박스에서 `.git`은 쓰기 불가).
   - 실행기는 시도 전에 그 result를 지운다. 두 index는 실행기만 쓰고, 시도 중에는 실행기도 쓰지 않는다.
7. **시도 판정**(모두 참이어야 통과)
   - ① 이번 시도의 result가 `completed`이고 `summary`가 있다
   - ② HEAD가 시도 전과 같다
   - ③ 변경 경로가 허용 경로 안이다
   - ④ 저장소 루트 바로 아래의 `.env`·`.env.*`(`.env.example` 제외) 해시가 같다. 하위 디렉토리는 보지 않는다
   - ⑤ `.run/`·`__pycache__/`·`*.pyc` 밖에 새 무시 경로가 없다
   - ⑥ AC가 전부 종료 0이다
   - ⑦ AC 전후 HEAD와 작업 트리 tree sha가 같다
8. **재시도와 롤백**
   - unit당 최대 3회다. 재시도 프롬프트에 직전 실패 사유가 들어간다.
   - 실패한 시도는 먼저 작업 트리 밖 임시 index로 스냅샷을 만들어 `refs/harness/<phase>/<unit>/attempt<k>-<epoch>`에 남긴다(push하지 않는다). 그다음 실행기 프로세스가 `git reset --hard <pre_sha>`, `git clean -fd`(`-x` 없음)로 되돌린다. 되돌린 뒤 `git status --porcelain`이 비지 않으면 exit 1이다.
   - 스냅샷이 실패하면 파괴 명령을 실행하지 않고 exit 1이다.
   - reset 직전에 HEAD가 `feat-{phase}` 브랜치인지(`git symbolic-ref -q HEAD`) 확인한다. 아니면 스냅샷만 남기고 reset 없이 exit 1이다.
   - `blocked`는 롤백하고 시도 횟수에 넣지 않으며, index를 `blocked`로 확정한 뒤 exit 2다.
   - ④가 깨지면 롤백 뒤 재시도 없이 `error`다.
9. **커밋**
   - 순서: 검증 → `feat` 커밋 → marker `feat_done` → index 확정 → 두 index만 `chore` 커밋 → marker 삭제.
   - `feat` 커밋은 변경된 허용 경로만 literal pathspec으로 add한다. 변경이 없으면 생략한다.
   - 모든 커밋은 HEAD가 `feat-{phase}` 브랜치일 때만 한다. 아니면 커밋 없이 exit 1이다.
   - 실제 index에 `git add -A`를 쓰지 않는다. 예외는 스냅샷용 임시 index다.
   - 메시지: `feat: <phase> step{N} <name> (#<issue>)`, `fix: <phase> 리뷰 r{r} 반영 (#<issue>)`, `chore: <phase> <상태> (#<issue>)`.
10. **잠금·marker·복구**
    - worktree 단위 잠금 `phases/.run/lock`에 flock을 건다. 같은 worktree의 두 번째 실행기는 phase가 달라도 exit 1이다.
    - **marker 불변식:** marker는 시도가 진행 중이거나 feat 커밋과 chore 커밋 사이일 때만 존재한다. unit을 끝내는 모든 경로는 chore 뒤에 marker를 지운다.
    - `.run/`은 세션이 쓸 수 있으므로 실행기는 marker를 메모리 값으로 다시 쓰고, `gh` 대기열은 정해진 모양만 실행한다.
    - `.run/attempt.json` marker는 `{unit, k, pre_sha, stage, feat_sha, pgid}`다.
    - 기동 시 복구는 셋이다.
      - ① `stage=running`이고 HEAD가 `pre_sha`면 남은 세션 그룹을 죽인다. 그 그룹에 codex 프로세스가 있을 때만 죽인다. 그다음 롤백하고 marker를 지운 뒤 k+1로 이어 간다. 다음 시도 번호는 메모리에만 있다.
      - ② `stage=feat_done`이고 HEAD가 `feat_sha`면 chore만 이어서 한다.
      - ③ 그 밖이면 아무것도 건드리지 않고 exit 1이다(marker 경로와 사유를 출력한다).
    - SIGINT·SIGTERM·SIGHUP에는 자식 프로세스 그룹을 죽이고 marker를 남긴다.
11. **리뷰 관문**
    - 진입: 모든 step이 completed이고 `review.status`가 `passed`가 아니면 들어간다.
    - 먼저 `end_sha`(= HEAD)에서 전 step AC 기준선을 돌린다. 실패하면 리뷰 없이 phase `error`, exit 1이다.
    - Claude와 Grok을 순차로 돌린다. Claude는 `/review <base_commit>..<end_sha>`와 계약문을 받고, Grok은 `review.md` 본문과 범위, 계약문을 받는다.
    - 리뷰어 전후로 브랜치·HEAD·porcelain·`.env` 해시를 검사한다. 브랜치가 바뀌었으면 스냅샷만 남기고 되돌리지 않은 채 exit 1이다. 나머지가 어긋나면 스냅샷 뒤 되돌리고 그 리뷰어는 `unverifiable`이다.
    - 판정은 결과의 마지막 비어 있지 않은 줄 `REVIEW_RESULT: passed|failed`다. 없거나 비정상이면 1회 재시도하고, 그래도 없으면 `unverifiable`이다.
    - 결과: 둘 다 passed면 phase `completed`다. 하나라도 `unverifiable`이면 수정 없이 exit 3이다. 그 밖이면 수정 루프로 간다.
    - 리뷰 원문은 `.run/review-r{r}-{claude|grok}.txt`에 남는다.
12. **수정 루프**
    - `failed`일 때만 돈다. 기동당 최대 2라운드이고, unit은 `fix{r}`다.
    - 허용 경로는 전 step의 합집합이고, AC는 전 step AC다. 판정·3회 시도·롤백은 step과 같다.
    - 통과하면 fix 커밋 → 재리뷰다.
    - 2라운드 뒤에도 failed거나 시도를 소진하면 `review.status=failed`, phase `error`, exit 3이다.
    - 수정 세션이 blocked면 `review.status=blocked`, phase `blocked`, exit 2다. 재개는 3의 (b)다.
13. **Issue 반영**(`gh`는 실행기만 쓴다)
    - 라벨은 `ready-for-agent`와 `ready-for-human` 사이의 remove/add만 한다. 다른 라벨은 유지한다.
    - `blocked`면 `ready-for-human`으로 바꾸고 사유 댓글을 단다. 재개할 때 라벨이 여전히 `ready-for-human`이고 `ready-for-agent`가 없으면 되돌린다.
    - `error`, 리뷰 실패, `unverifiable`이면 댓글을 단다(리뷰 요약 포함). phase 완료면 요약 댓글과 두 리뷰 댓글을 단다.
    - 실패한 `gh` 명령은 `.run/gh-pending.json`에 쌓이고 다음 기동 때 시작 전 검사 전에 재시도된다. phase 결과는 바꾸지 않는다.
    - 재시도하는 것은 실행기가 만드는 두 모양(이 Issue의 comment, `ready-for-agent`↔`ready-for-human` 라벨 edit)뿐이다. 그 밖의 항목은 실행하지 않고 버린다.
    - close와 병합은 사람이 한다.
14. **`--push`**
    - 선택 플래그이고 기본은 꺼져 있다. 리뷰 통과 뒤 `git push -u origin feat-{phase}`를 하고 force는 쓰지 않는다.
    - 실패하면 exit 1이고 phase는 `completed`로 남는다. 완료된 phase를 `--push`로 다시 실행하면 push만 한다.
15. **종료 코드:** 0 = 전 step 완료와 리뷰 통과(+push), 1 = `error`·내부 실패·push 실패, 2 = `blocked`, 3 = 리뷰 실패·`unverifiable`.
16. **timeout:** 세션 1800초, AC 줄당 600초, 리뷰어 1800초, `gh` 명령당 60초.
17. **자식 env**
    - 세션·AC·리뷰어는 정리된 env를 받는다. `GH_TOKEN`·`GITHUB_TOKEN`·`SSH_AUTH_SOCK`을 지우고, `GH_CONFIG_DIR`는 빈 임시 디렉토리, `PYTHONDONTWRITEBYTECODE=1`이다. Codex 세션은 `ORCA_*`도 지운다.
    - `gh` 래퍼와 push만 원래 env를 쓴다.
18. **`.run/`(gitignore)**
    - phase의 `phases/{dir}/.run/`: `attempt.json`, `<unit>-result.json`, `<unit>-last.txt`, `<unit>-session.jsonl`, `review-r{r}-{claude|grok}.txt`, `gh-pending.json`
    - worktree 공용 `phases/.run/`: `lock`
19. **알려진 한계**
    - 무시 파일은 되돌리지 않는다. ④·⑤가 감지만 한다. 기존 무시 디렉토리 안의 제자리 수정과, 루트가 아닌 곳의 `.env` 파일 변경은 감지하지 못한다.
    - Grok 리뷰어는 `guard-bash.py`를 실행하지 않는다. 보호는 사후 검사·되돌림, 자격 증명 제거, 계약문뿐이다.

### 파일별 수정

**`docs/agents/harness.md`**
- `:3` "여러 Claude 세션"을 모델 중립 표현(예: "여러 에이전트 세션")으로 바꾼다.
- `:20` close 규칙을 바꾼다. close와 병합은 사람이 한다. 실행기는 리뷰 관문까지 가고 phase 완료 요약 댓글을 단다.
- `:31` 디렉토리 그림의 `step{N}-output.json` 줄을 `.run/` 줄(실행기 산출물, gitignore)로 바꾼다. 실행기가 `step{N}-output.json`을 더는 만들지 않는지 코드로 확인한다.
- 스키마(`:34-64`)에 `created_at`·`base_commit`·`review{status, end_sha, round, blocked_reason?}`를 실행기가 기록하는 필드로 적는다. 줄 수를 늘리지 않는다. 자세한 의미는 실행기 절에 둔다.
  - `phases/index.json`이 실행기 소유라는 점도 적는다.
  - 코드가 기록하지 않는 필드(예: `started_at`)를 실행기가 기록한다고 적은 곳(`:64`, `:70`)은 코드에 맞춰 제자리에서 고친다.
- 상태 기계 표(`:68-73`)는 제자리에서 고친다.
  - `:73` Issue 열은 `ready-for-human` 하나다. 문자열 `` `needs-info` 또는 ``이 사라져야 한다.
  - `:71`의 close 표현과 `:72`의 Issue 열은 13(Issue 반영)과 맞춘다.
  - 세션이 index가 아니라 result 파일로 보고한다는 점이 표 머리나 칸에서 어긋나면 제자리에서 맞춘다.
- 복구(`:81-84`)는 제자리에서 고친다. 3의 (a)와 함께 리뷰 blocked 재개인 (b)를 기존 줄 안에 담는다.
- `:96-97`은 첫 줄의 `AC는 실행 가능한 커맨드` 문구를 유지한다. `:97`은 제자리에서 "실행기가 줄마다 따로 실행한다" 정도로 다듬어도 된다.
- 템플릿(`:101-141`)
  - `## 작업`과 `## Acceptance Criteria` 사이에 `## 변경 허용 경로` 절을 넣는다. 형식 규칙은 4를 따른다.
  - AC 절 안내에 줄 단위 실행 규칙(4)을 적는다.
  - 다음 세 문장을 템플릿 안(AC 안내 또는 금지사항)에 그대로 넣는다.
    - "AC는 반복 실행해도 되는 격리 자원(세계 격리·replay)을 쓴다."
    - "AC·빌드·테스트가 만드는 파일은 `.gitignore` 대상이어야 한다."
    - "step AC는 phase 끝까지 참이어야 한다."
  - `## 검증 절차` 3번을 바꾼다. index 갱신 지시를 "한 시도만 하고 `phases/{dir}/.run/step{N}-result.json`에 보고한다"로 바꾸고 result 필드를 적는다. index를 쓰지 않고 커밋하지 않는다는 점도 적는다. 문자열 "3회 시도 후에도 실패"가 사라져야 한다.
- 실행기 절(`:143-160`)은 1~19를 근거로 다시 쓴다.
  - `:145`의 "기술 스택 확정 후 도입한다. 그때까지 phase는 손으로 실행한다"를 지운다.
  - 담을 것: 실행 방법과 모델 역할, 책임 목록, 종료 코드, 시도 판정 ①~⑦, 롤백 예외(임시 index의 `add -A`, `reset --hard`·`clean -fd`는 실행기 프로세스만, 스냅샷 ref `refs/harness/`), 잠금, 복구, timeout, `.run/`.
  - 가드레일 주입 항목("`AGENTS.md`, `CONTEXT.md`, `docs/adr/*.md`, `docs/PRD.md`를 step 프롬프트에 포함")은 한 줄 항목으로 남긴다. 그 한 줄 안에 문자열 `docs/PRD.md`가 있어야 한다. `docs/PRD.md:5`가 그 줄을 가리키고, AC가 그 줄에서 `docs/PRD.md`를 찾는다.
  - 실행기 절을 다시 쓰면 이 줄의 번호가 바뀐다. **`docs/PRD.md:5`의 포인터도 반드시 함께 갱신한다.**
  - `:160`의 "위 6개 항목"은 목록과 개수가 맞지 않게 되므로 개수 없이 다시 쓴다. 원본(`https://github.com/jha0313/harness_framework`)을 그대로 복사하지 말라는 문장은 유지한다.

**`.claude/commands/harness.md`**
- D절: 사용자가 승인하면 phase 파일(`phases/index.json`, `phases/{dir}/index.json`, `step*.md`)을 만들고 **한 chore 커밋으로 커밋한다.** 실행기는 HEAD에 커밋된 step 파일만 읽는다.
  - step 파일마다 `## 변경 허용 경로` 절이 있어야 한다.
  - 타임스탬프 필드를 넣지 않는다는 규칙과 Issue 본문 `Phase:` 줄 규칙은 유지한다.
- E절: `:53`의 "기술 스택 확정 전까지 `scripts/execute.py`는 없다"를 지운다.
  - 실행은 `python3 scripts/execute.py <phase_dir>`(`--push`는 선택)이다.
  - 종료 코드별 사람의 할 일을 적는다. 1과 2는 복구 절차대로 원인을 고치고 index를 `pending`으로 되돌려 재실행한다. 3은 `.run/review-r*` 원문을 본다.
  - close와 병합은 사람이 한다.
  - 손 실행은 실행기가 없거나 쓸 수 없을 때만 한다(예: 실행기 자체를 만드는 phase). 그때의 절차는 기존 1~4를 AC 줄 단위 실행에 맞춰 남긴다.

**`.claude/commands/review.md`**
- 2절(변경 범위): 범위가 인자로 주어지면(`$ARGUMENTS`, 예: `<base>..<end>`) 그 범위를 쓰고 **묻지 않는다.** 인자가 없을 때만 지금처럼 추측하지 말고 물어본다(`:18`).
- 4절(출력): 출력의 **마지막 줄**은 정확히 `REVIEW_RESULT: passed` 또는 `REVIEW_RESULT: failed`다. ❌가 하나라도 있으면 `failed`다.
- frontmatter는 유지한다.

**`AGENTS.md`**(`### Bash 안전 가드` 절에 더한다)
- 실행기 롤백 예외: `git reset --hard`와 `git clean -fd`는 실행기(`scripts/execute.py`) 프로세스만 실행한다. 반드시 `refs/harness/` 스냅샷 뒤다. 세션과 사람에게는 여전히 금지다.
- Codex 세션은 `.codex/hooks.json`으로 같은 `guard-bash.py`를 받는다. `--ignore-user-config`는 이 훅을 끄므로 쓰지 않는다.
- Grok은 이 가드를 실행하지 않는다(가드 밖). Grok 리뷰어의 보호는 사후 HEAD·트리 검사와 되돌림, 자격 증명 제거, 계약문뿐이다.

**`docs/PRD.md`**
- `:5`의 주입 주체를 `/harness`에서 실행기(`scripts/execute.py`)로 바꾼다.
- 포인터 `docs/agents/harness.md:150`을 새 실행기 절의 가드레일 주입 줄 번호로 갱신한다. `:5`에는 `harness.md:<숫자>` 형태의 포인터가 **정확히 하나**만 있어야 한다. AC가 그 숫자를 뽑아 그 줄을 검사한다.
- 한 줄 제자리 수정이다. 그 줄의 나머지 문장은 유지한다.

## 변경 허용 경로

docs/agents/harness.md
.claude/commands/harness.md
.claude/commands/review.md
AGENTS.md
docs/PRD.md

## Acceptance Criteria

```bash
python3 scripts/test_execute.py
! python3 scripts/test_execute.py -k __no_such_test__
python3 .claude/hooks/test_guard_bash.py
sed -n 96p docs/agents/harness.md | grep -qF 'AC는 실행 가능한 커맨드'
sed -n 73p docs/agents/harness.md | grep -qF '| `blocked`'
test "$(wc -l < docs/PRD.md)" -eq 178
n=$(sed -n 5p docs/PRD.md | grep -o 'harness.md:[0-9]*' | cut -d: -f2) && test -n "$n" && sed -n "${n}p" docs/agents/harness.md | grep -qF 'docs/PRD.md'
grep -qF 'REVIEW_RESULT' .claude/commands/review.md
grep -qF '$ARGUMENTS' .claude/commands/review.md
grep -qF '변경 허용 경로' docs/agents/harness.md
grep -qF '.codex/hooks.json' AGENTS.md
grep -qF 'refs/harness/' docs/agents/harness.md
! grep -qF '기술 스택 확정 후' docs/agents/harness.md .claude/commands/harness.md .claude/commands/review.md AGENTS.md docs/PRD.md
! grep -qF '기술 스택 확정 전까지' docs/agents/harness.md .claude/commands/harness.md .claude/commands/review.md AGENTS.md docs/PRD.md
! grep -qF '3회 시도 후에도 실패' docs/agents/harness.md .claude/commands/harness.md .claude/commands/review.md AGENTS.md docs/PRD.md
! grep -qF 'needs-info` 또는' docs/agents/harness.md .claude/commands/harness.md .claude/commands/review.md AGENTS.md docs/PRD.md
! grep -qF '여러 Claude 세션' docs/agents/harness.md .claude/commands/harness.md .claude/commands/review.md AGENTS.md docs/PRD.md
```

## 검증 절차

1. 저장소 루트에서 위 AC 블록의 각 줄을 **한 줄씩 따로** 실행한다(`bash -o pipefail -c '<줄>'`). 모든 줄이 종료 0이어야 한다.
2. 체크리스트:
   - `sed -n 73p docs/agents/harness.md`가 `blocked` 행이고 의미 칸에 "API 키"가 남아 있는가? `sed -n 96p`가 7원칙 5번 첫 줄인가?
   - `wc -l docs/PRD.md`가 178인가? 실행기 절을 다시 쓴 뒤 PRD `:5`의 포인터를 갱신했는가? 그 포인터가 가리키는 `harness.md` 줄(`sed -n <그 줄>p docs/agents/harness.md`)이 가드레일 주입 항목인가? AC의 포인터 줄이 이것을 기계로 확인한다.
   - 문서의 실행기 서술이 `scripts/execute.py`의 실제 동작과 맞는가? 종료 코드, 판정 항목, `.run/` 파일, 커밋 메시지 형식을 코드와 대조한다.
   - 세션이나 사람이 `reset --hard`·`clean`을 써도 된다고 읽히는 문장이 없는가?
   - `AGENTS.md`의 graft 블록이 그대로인가? 표와 목록의 Markdown이 깨지지 않았는가?
   - 바뀐 파일이 `## 변경 허용 경로`의 다섯 파일뿐인가? `git status --porcelain`으로 확인한다. 무시 파일은 제외다.
   - `CONTEXT.md`, `docs/adr/`, `AGENTS.md`의 규칙과 어긋나지 않는가?
3. 결과를 보고하고 끝낸다. 이 세션은 **한 번만 시도**한다. 재시도, 롤백, 커밋은 바깥이 한다.
   - `phases/24-harness-executor/.run/step9-result.json`에 JSON 객체 하나를 쓴다. 디렉토리가 없으면 만든다(gitignore 대상이다).
   - 통과: `{"status": "completed", "summary": "<산출물 한 줄 요약: 고친 문서와, 코드와 설계가 달랐던 곳이 있으면 그 내용>"}`
   - 실패: `{"status": "error", "summary": "...", "error_message": "<구체적 에러>"}`
   - 사람만 풀 수 있음(자격 증명, 외부 인증, 샌드박스가 막는 설정): `{"status": "blocked", "summary": "...", "blocked_reason": "<사유>"}`를 쓰고 즉시 중단한다.
   - `phases/24-harness-executor/index.json`과 `phases/index.json`은 수정하지 않는다. 커밋하지 않는다. 샌드박스에서 `.git`은 쓰기 불가다.

## 금지사항

- `scripts/`를 고치지 마라. 이유: 코드는 step 0~8에서 끝났고 문서가 코드를 따른다. 코드와 설계가 다르면 코드 동작을 문서에 적고 summary에 남긴다.
- `docs/adr/`를 고치지 마라. 이유: 허용 경로 밖이다. ADR의 포인터는 줄 번호를 지켜서 유지한다.
- `docs/agents/harness.md`의 73번째 줄과 96번째 줄을 다른 내용으로 밀어내지 마라. 이유: ADR-0013 `:55`와 ADR-0016 `:12`가 그 줄을 가리킨다.
- `docs/PRD.md`의 줄 수를 바꾸지 마라. 이유: 여러 ADR이 PRD의 줄 번호를 가리킨다.
- `AGENTS.md`의 graft 블록을 고치지 마라. 이유: 도구가 관리하는 블록이다.
- 세션이나 사람에게 `git reset --hard`·`git clean`을 허용하는 문장을 쓰지 마라. 이유: 예외는 스냅샷을 먼저 남기는 실행기 프로세스뿐이다.
- 설명 문장에 낡은 문구("기술 스택 확정 후", "기술 스택 확정 전까지", "3회 시도 후에도 실패", `` `needs-info` 또는 ``, "여러 Claude 세션")를 인용으로라도 남기지 마라. 이유: AC가 그 문자열의 부재를 검사한다.
- 이 저장소의 실제 Issue에 `gh`로 댓글·라벨·본문 수정을 하지 마라. 이유: Issue 본문 갱신은 phase 착수 전에 사람이 했고, `gh` 쓰기는 실행기만 한다.
- `.claude/hooks/guard-bash.py`, `.gitignore`, `.codex/hooks.json`을 수정하지 마라. 이유: 가드는 무수정으로 재사용하고, 무시 규칙은 착수 전에 확정했다.
- 원본 하네스 구현(`jha0313/harness_framework`)의 문서나 코드를 복사하지 마라. 이유: 라이선스가 없다.
- AC에서 실제 `codex`, `claude`, `grok`, `gh`, 네트워크를 부르지 마라. 이유: AC가 결정적이어야 하고, 비용과 외부 부작용이 생긴다.
- `phases/24-harness-executor/index.json`과 `phases/index.json`을 수정하지 마라. 이유: 두 index는 실행기(이 phase에서는 코디네이터)만 쓴다.
- 커밋, stash, checkout, reset, push, `gh` 쓰기를 하지 마라. 이유: 커밋은 바깥이 검증한 뒤에 한다. 샌드박스에서 `.git`은 쓰기 불가다.
- `## 변경 허용 경로` 밖의 파일을 만들거나 고치지 마라. 이유: 허용 경로 밖 변경은 시도 실패로 판정된다.
- 기존 테스트를 깨뜨리지 마라. 이유: 이전 step의 AC는 phase 끝까지 참이어야 한다.
