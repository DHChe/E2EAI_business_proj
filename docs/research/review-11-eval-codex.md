# #11 Eval 계획 독립 검수 — codex

- **검수일**: 2026-09-25
- **대상 HEAD**: `706ca9e` (`958862d..706ca9e`의 변경 전부)
- **기준**: `docs/research/eval-plan-comparison.md:44-190`의 A1~A16·G1~G8·F1~F15·U1~U5·C1~C18, `docs/research/eval-plan-lane-brief.md:24-46`의 D1~D15, 세 레인 원문 브랜치의 제안서. 합격 값은 `docs/PRD.md:145-166`을 기준으로 보았다.

## 요약

**병합 전 수정 필요.** 83개 ADR 반증 조건과 추가 7개는 모두 표에 있으나, U2의 판정 조건을 늘린 문장, H9·H10의 분류, 첫 실측 전 재생 절차, 세계 경계, 기준선 근거 포인터, 인용 규율을 고쳐야 한다.

U1~U5·C1~C18·D1~D15의 나머지 결정은 대체로 옮겨졌고, ADR-0032~0036이 가리키는 EVAL §1·§5·§7·§9·§10·§11·§12·§15도 존재하며 해당 절에 설명이 있다(`docs/EVAL.md:25-31`, `docs/EVAL.md:35-62`, `docs/EVAL.md:286-389`, `docs/EVAL.md:446-657`, `docs/EVAL.md:724-753`). 아래 결함은 결정 자체를 바꾸자는 뜻이 아니다.

## 결함

### D1. H9·H10을 한 덩어리의 함정 합격 조건으로 적었다

- **위치**: `docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:40-41`; `docs/adr/0034-two-synthetic-sets-distribution-refutes-only.md:85`.
- **문제·근거**: 보완 문장은 **H 전체**를 함정 집합의 합격 조건이라고 한다. 그러나 H9는 월별 수기 확정 비율 10%, H10은 규칙 강등 문턱 7%인 `[설계 가정]`이다(`docs/design/receipt-pipeline.md:2525-2526`). PRD와 EVAL은 H1~H8·H11만 위반 0으로 두고 H9·H10은 별도로 취급한다(`docs/PRD.md:162`, `docs/EVAL.md:81`, `docs/EVAL.md:585`). 함정 집합에서 비율을 합격으로 내면 D3의 함정 집합 규칙에도 어긋난다(`docs/research/eval-plan-lane-brief.md:32`).
- **고칠 안·작성자 선택 판정**: ADR-0010 결정 4 보완은 **수정 권고**. H1~H8·H11의 하드 위반 0만 함정 합격으로 쓰고, H9·H10 및 R1~R4의 값 초과는 자체 렌더링 분포에서 `가정 반증`으로 보고한다고 분리한다. 제품 실행 중 초과 시 멈추는 결정 3과 평가 phase가 멈추지 않는 D12는 그대로 둔다(`docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:36-42`, `docs/EVAL.md:714-715`).

### D2. 첫 실측 전에는 없는 기록으로 매 커밋 재생을 요구한다

- **위치**: `docs/adr/0035-live-model-runs-only-on-user-approval.md:25-31`; `docs/EVAL.md:49-61`, `docs/EVAL.md:532`, `docs/EVAL.md:569`.
- **문제·근거**: 첫 승인 실측에서 재생 기록을 *처음* 만든다고 하면서 코드 변경 때마다 전 시나리오 재생을 요구한다. 첫 실측 전 재생은 기록이 없어 `REPLAY_MISS`가 되고, ADR-0016은 이를 실패로 정의한다(`docs/adr/0016-record-and-replay-model-calls.md:31`). 첫 step 뒤 구현이 계속되는 구간의 AC가 무엇으로 통과하는지 주니어 구현자가 정할 수 없다. 손으로 쓴 응답은 제어 흐름·하드 규칙 시험용이라고 이미 정했다(`docs/EVAL.md:516-530`).
- **고칠 안**: 첫 승인 실측 전에는 가짜 응답 시험을 매 커밋 실행하고 재생은 `시드 전·미측정`으로 기록한다. 승인 실측으로 기록이 생긴 뒤에는 D8대로 매 커밋 전 시나리오를 재생한다고 ADR-0035와 EVAL §9·§10에 시점을 분명히 적는다. 첫 실측 전 `REPLAY_MISS`를 성공한 재생으로 표시하지 않는다.

### D3. U2의 지표 이동 조건에 새 동시 문턱을 더했다

- **위치**: `docs/EVAL.md:623-625`, `docs/EVAL.md:222`; 사용자 결정은 `docs/research/eval-plan-comparison.md:159`, 두 벌을 정한 U4는 `:161`.
- **문제·근거**: U2는 해시로 고정한 **분포 집합의 첫 실측**에서 해외 출장·법인카드 지출의 법정 플래그가 3건 미만이면 지표를 옮기라고 정했다. U4는 카드 전표 두 벌의 **R1을 두 줄로 공개**하라고 정했다. EVAL은 법정 플래그까지 벌마다 세고 **두 벌 모두** 3건 미만일 때만 옮긴다고 새 조건을 추가했다. 한 벌만 3건 미만일 때 U2와 결과가 달라지고, ADR-0034는 U2의 원래 단일 문장만 싣는다(`docs/adr/0034-two-synthetic-sets-distribution-refutes-only.md:37-44`). `[설계 가정]` 표기만으로 사용자 결정의 판정 문장을 바꿀 수는 없다.
- **고칠 안·작성자 선택 판정**: 두 벌 동시 문턱은 **수정 권고**. 첫 실측 전에 U2 판정에 쓸 고정 분포 한 벌을 지정하고 U2 문장을 그대로 적용한다. 둘째 벌의 플래그는 민감도 결과로 나란히 공개하되 지표 이동의 추가 조건으로 삼지 않는다. U4의 R1 두 줄 공개는 유지한다.

### D4. 분포 전체를 한 세계에 넣는 선택이 세계 정의와 충돌한다

- **위치**: `docs/EVAL.md:315`; 기존 세계 정의는 `docs/ARCHITECTURE.md:567`.
- **문제·근거**: ARCHITECTURE는 평가 시나리오 하나를 세계 하나로 둔다. EVAL은 분포 집합 전체를 `world_id` 하나로 묶는다. §5는 24개 출장을 구성하고 §9의 정답은 `scenario_id`별이다(`docs/EVAL.md:297-305`, `docs/EVAL.md:452-460`). 이대로는 각 출장 시나리오의 격리와 한 세계의 R4 집계가 동시에 성립하는지 불분명하며, 세계 누수 시험의 기준도 흔들린다(`docs/EVAL.md:341`, `docs/EVAL.md:507-514`).
- **고칠 안·작성자 선택 판정**: 한 세계 선택은 **수정 권고**. 각 시나리오의 `world_id`를 유지하고 평가기가 공통 합성 시계와 사람 ID로 1인 하루 R4를 집계하도록 적는다. 한 세계로 묶을 이유가 있다면 ARCHITECTURE의 세계 정의와 시나리오 단위를 먼저 일치시키고 격리 시험을 다시 설명한다. R4 측정 자체는 유지한다(`docs/EVAL.md:137`).

### D5. S16 기준선의 두 번째 동작을 뒷받침하지 못하는 포인터

- **위치**: `docs/EVAL.md:410`; 같은 포인터를 쓰는 PRD는 `docs/PRD.md:166`.
- **문제·근거**: EVAL은 `docs/research/ax-competitive-landscape.md:207`을 거래 한 건의 금액을 유형 한도와 대조한다는 근거로 든다. 그 줄은 Policy Agent가 카드 거래와 환급을 평가하고 승인·거절·상향 권고를 한다는 설명일 뿐, **거래 단위 금액 한도 대조**를 말하지 않는다. 40개 포인터 표본에서 주장과 다른 줄은 이 한 곳이다. C11이 정한 기준선의 두 동작을 철회하자는 뜻은 아니다(`docs/research/eval-plan-comparison.md:183`).
- **고칠 안**: 실제로 거래 단위 한도 대조를 서술한 원문 줄로 교체한다. 확인된 원문이 없다면 해당 동작의 근거 상태를 `[설계 가정]`으로 밝히고, C11의 기준선 정의와 §8-3 허수아비 점검은 유지한다(`docs/EVAL.md:403-444`).

### D6. 자기보고 신뢰도 인용에서 원문의 주어를 잘랐다

- **위치**: `docs/adr/0032-pass-judged-by-deterministic-checks-and-human-sample.md:11`; 인용 규칙은 `AGENTS.md:16-18`.
- **문제·근거**: ADR-0032는 자기보고 신뢰도에 관한 원문의 술어만 따옴표로 감쌌다. 원문 주어는 바로 앞줄에 있고(`docs/adr/0008-extraction-uncertainty-is-first-class.md:39-42`), 인용 구절만 읽으면 무엇을 단독 게이트로 쓸 수 없는지 빠진다. 문자열 자체는 연속이지만, 이번 작업의 주어·스코프 보존 규칙에는 미달한다(`docs/research/eval-plan-lane-brief.md:19-22`).
- **고칠 안**: 따옴표를 빼고 ADR-0008의 판단을 주어와 함께 간접 서술한다. 두 줄을 이어 하나의 직접 인용으로 만들지 않는다.

## 권고

### R1. T-LIMIT 추가는 수용하고 전체 코드 수를 밝혀 둔다

**판정: 수용.** C12는 claude의 15종을 *뼈대*로 정했으므로 한도 전용 T-LIMIT을 보태는 것은 결정을 뒤집지 않는다(`docs/research/eval-plan-comparison.md:184`). S3·S10의 독립 재계산을 구별하는 데에도 쓸모가 있다(`docs/EVAL.md:331`, `docs/EVAL.md:682`). 다만 표에는 현재 16개 코드가 있으므로 “15종 뼈대 + T-LIMIT 1종”이라고 명시하면 “15종”을 완성 목록으로 오독하지 않는다(`docs/EVAL.md:327-346`).

### R2. 사원·주임 무명 출장자는 수용하되 식별자를 고정한다

**판정: 수용, 식별 방식 보완 권고.** 명명된 직원 12명에 없는 두 직급을 시험하는 것은 결재선·한도 경계를 넓힌다(`docs/EVAL.md:298`, `docs/company/org.md:48-61`). 그러나 S11은 사건의 책임자·행위자를 다시 찾아야 한다(`docs/PRD.md:161`). 첫 step의 시나리오 입력에 각 무명 출장자의 안정된 합성 사람 ID와 소속·직급·역할을 기록하고, 이름이 없다는 이유로 감사 식별자가 빈칸이 되지 않게 한다.

### R3. S16의 “거래 한도 안·합계 한도 초과”는 조건을 더 적는다

**판정: 수정 권고.** 만들 수 없다면 첫 step이 장부에 기록한다는 안전장치는 옳다(`docs/EVAL.md:418`). 다만 같은 유형의 거래 각각이 한도 안이어도 합계가 한도를 넘을 때, 기준선의 다른 동작인 **신청↔정산의 유형·세그먼트 금액 대조**가 먼저 잡을 수 있다(`docs/EVAL.md:409-410`, `docs/EVAL.md:426`). 첫 step이 거래 금액·합계 한도·사전 신청의 유형/세그먼트 승인액을 함께 적고, 기준선 두 동작 모두를 통과하는 쌍일 때만 `놓침`을 기대값으로 둔다. 그런 쌍이 규정으로 불가능하면 30쌍을 억지로 채우지 말고 불가능한 이유와 실제 쌍 수를 장부와 보고서에 공개한다(`docs/EVAL.md:418`, `docs/EVAL.md:433`).

### R4. 첫 step의 시나리오 입력 소유자와 파일을 지정한다

첫 step은 규정과 “시나리오 입력”을 받아 정답·세계 픽스처·S16 차이 목록을 출력한다고 하지만, 입력 시나리오를 어느 파일에서 누가 먼저 만드는지 정하지 않는다(`docs/EVAL.md:465-472`). §6은 첫 step이 함정 항목·변형을 채운다고 하고 §5는 첫 실측 전에 해시를 고정한다고만 한다(`docs/EVAL.md:322`, `docs/EVAL.md:310-311`). 주니어 개발자가 EVAL만 보고 바로 step을 쓰려면, 같은 step에서 시나리오 파일을 먼저 만드는지와 허용 경로·해시 시점을 한 문장으로 명시해야 한다. 정답을 코드보다 먼저 잠그는 D6은 그대로 지킨다(`docs/research/eval-plan-lane-brief.md:35`).

### R5. 인용의 적용 범위는 사람 표본에서도 확인한다

F7의 존재 검사는 모델이 문구나 `span`을 직접 고르는 길을 막는 점에서 맞다(`docs/EVAL.md:635-638`). 그러나 ADR-0036은 조항 하나의 바깥 머리말이 적용 범위를 정할 수 있다고 스스로 반증 조건을 둔다(`docs/adr/0036-hold-answer-quotes-whole-clause.md:58-60`). 따라서 “범위가 틀린 인용이 구조상 생기지 않는다”는 단정을 줄이고(`docs/EVAL.md:631`), 정답 조항 목록 검토와 사람 표본의 “조항 전문이 질문과 맞는가”를 그 위험의 보완 검사로 연결해 적는다(`docs/EVAL.md:643-645`, `docs/EVAL.md:601`). D11의 조항 전문 부착은 유지한다.

## nit

### N1. 띄어쓰기

`docs/EVAL.md:272`의 “하나 는”을 “하나는”으로 고친다.

### N2. S16의 규모 표기

§2는 S16을 “30쌍”으로 단정하고 §8은 만들 수 없는 종류를 장부에 남긴다고 한다(`docs/EVAL.md:85`, `docs/EVAL.md:418`). §2에도 “계획 30쌍, 실제 수는 첫 step에서 확정”이라고 적으면 독자가 결과 수로 읽지 않는다.

## §4 교차 검증

codex가 찾은 F13을 제외한 **F1~F12·F14·F15**를 세 레인 원문에 `git show DHChe/frontier-11-eval-{codex,grok,claude}:docs/research/eval-plan-proposal-*.md`로 대조했다. 아래 레인 원문 포인터는 해당 브랜치의 파일:줄이며, 작업 브랜치를 바꾸지 않았다. `확인`은 원문 주장과 현재 근거가 맞음을, `부분`은 주장에 유효한 범위 제한이 있음을 뜻한다.

| 항목 | 찾은 레인 | 판정 | 근거(파일:줄) | 새 문서에 미치는 영향 |
| --- | --- | --- | --- | --- |
| F1 구현·정답의 같은 모델 계열 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:28`; `docs/agents/harness.md:173` | EVAL §9-5의 무충돌 재계산 근거가 맞다(`docs/EVAL.md:493-503`). |
| F2 합의값을 옮길 주체 부재 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:519`; `docs/agents/harness.md:274`, `:289` | U5의 별도 하네스 이슈·그 전 `blocked`가 필요하다(`docs/EVAL.md:502`). |
| F3 가짜 응답과 ADR-0016 기각의 긴장 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:827`; `docs/adr/0016-record-and-replay-model-calls.md:56` | 제어 흐름·하드 규칙으로만 좁힌 보완이 타당하다(`docs/EVAL.md:518`). |
| F4 공휴일·환율 입력 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:493-500`; `docs/company/travel-procedure.md:61`, `docs/company/travel-policy.md:319` | 첫 step의 세계 픽스처 둘이 필요하다(`docs/EVAL.md:476-483`). |
| F5 S12 출처별 측정 한계 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:54`; `docs/PRD.md:162` | JaWildText·실물의 H·R은 해당 없음으로 옮긴 수정이 맞다(`docs/EVAL.md:81`). |
| F6 #11 코멘트의 낡은 포인터 둘 | claude | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:835`; `docs/design/receipt-pipeline.md:2296`, `:2505`; `docs/PRD.md:116`, `:121` | 새 EVAL의 PRD-2는 `:121`을 쓴다(`docs/EVAL.md:223`). 이 검수의 수정 범위 밖인 이슈 코멘트 정정은 남는다. |
| F7 D11 뒤 인용 범위 결함 | claude | 부분 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:651-664`; `docs/adr/0036-hold-answer-quotes-whole-clause.md:58-60` | 모델의 구간 선택 경로는 사라지지만 조항 바깥의 스코프는 남을 수 있다. R5. |
| F8 D13과 가설의 모집단 차이 | claude·grok | 확인 | `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:523`; `docs/PRD.md:120` | U2의 해외 출장·법인카드 범위가 맞다(`docs/EVAL.md:618`). |
| F9 판 전환 시나리오의 두 ADR 반증 | grok | 확인 | `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:644`; `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:84`, `docs/adr/0022-policy-amendment-by-ceo-no-in-app-publishing.md:58` | 제외와 `TRV-15-2` 한 블록 취급이 맞다(`docs/EVAL.md:732`). |
| F10 93%와 H10 7%의 관계 | grok | 확인 | `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:643`; `docs/design/receipt-pipeline.md:2526`; `docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:59-60` | H10은 `[설계 가정]`으로만 쓰는 것이 맞다(`docs/EVAL.md:734`). |
| F11 거절 권고 대시보드의 측정 대상 | grok | 확인 | `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:641`; `docs/PRD.md:141` | 권고를 싣지 않으므로 그 비율은 Eval 밖이고 정적 결과 페이지만 둔다(`docs/EVAL.md:733`). |
| F12 루프 상한의 가정성 | grok | 확인 | `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:304`; `docs/ARCHITECTURE.md:196` | 요청 4·도구 8 및 요청 3·도구 6 대조가 `[설계 가정]`으로 실렸다(`docs/EVAL.md:174`). |
| F14 `span` 스케치 | claude·grok | 확인 | `DHChe/frontier-11-eval-claude:docs/research/eval-plan-proposal-claude.md:790`; `DHChe/frontier-11-eval-grok:docs/research/eval-plan-proposal-grok.md:539`; `docs/ARCHITECTURE.md:204` | `span`을 뺀 스케치와 ADR-0036이 일치한다(`docs/EVAL.md:638`). |
| F15 분포 일부만 실측한 비율 | 코디네이터(레인 안의 일부 실측안) | 확인 | `DHChe/frontier-11-eval-codex:docs/research/eval-plan-proposal-codex.md:241`; `docs/research/eval-plan-comparison.md:148` | 첫 실측 전건 원칙을 지지한다(`docs/EVAL.md:310`). |

## 확인한 범위

- `git diff 958862d..706ca9e`의 14개 변경 파일: `docs/EVAL.md` §0~§15, ADR-0032~0036, PRD S3·S4·S10·S12와 #11 행, ARCHITECTURE의 요청된 줄, ADR-0010·0014·0016·0020, CONTEXT §4, AGENTS 인용 절을 읽었다. 기준 결정의 A·G·U·C와 D1~D15를 해당 절에 대조했다(`docs/research/eval-plan-comparison.md:44-190`, `docs/research/eval-plan-lane-brief.md:24-46`, `docs/EVAL.md:7`).
- 반증 수집은 저장소 루트에서 ADR-0011~0031의 `**반증 조건.**` 뒤 번호 행만 추출하고, ADR-0016의 번호 없는 한 문장을 1로 세어 확인했다. 결과는 **82+1=83**이며 ADR별 개수는 EVAL §3의 열거와 같았다(`docs/EVAL.md:93-95`). EVAL 표의 첫 열을 정규식 `^\| (00[0-9]{2}-(숫자|R1~R4|결정7)|PRD-[12]) \|` 형태로 다시 모아 **90개 고유 행**을 얻었다. 집합 차이는 0개였다: 83 + ADR-0010 R1~R4 4 + ADR-0020 결정 7 1 + PRD 논증 반증 2 = 90(`docs/EVAL.md:91-97`, `docs/EVAL.md:134-137`, `docs/EVAL.md:174`, `docs/EVAL.md:222-223`).
- 포인터는 중요한 결정·숫자·인용을 여러 절에서 고르는 **층별 목적 표본 40개**를 해당 원문 줄과 대조했다. 표본: `docs/agents/harness.md:73,156,173,186,274,289`(6), `docs/ARCHITECTURE.md:151,196,204,519,520,567`(6), `docs/company/travel-policy.md:65,73,116,129,319`(5), `docs/company/travel-procedure.md:27,33,61`(3), `docs/company.md:33,34`(2), `docs/company/org.md:53,82`(2), `docs/design/receipt-pipeline.md:2502,2503,2505,3013,3028,3030,3031,3071`(8), `docs/adr/0008-extraction-uncertainty-is-first-class.md:42`(1), `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:37`(1), `docs/adr/0016-record-and-replay-model-calls.md:31,56,65,66`(4), `docs/research/ax-competitive-landscape.md:207`(1), `docs/research/request-vs-expense-comparison.md:27`(1). 이 중 주장과 맞지 않은 포인터는 D5의 1개이고, 주어를 자른 인용은 D6이다.
- EVAL §9-4의 590,000원 계산은 `TRV-6-2`의 합계 비교와 부장·`나` 등급 200,000원 상한에 맞는다(`docs/EVAL.md:485-493`, `docs/company/travel-policy.md:116-129`). 새 합격 수치 중 근거가 없는 24건·40장·k=10·10종×3건·요청 4/도구 8·N=3 등은 `[설계 가정]`으로 표기되어 있다(`docs/EVAL.md:292-305`, `docs/EVAL.md:366`, `docs/EVAL.md:418`, `docs/EVAL.md:503`, `docs/EVAL.md:575`, `docs/EVAL.md:617`).
- 세 레인 원문은 `git show`로만 읽었다. 다른 #11 검수자의 문서는 읽지 않았고, 대상 파일은 고치지 않았다.
