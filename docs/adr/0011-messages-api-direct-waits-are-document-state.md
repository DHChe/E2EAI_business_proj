# ADR-0011 — Claude 호출은 Messages API 직접이고, 사람 대기는 문서 상태이며, 내구 실행 계층을 두지 않는다

- **상태**: Accepted
- **날짜**: 2026-09-22
- **맥락 티켓**: #9 (결정), #4 (후보 조사), #10 (도구·책임 배정), #17 (미정 전이)

## 맥락

#4는 런타임 후보를 일곱 갈래로 조사했다. 오케스트레이션 계층(Temporal·Inngest·LangGraph)은
Claude 루프의 **대안이 아니다** — 어느 것을 골라도 그 안에서 Agent SDK나 수동 루프를 다시 골라야 한다
(`docs/research/agent-runtime-candidates.md:963-964`).

#4는 "루프 안에서 사람 승인을 기다리는 것"(C1)을 첫 기준으로 삼았다. 그 뒤 저장소의 결정이 그 수요를 없앴다.

- **에이전트는 결재 행위(승인·동의·반려·보류)의 행위자가 되지 않는다**(`CONTEXT.md:331`, 제외 13 `docs/PRD.md:141`).
- 증빙 파이프라인에서 모델을 부르는 곳은 두 곳뿐이고, 검산·대사·판정은 코드다(`docs/design/receipt-pipeline.md:74`).
  그 밖의 호출은 보류 답변(`docs/PRD.md:45`)과 여행사 이메일 판독(`CONTEXT.md:345`)이다.
- 기한은 저장값이 아니라 계산값이다(`PRC-3-1`, `docs/company/travel-procedure.md:48`). "N일 뒤에 깨워라"가 필요 없다.

그러면 에이전트 작업은 요청 한두 개로 끝나는 **짧은 작업**이고, 사람의 판단은 루프 **밖에서** 문서 상태를 바꾼다(claude §1).
세 레인(codex·grok·claude)이 서로 읽지 않고 같은 답에 닿았다(비교 문서 A1·A2·A3).

## 결정

1. **Claude 호출은 Messages API 직접 호출이다(B1).** TypeScript `@anthropic-ai/sdk`와 구조화 출력을 쓴다.
   Agent SDK(A)·Tool Runner(B2)·Managed Agents(B3)는 쓰지 않는다.
2. **보류 답변만 작은 수동 루프다.** 도구는 계산 기록과 조항 원문을 읽는 읽기 전용 도구뿐이고, 목록은 #10이 정한다.
   여러 요청에 걸치는 `messages` 배열은 작업 행에 저장한다. #4는 "`messages` 배열을 직렬화해 DB에 넣고"(`docs/research/agent-runtime-candidates.md:331`)까지만 적었고, 작업 행을 고른 것은 이 ADR의 결정이다.
3. **내구 실행 계층을 두지 않는다.** Temporal·Inngest·LangGraph 없이 자체 상태 기계와 DB `job` 테이블을 쓴다.
   `job`은 임대(lease)·시도 횟수·멱등 key·fencing 값을 갖는다.
4. **사람 결재 대기는 문서 상태(DB 행)다.** 에이전트 프로세스가 대기를 붙들지 않는다.
   `재무합의대기`인 문서의 실행은 끝나 있고 워커 슬롯은 반환돼 있다(codex §3.3-1).
5. **워커는 compose의 별도 서비스다**([ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md)의 그림).
   동시 LLM 작업 상한은 설정값이고 초기값은 2다 `[설계 가정]`.
6. **#17이 정하지 않은 전이는 이름 붙은 거부로 막는다.** 반려·보류 이후, 재심 복귀, 타임아웃이 그 자리다.
   리듀서는 그 전이를 추측하지 않고 `UNDEFINED_BY_17` 같은 거부를 돌려준다(claude §3.4). S11의
   "#17이 정하지 않은 후속 상태를 성공으로 처리하지 않는다"(`docs/PRD.md:161`)를 코드로 옮긴 것이다.

### 자체 구현이 지는 복구 계약

codex §3.3을 받는다. 요지만 적는다.

- 업무 상태·실행 상태·표시 상태를 나눈다. 승인자 큐의 문서 수와 동시 API 호출 수를 같게 세지 않는다.
- 작업은 입력 revision·정책 판·모델·프롬프트·스키마 판·시도 번호를 고정한다. 호출 전에 작업 의도를, 다음 턴 전에 완성된 응답을 저장한다.
  부분 토큰은 확정값이 아니다.
- 워커는 짧은 트랜잭션으로 임대를 잡고 **트랜잭션 밖에서** API를 부른다. 임대가 끝난 뒤의 늦은 결과는 fencing 값으로 거절한다.
- **API exactly-once는 주장하지 않는다.** 업무 반영을 revision·명령 key로 한 번만 받는다.

## 근거

**왜 B1인가.** 작업 모양이 요청 한두 개이기 때문이다. 나머지 후보는 이 모양에서 비용만 남긴다.

| 기각한 대안 | 기각 이유 |
| --- | --- |
| A Agent SDK | `canUseTool` 대기는 프로세스가 살아 있어야 한다(`docs/research/agent-runtime-candidates.md:112`). `defer`는 한 턴 도구 하나·`-p` 모드에서만 되고 세션 파일은 기본 30일 뒤 지워진다(`:134-136`). OTel `tool_decision`의 `source`는 출처 분류이지 사람이 아니다(`:242`). 내장 도구(파일·Bash·웹)가 이 작업에 쓸모없다(claude §3.2) |
| B2 Tool Runner | 공식 문서가 HITL·custom logging에는 수동 루프를 쓰라고 한다(`:305`). 러너 상태를 프로세스 밖으로 직렬화하는 방법이 문서에 없다(`:983`) |
| B3 Managed Agents | Beta다(`:417`). `user.tool_confirmation` 입력 예시의 칸은 `type`·`tool_use_id`·`result`·`deny_message` 넷이고 사람 actor 계약이 문서에 없다 `[1차]` — <https://platform.claude.com/docs/en/managed-agents/permission-policies>(사실 검증 6, 확인 2026-09-22). 이 판정은 "문서 부재" 수준이다 |
| B1 + Temporal | 아래 **Temporal** 문단 |
| B1 + Inngest | 트레이스·로그 보존이 플랜에 묶인다 — Free 24시간 ~ Enterprise 90일(`:723`). Free는 동시 step 5개다(`:945`) |
| B1 + LangGraph | checkpoint 히스토리는 그래프 상태 스냅샷이지 승인 감사 레코드가 아니다(`:799`). 재개하면 `interrupt()` 앞의 코드가 다시 돈다(`:750-751`) |
| 메모리 안 루프 | 재시작하면 대기가 사라진다(codex §3.2, claude §3.3) |

**왜 내구 실행 계층이 필요 없는가.** 세 계층 모두 **감사 원장으로는 탈락**이라, 어느 것을 골라도 감사는 우리 DB에 따로 쓴다.
그러면 계층이 가져오는 것은 R-b(대기)·R-d(재개)의 내구성뿐이다. 그런데 이 MVP의 대기는 계층 밖의 문서 상태이고,
재개는 짧은 작업의 재시도로 충분하다 — 결정성 제약·셀프호스팅·이중 쓰기의 비용만 남는다(claude §3.3, `[유도]`).

**Temporal.** 기각 논거는 둘이다.

1. **히스토리를 감사 원장으로 쓸 수 없다(R-e).** Retention Period는 "closed Workflow Executions"의 데이터 보존이고,
   그 끝에 정리 타이머가 돈다 `[1차]` — <https://docs.temporal.io/temporal-service/temporal-server#retention-period>(사실 검증 1, 확인 2026-09-22).
   Cloud의 보존은 1–90일이다(`docs/research/agent-runtime-candidates.md:603`). 승인자 신원은 자동으로 남지 않고 핸들러 입력에 직접 담아야 한다(`:644`).
   Cloud에는 종료 히스토리를 객체 저장소로 내보내는 Workflow History Export가 있다 — <https://docs.temporal.io/cloud/export>(사실 검증 1(d)).
   그 경우에도 보관되는 것은 Temporal 히스토리가 아니라 사본이므로 "히스토리를 원장으로 두는 안은 탈락"은 흔들리지 않는다 `[유도]`.
2. **상태가 둘이 된다.** 결재 상태와 감사 DB는 어차피 우리가 구현한다. 승인자 큐를 SQL에 다시 만들면 같은 상태가 SQL과 Temporal 두 곳에 산다(grok §3.3 R-c 셀).
   codex도 같은 이유로 보류했다 — "결재 상태·감사 DB를 어차피 구현해야 하는 현재 MVP에서 실행 엔진의 추가 상태와 운영 면까지 늘리지 않으려는 설계 판단이다"(codex §3.2).

**"90일 대기 상한"은 근거로 쓰지 않는다.** #4의 T-4는 이 보존 기간을 승인 대기 상한으로 읽었다. 그 읽기는 틀렸고
#9에서 정오표를 달았다(`docs/research/agent-runtime-candidates.md:937`). 같은 문서도 대기에는 별도 타임아웃이 없다고 썼다(`:592`).
열린 실행은 retention에 묶이지 않는다(사실 검증 1(c)). codex가 먼저 짚었다 — "Temporal은 강한 대안이다. **90일 대기로 탈락시키지 않는다.**"(codex §3.2)

**왜 워커를 처음부터 떼는가.** claude·grok은 API와 워커를 한 프로세스에 두었고, claude는 처리량이 모자랄 때 떼자고 했다(claude §3.6-4).
codex는 처음부터 뗐다(codex §4). 저장을 PostgreSQL로 고르면서 워커를 별도 프로세스로 떼기 쉬워진 것이 그 선택의 이유 중 하나였고
([ADR-0013](0013-postgres-object-storage-isolated-by-world-id.md)), 배포 그림도 별도 서비스로 그렸다([ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md)).
동시 상한은 codex 2, grok 4, claude 설정값으로 갈렸다. 설정값으로 두고 codex의 2에서 시작한다.

## 결과

- **반증 조건.** 아래 중 하나가 관측되면 이 결정은 틀렸다.
  1. #10이 에이전트에게 실행 전에 사람 확인이 필요한 부작용 도구를 주고, **한 작업 안에 사람 확인 지점이 둘 이상이며 그 사이에 보상 동작이 필요해진다**.
     그때 내구 실행 계층을 다시 평가한다(claude §3.6-1).
  2. API 응답 저장 직전·명령 저장 직후·임대 만료 시점에 프로세스를 끊었을 때 필드 이력 누락, 중복 결재, 무기한 고립 작업 중 하나라도 재현된다.
     그러면 자체 구현이 채택 조건을 통과하지 못한 것이고 Temporal 도입으로 추천을 바꾼다(codex §3.3).
  3. 커밋 전 부작용의 재시도를 멱등 key로 막을 수 없다. 그때는 그 호출만 액티비티로 감싸는 편이 맞고, 전체 이관과는 별개다(grok §3.4).
- 루프·상태 저장·재개·병렬 도구 결과 취합·감사 스키마를 우리가 쓴다. #4가 B1의 대가로 적은 그대로다(`docs/research/agent-runtime-candidates.md:905`).
- #10은 "에이전트에게 부작용 도구가 있는가"에 답해야 한다. 그 답이 반증 1을 연다.
- #17이 전이를 정하면 리듀서에 표 행을 더한다. 그 전까지 미정 전이는 성공으로 기록되지 않는다.
- 기존 결정과의 관계.
  - [ADR-0003](0003-approver-actions-three.md)은 provisional이다(`docs/adr/0003-approver-actions-three.md:3`). 역할별 액션 집합을 리듀서의 **데이터**로 두면 #17의 결과를 반영하기 쉽다(claude §3.4).
  - [ADR-0010](0010-human-routing-bounded-by-structure-measured-by-ratio.md)의 "멈추고 드러내는 것"(`docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:54`)은 작업 큐를 멈추는 것으로 구현할 수 있다(claude §3.1). 구현이 받는 규칙은 "미완료·대기 수를 공개하고 처리를 멈춘다"(`:36-37`)이다.
  - #9 본문 갱신 1은 "에이전트가 기안·결재를 대신 올리는 순간"을 전제로 적었다. ~~그 전제는 `CONTEXT.md:331`이 거뒀다.~~ **정정(#23, 2026-09-22)**: `CONTEXT.md:331`이 거둔 것은 결재 쪽뿐이다 — 에이전트는 결재 행위의 행위자가 되지 않는다. 기안 쪽은 다루지 않는다(`docs/PRD.md:111`). R-e는 그 뒤에도 채택 조건이다 —
    에이전트가 만든 값의 책임자와 사람이 한 결재의 행위자·책임자를 여전히 갈라 적어야 한다(claude §11).
- 감사·필드 출처의 저장 계약은 [ADR-0012](0012-transition-audit-provenance-in-one-transaction.md), 모델 호출 기록은 [ADR-0016](0016-record-and-replay-model-calls.md)이다.
- 통합 비교와 원문 링크는 [`docs/research/tech-stack-comparison.md`](../research/tech-stack-comparison.md).
