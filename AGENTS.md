## Agent skills

### Issue tracker

이슈와 스펙은 이 저장소의 GitHub Issues에서 관리한다(`gh` CLI 사용). `docs/agents/issue-tracker.md` 참고.

### Triage labels

다섯 가지 표준 triage 역할은 기본 라벨 문자열을 그대로 쓴다(`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). `docs/agents/triage-labels.md` 참고.

### Domain docs

Single-context: 저장소 루트에 `CONTEXT.md` 하나와 `docs/adr/`를 둔다. `docs/agents/domain.md` 참고.

### Harness

작업은 GitHub Issue(WHAT: 스펙·논의·승인)와 `phases/`(HOW: step 지시서·실행 상태)로 나눠
실행한다. step 설계 7원칙, 상태 기계, JSON 스키마는 `docs/agents/harness.md` 참고.
진입점은 `/harness`, 검수는 `/review`다.

### Bash 안전 가드

`.claude/hooks/guard-bash.py`가 PreToolUse에서 되돌릴 수 없는 Bash 명령을 차단한다.
차단당하면 우회하지 말고 대안을 쓴다 — `git reset --hard` 대신 `git stash`,
`git clean -f` 대신 `git stash -u`, `git push --force` 대신 `--force-with-lease`.
가드를 고쳐야 한다면 `.claude/hooks/test_guard_bash.py`에 케이스를 먼저 추가한다.

실행기 롤백 예외: `git reset --hard`와 `git clean -fd`는 실행기(`scripts/execute.py`)
프로세스만, 반드시 `refs/harness/` 스냅샷을 남긴 뒤 실행한다. 세션과 사람에게는 여전히 금지다.
Codex 세션은 `.codex/hooks.json`으로 같은 `guard-bash.py`를 받는다.
`--ignore-user-config`는 이 훅을 끄므로 쓰지 않는다.
Grok은 이 가드를 실행하지 않는다(가드 밖). Grok 리뷰어의 보호는 사후 HEAD·트리 검사와
되돌림, Git config·hooks·info 해시 검사, 계약문에 기댄다. env의 토큰 변수 제거와 credential.helper 비우기. 파일·키체인의 자격 자체는 남는다.
모든 자식에서 ORCA_*·BASH_ENV·ENV도 제거한다. marker는 `.git`의 `harness/{phase}/attempt.json`에 두고 `.run/` 리뷰 원문은 되읽지 않는다. 새 무시 산출물은 unit 허용 경로 안에서만 허용하며 실패 롤백 시 그 새 파일만 지운다.

<!-- graft:start -->
## Graft — repo context graph

This repo is indexed in `graft/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `graft map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `graft ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `graft grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `graft skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `graft callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `graft/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `graft ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `graft build` (deterministic,
no API key, $0).
<!-- graft:end -->
