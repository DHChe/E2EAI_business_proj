# 경쟁 제품의 승인 큐·인박스 실물 화면

> 조사 대상 이슈: [#13](https://github.com/DHChe/E2EAI_business_proj/issues/13) · 부모 map: #1 · 선행 조사: [#3](https://github.com/DHChe/E2EAI_business_proj/issues/3)
> 조사 시점: 2026-09-20
> 이 문서는 상호작용 모델 프로토타입(#8)의 재료다. #3은 인터페이스를 **제품 문서의 텍스트 묘사**로만 정리했고, 실제 화면을 본 항목이 하나도 없었다. 이 문서는 그 구멍만 메운다.

## 이 문서를 읽는 법 — 증거 등급

이 티켓이 존재하는 이유가 "본 것과 읽은 것이 섞였다"는 것이므로, 모든 항목에 등급을 붙인다.

| 태그 | 뜻 |
|---|---|
| `[화면-라이브]` | 브라우저로 직접 접속해 눈으로 확인한 화면 |
| `[화면-공식캡처]` | 제품사 공식 문서·저장소의 스크린샷 이미지를 내려받아 직접 판독. 화면 자체는 봤지만 조작하지는 못했다 |
| `[코드]` | 그 화면을 그리는 오픈소스 코드를 직접 읽음. 화면은 아니지만 화면의 **정의**이고, 스크린샷보다 정확하다 |
| `[문서텍스트]` | 제품 문서의 서술만 읽음. #3과 같은 등급 — 화면으로 확인되지 않았다 |
| `[못 봄]` | 확인 실패. 이유를 함께 적는다 |

**추론에는 반드시 "추론"이라고 적었다.** 화면에서 보이지 않는 것은 "보이지 않는다"고 쓰고, 그 자리에 그럴듯한 서술을 채우지 않았다.

스크린샷은 `docs/research/screens/competitor-screens/`에 번호순으로 저장했고, 각 항목에서 파일명과 원본 URL을 함께 적는다. 모두 로그인 없이 접근 가능한 공개 자료다.

---

## 0. 무엇을 봤고 무엇을 못 봤나

### 실제로 화면을 확보한 제품 (3개)

| 제품 | 성격 | 확보한 화면 | 최고 증거 등급 |
|---|---|---|---|
| **LangChain Agent Inbox** | AI-native 범용 인박스, 오픈소스 | 목록 화면, 라이브 빈 상태, 상세 화면의 전체 소스 | `[코드]` + `[화면-공식캡처]` + `[화면-라이브]` |
| **Ramp Policy Agent** | 경비 도메인, AI가 승인/검토/거절을 **추천**하는 제품 | 승인 카드 3종(승인권고/검토필요/거절권고), 사후 상태 카드, 대량 자동승인 롤업, 활동 피드, 에이전트-사람 정렬률 리포트 | `[화면-공식캡처]` |
| **Moveworks Approvals Engine** | HR·IT 직원지원 에이전트, Slack/Teams 인라인 승인 | 승인자 카드, 거절 사유 입력 플로우, 거절 통보, 결재선 진행 상태(worknote) | `[화면-공식캡처]` |

### 화면을 못 본 것 (이유 포함)

- **Ramp 라이브 제품** — `[못 봄]` 공개 데모(<https://ramp.com/view-demo>)가 업무용 이메일 입력 폼 뒤의 **영상** 데모다. 폼 제출은 하지 않았다. 대신 공식 헬프센터의 제품 스크린샷을 썼다.
- **Agent Inbox의 승인 상세 화면(라이브)** — `[못 봄]` 호스팅 앱 <https://dev.agentinbox.ai/>는 접속되지만 첫 화면이 "Welcome to the Agent Inbox! ... Assistant/Graph ID, Deployment URL" 입력 모달이다(`02-agent-inbox-live-add-inbox.jpg`). 실제 LangGraph 배포가 있어야 카드를 볼 수 있어 라이브 상세 화면은 못 봤다. **대신 그 화면을 그리는 소스 전체를 읽어 대체했다** — 등급은 `[코드]`.
- **Microsoft Copilot Studio 승인자 카드** — `[못 봄]` Microsoft Learn의 `flows-advanced-approvals` 페이지에 스크린샷이 15장 있으나 **전부 플로우 빌더(관리자) 화면**이다. 승인자가 보는 카드는 그 페이지에 없다. Power Automate 승인 앱 문서(`/power-automate/approvals-app-navigation`)는 404. → #3이 지적한 "캔버스는 관리자 화면이지 승인자 화면이 아니다"가 **문서 구조 수준에서도** 재확인된다. <https://learn.microsoft.com/en-us/microsoft-copilot-studio/flows-advanced-approvals>
- **ServiceNow AI Control Tower 승인 화면** — `[못 봄]` `servicenow.com/docs`의 딥링크가 문서 홈으로 리다이렉트되어 해당 페이지에 도달하지 못했다. 또한 AI Control Tower의 "approvals"는 **에이전트/자산을 배포 승인하는 거버넌스 화면**이지 업무 승인 큐가 아니어서, 도달했더라도 이 티켓의 질문과는 다른 화면이었을 것이다(문서 제목·요약 기준 **추론**).
- **Workday Inbox** — `[못 봄]` 공식 문서는 로그인 필요. 대학 IT의 공개 PDF 가이드가 있으나 다운로드가 HTML로 반환되어 이미지를 판독하지 못했다. 텍스트 검색으로 확인한 행동 어휘(**Approve / Deny / Send Back**, Bulk Approve)는 `[문서텍스트]` 등급이라 결론에 쓰지 않았다.
- **국내 제품(flex, 더존, 그룹웨어) 화면** — `[못 봄]` 이번 조사 범위에서 손대지 않았다. 한국 결재선은 별도 티켓 #14의 대상이다.

---

## 1. 다섯 가지 질문에 대한 답 (요약)

티켓이 정한 5개 항목에 대해, **화면에서 실제로 확인된 것만** 먼저 요약한다.

### ① 한 건의 승인 카드에 무엇이 담기는가

셋 다 다르고, 그 차이가 이 프로젝트의 설계 선택지다.

- **Agent Inbox**: `action_request.args` 딕셔너리를 **키별 텍스트 상자로 그대로 펼친 것**. 즉 툴 호출 인자 원본이다. 여기에 마크다운 `description` 한 덩어리가 붙는다. 요약문도 아니고 변경 명세도 아니다 — **툴 호출의 raw args**다. `[코드]`
- **Ramp**: `$712.65 at Uluh` — **금액과 상대방이 제목**이다. 그 아래 구조화 필드(`Spent from*`, `Entity*`, `Memo`)와, 에이전트의 판정 배너 + 정책 수치를 인용한 근거 불릿. `[화면-공식캡처]`
- **Moveworks**: 티켓 ID(`RITM011989`)와 대상 시스템(`Github`)이 제목, 그 아래 **레이블 붙은 필드 블록** — `Requestor Info` / `Role Requested` / `Business Justification`. AI가 쓴 문장은 한 줄도 없다. 전부 요청자와 티켓에서 온 값이다. `[화면-공식캡처]`

**→ "전부 자연어 요약 + 예/아니오"라는 #3의 일반화는 화면으로 보면 부정확하다.** 셋 중 자연어 요약을 카드 본문으로 쓰는 제품은 없다. Agent Inbox는 raw args, Ramp와 Moveworks는 **구조화된 필드 목록**이다. AI가 생성한 문장이 카드에 들어가는 것은 Ramp의 **판정 근거 불릿뿐**이고, 그것도 본문이 아니라 별도 배너 안이다.

### ② 승인자가 취할 수 있는 행동의 가짓수와 이름

| 제품 | 화면에 있는 결정 행동 | 부수 행동 |
|---|---|---|
| **Agent Inbox** `[코드]` | `Accept` / `Submit`(=수정 후 승인) / `Send Response` / `Ignore` / `Mark as Resolved` — **5개** | `Reset`, `State`·`Description` 패널 토글, `Studio`(외부 개발도구), 뒤로가기 |
| **Ramp** `[화면-공식캡처]` | 카드에서 직접 보이는 것은 **👍/👎 피드백 2개와 `Options ˅` 메뉴뿐**. 승인/거절 버튼은 캡처 하단이 잘려 보이지 않는다 | `Add fields ˅`, 필드별 인라인 편집(연필·드롭다운) |
| **Moveworks** `[화면-공식캡처]` | `Approve` / `Deny` / `Add comment` / `View other approvals` — **4개** | 거절 후: `View next approval` / `View all approvals` |

Ramp의 행동 목록은 문서 텍스트로만 확인된다: "Approve or reject / Override incorrect approvals or rejections / Request changes or repayment / Provide thumbs up/down feedback on each agent decision". `[문서텍스트]` <https://support.ramp.com/use-policy-agent-for-approvals>

**눈에 띄는 것 — 행동이 두 축으로 갈린다.** Ramp와 Agent Inbox 모두 "이 건을 어떻게 처리할 것인가"와 "에이전트의 판단이 옳았는가"를 **분리**한다. Ramp는 판정 배너 안의 👍/👎로, Agent Inbox는 `accept`/`edit`의 구분으로. Moveworks에는 이 두 번째 축이 아예 없다 — 승인자가 에이전트를 평가할 자리가 화면에 없다. (Moveworks의 승인 카드에는 애초에 에이전트의 판단이 들어 있지 않으므로 그 자체로는 일관된 설계다.)

### ③ 여러 건이 쌓였을 때의 배열·정렬·묶음 방식

세 제품이 **세 가지 전혀 다른 전략**을 쓴다. 이것이 이번 조사에서 가장 큰 수확이다.

- **Agent Inbox — 평평한 목록 + 실행 상태 탭.** 상단 탭이 `All / Interrupted / Idle / Busy / Error`다. 즉 **묶음의 기준이 업무가 아니라 그래프 실행 상태**다. 기본 선택은 `Interrupted`. 하단은 페이지 크기 선택(10/25/50/100)과 `Previous`/`Next`. **정렬 컨트롤이 없고, 일괄 선택 체크박스도 없다.** `[화면-라이브]` + `[코드]` (`01-agent-inbox-list.png`, `02-agent-inbox-live-add-inbox.jpg`)
- **Ramp — 에이전트의 판정으로 섹션을 나눈다.** 홈 화면에서 `Transactions ready to approve` / `Transactions to review` / `Transactions ready to reject`(및 Reimbursements 대응 섹션)로 갈라진다. `[문서텍스트]` 그리고 **자동 승인된 대량 건은 목록에 올리지 않는다** — `971 transactions were automatically approved by agent · 3d ago · Purchases totaling $84,466.99 were in policy` 한 줄짜리 접힌 롤업으로 처리하고 `×`로 닫는다. `[화면-공식캡처]` (`09-ramp-auto-approved-rollup.png`)
- **Moveworks — 목록 화면이 없다. 큐 포인터만 있다.** 한 건을 처리하면 봇이 바로 `You have 5 more approvals to review.`와 `View next approval` / `View all approvals` 버튼을 띄운다. 배치 처리를 **대화 흐름 안에서 한 건씩 밀어주는 방식**이다. `[화면-공식캡처]` (`06-moveworks-deny-reason.png`)

**→ #3의 패턴 카탈로그가 "인박스"라는 하나의 칸에 넣었던 것이 실제로는 최소 세 갈래다: 평평한 목록 / 판정별 섹션 + 롤업 / 큐 포인터.** 그리고 셋 다 **마감일·법정 기한으로 정렬하지 않는다.** 인사·총무는 기한이 1급 속성인 도메인인데, 확인한 어떤 화면에도 기한 축이 없었다.

### ④ 근거·출처를 보여주는 자리가 있는가 (#3의 빈틈 ②)

**있다 — 단, 한 제품뿐이고, 그 제품은 HR이 아니다.**

- **Ramp에는 있다.** 판정 배너 안에 근거가 불릿으로 들어가고, 각 불릿 끝에 ⓘ 아이콘이 붙는다. 실제 문구(캡처에서 판독):
  - 승인 권고: *"The client lunch for 6 attendees cost $712.65, comfortably under the $900 domestic limit set by the $150-per-person domestic cap"* / *"Receipt has been auto-verified"*
  - 검토 필요: *"The daily domestic meal allowance for a single employee is $50"* / *"This $275.76 restaurant charge exceeds the allowed limit for a single employee by $225.76"* / *"The non-itemized receipt indicates that there were four guests, so this expense may be in policy if the employee adds relevant and applicable attendees"*
  - 거절 권고: *"Gift card purchases are prohibited, so the full amount must be repaid"* / *"The provided receipt appears to be generated using artifical intelligence tools"*

  `[화면-공식캡처]` (`03-ramp-approval-cards.png`)

  세 가지가 동시에 들어 있다: **정책 수치의 인용**, **위반 금액의 산술**(초과분 $225.76), 그리고 **판정을 뒤집을 조건**("attendees를 추가하면 in policy일 수 있다"). ⓘ가 정책 원문 툴팁일 것이라는 것은 **추론**이다 — 툴팁을 열어보지 못했다. 다만 문서는 활동 피드가 "The agent's rationale and **cited policy text**"와 "The policy version used"를 남긴다고 명시한다. `[문서텍스트]`
- **Agent Inbox에는 없다.** 상세 화면의 근거 자리는 `State` / `Description` 토글 두 개뿐이다. `State`는 **LangGraph 스레드 상태 원본**이고, `Studio` 버튼은 아예 외부 개발자 도구로 나간다. 즉 근거는 "개발자가 디버깅하는 화면"으로 위임되어 있고, **승인자용 근거 화면은 존재하지 않는다.** `[코드]`
- **Moveworks에는 없다.** 카드의 `Business Justification`은 **요청자가 쓴 문장**이다. 에이전트의 근거가 아니다. 대신 `View other approvals` 버튼과 티켓 worknote가 **절차적 근거**(누가 이미 승인했고 누구를 기다리는가)를 제공한다. `[화면-공식캡처]`

**→ #3의 빈틈 ②("승인자에게 근거를 설명하는 HR 제품이 없다")는 화면으로 확인됐고, 더 날카로워진다.** 빈 것은 "근거 표시 기능"이 아니다. Ramp가 보여주듯 근거 칸은 **판정 배너 안 서너 줄**이면 충분하다. 빈 것은 그 서너 줄을 쓸 수 있게 해 주는 것 — **기계가 대조할 수 있는 형태의 정책 원문**이다. Ramp는 그걸 위해 별도의 "agent-facing policy" 문서와 Policy Editor라는 제품 표면을 따로 만들었다. `[문서텍스트]` 인사·총무에서 이 자리를 채우려면 UI가 아니라 **정책 본문의 기계 판독 가능한 형태**를 먼저 설계해야 한다.

### ⑤ 거절했을 때 무엇이 일어나는가가 화면에 드러나는가

**두 제품이 정반대다. 이 대비가 이번 조사에서 가장 실무적인 발견이다.**

- **Moveworks — 거절이 가장 무겁게 다뤄진다.** `[화면-공식캡처]` (`06`, `07`)
  1. `Deny`를 누르면 즉시 되묻는다: **"Why are you denying this request?"** → *"Your company policy requires you to provide a justification. Please keep typing to add reason or type cancel to exit."* 사유 없이는 거절이 완료되지 않는다(설정 가능한 "Require comment on deny").
  2. 사유는 자유 텍스트다(예: *"It's too expensive. Use regular LinkedIN"*). 구조화된 반려 코드가 아니다.
  3. 확정 후 화면: **❌ "You have denied the request. I will notify Shaumik Mondal as this ticket updates."** — 화면이 알려주는 것은 *무엇이 취소되는가*가 아니라 ***누구에게 통보되는가***다.
  4. 요청자에게 가는 통보에 **거절자 이름과 사유가 그대로 실린다**: *"your request for Xactly, tracked in RITM000876, was denied by Ameet. Please contact IT for help. Comment: Xactly is not aapproved for security reasons. Use Oracle."*
  5. 다건 규칙: *"If any one approver denies the request, then the entire request is denied."* `[문서텍스트]`
- **Agent Inbox — 거절이 가장 가볍게 다뤄진다.** `[코드]`
  - `Ignore` 버튼의 툴팁 문구가 전부다: *"Ignore this interrupt and end the thread."* 스키마상 `ignore` 응답의 `args`는 **`null`** — **사유를 담을 자리가 스키마에 없다.**
  - `Mark as Resolved`는 더 세다. 구현이 `client.threads.updateState(threadId, { values: null, asNode: END })`다 — 그래프를 **강제로 END로 점프**시키고 목록에서 행을 지운다. 토스트 문구는 "Ignored thread". 그래프는 왜 끝났는지 알지 못한다.
  - 즉 **거절 = 이유 없이 실행을 종료시키는 버튼**이고, 아무에게도 통보되지 않는다.
- **Ramp — 거절이 "상환 요구"라는 다른 상태로 번역된다.** 에이전트-사람 정렬률 리포트의 결과 축이 `expense was approved`와 `expense was repaid` **두 가지뿐**이다. 이미 집행된 거래에서 "거절"에 해당하는 종착지는 거부가 아니라 **repayment**다. 상단 KPI 타일도 `Repayments 91.2% of repayments requested have been repaid`로 그 상태를 추적한다. `[화면-공식캡처]` (`04-ramp-activity-and-alignment.png`)

**→ 인사·총무에 옮길 때의 질문이 여기서 구체화된다.** 반려의 후속 상태가 도메인마다 다르다 — 접근권한은 "없던 일", 경비는 "상환", 인사는? (휴가 반려 = 재신청 유도? 발령 반려 = 원안 유지? 경조사 반려 = ?) **반려의 후속 상태를 도메인 모델에서 먼저 정의하지 않으면 반려 버튼을 그릴 수 없다.**

---

## 2. 제품별 상세

### 2.1 LangChain Agent Inbox

저장소: <https://github.com/langchain-ai/agent-inbox> · 호스팅: <https://dev.agentinbox.ai/> · 배경 글: <https://www.langchain.com/blog/introducing-ambient-agents>

#### 목록 화면 `[화면-공식캡처]` `01-agent-inbox-list.png`

원본: <https://raw.githubusercontent.com/langchain-ai/agent-inbox/main/public/inbox_screenshot.png>

- 좌측 레일: 인박스가 **에이전트(그래프)별로** 나열된다 — `Gen Post`, `Translate Code`, `Changelog`, `Email`, `Curated Posts`, `Repurposer`, `LLManager`, `General Inbox` 등. 하단에 `Add Inbox`, `Settings`, `Documentation`.
- 브레드크럼: `General Inbox > Interrupted`
- 탭: `All` / `Interrupted` / `Idle` / `Busy` / `Error`
- 행 한 줄의 구성(코드로 확인, `interrupted-inbox-item.tsx`):
  - 파란 점 — **하드코딩된 `bg-blue-400`**이다. 읽음/안읽음 표시가 아니다. `[코드]`
  - 제목 = `action_request.action` (툴/액션 이름). 값이 없거나 스키마가 깨졌으면 문자열 `"Interrupt"`.
  - 부제 = `description`의 **앞 65자**를 자른 것 + `...`
  - 상태 배지 = `Requires Action`(초록) 또는 `Ignore`(회색). **판정 기준은 `config`의 허용 플래그뿐** — `allow_ignore`만 켜져 있으면 `Ignore`, 아니면 `Requires Action`. 위험도·긴급도·금액과 무관하다.
  - 시각 = `updated_at`을 `MM/dd h:mm a`로.
- **행에 없는 것**: 요청자, 담당자, 우선순위, 기한, 금액, 위험 등급, 일괄 선택 체크박스.
- 블로그의 같은 화면(<https://www.langchain.com/blog/introducing-ambient-agents>)에서는 제목 열이 전부 `ResponseEmailDraft`로 반복된다 — **툴 이름을 제목으로 쓰면 목록이 구분되지 않는다**는 것이 벤더 자신의 스크린샷에서 드러난다.

#### 라이브 확인 `[화면-라이브]` `02-agent-inbox-live-add-inbox.jpg`

<https://dev.agentinbox.ai/> 접속 결과: 같은 5개 탭, 같은 페이지네이션(`10`, `Previous`, `Next`), `No threads found` 빈 상태. 첫 화면에 `Welcome to the Agent Inbox!` 모달이 뜨고 `Assistant/Graph ID`(필수), `Deployment URL`(필수), `Name`(선택)을 요구한다. 자체 LangGraph 배포가 없으면 카드를 볼 수 없어 여기서 멈췄다.

#### 상세 화면 `[코드]` — `components/thread-actions-view.tsx`, `components/inbox-item-input.tsx`

화면 구조(위에서 아래로):

1. 헤더: 뒤로가기 화살표 / 노란 `AlertCircle` 아이콘 / 제목 / `thread_id` 복사 칩 / `Studio` 버튼 / `State`·`Description` 토글 버튼 그룹
2. `Mark as Resolved` 버튼, 그리고 `allow_ignore`일 때만 `Ignore` 버튼
3. 액션 카드 — 아래 세 형태 중 `config` 조합에 따라 결정:
   - **Accept 전용**: `args`를 읽기 전용으로 렌더 + 가로 전폭 `Accept` 버튼
   - **Edit(+Accept)**: 헤더가 `Edit/Accept` 또는 `Edit`. `args`의 키마다 텍스트 상자 하나(키 이름은 `prettifyText`로 사람이 읽게 변환). 우상단 `Reset`. 제출 버튼 라벨이 **상태에 따라 바뀐다** — 수정 전이면 `Accept`, 한 글자라도 고치면 `Submit`.
   - **Respond**: 헤더 `Respond to assistant`, 4줄 텍스트 영역(placeholder `Your response here...`), 버튼 `Send Response`. ⌘/Ctrl+Enter 제출.

스키마(README 기준, 1차): `HumanInterrupt = { action_request: {action, args}, config: {allow_ignore, allow_respond, allow_edit, allow_accept}, description? }`, 응답은 `HumanResponse = { type: 'accept'|'ignore'|'response'|'edit', args: null|string|ActionRequest }`.

**이 설계에서 읽어낼 것 두 가지.**

- `edit`가 1급 행동이라는 점은 #3이 옳게 짚었다. 그리고 화면에서 그것은 **"인자 텍스트 상자를 고친다"**는 구체적 형태다 — 즉 승인 단위가 툴 호출이면 수정 단위도 툴 호출 인자다. 인사·총무의 "이 부분만 고쳐서 진행"을 이 형태로 옮기려면 **행동의 인자가 사람이 읽고 고칠 수 있는 어휘**여야 한다.
- 반대로 **거절 쪽은 비어 있다.** `ignore`의 `args`가 `null`이라는 것은 UI의 누락이 아니라 **스키마의 선택**이다. 승인은 4가지로 쪼개 놓고 거절은 하나, 그것도 이유 없이. 이 비대칭이 이 프로젝트가 파고들 수 있는 가장 구체적인 지점이다.

### 2.2 Ramp Policy Agent

공식 헬프센터: <https://support.ramp.com/use-policy-agent-for-approvals>, <https://support.ramp.com/policy-agent-overview>

#### 승인 카드 3종 `[화면-공식캡처]` `03-ramp-approval-cards.png`

원본: <https://assets.ramp.com/help-center/use-policy-agent-for-approvals/attachments/47618321661203.png>

카드 한 장의 구성(위→아래):

1. 머천트 로고
2. **`$712.65 at Uluh`** — 금액 + 상대방이 제목
3. `Angela Martin · Uluh · Jul 1, 2025 at 5:00 AM` + 우측 `Options ˅`
4. **판정 배너**(색상 구분) + 우측 👍/👎
   - 초록 `Approval recommended` / 노랑 `Requires review` / 빨강 `Rejection recommended`
   - 배너 안에 근거 불릿 1~3개, 각 끝에 ⓘ
5. **`Requirements`** 섹션 — `Complete` 칩, 우측 `Add fields ˅`
   - `Spent from*` = `General Expenses Card (9634)` ˅
   - `Entity*` = `Solutions Inc.` ˅
   - `Memo` = `Client dinner` ✎

`*`는 필수 필드, `˅`는 인라인 편집 가능. **승인/거절 버튼은 이 캡처의 하단이 잘려 보이지 않는다** — 없다고 단정하지 않는다.

세 장이 같은 틀을 쓰고 **배너의 색과 문구만 다르다.** 즉 판정은 카드의 레이아웃을 바꾸지 않고, 사람은 항상 같은 자리에서 같은 순서로 읽는다.

#### 결정 이후의 카드, 그리고 대량 자동승인 `[화면-공식캡처]` `09-ramp-auto-approved-rollup.png`

원본: <https://assets.ramp.com/help-center/policy-agent-overview/attachments/44077947197587.png>

- 같은 카드 틀에서 배너 제목만 **`Transaction complete`**로 바뀌고, 그 아래 한 줄 `Ramp found no issues and suggested it be approved ^`가 **기본 접힘** 상태다. 근거 불릿은 펼쳐야 보인다.
  - **→ 근거는 결정 전에는 펼쳐져 있고 결정 후에는 접힌다.** 근거 표시의 비용을 시점으로 나눈 설계다.
- 화면 하단에 별도 롤업 행: **`971 transactions were automatically approved by agent`** / `3d ago · Purchases totaling $84,466.99 were in policy` + `×` + `Collapse`.
  - **→ 자동 처리된 대량 건은 개별 행으로 쌓이지 않고 "건수 + 금액 합계" 한 줄로 접힌다.** 승인 피로를 UI 밀도가 아니라 **집계 단위**로 푼 사례다.

#### 활동 피드와 정렬률 리포트 `[화면-공식캡처]` `04-ramp-activity-and-alignment.png`

원본: <https://assets.ramp.com/help-center/use-policy-agent-for-approvals/attachments/47618318132243.png>

**우측 — 건별 활동 피드.** 행위자 아바타 + 이름 + 시각 + 한 줄 서술이 시간 역순으로:

- `Ramp · Today, 4:36 AM — Approved transaction because it's in policy and no other issues were found`
- `Catalina Crunch · Today, 4:35 AM — Catalina Crunch cleared this transaction`
- `Ramp · Today, 12:24 AM — Automatically matched a receipt from Gmail Integration with this transaction`
- `Ramp · Today, 12:15 AM — Updated the memo` + 변경값 칩 `Office snacks and beverages`
- `Matthew Shafeek · Today, 12:15 AM — Spent $56.19 at Catalina Crunch`

**에이전트의 행동과 사람의 행동, 그리고 외부 시스템의 이벤트가 같은 피드에 같은 형식으로 섞인다.** 에이전트용 별도 로그 탭이 아니다. 값이 바뀐 행동은 **바뀐 값을 칩으로 함께 보여준다**(메모 변경).

**좌측 — `Ramp's policy agent` 리포트.** 부제가 *"See how closely reviewers align with AI agent policy decisions."* 표의 `Outcome` 열이 **에이전트 추천 × 사람의 실제 결정 교차표**다:

| # | Outcome | % of total | Trend |
|---|---|---|---|
| 1 | Suggested review, expense was approved | 49.24% ($3,160,347.33) | ↓0.2% |
| 2 | Suggested approval, expense was approved | 37.98% ($2,438,110.85) | ↑0.6% |
| 3 | **Suggested rejection, expense was approved** | **12.40%** ($795,683.02) | — |
| 4 | Suggested review, expense was repaid | 0.15% ($9,693.91) | ↓0.2% |
| 5 | Suggested rejection, expense was repaid | 0.15% ($9,428.02) | ↑0.4% |
| 6 | Suggested approval, expense was repaid | 0.09% ($5,504.82) | ↓0.2% |

상단 KPI 타일: `In policy spend 91.6% (Up 1.6%)`, `Repayments 91.2% of repayments requested have been repaid (Down 7.5%)`, `Policy agent 99.6% of approval suggestions accepted (Up 0.8%)`.
하단 `Department` 표: `Corporate / $308,226.35 / 112 items / ↑3.7% / "Alcohol violations and gift card purchases consistently bypass controls across multiple employees"`.

**주의**: 이 수치는 제품 문서의 예시 데이터이므로 **실제 통계로 인용하면 안 된다.** 의미가 있는 것은 **화면의 구조**다 — 제품이 "에이전트가 거절을 권했는데 사람이 승인한 비율"을 **대놓고 제품 화면에 띄운다.** 그리고 사람의 결정 축에 `rejected`가 없고 `repaid`만 있다.

**→ 이것은 #3에서 아무도 갖고 있지 않던 화면이다.** "에이전트를 감독한다"의 제품적 구현이 승인 버튼만이 아니라 **override 비율 리포트**로도 존재한다. 포트폴리오에서 "실패를 보여주기"(#3 §5.4)를 구현할 때 참고할 실물 선례다.

### 2.3 Moveworks Approvals Engine

공식 문서: <https://docs.moveworks.com/agent-studio/core-platform/approval-workflow>

#### 승인자 카드 `[화면-공식캡처]` `05-moveworks-approver-card.png`

원본: <https://files.readme.io/ddccaaa-small-Untitled_-_2023-04-30T235050.866.png> (문서의 캡션: "Approver is presented with all relevant information to make a decision")

```
Moveworks  10:22 AM
New Approval Request
RITM011989 - Github
  │ Requestor Info
  │ @Alex
  │
  │ Role Requested
  │ Back-End
  │
  │ Business Justification
  │ I want to test some changes to the front-end which require hitting a local back-end.
  │
  │ [Approve] [Deny] [Add comment] [View other approvals]
```

- 제목이 **티켓 ID + 대상 시스템**이다. 요약문이 아니다.
- 필드가 **레이블-값 블록**으로 고정되어 있다. 이 필드 구성은 요청 유형별로 설정 가능하다(문서: "the multiple choice question is customizable to describe what the approval process is for visibility to the end user"). `[문서텍스트]`
- **`Business Justification`은 요청자가 쓴 문장이다.** 에이전트의 판단·근거가 아니다.
- `View other approvals`가 카드 안에 있다 — **한 건을 보면서 자기 큐 전체로 나갈 수 있다.**

#### 거절 플로우 `[화면-공식캡처]` `06-moveworks-deny-reason.png`

원본: <https://files.readme.io/04cd24e-small-Untitled_-_2023-04-30T215017.564.png>

```
Why are you denying this request?
  │ Your company policy requires you to provide a justification.
  │ Please keep typing to add reason or type cancel to exit.

Saloni Dandavate  6:21 PM
It's too expensive. Use regular LinkedIN

movedev APP  6:21 PM
❌ You have denied the request. I will notify Shaumik Mondal as this ticket updates.
   RITM0011679: ███████
   You have 5 more approvals to review.
   [View next approval] [View all approvals]
```

#### 거절 통보 `[화면-공식캡처]` `07-moveworks-denied-notice.png`

원본: <https://files.readme.io/e54a192-small-Untitled_-_2023-04-30T214911.981.png>

> Moveworks IT 2021-4-4 12:04 AM PDT
> Hi Saloni, your request for Xactly, tracked in RITM000876, was denied by Ameet. Please contact IT for help.
> **Comment:** Xactly is not aapproved for security reasons. Use Oracle.

거절자 이름 + 사유 원문 + 다음 행동 안내("contact IT")가 한 메시지에 들어간다. (원문의 `aapproved` 오타는 제품 문서 그대로다.)

#### 결재선 진행 상태 `[화면-공식캡처]` `08-moveworks-approval-chain.png`

원본: <https://files.readme.io/30514d3-small-Untitled_-_2023-04-30T215038.643.png> (캡션: "Identify pending approvers — Auditor / Agent")

티켓 상세의 `Comments & Worknotes`가 결재 진행을 기록한다. 매 worknote가 **두 줄 고정 포맷**으로 끝난다:

```
[Worknote] Moveworks - 7:22 AM
Sent request for approval to Chelsea.
---
Approved by: None
Waiting for: Chelsea

[Worknote] Moveworks - 9:52 AM
Chelsea has approved this request. We are still waiting for an approval from Lewis
--
Approved by: Chelsea
Waiting for: Lewis

[Comment] Moveworks - 9:52 AM
Hi Alex,
Your request for Github, tracked in RITM011989, was approved by Chelsea.
We are now waiting for an approval from Lewis.

[Worknote] Moveworks - 10:22 AM
Lewis has approved this request. This request has all the neccessary approvals.
--
Approved by: Chelsea, Lewis
```

- **`Approved by:` / `Waiting for:` 두 필드가 결재선 상태의 전부다.** 화면에 나타난 결재선 모델은 이 두 집합이다.
- `[Worknote]`(내부용)와 `[Comment]`(요청자에게 보이는 것)를 구분한다 — 문서는 그 이유를 "Intermediate approval updates are provided as ticket comments. This reduces in-bot noise"로 설명한다. `[문서텍스트]`
- 설정 가능한 결재 구조 `[문서텍스트]`: **Sequential**(순차), **Parallel**(1명/N of M/전원), **Conditional**(부서·역할·사용자 속성별 승인자 분기 — 문서 예시: "Alexa's request goes to Georgia since she's in UX, but Paul's goes to Chris since he's in Marketing"), **Bring your own Approval Group**(IDAM 보안 그룹에서 승인자 로드), 그리고 이들의 조합.
- 종료 규칙 `[문서텍스트]`: "After all approvals within a group have been collected, other approvers will no longer be able to approve these records." / "If any one approver denies the request, then the entire request is denied."

**→ #14(한국 결재 문법)와의 접점.** Moveworks가 화면에서 다루는 결재 개념은 **순차·병렬(N of M)·조건 분기·집합 완료** 네 가지다. 합의·전결·후결은 여기 없다. 다만 "Parallel 중 N of M"은 합의의, "Conditional"은 전결의 **일부 구조**를 담을 수 있다 — 어디까지 담기고 어디서 깨지는지는 #14가 1차 자료로 확인해야 한다.

---

## 3. 세 화면을 겹쳐 보았을 때

### 3.1 #3의 결론 중 화면으로 **뒤집힌** 것

1. **"전부 자연어 요약 + 예/아니오"** → **부정확하다.** 확인한 세 카드 중 자연어 요약을 본문으로 쓰는 것은 없다. Agent Inbox는 툴 호출 인자 원본, Ramp와 Moveworks는 레이블 붙은 구조화 필드다. 자연어는 **판정의 근거**(Ramp) 또는 **요청자의 사유**(Moveworks) 자리에만 나타난다.
2. **"인박스는 승인 큐의 상위 집합"** → **한 축에서만 맞다.** 수정(`edit`) 축에서는 Agent Inbox가 넓지만, **거절 축에서는 승인 큐가 훨씬 넓다.** Moveworks의 `Deny`는 사유를 강제하고 요청자·티켓·감사 로그로 전파되지만, Agent Inbox의 `Ignore`는 `args: null`로 스레드를 끝낸다. "상위 집합"이라는 서술은 화면 앞에서 성립하지 않는다.
3. **"근거를 보여주는 HR 제품이 없다"** → **확인됐지만 원인이 다르다.** Ramp에서 근거 칸은 배너 안 서너 줄에 불과하다. 문제는 자리가 없는 게 아니라 **채울 재료가 없는 것**이다 — Ramp는 그 재료를 만들려고 agent-facing policy라는 별도 산출물과 Policy Editor라는 별도 제품 표면을 세웠다.

### 3.2 #3의 결론 중 화면으로 **확인된** 것

- **워크플로 캔버스는 승인자의 화면이 아니다.** Microsoft Learn의 승인 문서 스크린샷 15장이 전부 빌더 화면이고 승인자 카드는 한 장도 없다는 사실이, 이 구분을 문서 구조 수준에서 보여준다.
- **승인 피로는 실재하는 설계 압력이다.** Ramp의 대량 롤업(971건 한 줄)과 Moveworks의 큐 포인터("5 more approvals"), Agent Inbox의 페이지 크기 100까지의 선택지가 전부 같은 문제에 대한 서로 다른 대응이다.
- **"채팅창이 아니다"는 차별점이 아니다.** 셋 중 둘(Ramp, Moveworks)의 승인 화면은 애초에 채팅창이 아니고, Moveworks는 채팅창 **안에** 구조화 카드를 띄운다. 채팅이냐 아니냐가 아니라 카드 안에 무엇이 있느냐가 갈린다.

### 3.3 이 조사가 #8(상호작용 모델 프로토타입)에 넘기는 것

화면으로 확인된 **구체적 설계 결정 목록**. 프로토타입은 이 칸들을 채우는 일이다.

| 결정해야 할 칸 | 확인된 선례 (Agent Inbox / Ramp / Moveworks) | 인사·총무에서의 질문 |
|---|---|---|
| 카드 제목에 무엇을 쓰는가 | 툴 이름 / 금액+상대방 / 티켓ID+시스템 | 인사·총무 사건의 "금액+상대방"에 해당하는 한 줄은 무엇인가 |
| 카드 본문의 형태 | raw args / 구조화 필드 / 구조화 필드 | 승인 단위를 어떤 필드 집합으로 정의할 것인가(#3 빈틈 ①) |
| 결정 행동의 가짓수와 이름 | 5 / (화면 미확인) / 4 | 한국 결재 어휘(승인·반려·합의·전결)와 어떻게 맞출 것인가(#14) |
| 다건 배열 기준 | 실행 상태 탭 / 판정별 섹션 + 롤업 / 큐 포인터 | **기한으로 정렬하는 선례가 없다** — 법정 기한이 있는 도메인에서 이건 빈칸인가 기회인가 |
| 근거 칸의 위치와 분량 | 없음(State/Studio로 위임) / 판정 배너 안 서너 줄 + 결정 후 접힘 / 없음 | 근거로 인용할 "정책 원문"을 무엇으로 둘 것인가 |
| 거절의 후속 상태 | 스레드 END(사유 없음) / repayment / 요청 전체 거절 + 사유 전파 | 휴가·발령·경조사 반려의 후속 상태를 각각 무엇으로 정의할 것인가 |
| 에이전트 판단을 평가하는 축 | edit/accept 구분 / 👍👎 + override 비율 리포트 / 없음 | 감독의 품질을 무엇으로 측정해 화면에 띄울 것인가 |

---

## 4. 이 조사의 한계

- **라이브로 조작한 제품은 하나도 없다.** Agent Inbox의 빈 목록·설정 모달만 라이브였고, 실제 승인 카드를 클릭해 본 것은 없다. Ramp·Moveworks의 근거는 전부 제품사가 **직접 고른** 공식 스크린샷이므로, 제품이 가장 잘 보이는 상태만 담겨 있을 수 있다.
- **캡처가 잘린 부분은 단정하지 않았다.** 특히 Ramp 승인 카드의 승인/거절 버튼은 프레임 밖이라 확인하지 못했다.
- **Ramp 리포트의 수치는 예시 데이터다.** 구조만 인용 가능하고 통계로는 인용 불가.
- **Moveworks 캡처의 원본 파일명이 2023-04-30**이다. 현재 제품 화면이 이와 같다는 보장은 없다. 다만 문서가 지금도 현행으로 게시하고 있다.
- **국내 제품 화면을 하나도 보지 않았다.** flex·더존·그룹웨어의 결재 화면은 이 조사 밖이고, 한국 결재 문법은 #14의 몫이다.
- **인사·총무 도메인의 AI 승인 화면은 결국 못 찾았다.** 확보한 셋 중 둘(Ramp=경비, Moveworks=IT 접근권한)은 인접 도메인이고, 하나(Agent Inbox)는 도메인 무관 범용이다. **"인사·총무 사건의 승인 카드"를 보여주는 실물 화면은 이번 조사에서 발견되지 않았다.** 이것은 조사의 실패일 수도, 빈틈의 증거일 수도 있다 — 단정하지 않는다.
