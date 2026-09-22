# ADR-0016 — 모델 호출을 기록하고 재생한다

- **상태**: Accepted
- **날짜**: 2026-09-22
- **맥락 티켓**: #9 (결정), #11 (회귀·평가), #1 (공개 데모)

## 맥락

세 가지 압력이 한 자리에서 만난다.

- **공개 링크는 기본이 재생이다**([ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md)). 방문자마다 API를 부르면 키·비용·비결정성이 모두 공개 경로에 실린다.
- **하네스는 API 키를 사람만 풀 수 있는 `blocked` 사유로 둔다**(`docs/agents/harness.md:73`). AC는 셸에서 그대로 도는 커맨드여야 한다(`docs/agents/harness.md:96`).
  설계 문서도 실제 영수증으로 돌린 결과가 없는 이유를 `ANTHROPIC_API_KEY`가 없어서라고 적는다(`docs/design/receipt-pipeline.md:7`).
- **#11은 회귀를 재야 한다.** 프롬프트나 모델을 바꾸면 무엇이 바뀌었는지 드러나야 한다.

"재생"의 대상이 세 레인에서 갈렸다.

- grok: 과거에 로컬에서 남긴 **진행 이벤트 행**을 시계만 맞춰 다시 보낸다(grok §6.1).
- codex: "준비된 이전 추출"을 명확히 표시해 보여 주고, 재생 JSON을 추출 완료로 치지 않는다(codex §6.1).
- claude: **모델 호출**을 해시로 기록하고 재생한다. 나머지 코드는 지금 돈다(claude §5.5).

## 결정

1. **모든 모델 호출을 `model_call` 행으로 기록한다.** 열의 예시는 `request_hash`, `model`, 요청(이미지는 sha256 참조), 응답, `usage`, 시각, `job_id`다(claude §5.3).
2. **`request_hash`는 모델·시스템 프롬프트·메시지·이미지 sha256·출력 스키마를 정규화한 해시다.**
3. **실행 모드는 셋이다.**

   | 모드 | 동작 | 쓰는 곳 |
   | --- | --- | --- |
   | `live` | API를 부르고 기록한다 | 로컬 개발, 공개 데모의 [실시간 판독] |
   | `replay` | 해시로 기록을 찾아 돌려준다. **못 찾으면 `REPLAY_MISS`로 실패한다 — 몰래 live로 넘어가지 않는다** | 공개 데모 기본, 하네스 AC, #11 회귀 |
   | `record-missing` | 기록에 없는 것만 live로 부르고 기록한다 | 시드 만들기 |

4. **재생되는 것은 모델 응답뿐이다.** 재생 중에도 검산·대사·결재선·감사는 **실제 코드가 지금** 돈다.
5. 재생한 실행과 live 실행은 run 메타데이터에서 구분된다. 화면 표시는 [ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md)의 "기록된 실행" 배지다.

## 근거

**얻는 것은 셋이다**(claude §5.5).

1. **API 키 없이 시스템 전체가 돈다.** 모델 호출이 끼는 step도 재생으로 AC를 통과할 수 있다. 하네스의 `blocked` 사유 하나가 사라진다.
2. **바뀐 호출이 드러난다.** 프롬프트나 모델을 바꾸면 해시가 달라져 재생이 실패한다. 이것을 회귀로 쓸지는 #11이 정한다.
3. **데모가 결정적이다.** 같은 세계에서 같은 행동을 하면 같은 결과가 나온다.

**왜 모델 호출인가.** 재생의 경계를 모델 응답에 두면, 그 위의 모든 결정론 코드가 재생 중에도 **실제로** 검증된다.
공개 데모에서 심사자가 보는 검산·대사·결재선 계산과 감사 기록이 녹화본이 아니라 지금 돈 결과다.
[ADR-0011](0011-messages-api-direct-waits-are-document-state.md)의 복구 계약도 완성된 모델 응답을 다음 턴 전에 저장하라고 요구한다(codex §3.3). 같은 기록을 쓴다.

**왜 못 찾으면 실패하는가.** `replay`에서 조용히 live로 넘어가면 "기록된 실행"이라는 표시가 거짓이 되고, 공개 경로의 비용이 [ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md)의 상한 밖으로 샌다 `[유도]`.
하네스에서는 키가 없는 환경에서 AC가 우연히 네트워크를 타는 일이 생긴다 `[유도]`. 큰 소리로 실패해야 빠진 기록을 채운다(claude §5.5).

| 기각한 대안 | 기각 이유 |
| --- | --- |
| 진행 이벤트 행의 재전송(grok §6.1) | 재생되는 것이 파이프라인의 결과 이벤트라, 재생 중에 검산·대사 코드가 돌지 않는다. 키 없는 AC와 회귀의 재료가 되지 못한다 `[유도]` |
| 미리 만든 결과만 표시(codex §6.1 "준비된 이전 추출") | 같은 이유로 코드가 돌지 않는다. codex 스스로 "실제 추출은 준비된 구조화 JSON 재생으로 대체 완료 처리하지 않는다"고 적었다(codex §6.1) |
| 목(mock) 응답을 손으로 쓰는 안 | 실제 응답과 멀어진다(claude §7 ADR-F) |
| 매번 live | 키·비용·비결정성이 모든 경로에 실린다(claude §7 ADR-F) |
| `replay`에서 기록이 없으면 live로 대체 | 위 근거 |

## 결과

- **반증 조건.** 요청 해시가 비결정적이라 재생이 계속 빗나간다 — 예를 들어 같은 증빙인데 이미지 인코딩이 매번 달라 sha256이 바뀐다(claude §7 ADR-F).
  그러면 이 결정은 틀렸다. **해시 정규화가 이 ADR의 약한 고리다.**
  [ADR-0009](0009-evidence-is-crop-plus-original-toggle.md)의 pre-resize(`docs/adr/0009-evidence-is-crop-plus-original-toggle.md:27`)가 만든 이미지가 결정적이어야 한다 `[유도]`.
- 재생한 응답은 **기록 당시의 모델 응답**이다. 재생이 통과한다고 지금 모델의 품질이 입증되지는 않는다. 모델 선택과 품질 검증은 #11이다.
- 시드를 만들 때(`record-missing`)는 한 번 키가 필요하다. 그 기록은 [ADR-0013](0013-postgres-object-storage-isolated-by-world-id.md)의 PostgreSQL에 두고, 이미지는 sha256으로 객체 저장소를 가리킨다.
- 재생에서 나온 판독값의 출처 표기는 이 ADR이 새로 정하지 않는다. 출처는 3값뿐이고([ADR-0012](0012-transition-audit-provenance-in-one-transaction.md)), 재생 여부는 run 메타데이터가 가른다(결정 5).
- 감사 이벤트가 `model_call`을 참조하면(ADR-0012의 `model_call_id` 예시) 한 판독값에서 그 요청·응답까지 거슬러 갈 수 있다.
- 기존 결정과의 관계.
  - [ADR-0009](0009-evidence-is-crop-plus-original-toggle.md): 해시의 이미지 입력은 그 ADR의 pre-resize가 만든 이미지다(위 반증 조건).
  - [ADR-0011](0011-messages-api-direct-waits-are-document-state.md): 복구 계약이 요구하는 모델 응답 저장과 같은 기록을 쓴다.
  - [ADR-0012](0012-transition-audit-provenance-in-one-transaction.md): 출처 3값을 늘리지 않는다. [ADR-0013](0013-postgres-object-storage-isolated-by-world-id.md): 기록은 PostgreSQL, 이미지는 객체 저장소.
  - [ADR-0017](0017-public-demo-single-vm-replay-default-capped-live.md): 공개 링크의 재생 기본이 이 ADR의 `replay` 모드다.
