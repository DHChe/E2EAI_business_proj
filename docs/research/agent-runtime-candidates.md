# 에이전트 런타임·스택 후보 조사

> **이 문서의 성격**: GitHub Issue #4(wayfinder `research`)의 산출물이다.
> **결정 문서가 아니다.** 선택지와 그 제약을 나열할 뿐이고, 실제 스택 결정은 Issue #9에서 사람이 한다.
> 어떤 후보도 추천하지 않는다.
>
> **조사일 / 모든 URL 확인일**: 2026-09-20
> **근거 원칙**: 1차 자료(공식 문서·API 레퍼런스·패키지 레지스트리)만 인용한다. 블로그 요약은 근거로 쓰지 않았다.

---

## 0. 조사 범위와 읽는 법

### 0.1 문제 설정

가상 중견기업의 인사·총무 업무(휴가 승인, 경비 정산, 비품 요청, 채용 일정 조율 등)를
여러 건 동시에 처리하는 에이전트 시스템을 만든다고 할 때, **에이전트 루프를 무엇 위에 올릴 것인가**.

### 0.2 다섯 가지 비교 기준

| 기호 | 기준 | 묻는 것 |
| --- | --- | --- |
| C1 | 사람 승인(HITL) 지점 | 중간에 멈추고 사람을 기다리는 것이 1급 개념인가, 직접 만들어야 하는가 |
| C2 | 장기 실행 작업과 상태 | 중단·재개·타임아웃·재시도를 런타임이 책임지는가 |
| C3 | 프론트엔드로의 진행 상황 전달 | 스트리밍·이벤트·폴링 중 무엇이 제공되는가 |
| C4 | 도구 권한과 감사 기록 | "누가 무엇을 승인했는지"가 어디에 남는가 |
| C5 | 동시성·격리 | 여러 건이 동시에 진행될 때의 모델 |

### 0.3 후보 목록

조사 대상은 세 갈래지만, 두 번째 갈래는 Anthropic이 1차로 제공하는 수단이 셋으로 갈리고
각각의 제약이 서로 매우 다르므로 **행을 분리해서** 다룬다.

| ID | 후보 | 한 줄 정의 |
| --- | --- | --- |
| **A** | Claude Agent SDK | Claude Code 하네스를 라이브러리로 패키징한 것. 내장 도구 + 에이전트 루프 제공, **배포는 직접** |
| **B1** | Messages API 수동 tool-use 루프 | `stop_reason == "tool_use"` 루프를 직접 작성. 하네스도 배포도 직접 |
| **B2** | Tool Runner (SDK 베타 헬퍼) | 같은 Messages API 위에서 루프만 SDK가 돌려줌. 하네스 일부 제공, 배포는 직접 |
| **B3** | Claude Managed Agents (베타) | Anthropic이 에이전트 루프 **와** 세션별 샌드박스를 호스팅. 하네스 + 배포 제공 |
| **C1'** | Temporal | 내구성 실행(durable execution) 워크플로 엔진 |
| **C2'** | Inngest | 이벤트 기반 durable step 함수 플랫폼 |
| **C3'** | LangGraph | 그래프 기반 에이전트 프레임워크(+ 유료 관리형 LangGraph Platform) |

Anthropic 공식 문서가 직접 정리한 A / B1·B2 / B3의 구분은 다음과 같다
(출처: [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview), 확인 2026-09-20):

> | If you're... | Use | Why |
> | --- | --- | --- |
> | Building an agent without implementing the tool loop yourself | **Agent SDK** | A Python or TypeScript library that runs the agent loop for you. |
> | Calling the API directly and implementing the tool loop yourself | **Client SDK** | Direct access to the Anthropic API rather than to Claude Code. You implement the tool loop yourself. |
> | Running long-running or asynchronous agents without managing your own sandbox or session infrastructure | **Managed Agents** | Hosted REST API, a separate product from the Agent SDK. Anthropic runs the agent and the sandbox. |

핵심 구분축은 **"하네스를 누가 주는가"** 와 **"배포(인프라)를 누가 주는가"** 두 개다.
A·B1·B2는 배포를 전부 직접 해야 하고, **B3만 배포까지 제공한다.**

---

## 1. 후보 A — Claude Agent SDK

### 1.0 기본 정보

| 항목 | 값 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 패키지 (TS) | `@anthropic-ai/claude-agent-sdk` **0.3.278** | <https://registry.npmjs.org/@anthropic-ai/claude-agent-sdk/latest> |
| 패키지 (Python) | `claude-agent-sdk` **0.2.157** | <https://pypi.org/pypi/claude-agent-sdk/json> |
| 지원 언어 | Python, TypeScript **만**. 다른 언어는 CLI를 `-p` 플래그로 서브프로세스 실행 | <https://code.claude.com/docs/en/agent-sdk/overview> |
| 라이선스/약관 | Anthropic Commercial Terms of Service 적용 | 같은 문서 |
| 버전 번호 | 둘 다 **0.x** (1.0 미도달) | 위 레지스트리 |
| 런타임 요구사항 (TS) | `engines: {node: ">=18.0.0"}`. **플랫폼별 네이티브 바이너리를 optionalDependencies로 배포**(linux/darwin/win32 × x64/arm64 + musl) — 즉 Claude Code CLI 바이너리가 함께 깔린다 | npm 패키지 메타데이터 |
| 런타임 요구사항 (Python) | `requires_python: >=3.10`. 의존성: `anyio`, `jsonschema`, `mcp>=1.23.0`, `sniffio`. `otel` extra로 `opentelemetry-api` | PyPI 패키지 메타데이터 |
| 인증 제약 | "Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." → **API 키 인증만** | overview |

> 문서 원문: "The SDK is available as a library for Python and TypeScript only. To drive the same agent loop from another language, run the CLI as a subprocess with the `-p` flag and `--output-format json`."
> — <https://code.claude.com/docs/en/agent-sdk/overview> (확인 2026-09-20)

제공 기능: 내장 도구(파일 읽기/쓰기/편집, bash, 검색, 웹 검색), 훅, 서브에이전트, MCP, 권한, 세션, 스킬/커맨드/메모리, 플러그인.
출처: <https://code.claude.com/docs/en/agent-sdk/overview> (확인 2026-09-20)

### 1.1 C1 — 사람 승인(HITL) 지점

**결론: 1급 개념이 두 층으로 존재한다. 단 "프로세스가 살아 있어야 하는 승인"과 "프로세스를 죽이고 나중에 재개하는 승인"이 서로 다른 메커니즘이다.**

#### (a) 권한 평가 파이프라인 — 6단계

도구 호출은 다음 순서로 평가된다
(출처: <https://code.claude.com/docs/en/agent-sdk/permissions>, 확인 2026-09-20):

1. **Hooks** — 먼저 실행. `PreToolUse` 훅은 무조건 거부할 수 있다.
2. **Deny rules** — `disallowedTools` / `settings.json`. 매칭되면 `bypassPermissions` 모드에서도 차단.
3. **Ask rules** — `settings.json`의 `ask` 규칙. 매칭되면 `canUseTool` 콜백으로 떨어진다(`bypassPermissions`에서도).
4. **Permission mode** — `default` / `dontAsk` / `acceptEdits` / `bypassPermissions` / `plan` / `auto`
5. **Allow rules** — `allowedTools` / `settings.json`
6. **`canUseTool` 콜백** — 위에서 해결되지 않은 경우 호출

#### (b) `canUseTool` 콜백 — 동기식 승인

콜백 시그니처와 반환값
(출처: <https://code.claude.com/docs/en/agent-sdk/user-input>, 확인 2026-09-20):

| 응답 | Python | TypeScript |
| --- | --- | --- |
| 허용 | `PermissionResultAllow(updated_input=...)` | `{ behavior: "allow", updatedInput }` |
| 거부 | `PermissionResultDeny(message=...)` | `{ behavior: "deny", message }` |

가능한 응답 유형: 승인 / **입력을 수정해서 승인**(`updatedInput`) / **승인하고 규칙으로 기억**(`updatedPermissions`) / 거부 / 대안 제시(거부 + 메시지) / 완전 방향 전환(스트리밍 입력).

**대기 시간 제약 — 문서 원문:**

> "The callback can stay pending indefinitely. Execution remains paused until your callback returns. If a user might take longer to respond than your process can reasonably stay running, register a `PreToolUse` hook that returns the `defer` decision instead of waiting in the callback, so the process can exit and resume later from the persisted session."
> — <https://code.claude.com/docs/en/agent-sdk/user-input> (확인 2026-09-20)

즉 **무한정 기다릴 수는 있지만 그동안 프로세스가 살아 있어야 한다.** 이것이 인사 승인처럼 며칠 걸리는 시나리오의 핵심 제약이다.

#### (c) `defer` 결정 — 프로세스를 끄고 나중에 재개하는 승인

`PreToolUse` 훅의 `permissionDecision`은 네 값을 가진다: `"allow"` / `"deny"` / `"ask"` / **`"defer"`**.
여러 훅이 서로 다른 결정을 내면 우선순위는 `deny` > `defer` > `ask` > `allow`.
(출처: <https://code.claude.com/docs/en/hooks#pretooluse-decision-control>, 확인 2026-09-20)

문서 원문(`#defer-a-tool-call-for-later`, 확인 2026-09-20):

> `"defer"` is for integrations that run `claude -p` as a subprocess and read its JSON output, such as an Agent SDK app or a custom UI built on top of Claude Code. It lets that calling process pause Claude at a tool call, collect input through its own interface, and resume where it left off. Claude Code honors this value only in non-interactive mode with the `-p` flag. In interactive sessions it logs a warning and ignores the hook result.

왕복 흐름:

1. Claude가 도구(전형적으로 `AskUserQuestion`)를 호출 → `PreToolUse` 훅 발화
2. 훅이 `permissionDecision: "defer"` 반환 → **도구 미실행, 프로세스가 `stop_reason: "tool_deferred"` 로 종료**, 대기 중인 도구 호출은 트랜스크립트에 보존
3. 호출자 프로세스가 결과 JSON의 `deferred_tool_use`(`id`, `name`, `input`)를 읽어 자체 UI에 질문을 띄우고 답을 기다린다
4. 답이 오면 `claude -p --resume <session-id>` 로 재개 → 같은 도구 호출이 `PreToolUse`를 다시 발화
5. 훅이 `"allow"` + `updatedInput`(답변 포함) 반환 → 도구 실행, Claude 계속

**`defer`의 제약 (모두 문서 명시, 확인 2026-09-20):**

- **타임아웃·재시도 한도 없음.** 세션은 재개할 때까지 디스크에 남는다 — 단 `cleanupPeriodDays` 보존 스윕이 **기본 30일 후 세션 파일을 삭제**한다.
- **한 턴에 도구 호출이 하나일 때만 동작한다.** 여러 개를 동시에 호출하면 `defer`는 경고와 함께 무시되고 일반 권한 흐름으로 진행된다. ("resume can only re-run one tool")
- **`-p` 비대화형 모드에서만 유효하다.** 대화형 세션에서는 경고 로그만 남기고 무시된다.
- 재개 시 도구가 사라졌으면(예: MCP 서버 미연결) `stop_reason: "tool_deferred_unavailable"` + `is_error: true` 로 종료된다.
- `-p`로 재개하면 저장된 권한 모드가 복원되지 않는다. `--permission-mode`를 다시 넘겨야 한다.

#### (d) 승인 대기 알림과 헤드리스 기본 거부

`PermissionRequest` 훅으로 Slack·이메일·푸시 등 외부 알림을 보낼 수 있다.
(출처: <https://code.claude.com/docs/en/agent-sdk/user-input>, 확인 2026-09-20)

**헤드리스 운영에서 반드시 알아야 할 기본값** — 문서 원문:

> "In sessions that can't show a prompt, such as background subagents in non-interactive mode, Claude Code still runs these hooks, and **if no hook returns a decision, it denies the tool call.**"
> — <https://code.claude.com/docs/en/hooks#permissionrequest> (확인 2026-09-20)

즉 서버에서 헤드리스로 돌리는 서브에이전트는 **결정을 내리는 훅이 없으면 도구 호출이 조용히 거부된다.**
또한 샌드박스 명령의 네트워크 요청에 대해서는 `PermissionRequest` 훅이 아예 실행되지 않는다(`permission_prompt` 알림 타입을 써야 함).

#### (e) 알려진 함정

문서가 **경고(Warning) 박스로** 명시한 것:

> "**Auto-approved tools never reach `canUseTool`.** A tool call approved at any earlier step, by `acceptEdits` or `bypassPermissions`, or by an allow rule, skips your `canUseTool` callback, so permission checks you put there are silently bypassed for that tool."
> — <https://code.claude.com/docs/en/agent-sdk/permissions> (확인 2026-09-20)

모든 도구 호출에 예외 없이 걸리는 검사가 필요하면 `canUseTool`이 아니라 `PreToolUse` 훅을 써야 한다.

### 1.2 C2 — 장기 실행 작업과 상태

**세션 = 대화 기록.** 프롬프트, 모든 도구 호출, 모든 도구 결과, 모든 응답을 SDK가 자동으로 디스크에 쓴다.
출처: <https://code.claude.com/docs/en/agent-sdk/sessions> (확인 2026-09-20)

| 항목 | 내용 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 저장 위치 | `~/.claude/projects/<encoded-cwd>/*.jsonl` (cwd의 비영숫자를 `-`로 치환). `CLAUDE_CONFIG_DIR` 설정 시 그 아래 | sessions |
| 재개 | `resume=<session-id>` / `continue: true`(가장 최근 세션) | sessions |
| 분기 | `fork_session=True` / `forkSession: true` — 새 세션 ID, 원본 불변 | sessions |
| 영속화 끄기 | `persistSession: false` (TS). Python은 `CLAUDE_CODE_SKIP_PROMPT_HISTORY` env | sessions / typescript |
| 보존 기간 | `cleanupPeriodDays` 기본 **30일** 후 세션 파일 삭제 | hooks#defer |
| 턴 상한 | `maxTurns` (기본 없음) | typescript |
| 비용 상한 | `maxBudgetUsd` — 클라이언트 측 비용 추정치가 이 값에 도달하면 중단 | typescript |
| 재시도 | 명시적 기능 **없음**. `error_max_turns` / `error_max_budget_usd` 로 끝난 뒤 한도를 올려 `resume` 하는 패턴을 문서가 제시 | sessions |

**결정적 제약: 세션 파일은 그 파일을 만든 머신에 로컬이다.**

> "Session files are local to the machine that created them."
> — <https://code.claude.com/docs/en/agent-sdk/sessions> (확인 2026-09-20)

다른 호스트(CI 워커, 임시 컨테이너, 서버리스)에서 재개하려면 셋 중 하나:

1. **`sessionStore` 어댑터**를 붙여 트랜스크립트를 자체 백엔드로 미러링한다. 조회 키는 작업 디렉터리에서 파생되므로 원래 실행과 같은 `cwd`에서 재개해야 한다. (`sessionStoreFlush`는 `'batched'`/`'eager'`, `loadTimeoutMs` 기본 60000 — 둘 다 문서에 *Alpha* 표기)
2. `.jsonl` 세션 파일을 직접 옮긴다.
3. 세션 재개에 의존하지 않고 결과를 애플리케이션 상태로 뽑아 새 세션 프롬프트에 넣는다 (문서가 "often more robust"라고 표현)

출처: <https://code.claude.com/docs/en/agent-sdk/sessions>, <https://code.claude.com/docs/en/agent-sdk/typescript> (확인 2026-09-20)

**타임아웃 / 재시도는 런타임 기능이 아니다.** 워크플로 엔진의 activity retry policy 같은 것은 없다.
파일 변경의 스냅샷/롤백은 별도 기능(file checkpointing)이며, 세션은 **대화만 보존하고 파일시스템은 보존하지 않는다**
("Sessions persist the conversation, not the filesystem." — sessions, 확인 2026-09-20).

### 1.3 C3 — 프론트엔드로의 진행 상황 전달

**SDK 자체는 HTTP 엔드포인트를 제공하지 않는다.** `query()`가 반환하는 async iterator에서 메시지를 읽어
**직접 만든 서버가 프론트엔드로 다시 중계해야 한다.**

| 수단 | 내용 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 메시지 스트림 | `for await (const message of query({...}))` — `system`(init), `assistant`, `result` 등 | overview / sessions |
| 부분 메시지 | `includePartialMessages: true` (기본 `false`) → `SDKPartialAssistantMessage` (`type: "stream_event"`) 수신. **메인 세션에만 적용**되고 `parent_tool_use_id`는 항상 `null` | typescript |
| 서브에이전트 텍스트 | `forwardSubagentText` 옵션으로 완성 메시지로 받음 | typescript |
| 스트리밍 입력 | 작업 도중 중단·추가 컨텍스트 주입·채팅 UI 구성 | streaming-vs-single-mode |

즉 **C3는 "SDK가 이벤트를 준다 → 그걸 SSE/WebSocket으로 다시 쏘는 서버는 내가 만든다"** 구조다.

### 1.4 C4 — 도구 권한과 감사 기록

**권한 표현은 강력하다. 감사 기록은 플랫폼 기능이 아니다.**

권한 표현 수단 (출처: <https://code.claude.com/docs/en/agent-sdk/permissions>, 확인 2026-09-20):

- 6가지 permission mode (위 1.1 (a))
- allow / deny / ask 규칙 — `settings.json` 선언형 또는 `allowedTools`/`disallowedTools`
- 스코프 규칙: `Bash(rm *)`, `Edit(//secrets/**)` 같은 패턴. `Edit(path)` 규칙이 `Write`, `NotebookEdit` 등 모든 파일 쓰기 도구를 관장
- MCP 도구는 `mcp__<server>__*` 형태로만 글롭 허용 (서버 세그먼트는 글롭 불가)

감사 기록 — **OpenTelemetry `tool_decision` 이벤트가 존재한다.** (이 조사에서 확인한, 후보 A의 가장 과소평가된 자산)

`CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_LOGS_EXPORTER=otlp` 로 켜면 Claude Code(= Agent SDK가 번들하는 CLI)가
**도구 권한 결정마다 `claude_code.tool_decision` 이벤트를 OTLP로 내보낸다.**
(출처: <https://code.claude.com/docs/en/monitoring-usage>, 확인 2026-09-20)

주요 속성:

| 속성 | 값 |
| --- | --- |
| `decision` | `"accept"` 또는 `"reject"` |
| `source` | 결정의 출처: `"config"`(규칙·모드로 자동) / `"hook"`(`PreToolUse` 또는 `PermissionRequest` 훅) / `"user_permanent"` / `"user_temporary"` / `"user_abort"` / `"user_reject"` |
| `tool_name` | 도구 이름. **사용자 설정 MCP 도구는 항상 리터럴 `"mcp_tool"`로 마스킹**되고, 실제 서버/도구 이름은 `OTEL_LOG_TOOL_DETAILS=1` 일 때만 `tool_parameters`에 들어간다 |
| `tool_use_id` | 훅에 전달되는 `tool_use_id`와 일치 → **OTel 이벤트와 훅이 잡은 데이터를 상관시킬 수 있다** |
| `tool_source` | `"builtin"` / `"mcp"` / `"sdk_host_builtin_mcp"` |
| `tool_parameters` | `OTEL_LOG_TOOL_DETAILS=1` 일 때만. Bash는 `bash_command`, `full_command`, `timeout` 등 |
| `event.timestamp`, `event.sequence` | ISO 8601 + 프로세스 단위 순서 카운터 |

문서가 직접 제시하는 탐지 규칙 매핑: "Tool call allowed or denied, and by what → `tool_decision` / `decision`, `source`, `tool_name`, `tool_parameters`".

**남는 공백 세 가지:**

1. **"어느 사람인가"는 기록되지 않는다.** `source`는 결정의 *출처 분류*(설정/훅/사용자)이지 사번이나 결재자 ID가 아니다. 사내 승인자 신원은 `canUseTool` 콜백/훅 안에서 내 애플리케이션이 따로 남겨야 한다.
2. **도구 인자는 기본적으로 로깅되지 않는다.** `OTEL_LOG_TOOL_DETAILS=1` 를 켜야 하고, 켜면 민감값이 텔레메트리 백엔드로 흘러갈 수 있어 백엔드에서 필터/마스킹하라고 문서가 경고한다.
3. **Claude Code는 자신이 띄우는 서브프로세스(Bash 도구, 훅, MCP 서버, language server)에 `OTEL_*` 환경변수를 전달하지 않는다.** 훅 안에서 별도로 계측하려면 그 명령에 직접 변수를 세팅해야 한다.

세션 트랜스크립트 `.jsonl`도 모든 도구 호출과 결과를 담지만 이것은 대화 로그이지 감사 로그가 아니다.
훅 자체의 stdout/stderr는 디버그 로그에만 남으며, 구조화된 감사 트레일 필드는 훅 출력 스키마에 없다.
출처: <https://code.claude.com/docs/en/hooks>, <https://code.claude.com/docs/en/monitoring-usage> (확인 2026-09-20)

### 1.5 C5 — 동시성·격리

**동시성 모델을 SDK가 제공하지 않는다.** 격리 단위는 다음뿐이다:

- **세션 ID** — 다중 사용자 앱이면 "one per user" 로 세션 ID를 직접 추적하라고 문서가 명시
  ("Required when you have multiple sessions (for example, one per user in a multi-user app)" — sessions, 확인 2026-09-20)
- **작업 디렉터리(`cwd`)** — 세션 파일 경로와 `sessionStore` 조회 키가 cwd에서 파생된다. 동시 실행 건들이 같은 디렉터리를 공유하면 파일 변경이 서로 보인다
  ("If a forked agent edits files, those changes are real and visible to any session working in the same directory." — sessions, 확인 2026-09-20)
- **서브에이전트** — 한 세션 안에서의 하위 작업 분리. 서브에이전트는 부모 세션의 permission mode를 상속한다(단 `bypassPermissions`는 부모 자신이 그 모드일 때만)

**세션 *안*에는 메시지 큐가 있다.** `queued_turn_count`, `interrupt()` 영수증의 `still_queued` / `cancelled`,
`cancel_queued: true` 제어 요청(`interrupt_cancel_queued_v1` capability). 다만 문서가 명시하듯
**Claude Code가 큐에 쌓인 여러 메시지를 한 턴으로 합칠 수 있다.**
→ 서로 다른 두 건(예: A 직원 휴가 / B 직원 경비)을 한 세션에 던지면 **합쳐져서 한 턴으로 처리될 수 있다.**
건별 격리를 원하면 **건당 세션 하나**가 사실상 강제된다.
출처: <https://code.claude.com/docs/en/agent-sdk/typescript> (확인 2026-09-20)

**세션 안의 오케스트레이션 DSL은 따로 있다.** `Workflow` 도구(Agent SDK v0.3.149+)는
`agent()` / `parallel()` / `pipeline()` / `phase()` 로 여러 서브에이전트를 백그라운드에서 조율하고
하나의 결과로 묶는다. `resumeFromRunId`로 이전 실행을 재개할 수 있으나 문서가 **"Same session only"** 로 한정한다.
즉 이것은 **한 건 안의 병렬성**이지 여러 건의 동시성이 아니다.
출처: 같은 문서 (확인 2026-09-20)

**결론: N건 동시 진행은 N개의 프로세스/세션을 내가 스케줄링해야 한다.**
큐, 워커 풀, 백프레셔, 중복 실행 방지(멱등성), 건별 락은 전부 애플리케이션 몫이다.

---

## 2. 후보 B — Anthropic이 1차로 제공하는 수단들

### 2.0 세 변종의 관계

| | 내가 쓰는 코드 | 하네스 | 배포 | 도구 |
| --- | --- | --- | --- | --- |
| **B1** 수동 루프 | `while stop_reason == "tool_use"` 직접 작성 | 직접 | 직접 | 내가 정의한 것만 |
| **B2** Tool Runner | 도구 함수만 | SDK가 루프 제공 | 직접 | 내가 정의한 것만 |
| **B3** Managed Agents | 에이전트 설정 + 커스텀 도구 결과 | **Anthropic** | **Anthropic** (세션별 샌드박스) | 내장 툴셋(bash/파일/웹) + Skills/MCP + 내 커스텀 도구 |

공통 기반 정보:

| 항목 | 값 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| Python SDK | `anthropic` **1.7.0** | <https://pypi.org/pypi/anthropic/json> |
| TypeScript SDK | `@anthropic-ai/sdk` **0.127.0** | <https://registry.npmjs.org/@anthropic-ai/sdk/latest> |
| 공식 클라이언트 SDK 언어 | Python, TypeScript, C#, Go, Java, PHP, Ruby (7종) + `ant` CLI | <https://platform.claude.com/docs/en/cli-sdks-libraries/overview> |

### 2.1 B1 — Messages API 수동 tool-use 루프

#### C1 — HITL

**1급 개념이 전혀 없다. 전부 직접 만든다.**
대신 루프의 모든 지점이 내 코드이므로 **원하는 곳 어디에나** 승인 게이트를 넣을 수 있다.

Anthropic 문서가 직접 이 트레이드오프를 서술한다:

> "The tool runner handles the agentic loop, error wrapping, and type safety so you don't have to. **When you need human-in-the-loop approval, custom logging, or conditional execution, use the manual loop instead.**"
> — <https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner> (확인 2026-09-20, 강조는 인용자)

즉 **"HITL이 필요하면 수동 루프"가 Anthropic의 공식 입장**이다.

루프의 형태 (출처: <https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview>, 확인 2026-09-20):

1. `tools`와 `messages`로 요청
2. 응답이 `stop_reason: "tool_use"` + 하나 이상의 `tool_use` 블록
3. 내 코드가 도구를 실행 → 승인이 필요하면 **여기서 멈추면 된다**
4. `tool_result` 블록을 담은 user 메시지로 다음 요청

병렬 도구 호출 시 **모든 `tool_result`를 하나의 user 메시지에 담아야 한다.**
문서가 명시한 두 가지 포맷 규칙: "every tool result returns in a single user message, and no text content appears before the tool results in that message."
호출 실행 순서는 API가 강제하지 않는다 — 동시(`Promise.all`, `asyncio.gather`)든 순차든 내 선택이다.
출처: <https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use> (확인 2026-09-20)

#### C2 — 장기 실행과 상태

**Messages API는 상태가 없다.** 문서 원문:

> "The Messages API is stateless, which means that you always send the full conversational history to the API."
> — <https://platform.claude.com/docs/en/build-with-claude/working-with-messages> (확인 2026-09-20)

따라서 **모든 상태는 내 DB에 있다.** 뒤집어 말하면:

- **중단·재개가 자연스럽다.** `messages` 배열을 직렬화해 DB에 넣고 며칠 뒤 꺼내 이어 붙이면 된다. 보존 기간 제한도, 머신 로컬 제약도 없다.
- 반대로 **재시도·타임아웃·데드레터·멱등성은 전부 내가 만든다.** SDK가 주는 것은 HTTP 레벨 재시도뿐이다:
  "Certain errors are automatically retried **2 times by default**, with a short exponential backoff. Connection errors …, 408 Request Timeout, 409 Conflict, 429 Rate Limit, and >=500 Internal errors are all retried by default."
  그리고 "By default requests **time out after 10 minutes**." (`max_retries` / `timeout` 로 조정)
  → 이것은 **한 번의 HTTP 요청**에 대한 재시도이지, "휴가 승인 워크플로 전체"에 대한 재시도가 아니다.
  출처: <https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python> (확인 2026-09-20)
- 컨텍스트 윈도 초과 대비: 서버 측 **compaction**(베타 `compact-2026-01-12`, 기본 트리거 150K 토큰)과 **context editing**(베타 `context-management-2025-06-27`)을 API가 제공한다.
- 에이전트 루프 전체 토큰 상한: **task budget**(베타 `task-budgets-2026-03-13`, `output_config.task_budget`, 최소 `total` 20,000). 단 이것은 **권고적**이며 모델이 스스로 페이스를 조절하게 하는 장치다. 강제 상한이 아니다.
- 출처: <https://platform.claude.com/docs/en/build-with-claude/compaction>, <https://platform.claude.com/docs/en/build-with-claude/context-editing> (확인 2026-09-20)

#### C3 — 프론트엔드 전달

**Messages API의 스트리밍은 SSE다.**

> "When creating a Message, you can set `"stream": true` to incrementally stream the response using server-sent events (SSE)."
> — <https://platform.claude.com/docs/en/build-with-claude/streaming> (확인 2026-09-20)

이벤트 종류: `message_start`, `content_block_start`, `content_block_delta`(text/input_json/thinking/signature), `content_block_stop`, `message_delta`, `message_stop`.
`eager_input_streaming: true`를 도구 정의에 켜면 큰 도구 입력이 생성되는 대로 흘러온다
(대신 **API가 입력을 검증·보정하지 않으므로** 누적된 `partial_json`이 불완전할 수 있고 파싱을 직접 가드해야 한다).

단 이것은 **Anthropic → 내 서버** 구간의 스트림이다. **내 서버 → 프론트엔드** 구간은 여전히 직접 만든다.
진행 상황 이벤트의 스키마, 재연결, 중복 제거, 커서도 전부 내 설계다.

#### C4 — 권한과 감사

**전부 직접.** API 레벨에 도구 권한 개념이 없다.
있는 것은:

- `tool_choice`(`auto`/`any`/`tool`/`none`)와 `disable_parallel_tool_use` — 모델이 도구를 부르는 방식의 제어이지 권한이 아니다
- `strict: true` — 도구 인자가 스키마를 정확히 만족하도록 보장 (`additionalProperties: false` + `required` 필요)
- 출처: <https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview> (확인 2026-09-20)

**장점**: 감사 레코드의 스키마를 내가 정한다. "누가(사번) 언제 무엇을 어떤 근거로 승인했는지"를 기존 사내 DB 트랜잭션과 같은 커밋 안에 넣을 수 있다.
**단점**: 아무것도 공짜로 주어지지 않는다.

#### C5 — 동시성·격리

**API 쪽 제약은 rate limit뿐이고, 동시성 모델은 전적으로 내 애플리케이션 몫이다.**
각 "건"은 내 DB의 레코드 하나이고, 격리는 내가 설계한 트랜잭션 경계가 제공한다.
Batch API(비동기, 50% 비용)는 지연에 민감하지 않은 대량 처리용이며 HITL과는 무관하다.

### 2.2 B2 — Tool Runner (SDK 베타 헬퍼)

#### 위치

`client.beta.messages.tool_runner(...)` — 일반 Anthropic SDK(`anthropic` / `@anthropic-ai/sdk`)의 일부다.
**Claude Agent SDK와 다른 물건이다.** 내장 도구도, 파일시스템 접근도, 샌드박스도 없다. 내가 정의한 도구만 돌린다.
7개 언어 SDK 모두 지원(Python `@beta_tool`, TS `betaZodTool`, Go `toolrunner`, Ruby `BaseTool`, C#/PHP/Java 각각).
출처: <https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner> (확인 2026-09-20)

#### C1 — HITL

**공식 문서가 "HITL이 필요하면 이걸 쓰지 말라"고 명시한다** (위 2.1 C1의 인용문).

그래도 루프에 개입할 수는 있다. 러너는 iterable이고, 각 iteration에서:

1. 러너가 현재 상태로 Messages API 요청
2. 응답 메시지를 내 루프 바디에 yield
3. 내 루프 바디 실행 — 여기서 메시지를 읽고 러너 상태를 수정할 수 있다
4. 바디가 반환되면 러너가 **메시지 히스토리가 수정되었는지** 확인
   - 수정 안 됨 → 도구 호출이 있으면 자동으로 실행·append 후 계속
   - 수정됨 → 러너의 자동 append를 건너뛰고 내 상태를 그대로 사용 ("Taking over message history")

즉 **`break`로 루프를 빠져나오거나, 메시지 히스토리를 take over해서 도구 실행을 가로챌 수 있다.**
Python은 `generate_tool_call_response()` + `append_messages()`, TypeScript는 `generateToolResponse()`.
C#·Go는 이 훅을 노출하지 않는다(각각 `BetaToolError` throw, 내부 콘텐츠 블록에만 `cache_control` 설정 가능).
`max_iterations`는 7개 언어 SDK 모두 지원.
출처: 같은 문서 (확인 2026-09-20)

**한계**: 이것은 "실행 전 승인"이 아니라 "결과 가로채기"에 가깝고, **프로세스가 살아 있는 동안에만** 가능하다.
러너 상태는 인메모리다. 며칠짜리 승인 대기를 위해 러너 자체를 직렬화해 재개하는 방법은 문서에 없다 → **B1으로 내려가야 한다.**

#### C2 / C3 / C4 / C5

- **C2**: B1과 동일(Messages API 상태 없음). 러너는 **한 프로세스 안의 루프 상태**만 관리한다. `max_iterations` 로 루프 길이를 제한. 프로세스 경계를 넘는 중단/재개는 문서에 없다 → **B1으로 내려간다.**
- **C3**: `stream=True` 로 각 iteration이 스트림 객체를 yield(`BetaMessageStream`). `get_final_message()`로 누적. 프론트엔드 중계는 여전히 내 몫.
- **C4**: B1과 동일하게 **없음**. 단 러너가 자동으로 도구를 실행하므로 **승인 없이 실행되는 경로가 기본값**이라는 점이 B1보다 위험하다.
- **C5**: B1과 동일. 러너 인스턴스 하나 = 한 건. 동시 실행은 내가 스케줄링.

### 2.3 B3 — Claude Managed Agents (베타)

#### 기본 정보

| 항목 | 값 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 상태 | **Beta**. 모든 엔드포인트가 `anthropic-beta: managed-agents-2026-04-01` 헤더 필요 | overview |
| 접근 | 모든 API 계정에 기본 활성화 | overview |
| 핵심 개념 4개 | **Agent**(모델·시스템 프롬프트·도구·MCP·스킬) / **Environment**(클라우드 샌드박스 또는 self-hosted) / **Session**(환경 안에서 도는 에이전트 인스턴스) / **Events** | overview |
| 데이터 보존 | **ZDR 불가, HIPAA BAA 불가.** "stateful by design" 이기 때문 | overview |
| 클라우드 제공자 | Claude Platform on AWS에서도 사용 가능(기능·세션 동작 차이 있음). **Bedrock / Vertex / Foundry에서는 미지원** | overview |

문서 원문:

> "Because of this, Managed Agents is not currently eligible for Zero Data Retention (ZDR) or HIPAA Business Associate Agreement (BAA) coverage."
> — <https://platform.claude.com/docs/en/managed-agents/overview> (확인 2026-09-20)

#### C1 — HITL: **세 후보군 중 가장 명시적인 1급 개념**

**Permission policy가 툴셋/도구 단위 설정이다**
(출처: <https://platform.claude.com/docs/en/managed-agents/permission-policies>, 확인 2026-09-20):

| 정책 | 동작 |
| --- | --- |
| `always_allow` | 확인 없이 자동 실행 |
| `always_ask` | **세션이 멈추고 내 승인을 기다린다** |
| `auto` | 서버가 호출마다 평가 → 실행 / 거부 / 승인 대기 |

기본값: **agent toolset은 `always_allow`**, **MCP toolset은 `always_ask`**. `auto`를 기본으로 쓰는 툴셋은 없다.
`default_config.permission_policy`로 툴셋 전체에, `configs[]`로 개별 도구에 적용한다(예: `bash`만 `always_ask`).

**승인 대기 왕복 (문서 명시 4단계):**

1. 세션이 `agent.tool_use` 또는 `agent.mcp_tool_use` 이벤트를 방출
2. `session.status_idle` 이벤트로 멈추고 `stop_reason.type`이 `requires_action`. 막고 있는 이벤트 ID들이 `stop_reason.event_ids` 배열에 들어 있다. **"The session waits indefinitely for a response."**
3. 막고 있는 각 이벤트에 대해 `user.tool_confirmation` 이벤트를 보낸다 (`tool_use_id`, `result: "allow" | "deny"`, 선택적 `deny_message`). 한 요청에 여러 개를 한꺼번에 보낼 수 있다
4. 전부 해결되면 세션이 `running`으로 복귀. 거부된 도구는 실행되지 않고 에이전트는 `deny_message`를 포함한 거부 결과를 받는다

**중요한 경고 — `auto`는 사람 체크포인트가 아니다.** 문서 원문:

> "**`auto` is not a human checkpoint.** If the server determines that a call is safe, the call runs before anyone sees it, and its effects might not be reversible. If a person must review a tool's calls before they run, configure `always_ask` on that tool."
> — permission-policies (확인 2026-09-20)

그리고 **`auto`가 high-risk로 거부한 호출은 클라이언트가 뒤집을 수 없다.**
`evaluated_permission`이 `ask`가 아닌 이벤트에 `user.tool_confirmation`을 보내면 **400 에러**다.

**또 하나의 함정**: `user.message` 이벤트에 담긴 내용은 "내 의도"로 간주되어 `auto` 평가에 영향을 준다.
신뢰할 수 없는 최종 사용자 입력을 그대로 `user.message`에 중계하면 그 입력이 의도로 읽혀 호출이 허용될 수 있다.
→ 문서가 직접 "그 사용자에게 검토 없이 맡기지 않을 도구에는 `always_ask`를 걸라"고 권고한다. (확인 2026-09-20)

**커스텀 도구는 permission policy가 적용되지 않는다.** 내 애플리케이션이 `agent.custom_tool_use` 이벤트를 받아
실행 여부를 스스로 결정한 뒤 `user.custom_tool_result`를 돌려준다. (확인 2026-09-20)

#### C2 — 장기 실행과 상태

**세션 상태 (출처: <https://platform.claude.com/docs/en/managed-agents/session-operations>, 확인 2026-09-20):**

| 상태 | 의미 |
| --- | --- |
| `idle` | 사용자 메시지나 도구 승인 등 입력 대기. `initial_events` 없이 생성된 세션의 초기 상태 |
| `running` | 실행 중 |
| `rescheduling` | 일시적 오류 발생, **자동 재시도 중** |
| `terminated` | 복구 불가 오류 또는 아카이브로 종료. **작업을 끝낸 세션은 `terminated`가 아니라 `idle`이 된다** |

- **대화 기록, 샌드박스 상태, 산출물이 전부 서버에 저장된다.** "sessions are long-running, resume cleanly after pauses" (overview, 확인 2026-09-20)
- 승인 대기 시간 상한: 문서상 **"waits indefinitely"**. 명시적 타임아웃 값은 문서에 없다.
- **재시도**: `rescheduling` 상태로 일시적 오류를 자동 재시도한다. `session.error` 이벤트에 `retry_status`가 담긴 타입 있는 `error` 객체가 온다.
- **비용 상한(session budget)**: 생성 시 `budget: {type: "limit", max_list_cost: {amount: "2500", currency: "USD"}}` (amount는 **미국 센트 단위 문자열**). 도달하면 세션이 `budget_reached` stop reason으로 idle. **모델 요청 사이에서 강제**되므로 넘어선 요청은 끝까지 실행되고 최종 비용이 상한을 약간 초과할 수 있다. **생성 시에만 붙일 수 있고**, 나중에 변경·제거는 가능하나 제거는 일방향이며 없던 세션에 추가할 수 없다.
- **컨텍스트**: `agent.thread_context_compacted` 이벤트로 압축이 일어났음을 알린다.
- 삭제: 세션을 지우면 **세션이 만든 파일도 영구 삭제된다.** 마지막 턴의 출력 파일은 idle 이후 몇 초 뒤에야 파일 목록에 뜨므로, 지우기 전에 확인하라고 문서가 경고한다.

#### C3 — 프론트엔드 전달: **SSE가 1급으로 제공된다**

| 수단 | 엔드포인트 / 형태 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 세션 스트림 | `GET /v1/sessions/{session_id}/events/stream` (SSE, `text/event-stream`) | events-and-streaming |
| 스레드 스트림 | `GET /v1/sessions/{session_id}/threads/{thread_id}/stream` | 같은 문서 |
| 이벤트 전송 | `POST /v1/sessions/{session_id}/events` | 같은 문서 |
| 이벤트 히스토리 | `GET /v1/sessions/{session_id}/events` (`types[]` 필터 지원, 페이지네이션) | 같은 문서 |
| 토큰 단위 미리보기 | `event_deltas[]` 쿼리 파라미터로 opt-in. `agent.message`, `agent.thinking` 값 허용(연결당 최대 100). `event_start` → `event_delta` → 버퍼된 최종 이벤트 순서 | 같은 문서 |
| 웹훅 | Console에서 HTTPS 엔드포인트 등록. `session.status_idled` 가 **승인 대기 알림용** 이벤트 | webhooks |

**재연결 모델의 제약:**

- **명시적 커서·시퀀스 번호가 없다.** 재연결 시 이벤트 `id` 값을 추적해 중복 제거한다(히스토리를 `list`로 먼저 받고 스트림을 tail하는 패턴).
- **event delta는 best effort다.** 부하 시 누락될 수 있고, 재연결 시 재생되지 않으며, 히스토리에 영속화되지 않는다. 연결당 스레드 하나로 한정된다.
- 문서 권고: **이벤트를 보내기 전에 스트림을 먼저 열어라**(레이스 방지).

**웹훅의 제약 (출처: webhooks, 확인 2026-09-20):**

- 이벤트 `type`과 `id`만 오고 **전체 객체는 오지 않는다.** 받은 뒤 `GET`으로 직접 조회해야 한다.
- **순서 보장 없음.** `session.status_idled`가 `session.outcome_evaluation_ended`보다 먼저 올 수 있다.
- **재시도 3회** (5~120초 지터 지수 백오프). 마지막 시도가 실패하면 **이벤트는 그냥 버려진다. 큐잉되지 않고 유실 신호도 없다.**
  → 문서 원문: "Webhooks aren't a durable log, so if you need to observe every transition, reconcile by listing or fetching the resource through the API."
- 엔드포인트가 `3xx`를 반환하면 **첫 시도에 즉시 비활성화**된다(리다이렉트는 따라가지 않음). 비공개 IP로 해석돼도 즉시 비활성화.
- 구독하지 않은 상태에서 발생한 이벤트는 나중에 구독해도 **백필되지 않는다.**
- 시그니처: `webhook-id` / `webhook-timestamp` / `webhook-signature` 헤더 + `whsec_` 접두 32바이트 서명 키. SDK의 `unwrap()` 헬퍼가 검증(5분 초과 페이로드는 거부).

#### C4 — 권한과 감사: **세 후보군 중 가장 구조화된 감사 레코드**

**모든 `agent.tool_use` / `agent.mcp_tool_use` 이벤트가 `evaluated_permission` 필드를 갖는다**
(`"allow"` / `"ask"` / `"deny"`), 그리고 대부분 `evaluation` 객체를 함께 갖는다.
(출처: permission-policies §"See how each call was evaluated", 확인 2026-09-20)

| `evaluation` | 최상위 `evaluated_permission` | 의미 |
| --- | --- | --- |
| `{"type": "always_allow"}` | `"allow"` | 정책이 `always_allow`라 실행됨 |
| `{"type": "always_ask"}` | `"ask"` | 정책이 `always_ask`라 승인 대기 |
| `{"type": "auto", "evaluated_permission": {"type": "allow"}}` | `"allow"` | `auto` 하에서 서버가 안전하다고 판단, 실행됨 |
| `{"type": "auto", "evaluated_permission": {"type": "ask", "reason_code": "indeterminate"}}` | `"ask"` | `auto`가 판단 불가 → 승인 대기 |
| `{"type": "auto", "evaluated_permission": {"type": "deny", "reason_code": "high_risk"}}` | `"deny"` | `auto`가 고위험으로 판단, 거부 |

`reason_code`에 대한 문서의 지시: "**a value for your client to branch on and keep in audit records**, not text to display to end users." (확인 2026-09-20)
→ **감사 레코드에 넣으라고 문서가 직접 말한다.**

승인 행위 자체도 `user.tool_confirmation` 이벤트로 이벤트 히스토리에 영속화되며 `result`와 `deny_message`를 담는다.
모든 영속 이벤트는 `processed_at`(ISO 8601) 타임스탬프를 갖는다(큐에 있는 동안은 `null`).

**그러나 "누가" 승인했는지는 플랫폼이 기록하지 않는다.**
`user.tool_confirmation` 이벤트 스키마에 actor / identity 필드는 문서에 없다.
API 키 하나로 내 서버가 대신 보내는 구조이므로, **사람 주체는 내 애플리케이션이 별도로 기록해야 한다.**

**관측성의 공백** (managed-agents/observability, 확인 2026-09-20):
이벤트 스트림과 `span.*` 이벤트(`span.model_request_start` / `span.model_request_end`+`model_usage`)가 있지만,
**OpenTelemetry 연동, 로그 집계, 메트릭/대시보드, 승인 이벤트를 넘어선 커스텀 감사 로그는 문서에 없다.**

#### C5 — 동시성·격리

| 항목 | 내용 | 출처 (확인 2026-09-20) |
| --- | --- | --- |
| 격리 단위 | **세션 1개 = 건 1개.** 문서 원문: "Each session gets its own sandbox instance, even when multiple sessions reference the same environment. **Sessions do not share filesystem state.**" | environments §Environment lifecycle |
| 환경 재사용 | 환경은 아카이브/삭제 전까지 유지되며 **버전 관리되지 않는다.** 자주 바꾸면 어느 세션이 어떤 설정으로 돌았는지 직접 기록해 두라고 문서가 권고 | environments |
| 샌드박스 네트워크 | `networking: {type: "unrestricted"}`(기본, 일반 안전 차단 목록 제외 전체 허용) 또는 `{type: "limited"}` + `allowed_hosts`. **`web_search`/`web_fetch`는 Anthropic 서버에서 돌기 때문에 이 설정의 영향을 받지 않는다** — 그쪽은 도구 엔트리의 `allowed_domains`/`blocked_domains`로 따로 제한 | environments §Networking |
| 세션 목록 | `GET /v1/sessions` 페이지네이션(`limit`, `page` 커서, `order` asc/desc). `agent_id` 등으로 필터 | session-operations |
| 세션별 설정 오버라이드 | `agent_with_overrides`로 세션 하나만 `model`/`system`/`tools`/`mcp_servers`/`skills` 교체. **머지가 아니라 전체 치환** | sessions |
| 에이전트 버전 고정 | `agent: {type: "agent", id, version}` 로 세션을 특정 에이전트 버전에 핀. 실행 중 세션은 생성 시점 툴셋 설정을 유지 | sessions |
| 멀티에이전트 | 한 세션 안에 여러 thread. `session.thread_created` 등 thread 단위 이벤트 | reference |
| **Rate limit** | **생성 엔드포인트(에이전트/세션/환경 등) 300 req/min, 읽기 엔드포인트(retrieve/list/stream) 1,200 req/min** — 조직 단위 | reference §Rate limits |
| 동시 세션 수 상한 | **문서에 명시 없음** (조직 단위 spend limit과 usage-tier rate limit이 별도로 적용된다고만 기술) | reference |

**동시 세션 개수 자체의 상한은 문서에서 찾지 못했다 → 빈칸.** (§6 참고)

---

## 3. 후보 C — 워크플로 오케스트레이션 도구

### 3.0 버전 확인 (패키지 레지스트리, 2026-09-20 직접 조회)

| 후보 | 패키지 | 버전 | 출처 |
| --- | --- | --- | --- |
| Temporal | `temporalio` (Python) | **1.33.0** | <https://pypi.org/pypi/temporalio/json> |
| Temporal | `@temporalio/client` (TS) | **1.24.0** | <https://registry.npmjs.org/@temporalio/client/latest> |
| Inngest | `inngest` (TS) | **4.20.0** | <https://registry.npmjs.org/inngest/latest> |
| Inngest | `inngest` (Python) | **0.5.19** (**0.x — 1.0 미도달**) | <https://pypi.org/pypi/inngest/json> |
| LangGraph | `langgraph` (Python) | **1.2.11** | <https://pypi.org/pypi/langgraph/json> |
| LangGraph | `@langchain/langgraph` (JS) | **1.4.16** | <https://registry.npmjs.org/@langchain/langgraph/latest> |

이 세 후보는 모두 **에이전트 전용 런타임이 아니라 범용 오케스트레이션 계층**이며,
Claude 호출은 그 위에서 후보 B1(수동 tool-use 루프) 또는 후보 A(Agent SDK)로 구현하게 된다.
**즉 후보 C는 A/B의 대안이 아니라 A/B를 감싸는 층이다.** 이 점이 #9 결정에서 중요하다.

### 3.1 Temporal

#### C1 — 사람 승인(HITL)

**"멈추고 기다리기"가 언어 차원의 1급 개념이다.** 세 가지 메시지 프리미티브
(출처: <https://docs.temporal.io/encyclopedia/workflow-message-passing>, 확인 2026-09-20):

| 프리미티브 | 문서 정의 | 이벤트 히스토리 기록 |
| --- | --- | --- |
| **Query** | "read requests. They can read the current state of the Workflow but **cannot block**" | **기록되지 않음** ("never add entries to the Workflow Event History") |
| **Signal** | "**asynchronous** write requests. They cause changes in the running Workflow, but you **cannot await any response or error**" | 기록됨 |
| **Update** | "**synchronous, tracked** write requests. The sender of the Update **can wait for a response** on completion or an error on failure" | accepted 시 기록됨 |

Python 구현 (출처: <https://docs.temporal.io/develop/python/message-passing>, 확인 2026-09-20):

- `@workflow.signal` — "A Signal handler mutates the Workflow state but cannot return a value." `async def` 가능(액티비티 실행/조건 대기 가능)
- `@workflow.update` — "An Update handler can mutate the Workflow state and return a value." `@<update-handler-name>.validator` 로 **기록 전에 거절** 가능
- `@workflow.query` — "A Query handler returns a value: it can inspect but must not mutate the Workflow state." 반드시 `def`(`async def` 불가)
- **`await workflow.wait_condition(lambda: self.approved_for_release)`** — 조건이 참이 될 때까지 워크플로를 블로킹

승인 대기 중 워크플로는 **워커 메모리를 점유하지 않는다**(내구성 실행 모델의 본질). 대기 자체에 별도 타임아웃은 없고, 타이머를 같이 걸어 데드라인을 만드는 것이 일반 패턴이다.

#### C2 — 장기 실행과 상태

이벤트 히스토리가 곧 상태다. **Temporal Cloud의 정확한 수치**
(출처: <https://docs.temporal.io/cloud/limits>, 확인 2026-09-20):

| 항목 | 값 |
| --- | --- |
| 이벤트 히스토리 **하드 리밋** | **51,200 이벤트 또는 50 MB** |
| 이벤트 히스토리 **경고 임계치** | **10,240 이벤트 또는 10 MB** |
| 워크플로 보존 기간 | 기본 **30일**, **1–90일** 설정 가능 |
| 미완료 동시 작업(액티비티/시그널/자식 워크플로/취소) | 최대 **2,000**, 권장 **500 이하** |
| 실행당 시그널 수 | **10,000** |
| in-flight Update | **10** / 히스토리 총 Update **2,000** |
| 네임스페이스 쿼터 | 계정당 **10**(자동 증가) |
| 네임스페이스 rate limit (APS) | **500 actions/sec** (On-Demand 기본) |
| Visibility API | **30 calls/sec** |
| gRPC 메시지 | **4 MB** / 단일 요청 페이로드 **2 MB** |

히스토리가 한계에 가까워지면 **Continue-As-New**로 히스토리를 잘라 새 실행으로 넘긴다.
액티비티 재시도 정책, start-to-close / schedule-to-close / heartbeat 타임아웃이 런타임 기능으로 제공된다.

**핵심 제약: 워크플로 코드는 결정적(deterministic)이어야 한다.** 문서 원문
(출처: <https://docs.temporal.io/workflow-definition>, 확인 2026-09-20):

> "a Workflow Definition can not have inline logic that branches (emits a different Command sequence) based off a local time setting or a random number."
> "All operations that do not purely mutate the Workflow Execution's state should occur through a Temporal SDK API."

<https://docs.temporal.io/workflows>(확인 2026-09-20)는 문제 패턴으로 `Date.now()` 직접 호출, 난수, 기록되지 않은 네트워크 호출을 든다.
Python SDK는 **샌드박스**로 이를 강제한다: 워크플로 정의 파일을 새로 만든 샌드박스에 import하고
"proxy objects on modules wrapped around the custom importer"로 "known non-deterministic library calls"를 막는다
(기본 제한 예시로 `datetime.date.today()`가 명시됨).
표준 라이브러리와 Temporal 모듈은 pass-through, 그 외 모듈은 실행마다 재로딩된다.
출처: <https://docs.temporal.io/develop/python/python-sdk-sandbox> (확인 2026-09-20)

→ **LLM 호출은 워크플로가 아니라 액티비티 안에 있어야 한다.** 이것이 Temporal 위에 에이전트를 올릴 때의 구조적 제약이다.

#### C3 — 프론트엔드로의 진행 상황 전달

**서버 푸시(SSE/WebSocket) 메커니즘을 1차 자료에서 찾지 못했다.** 문서가 제시하는 것은 **폴링**이다:

> "You could poll periodically with Queries until the Workflow is ready" — 그리고 효율·지연 면에서는 읽기를 Update로 구현하는 편이 낫다고 덧붙인다.
> — <https://docs.temporal.io/encyclopedia/workflow-message-passing> (확인 2026-09-20)

Query는 이벤트 히스토리에 남지 않으므로 고빈도 폴링에 적합하지만, Visibility API는 **30 calls/sec**로 제한된다(cloud/limits).
→ **LLM 토큰 스트리밍 같은 고빈도 진행 표시는 Temporal 바깥(별도 채널)에서 처리해야 한다.** (§6 빈칸 참고)

#### C4 — 도구 권한과 감사 기록

- **도구 권한이라는 개념은 없다.** 범용 워크플로 엔진이므로 "도구"를 모른다.
- **감사 기록은 이벤트 히스토리가 사실상 제공한다.** Signal/Update는 히스토리에 기록되고, Update는 accepted/rejected가 추적된다. Query는 기록되지 않으므로 **승인 행위를 Query로 구현하면 감사 흔적이 남지 않는다.**
- **승인자 신원은 자동 기록되지 않는다.** 문서 확인 결과, 핸들러 입력 구조체에 직접 담아야 한다(예: `ApproveInput(name: str)`).
  출처: <https://docs.temporal.io/develop/python/message-passing> (확인 2026-09-20)

#### C5 — 동시성·격리

- 격리 단위는 **Workflow Execution**(워크플로 ID 단위). 건마다 워크플로 하나를 띄우는 것이 자연스러운 모델이다.
- 실행 라우팅은 **Task Queue**, 격리 경계는 **Namespace**(계정당 기본 10개).
- 처리량 제약은 위 표의 APS 500/sec, 미완료 동시 작업 2,000(권장 500 이하).
- **동시 워크플로 실행 개수 자체의 상한은 문서에서 확인하지 못했다** — 워커 수로 스케일하는 모델로 보이나 수치 근거 없음.

---

### 3.2 Inngest

#### C1 — 사람 승인(HITL)

**`step.waitForEvent`가 1급 프리미티브이고, 문서가 이를 명시적으로 HITL 용도로 든다.**
"useful [to] implement Human in the loop in AI Agent workflows"
(출처: <https://www.inngest.com/docs/features/inngest-functions/steps-workflows/wait-for-event>, 확인 2026-09-20)

파라미터: **`event`**(기다릴 이벤트 타입), **`timeout`**(예: `"3d"`), **`if`**(상관관계 조건식).
타임아웃 시 TypeScript에서 **`null`을 반환한다** ("if no event is received within 3 days, `onboardingCompleted` will be null")
→ **거부·무응답을 예외가 아니라 값으로 분기**하는 모델이다.

대기 가능 기간의 실질 상한은 usage limits가 정한다(아래 C2).

#### C2 — 장기 실행과 상태

**Step 메모이제이션 기반 durable execution.**
"each step runs once, its result is persisted, and subsequent executions skip completed steps by injecting their stored results."
"Function state is persisted outside of the function execution context. This enables function execution to be resumed from the point of failure on the same *or* different infrastructure."

**가장 중요한 경고 (문서 원문):**

> "Each step in your function is executed as a **separate HTTP request**. Any non-deterministic logic (such as DB calls or API calls) **must be placed within a `step.run()` call**."

→ **step 바깥의 코드는 매 invocation마다 다시 실행된다.** LLM 호출과 사내 시스템 호출은 반드시 `step.run()` 안에 있어야 한다.
출처: <https://www.inngest.com/docs/learn/how-functions-are-executed> (확인 2026-09-20)

**재시도** (출처: <https://www.inngest.com/docs/guides/error-handling>, 확인 2026-09-20):

- 기본 **"up to four times in addition to the initial attempt"** (= 최초 1회 + 재시도 4회). `retries` 옵션으로 조정, `retries: 0`으로 비활성화
- **step 단위 재시도.** 이미 성공한 이전 step은 저장된 결과를 재사용하고 다시 돌지 않는다
- **`NonRetriableError`** — 영구 실패(잘못된 입력, 없는 레코드)에 남은 재시도를 건너뛴다
- 재시도 소진 시 `onFailure` 핸들러 또는 **`inngest/function.failed`** 시스템 이벤트
- 문서가 **멱등성 요구**를 명시: 재시도되는 코드는 여러 번 돌아도 중복 부작용을 만들면 안 된다

**수치 제약** (출처: <https://www.inngest.com/docs/usage-limits/inngest>, 확인 2026-09-20):

| 항목 | Free | Basic | Pro | Enterprise |
| --- | --- | --- | --- | --- |
| 최대 함수 실행 기간 | **30일** | 90일 | 366일 | custom |
| 최대 sleep 기간 | **7일** | 최대 1년 | 최대 1년 | 최대 1년 |
| **최대 동시 step 수(concurrency)** | **5** | 25 | 200+ | custom |
| 단일 이벤트 페이로드 | 256 KiB | 512 KiB | 3 MiB | custom |
| 트레이스/로그 보존 | **24시간** | 7일 | 14일 | 90일 |
| 이벤트 lookback | 1시간 | 1시간 | 3일 | custom |

플랜 무관 공통: 함수당 **최대 step 1,000개**, step 출력 **4 MiB**, step 타임아웃 **최대 2시간**,
함수 run state **32 MiB**, 요청당 이벤트 **5,000개**, 배치 하드캡 **10 MiB**, 이벤트 이름 **256자**.

#### C3 — 프론트엔드로의 진행 상황 전달

**Inngest Realtime이 pub/sub을 제공한다** (출처: <https://www.inngest.com/docs/features/realtime>, 확인 2026-09-20):

| 요소 | 내용 |
| --- | --- |
| 발행 (비내구성) | `inngest.realtime.publish()` — "non-durable and fires immediately". 고빈도 업데이트용 |
| 발행 (내구성) | `step.realtime.publish()` — "a durable step that is memoized, so it will **not re-fire if the function retries**". 중요한 상태 전이·최종 결과용 |
| 채널/토픽 | 채널은 범위(사용자 세션·문서·배치 잡), 토픽은 채널 내 타입 있는 페이로드. Standard Schema 검증기(Zod 또는 `staticSchema<T>()`) 필요 |
| React 훅 | **`useRealtime`** (`inngest/react`) — 토큰 갱신·재연결·버퍼링 관리. 파라미터: `channel`, `topics`, `token`, `enabled`, `bufferInterval`, `historyLimit` |
| 구독 인증 | `getClientSubscriptionToken()` — 서버에서 인가 후 발급. 토큰은 **채널 1개 + 명시된 토픽 목록**으로 스코프. "the token is a capability, so only hand one out once you know this user may read this channel" |

**주의**: 이 페이지에서 GA/베타 안정성 표기를 찾지 못했다(§6 빈칸).
`step.realtime.publish()`가 memoize된다는 점은 **재시도 시 중복 알림을 막아주는 동시에, 재개 후 프론트엔드가 그 이벤트를 다시 받지 못한다**는 뜻이기도 하다.

#### C4 — 도구 권한과 감사 기록

- **도구 권한 개념 없음.** 범용 워크플로 플랫폼이다.
- 감사 기록은 **run/step 히스토리**가 제공하지만, 보존 기간이 플랜에 묶인다: **Free 24시간 / Basic 7일 / Pro 14일 / Enterprise 90일.**
  → 인사 승인 기록을 규정 기간 보관해야 한다면 **Inngest 안에 두면 안 되고 자체 DB에 써야 한다.**
- "누가 승인했는가"는 `waitForEvent`로 기다리는 **승인 이벤트 페이로드에 내가 직접 담는 것**이 구조상 자연스럽다 — 즉 내 설계이지 플랫폼 기능이 아니다.
- 별도 감사 로그(audit log) 기능은 확인하지 못했다(§6 빈칸).

#### C5 — 동시성·격리

- 격리 단위는 **function run 1개**. 이벤트 하나가 run 하나를 만든다.
- **concurrency는 플랜별 "최대 동시 step 수"로 하드 제한된다 — Free 5, Basic 25, Pro 200+.**
  키 기반 가상 큐(`concurrency` 설정), `throttle`, `rateLimit`, `debounce` 등의 제어 수단이 존재하나, 이 조사에서 각각의 정확한 파라미터까지는 확인하지 못했다(§6 빈칸).

---

### 3.3 LangGraph

#### C1 — 사람 승인(HITL)

**`interrupt()`가 1급 프리미티브다.**
(출처: <https://docs.langchain.com/oss/python/langgraph/interrupts>, 확인 2026-09-20)

- `from langgraph.types import interrupt` — "The function accepts any JSON-serializable value which is surfaced to the caller."
- 재개: `from langgraph.types import Command` → `Command(resume=user_response)`
- **영속 checkpointer가 필수.** "the checkpointer writes the exact graph state so you can resume later, even when in an error state." `config={"configurable": {"thread_id": ...}}` 로 어느 상태를 불러올지 지정
- 감지: `stream_events(..., version="v3")`의 `stream.interrupted`(bool), `stream.interrupts`(Interrupt 페이로드 튜플), `stream.output`

**문서가 경고하는 네 가지 함정 (모두 원문 인용, 확인 2026-09-20):**

1. **노드 전체가 처음부터 재실행된다** — "the node restarts from the beginning of the node where the `interrupt()` was called when resumed, so **any code before the `interrupt()` runs again**."
   → `interrupt()` 앞의 부작용(DB 쓰기, 메일 발송)은 **멱등이어야 한다.**
2. **`try/except`로 감싸면 안 된다** — "wrapping the `interrupt()` call in a try/except block, you will catch this exception and the interrupt will not be passed back to the graph."
3. **순서가 의미를 가진다** — resume 값 매칭이 "strictly index-based, so the order of interrupt calls within the node is important."
4. **비결정적 루프 금지** — "Do not loop `interrupt()` calls using logic that isn't deterministic across executions, including `while True` validation loops." 대신 conditional edge를 쓰라고 안내
5. 추가로 `Command(update=...)`를 멀티턴 대화 계속에 쓰지 말라는 경고, 그리고 JSON 직렬화 가능한 값만 쓰라는 제약

**정적 interrupt는 프로덕션 HITL용이 아니다.** `builder.compile(interrupt_before=[...], interrupt_after=[...], checkpointer=...)` 는
문서가 **"for debugging only — not recommended for production human-in-the-loop workflows"** 로 명시한다.

#### C2 — 장기 실행과 상태

**Checkpointer가 상태를 책임진다**
(출처: <https://docs.langchain.com/oss/python/langgraph/durable-execution>, 확인 2026-09-20 — 해당 URL은 persistence 개념 문서를 반환한다):

| Checkpointer | 용도 |
| --- | --- |
| `InMemorySaver` | RAM 저장. **"does not persist between restarts"** → **HITL 프로덕션에 사용 불가** |
| `SqliteSaver` | "Local file-based storage for **development**" |
| `PostgresSaver` / `AsyncPostgresSaver` | 프로덕션 |

- 스레드 키: `{"configurable": {"thread_id": "thread-1"}}`. **`thread_id`는 255자 미만**이어야 PostgreSQL 오류를 피한다
- **Checkpointer(스레드 범위 단기 메모리)와 Store(스레드 교차 장기 메모리)는 별개 시스템**이다
- 문서가 **"Checkpoints growing unboundedly"** 를 문제로 지적하며 pruning 전략을 요구한다 → **보존 정책을 내가 설계해야 한다**
- **중단 상태 유지 가능 기간에 대한 상한은 문서에 없다.** 내 Postgres가 보관하는 한 유지된다고 읽히지만 명시적 서술은 확인하지 못했다(§6 빈칸)

#### C3 — 프론트엔드로의 진행 상황 전달

**스트림 모드 7종** (`stream()` / `astream()`, 출처: <https://docs.langchain.com/oss/python/langgraph/streaming>, 확인 2026-09-20):

| 모드 | 내용 |
| --- | --- |
| `values` | "Full state after each step." |
| `updates` | "State updates after each step." |
| `messages` | "(LLM token, metadata) from LLM calls." |
| `custom` | "Custom data emitted from nodes via `get_stream_writer`." |
| `checkpoints` | "Checkpoint events (same format as `get_state()`)." |
| `tasks` | "Task start/finish events with results and errors." |
| `debug` | "All available info — combines checkpoints and tasks." |

노드 안에서 임의 진행 상황을 밀어 넣는 방법:
`from langgraph.config import get_stream_writer` → `writer({"custom_key": "value"})` + `stream_mode="custom"`.

**OSS 라이브러리에는 내장 HTTP/SSE 서버가 없다.** 해당 문서에 서버 구현 안내가 없으며, 별도로 만들어야 한다.
→ **`messages` 모드가 LLM 토큰 단위 스트림을 주므로, 이 후보만 "토큰 스트리밍"이 라이브러리 레벨에서 바로 나온다.**

#### C4 — 도구 권한과 감사 기록

- **도구 권한 개념이 내장되어 있지 않다.** `interrupt()`로 승인 게이트를 만들 수는 있으나, "이 도구는 항상 승인 필요" 같은 선언형 정책 레이어는 확인하지 못했다.
- **감사 기록은 checkpoint 히스토리**가 사실상 담당한다(`checkpoints` 스트림 모드, `get_state()`). 다만 이것은 그래프 상태 스냅샷이지 승인 감사 레코드가 아니다.
- **승인자 신원은 내가 `Command(resume=...)` 값과 그래프 state에 직접 넣어야 한다.**
- 관측성은 LangSmith(별도 유료 제품)가 담당하는 구조로 보이나, 이 조사에서 LangSmith의 감사 기능까지는 확인하지 못했다(§6 빈칸).

#### C5 — 동시성·격리

- 격리 단위는 **thread (`thread_id`)**. 건마다 thread 하나가 자연스러운 모델이다.
- 스레드 교차 데이터는 **Store**로 분리된다.
- **동시성 제한·큐잉은 OSS 라이브러리가 제공하지 않는다.** 그래프는 그냥 내 프로세스 안의 파이썬 객체이므로, 워커/큐는 내가 만들거나 관리형 플랫폼을 써야 한다.
- 같은 thread에 동시 run이 들어올 때의 정책(`reject`/`rollback`/`interrupt`/`enqueue` 같은 multitask 전략)은 **관리형 플랫폼 쪽 기능으로 알려져 있으나 이 조사에서 1차 자료로 확인하지 못했다**(§6 빈칸).

#### 관리형 플랫폼(LangSmith Deployment / "Agent Server")

<https://docs.langchain.com/langgraph-platform/index>(확인 2026-09-20)는 이를
"a workflow orchestration runtime purpose-built for agent workloads"로 소개하고,
"managed infrastructure agents need to run reliably in production at scale",
"durable execution, real-time streaming, and horizontal scaling"을 제공한다고 서술하며 런타임 이름으로 "Agent Server"를 든다.
**그러나 OSS 라이브러리 대비 정확히 무엇이 더 제공되는지, API 엔드포인트 구성, 가격, 서버 소스 공개 여부는 이 페이지에서 확인하지 못했다**(§6 빈칸).
→ **#9에서 LangGraph를 진지하게 고려한다면, 이 부분은 추가 조사가 필요한 열린 항목이다.**

---

## 4. 제약 요약표

### 4.1 후보 × 다섯 기준 매트릭스

표기: **1급** = 런타임이 제공하는 명시적 개념 / **부분** = 수단은 있으나 제약이 큼 / **직접** = 애플리케이션이 만든다 / **없음** = 해당 개념 부재

#### C1 — 사람 승인(HITL) 지점

| 후보 | 등급 | 표현 방식 | 결정적 제약 |
| --- | --- | --- | --- |
| **A** Agent SDK | **1급** | `canUseTool` 콜백, `PreToolUse` 훅의 `allow`/`deny`/`ask`/**`defer`**, permission mode 6종, allow/deny/ask 규칙 | `canUseTool`은 프로세스가 살아 있어야 함. `defer`는 `-p` 모드 + **한 턴 한 도구**만, 세션 파일 30일 후 삭제 |
| **B1** 수동 루프 | **직접** | 루프의 임의 지점에서 멈춘다 | 전부 자체 구현. 대신 제약도 없음 |
| **B2** Tool Runner | **없음(권장 배제)** | 루프 body에서 `break` / 히스토리 take over | 문서가 "HITL이면 수동 루프를 쓰라"고 명시 |
| **B3** Managed Agents | **1급** | `permission_policy`: `always_allow`/`always_ask`/`auto`, `session.status_idle` + `stop_reason.requires_action` → `user.tool_confirmation` | **무기한 대기 가능.** 단 `auto`는 사람 체크포인트가 아니고, `auto` 거부는 뒤집을 수 없음(400). 커스텀 도구는 정책 미적용 |

#### C2 — 장기 실행 작업과 상태

| 후보 | 등급 | 상태 보관 위치 | 재시도·타임아웃 | 결정적 제약 |
| --- | --- | --- | --- | --- |
| **A** Agent SDK | **부분** | `~/.claude/projects/<encoded-cwd>/*.jsonl` (로컬 디스크) + 선택적 `sessionStore` 미러 | **없음** (`maxTurns`, `maxBudgetUsd` 상한만) | 세션 파일이 **생성 머신 로컬**. 재개는 `cwd` 일치 필요. 30일 보존 |
| **B1** 수동 루프 | **직접** | 내 DB (API는 stateless) | **없음** (SDK `max_retries` 기본 2, `timeout` 기본 10분) | 전부 자체 구현. 대신 보존 기간·머신 제약 없음 |
| **B2** Tool Runner | **직접** | 인메모리 러너 상태 + 내 DB | `max_iterations` 상한만 | 프로세스 경계를 넘는 재개 방법이 문서에 없음 |
| **B3** Managed Agents | **1급** | **Anthropic 서버** (대화 히스토리 + 샌드박스 파일시스템 + 산출물) | `rescheduling` 상태로 **일시 오류 자동 재시도**, `session.error.retry_status` | ZDR/HIPAA 불가. 세션 삭제 시 산출 파일도 영구 삭제. 유휴 최대 기간 미공개 |

#### C3 — 프론트엔드로의 진행 상황 전달

| 후보 | 등급 | 제공 수단 | 결정적 제약 |
| --- | --- | --- | --- |
| **A** Agent SDK | **부분** | `query()` async iterator, `includePartialMessages`(기본 off), `forwardSubagentText` | **HTTP 엔드포인트 없음.** SSE/WebSocket 중계 서버는 직접 작성. 부분 메시지는 메인 세션만 |
| **B1** 수동 루프 | **부분** | Messages API SSE(`stream: true`), `eager_input_streaming` | Anthropic→내 서버 구간만. 내 서버→프론트엔드는 직접 |
| **B2** Tool Runner | **부분** | `stream=True` → iteration마다 `BetaMessageStream` | 위와 동일 |
| **B3** Managed Agents | **1급** | `GET /v1/sessions/{id}/events/stream` (SSE), `event_deltas[]` 토큰 미리보기, 이벤트 히스토리 `list`, **웹훅** | **커서·시퀀스 번호 없음**(이벤트 `id`로 중복 제거). event delta는 best-effort·재연결 시 미재생·비영속. 웹훅은 순서 미보장 + 3회 실패 시 **유실** |

#### C4 — 도구 권한과 감사 기록

| 후보 | 권한 등급 | 감사 등급 | 감사 레코드의 실체 | 결정적 제약 |
| --- | --- | --- | --- | --- |
| **A** Agent SDK | **1급** | **부분** | OTel `claude_code.tool_decision` 이벤트: `decision`(accept/reject), `source`(config/hook/user_*), `tool_name`, `tool_use_id`, `tool_source`, `tool_parameters` | **승인자 신원 없음.** 도구 인자는 `OTEL_LOG_TOOL_DETAILS=1` 필요. MCP 도구명은 기본 `"mcp_tool"`로 마스킹. `OTEL_*`가 서브프로세스에 전달되지 않음 |
| **B1** 수동 루프 | **없음** | **직접** | 내가 정의한 스키마 | API에 권한 개념 없음(`tool_choice`·`strict`는 권한이 아님). 대신 사내 DB 트랜잭션에 승인 기록을 함께 커밋 가능 |
| **B2** Tool Runner | **없음** | **직접** | 위와 동일 | 러너가 도구를 **자동 실행**하므로 "승인 없이 실행"이 기본 경로 |
| **B3** Managed Agents | **1급** | **1급(구조)** | 모든 `agent.tool_use`/`agent.mcp_tool_use`에 `evaluated_permission` + `evaluation`(`reason_code` 포함), `user.tool_confirmation` 이벤트(`result`, `deny_message`), 모든 영속 이벤트에 `processed_at` | **승인자 신원 없음.** OTel/로그 집계/메트릭/트레이싱 연동이 문서에 없음. 이벤트 보존 기간 미공개 |

#### C5 — 동시성·격리

| 후보 | 등급 | 격리 단위 | 결정적 제약 |
| --- | --- | --- | --- |
| **A** Agent SDK | **직접** | 세션 ID + 작업 디렉터리(`cwd`) | 같은 디렉터리를 공유하면 **파일 변경이 서로 보인다**. 한 세션에 여러 메시지를 넣으면 **한 턴으로 합쳐질 수 있다** → 건당 세션 강제. `Workflow` 도구의 `parallel()`은 **한 건 안의 병렬성**("Same session only") |
| **B1** 수동 루프 | **직접** | 내 DB 레코드 + 내가 만든 트랜잭션 경계 | API 쪽 제약은 rate limit뿐 |
| **B2** Tool Runner | **직접** | 러너 인스턴스 1개 = 1건 | 위와 동일 |
| **B3** Managed Agents | **1급** | **세션 1개 = 건 1개, 세션마다 독립 샌드박스.** "Sessions do not share filesystem state." | 동시 세션 **개수** 상한은 미공개(요청 rate limit만: create 300/min, read 1,200/min). 환경은 **버전 관리되지 않음** |

#### 후보 C (오케스트레이션 계층) — 다섯 기준 한 번에

| 기준 | **Temporal** | **Inngest** | **LangGraph** (OSS) |
| --- | --- | --- | --- |
| **C1** HITL | **1급.** Signal(비동기) / Update(동기, 응답 대기 가능, validator로 사전 거절) / `workflow.wait_condition()`. Query는 블로킹 불가 | **1급.** `step.waitForEvent({event, timeout, if})`. 문서가 명시적으로 "Human in the loop in AI Agent workflows" 용도로 안내. **타임아웃 시 `null` 반환** | **1급.** `interrupt()` + `Command(resume=...)`. **영속 checkpointer 필수.** 정적 interrupt(`interrupt_before/after`)는 문서가 **"debugging only, not recommended for production HITL"** 로 배제 |
| **C2** 장기 실행·상태 | **1급.** 이벤트 히스토리 = 상태. 하드 51,200 이벤트/50 MB, 경고 10,240/10 MB. 보존 기본 30일(1–90일). Continue-As-New. 액티비티 재시도 정책 + 3종 타임아웃. **대가: 워크플로 코드 결정성 강제(Python 샌드박스)** | **1급.** step 메모이제이션. 상태는 실행 컨텍스트 밖에 영속 → 다른 인프라에서도 재개. 기본 재시도 **최초 1회 + 4회**, `NonRetriableError`. **대가: step 바깥 코드는 매번 재실행** | **1급(단 저장소는 내 것).** checkpointer + `thread_id`. `InMemorySaver`는 재시작 시 소실 → **프로덕션 불가**, `PostgresSaver` 필요. **대가: 재개 시 노드가 처음부터 재실행 → 멱등성 필수** |
| **C3** 프론트엔드 전달 | **폴링.** 문서 권고가 "poll periodically with Queries". 서버 푸시 메커니즘 1차 자료에서 미확인. Visibility API는 30 calls/sec 제한 | **1급 pub/sub.** Inngest Realtime: `inngest.realtime.publish()`(비내구) / `step.realtime.publish()`(내구·memoized), 채널·토픽, React `useRealtime`, `getClientSubscriptionToken()` | **부분.** 스트림 모드 7종(`messages`가 **LLM 토큰 단위**). `get_stream_writer`로 커스텀 진행 상황. **내장 HTTP/SSE 서버 없음** |
| **C4** 권한·감사 | 권한 **없음**(도구 개념 부재). 감사는 **이벤트 히스토리가 사실상 제공**(Signal/Update 기록, Query는 **미기록**). **승인자 신원은 자동 기록되지 않음** — 핸들러 입력에 직접 담아야 함 | 권한 **없음**. run/step 히스토리는 있으나 **보존이 플랜에 묶임(Free 24h / Basic 7d / Pro 14d / Ent 90d)** → 규정 보관은 자체 DB 필요. 승인자는 이벤트 페이로드에 내가 담는 구조 | 권한 **없음**. checkpoint 히스토리가 상태 스냅샷을 제공하나 감사 레코드는 아님. 승인자는 `Command(resume=...)` 값과 state에 내가 담음 |
| **C5** 동시성·격리 | **1급.** Workflow Execution = 건 1개. Task Queue로 라우팅, Namespace로 격리(계정당 기본 10). APS 500/sec, 미완료 동시 작업 2,000(권장 ≤500) | **1급(단 플랜에 묶임).** function run = 건 1개. **최대 동시 step: Free 5 / Basic 25 / Pro 200+.** 키 기반 concurrency·throttle·rateLimit·debounce 존재 | **부분.** thread(`thread_id`) = 건 1개, Store로 스레드 교차 데이터 분리. **큐잉·동시성 제어는 OSS가 제공하지 않음** — 내가 만들거나 관리형 플랫폼 필요 |

---

## 5. Deal-breaker — 각 후보가 명백히 부적합해지는 조건

"단점"이 아니라 **"이 조건이 참이면 이 후보는 탈락"** 에 해당하는 것만 적는다. 모두 1차 자료로 확인된 사실에서 도출했다.

### A — Claude Agent SDK

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| A-1 | **승인 대기가 30일을 넘을 수 있다** | `defer` 세션은 `cleanupPeriodDays` 기본 30일 보존 스윕으로 삭제된다 (hooks#defer) |
| A-2 | **한 턴에 여러 도구 호출을 동시에 하면서 그 중 하나만 승인받아야 한다** | `defer`는 "only works when Claude makes a single tool call in the turn". 여러 개면 경고와 함께 무시되고 일반 권한 흐름으로 진행 (hooks#defer) |
| A-3 | **승인 대기 중 서버 프로세스를 살려둘 수 없고, 동시에 `-p` 서브프로세스 구조도 쓸 수 없다** | `canUseTool`은 프로세스가 살아 있어야 하고, `defer`는 `-p` 비대화형 모드에서만 유효 (user-input, hooks#defer) |
| A-4 | **오토스케일·서버리스처럼 재개 호스트를 고정할 수 없다** | 세션 파일은 생성 머신 로컬. `sessionStore`를 붙여도 조회 키가 `cwd`에서 파생되므로 **원래와 일치하는 작업 디렉터리에서 재개해야 한다** (sessions, session-storage) |
| A-5 | **Python/TypeScript를 쓸 수 없다** | 라이브러리는 두 언어뿐. 다른 언어는 CLI를 `-p` 서브프로세스로 감싸야 한다 (overview) |
| A-6 | **claude.ai 로그인/요금제를 제품 사용자에게 제공해야 한다** | 사전 승인 없이는 금지. API 키 인증만 가능 (overview) |
| A-7 | **`0.x` 버전 의존성을 조직이 허용하지 않는다** | TS 0.3.278 / Python 0.2.157 — 둘 다 1.0 미도달 (레지스트리) |

### B1 — Messages API 수동 루프

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| B1-1 | **런타임이 재시도·타임아웃·데드레터를 책임져 주기를 기대한다** | API는 stateless. SDK 클라이언트 재시도(`max_retries` 기본 2)와 타임아웃(기본 10분) 외에 아무것도 없다 (working-with-messages) |
| B1-2 | **에이전트 루프를 직접 작성·유지보수할 인력·시간이 없다** | 루프, 상태 저장, 재개, 병렬 도구 결과 취합, 감사 스키마가 전부 자체 구현 |
| B1-3 | **bash·파일 편집·웹 검색 같은 내장 도구 일습이 곧바로 필요하다** | 수동 루프는 "내가 정의한 도구만" 제공한다. Anthropic 스키마 도구(`bash_20250124`, `text_editor_20250728`)는 스키마만 제공되고 **실행 핸들러는 내가 구현**해야 한다 (tool-use overview) |

### B2 — Tool Runner

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| B2-1 | **사람 승인 게이트가 필요하다** | Anthropic 문서가 직접 배제한다: "When you need human-in-the-loop approval, custom logging, or conditional execution, **use the manual loop instead**" (tool-runner) |
| B2-2 | **프로세스를 넘어서는 중단·재개가 필요하다** | 러너 상태는 인메모리. 직렬화·재개 방법이 문서에 없다 |
| B2-3 | **베타 API에 의존할 수 없다** | `client.beta.messages.tool_runner` — 베타 네임스페이스 |

→ **이 프로젝트의 핵심 요구(사람 승인)와 정면으로 충돌하므로, B2는 단독 런타임 후보로는 사실상 성립하지 않는다.**

### B3 — Claude Managed Agents

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| B3-1 | **인사 데이터에 Zero Data Retention 또는 HIPAA BAA가 필요하다** | "not currently eligible for Zero Data Retention (ZDR) or HIPAA Business Associate Agreement (BAA) coverage" (overview) |
| B3-2 | **Bedrock / Vertex AI / Microsoft Foundry 위에서 돌려야 한다** | Managed Agents 미지원. Claude API와 Claude Platform on AWS에서만 (overview) |
| B3-3 | **베타 API에 프로덕션을 걸 수 없다** | 전 엔드포인트가 `anthropic-beta: managed-agents-2026-04-01` 필요. "Behaviors may be refined between releases" (overview) |
| B3-4 | **대화·샌드박스 상태를 Anthropic 서버에 두면 안 된다** | "stateful by design": 대화 히스토리·샌드박스 상태·산출물이 서버에 저장된다. 자체 인프라를 원하면 self-hosted sandbox가 있으나 **에이전트 루프 자체는 여전히 Anthropic이 돈다** (overview) |
| B3-5 | **모델 자동 판단(`auto`)이 사람 승인을 대체한다고 가정하고 설계한다** | 문서가 명시적으로 부정: "`auto` is not a human checkpoint." 게다가 `auto`가 거부한 호출은 클라이언트가 뒤집을 수 없다(400) (permission-policies) |
| B3-6 | **승인 대기 알림을 웹훅에만 의존해야 한다** | 웹훅은 재시도 3회 후 이벤트를 **조용히 버린다.** "Webhooks aren't a durable log" — 모든 전이를 관찰하려면 API로 reconcile해야 한다 (webhooks) |
| B3-7 | **승인자 신원을 플랫폼이 기록해 주기를 기대한다** | `user.tool_confirmation`에 actor 필드 없음. API 키 하나로 내 서버가 대신 보내는 구조 (§6 빈칸 참고) |

### C1' — Temporal

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| T-1 | **워크플로 코드 안에서 LLM을 직접 호출하고 싶다** | 워크플로는 결정적이어야 한다. Python SDK 샌드박스가 비결정적 라이브러리 호출을 막는다. LLM 호출은 액티비티로 밀려나며, 이는 에이전트 코드를 두 층으로 쪼갠다 (workflow-definition, python-sdk-sandbox) |
| T-2 | **에이전트 진행 상황을 토큰 단위로 프론트엔드에 흘려야 한다** | 서버 푸시 메커니즘을 1차 자료에서 확인하지 못했다. 문서 권고는 Query 폴링이고 Visibility API는 30 calls/sec 제한 |
| T-3 | **한 건이 51,200 이벤트 또는 50 MB를 넘길 수 있는데 Continue-As-New를 설계할 여력이 없다** | 하드 리밋 (cloud/limits) |
| T-4 | **승인 대기가 90일을 넘을 수 있다** | Temporal Cloud 보존 기간 최대 90일 (cloud/limits) |
| T-5 | **포트폴리오 MVP 수준의 운영 여력만 있고 Temporal Cloud 비용도 쓸 수 없다** | 셀프 호스팅 구성 요소·요구사항은 이 조사에서 1차 자료로 확인하지 못했다(§6) — 즉 **운영 부담을 정량화하지 못한 상태로는 선택할 수 없다** |

### C2' — Inngest

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| I-1 | **승인 감사 기록을 플랫폼에 보관해야 하는데 Free/Basic 플랜만 쓸 수 있다** | 트레이스/로그 보존 Free **24시간**, Basic 7일. 인사 결재 기록 보관 기간에 한참 못 미친다 (usage-limits) |
| I-2 | **Free 플랜으로 동시에 5건을 넘게 처리해야 한다** | 최대 동시 step Free **5**, Basic 25 (usage-limits) |
| I-3 | **Free 플랜에서 승인 대기가 7일을 넘을 수 있다** | 최대 sleep 기간 Free **7일** (usage-limits) |
| I-4 | **한 건의 처리가 1,000 step 또는 32 MiB run state를 넘는다** | 플랜 무관 하드 리밋 (usage-limits) |
| I-5 | **step 하나가 2시간을 넘게 걸릴 수 있다** | step 타임아웃 최대 2시간 (usage-limits) |
| I-6 | **내 앱이 Inngest로부터 HTTP 요청을 받을 수 없는 망 구성이다** | "Each step in your function is executed as a separate HTTP request" — 실행 모델 자체가 HTTP 왕복이다 (how-functions-are-executed). 자체 호스팅·Connect 옵션의 요구사항은 이 조사에서 확인하지 못했다(§6) |

### C3' — LangGraph (OSS)

| # | 이 조건이면 탈락 | 근거 |
| --- | --- | --- |
| L-1 | **`interrupt()` 앞의 코드를 멱등하게 만들 수 없다** | "the node restarts from the beginning of the node where the `interrupt()` was called when resumed, so **any code before the `interrupt()` runs again**" — 결재 알림 메일이 재발송되는 식의 사고가 난다 (interrupts) |
| L-2 | **영속 DB(Postgres 등)를 붙일 수 없다** | `InMemorySaver`는 "does not persist between restarts" → 프로세스가 죽으면 대기 중인 승인이 사라진다. HITL에는 사실상 `PostgresSaver`가 필수 |
| L-3 | **큐·워커·동시성 제어를 런타임이 제공해 주기를 기대한다** | OSS 라이브러리는 제공하지 않는다. 별도 관리형 플랫폼 또는 자체 구현이 필요하다 |
| L-4 | **"이 도구는 항상 사람 승인" 같은 선언형 권한 정책이 필요하다** | 내장 개념이 없다. `interrupt()` 호출 위치를 그래프에 직접 배치하는 방식뿐 |
| L-5 | **관리형 플랫폼 비용·라이선스를 지금 확정해야 한다** | LangSmith Deployment의 OSS 대비 제공 범위·가격·소스 공개 여부를 1차 자료로 확인하지 못했다(§6) |

### 후보군 전체에 걸린 공통 제약

**후보 C는 후보 A/B를 대체하지 않는다.** Temporal·Inngest·LangGraph 어디에도 "Claude를 호출하는 에이전트 루프"가 내장되어 있지 않다.
셋 중 무엇을 고르든 그 안에서 다시 **A(Agent SDK)** 또는 **B1(수동 루프)** 을 골라야 하고,
그 순간 A의 제약(프로세스 생존, 세션 파일 로컬성) 또는 B1의 제약(전부 자체 구현)이 그대로 따라온다.
특히 **A + Temporal 조합은 A-4(세션 파일 머신 로컬)와 T-1(워크플로 결정성)이 겹쳐서 설계 난이도가 곱해진다.**

---

## 6. 자료를 찾지 못해 빈칸으로 남은 셀

1차 자료에서 확정하지 못한 항목만 여기 모은다. **추정으로 채우지 않았다.**

| 후보 | 기준 | 못 찾은 것 | 비고 |
| --- | --- | --- | --- |
| A (Agent SDK) | C2 | **동시 실행 세션 수의 상한 / 권장치** | 문서에 없음. 라이브러리이므로 호스트 자원 문제로 보이지만 문서 근거 없음 |
| A (Agent SDK) | C5 | **여러 건을 동시에 돌릴 때의 공식 권장 패턴** | "one per user in a multi-user app" 외에 큐잉·워커 풀 가이드가 문서에 없음 |
| A (Agent SDK) | C2 | **`sessionStore` 어댑터의 안정성 등급** | 인터페이스 자체는 문서화되어 있으나 `sessionStoreFlush`·`loadTimeoutMs`가 *Alpha* 표기. 인터페이스 전체의 안정성 보장 문구는 못 찾음 |
| B3 (Managed Agents) | C5 | **조직당 동시 세션 개수 상한** | reference의 rate limit 표는 **요청 수**(create 300/min, read 1,200/min)만 규정. 동시 세션 개수 상한 자체는 문서에 없음 |
| B3 (Managed Agents) | C2 | **`idle` 세션이 유지되는 최대 기간 / 샌드박스 수명** | "waits indefinitely"만 서술. 샌드박스 컨테이너가 얼마나 살아 있는지, 유휴 세션이 자동 종료되는지에 대한 수치를 못 찾음 |
| B3 (Managed Agents) | C4 | **`user.tool_confirmation` 이벤트의 승인자(actor) 필드** | 이벤트 스키마에 사람 주체를 담는 필드가 문서에 없음. "없다"는 것이 결론이지만, 명시적 부정문이 아니라 부재로 확인한 것이므로 빈칸으로 표시 |
| B3 (Managed Agents) | C4 | **이벤트 히스토리 보존 기간** | `GET /v1/sessions/{id}/events`로 전체를 받을 수 있다고만 서술. 보존 기간 수치 없음 |
| B2 (Tool Runner) | C2 | **러너 상태를 프로세스 경계 너머로 직렬화·재개하는 방법** | 문서에 없음. 실질적으로 B1으로 내려가야 하는 것으로 읽힌다 |

| Temporal | C3 | **서버 푸시(SSE/WebSocket) 메커니즘의 유무** | 문서가 제시하는 것은 Query 폴링뿐. "푸시가 없다"는 결론을 명시적 부정문으로는 확인하지 못했다 |
| Temporal | C2 | **셀프 호스팅 구성 요소와 요구사항** (Cassandra/Postgres/MySQL + Elasticsearch 등) | 확인하지 못함. 운영 부담 정량화 불가 |
| Temporal | C5 | **동시 워크플로 실행 개수의 상한** | cloud/limits는 *실행당* 미완료 작업 2,000과 네임스페이스 APS 500/sec만 규정 |
| Temporal | C2 | **Continue-As-New의 구체적 사용법과 히스토리 절단 시 상태 인계 규칙** | limits 페이지에서 수치만 확인, 메커니즘 상세는 미확인 |
| Inngest | C3 | **Inngest Realtime의 안정성 등급(GA/베타/실험적)** | 해당 문서 페이지에서 상태 표기를 찾지 못함 |
| Inngest | C5 | **`concurrency`/`throttle`/`rateLimit`/`debounce`/`singleton`/`priority`의 정확한 파라미터** | 기능의 존재는 확인, 파라미터 스펙은 미확인 |
| Inngest | C4 | **별도 audit log 기능의 유무** | 확인하지 못함 |
| Inngest | 호스팅 | **자체 호스팅 지원 여부와 Inngest Connect의 요구사항** | 확인하지 못함. "각 step이 별도 HTTP 요청"이라는 실행 모델만 확인 |
| Inngest | C1 | **`waitForEvent` timeout의 하드 상한** | 해당 페이지에 없음. usage-limits의 최대 sleep(Free 7일 / 유료 최대 1년)과 최대 함수 실행 기간이 실질 상한으로 보이나 직접 연결하는 문장은 미확인 |
| LangGraph | C2 | **durability 모드(`"exit"` / `"async"` / `"sync"`)** | 조사한 페이지에 없음 |
| LangGraph | C2 | **중단 상태를 유지할 수 있는 최대 기간** | 명시 없음. 내 Postgres가 보관하는 한으로 읽히나 문장 근거 없음 |
| LangGraph | C5 | **같은 thread에 동시 run이 들어올 때의 multitask 전략**(`reject`/`rollback`/`interrupt`/`enqueue`) | 관리형 플랫폼 기능으로 알려져 있으나 1차 자료 미확인 |
| LangGraph | 플랫폼 | **LangSmith Deployment가 OSS 대비 추가 제공하는 것, API 엔드포인트, 가격, 서버 소스 공개 여부** | index 페이지에 비교 정보 없음. **#9 전에 반드시 채워야 할 항목** |
| LangGraph | C4 | **LangSmith의 감사·추적 기능 범위** | 확인하지 못함 |
| 전체 | — | **각 후보의 실측 운영 비용** | 조사 범위 밖(#9의 입력으로 별도 필요) |

> **방법론 주석**: 이 조사는 세션의 웹 검색 예산(200회)을 소진했다.
> 위 빈칸 중 Temporal 셀프 호스팅, Inngest 자체 호스팅/Connect, LangSmith Deployment 세 항목은
> **#9 결정에 직접 영향을 주므로 후속 조사 대상으로 남긴다.**

---

## 7. 출처 목록

모든 URL 확인일: **2026-09-20**.

### 7.1 후보 A — Claude Agent SDK

| # | 문서 | URL |
| --- | --- | --- |
| A1 | Agent SDK overview | <https://code.claude.com/docs/en/agent-sdk/overview> |
| A2 | Configure permissions | <https://code.claude.com/docs/en/agent-sdk/permissions> |
| A3 | Handle approvals and user input | <https://code.claude.com/docs/en/agent-sdk/user-input> |
| A4 | Work with sessions | <https://code.claude.com/docs/en/agent-sdk/sessions> |
| A5 | Persist sessions to external storage (`SessionStore`) | <https://code.claude.com/docs/en/agent-sdk/session-storage> |
| A6 | Hooks reference (특히 `#pretooluse-decision-control`, `#defer-a-tool-call-for-later`) | <https://code.claude.com/docs/en/hooks> |
| A7 | TypeScript SDK reference (`Options` 표) | <https://code.claude.com/docs/en/agent-sdk/typescript> |
| A8 | Streaming Input | <https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode> |
| A9 | Monitoring usage (OpenTelemetry, `tool_decision` 이벤트) | <https://code.claude.com/docs/en/monitoring-usage> |
| A10 | npm 패키지 메타데이터 (0.3.278, node>=18, 네이티브 바이너리) | <https://registry.npmjs.org/@anthropic-ai/claude-agent-sdk/latest> |
| A11 | PyPI 패키지 메타데이터 (0.2.157, python>=3.10) | <https://pypi.org/pypi/claude-agent-sdk/json> |

### 7.2 후보 B — Anthropic 1차 제공 수단

| # | 문서 | URL |
| --- | --- | --- |
| B-a | Tool use with Claude (개요·루프) | <https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview> |
| B-b | Parallel tool use | <https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use> |
| B-c | Tool runner (SDK) | <https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner> |
| B-d | Working with the Messages API (statelessness) | <https://platform.claude.com/docs/en/build-with-claude/working-with-messages> |
| B-e | Streaming (SSE) | <https://platform.claude.com/docs/en/build-with-claude/streaming> |
| B-f | Compaction | <https://platform.claude.com/docs/en/build-with-claude/compaction> |
| B-g | Context editing | <https://platform.claude.com/docs/en/build-with-claude/context-editing> |
| B-h | CLI, SDKs, and libraries (7개 언어) | <https://platform.claude.com/docs/en/cli-sdks-libraries/overview> |
| B-i | Managed Agents overview (베타·ZDR 불가) | <https://platform.claude.com/docs/en/managed-agents/overview> |
| B-j | Managed Agents — Start a session (budget, overrides, initial_events) | <https://platform.claude.com/docs/en/managed-agents/sessions> |
| B-k | Managed Agents — Session operations (상태, 페이지네이션, archive/delete) | <https://platform.claude.com/docs/en/managed-agents/session-operations> |
| B-l | Managed Agents — Permission policies (`always_ask`, `auto`, `evaluated_permission`) | <https://platform.claude.com/docs/en/managed-agents/permission-policies> |
| B-m | Managed Agents — Events and streaming (SSE, event deltas) | <https://platform.claude.com/docs/en/managed-agents/events-and-streaming> |
| B-n | Managed Agents — Environments (샌드박스 격리, networking) | <https://platform.claude.com/docs/en/managed-agents/environments> |
| B-o | Managed Agents — Webhooks (`session.status_idled`, 재시도 3회) | <https://platform.claude.com/docs/en/managed-agents/webhooks> |
| B-p | Managed Agents — Reference (이벤트 타입, rate limits) | <https://platform.claude.com/docs/en/managed-agents/reference> |
| B-q | Managed Agents — Observability | <https://platform.claude.com/docs/en/managed-agents/observability> |
| B-r | PyPI `anthropic` 1.7.0 | <https://pypi.org/pypi/anthropic/json> |
| B-s | npm `@anthropic-ai/sdk` 0.127.0 | <https://registry.npmjs.org/@anthropic-ai/sdk/latest> |
| B-t | Python SDK (재시도 기본 2회, 타임아웃 기본 10분) | <https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python> |

### 7.3 후보 C — 워크플로 오케스트레이션

| # | 문서 | URL |
| --- | --- | --- |
| T-a | Temporal — Workflow message passing (Signal / Query / Update) | <https://docs.temporal.io/encyclopedia/workflow-message-passing> |
| T-b | Temporal — Python message passing (`@workflow.signal/query/update`, `wait_condition`) | <https://docs.temporal.io/develop/python/message-passing> |
| T-c | Temporal Cloud — Limits (51,200 이벤트/50 MB 등 전 수치) | <https://docs.temporal.io/cloud/limits> |
| T-d | Temporal — Workflow definition (결정성 제약) | <https://docs.temporal.io/workflow-definition> |
| T-e | Temporal — Workflows (replay와 비결정성 문제 패턴) | <https://docs.temporal.io/workflows> |
| T-f | Temporal — Python SDK sandbox | <https://docs.temporal.io/develop/python/python-sdk-sandbox> |
| T-g | PyPI `temporalio` 1.33.0 | <https://pypi.org/pypi/temporalio/json> |
| T-h | npm `@temporalio/client` 1.24.0 | <https://registry.npmjs.org/@temporalio/client/latest> |
| I-a | Inngest — `step.waitForEvent` | <https://www.inngest.com/docs/features/inngest-functions/steps-workflows/wait-for-event> |
| I-b | Inngest — How functions are executed (step 메모이제이션, step당 HTTP 요청) | <https://www.inngest.com/docs/learn/how-functions-are-executed> |
| I-c | Inngest — Error handling (기본 재시도, `NonRetriableError`, `inngest/function.failed`) | <https://www.inngest.com/docs/guides/error-handling> |
| I-d | Inngest — Usage limits (전 수치) | <https://www.inngest.com/docs/usage-limits/inngest> |
| I-e | Inngest — Realtime (`publish`, 채널·토픽, `useRealtime`) | <https://www.inngest.com/docs/features/realtime> |
| I-f | npm `inngest` 4.20.0 | <https://registry.npmjs.org/inngest/latest> |
| I-g | PyPI `inngest` 0.5.19 | <https://pypi.org/pypi/inngest/json> |
| L-a | LangGraph — Interrupts (`interrupt()`, `Command(resume=...)`, 재실행 경고) | <https://docs.langchain.com/oss/python/langgraph/interrupts> |
| L-b | LangGraph — Durable execution / Persistence (checkpointer 종류, `thread_id`, Store) | <https://docs.langchain.com/oss/python/langgraph/durable-execution> |
| L-c | LangGraph — Streaming (stream_mode 7종, `get_stream_writer`) | <https://docs.langchain.com/oss/python/langgraph/streaming> |
| L-d | LangSmith Deployment / LangGraph Platform index | <https://docs.langchain.com/langgraph-platform/index> |
| L-e | PyPI `langgraph` 1.2.11 | <https://pypi.org/pypi/langgraph/json> |
| L-f | npm `@langchain/langgraph` 1.4.16 | <https://registry.npmjs.org/@langchain/langgraph/latest> |
