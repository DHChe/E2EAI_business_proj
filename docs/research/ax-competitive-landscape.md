# 인사·총무 AX 경쟁 지형과 인터페이스 관행

> 조사 대상 이슈: [#3](https://github.com/DHChe/E2EAI_business_proj/issues/3) · 부모 map: #1
> 조사 시점: 2026-09-20
> 이 문서는 PRD의 차별점 주장(#7)과 상호작용 모델 프로토타입(#8)의 재료다.

## 이 문서를 읽는 법

- 모든 주장에 출처 URL을 붙였다. `[1차]`는 제품 공식 문서·공식 블로그·릴리스 노트·논문 원문, `[2차]`는 언론·애널리스트·커뮤니티 자료다.
- 확인하지 못한 것은 **확인 불가**로 적었다. 있을 법하지만 근거를 못 찾은 기능은 쓰지 않았다.
- 마지막 두 절(「이 프로젝트가 비집고 들어갈 빈틈」, 「근거가 약한 부분」)이 결론이다.

---

## 0. 배경: "자동화한다"는 주장과 실제의 간극

시장 전체 수준에서 먼저 눈금을 맞춰 둔다. 개별 제품의 마케팅 문구를 그대로 믿으면 경쟁 지형을 잘못 읽는다.

- Gartner는 2027년 말까지 **agentic AI 프로젝트의 40% 이상이 취소될 것**으로 예측하며, 그 이유로 비용 상승·불분명한 사업 가치·미흡한 리스크 통제를 든다. 같은 자료에서 Gartner는 **"agent washing"** — 기존 AI 어시스턴트·RPA·챗봇을 실질적 에이전트 역량 없이 리브랜딩하는 행위 — 를 지목하고, 수천 개 agentic AI 벤더 중 실제는 **약 130개** 수준으로 추정한다. [2차/애널리스트] <https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027>
  - *주의*: 이 URL은 직접 본문 조회가 차단(HTTP 403)되어, 검색 결과에 인용된 발췌문으로 확인했다. 수치 자체는 널리 인용되나 본문 전문은 직접 확인하지 못했다.

이 배경 때문에 아래 제품 조사에서는 **"무엇을 자동화한다고 말하는가"와 "문서상 사람이 무엇을 하도록 되어 있는가"를 분리해서** 기록했다. 후자가 인터페이스 설계의 실제 입력값이다.

---

## 1. 국내 인사·총무 제품

### 1.1 flex (flex.team) — 규칙 기반 전자결재 + "AI 전환" 포지셔닝

- **주장**: 홈페이지는 "조직을 제대로 아는 AI", "flex가 곧 AI 전환입니다", "AI가 조직과 구성원의 관계와 맥락을 이해해야 일하는 방식이 바뀝니다"로 포지셔닝한다. AI가 "사용자가 해야 할 일을 먼저 찾아 우선순위와 함께 알려주고, 리더에게는 하위 조직의 몰입도 저하나 목표 달성 미비 등 문제 시그널까지 선제적으로 포착해 보고"한다고 말한다. [1차] <https://flex.team/>
- **실제로 문서화된 자동화**(워크플로우 제품 페이지): 전자결재 문서에 "flex에 등록된 인사 정보만 있으면 설정만 하면 자동으로 구성원 정보가 입력돼요", "필요에 따라 단계별로 자동 승인을 설정할 수 있어요", "담당자가 바뀌었나요? 여러 문서 양식의 승인 정책을 한 번에 변경할 수 있어요". [1차] <https://flex.team/about/features/workflow>
- **인터페이스**: 채팅창이 아니다. ① **알림함 + "할 일"** — "알림으로 문서 상태를 손쉽게 확인하고, 내 승인이 필요하면 할 일로 알려줘요" ② **승인/참조 라인 설정 화면** — "참조와 승인을 단계별로 자유롭게 설정할 수 있고, 승인/참조 대상을 개인이 아닌 팀으로도 설정할 수 있어요" ③ **활동기록** — 작성·승인·결재선 변경·댓글을 시간순으로 확인. [1차] <https://flex.team/about/features/workflow>
- **사람에게 남는 일**: 승인 라인의 각 단계. 공식 블로그는 "사용자가 직접 Rule 기반의 업무 프로세스를 설계할 수 있으며, 필요한 지점에 AI의 판단을 통합"한다고 서술한다. [1차] <https://flex.team/blog/2025/05/28/hr_ai/>
- **한계**: 2025년 5~6월 블로그의 온보딩 자동 조정("입사자의 역할과 부서에 따라 필요한 교육과 액세스 권한, 멘토 매칭 등이 자동으로 조정")과 "AI 동료" 서술은 **로드맵 성격**이며, 상용 기능(전자결재 자동입력/자동승인)과 섞여 있다. AI가 개입하는 구체적 UI·승인 메커니즘은 문서화되어 있지 않다(확인 불가). [1차] <https://flex.team/blog/2025/06/23/flexible_4/>

### 1.2 시프티 (Shiftee) — AI 없이도 승인 워크플로는 완성되어 있다

- **중요 발견**: 워크플로우 공식 페이지 전문에 **"AI"라는 단어가 한 번도 등장하지 않는다.** 근태·스케줄 자동화는 전부 규칙 기반으로 서술된다. [1차] <https://shiftee.io/ko/workflow>
- **자동화**: "시차출퇴근, 유연근무제 등 정해진 시간 범위 내에서… 매번 관리자의 승인을 필요로 하지 않을 수 있습니다"(선택적 자동승인), "요청의 종류/조직/직무 별로 각기 다른 승인라인을 요구할 경우, 승인규칙을 커스텀하여 적용"(병렬·순차 승인), 반복 근무 패턴용 스케줄 패턴 생성. [1차] <https://shiftee.io/ko/workflow>, <https://shiftee.io/ko/scheduler>
- **인터페이스**: 웹·모바일의 요청/승인 버튼과 댓글, "진행 현황을 확인하고 처리하는 모든 과정이 하나의 흐름으로 매끄럽게" 보이는 요청 관리 화면.
- **왜 중요한가**: 이 프로젝트가 "승인 큐"를 만든다면, 그건 새로운 발명이 아니라 **국내 근태 SaaS가 이미 규칙 기반으로 갖고 있는 것**이다. 차별점은 큐의 존재가 아니라 큐에 올라오는 항목의 성격(누가 무엇을 근거로 올렸는가)에 있어야 한다.
- **한계**: 제3자 리뷰(MWM 등)의 "AI 기반 자동화" 표현은 위치/WiFi 인증 출퇴근 기록을 가리키며, 이는 규칙 기반이다. 생성형 AI 기능의 존재 자체가 확인 불가.

### 1.3 더존비즈온 ONE AI / WEHAGO — "AI 초안 → 사람 검토·승인"을 명시한 유일한 국내 사례

- **자동화 주장**:
  - 인사: "입·퇴사자별로 신고 기한 안내와 신고서를 자동으로 작성"(4대보험), 육아휴직·청년고용 등 관련 법률 및 지원제도 자동 확인.
  - 전자결재: "이전 결재문서를 파악하여 품의서, 기안서 등 문서 초안을 빠르게 작성", "본문 내용과 첨부파일을 분석하여 검토가 필요한 내용을 알려줌".
  [1차] <https://www.douzone.com/product/oneai.jsp>, <https://www.wehago.com/landing/ko/oneai/>
- **인터페이스**: **자연어 요청 + 초안 생성**. "이번 달 입·퇴사자 목록을 알려주고, 4대 보험 신고서 작성해 줘", "프로모션 계획안 보고서를 참고해서 이벤트 상품 구매 품의서를 작성해 줘" 같은 요청에 AI가 초안을 만들고 **사람이 검토·승인**하는 협력 형태로 문서에 명시되어 있다.
- **사람에게 남는 일**: 초안 검토와 결재. 즉 AI는 **결재 라인의 앞단(기안)에 붙고, 결재 라인 자체는 사람이 그대로 돈다.**
- **한계**: ERP(회계·인사·물류) 데이터 분석 기능은 언급되나 구체 절차는 "제품문의/세미나 확인 필요"로 미공개(확인 불가). [2차] <https://www.etnews.com/20240308000166>

### 1.4 뉴플로이 (Newploy) — RPA 프레이밍

- **자동화**: 급여대장 생성, 퇴직금 자동 계산, 자동 급여 이체, 원천세·4대보험 신고·납부, 출퇴근·연차 관리, 전자근로계약서, 퇴사자 급여 처리. RPA를 적용해 "급여계산, 급여이체, 원천세/4대보험 신고와 납부까지 모든 급여 업무를 클릭 몇 번으로 해결"한다고 주장. [1차] <https://www.newploy.net/> [2차] <https://www.hankyung.com/article/202306013044i>
- **인터페이스**: 매니저 앱(2023-06 정식 출시). 구체적 승인 UI·사람 개입 지점은 확인 불가.
- **관찰**: 프레이밍이 "AI"가 아니라 **"RPA·자동화"**다. 생성형/판단형 AI 요소의 존재는 확인 불가. 인사·총무의 가장 반복적인 영역(급여·신고)은 이미 결정론적 자동화로 상당 부분 먹혔다는 뜻이기도 하다.

### 1.5 그룹웨어의 AI — 커뮤니케이션 생산성에 머문다

**네이버웍스 (WORKS AI)** [1차] <https://naver.worksmobile.com/products/naver-works/works-ai/>
- 읽지 않은 메시지 요약(30건 이상일 때), 이메일 초안 작성, 클로바노트 기반 AI 회의록, 클로바 OCR 기반 명함·영수증·문서 텍스트 자동추출, "AI 스튜디오"로 사내 AI 어시스턴트 구성.
- 명시적 제약: **1:1 메시지방과 Bot 메시지방은 요약 불가**. [1차] <https://help.worksmobile.com/ko/use-guides/message/check-message/summary-unread-message/>
- 인터페이스: 채팅 UI 내 요약 버튼, 드라이브 문서 내 AI 요약/번역 버튼.
- **인사(근태·급여) 특화 AI 자동화는 공식 자료에서 확인 불가.** 제품 성격이 커뮤니케이션·문서 생산성이다.

**카카오워크 (캐스퍼)** [1차] <https://blog.kakaowork.com/165>, <https://blog.kakaowork.com/135>
- 슬래시 명령어로 동료·조직 정보 조회(프로필봇), 칭찬 발송·월간 랭킹(칭찬봇), 업로드 문서 기반 질의응답(지식검색), 맞춤법·말투 교정, 읽지 않은 대화·멘션 요약, 실시간 번역, 이미지 내 텍스트 검색.
- **인터페이스는 명시적 호출형(pull)이다**: `/캐스퍼 @라이언 소속이 어디야?`, `/캐스퍼 @어피치 칭찬!` 처럼 사용자가 멘션과 키워드를 직접 입력해야 작동한다. 자동 트리거가 아니다.
- "업무를 직접 수행하는 실행형 AI 에이전트"는 '카카오워크 2.0'의 **예고 단계**이며 미출시다. [2차] <https://m.news.nate.com/view/20260714n22151>

**두레이 (NHN Dooray!)** [1차] <https://inside.nhn.com/service/236>, <https://inside.nhn.com/service/235>
- 2024-10 두레이AI 공개. 마이 에이전트("수많은 메일 중 우선순위가 높은 건을 선별하거나, 흩어져 있는 업무를 모아 효율적인 스케줄을 제안"), 프로젝트 에이전트("오늘 프로젝트 진행 현황 어때?", "지연된 업무 리스트 뽑아줘"), **익스텐션 에이전트 — "휴가 신청, 연장근로 등록, 사내 임직원 검색 등의 작업을 즉시 처리"**.
- 인터페이스: 메신저 대화방에 AI 에이전트를 초대해 사람과 "동일한 지위"로 토론하는 협업 방식.
- **핵심 공백**: "휴가 신청, 연장근로 등록"을 "즉시 처리"한다고 하면서, **그것이 조직의 결재 라인과 어떻게 맞물리는지 공식 자료에 설명이 없다.** 사람의 검토·승인 지점이 명시되어 있지 않다(확인 불가). 인사·총무 업무의 핵심이 "누가 승인했는가"인데 그 부분이 문서화되지 않았다는 점 자체가 이 조사의 중요한 발견이다.

**하이웍스 (가비아)** [1차] <https://library.gabia.com/contents/groupware/14376/> [2차] <https://zdnet.co.kr/view/?no=20260513102249>
- AI채팅이 메일·전자결재·게시판·일정·드라이브·업무관리와 연동되어 "필요한 데이터를 한 번에 확인"하고 업무 요청을 처리. 업무 지시 입력 시 Word·PPT·Excel 자동 생성. GPT·Claude·Gemini 등 복수 모델 연동.
- 인터페이스: **채팅**.

### 1.6 대기업 SI의 HR 에이전트

- **삼성SDS Brity RPA**: 반복업무 RPA에 챗봇(Brity Assistant), 딥러닝 이미지인식(AICR), 텍스트분석을 붙여 "판단·심사·평가 등 한 차원 높은 복합 업무 영역까지 자동화"한다고 주장. '헤드리스 봇'(다중 프로세스 동시 실행), '스텝 레코더'(PC 화면 녹화로 프로세스 자동 생성). 인사·재무 적용을 언급하나 구체 프로세스는 미상세(확인 불가). [1차] <https://www.samsungsds.com/global/ko/solutions/off/brity/brity.html>
- **LG CNS AgenticWorks**: HR 특화 에이전틱 AI — 대규모 채용에서 수만 건의 자기소개서·인적성 데이터와 기존 인사 문서를 분석해 적합 인재 추천, 지원자별 면접질문 자동 생성. "업무 생산성 약 26% 향상"은 **자체 발표 수치**이며 제3자 검증 자료를 찾지 못했다. ERP·CRM 연동은 MCP·A2A 프로토콜 기반의 범용 플랫폼이고 HR은 그 적용 사례다. [1차] <https://www.lg.co.kr/media/release/29289>
- **원티드 HR**: LLM 기반 'AI 채용 에이전트'(2025-10). 자연어로 조건을 넣으면("3년 이상 리액트 경험이 있는 프론트엔드 개발자 중 커뮤니케이션 능력이 뛰어난 인재") AI가 후보자를 제시하고, 대화형으로 조건 수정·이유 확인이 가능하다. 역할 분담을 명시한다: **"AI가 탐색과 초기 매칭을 담당하는 동안 담당자는 인터뷰, 인재 설득 등 핵심 의사결정에 집중."** [1차] <https://blog.wantedlab.com/hr/trend/wanted-agent-matching> [2차] <https://www.etnews.com/20251021000282>

### 1.7 국내 지형 요약

| 관찰 | 근거 |
|---|---|
| 인사·총무 SaaS의 승인 인터페이스는 **이미 존재하지만 규칙 기반이다** (결재선·자동승인 규칙) | flex 워크플로우, 시프티 워크플로우 |
| AI는 주로 **결재 라인의 앞단(기안·초안 생성)**에 붙는다. 결재 라인 자체는 사람이 돈다 | 더존 ONE AI |
| 그룹웨어 AI는 **커뮤니케이션 생산성**(요약·번역·초안)에 머문다 | 네이버웍스, 카카오워크, 하이웍스 |
| "업무를 즉시 처리한다"는 주장이 나오면 **승인 라인과의 관계가 문서화되지 않는다** | 두레이 익스텐션 에이전트 |
| 가장 반복적인 영역(급여·4대보험 신고)은 이미 **결정론적 RPA**가 점유했다 | 뉴플로이 |

## 2. 해외 인사·총무 플랫폼의 AI 에이전트

국내와 가장 크게 갈리는 지점은 **"에이전트 자체를 관리하는 별도 화면"의 존재 여부**다. 아래에서 반복적으로 확인된다.

### 2.1 ServiceNow — 승인 게이트가 가장 구체적으로 문서화된 사례

- **자동화**: Tier-1 HR 문의 self-service 처리, 케이스 triage·라우팅, 지식베이스 응답 합성, 온보딩 플랜 생성, 오프보딩 인수인계 문서 생성, 면접 일정 최적화. [1차] <https://www.servicenow.com/community/hrsd-blog/agentic-ai-capabilities-for-hr/ba-p/3288346>
- **인터페이스 — 명시적 게이트**:
  - 온보딩: "the **Reviewer Agent presents the plan to the manager for review and customization**. Once approved, the new hire gains access." 즉 **승인 전에는 접근 권한이 부여되지 않는다.**
  - 중요 케이스: 담당자가 "review, adjust, and approve the plan, which is then saved to the **worknotes for audit purposes**"
  - 등급 분류: "Critical cases are flagged VIP or complex requests for Tier 1 agent support" — 중요도에 따라 사람에게 갈지 AI가 답할지 갈린다.
  - 오프보딩: 매니저가 "review the handoff document"하고 후임자를 지정.
  [1차] <https://www.servicenow.com/community/hrsd-articles/resolve-hr-case-nbsp-using-nbsp-agentic-nbsp-ai-nbsp-overview/ta-p/3450076>
- **전담 화면 3종**: **AI Agent Studio**(에이전트 구성·테스트), **Manager Hub**(업무 화면 내 승인), **AI Control Tower**("a centralized command center to govern, manage, secure, and realize value from any AI agent, model, and workflow"). [1차/뉴스룸] <https://newsroom.servicenow.com/press-releases/details/2025/ServiceNow-Launches-AI-Control-Tower-a-Centralized-Command-Center-to-Govern-Manage-Secure-and-Realize-Value-From-Any-AI-Agent-Model-and-Workflow/default.aspx>
- **한계**: AI Control Tower의 화면 단위 구성(예: "Risk & Compliance tab")은 공식 docs가 403으로 막혀 **2차 블로그 인용에 의존**한다. 확인 불가로 표기.

### 2.2 Salesforce Agentforce for HR Service — 에스컬레이션 트리거가 가장 구체적

- **자동화**: HR 질의 응답, 휴가 신청 관리, 개인정보·직접입금 정보 업데이트, HR 케이스 추적. Slack과 Employee Portal에서 티켓 없이 처리. [1차] <https://www.salesforce.com/news/stories/agentforce-hr-service-announcement/>
- **인터페이스**:
  - **HR Service Console** — 담당자 전용 워크스페이스에 Agentforce가 임베드되고, "Agentforce **generates recommended replies and summaries** in real time"으로 **초안을 사람 옆에 띄운다.**
  - 정책 위반 요청 시: "summarize the policy for the HR rep, **draft a response** to the employee" — 즉 AI가 보내지 않고 사람에게 초안을 준다.
  - 명시적 에스컬레이션: "If an inquiry is **highly complex or highly personal**, Agentforce will seamlessly transfer the conversation to a human HR representative" — **bereavement(사별), harassment(괴롭힘)** 같은 민감 사안이 예시로 명시된다.
  - "submit an **automated approval request to the manager** once compliance is reached"
  - **Testing Center** — "simulate conversations at scale… check how **guardrails are being respected**"로 배포 전 대규모 시뮬레이션.
  [1차] <https://www.salesforce.com/blog/agent-handoff/>, <https://trailhead.salesforce.com/content/learn/modules/agentforce-agent-planning/define-the-agent-guardrails>
- **Guardrails 공식 4요소**: data access permissions / action authorization / scope boundaries / escalation protocols. [1차] <https://www.salesforce.com/welcome-to-the-agentic-enterprise/ai-guardrails/>
- **한계**: confidence threshold 구체 수치 미공개. Guardrails·Testing Center 문서는 플랫폼 전반용이고 HR 전용 튜닝 사례는 확인 불가.

### 2.3 Workday — "Agent System of Record"라는 카테고리 주장

- **자동화**: Self-Service Agent, Performance Agent, Case Agent, Employee Sentiment Agent, Job Architecture Agent, Document Intelligence for Contingent Labor Agent 등. [1차] <https://newsroom.workday.com/2025-09-16-Workday-Illuminate-TM-Expands-with-New-AI-Agents-for-HR,-Finance,-and-Industry>
- **인터페이스**: 챗봇이 아니라 **거버넌스 레이어**를 전면에 내세운다. **Agent System of Record**(에이전트+사람의 blended workforce 허브), **Agent Analytics Hub**, **Agent Gateway**(에이전트가 Workday 데이터에 접근할 때 거치는 secure hub, identity permissioning 적용), **Agent Lifecycle Management**(register / configure / activate / deactivate). [1차] <https://www.workday.com/en-us/artificial-intelligence/agent-system-of-record.html>
- **한계**: 거버넌스 용어는 강하나 **승인 큐·확인 버튼 같은 화면 단위 워크플로는 공식 페이지에 서술되지 않는다.** 마케팅 카피 수준에 머문다.

### 2.4 Rippling — "승인" 언어가 가장 명확한 HR SaaS

- **인터페이스**(원문 인용):
  - "Before it takes action, **it gets your approval**, so your critical tasks never go off course."
  - "Any action Rippling AI proposes **requires explicit human confirmation** before execution."
  - 급여: AI가 "**stages the payroll run for your approval**" — 실행이 아니라 **스테이징**이다.
  - 조직 개편: 변경사항을 "a single proposal so you can review and confirm"으로 묶어 제시.
  - 출처 검증: "numbers and names appear as **clickable links to real records**, so you can quickly see where answers come from"
  - 권한: "Rippling AI runs on **your existing permissions**, so employees never see data they shouldn't"
  [1차] <https://www.rippling.com/platform/ai>, <https://www.rippling.com/blog/introducing-rippling-ai>
- **관찰**: Rippling은 별도 에이전트 콘솔을 만들지 않고 **기존 승인 워크플로에 AI의 제안을 밀어넣는다**. 이것이 이 조사에서 가장 중요한 분기점 중 하나다(§5 참조).
- **한계**: "70% 관리업무 절감", "90% 조달 업무 절감" 같은 수치는 전부 벤더 자체 주장이며 제3자 검증 없음.

### 2.5 나머지 — "human oversight"는 말하지만 메커니즘은 없다

| 벤더 | 확인된 것 | 확인 안 된 것 |
|---|---|---|
| **ADP Assist** | "agents that think, plan and take action **with human oversight**", "keeping people **in the loop wherever judgment matters**", 급여 변동은 "suggest and facilitate remediations under human oversight" [1차] <https://www.adp.com/what-we-offer/ai-solutions/ai-agents.aspx> | 대시보드·승인 큐·에스컬레이션 임계값 등 **화면 단위 메커니즘 전무** |
| **Deel AI Workforce** | "AI agents are deployed by your team when you want answers or help resolving something"(온디맨드 호출형), "**your team stays in control of decisions and approvals**" [1차] <https://www.deel.com/solutions/ai-workforce/> | 승인 큐·에스컬레이션 트리거·신뢰도 임계값 |
| **SAP SuccessFactors Joule** | 공식 커뮤니티 블로그 제목 자체가 *"Human-in-the-Loop SAP Agents: Approval, Escalation, and Audit"*로 존재 | **본문 403으로 확인 실패.** 인용 가능한 것은 검색 스니펫뿐 |
| **Oracle Fusion HCM** | "AI Agent Studio for Fusion Applications", "keeping people in control of business-critical decisions" [1차] <https://www.oracle.com/news/announcement/oracle-adds-new-fusion-agentic-applications-and-ai-agents-to-help-improve-talent-management-2026-08-11/> | 승인이 어떻게 트리거·라우팅되는지, 감사 추적이 무엇인지 **전혀 미공개** |
| **BambooHR Bamboo AI** | "easy-to-use **AI-powered chat interface**"(Ask BambooHR), 서베이 자유응답 토픽 요약 [1차] <https://www.bamboohr.com/about-bamboohr/press-release/bamboohr-launches-bamboo-ai> | 승인·에스컬레이션·가드레일 서술 **없음**. 현재 공개 정보 기준 챗봇 수준 |
| **Microsoft Employee Self-Service Agent** | HR starter가 "**enforces boundaries by escalating complex or sensitive requests (such as legal or personnel decisions) to HR specialists**", **Handoff template**, 모든 상호작용 "logged for auditability", **"Official Answer"** 배지로 권위 있는 출처 기반 답변임을 표시 [1차] <https://learn.microsoft.com/en-us/microsoft-365/copilot/employee-self-service/overview> | — |

**Microsoft의 문서화된 실제 제약(중요)**: 모바일 앱에서는 **"Agent Handoff to another agent or live agent isn't supported"** — 즉 사람에게 넘기는 기능이 웹에서만 동작한다. multi-agent orchestration도 모바일에서 "limited functionality"로 명시된다. 벤더가 스스로 적어 둔 몇 안 되는 구체적 한계다. [1차] <https://learn.microsoft.com/en-us/microsoft-365/copilot/employee-self-service/overview>

### 2.6 주류 HR SaaS 요약

| 성숙도 | 벤더 | 전담 화면 |
|---|---|---|
| 승인·에스컬레이션이 화면 수준까지 문서화됨 | ServiceNow, Salesforce | Agent Studio / Control Tower / Manager Hub, HR Service Console / Agent Builder / Testing Center |
| 거버넌스 콘솔은 있으나 현업 승인 화면은 불명 | Workday, Microsoft | Agent System of Record / Agent Gateway, Copilot Studio / Agent 365 |
| 전용 화면 없이 **기존 승인 워크플로에 편입** | Rippling | — |
| "human oversight" 철학만 반복, 메커니즘 미공개 | ADP, Deel, SAP, Oracle | — |
| 사실상 챗봇 | BambooHR | — |

---

### 2.7 AI-native 직원지원 에이전트 — 두 갈래의 승인 철학

기존 HR SaaS가 아니라 **직원 지원(employee support)을 처음부터 에이전트로 만든 제품들**이 있다. 여기서 이 조사에서 가장 중요한 구조적 분기가 드러난다.

#### (A) 미러링형 — 기존 승인 체계를 건드리지 않는다

**Moveworks** (2025년 ServiceNow에 인수)
- Slack·Teams·Webex·Google Chat·웹포털에 상주하며 IT/HR/재무 요청을 자연어로 받아 다단계 워크플로를 실행한다. 100개 이상의 엔터프라이즈 시스템(Workday, ServiceNow, Salesforce 등)과 연동. [1차] <https://www.moveworks.com/us/en/platform/integrations/slack>
- 승인은 **"Approvals Queue"** 와 카드형 UI로 처리한다 — "Users can approve or reject with **one-click buttons or natural language responses**." 코멘트를 강제하는 **"Deny with Comment"** 옵션도 있다. [1차] <https://www.moveworks.com/us/en/platform/approval-workflow>
- **핵심 설계 원칙 — "Approval Mirroring"**: **"Moveworks makes sure to respect your approval workflows by only integrating with your approval records."** 조직의 비즈니스 로직을 재현하지 않고 **"just the last mile, the approval record, and make it happen faster"** — 이메일 기반 승인을 채팅 액션으로 바꿔 며칠 걸리던 것을 몇 분으로 줄인다. [1차] <https://docs.moveworks.com/service-management/approval-mirroring>
- 승인 UI 구성요소가 세 가지로 문서화되어 있는데, 세 번째가 특히 눈여겨볼 만하다:
  1. **Action Buttons** — 한 번 클릭으로 승인/거부, 또는 코멘트를 **필수로 받은 뒤** 적용하는 버튼
  2. **Link Buttons** — system of record의 원본 승인 화면으로 보낸다(위임하거나 추가 맥락이 필요할 때)
  3. **Approval Queue** — 연동 시스템에서 감지한 승인 알림 데이터를 저장해, 사용자가 **대기 중인 승인을 AI 어시스턴트에게 물어 꺼내볼 수 있게** 한다
- 즉 채팅이 승인을 **대체**하는 것이 아니라, 승인 레코드로 가는 **가장 빠른 입구**로 쓰인다.

**Rippling**도 같은 계열이다(§2.4) — 별도 에이전트 콘솔 없이 기존 승인 워크플로에 AI의 제안을 밀어넣는다.

#### (B) 별도 인박스형 — 자체 승인 레이어를 얹는다

**Leena AI** ("Harrison")
- 휴가, 급여·보상, 복리후생, 청구·환급, 인사기록 변경, 전보·승진·퇴사, 근무형태 변경, 채용요청서, L&D 등록까지 HR 전 생애주기를 다룬다고 주장. [1차] <https://leena.ai/function/hr>
- 인터페이스: Slack/Teams/웹 챗 + **"pending inbox tasks"** — 관리자가 "approve, reject, or send…back" 할 수 있다. 프로세스는 **AOP(Agent Operating Protocol)** 단위로 구성되며 "Colleagues can **pause for approval before resuming with full context**."
- 벤더가 스스로 명시한 가드레일: **"No irreversible action without a check"**, **"No escalation without a manager."** 뒤집어 읽으면, 되돌릴 수 없는 액션과 에스컬레이션에는 반드시 사람이 붙는다는 것을 벤더도 인정한 것이다.

**나머지**: Espressive Barista(IT/HR/재무/시설을 "single front door"로, 2025-09 Resolve에 인수) [1차] <https://www.espressive.com/press/espressive-barista-is-the-first-ai-based-employee-self-service-solution-to-automate-processes-while-maintaining-compliance>, Atomicwork("AI service desk in Slack, Teams, email, or Claude") [1차] <https://www.atomicwork.com/solutions/ai-service-desk>, Aisera(부서별 "Agent Library" + 시스템 이벤트 기반 사전 트리거 "Event Studio") [1차] <https://content.aisera.com/one-pagers/aisera-agentic-ai-for-hr>. 성과 지표(84% 자동해결률 등)는 전부 벤더 자체 발표이며 제3자 검증이 없다.

**Paradox (Olivia)** (2025년 Workday 인수): 후보자와 **SMS·WhatsApp·WeChat·Messenger·웹챗**으로 직접 대화한다. HR팀 UI가 아니라 **지원자 대면 챗봇**이고, HR 담당자는 확정된 스케줄만 확인한다. 인터페이스의 주인공이 직원이 아니라 외부인이라는 점에서 이 프로젝트와 성격이 다르다. [1차] <https://www.paradox.ai/products/conversational-scheduling>

---

### 2.8 인접 도메인: 경비·지출 에이전트가 가장 앞서 있다

인사·총무에서 "AI가 판단하고 사람이 승인한다"를 **가장 구체적으로 구현한 곳은 HR 제품이 아니라 경비 관리 제품**이다.

**Ramp — Policy Agent** [1차] <https://ramp.com/blog/ai-agents-finance> (설정 경로는 <https://support.ramp.com/policy-page-ai-agent>)
- "Policy Agent **reads your expense policy, evaluates every card transaction and reimbursement**, and recommends **approval, rejection, or escalation**."
- **가장 중요한 설계 ① — 점진적 자율성**: **"It starts in review-only mode by default, so you can build trust before enabling auto-approval."** 처음에는 전건을 사람이 검토하고, 신뢰가 쌓인 뒤에 자동승인을 켠다. **자율성 수준 자체를 제품의 설정 가능한 축으로 만든 드문 사례다.**
- **가장 중요한 설계 ② — 근거의 출처를 못 박는다**: "It handles the gray areas in your policy language and **cites the exact policy text behind each recommendation, so reviewers can audit its reasoning.**" 승인자가 보는 것은 예/아니오도, AI가 지어낸 요약도 아니라 **어느 정책 문장에 근거했는가**다.
- *주의*: support.ramp.com의 설정 문서에는 위 문구가 없다(설정 경로 안내만 있음). 인용은 공식 블로그를 근거로 한다.

**Navan — Audit Engine** [1차] <https://navan.com/blog/audit-engine>
- 카드 거래와 영수증을 자동 매칭해 **경비보고서라는 산출물 자체를 없앤다.** 45개 이상의 감사 체크(허위 영수증 탐지, 팁 과다, FCPA 스크리닝)를 거래 시점에 실시간 적용한다.
- 3단계 분류(승인 / 플래그 / 거부)와 관리자용 실시간 대시보드. "your people only spend their time on **decisions that actually require judgment**."

**Expensify / Brex**: 영수증-거래 자동 매칭, 정책별 자동 분류, 저위험 건 자동승인 + 예외 에스컬레이션. [1차] <https://use.expensify.com/ai-expense-management>, <https://www.brex.com/platform/intelligent-finance>

**왜 경비가 앞섰는가**(이 조사의 해석): 지출은 ① 구조화된 데이터(금액·가맹점·날짜)가 이미 있고 ② 정책이 명문화되어 있으며 ③ **금액이라는 단일 축으로 위험도를 정렬할 수 있다.** 인사 업무는 이 세 조건이 모두 약하다 — 이것이 §5의 빈틈 논의로 이어진다.

---

### 2.9 한국 전자결재 문화와 AI 승인 인터페이스

인사·총무의 인터페이스를 논할 때 한국에서는 **결재선**을 피할 수 없다. 표준 어휘는 그룹웨어 공식 도움말에 정의되어 있다. [1차] <https://helpdesk.daouoffice.co.kr/hc/ko/articles/45265901184281>

> **출처 주의**: 아래 정의표는 조사 중 다우오피스 도움말에서 수집했으나, **최종 확인 시점에 해당 URL이 HTTP 403으로 재조회되지 않았다.** 용어 자체는 국내 그룹웨어 업계의 표준 어휘이고 하이웍스 공식 페이지에서도 "필요한 항목과 **결재선을 지정**해 우리 회사에 맞는 양식을 직접 만들어 보세요"라는 결재선 개념을 확인했으나([1차] <https://biz-solution.hiworks.com/product/function/groupware/approval>), **정의문 자체의 축자적 재확인은 못 했다.** §5.3에서 이 표를 인용할 때 이 점을 감안할 것.

| 용어 | 정의 |
|---|---|
| 결재 | 최종결재자 승인으로 프로세스 완료 |
| 전결 | 최종결재자 이전 결재자가 대신 승인 완료 |
| 후결 | 대결자가 처리한 문서를 원 결재자가 사후 열람 |
| 합의 | 결재선에서 결재/합의 중 선택 가능한 병행 승인 |
| 확인 | 결재선에 나타나지 않고 이력만 남는 열람성 승인 |

**조사 결과 — 한국 제품은 대체로 "미러링형"이다.**

1. **이카운트**: "ERP 전표를 승인 기안과 연결" — 승인자가 결재 화면에서 전표 상세를 바로 확인한다. e-approval 모듈 자체에 AI 자동판단이 있다는 근거는 확인 불가. [1차] <https://www.ecount.com/us/ecount/product/groupware_e-approval>
2. **영림원 K-System Ace I&I**: "ERP에서 작성한 구매 품의서가 자동으로 그룹웨어 전자결재와 연동되며, 결재 상태는 실시간으로 ERP와 동기화" — AI/자동화가 만든 문서가 **기존 결재선에 그대로 올라간다.** [2차] <https://www.etnews.com/20250428000038>
3. **스펜딧**: 결재선을 유지하면서 "회사의 비용 정책을 준수하는 비용을 **자동으로 승인**하고 **검토가 필요한 비용을 관리자에게 알릴 수 있습니다**"라는 하이브리드. 다만 공식 도움말에 **전결·합의 같은 한국 특유 용어는 등장하지 않고** "승인자/최종승인자"로 단순화되어 있다. [1차] <https://docs.spendit.kr/ko/articles/3573165>
4. **비즈플레이**: 법인카드 결제 시 "결제와 동시에 법인카드 사용 내역이 카드사로부터 자동 수집"되어 영수증 수기 입력이 불필요. 사람은 확인 후 제출한다. "AI 영수증 처리"라는 표현 자체의 공식 근거는 약함. [1차] <https://bizplay.gitbook.io/manual/app/corpcard-manager>
5. **반례 — 채널톡 팀 알프**: 결재·승인이 아니라 **사내 Q&A·정보검색**에 특화된 별도 챗봇이다. 애초에 결재선과 만날 지점이 없다. 즉 "결재가 필요한 업무"와 "정보를 찾아주는 업무"를 제품 설계 단계에서 분리하고, **후자만** 독립 챗봇으로 떼어냈다. [1차] <https://channel.io/en/alf-team>

**정리**: 국내외를 막론하고 두 갈래가 공존한다 — Moveworks·Rippling·이카운트·영림원의 **미러링형**(기존 결재선에 AI 산출물을 태운다)과 Leena AI의 **별도 인박스형**(자체 승인 레이어를 얹는다). 그리고 **결재가 필요한 업무는 아무도 순수 채팅으로 처리하지 않는다.** 채팅은 정보 검색·초안 생성에 배치되고, 승인은 기존 결재 화면이나 전용 큐로 간다.

---

## 3. 인터페이스 패턴 카탈로그

여기서부터는 "업무를 실제로 처리하는 에이전트"가 사람과 만나는 지점의 형태를 패턴별로 정리한다. 각 패턴에 대해 ① 어떤 제품이 쓰는가 ② 어떤 업무 성격에 맞는가 ③ 알려진 약점을 적는다.

### 3.0 먼저: 왜 "채팅창 하나"로는 부족한가 (제품 벤더 스스로의 진단)

LangChain은 채팅 UI의 한계를 세 가지로 명시한다. [1차] <https://www.langchain.com/blog/introducing-ambient-agents>

1. **개시 비용**: "they rely on you to initiate the conversation. The agent is kicked off by the human sending a message."
2. **확장 불가**: "It requires the user to go into the chat interface and send a message every time they want the agent to do work. There is a lot of overhead in having the agent start work."
3. **동시성 없음**: "you can only have one conversation at a time. This makes it hard for us humans to scale ourselves — an agent can only be doing one thing for us at a time."

그 대안으로 제시된 **ambient agents**는 "listen to an event stream and act on it accordingly, potentially acting on multiple events at a time"로 정의된다. 그리고 그것을 사람이 감독하는 UI가 **Agent Inbox** — "modeled after some combination of an **email inbox and a customer support ticketing system**"이다.

인사·총무 업무는 정확히 ambient 성격이다. 입사일이 다가오고, 휴가 신청이 들어오고, 계약 만료가 다가오고, 법정 신고 기한이 온다. **사람이 채팅창을 열어야만 시작되는 구조는 이 도메인과 맞지 않는다.** 이것이 이 프로젝트의 상호작용 모델 논의의 출발점이다.

---

### 3.1 승인 큐 (Approval Queue) — "실행 전 정지"

**어떤 제품이 쓰는가**

- **OpenAI Agent Builder**: 캔버스에 **User Approval node**를 넣으면 사람이 승인할 때까지 워크플로가 멈춘다. "Agent Builder supports User Approval nodes that **pause the workflow until a human signs off**, useful for high-impact operations such as system changes or financial transactions." [1차] <https://developers.openai.com/api/docs/guides/agent-builder-safety>
- **OpenAI Agents SDK**: 툴 호출에 `needsApproval: true`(또는 비동기 판정 함수)를 걸면 run이 멈추고 `interruptions`를 반환하며, 같은 `RunState`에서 재개한다. [1차] <https://openai.github.io/openai-agents-js/guides/human-in-the-loop/>
- **OpenAI Operator**: 부작용이 있는 **최종 액션**(구매 완료, 삭제, 메시지 발송) 직전에만 확인을 요청하도록 학습되었고, 장바구니 담기 같은 중간 단계는 확인하지 않는다. 평가셋 607개 태스크에서 확인 요청 recall 92%. [1차] <https://cdn.openai.com/operator_system_card.pdf>
- **Zapier**: 툴별 "Require approval before running" 토글 + Human in the Loop 앱의 **Request Approval** 액션. 75개 태스크 실행 시 자동으로 사람 검토를 위해 일시정지한다. [1차] <https://help.zapier.com/hc/en-us/articles/38731463206029-Request-approval-to-keep-your-workflow-running-with-Human-in-the-Loop>
- **Lindy**: 부작용 있는 액션마다 "Ask for Confirmation" 토글. [1차] <https://docs.lindy.ai/testing/human-in-the-loop>
- **LangGraph**: `interrupt()` + `Command(resume=...)`. 문서가 이름 붙인 패턴이 **Approval Workflows**("Pause before executing critical actions (API calls, database changes, financial transactions)")다. [1차] <https://docs.langchain.com/oss/python/langgraph/interrupts>

**어떤 업무에 맞는가**: 되돌리기 어렵거나 고위험인 **단일 액션** — 금전 이동, 삭제, 대외 발송. 빈도가 낮을수록 잘 맞는다. 인사·총무로 치면 급여 이체, 퇴직 정산, 대외 공문 발송, 계약 체결.

**알려진 약점**

- **승인 피로 → 도장 찍기**: 승인 요청이 사람이 읽을 수 있는 속도보다 빨리 쌓이면 감독은 형식적 승인으로 붕괴한다. 학술적 근거는 §4.1(역U자 곡선)과 §4.2(확신-정확도 격차)에 있다.
- **승인 UI 자체가 공격 표면**: OWASP의 Lies-in-the-Loop — 사람이 보는 요약과 실제 실행되는 행동이 다를 수 있다(§4.3).
- **OpenAI Operator의 설계가 시사하는 것**: 모든 단계가 아니라 **되돌릴 수 없는 마지막 단계에만** 확인을 붙이는 것이 실제로 배포된 제품의 선택이다. "전부 승인받기"는 현실 제품의 기본값이 아니다.

---

### 3.2 인박스 (Inbox) — "여러 에이전트의 개입 요청을 한 곳에 모은다"

**어떤 제품이 쓰는가**

- **LangChain Agent Inbox** (`langchain-ai/agent-inbox`): "📥 An inbox UX for interacting with human-in-the-loop agents." 응답 액션이 네 가지로 고정되어 있다 — `accept`(그대로 승인), `edit`(인자 수정 후 승인), `response`(텍스트로 답변), `ignore`(처리하지 않고 닫음). `HumanInterrupt` 스키마는 `action_request{action, args}`, `config{allow_ignore, allow_respond, allow_edit, allow_accept}`, `description`(markdown)으로 구성된다. [1차] <https://github.com/langchain-ai/agent-inbox>
- 상위 개념(ambient agents)에서 HITL 상호작용은 세 종류로 나뉜다: **Notify**("let the user know some event is important, but not take any actions"), **Question**("ask the user a question to help unblock the agent"), **Review**("review an action the agent wants to take"). [1차] <https://www.langchain.com/blog/introducing-ambient-agents>

**설계상 중요한 점**: 인박스는 **승인 큐의 상위 집합**이다. 승인 큐는 "예/아니오"만 받지만, Agent Inbox는 **`edit`(사람이 인자를 고쳐서 진행)**과 **`ignore`**를 1급 액션으로 둔다. 인사·총무에서 실제로 자주 필요한 것은 "승인/반려"보다 "**이 부분만 고쳐서 진행**"이다.

**어떤 업무에 맞는가**: 여러 건의 개입 요청이 동시다발로 발생하고, 실시간성보다 **배치 처리**가 중요한 업무. 인사·총무의 일상(하루에 휴가 신청 12건, 경비 40건, 증명서 요청 8건)이 정확히 이 모양이다.

**알려진 약점**: 구조적으로 ① 알림 과부하, ② **맥락 손실** — 비동기로 검토할 때 "이 요청이 왜 왔는지"를 다시 파악해야 한다. 명시적으로 보고된 제품별 실패 사례는 확인 불가.

---

### 3.3 작업 목록 / 세션 기록 (Run History, Activity Feed)

**어떤 제품이 쓰는가**

- **Linear Agents**: `AgentSession`이 실행 생명주기를 추적하며 상태값은 **`pending / active / error / awaitingInput / complete / stale`** 6가지. `AgentActivity`가 **thought / action / elicitation / response / error / prompt** 콘텐츠 타입으로 세션 내 이벤트를 기록한다. [1차] <https://linear.app/developers/agent-interaction>
- **GitHub Copilot coding agent**: PR 타임라인의 "Copilot started work…" 이벤트에서 **session log**로 이동하고, 실시간 관전("watch the session live")도 가능하다. 어떤 MCP 서버·툴이 호출됐는지 로그에서 확인할 수 있고, 커밋마다 세션 로그 링크가 남아 감사 추적이 된다. 문서의 권장 리뷰 순서: "The **first thing to read** in a Copilot pull request is **the session log**, followed by the workflow approval prompt." [1차] <https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/manage-and-track-agents>
- **Devin**: 세션 뷰에 태스크 성공 확신도를 🟢🟡🔴로 표시한다. "Confidence Scores are **highly correlated with task success**, with 🟢 scores resulting in **twice the likelihood of a merged PR** compared to 🔴." [1차] <https://docs.devin.ai/work-with-devin/devin-review>

**어떤 업무에 맞는가**: 비동기·장시간 실행되고, 결과물과 과정을 분리해 보여줄 수 있는 업무. 사후 감사가 필요한 업무.

**알려진 약점**: 로그가 장황해지면 아무도 읽지 않는 형식적 아카이브가 된다. §4.2의 연구가 이를 뒷받침한다 — trace를 보여줘도 **오류 탐지 정확도는 개선되지 않았다.** Linear의 `stale` 상태값은 이 문제를 제품이 인정한 흔적으로 읽을 수 있다.

---

### 3.4 워크플로 캔버스 (Node Graph + Human Node)

**어떤 제품이 쓰는가**

- **OpenAI Agent Builder**: 노드 캔버스 안에 User Approval node를 다른 로직 노드처럼 연결. "The User Approval node is useful for workflows where agents **draft work that could use a human review before it goes out**." [1차] <https://developers.openai.com/api/docs/guides/agent-builder-safety>
- **n8n**: Slack 노드의 **"Send and Wait for Response"** + Response Type을 **Approval**로 설정. "No browser page opens: the workflow resumes as soon as someone responds, and **the output records who responded**." "Capture Who Responded"로 응답자를 기록하고, **"Restrict Who Can Approve"**로 승인 권한자를 제한한다. [1차] <https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.slack/approvals>
- **Make.com**: **Human in the Loop (Enterprise)** 앱을 시나리오 캔버스에 노드로 삽입, 검토 URL 생성 후 승인/거절을 웹훅으로 전달. "Make automatically **tracks who approved what and when**, making compliance reviews simple." [1차] <https://www.make.com/en/integrations/human-in-the-loop-enterprise>

**어떤 업무에 맞는가**: 다단계 비즈니스 프로세스에서 **특정 단계에만** 사람 게이트를 끼워 넣는 경우. 배치성·중간 빈도.

**알려진 약점**: 캔버스는 "이 노드를 지나면 무슨 일이 벌어지는지"를 **시각적으로 숨긴다.** 승인은 여전히 이진 버튼이고, 실제 실행될 내용을 노드 그래프에서 확인하기 어렵다. 그리고 이 패턴은 **구성하는 사람(관리자)의 화면**이지 승인하는 사람의 화면이 아니다 — 둘을 혼동하면 안 된다.

---

### 3.5 기존 도구 임베드 (Slack / Teams / 콘솔 인라인)

**어떤 제품이 쓰는가**

- **n8n Slack 승인**: Slack 자체가 승인 UI가 된다(위 3.4).
- **Slack Block Kit 기반 승인**: 버튼 클릭이 `block_actions` 이벤트로 돌아와 중단된 에이전트 실행을 재개한다. [1차] <https://docs.copilotkit.ai/slack/interactive>
- **Salesforce Agentforce**: 에스컬레이션 시 Omni-Channel Flow로 대화를 전송하고, Enhanced Chat이 전체 트랜스크립트 + 사용자 메타데이터를 사람 상담원 콘솔로 스트리밍한다 — "completely **eliminating redundant questions**". [1차] <https://www.salesforce.com/blog/agent-handoff/>
- **국내 대응물**: flex의 알림함/"할 일", 카카오워크의 슬래시 명령어가 같은 계열이다(§1).

**어떤 업무에 맞는가**: 팀이 이미 상주하는 도구에서 컨텍스트 전환 없이 빠르게 처리해야 하는 **고빈도** 업무.

**알려진 약점**: 채널 노이즈에 승인 요청이 묻힌다. 여러 채널에 흩어진 승인 이력을 감사하기 어렵다. (구조적 추정 — 이 제품들에 대한 구체적 사고 보고는 확인 불가.)

---

### 3.6 Diff / 미리보기 승인 — "요약이 아니라 실물을 승인한다"

**어떤 제품이 쓰는가**

- **Claude Code — Plan mode**: "Plan mode tells Claude to **research and propose changes without making them**… edits stay blocked until you approve the plan." 승인 후 편집 가능한 권한 모드로 전환된다. [1차] <https://code.claude.com/docs/en/permission-modes>
- **Cursor**: 에이전트가 작업하는 동안 실시간 diff를 보여주고("The diff view shows changes as they happen when the agent is working"), 방향이 틀렸으면 완료를 기다리지 않고 중단·리다이렉트할 수 있다. 완료 후 **"Keep All" / "Reject All"** 리뷰 바 + 파일별 내비게이션, 인라인 수정 후 수락도 가능. [1차] <https://cursor.com/learn/reviewing-testing>
- **GitHub Copilot coding agent**: 결과물이 **표준 GitHub PR**이므로 일반 PR 리뷰(diff·코멘트·승인)가 그대로 HITL 게이트가 된다. [1차] <https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent>
- **Devin Review**: PR diff의 이슈를 red(probable bug) / yellow(warning) / gray(FYI)로 **등급 분류**한다. [1차] <https://docs.devin.ai/work-with-devin/devin-review>

**어떤 업무에 맞는가**: 결과가 본질적으로 **before/after 구조 비교**로 표현되는 업무. 소프트웨어 변경이 대표적이다.

**알려진 약점**

- **리뷰 불가능한 diff**: diff가 커지면 반사적 승인으로 흐른다. 코드 리뷰 문헌에서 널리 보고되나 제품별 정량 데이터는 확인 불가.
- **리뷰 UI 자체가 사라지는 회귀**: Cursor는 최근 버전에서 리뷰 바/diff 내비게이션이 사라지는 문제가 공식 포럼에 다수 보고되었고, "Bring back per-change Apply + inline diff review — you're throwing away your best UX advantage"라는 사용자 피드백 스레드가 존재한다. [1차/제품 포럼] <https://forum.cursor.com/t/review-diff-navigation-bar-missing-after-agent-changes-v2-6-20/155587>, <https://forum.cursor.com/t/bring-back-per-change-apply-inline-diff-review-you-re-throwing-away-your-best-ux-advantage/160856>
- **인사·총무로 옮길 때의 어려움**: 코드는 diff가 자연스럽지만, "휴가 승인"이나 "급여 조정"의 diff는 무엇인가? **이것이 이 프로젝트가 풀어야 할 구체적 설계 문제다**(§5).

---

### 3.7 진행 상황 스트리밍 (Live Trace)

**어떤 제품이 쓰는가**: GitHub Copilot coding agent("watch the session live"), Linear Agent Activity(thought/action/elicitation/response/error/prompt가 실시간으로 쌓임), ServiceNow AI Control Tower(수명주기 전체 관찰을 표방하나 화면 단위 1차 문서는 확인 불가).

**어떤 업무에 맞는가**: 장시간 비동기 실행 중 사람을 **막지 않으면서**(non-blocking) 신뢰를 만들어야 하는 업무.

**알려진 약점**: **가장 중요한 경고가 여기 있다.** §4.2의 사용자 연구는 trace 인터페이스를 개선했을 때 오류 탐색 시간이 줄고 **사용자 확신은 높아졌지만 실제 정확도는 유의하게 개선되지 않았다**고 보고한다. 즉 **스트리밍은 신뢰를 만드는 장치이지 검증 장치가 아니다.** 포트폴리오 데모에서 이 구분을 흐리면 안 된다.

---

### 3.8 에스컬레이션 / 핸드오프 — "못 하겠으면 사람에게"

**어떤 제품이 쓰는가**

- **Intercom Fin**: 응답마다 **0~1 confidence score**를 매기고("Fin assigns a confidence score (0-1) to its response based on relevance of source material and clarity of the answer") 임계값 미달 시 에스컬레이션한다. **Escalation Rules**는 특정 데이터 속성이 감지되면 답을 생성하지 않고 곧바로 팀에 전달한다. 기본 에스컬레이션 조건에는 명시적 "사람 연결" 요청, 강한 불만 감지, **반복 루프에 갇힘(3회 연속 미해결 턴)**이 포함된다. [1차] <https://www.intercom.com/help/en/articles/12396892-manage-fin-ai-agent-s-escalation-guidance-and-rules>
- **Decagon**: "AI agent handoff is the process by which an AI-powered customer service system transfers a conversation — **along with its full context** — to a human agent when the AI cannot or should not handle it alone." 트리거: 낮은 확신도, 명시적 요청, 감정 임계값, 정책 기반 규칙(법적 분쟁·사기·VIP). 중요한 설계 지침: **모든 에스컬레이션이 풀 warm handoff를 요구하지 않으며**, 저확신 응답을 즉시 에스컬레이션하는 대신 **비동기 사람 검토로 플래그**하는 배포 방식도 있다. [1차] <https://decagon.ai/glossary/what-is-ai-agent-handoff>, <https://decagon.ai/glossary/what-is-an-ai-escalation-policy>
- **Sierra**: 에스컬레이션 시 대화를 적절한 팀으로 라우팅하며 **핸드오프용 요약을 자동 생성**한다. "supervised checks"로 두 번째 에이전트가 첫 번째의 실수를 잡아내는 계층도 있다. [1차] <https://sierra.ai/product/agent-sdk>
- **Salesforce Agentforce / Microsoft ESS Agent**: §2.2, §2.5 참조.

**어떤 업무에 맞는가**: 매 턴 계속/중단을 판단해야 하는 실시간 대화형 업무.

**알려진 약점**

- **에스컬레이션 블랙홀**: 사람 큐가 밀리면 넘어간 건이 방치된다. 개념은 업계에서 통용되나 위 제품들의 구체적 사고 사례 보고는 확인 불가.
- **확률적 가드레일 vs 결정론적 요구**: Sierra의 자연어 기반 가드레일은 확률적이어서, 규칙 기반의 결정론적 에스컬레이션을 요구하는 조직(감사·컴플라이언스)과 충돌할 수 있다. [2차] <https://www.getvocal.ai/blog/sierra-escalation-handling-comparison>
- **핸드오프 채널 제약**: Microsoft ESS Agent는 모바일에서 핸드오프가 **지원되지 않는다**(§2.5).

---

### 3.9 (인프라 계층) 사람 신호 대기 — Durable Workflow

**Temporal**: `workflow.wait_condition()` 호출 시 워커가 태스크를 서버에 반환하고 **컴퓨트를 전혀 쓰지 않는 상태**로 대기하며, 워크플로 상태는 서버에 영속화된다. 외부 승인 UI가 **signal**을 보내면(또는 타임아웃 시) 재개한다. "몇 초든 몇 달이든 동일하게 동작"하고 워커 재시작·배포·인프라 마이그레이션에도 타이머가 살아남는다. 계약 법무 서명, 임상 승인, AI 생성 문서의 사람 검토 등을 사례로 든다. [1차] <https://temporal.io/blog/human-in-the-loop-approvals>, <https://docs.temporal.io/ai-cookbook/human-in-the-loop-python>

**이 프로젝트에의 함의**: 인사·총무 승인은 **며칠 걸린다**(결재자 출장, 주말, 휴가). "사람이 응답할 때까지 프로세스가 살아 있어야 한다"는 것은 UI 문제가 아니라 상태 관리 문제다. LangGraph도 같은 요구를 체크포인터로 푼다("Nodes restart from the beginning on resume", "Side effects before `interrupt()` must be idempotent"). [1차] <https://docs.langchain.com/oss/python/langgraph/interrupts>

---

### 3.10 패턴 요약표

| 패턴 | 한 줄 정의 | 맞는 업무 | 대표 약점 |
|---|---|---|---|
| 승인 큐 | 되돌릴 수 없는 액션 직전에 실행을 멈추고 예/아니오를 받는다 | 저빈도·고위험 단일 액션 | 승인 피로 → 도장 찍기, 승인 다이얼로그 위조 |
| 인박스 | 여러 실행의 개입 요청을 받은편지함에 모아 배치로 처리한다 (accept/edit/response/ignore) | 다건·비실시간·이질적 요청 | 알림 과부하, 비동기 맥락 손실 |
| 작업 목록/세션 기록 | 에이전트 실행의 상태와 활동을 시간순으로 남긴다 | 장시간 비동기, 사후 감사 필요 | 아무도 읽지 않는 아카이브가 됨 |
| 워크플로 캔버스 | 프로세스를 노드로 그리고 특정 지점에 사람 노드를 끼운다 | 다단계 배치 프로세스 | 관리자 화면이지 승인자 화면이 아님 |
| 기존 도구 임베드 | Slack·콘솔 등 이미 쓰는 도구 안에서 처리한다 | 고빈도·저마찰 | 채널 노이즈에 묻힘, 감사 추적 분산 |
| diff/미리보기 승인 | 요약이 아니라 실제 변경 내용을 보여주고 승인받는다 | 결과가 before/after로 표현되는 업무 | 큰 diff는 리뷰 불가, 비-코드 도메인으로 옮기기 어려움 |
| 진행 상황 스트리밍 | 실행 중 단계·추론을 실시간으로 노출한다 | 장시간 비동기, 비차단 신뢰 형성 | **확신은 올리지만 정확도는 안 올림** |
| 에스컬레이션/핸드오프 | 확신도·정책·감정 조건에서 사람에게 맥락째 넘긴다 | 실시간 대화형 | 에스컬레이션 블랙홀, 채널 제약 |
| (인프라) durable wait | 사람 응답까지 프로세스를 영속 상태로 대기시킨다 | 며칠~몇 달 걸리는 승인 | UI가 아님 — 다른 패턴의 뒷단 |

---

## 4. 인터페이스 설계를 제약하는 외부 근거

제품 조사와 별개로, "사람이 개입하는 지점"을 어떻게 설계해야 하는지에 대해 인용 가능한 1차 근거들이 있다. 이 프로젝트의 상호작용 모델이 방어 가능해지려면 이 제약들을 설계에 반영했다는 것을 보여야 한다.

### 4.1 감독은 용량이 있는 자원이다

Emre Turan, *"Oversight Has a Capacity: Calibrating Agent Guards to a Subjective, Fatiguing Human"* (arXiv, 2026-06-08). [1차/논문] <https://arxiv.org/abs/2606.08919>

- 에이전트 행동 125건을 사람이 직접 라벨링한 결과, **무엇이 위험한지에 대한 리뷰어 간 합의가 약했다**: "reviewers only moderately agree on what is risky (Fleiss' kappa = 0.52), so there is no single correct label."
- 핵심 주장은 반직관적이다: **"more human oversight can make a system less safe, and the safety-optimal guard escalates below full escalation."** 에스컬레이션 양이 늘면 리뷰어가 피로해지므로, 안전성은 최대 감독이 아니라 중간 수준의 에스컬레이션 비율에서 정점을 찍는 역U자 곡선을 그린다.
- 따라서 감독은 분류 문제가 아니라 **자원 배분 문제**다: "human attention is finite, and the guard's escalation policy spends it."

**이 프로젝트에의 함의**: "모든 행동에 승인을 받는다"는 안전한 기본값이 아니다. 무엇을 사람에게 올릴지 고르는 정책 자체가 설계 대상이다.

### 4.2 근거(trace)를 보여줘도 정확도는 오르지 않을 수 있다

Madeleine Grunde-McLaughlin, Hussein Mozannar, Maya Murad, Jingya Chen, Saleema Amershi, Adam Fourney, *"Overseeing Agents Without Constant Oversight: Challenges and Opportunities"* (arXiv, 2026-02-18). [1차/논문] <https://arxiv.org/abs/2602.16844>

- Computer User Agent를 대상으로 한 사용자 연구 3건. 에이전트의 reasoning trace를 어떻게 보여줘야 사람이 오류를 잡아내는지 실험했다.
- 현행 관행에 대한 평가: **"current practices are cumbersome, limiting their efficacy."** 그리고 "Designing traces to have an informative, but not overwhelming, level of detail remains a critical challenge."
- 가장 중요한 결과 — **확신-정확도 격차**: 제안한 인터페이스는 오류 탐색 시간을 줄이고 사용자 확신을 높였지만, **실제 오류 탐지 정확도는 유의하게 개선하지 못했다.**
- 검증을 막는 요인으로 세 가지를 든다: 에이전트에 내장된 암묵적 가정, "users' subjective and changing correctness criteria", 그리고 추론 과정을 전달하는 것 자체의 어려움.

**이 프로젝트에의 함의**: "진행 상황 스트리밍 / thinking 노출"은 신뢰감을 만들지만 그것이 곧 검증은 아니다. 심사자에게 보여줄 때도, trace를 보여주는 것과 사람이 실제로 틀린 것을 잡아낼 수 있게 하는 것은 별개의 설계 목표로 다뤄야 한다.

### 4.3 승인 UI 자체가 공격 표면이다

OWASP, *"HITL Dialog Forging (aka Lies-in-the-Loop)"*. [1차/OWASP] <https://community.owasp.org/attacks/Lies_in_the_Loop>

- 정의: "HITL Dialog Forging, also known as LITL (Lies-in-the-Loop), is an attack vector that exploits Human-in-the-Loop (HITL) security mechanisms in AI agents."
- 공격 벡터 셋: **Dialog Padding**(악성 명령 뒤에 긴 무해한 텍스트를 붙여 사람 눈에 보이는 부분만 안전하게 만듦), **Markdown/HTML Injection**(승인 다이얼로그의 구조를 조작해 공격자 내용을 정상 UI 요소로 위장), **Action Descriptor Tampering**(에이전트가 할 일을 요약하는 메타데이터 변조).
- 실패 메커니즘: 사용자는 전체 작업의 일부 조각만 본다. 문서의 예시에서 사용자는 "the last portion of the wall of text, followed by 'Now I will conduct a security review'"만 보고 승인하지만 앞쪽에 심어 둔 명령이 실행된다.
- 권고: "HITL dialog clarity", 원격 소스 입력 검증, LLM 출력의 markdown/HTML sanitize, 다이얼로그 메타데이터 변조 방지.

**이 프로젝트에의 함의**: 승인 화면에 "에이전트가 요약한 자연어 설명"만 띄우는 설계는 구조적으로 취약하다. 승인 대상은 요약문이 아니라 **실행될 구조화된 행동 자체**여야 한다.

### 4.4 규제도 "사람이 도장만 찍는 상태"를 문제 삼는다

EU AI Act 제14조(Human oversight), 특히 제4항. [1차/법령] <https://artificialintelligenceact.eu/article/14/>

배치자가 감독자에게 보장해야 하는 능력으로 다음을 명시한다(원문 발췌):

- 자동화 편향 인식: "to remain aware of the possible tendency of automatically relying or over-relying on the output produced by a high-risk AI system (automation bias)"
- 출력 해석: "to correctly interpret the high-risk AI system's output, taking into account, for example, the interpretation tools and methods available"
- 무시·번복 권한: "to decide, in any particular situation, not to use the high-risk AI system or to otherwise disregard, override or reverse the output of the high-risk AI system"
- 정지: "to intervene in the operation of the high-risk AI system or interrupt the system through a 'stop' button or a similar procedure that allows the system to come to a halt in a safe state"

**이 프로젝트에의 함의**: 채용·인사평가 등 고위험 분류에 걸릴 수 있는 인사 업무에서, "사람을 한 명 끼워 넣었다"는 것만으로는 요건을 충족하지 못한다. **무시·번복·정지**가 UI에 실제로 존재해야 한다. (EU 역외 규제이지만, 포트폴리오 심사자에게 설계 근거로 인용 가능한 가장 구체적인 공개 기준이다.)

### 4.5 HITL 병목은 의도적으로 공격될 수 있다

OWASP Agentic AI Threats and Mitigations 계열 자료는 **"Overwhelming HITL" / Human Overload**를 별도 위협으로 분류한다. 시스템이 사람이 처리 가능한 양보다 많은 확인 요청을 만들어내면, 사용자는 급하고 일관성 없는 피드백을 주기 시작하고 에이전트는 그것을 신뢰할 수 있는 입력처럼 받아들인다. 공격자는 저위험 요청을 의도적으로 쏟아부어 리뷰어를 "승인 반사"에 길들인 뒤 고위험 행동을 끼워 넣을 수 있다. [2차] <https://kanupriyayakhmi.substack.com/p/the-limits-of-human-in-the-loop>

- *주의*: OWASP의 해당 가이드 원문(PDF)을 직접 열어 확인하지 못했다. 위 요약은 2차 정리본과 검색 발췌에 근거한다. 4.3의 Lies-in-the-Loop는 OWASP 자체 페이지로 직접 확인했으므로 신뢰도가 더 높다.

### 4.6 Human-AI 상호작용 설계 가이드라인

Microsoft HAX Toolkit, *Guidelines for Human-AI Interaction* (18개 가이드라인, Amershi et al., CHI 2019 논문 기반). [1차/벤더 연구] <https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/>

- 18개 가이드라인은 상호작용의 네 국면으로 묶인다: **최초 상호작용 시 / 상호작용 중 / AI가 틀렸을 때 / 시간이 지나면서.**
- "AI가 틀렸을 때"를 독립된 설계 국면으로 다룬다는 점이 이 프로젝트에 직접 쓰인다. 대부분의 제품 데모는 성공 경로만 보여준다.
- *주의*: 공개 페이지에서 18개 항목의 전문(번호+제목)을 직접 추출하지 못했다(이미지로만 제공). 네 국면 구분과 CHI 2019 출처는 확인했다.

---

## 5. 이 프로젝트가 비집고 들어갈 빈틈

### 5.0 먼저: 빈틈이 **아닌** 것 (차별점으로 쓰면 안 되는 것들)

조사 결과 아래는 **이미 포화**다. 이걸 차별점으로 내세우면 심사자가 30초 안에 반례를 댈 수 있다.

| 흔히 차별점으로 착각하는 것 | 이미 하고 있는 곳 |
|---|---|
| "채팅이 아니라 승인 큐를 쓴다" | OpenAI Agent Builder(User Approval node), Zapier, Lindy, Moveworks(Approvals Queue), Leena AI(pending inbox), n8n, Make |
| "인박스 모델로 여러 요청을 모은다" | LangChain Agent Inbox — 레퍼런스 구현과 스키마까지 오픈소스로 공개됨 |
| "확신도가 낮으면 사람에게 넘긴다" | Intercom Fin(0~1 confidence score), Decagon, Sierra, Agentforce |
| "에이전트의 작업 내역을 남긴다" | Linear(AgentSession/AgentActivity), GitHub Copilot(session log), ServiceNow(worknotes 감사) |
| "기존 승인 체계를 존중한다" | Moveworks의 Approval Mirroring, Rippling, 이카운트·영림원의 ERP↔전자결재 연동 |
| "에이전트를 관리하는 콘솔이 있다" | Workday ASOR, ServiceNow AI Control Tower, Microsoft Agent 365 — 대기업이 이미 카테고리를 선점 |
| "AI가 문서 초안을 쓰고 사람이 결재한다" | 더존 ONE AI가 이미 이 문장 그대로 제품 문서에 써 두었다 |

**상호작용 패턴 자체는 전부 누군가 쓰고 있다.** 따라서 차별점은 "어떤 패턴을 쓰는가"가 아니라 **"그 패턴 안에 무엇을 담는가"**에서 나와야 한다.

---

### 5.1 빈틈 ① — 인사·총무 업무의 "diff"를 아무도 정의하지 않았다

**관찰한 사실**

- 코딩 에이전트 생태계는 **승인의 대상을 요약이 아니라 실물(diff)로** 만들었다. Cursor는 "Keep All / Reject All"과 파일별 diff 내비게이션을 주고, Copilot은 표준 PR을, Claude Code는 plan mode에서 "propose changes without making them"을 준다(§3.6).
- 반면 **인사·총무 제품은 예외 없이 자연어 요약 + 예/아니오 버튼**이다. ServiceNow는 "review, adjust, and approve **the plan**", Salesforce는 "**draft a response**", Rippling은 "a single **proposal** so you can review and confirm", Moveworks는 "one-click buttons or natural language responses"다. 가장 앞선 Rippling조차 "numbers and names appear as **clickable links to real records**"까지가 최선 — 근거로 **역추적**은 되지만 **변경 전후 대조**는 아니다.
- 가장 가까이 간 것은 경비 도메인의 Ramp다: 권고마다 **"cites the exact policy text behind each recommendation, so reviewers can audit its reasoning"** — AI가 쓴 요약이 아니라 **회사 정책의 원문**을 근거로 붙인다(§2.8).

**왜 비어 있는가 — 어려워서다, 가치가 없어서가 아니다**

1. 코드는 텍스트라 diff가 공짜다. "휴가 승인"의 diff는 공짜가 아니다 — 잔여 연차 12→9일, 해당 주 팀 커버리지 4명→3명, 겹치는 신청자 2건, 성수기 정책 저촉 여부. **이 diff를 만들려면 도메인 상태 모델을 먼저 설계해야 한다.**
2. 그런데 §4.3의 OWASP Lies-in-the-Loop가 보여주듯, **요약문을 승인받는 구조는 구조적으로 취약하다.** 사람이 보는 것과 실행되는 것이 분리되어 있기 때문이다. 즉 이 빈틈은 "있으면 좋은 것"이 아니라 **안전성 논증이 붙는 것**이다.
3. 그리고 §4.2의 연구가 이를 보강한다 — trace(과정)를 더 잘 보여줘도 오류 탐지 정확도는 오르지 않았다. **과정이 아니라 결과의 구조를 보여주는 쪽**이 아직 시도되지 않은 영역이다.

**이 프로젝트가 할 수 있는 주장**: "인사·총무 행동의 승인 단위를 **구조화된 변경 명세(before/after + 영향 범위 + 저촉 정책)**로 정의하고, 사람은 요약이 아니라 그것을 승인한다."

---

### 5.2 빈틈 ② — "왜 이게 내 큐에 올라왔는가"를 승인자에게 설명하지 않는다

**관찰한 사실**

- 거의 모든 제품이 **관리자가 사전에 켜는 토글**로 승인 여부를 정한다: Zapier "Require approval before running", Lindy "Ask for Confirmation", OpenAI Agents SDK `needsApproval: true`, n8n "Restrict Who Can Approve".
- 즉 **정책은 관리자 화면에 있고, 승인자 화면에는 결과만 온다.** 승인자는 "이게 왜 나한테 왔는지", "내가 안 봤으면 시스템이 뭘 했을지"를 모른다.
- 예외가 둘 있다. **Ramp**(① review-only → auto-approval 점진적 자율성, ② "cites the exact policy text behind each recommendation, so reviewers can **audit its reasoning**")와 **Devin**의 🟢🟡🔴 confidence score("🟢 scores resulting in **twice the likelihood of a merged PR** compared to 🔴"). 둘 다 **인사·총무 제품이 아니다.**
- Ramp가 보여주는 것은 정확히 이 빈틈의 반대 사례다: 승인자에게 **AI가 만든 문장이 아니라 회사 정책의 원문**을 근거로 제시한다. 인사·총무에서 같은 것을 하려면 "어느 사규 조항", "어느 노동법 조문", "어느 결재 규정"에 근거했는지를 화면에 못 박아야 한다. 조사 범위의 **어떤 HR 제품도 이걸 하지 않는다.**

**왜 비어 있는가 — 벤더가 인정하기 싫은 것이기 때문이다**

"이 건은 에이전트가 판단을 못 해서 올렸습니다"라고 쓰는 것은 제품이 자기 한계를 화면에 노출하는 일이다. 마케팅 문구("human oversight built in")와 정면으로 충돌한다. §2.5 표에서 본 것처럼 ADP·Deel·Oracle은 "human oversight"를 반복하면서 **그 오버사이트가 언제 발동하는지는 끝내 쓰지 않았다.**

그러나 §4.1의 연구는 정확히 반대를 말한다 — **"human attention is finite, and the guard's escalation policy spends it"**, 그리고 감독량을 늘릴수록 안전해지는 것이 아니라 역U자를 그린다. **에스컬레이션 정책 자체가 1급 설계 대상**이라면, 그것은 화면에 보여야 한다.

**이 프로젝트가 할 수 있는 주장**: "승인 항목마다 **왜 사람에게 왔는지(어떤 규칙·어떤 불확실성)**와 **사람이 없었다면 무엇을 했을지**를 함께 보여준다. 그리고 그 정책은 시간이 지나며 좁혀진다(Ramp식 점진적 자율성)."

---

### 5.3 빈틈 ③ — 한국 결재선 문법을 1급으로 다루는 에이전트가 없다

**관찰한 사실**

- 한국 전자결재에는 **결재 / 전결 / 후결 / 합의 / 확인**이라는 고유 문법이 있다(§2.9). 특히 **합의**는 순차 승인이 아니라 **병행 동의**이고, **후결**은 이미 실행된 것을 사후에 열람·추인하는 구조다.
- 그런데 조사한 모든 에이전트 제품의 승인 원시형은 **단일 승인자의 예/아니오**다. LangChain Agent Inbox조차 `accept / edit / response / ignore` 네 가지이고, 여기에 "여러 부서가 병행 동의한다"나 "먼저 실행하고 나중에 추인한다"는 개념이 없다.
- 국내 제품도 메우지 못했다. 그룹웨어는 결재선 문법은 갖췄지만 AI는 요약·번역에 머문다(§1.5). 하이웍스 전자결재 공식 제품 페이지를 직접 확인한 결과 **결재선 지정·양식 설정·진행 확인·ERP 연동은 있지만 AI 기능 언급이 한 줄도 없다** — AI는 별도의 "AI채팅" 제품에 있다. [1차] <https://biz-solution.hiworks.com/product/function/groupware/approval> 반대로 신생 SaaS(스펜딧)는 AI 자동승인을 하되 **전결·합의 용어를 버리고 "승인자/최종승인자"로 단순화**했다(§2.9). **결재 문법과 AI가 같은 화면에서 만나는 제품을 이 조사에서 찾지 못했다.**

**왜 비어 있는가 — 시장 구조 때문이다, 가치가 없어서가 아니다**

해외 벤더에게는 한국 결재 문법이 시장이 아니다. 국내 그룹웨어에게는 에이전트가 아직 제품 로드맵이다. **교집합이 구조적으로 비어 있다.** 두레이가 "휴가 신청, 연장근로 등록을 즉시 처리"한다고 하면서 **결재 라인과의 관계를 끝내 문서화하지 않은 것**(§1.5)이 이 공백의 가장 선명한 증거다.

**단, 정직하게 짚어 둘 것**: 이것이 인터페이스 차별점인지 도메인 모델링 차별점인지는 논쟁의 여지가 있다. 다만 **합의(병행 동의)는 실제로 승인 UI의 위상(topology)을 바꾼다** — 하나의 "승인" 버튼이 아니라 N명의 동의 상태를 동시에 보여줘야 하고, 에이전트는 "누가 아직 동의 안 했는지"를 추적하며 대기해야 한다(§3.9의 durable wait 문제와 직결). 그 점에서 인터페이스 문제로 볼 근거가 있다.

---

### 5.4 빈틈이 아니지만 포트폴리오에서 유리한 것 — 실패를 보여주기

이것은 시장의 빈틈이라기보다 **데모의 빈틈**이다.

- Microsoft HAX Toolkit은 "**AI가 틀렸을 때**"를 네 개 설계 국면 중 하나로 독립시켰다(§4.6). Google PAIR도 "Errors + Graceful Failure"를 독립 카테고리로 둔다. [1차] <https://pair.withgoogle.com/guidebook-v2/>
- 그런데 이 조사에서 본 **모든 벤더 자료는 성공 경로만 보여준다.** 자기 한계를 문서에 적은 유일한 사례가 Microsoft의 "모바일에서 핸드오프 미지원"(§2.5)과 Cursor 포럼의 리뷰 UI 회귀 보고(§3.6)인데, 전자는 제약 목록이고 후자는 버그 리포트다.
- 심사자 관점에서 **"에이전트가 틀렸을 때 이 인터페이스가 어떻게 잡아내는가"를 데모에 넣는 것**은 낮은 비용으로 확실히 구별되는 선택이다. §4.2의 확신-정확도 격차를 인용하면 근거까지 붙는다.

---

### 5.5 정직한 결론

- **패턴 수준의 빈틈은 없다.** 승인 큐·인박스·활동 피드·캔버스·임베드·diff 승인·스트리밍·에스컬레이션 — 전부 누군가 배포했고, 상당수는 오픈소스 레퍼런스까지 있다. "채팅창이 아니다"는 그 자체로 차별점이 아니다.
- **빈틈은 한 층 아래에 있다**: ① 이 도메인에서 **승인 단위를 무엇으로 정의할 것인가**(요약문이 아니라 구조화된 변경 명세), ② **에스컬레이션 정책을 승인자에게 보여줄 것인가**, ③ **한국 결재 문법(특히 합의·후결)을 에이전트 원시형으로 다룰 것인가**.
- 셋 다 **가치가 없어서 비어 있는 게 아니라, 도메인 상태 모델을 먼저 설계해야 해서 비어 있다.** 벤더 입장에서는 범용 플랫폼을 파는 편이 이득이고, 국내 그룹웨어 입장에서는 아직 AI가 로드맵이다.
- **위험**: 이 세 가지는 전부 "인터페이스"라기보다 **"인터페이스가 드러내는 도메인 모델"**이다. PRD(#7)에서 차별점을 쓸 때 "우리는 채팅 대신 X를 쓴다"가 아니라 **"우리는 인사·총무 행동을 Y라는 단위로 모델링했고, 인터페이스는 그 단위를 그대로 보여준다"**로 써야 방어된다. 프로토타입(#8)은 ①을 먼저 검증하는 것이 가장 정보량이 높다 — ②③은 ①이 있어야 올라탈 수 있다.


---

## 6. 근거가 약한 부분

이 절은 위 결론 중 **다시 확인해야 할 것**을 모아 둔다. #7(PRD)과 #8(프로토타입)에서 이 문서를 인용할 때, 여기 적힌 항목은 단독 근거로 쓰면 안 된다.

### 6.1 접근 자체가 막힌 출처 (원문 대조 실패)

| 대상 | 문제 |
|---|---|
| Gartner 보도자료(40% 취소·agent washing·"약 130개 벤더") | HTTP 403. 검색 결과에 인용된 발췌문으로만 확인. 수치는 널리 인용되나 **전문 미확인** |
| SAP SuccessFactors Joule의 HITL 문서 | community.sap.com 3건 전부 403. *"Human-in-the-Loop SAP Agents: Approval, Escalation, and Audit"* 라는 제목이 존재한다는 것까지만 확인 |
| ServiceNow AI Control Tower의 화면 구성 | 공식 docs 403. "Risk & Compliance tab" 등 화면명은 **2차 블로그 인용**이며 §2.1의 게이트 서술(공식 커뮤니티 문서)보다 신뢰도가 낮다 |
| OWASP Agentic AI Threats Guide의 "Overwhelming HITL" | 가이드 PDF 원문 미확인. §4.5는 2차 정리본 기반. (반면 §4.3 Lies-in-the-Loop는 OWASP 자체 페이지로 직접 확인했으므로 신뢰도가 높다) |
| Microsoft HAX 18개 가이드라인 전문 | 이미지로만 제공되어 항목별 번호·제목 추출 실패. 네 국면 구분과 CHI 2019 출처만 확인 |
| 다우오피스 결재/전결/후결/합의/확인 정의(§2.9 표) | 최종 확인 시점에 HTTP 403. **정의문의 축자적 재확인 실패.** 하이웍스 공식 페이지로 "결재선" 개념만 간접 확인. §5.3의 빈틈 ③이 이 표에 의존하므로 재확인 필요 |
| Ramp Policy Agent 설정 문서(support.ramp.com) | 페이지에 "review-only mode" 문구가 **없다.** 해당 문구는 공식 블로그(ramp.com/blog/ai-agents-finance)에서 직접 확인했으므로 인용은 블로그를 근거로 한다 |

### 6.2 벤더 자체 주장 (제3자 검증 없음)

Rippling "70% 관리업무 절감 / 90% 조달 업무 절감", Navan "75% 자동승인율", Aisera "84% 자동해결률 / 78% 만족도 상승", Espressive "채택률 80~85% / 헬프데스크 콜 50~70% 감소", Leena AI "티켓 70%+ 자동해결", LG CNS "생산성 약 26% 향상", Oracle "600+ 사전 구축 에이전트", 뉴플로이 "누적 3조 원 / 20만 사업장", Brex "99% 무인 처리"(공식 페이지에서 동일 수치 확인 실패).

→ **이 문서의 어떤 주장도 이 수치들에 의존하지 않는다.** 인용할 경우 반드시 "벤더 자체 발표"로 표기할 것.

### 6.3 로드맵·예고 단계를 현재 기능으로 오독할 위험

- **flex**: 2025년 5~6월 블로그의 온보딩 자동 조정·"AI 동료"는 **로드맵**이다. 상용 확인된 것은 전자결재 자동입력·자동승인·알림함이다.
- **카카오워크 2.0**의 "실행형 AI 에이전트"는 **예고 단계**(미출시).
- **자버**의 연차 소진 예측·노무 리스크 알림은 "향후 강화 방침"으로 **미출시**.
- **BambooHR Bamboo AI**는 2026-09 컨퍼런스에서 "early look"만 예정 — 현재 공개 정보는 챗 인터페이스 소개 수준.
- **Deel AI Workforce**는 2025-08 베타. GA 시 인터페이스가 달라질 수 있다.

### 6.4 존재 여부 자체가 확인되지 않은 것

- **시프티**: 공식 워크플로우 페이지에 "AI"가 한 번도 없다. 생성형 AI 기능의 존재 자체가 확인 불가. (이 문서는 시프티를 "규칙 기반 승인 워크플로의 레퍼런스"로만 인용한다.)
- **뉴플로이**: RPA 프레이밍. 생성형/판단형 AI 요소 확인 불가.
- **두레이 익스텐션 에이전트**: "휴가 신청, 연장근로 등록 즉시 처리"가 조직 결재 라인과 어떻게 맞물리는지 **공식 자료에 설명 없음**. §5.3에서 이 공백 자체를 근거로 쓰고 있으므로, 반대 증거(문서화된 승인 단계)가 나오면 §5.3의 논증이 약해진다.
- **이카운트 e-approval**: 모듈 자체에 AI 자동판단이 있는지 확인 불가.
- **비즈플레이**: 자동 수집·저장은 확인. "AI 영수증 처리"라는 표현의 공식 근거는 약함.
- **영림원 K-System Ace I&I**: 보도자료 기반. AI가 결재 의사결정 자체를 하는지 불명확.
- **Gumloop의 human approval node**, **Notion Agents의 명시적 HITL 게이트**, **Relevance AI의 HITL 기능**: 1차 문서 확인 실패.
- **알리오·셀리즈**: 총무 백오피스 SaaS로서의 실체 확인 실패.

### 6.5 "구조적 추정"으로만 적은 약점들

§3의 패턴별 약점 중 다음은 **개념은 업계에서 통용되지만 해당 제품의 구체적 사고 사례 보고를 찾지 못한 것**이다: 인박스의 알림 과부하·맥락 손실, 세션 로그의 아카이브화, 캔버스의 실행 내용 은폐, Slack 임베드의 채널 노이즈, 에스컬레이션 블랙홀, 리뷰 불가능한 diff의 정량 실패율.

**예외적으로 직접 근거가 있는 약점**은 다음 넷이다 — 인용할 때 이쪽을 우선할 것.
1. §4.1 역U자 곡선과 Fleiss' kappa = 0.52 (논문 원문)
2. §4.2 확신은 오르지만 정확도는 안 오름 (논문 원문)
3. §4.3 Lies-in-the-Loop 공격 벡터 (OWASP 자체 페이지)
4. §3.6 Cursor의 리뷰 바/diff 내비게이션 회귀 (제품 공식 포럼)

### 6.6 조사 자체의 한계

- 세션 공용 WebSearch 예산(200회)이 소진되어, 마지막 단계의 보강은 WebFetch(직접 URL 접근)로만 수행했다. 따라서 **검색으로 발견됐어야 할 제품이 누락됐을 가능성**이 있다. 특히 국내 중소 HR SaaS와 총무·자산관리 영역이 얇다.
- **UI 스크린샷을 직접 본 항목은 없다.** 모든 인터페이스 서술은 제품 문서의 **텍스트 묘사**에 근거한다. "화면이 이렇게 생겼다"가 아니라 "문서가 이렇게 적었다"로 읽어야 한다. #8 프로토타입 전에 최소 2~3개 제품의 실제 화면(공개 데모·리뷰 영상)을 확인하는 후속 조사를 권한다.
- 인사·총무 **현업 담당자 인터뷰는 없다.** 이 문서는 전적으로 공개 문서 기반이며, "실제로 사람이 하는 일이 어디까지 남는가"에 대한 답은 **벤더가 문서에 쓴 대로**이지 관찰된 현실이 아니다.

