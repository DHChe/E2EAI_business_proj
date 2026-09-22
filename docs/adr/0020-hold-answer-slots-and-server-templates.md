# ADR-0020 — 보류 답변은 슬롯으로 짓고, 방향을 단정하는 문장은 서버 템플릿에서만 나온다

- **상태**: Accepted
- **날짜**: 2026-09-22
- **맥락 티켓**: #10 (결정), #9 (ADR-0011 결정 2의 도구 목록), #16 (조항·재량 블록), #11 (검증 잔여 위험의 측정)

## 맥락

승인자가 보류하고 에이전트에게 물으면, 그 답변은 카드와 같은 규율을 따른다. 숫자는 계산 기록에서만 가져오고, 근거는 `(문서코드, 판, 조항 식별자)`와 원문 인용으로 댄다.
재량 조항은 답하지 않고 물어볼 사실과 함께 판단 책임자에게 되돌린다. 답변은 새 판정 입력을 만들지 않는다(`docs/PRD.md:45`).
성공 기준은 인용이 원문의 연속 부분문자열이고 답변의 숫자가 계산 기록과 같기를(S4, `docs/PRD.md:154`), 재량을 판단한 답변이 0이기를(S5, `:155`) 요구한다.
[ADR-0011](0011-messages-api-direct-waits-are-document-state.md)은 이 답변만 작은 수동 루프로 두고, 읽기 전용 도구의 목록을 #10에 넘겼다(`docs/adr/0011-messages-api-direct-waits-are-document-state.md:27`).

Issue #10 갱신 2는 SlipScan의 ADR-7 "숫자는 SQL, 서술만 Claude"를 가리키며 "계산 환각이 구조적으로 불가능해진다"고 적었다(<https://github.com/DHChe/E2EAI_business_proj/issues/10>).
두 레인(codex·claude)이 그 문장을 SlipScan 코드가 받치지 않는다고 찾았고 코디네이터가 재확인했다 — 프롬프트 지시뿐이고, 스트림 조각을 검증 없이 흘리며, 저장 조건은 `stop_reason === "end_turn"`뿐이다(비교 문서 `:69`).

답변의 형태는 세 레인이 갈렸다(비교 문서 D4).

- grok: 모델이 문장을 쓰고 검사기가 숫자 = 계산 기록, 인용 = 부분문자열, 재량 판단·권고 없음을 대조한다(grok §4).
- codex: 모델은 계산 ref·조항 ref와 서술 조각만 내고 서버가 숫자·인용을 채운다. 방향을 주장하는 문장은 서버 템플릿으로만(codex §2.2).
  원문은 이렇게 적는다 — "계산이 120,000원 초과라도 LLM이 '한도 이내'라고 쓰면 숫자 일치 검사만 통과할 수 있다."
- claude: `text`/`calc`/`quote` 슬롯, `text`에 숫자 리터럴 금지, 결과 enum, 검증기 V1~V5. V1의 수사·V4의 문형·V5는 목록형이라 불완전하다고 스스로 적었다(claude §3.3, §4.3).

코디네이터는 codex의 반례가 grok 방식에 그대로 적용되고, claude 방식에서도 방향 문장이 `text` 조각 안에 남을 수 있다고 적었다(비교 문서 `:112`). 사용자가 U2로 codex와 claude를 합친 안을 골랐다.
도구 수는 codex 3, grok 4, claude 3이었고(비교 문서 `:34`), 코디네이터가 C2로 셋을 정했다.

이 ADR에서 **비교 문서**는 `docs/research/agent-architecture-comparison.md`다. A1–A15는 그 문서 `:48-62`, U1–U6은 `:175-180`, C1–C9는 `:191-199`, D1–D9는 `:75-147`에 있다.
레인 인용(codex·grok·claude §N)은 비교 문서 §0(`:11-19`)이 가리키는 #10 제안서의 절이다. `slipscan:`은 `/Users/astralpig/DEV/fc-Agentic-Workflow-prac`의 파일이다.

## 결정

1. **답변은 조각의 목록이다**(U2). 이음말 조각, 계산 기록을 가리키는 조각, 조항 원문의 구간을 가리키는 조각이 있다.
   숫자와 인용은 코드(렌더러)가 채운다 — 숫자는 작업 행에 고정된 revision의 계산 기록에서, 인용은 적용 판의 조항 원문에서 잘라서(claude §3.3, codex §2.2).
   그래서 S4의 "연속 부분문자열"은 검사 이전에 구성으로 성립한다(claude §3.3).
2. **금액·기한·결재선·판정의 방향을 단정하는 문장은 서버 템플릿에서만 나온다**(U2). 템플릿은 계산 기록의 의미 태그에 대응한다(codex §2.2).
   **모델은 이음말만 쓴다.**
3. **이음말에는 숫자 리터럴이 없다**(claude §4.3 V1). 승인·반려 권고를 싣지 않는다(`docs/PRD.md:141`).
4. **재량 조항이 걸린 질문은 판단하지 않고 되돌린다.** 물어볼 사실(`facts_to_ask`)과 판단 책임자(`decided_by`)는 코드가 조항 블록에서 복사한다. 모델이 쓰지 않는다
   (`docs/PRD.md:45`, `docs/adr/0005-policy-source-of-truth.md:76-77`, claude §3.3).
5. **답변은 판정 입력을 만들거나 바꾸지 않는다.** 답변기에게 쓰기 도구가 없고([ADR-0018](0018-two-model-contracts-no-side-effect-tools.md)), 답변 명령은 답변 행과 전이만 쓴다(claude §4.3 끝, S5 `docs/PRD.md:155`).
6. **도구는 읽기 전용 셋이다**(C2). 계산 기록(입력 revision 포함)을 읽는 것과 조항 원문을 읽는 것뿐이다.
   모두 작업 행에 고정된 문서 revision과 그 문서의 적용 판(`PRC-2-2`, `docs/company/travel-procedure.md:33`)에 묶인다.
   ADR-0011 결정 2의 "계산 기록과 조항 원문을 읽는 읽기 전용 도구"(`docs/adr/0011-messages-api-direct-waits-are-document-state.md:27`) 문언 안이다.
   grok의 `read_field`·`read_card_snapshot`은 문언 밖이라 두지 않는다(C2).
   원본 이미지·메일 원문·SQL·웹·커넥터·다른 문서 탐색은 도구가 아니다(A5, codex §3.2).
7. **루프 상한은 설정값이고, 초기값은 `[설계 가정]`이다**(A5). #11이 반증한다.
   레인의 제안은 codex 모델 요청 3회·도구 호출 6회(codex §3.2), grok 모델 턴 4회·도구 호출 8회(grok §5.2), claude 요청 4회(claude §4.3)였다.
8. **검증을 통과한 완성 답변만 보인다**(`docs/adr/0015-typescript-web-stage-sse-no-unverified-answer-text.md:26`).
   검증에 실패하면 원기록과 조항만 표시하고 실패 이유를 남긴다. 답변 생성 실패 때문에 새 사람 확인을 자동으로 만들지 않는다(codex §2.2).
9. **ADR-7("숫자는 SQL, 서술만 Claude")은 수정 채택한다.** 계약은 계산 언어(SQL이냐 TypeScript냐)가 아니라, LLM이 계산의 원본이 되지 않는다는 것이다(codex §2.2).
   계산은 정책 엔진이 하고, 결과는 입력 revision·계산기 버전·적용 조항을 가진 계산 기록으로 남는다(`docs/adr/0012-transition-audit-provenance-in-one-transaction.md:43`, claude §3.3).

### 세 도구의 나눔

codex와 claude는 셋을 다르게 나눴다.

| 레인 | 세 도구 |
| --- | --- |
| codex §3.2 | 계산 기록 읽기 · 조항 원문 읽기 · 계산 입력 계보 읽기 |
| claude §4.3 | 계산 기록 목록 · 계산 기록 한 건(입력의 출처·검증 수준 포함) · 조항 원문 |

어느 나눔을 쓸지와 도구 이름은 구현에서 정한다 `[설계 가정]`. 어느 쪽이든 범위는 계산 기록과 그 입력 계보, 조항 원문을 넘지 않는다.

## 근거

**왜 문장 검사로는 모자란가.** 숫자가 계산 기록과 같아도 문장의 방향은 반대일 수 있다. codex의 반례가 그것이다(codex §2.2).
숫자 대조와 부분문자열 대조는 방향을 보지 않는다. SlipScan의 방식은 그보다 약하다 — 지시문이 "그대로 인용합니다"라고 적을 뿐이고(`slipscan:lib/claude/prompts/report.ts:11`),
스트림 조각을 받는 즉시 흘리며(`slipscan:lib/claude/report.ts:205-212`), 저장 전에 보는 것은 `stopReason === "end_turn"`뿐이다(`:144-148`. API 필드 `stop_reason`은 `slipscan:lib/claude/report.ts:201`).

**왜 슬롯만으로도 모자란가.** 슬롯은 숫자와 인용을 구성으로 지킨다. 그러나 방향 문장은 이음말 안에 남을 수 있고, 검증기 V4는 권고 문형만 본다(비교 문서 `:112`).
그래서 방향을 단정하는 문장을 모델에게서 빼 서버 템플릿으로 옮긴다. U2가 codex §2.2와 claude §3.3을 합친 이유다.

**왜 도구가 셋이면 되는가.** 판정에 쓰인 사실은 모두 어떤 계산 기록의 입력이고, 입력 revision이 계산 기록에 남는다(`docs/adr/0012-transition-audit-provenance-in-one-transaction.md:43`).
판정에 쓰이지 않은 사실은 답할 필요가 없다. 답변은 새 판정 입력을 만들지 않기 때문이다(`docs/PRD.md:45`, claude §4.3).
재량 블록(`facts_to_ask`·`decided_by`·`must_not_auto_decide`)은 조항 원문의 블록 안에 있다(`docs/adr/0005-policy-source-of-truth.md:68-73`).

| 기각한 대안 | 기각 이유 |
| --- | --- |
| 모델이 문장을 쓰고 검사기가 숫자 = 계산 기록, 인용 = 부분문자열을 대조(grok §4) | 숫자가 맞아도 방향이 반대인 문장이 통과한다(codex §2.2, 비교 문서 `:112`) |
| 슬롯 + 목록형 검사기(V1~V5)만(claude §3.3, §4.3) | 방향 문장이 이음말 안에 남을 수 있고 V4는 권고 문형만 본다(비교 문서 `:112`). 슬롯 자체는 결정 1로 받았다 |
| 프롬프트 지시만(SlipScan ADR-7, Issue #10 갱신 2) | 모델이 숫자를 바꿔 써도 잡는 코드가 없다(비교 문서 `:69`) |
| 계약 1개 + 보류 답변은 템플릿만(grok §3.4 B) | ADR-0011 결정 2(보류 답변은 모델의 수동 루프)를 개정해야 하고, 열린 질문은 템플릿에 없다(grok §3.4) |
| 읽기 도구 4개 — `read_field`·`read_card_snapshot` 포함(grok §5.2) | ADR-0011:27의 "계산 기록과 조항 원문" 문언 밖이다(C2) |
| 답변 토큰 스트리밍(SlipScan ADR-6, `slipscan:docs/ARCHITECTURE.md:521`) | [ADR-0015](0015-typescript-web-stage-sse-no-unverified-answer-text.md) 결정 5와 충돌한다(`docs/adr/0015-typescript-web-stage-sse-no-unverified-answer-text.md:26`) |

## 결과

- **반증 조건.** 아래 중 하나가 관측되면 이 결정은 틀렸다.
  1. 슬롯과 템플릿으로 지은 답변을 승인자가 읽지 못한다. 예를 들어 #11 사용자 검수에서 "표 조각의 나열"로 판정되는 비율이 높다(claude §3.4-1). 그때도 검증 전 비노출은 유지한다.
  2. 한국어 수사("삼만 원", "사박")가 V1을 새어 S4·S5 위반이 #11 검수에서 나온다(claude §3.4-2).
  3. 숫자가 같은데 설명의 방향이 틀린 답이 노출되거나, 독립 재계산의 입력이 빠진다. 그러면 이음말을 더 줄여 근거 선택과 템플릿 구성만 남긴다(codex §2.2 "추천이 틀리는 조건").
  4. 세 도구로 답할 수 없는 질문이 핵심 시나리오의 대부분이다(codex §3.2 "추천이 틀리는 조건", claude §4.7-4). 그때도 범용 DB·브라우저 도구를 열지 않고, 읽기 전용을 유지한 채 범위를 사례별로 다시 본다.
  5. 모델이 읽어야만 나오는 **판정**이 규정에 생긴다(claude §3.4-3).
- 템플릿 목록, 의미 태그, 조각 스키마의 이름은 구현에서 정한다 `[설계 가정]`. 설명용 스케치는 `docs/ARCHITECTURE.md` §4다.
- 공개 데모의 보류 질문은 미리 고른 목록뿐이다(C7). 공개 링크에는 "임의 업로드와 자유 대화는 없다"(`docs/adr/0017-public-demo-single-vm-replay-default-capped-live.md:39`).
- 기존 결정과의 관계.
  - [ADR-0011](0011-messages-api-direct-waits-are-document-state.md) 결정 2의 도구 목록을 채운다(`docs/adr/0011-messages-api-direct-waits-are-document-state.md:27`). 수동 루프와 `messages` 배열의 작업 행 저장(`:28`)은 그대로다.
  - [ADR-0005](0005-policy-source-of-truth.md) ⑦: 근거 문구는 조항의 본문과 블록을 원문에서 그대로 가져온다(`docs/adr/0005-policy-source-of-truth.md:110`). 인용 조각이 그것을 구성으로 지킨다.
  - [ADR-0015](0015-typescript-web-stage-sse-no-unverified-answer-text.md) 결정 5: 화면에는 단계만 SSE로 보내고, 검사를 통과한 완성 문장만 표시한다.
  - [ADR-0018](0018-two-model-contracts-no-side-effect-tools.md): 이 답변을 쓰는 것이 답변기다.
