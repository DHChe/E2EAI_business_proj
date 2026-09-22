# #9 기술 스택 — 3레인 통합 비교와 결정 기록

- **날짜**: 2026-09-22
- **맥락 티켓**: #9 (기술 스택 결정)
- **상태**: 결정 완료 — [ADR-0011](../adr/0011-messages-api-direct-waits-are-document-state.md) ~ [ADR-0017](../adr/0017-public-demo-single-vm-replay-default-capped-live.md)

이 문서는 세 레인의 독립 제안을 한 자리에 놓고, 무엇이 합의였고 무엇이 갈렸으며 누가 어떻게 정했는지를 남긴다.
여기의 번호(A·B·U·C)는 ADR 본문이 그대로 인용한다.

## 0. 방법

1. **세 레인 독립 제안.** codex·grok·claude 세 모델이 같은 과제를 서로 읽지 않고 풀었다. 셋 다 develop `5adc6c3`에서 갈라졌다.

   | 레인 | 커밋 | 분량 | 원문 |
   | --- | --- | --- | --- |
   | codex | `9f3134f` | 273줄 | [`DHChe/frontier-9-stack-codex`](https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-codex/docs/research/tech-stack-proposal-codex.md) |
   | grok | `9e36d10` | 436줄 | [`DHChe/frontier-9-stack-grok`](https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-grok/docs/research/tech-stack-proposal-grok.md) |
   | claude | `2a08a98` | 519줄 | [`DHChe/frontier-9-stack-claude`](https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-claude/docs/research/tech-stack-proposal-claude.md) |

   원문은 develop에 병합하지 않고 위 브랜치로만 보존한다(U8). 이 문서와 ADR은 원문을 "codex §3.2"처럼 절 번호로 가리킨다.
2. **쟁점 사실의 교차 검증.** 레인이 내세운 사실 가운데 결정을 가를 수 있는 9건을 **저자와 다른 모델**이 원문·1차 출처와 대조했다(§6, 예외 두 건은 거기에 적었다).
3. **결정.** 세 레인이 독립으로 같은 답을 낸 14건은 합의로 받았다(§2). 갈린 자리 가운데 되돌리기 어려운 8건은 사용자가 골랐고(§4),
   되돌리기 쉽거나 다른 티켓으로 넘길 6건은 코디네이터가 정해 사용자에게 알렸다(§5, 이의 없음).

출처 표기: **합의** = 세 레인이 서로 읽지 않고 같은 답. **사용자** = 사용자가 고름. **코디네이터** = 코디네이터가 정하고 사용자에게 알림.

## 1. 결정과 ADR

| ADR | 제목 | 담은 결정 |
| --- | --- | --- |
| [0011](../adr/0011-messages-api-direct-waits-are-document-state.md) | Claude 호출은 Messages API 직접이고, 사람 대기는 문서 상태이며, 내구 실행 계층을 두지 않는다 | A1·A2·A3·C2·C4·C6 |
| [0012](../adr/0012-transition-audit-provenance-in-one-transaction.md) | 상태 전이·감사·필드 출처는 업무 DB의 한 트랜잭션에 있고, 책임자는 사람이다 | A4·A5·C3·C5 |
| [0013](../adr/0013-postgres-object-storage-isolated-by-world-id.md) | 저장은 PostgreSQL + 비공개 객체 저장소이고, 격리는 `world_id`다 | U1·A7·A9·A10·A13 |
| [0014](../adr/0014-apv-9-3-exposed-declaratively.md) | 재무합의 설정값(`APV-9-3`)은 선언형으로 노출한다 | U4·A8 |
| [0015](../adr/0015-typescript-web-stage-sse-no-unverified-answer-text.md) | 웹은 TypeScript 단일 언어이고, 진행은 단계 이벤트 SSE로 보내며, 검증 전 답변 문장은 화면에 내보내지 않는다 | A6·A11·U7·C1 |
| [0016](../adr/0016-record-and-replay-model-calls.md) | 모델 호출을 기록하고 재생한다 | U3 |
| [0017](../adr/0017-public-demo-single-vm-replay-default-capped-live.md) | 공개 시연은 단일 VM 위의 재생 기본 + 상한 있는 실시간 판독이다 | U2·U5·U6·A12, AGPL 회피 제약(사실 검증 5) |

A14(#4 빈 셀 23행)는 ADR이 아니라 이 문서와 #4 정오표로 남는다. U8(산출물 보존)은 이 문서의 형태 자체다.

## 2. 합의 — 세 레인이 독립으로 같은 답에 닿은 것 (14)

| # | 합의 | codex | grok | claude |
| --- | --- | --- | --- | --- |
| A1 | 런타임 = Messages API 직접 호출(`@anthropic-ai/sdk`, 구조화 출력). Agent SDK·Tool Runner·Managed Agents 비채택 | §3.1 | §3.1 | §3.1 |
| A2 | 오케스트레이션 계층 없음(Temporal·Inngest·LangGraph). 자체 상태 기계 + DB `job` 테이블(lease·시도 횟수·멱등 key·fencing) | §3.2–3.3 | §3.1, §8 ADR-B | §3.3, §7 A |
| A3 | 사람 결재 대기 = 문서 상태(DB 행). 에이전트 프로세스가 대기를 붙들지 않음. 에이전트는 결재 행위(승인·동의·반려·보류)의 행위자가 되지 않음 | §1 | §3.1 | §1 |
| A4 | 감사 = 업무 DB append-only. 상태 전이·감사 이벤트·후속 작업·outbox를 한 트랜잭션. `actor_kind`/`actor_id` + 책임자(사람, NOT NULL). 결재 4행위의 행위자는 현재 단계 담당자인 사람, 자기 결재 거부. 행위자 식별자는 서버 세션에서(요청 본문에서 받지 않음). 앱 DB 계정은 감사 UPDATE/DELETE 불가(DBA까지 막는 불변 저장이라고는 주장하지 않음). 플랫폼 기록(OTel·세션 이벤트·워크플로 히스토리·checkpoint)은 감사 원장으로 탈락 — **탈락은 "플랫폼 기록을 감사 원장으로 쓸 때"에 한정** | §2 M, §5 | §5.3, §8 ADR-C | §5.3, §7 C |
| A5 | 필드 출처 = `(entity, field, revision)` 필드 버전 행의 3값 제약(에이전트 추출 / 사람 수기 확정 / 시스템 연동), 덮어쓰지 않고 새 행. 출처와 검증 수준은 다른 축. 계산값은 네 번째 출처가 아니라 계산 기록(입력 revision·계산기 버전·조항·달력 판·환율 근거) | §2, §5.1 | §5.3, §8 ADR-D | §5.3 |
| A6 | 웹 = TypeScript 단일 언어 · React(Vite) SPA · Node API · SSE(명령은 POST). SSE `id`는 영속 순번/cursor, 재접속은 snapshot + cursor, SSE가 막히면 폴링으로 내려감 | §4 | §4 | §4 |
| A7 | 정책 원본 = 규정 3종 Markdown(ADR-0005). DB에는 `(code, edition, sha256)`과 계산 기록만. 같은 `(code, edition)`인데 해시가 다르면 부팅 실패. 파생 JSON 커밋 금지 | §5.1 | §5.2, §8 ADR-E | §5.3, §7 G |
| A8 | `APV-9-3` 읽기 전용 표시, 변경은 새 판 게시로만, admin 토글 없음(엔진 동작은 U4로 확정) | §7 | §5.5 | §3.5 |
| A9 | 기한은 저장하지 않고 기준일·주입 시계·공휴일 달력·판으로 계산 | §5.1 | §5.2 | §5.3 |
| A10 | 증빙 원본 + 모델에 보낸 이미지(좌표계) 보존, 크롭은 저장하지 않고 재생성(ADR-0009) | §5.1 | §5.2 | §5.3 |
| A11 | receipt-pipeline의 TS 블록은 언어를 법적으로 구속하지 않지만 TS로 기운다(`docs/design/receipt-pipeline.md:6`) | §4 | §7 | §4.2 |
| A12 | 심사자 입구 = 공개 링크, 같은 구성을 로컬 compose로 재현 | §6 | §6 | §6 |
| A13 | 독립 재계산(S2·S3·S10): 입력을 전부 저장하고 평가기는 별도 경로. 제품 함수를 두 번 부르는 것은 독립이 아님 | §5.1 | §11 | §5.3 |
| A14 | #4 빈 셀은 **23행**이다(#1의 "15개"와 불일치). 정오표 뒤 #4 §6 표는 `docs/research/agent-runtime-candidates.md:976-998` | §8 | §9 | §8, §11 모순 1 |

## 3. 갈린 자리와 각 레인의 입장

| # | 쟁점 | codex | grok | claude | 어떻게 정했나 |
| --- | --- | --- | --- | --- | --- |
| B1 | 저장 엔진 | PostgreSQL + R2 객체 저장 | SQLite WAL(연결 하나) + 콘텐츠 주소 파일, 보통 SQL만(PG 이전 대비) | SQLite 세계(world)당 파일 — 방문자·평가 시나리오·하네스 AC가 시드 사본 | **U1** codex안(코디네이터 추천은 claude안) |
| B2 | 공개 링크의 API 키·실시간 실행 | 서버에 키(worker만), 합성 샘플 한정 live, 월 50,000원 상한 제안 | 공개 서버에 키 없음. 시드 + 기록 재생, live는 로컬만 | 서버에 키, 기본은 재생 + 프리셋 표본 live 버튼, 하루 상한 | **U2**·**U6** |
| B3 | 방문자 격리 | 방문자별 demo 공간 | 공유 시드 + 리셋 스크립트 | 방문자별 세계(파일 복사) | **U1** `world_id` |
| B4 | 재생의 대상 | 준비된 이전 추출을 명시 표시, 재생 JSON을 추출 완료로 치지 않음 | 진행 이벤트 행을 시계 맞춰 재전송 | 모델 호출 기록·재생(`request_hash`, 못 찾으면 실패) | **U3** claude안 |
| B5 | 보류 답변의 토큰 스트리밍 | 토큰은 임시 미리보기, 확정 단계만 주 표시 | 토큰을 진행 표시로 흘리고 규칙 검사 뒤 카드 고정 | 토큰 스트리밍 안 함 | **U7** claude안 |
| B6 | `APV-9-3` 엔진 동작 | 현재 판은 세 성질 변경·반려 끄기 미지원 | 엔진이 판의 세 불리언을 그대로 따름(장래 판 변경 허용) | 판 1의 조합만 실행, 다른 조합은 부팅 실패 | **U4** 선언형 |
| B7 | 추출·계산 이벤트의 책임자 | #10이 배정, 미배정 조작은 실행 전 차단 | 기안자로 고정(가정 4) | #10이 정함, NOT NULL만 강제 | **C3** #10으로 |
| B8 | 웹 서버·프로세스 | Fastify, API와 PDF worker 분리 | Hono, 한 프로세스 | Hono, 한 프로세스(워커 분리는 반증 시) | **C1** Hono, **C2** 워커는 별도 서비스 |
| B9 | 동시 LLM 작업 상한 `[설계 가정]` | 2 | 4 | 설정값 | **C2** 설정값, 초기 2 |
| B10 | 배포 기반 | 단일 Linux VM + Compose(§6) | 공개 인스턴스 — Node 장기 프로세스 하나 + 로컬 디스크, 업체·기반은 적지 않음(§6.1, §9.1) | PaaS 컨테이너 한 대, Fly.io 예시(§6.1) | **U5** 단일 VM + compose |
| B11 | 재량 관문(`gate=on`) 중 반려 | 승인·동의에 걸되 반려를 막지 않음(§7) | 승인·동의는 거절, 반려·보류는 받음(§2 가정 5) | 다루지 않음 | **C5** 반려·보류 허용 |

## 4. 사용자 결정 (8)

| ID | 쟁점 | 결정 | 기각한 대안 | 비고 · ADR |
| --- | --- | --- | --- | --- |
| **U1** ⚠ | 저장 엔진 | **PostgreSQL(업무·감사·작업·outbox) + 비공개 객체 저장소 Cloudflare R2(증빙 바이트).** 방문자·평가 시나리오 격리는 `world_id`(codex안) | SQLite 세계당 파일(claude, **코디네이터 추천이었음**), SQLite 단일 파일 + 리셋(grok) | **⚠ 코디네이터 추천과 다르게 골랐다.** 기록할 이유: 운영 규모로 보이는 저장, 워커를 별도 프로세스로 떼기 쉬움. 받아들인 대가: 쿼리마다 격리 조건, 운영 부담·월 비용, 하네스 AC에 PG 인스턴스 필요. 객체-DB 분산 트랜잭션 없음: 임시 업로드 → hash·크기 확인 → DB 첨부 커밋(codex §5.1). [ADR-0013](../adr/0013-postgres-object-storage-isolated-by-world-id.md) |
| U2 | 공개 링크 실행 | **재생 기본 + 제한 live.** 첫 화면은 "기록된 실행"(배지). 미리 고른 합성 표본에만 [실시간 판독]. API 키는 서버 환경변수 1개, 워커만 사용, 브라우저·번들·감사 본문에 없음. 임의 업로드·자유 대화 없음 | 키 없는 재생 전용(grok), 로컬 전용(3레인 기각) | 준비된 기록과 live run을 화면·run 메타데이터에서 구분(codex §6.1). [ADR-0017](../adr/0017-public-demo-single-vm-replay-default-capped-live.md) |
| U3 | 재생 대상 | **모델 호출 기록·재생**(claude §5.5). `request_hash`(모델·시스템 프롬프트·메시지·이미지 sha256·출력 스키마의 정규화 해시). 모드 `live` / `replay`(못 찾으면 `REPLAY_MISS`로 실패) / `record-missing`. 재생에서도 검산·대사·결재선·감사는 실제 코드가 돈다 | 진행 이벤트 재전송(grok), 미리 만든 결과만 표시(codex 쪽) | 덤: API 키 없는 하네스 AC와 #11 회귀. 반증 조건은 해시 정규화. [ADR-0016](../adr/0016-record-and-replay-model-calls.md) |
| U4 | `APV-9-3` 엔진 동작 | **선언형.** 판 1의 세 값을 `(APV, 판, APV-9-3)` 인용으로 읽기 전용 표시. 변경은 새 판 게시로만. 엔진은 `{sequential: true, blocking: true, reject_always_allowed: true}`만 실행, 다른 조합은 `APV_9_3_UNSUPPORTED` 같은 이름 붙은 오류로 부팅 실패. 지원 조합 확장은 ADR + 코드 + 시험 | 실행형(grok) | 근거: 제외 3(`docs/PRD.md:131`), 주석 "반려 권한을 설정으로 끌 수 없다"(`docs/company/approval-matrix.md:228`). 약점: `CONTEXT.md:67`을 조작 가능한 설정으로 읽으면 절반만 지킴 — ADR에 선언형 읽기를 명시. 변경 주체 = 규정 개정권자, admin 아님. [ADR-0014](../adr/0014-apv-9-3-exposed-declaratively.md) |
| U5 | 배포 기반 | **단일 Linux VM + docker compose**: TLS 진입점 · app(Hono API + React 정적) · worker(모델 호출·PDF 래스터화) · postgres(볼륨 + 야간 백업) + R2 비공개 버킷. 로컬은 같은 compose, R2 대신 로컬 디렉터리 | PaaS 컨테이너 + 관리형 PostgreSQL(코디네이터 절충안) | 운영 주체는 사용자. 고가용성·무중단 주장 없음. VM 업체·가격·RAM `[미확인]`, 구매·배포 실행 아님. [ADR-0017](../adr/0017-public-demo-single-vm-replay-default-capped-live.md) |
| U6 | live 비용 상한 | **월 5,000원 + 방문자(세계)당 실시간 판독 3회.** 넘으면 버튼만 꺼지고 기록 열람·결재 클릭 유지, "예산 소진" 표시 | 월 2만·5만·3천·1천 원 | 추정: Sonnet 5 $2/$0.20/$10 per MTok(사실 검증 4), 영수증 1장 ≈ $0.03~0.044(claude §6.4, 실측 전), 1달러 ≈ 1,400원 가정 → 약 80~120장/월. 상한은 DB의 `usage × 단가`로 우리가 센다. 보수적 admission budget(codex §6.2). [ADR-0017](../adr/0017-public-demo-single-vm-replay-default-capped-live.md) |
| U7 | 보류 답변 진행 표시 | **토큰 스트리밍 안 함.** 단계(작성 중 → 인용·숫자 검사 중 → 완료)만 SSE로, 검사를 통과한 완성 문장만 표시 | 미리보기로 흘리고 검사 후 고정(grok·codex), 문장 단위 검사 후 흘림(코디네이터 절충안) | 근거: S4(`docs/PRD.md:154`), 제외 13(`docs/PRD.md:141`). R-a는 "단계 전이의 새로고침 없는 도착". [ADR-0015](../adr/0015-typescript-web-stage-sse-no-unverified-answer-text.md) |
| U8 | 산출물 보존 | develop에는 **ADR + 이 통합 비교 문서**만. 세 레인 제안서 원문은 origin의 `DHChe/frontier-9-stack-{codex,grok,claude}` 브랜치로 보존 | 제안서도 develop 병합, push 없이 로컬만 | 이 문서가 브랜치 원문으로 링크한다(§0) |

⚠ = 코디네이터 추천과 다른 선택.

## 5. 코디네이터 결정 (6, 사용자에게 알림, 이의 없음)

| ID | 결정 | ADR |
| --- | --- | --- |
| C1 | 웹 서버 = **Hono**(grok·claude, 2:1). Fastify는 동등한 대안(codex). 되돌리기 쉬워 ADR로 올리지 않고 웹 ADR의 한 줄로 | 0015 |
| C2 | 워커 = compose의 별도 서비스(U5 그림). 동시 LLM 작업 상한은 설정값, 초기 2 `[설계 가정]` | 0011 |
| C3 | 추출·계산 등 비결재 조작의 책임자 규칙은 **#10으로 넘김**(codex·claude). #9는 "책임자 NOT NULL·사람·배정되지 않은 조작은 실행 전 차단"만 스키마 계약으로. grok의 "기안자로 고정"은 #10 후보 | 0012 |
| C4 | Temporal 기각 논거 = 히스토리를 감사 원장으로 쓸 수 없음(R-e)과 상태의 이중화. **"90일 대기 상한"은 근거로 쓰지 않는다**(사실 검증 1) | 0011 |
| C5 | 재량 관문(`gate=on`)이 열린 동안 승인·동의는 거절, 반려·보류는 허용(codex·grok 일치, `APV-9-3` 항상 반려와 정합) | 0012 |
| C6 | #17이 정하지 않은 전이(반려·보류 이후, 재심 복귀, 타임아웃)는 리듀서가 이름 붙은 거부(예: `UNDEFINED_BY_17`)로 막는다(claude §3.4) | 0011 |

## 6. 사실 교차 검증 결과 (9)

1·7은 claude 검증자, 나머지는 codex 검증자가 맡았다. 확인일은 모두 2026-09-22다.
1·2·3·4·5·8·9는 검증자가 저자와 다른 모델이다. 6은 claude·codex가, 7은 세 레인이 함께 낸 주장이라 검증자와 같은 모델의 레인도 저자에 들어 있다.

| # | 주장(누구) | 판정 | 반영 |
| --- | --- | --- | --- |
| 1 | #4의 T-4가 Temporal Retention Period를 승인 대기 상한으로 오독했다(codex §3.2) | **맞음.** Retention은 closed Workflow Execution의 보존이다 — <https://docs.temporal.io/temporal-service/temporal-server#retention-period>. 열린 실행의 대기에는 상한이 되지 않는다. #4도 `docs/research/agent-runtime-candidates.md:592`에서 "대기 자체에 별도 타임아웃은 없고"라고 썼다. codex가 적은 앵커 `#what-is-a-retention-period`는 실제로 없고 `#retention-period`가 맞다 | #4 정오표(`docs/research/agent-runtime-candidates.md:937`). Temporal 기각 논거는 R-e로(C4). grok §3.3의 R-b 셀과 claude §5.2의 S3 R-b 셀에 같은 오독의 흔적이 있다(**부분**) |
| 2 | SQLite WAL-reset 버그가 3.7.0–3.51.2에 있고 3.51.3에서 고쳐졌다(grok §5.1) | **맞음**(보충). 3.44.6·3.50.7 백포트 예외가 있다 — <https://sqlite.org/wal.html#walreset> | U1로 SQLite를 쓰지 않으므로 기록만(ADR-0013) |
| 3 | 방향 분류기 가중치의 실물이 없다(claude §11 모순 5) | **부분.** 저자 측 HF `krutrim-ai-labs/ocr_rotation_bench`에 `weights.zip`(12-class 두 개)이 공개돼 있다. 4-class 체크포인트와 실행 코드의 공개는 확인 불가, 라이선스는 Krutrim Community License | 모순이 아니라 "설계 채택과 실행 자산 검증 사이의 공백" → #18 후속/#10(ADR-0015) |
| 4 | Sonnet 5 $2/$0.20/$10, Opus 5 $5/$25 per MTok(claude §6.4) | **맞음** — <https://platform.claude.com/docs/en/about-claude/pricing> | 비용 추정 유지, 실측 전(ADR-0017) |
| 5 | `mupdf`는 AGPL, `pdfjs-dist`는 Apache, Node 래스터화에는 canvas가 필요하다(claude §5.4) | **맞음.** `mupdf` 1.28.1 AGPL-3.0-or-later, `pdfjs-dist` 6.3.289 Apache-2.0, 공식 Node 경로는 `@napi-rs/canvas`. AGPL의 법적 결론은 검증 범위 밖 | 공개 링크이므로 AGPL 계열 회피를 **제약**으로 기록, 라이브러리 선택은 구현 phase(ADR-0017) |
| 6 | Managed Agents `user.tool_confirmation`에 사람 actor 칸이 없다(claude §8, codex §8) | **맞음**(문서 부재 수준). 입력 예시의 칸은 `type`·`tool_use_id`·`result`·`deny_message` — <https://platform.claude.com/docs/en/managed-agents/permission-policies> | 유지(ADR-0011·0012) |
| 7 | #4 §6 빈 셀은 23행이고, 빈 줄 하나가 표를 끊어 뒤 15행이 표 밖으로 떨어진다(3레인, claude §11 모순 1) | **맞음.** GFM 렌더러 두 개(marked 16.4.2, micromark 4.0.2 + gfm-table)에서 표 1개(8행) + 15줄 문단. "#1의 15 = 뒤 조각의 행 수"만 **확인 불가**(#4 종료 댓글은 17항목을 열거한다) | 빈 줄을 지워 표를 이었다(정오표). #1 문구는 목록으로만(§9) |
| 8 | Fly.io `shared-cpu-1x` 256MB 월 $2.02(claude §6.1) | **맞음**(지역별 상이) — <https://fly.io/docs/about/pricing/> | 월 $2.02는 사실이고 지역별로 다르다. 비채택 근거로 쓰지 않는다 — PaaS 안은 사용자가 고르지 않았다(ADR-0017) |
| 9 | Vercel 함수 최대 실행 300/800/1800초(베타), 스트리밍 포함(grok·claude §4.2) | **맞음**(Fluid compute의 Node.js/Bun/Python 기준) — <https://vercel.com/docs/functions/limitations#max-duration> | 비채택 근거로만(ADR-0015·0017) |

사실 검증 1의 추가 사항: Temporal Cloud에는 종료 히스토리를 객체 저장소로 내보내는 Workflow History Export가 있다(<https://docs.temporal.io/cloud/export>).
내보내면 보관되는 것은 사본이므로 "Temporal 히스토리를 원장으로 두는 안은 탈락"은 흔들리지 않지만, "보존 기간 때문에 감사가 불가능하다"는 표현은 이 경로를 빼고 말한 것이다.

## 7. 한 레인만 찾은 것

| 찾은 레인 | 발견 | 처리 |
| --- | --- | --- |
| codex | #4 T-4의 Temporal 보존 기간 오독 | 사실 검증 1 맞음 → 정오표, C4 |
| codex | 합성 시나리오 날짜를 규정 시행일 2026-10-01과 맞춰야 한다 | 후속(§8), ADR-0017 |
| codex | 객체-DB 분산 트랜잭션 없이 "임시 업로드 → 해시 확인 → 첨부 커밋" | U1에 채택, ADR-0013 |
| codex (grok도) | `ConfirmationEntry`에 책임자 칸이 없다 | 후속(§8), ADR-0012에 명시 |
| codex | SSE cursor를 순번 할당 순서가 아니라 outbox가 확정한 순서로 준다 | ADR-0015 근거에 반영 |
| grok | SQLite WAL-reset 버그(3.51.3 수정) | 사실 검증 2 맞음, 기록만 |
| grok | ADR-0002 결과 절 미갱신(`docs/adr/0002-admin-read-only-audit-axis.md:61-62`) | 문서 낡음 목록(§9) |
| grok (codex도) | 재량 관문 중 반려·보류 허용 | C5 |
| grok | #1 Not yet specified의 "사전승인·정산 차이 표현"이 #8로 이미 닫힘 | 문서 낡음 목록(§9) |
| claude | 방향 분류기 가중치 미공개 | 사실 검증 3 **부분** → 공백으로 재기술, #18 후속/#10 |
| claude | PDF 래스터화 `mupdf` AGPL vs `pdfjs-dist` Apache | 사실 검증 5 맞음 → AGPL 회피 제약 |
| claude | 판이 여럿 동시에 살아야 한다(`PRC-2-2`) vs 문서당 파일 하나 | 후속(§8), ADR-0013에 모순 표시 |
| claude | `docs/design/receipt-pipeline.md:2666`이 런타임 질문을 #4로 보냄(소관 오류) | 후속(§8), ADR-0015에 답 |
| claude | #4 §6 표 가운데의 빈 줄 하나가 표를 끊어 뒤 15행이 표 밖으로 떨어짐(정오표로 그 빈 줄을 지웠다) | 사실 검증 7 맞음 → 정오표 |
| claude | `ReconciliationOutcome`에 `후보 복수`·`짝 보류` 없음 | 후보(§8), ADR-0013 |
| claude | 증빙당 모델 비용 추정 ≈ $0.03–0.044(Sonnet 5) | U6의 근거, 실측 전 |

## 8. 후속

구현 phase·다른 티켓으로 넘긴다. #9는 이것들을 정하지 않았다.

- 하네스 AC와 #11 평가가 PostgreSQL 인스턴스를 어떻게 얻는가(compose 서비스, 테스트용 임시 DB 등) — 구현 phase. 세계 격리는 `world_id`(ADR-0013).
- 판이 여럿 동시에 살아야 함(`PRC-2-2`, `docs/company/travel-procedure.md:33`) vs 문서당 파일 하나 — MVP는 판 1만 적재, 옛 판의 자리는 ADR-0005 후속(claude §11 모순 6).
- `docs/design/receipt-pipeline.md:287-305`의 `ConfirmationEntry`에 책임자 칸이 없다 → 공통 감사 envelope의 필수 책임자로 보완(codex §12, grok §2 가정 3).
- `ReconciliationOutcome`(`docs/design/receipt-pipeline.md:835-839`)에 `후보 복수`·`짝 보류`가 없다 → 저장은 영속 상태로 받음(#18 후속, claude §11 모순 8).
- `docs/design/receipt-pipeline.md:2666`이 "방향 분류기를 어디서 돌리는가"를 #4로 보냈다 → 소관은 #9/#10(claude §11 모순 2). 답: 필요하면 `job` 한 종류의 Python 사이드카(ADR-0015). 실행 자산의 공백은 #18 후속/#10(사실 검증 3).
- 합성 시나리오의 업무 날짜를 규정 시행일 2026-10-01과 맞춘다(codex §6.1, ADR-0017).
- 추출·계산 등 비결재 조작의 책임자 규칙 — #10(C3). 규정 개정권자의 가상 회사 직책 — #10(ADR-0014).
- **확인 필요**: #8 확정 댓글 결과 9는 프로토타입의 반려 자리를 비활성 "#17 대기"로 두었다(<https://github.com/DHChe/E2EAI_business_proj/issues/8#issuecomment-5769586450>).
  C5는 관문 중 반려를 서버가 받는다고 정했다. ADR-0012는 두 문장을 층이 다른 것(서버 허용 vs 화면 표시)으로 읽었다 `[유도]`. 화면에서 반려를 언제 열지는 #8·#12·#17이 확인한다.

## 9. 기존 문서의 낡은 문장 (고치지 않고 목록으로만)

이 티켓은 아래 파일을 수정하지 않았다. #9 종료 보고에 목록으로 넘긴다.

| 위치 | 낡은 점 | 무엇이 닫았나 |
| --- | --- | --- |
| `CONTEXT.md:378`, `CONTEXT.md:406` | 정책 대조를 주의 신호로 칠지 "#8 미정"으로 남음 | #8 확정 댓글 결과 4 — 카드의 별도 구획(codex §12, grok §12-1) |
| `docs/adr/0005-policy-source-of-truth.md:169`, `docs/adr/0009-evidence-is-crop-plus-original-toggle.md:66` | 카드·화면 형태를 #9·#10으로 넘김 | `docs/PRD.md:172`는 #8(세 레인 모두) |
| `docs/adr/0002-admin-read-only-audit-axis.md:61-62` | 수기 확정의 사전 방어가 #18에 남았다고 적음 | ADR-0008이 백지 입력·재검산·사유 기록을 채택(grok §12-4) |
| #9 본문 갱신 1 | "에이전트가 기안·결재를 대신 올리는 순간"을 전제 | `CONTEXT.md:331`, `docs/PRD.md:141`이 거둠(codex §12, claude §1·§11). 인용은 claude §1이 #9 갱신 1에서 옮긴 문구 |
| #1 Not yet specified | "사전승인과 정산의 차이를 화면과 모델에서 어떻게 표현할지" | #8 `diff=all`로 닫힘(grok §12-6) |
| #1 Not yet specified | "런타임 후보의 빈 셀 15개" | 실제로는 23행(A14, 사실 검증 7) |

## 10. 원문

- codex: <https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-codex/docs/research/tech-stack-proposal-codex.md>
- grok: <https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-grok/docs/research/tech-stack-proposal-grok.md>
- claude: <https://github.com/DHChe/E2EAI_business_proj/blob/DHChe/frontier-9-stack-claude/docs/research/tech-stack-proposal-claude.md>
- #4 런타임 후보 조사(정오표 포함): [`docs/research/agent-runtime-candidates.md`](agent-runtime-candidates.md)
