# Issue tracker: GitHub

이 저장소의 이슈와 스펙은 GitHub 이슈로 관리한다. 모든 작업에 `gh` CLI를 사용한다.

## 규칙

- **이슈 생성**: `gh issue create --title "..." --body "..."`. 본문이 여러 줄이면 heredoc을 쓴다.
- **이슈 읽기**: `gh issue view <number> --comments`. 댓글은 `jq`로 걸러내고 라벨도 함께 가져온다.
- **이슈 목록**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`에 상황에 맞는 `--label`, `--state` 필터를 붙인다.
- **이슈에 댓글 달기**: `gh issue comment <number> --body "..."`
- **라벨 추가 / 제거**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **닫기**: `gh issue close <number> --comment "..."`

저장소는 `git remote -v`로 추론한다. 클론 안에서 실행하면 `gh`가 자동으로 처리한다.

## Pull request를 triage 대상으로 다루기

**PRs as a request surface: no.** _(이 저장소가 외부 PR을 기능 요청으로 취급한다면 `yes`로 바꾼다. `/triage`가 이 플래그를 읽는다.)_

`yes`로 설정하면 PR도 이슈와 같은 라벨과 상태를 거치며, 대응하는 `gh pr` 명령을 쓴다:

- **PR 읽기**: `gh pr view <number> --comments`, diff는 `gh pr diff <number>`.
- **triage할 외부 PR 목록**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`를 실행한 뒤 `authorAssociation`이 `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `NONE`인 것만 남긴다(`OWNER`/`MEMBER`/`COLLABORATOR`는 제외).
- **댓글 / 라벨 / 닫기**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub은 이슈와 PR이 번호 공간 하나를 공유하므로 `#42`만으로는 어느 쪽인지 알 수 없다. `gh pr view 42`로 먼저 확인하고, 실패하면 `gh issue view 42`로 확인한다.

## 스킬이 "publish to the issue tracker"라고 할 때

GitHub 이슈를 생성한다.

## 스킬이 "fetch the relevant ticket"이라고 할 때

`gh issue view <number> --comments`를 실행한다.

## Wayfinding 작업

`/wayfinder`가 사용한다. **map**은 이슈 하나이고, **child** 이슈들이 티켓이다.

- **Map**: `wayfinder:map` 라벨이 붙은 이슈 하나. Notes / Decisions-so-far / Fog 본문을 담는다. `gh issue create --label wayfinder:map`.
- **Child ticket**: map에 GitHub sub-issue로 연결된 이슈(sub-issues 엔드포인트에 `gh api` 사용). sub-issue를 쓸 수 없으면 map 본문의 task list에 child를 추가하고 child 본문 맨 위에 `Part of #<map>`을 적는다. 라벨은 `wayfinder:<type>`(`research`/`prototype`/`grilling`/`task`). claim된 티켓은 작업을 진행하는 개발자에게 assign된다.
- **Blocking**: GitHub의 **네이티브 이슈 의존성**을 쓴다. UI에 보이는 표준 표현이다. `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`로 간선을 추가한다. `<blocker-db-id>`는 blocker의 숫자 **database id**다(`gh api repos/<owner>/<repo>/issues/<n> --jq .id`로 얻으며, `#number`나 `node_id`가 _아니다_). GitHub은 `issue_dependencies_summary.blocked_by`를 제공한다(열려 있는 blocker만 세며, 이것이 실제 게이트다). 의존성 기능을 쓸 수 없으면 child 본문 맨 위에 `Blocked by: #<n>, #<n>` 줄을 적는다. 모든 blocker가 닫히면 티켓은 unblocked 상태다.
- **Frontier query**: map의 열린 child를 나열한다(`gh issue list --state open`, map의 sub-issue / task list 범위로 한정). 열린 blocker가 있는 것(`issue_dependencies_summary.blocked_by > 0`, 또는 `Blocked by` 줄에 열린 이슈가 있는 경우)과 assignee가 있는 것은 제외한다. map 순서상 첫 번째 티켓을 고른다.
- **Claim**: `gh issue edit <n> --add-assignee @me`. 세션의 첫 번째 쓰기 작업이다.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, 이어서 `gh issue close <n>`, 그다음 map의 Decisions-so-far에 컨텍스트 포인터(요지 + 링크)를 추가한다.
