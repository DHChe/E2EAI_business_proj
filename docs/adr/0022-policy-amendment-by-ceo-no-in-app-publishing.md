# ADR-0022 — 규정 개정권자는 대표이사이고, 새 판은 저장소 개정과 부팅 적재로만 들어온다

- **상태**: Accepted
- **날짜**: 2026-09-22
- **맥락 티켓**: #10 (결정), #9 (ADR-0014 변경 주체), #16 (규정 3종), #20 (규정 문언의 후속)

## 맥락

[ADR-0014](0014-apv-9-3-exposed-declaratively.md)는 재무합의 설정값(`APV-9-3`)의 변경을 규정 새 판의 게시로만 하고, 변경 주체를 규정 개정권자로 두었다.
가상 회사에서 누가 그 권한을 갖는지(직책·게시 권한)는 #10에 넘겼다(`docs/adr/0014-apv-9-3-exposed-declaratively.md:29-30`).
`CONTEXT.md:67`은 "규정을 개정할 권한이 곧 이 설정을 바꿀 권한이 된다"고 적는다.
[ADR-0013](0013-postgres-object-storage-isolated-by-world-id.md)은 규정을 `(code, edition, sha256)`으로 적재하고 판 1만 적재한다(`docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:33-34`).

규정 3종 어디에도 개정권 조항이 없다(claude §7.2, 비교 문서 `:131`).

세 레인은 규정 개정의 최종 권한을 대표이사에 두고, 경영지원본부장 단독과 admin을 뺐다. 판 1 밖의 조합은 부팅이 실패한다는 것도 유지했다(A12).
갈린 것은 게시였다(비교 문서 D7). grok은 대표이사 단독 게시, codex는 대표이사 **승인** + 경영지원본부장 **게시**, claude는 앱 안에 게시 기능을 두지 않는 안이었다.
사용자가 U5로 "대표이사, 앱 안에 게시 기능 없음"을 골랐다. 코디네이터 추천과 같다(비교 문서 `:179`).

이 ADR에서 **비교 문서**는 `docs/research/agent-architecture-comparison.md`다. A1–A15는 그 문서 `:48-62`, U1–U6은 `:175-180`, C1–C9는 `:191-199`, D1–D9는 `:75-147`에 있다.
레인 인용(codex·grok·claude §N)은 비교 문서 §0(`:11-19`)이 가리키는 #10 제안서의 절이다.

## 결정

1. **규정 3종(`TRV`·`APV`·`PRC`)의 개정권자는 대표이사다**(U5, A12).
2. **경영지원본부장 단독과 admin은 개정권자가 아니다**(A12).
3. **앱 안에 게시·정책 편집 화면이 없다**(U5). 새 판은 저장소의 규정 문서(`docs/company/*.md`)를 개정해 판을 올리고, 부팅 때 `(code, edition, sha256)`으로 적재하는 것이다
   (`docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:33-34`, claude §7.2).
4. **세계마다 "판 적재" 이벤트를 남기고, 그 책임자는 대표이사다**(U5). 이야기 속의 게시는 대표이사의 행위이고, 시스템 속의 게시는 이 이벤트다(claude §7.2).
5. **판 1 밖의 `APV-9-3` 조합은 부팅이 실패한다.** [ADR-0014](0014-apv-9-3-exposed-declaratively.md) 결정 3(`docs/adr/0014-apv-9-3-exposed-declaratively.md:31-32`)을 그대로 둔다(A12).
6. **규정 문언에 개정권 조항을 넣는 일은 후속이다.** #20 방식 — 규정 + 기계 판독 블록 + `CONTEXT.md`를 함께 고치는 방식 — 으로 반영한다(비교 문서 `:187`).

## 근거

**왜 대표이사인가.** 전결은 대표이사가 하위 직책자에게 사전에 규범으로 결재권을 위임하는 것이다(`CONTEXT.md:49`).
전결표(`APV`)를 고치는 것은 그 위임 자체를 고치는 것이므로, 위임한 자리에 두는 것이 가장 짧은 해석이다. `TRV`·`PRC`는 같은 회사 규정 체계라 같이 둔다(claude §7.2).

**왜 경영지원본부장이 아닌가.** 세 레인이 같은 이유를 댔다 — 고액 전결권자가 자기가 결재하는 문서에 걸리는 검사(`APV-9-3`)를 정하게 된다(비교 문서 `:130`).
경영지원본부장은 고액 전결권자이고(`docs/company/org.md:60`), 재무팀이 그 본부 아래 있다(`docs/company/org.md:10-13`). 내부감사를 그 본부 밖에 둔 이유와 같은 논리다(`docs/company/org.md:26-27`).

**왜 admin이 아닌가.** admin은 `재무합의` 설정값을 바꿀 수 없다(`docs/adr/0002-admin-read-only-audit-axis.md:27`).

**왜 앱 안 게시가 없는가.** 앱 안에 정책 편집기를 두면 원본이 둘이 된다. 규정 3종이 유일한 원본이고 별도 정책 데이터 파일을 만들지 않는다([ADR-0005](0005-policy-source-of-truth.md), `docs/adr/0005-policy-source-of-truth.md:30-32`).
이 MVP는 판 1만 적재하므로(`docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:34`) 게시를 운영 명령으로 만들 수요도 없다 `[유도]`.

| 기각한 대안 | 기각 이유 |
| --- | --- |
| 대표이사 **승인** + 경영지원본부장 **게시**(권한 분리)(codex §7.1) | U5가 앱 안 게시를 두지 않으므로 게시 실행이라는 운영 명령이 따로 없다. codex도 두 사람 절차가 작은 데모에는 무겁다고 적었다(codex §9 "규정 개정 권한") |
| 대표이사 단독, 게시 명령 `publish_edition`(grok §8.2) | 개정권자는 같다. 앱 안의 게시 명령을 두지 않는다는 점만 다르다(U5) |
| 경영지원본부장(claude §7.2, grok §10.1) | 고액 전결권자가 자기 검사를 정한다(위 근거) |
| admin 게시(grok §9 ADR-0022 후보, claude §8 ADR-0023 후보) | [ADR-0002](0002-admin-read-only-audit-axis.md)와 충돌한다 |
| 앱 안의 정책 편집기·런타임 토글(claude §8 ADR-0023 후보, grok §9 ADR-0022 후보, `docs/adr/0014-apv-9-3-exposed-declaratively.md:66-67`) | 원본이 둘이 된다. ADR-0005와 충돌한다 |
| 이사회(claude §9 Q4 c) | 무대 밖이다(claude §9 Q4) |

## 결과

- **반증 조건.** 아래 중 하나가 관측되면 이 결정은 틀렸다.
  1. #11이 한 세계 안에서 판 전환을 요구한다(claude §8 ADR-0023 후보, `docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:84`). 그때는 옛 판의 자리와 판 적재의 운영 명령을 다시 본다.
  2. 사용자가 가상 회사에서 규정 개정을 이사회나 경영지원본부의 몫으로 둔다(claude §8 ADR-0023 후보, grok §8.2 끝).
  3. 대표이사가 자기 전결 범위를 판 개정으로 넓히는 시연이 제품의 결함이 된다(grok §8.2 끝).
  4. 개정마다 대표이사를 거치는 것이 데모 범위를 넘는 운영 병목이 되고, 사용자가 본부장에게 위임하는 편을 원한다(codex §7.1 반증 조건).
- 대표이사는 이름 있는 등장인물이 아니다(`docs/company/org.md:48-61`). 판 적재 이벤트의 책임자를 적으려면 세계에 직책만 가진 대표이사 사람 행이 필요하다 `[설계 가정]`(claude §7.2).
- 규정 문언 반영은 #20 방식의 후속이다(결정 6). 그 전까지 이 ADR이 개정권의 유일한 기록이다.
- 기존 결정과의 관계.
  - [ADR-0014](0014-apv-9-3-exposed-declaratively.md) 결정 2의 빈칸(`docs/adr/0014-apv-9-3-exposed-declaratively.md:30`)을 이 ADR이 채운다. "새 판의 게시"는 이 ADR의 결정 3·4로 읽는다.
  - [ADR-0001](0001-approval-semantics-per-term.md)·[ADR-0005](0005-policy-source-of-truth.md)의 #23 정정이 "개정권자의 직책은 #10에 남는다"고 적은 자리(`docs/adr/0001-approval-semantics-per-term.md:36`, `docs/adr/0005-policy-source-of-truth.md:164`)를 닫는다.
  - [ADR-0013](0013-postgres-object-storage-isolated-by-world-id.md): 같은 `(code, edition)`에 해시가 다르면 부팅이 실패한다(`docs/adr/0013-postgres-object-storage-isolated-by-world-id.md:33-34`). 판 적재 이벤트는 그 적재의 감사 기록이다.
  - [ADR-0019](0019-non-approval-owner-is-assigned-operations-person.md): 판 적재는 문서에 속하지 않는 시스템 조작이고, 그 책임자는 운영 담당자가 아니라 개정권자인 대표이사다.
