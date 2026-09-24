# #11 검수 반영 재확인 — codex

- **검수일**: 2026-09-25
- **대상 HEAD**: `7d3fa24` (`706ca9e..7d3fa24`)
- **범위**: codex·grok 독립 검수의 지적 22건, 반영 diff의 8개 파일, U1~U5·C1~C18·D1~D15와 관련 원문. 판정의 줄 번호는 `7d3fa24`의 파일 기준이다.

## 요약

**병합 보류.** 22건 중 해소 15건, 타당하게 다르게 해소 2건, 부분 5건, 미해소 0건이며, 반영 과정에서 새 결함 2건을 찾았다. 특히 S16의 0건·27쌍 선언은 C11의 종류마다 3건과 충돌하고, 둘째 분포 세계의 재생·비용 계산은 세계 격리와 이어지는 방법이 빠졌다.

## 지적별 판정

| 검수자 | ID | 요지 | 판정 | 근거(path:line) |
| --- | --- | --- | --- | --- |
| codex | D1 | H9·H10을 함정 합격으로 묶음 | 해소 | `docs/EVAL.md:81`, `docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:40-42`, `docs/adr/0034-two-synthetic-sets-distribution-refutes-only.md:85`가 하드 H와 비율 H·R을 갈라 적는다. |
| codex | D2 | 첫 실측 전 없는 기록으로 재생 요구 | 해소 | `docs/EVAL.md:49`, `:61`, `:534`와 `docs/adr/0035-live-model-runs-only-on-user-approval.md:26-27`이 가짜 응답 시험과 `시드 전·미측정`을 명시한다. `docs/adr/0016-record-and-replay-model-calls.md:31-32`의 `REPLAY_MISS`·시드 모드도 성공한 재생으로 바꾸지 않았다. |
| codex | D3 | U2에 두 벌 동시 문턱 추가 | 해소 | `docs/EVAL.md:615`, `:625-626`, `:222`는 판정 벌 하나만 세고 둘째는 참고로 둔다. 원문 조건은 `docs/research/eval-plan-comparison.md:159`와 같다. |
| codex | D4 | 분포 전체를 한 세계에 둔 이유 불명 | 다르게 해소(타당) | `docs/EVAL.md:315`는 한 분기 전체를 시나리오 하나, 출장 24건을 그 안의 사건으로 정의한다. 이는 `docs/ARCHITECTURE.md:567`와 `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:31-32`의 시나리오당 세계 하나에 맞는다. 둘째 벌의 실행 문제는 아래 새 결함 2다. |
| codex | D5 | 거래 한도 대조의 근거 포인터 과장 | 해소 | `docs/EVAL.md:410`과 `docs/PRD.md:166`이 금액 한도 대조를 원문 사실이 아닌 `[설계 가정]` 해석이라고 표시한다. 원문 `docs/research/ax-competitive-landscape.md:207`은 거래를 규정으로 평가한다는 말까지만 한다. |
| codex | D6 | 자기보고 신뢰도 인용의 주어 절단 | 해소 | `docs/adr/0032-pass-judged-by-deterministic-checks-and-human-sample.md:11`은 따옴표를 빼고 주어를 포함해 간접 서술한다. 원문 주어는 `docs/adr/0008-extraction-uncertainty-is-first-class.md:39-42`다. |
| codex | R1 | T-LIMIT 포함 코드 수 명시 | 해소 | `docs/EVAL.md:322`, `:346`에 15종 뼈대 + T-LIMIT 1종, 합 16종이라고 적었다. |
| codex | R2 | 이름 없는 출장자의 안정된 식별자 | 해소 | `docs/EVAL.md:298`은 첫 step 입력에 합성 사람 ID·소속·직급·역할을 고정하고 S11 감사 칸을 채우게 한다. |
| codex | R3 | S16의 두 기준선 동작을 모두 통과하는 쌍만 놓침으로 셈 | 부분 | `docs/EVAL.md:418`은 거래·합계·승인액과 두 동작을 모두 요구한다. 그러나 `:426`은 거래 한도 자체가 규정에 없는 상황에서 0건으로 확정하고 `docs/research/eval-plan-comparison.md:183`의 3건 결정을 어긴다. 새 결함 1. |
| codex | R4 | 첫 step 시나리오 입력의 소유자·파일 | 부분 | `docs/EVAL.md:469`, `:472`가 첫 step 소유와 `eval/scenarios/` 경로·잠금 순서를 정했다. 다만 입력 파일명·필수 칸·스키마는 없어 `:471`의 스키마 AC가 어느 입력을 검증할지 아직 모호하다. |
| codex | R5 | 조항 바깥 스코프 위험을 사람 표본에 연결 | 해소 | `docs/EVAL.md:633`이 조항 바깥 머리말을 남는 위험으로 적고 정답 목록·사람 표본에 연결한다(`:601-603`). |
| codex | N1 | “하나 는” 띄어쓰기 | 다르게 해소(타당) | `docs/EVAL.md:272`는 “같은 화면의 선택지가 하나 느는 것은”으로 고쳤다. 이 문맥의 동사는 ‘늘다’이므로 ‘하나는’보다 뜻이 정확하다. |
| codex | N2 | S16 계획 수와 실제 수 구별 | 해소 | `docs/EVAL.md:85`는 계획 수와 첫 step의 실제 확정을 구별한다. 계획값 27 자체의 C11 충돌은 새 결함 1로 별도 판정한다(`:418`). |
| grok | D1 | U2의 두 벌 동시 문턱 | 해소 | `docs/EVAL.md:625-626`과 `:222`는 끝4 인쇄 6장 중 1장인 벌에서 U2를 한 번 판정하고 다른 벌은 민감도로만 공개한다. `docs/research/eval-plan-comparison.md:159`, `:161`의 U2·U4를 추가 동시 조건 없이 읽었다. |
| grok | D2 | H 전체 함정 합격과 “S12 미통과” | 해소 | `docs/adr/0010-human-routing-bounded-by-structure-measured-by-ratio.md:40-42`가 H1~H8·H11만 함정 결함, H9·H10·R1~R4는 분포의 `가정 반증`으로 분리하고 “S12 미통과”를 뺐다. `docs/EVAL.md:81`도 같다. |
| grok | D3 | S16 합계 초과 0건과 제품 기대의 규정 불일치 | 부분 | `docs/EVAL.md:424`는 §9-4의 합계 계산에 맞게 제품 기대를 고쳤고 `:418`은 불가능한 쌍을 변경 장부 대신 차이 목록에 적게 했다. 다만 `:426`의 0건 확정은 거래 단위 한도가 없는 `docs/company/travel-policy.md:116`, `:125`로는 증명되지 않으며 C11(`docs/research/eval-plan-comparison.md:183`)과 충돌한다. 새 결함 1. |
| grok | R1 | 첫 step 입력 파일의 위치·칸·작성 step | 부분 | `docs/EVAL.md:469-472`는 작성 step과 디렉터리·순서를 정했지만, 입력 파일명과 출장·거래·증빙·세계 시계 등의 필수 칸을 정하지 않았다. `:471`의 스키마 AC도 대상이 불명확하다. |
| grok | R2 | 둘째 카드 전표 벌의 실행 세계 | 부분 | `docs/EVAL.md:315`, `:360`은 `dist/2026Q4-half`를 새 세계라고 지정했다. 하지만 같은 호출을 이전 세계의 기록으로 재생하는 방법과 `docs/EVAL.md:561`의 추가 비용 범위가 `docs/ARCHITECTURE.md:84`, `:567`의 격리와 맞게 정의되지 않았다. 새 결함 2. |
| grok | N1 | ADR-0035의 기각 표 포인터 | 해소 | `docs/adr/0035-live-model-runs-only-on-user-approval.md:50`이 기각 표를 `docs/adr/0016-record-and-replay-model-calls.md:52-56`으로 가리킨다. 남은 `:16`은 표가 아니라 그 논의의 맥락 포인터다. |
| grok | N2 | 정답 파일 이름 | 해소 | `docs/EVAL.md:450`, `:454-455`가 `scenario_id`별 JSON 경로와 분포 두 ID를 예시로 지정한다. |
| grok | N3 | 한 분기가 평가 시나리오 하나임을 명시 | 해소 | `docs/EVAL.md:315`가 분기 하나 = 시나리오 하나 = 세계 하나라고 적고, 출장 24건은 그 안의 사건으로 둔다. `docs/ARCHITECTURE.md:567`와 맞는다. |
| grok | N4 | 결함 B 인용에서 굵은 표시 누락 | 해소 | `docs/adr/0036-hold-answer-quotes-whole-clause.md:14`가 `"**안 잡힌다** — 스코프·주어를 보는 판단이 필요하다"`로 바뀌었다. #11의 “#15에서 관찰된 실패 하나” 댓글 표의 연속 부분문자열과 대조했다. |

## 새 결함

### 1. S16의 거래 한도 전제와 27쌍이 C11에 어긋난다

- **위치**: `docs/EVAL.md:85`, `:335`, `:346`, `:418`, `:424-426`; `docs/PRD.md:166`.
- **문제·근거**: C11은 열 종류 **각 3건**을 정했다(`docs/research/eval-plan-comparison.md:183`). 반영본은 한 종류를 0건으로 만들고 총 27쌍으로 바꾸었다. `TRV-6-2`는 1박 상한에 **지급 대상 밤의 수**를 곱해 **실비 합계**와 비교하며, “밤마다 따로 비교하지 않는다”(`docs/company/travel-policy.md:116`, `:125`). 따라서 매 밤의 금액이 1박 상한 이내라면 그 밤들의 합계가 한도 이내라는 조건부 계산은 맞지만, 규정에 **밤별 거래 금액 한도**는 없다. 다른 항목도 일비는 업무일 정액(`:89-108`), 교통비는 좌석 등급·실비(`:166-210`), 등록비는 사전승인 참가 요금 실비(`:212-216`)여서 거래별 **금액** 상한을 정의하지 않는다. `:424`의 “거래 한도 초과” 역시 가정한 기준선과 규정상 숙박 초과를 혼동하기 쉽다. `docs/research/ax-competitive-landscape.md:207`은 금액 한도 대조 자체를 말하지 않으므로 `[설계 가정]` 표기는 정직하지만, `docs/PRD.md:166`의 “문서로 확인된 가장 강한 동작”을 그 근거로 삼을 수는 없다.
- **고칠 안**: C11의 열 종류·각 3건을 설계 목표로 유지하고, 먼저 기준선의 **거래 단위**와 그 **가정한 한도**를 명시한다. 종류별 입력·기대값을 규정의 합계 판정과 대조해 3쌍이 가능한지 검증한다. 이 가정으로도 불가능하면 0건을 확정 선언하지 말고 C11과 충돌한다는 사실·계산·예시를 명시해 별도 결정을 받는다. 허수아비 점검(`docs/EVAL.md:435-444`)도 실제 규정 동작과 가정한 기준선 동작을 따로 검증한다.

### 2. 둘째 분포 세계의 재생 경로와 비용 범위가 빠졌다

- **위치**: `docs/EVAL.md:315`, `:360`, `:560-566`.
- **문제·근거**: 반영본은 `dist/2026Q4-half`를 새 세계에서 전부 다시 돌리면서 첫 벌과 같은 모델 호출은 재생하겠다고 단정한다(`docs/EVAL.md:360`). 하지만 업무 행·모델 호출 기록은 `world_id`로 격리되고(`docs/ARCHITECTURE.md:84`, `:567`; `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:25-32`), `replay`는 기록을 못 찾으면 실패한다(`docs/adr/0016-record-and-replay-model-calls.md:24-31`). 다른 세계의 기록을 직접 조회하면 격리 원칙에 걸리고, 새 세계 안에 기록이 없다면 같은 요청도 `REPLAY_MISS`다. 또 요청 해시는 메시지·이미지까지 포함하므로(`docs/adr/0016-record-and-replay-model-calls.md:25`), 세계별 메시지가 다르면 카드 외 호출도 새 요청일 수 있다. §10-2는 추가 비용을 “카드 전표 둘째 벌”만으로 제시해(`docs/EVAL.md:561`), 첫 승인 전 비용 추정이 낮아질 수 있다.
- **고칠 안**: 새 세계에 동일 요청의 재생 기록을 **세계 경계 안에서** 어떻게 시드하고 출처를 남길지 정한다. 시드가 없거나 요청 해시가 달라지는 호출은 승인 전 `REPLAY_MISS`로 세어 §10-2의 호출 지점별 비용에 더한다. U4의 R1 두 줄(`docs/research/eval-plan-comparison.md:161`)과 U1·C1의 첫 실측 전체 실행(`:158`, `:173`)은 유지한다.

## 권고·nit

- `docs/EVAL.md:469-472`: 첫 step 시나리오 입력의 파일명·필수 칸·스키마 AC를 한 표로 고정한다. 정답보다 먼저 입력을 커밋한다는 순서는 유지한다.
- `docs/EVAL.md:571`, `CONTEXT.md:448`: “코드만 바뀌면 매 커밋 재생”에 **첫 승인 실측 후**라는 시점을 같은 문장에 붙이면 `docs/EVAL.md:534`, `docs/adr/0035-live-model-runs-only-on-user-approval.md:27`을 보지 않아도 오해하지 않는다. 현재의 명시적 예외 때문에 D2는 해소로 판정했다.
- `docs/adr/0035-live-model-runs-only-on-user-approval.md:27`, `docs/EVAL.md:534`: “이때 나는”을 “이때 `REPLAY_MISS`는”으로 고치면 문서의 주어가 분명해진다.

## 확인한 범위

- 두 검수 원문은 `git show 431c991:docs/research/review-11-eval-codex.md`, `git show 5f235de:docs/research/review-11-eval-grok.md`로 읽었다. 반영 diff `706ca9e..7d3fa24`의 `CONTEXT.md`, `docs/EVAL.md`, `docs/PRD.md`, ADR-0010·0032·0034·0035·0036을 모두 대조했다. 브랜치는 바꾸지 않았다.
- 결정은 U1~U5·C1~C18(`docs/research/eval-plan-comparison.md:158-190`) 및 D1~D15(`docs/research/eval-plan-lane-brief.md:28-44`)와 비교했다. 특히 S16은 `docs/company/travel-policy.md:83-216`, U2는 `docs/EVAL.md:222`, `:611-627`, 세계·비용은 `docs/ARCHITECTURE.md:84`, `:567`, ADR-0013·0016·0035와 맞췄다. EVAL·ADR·PRD·ARCHITECTURE·CONTEXT 사이에서 위 두 건 외의 새 충돌은 찾지 못했다.
- 새 인용과 포인터 중 `docs/EVAL.md:410`, `:426`, `:482`, `docs/adr/0032-pass-judged-by-deterministic-checks-and-human-sample.md:11`, `docs/adr/0035-live-model-runs-only-on-user-approval.md:50`, `docs/adr/0036-hold-answer-quotes-whole-clause.md:14`를 원문과 대조했다. #11 댓글의 결함 B 표는 `gh issue view 11`로 읽었다. 이 표본에서 새로 잘린 주어·스코프 표지, 두 줄을 이은 직접 인용, 잘못된 줄 포인터는 찾지 못했다. 새 수치 27은 `[설계 가정]` 표기가 있지만 결정 C11과 충돌하며, 나머지 새 숫자 표기의 결함은 보이지 않았다.
- 문서 검수만 했다. 모델 API·유료 명령·제품 시험은 실행하지 않았고, 검수 대상 파일은 고치지 않았다.
