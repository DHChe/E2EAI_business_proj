# 영수증 파싱 파이프라인의 기법과 실패 모드

- 티켓: [#19](https://github.com/DHChe/E2EAI_business_proj/issues/19) (map: [#1](https://github.com/DHChe/E2EAI_business_proj/issues/1))
- 선행: [#18](https://github.com/DHChe/E2EAI_business_proj/issues/18) SlipScan 코드 조사 (재조사하지 않음)
- 조사일: 2026-09-20
- 성격: 문헌·공식문서 조사. **이미지를 넣어 실제로 돌려보지 않았다** — 실측은 #18의 버리는 코드 몫이다.

## 읽는 법

이 문서는 "재설계해야 한다"를 주장하지 않는다. 갈래마다 **어디서 깨지는지**를 적고,
깨지는 지점이 이 MVP의 판단(정책 원문 대조 + 적격증빙 대사)에 닿는지만 표시한다.

표기:
- **[1차]** 모델·API 공식 문서, 법령 원문, 논문 원문, 표준 문서, 공식 벤치마크 리포트.
- **[2차]** 블로그·벤더 마케팅·커뮤니티 벤치마크. 수치는 신뢰하지 않는다.
- **[유도]** 1차 자료에 공개된 알고리즘·수식을 이 문서에서 직접 계산한 값. 출처의 주장이 아니다.

---

## ① 입력 품질 — 전처리 항목마다 근거 등급이 다르다

"전처리"로 한 덩어리로 묶으면 근거 있는 것과 없는 것이 섞인다. 항목별로 갈라 둔다.

| 전처리 | 근거 | 판단 |
|---|---|---|
| **회전·방향 보정** | Seeing Straight(arXiv 2511.04161): Phi-3.5-Vision 인코더 기반 304M 4-class 분류기, ORB-En 96.81%·ORB-Indic 92.68%, 12-class 98%. 보정 후 다운스트림 OCR이 **폐쇄형 모델 최대 +14%p**, 오픈웨이트 최대 4배 개선. H100 지연 0.5초 [1차] | **넣는다** |
| 기하 보정(dewarping) | DocTr++(arXiv 2304.08796) CER 50.89%→16.95%는 **Tesseract v5.0.1 기준**. 같은 논문의 VLM 근거는 Qwen-VL 정성 사례 1건, 정량 수치 없음 [1차, 원문 대조] | **보류** — 자체 측정 선행 |
| 이진화·대비강화·노이즈 제거 | 전통 OCR 상식이 VLM에서 뒤집힌다는 1차 근거 [근거 없음] | **넣지 않는다** |
| JPEG 품질 임계값 | 동료검토 자료 [근거 없음]. 2차 튜토리얼 1건만 존재 | **측정 대상** |
| 긴 영수증 분할 겹침 비율 | 영수증·VLM 특화 기준 [근거 없음]. TrOCR 확장(arXiv 2212.05525)은 청크 분할이 CER 4.98%로 최적이라 보고하나 겹침 비율 미명시 | **추정치로 명시** |

방증: DocPTBench(arXiv 2511.18434)는 촬영 문서에서 MLLM end-to-end 정확도 평균 **-18%**, 전문 파싱 모델 **-25%** 하락을 보고한다 [1차]. 촬영 조건이 실재하는 비용임은 확인되지만, dewarping을 완화책으로 직접 비교하지는 않았다.

Claude 공식 문서는 **"Rotate pages to proper upright orientation"**을 권고하면서 방법을 주지 않았다. 이제 실행 수단이 생겼다.
부록 A.2가 긴 영수증 **분할의 필요성**을 확정했지만 **분할 방법**은 근거가 없다 — 이 구분을 흐리지 않는다.

→ **이 MVP의 전처리에서 근거 위에 서 있는 것은 회전 보정 하나다.** 나머지는 전부 측정 항목이다.

---

## ② 해외 로캘 — 모른다는 것이 연역되는 자리

### 숫자 구분자는 통화로 좁혀지지 않는다

EUR이 결정적 반례다. 독일·프랑스 `1.234,56` / 아일랜드·몰타 `1,234.56` — **같은 통화, 정반대 표기** [1차/2차].
CLDR은 로캘별 기호만 정의하고, ISO 80000-1 §7.2.2는 콤마·점 **둘 다 허용**하며 문서 내 일관성만 요구한다 [1차].
ECMA-402 `Intl.NumberFormat`도 구분자 문자를 CLDR에서 가져올 뿐 모호성을 해소하지 않는다 [1차].

**유일한 결정 규칙** — 구분자 뒤 자릿수가 3이 아니면 그 구분자는 소수점이다.

| 입력 | 판정 |
|---|---|
| `1,23` | 1.23 확정 |
| `12,3456` | 12.3456 확정 |
| **`1,234`** | **판별 불가** — 미국식 1234 / 유럽식 1.234, **1000배** 차이 |

이것이 이 문서 전체에서 유일하게 **모델 신뢰도도 검산도 없이 "모른다"가 연역되는** 자리다.
규칙이 모호성을 *증명*하므로 모델이 추측해서는 안 되고, 구조적으로 사람에게 간다.

### ISO 4217 minor unit exponent

| exponent | 통화 |
|---|---|
| **0** | JPY, KRW, VND, ISK, PYG, RWF, UGX, XAF, XOF, XPF |
| 2 | 대부분 |
| **3** | BHD, IQD, JOD, KWD, LYD, OMR, TND |

SlipScan의 `z.number().int()` + 프롬프트 `"금액은 원 단위 정수로 반환합니다"`는 **원화 전용 가정**이다.
exponent를 2로 하드코딩하면 원화는 **100배**, 쿠웨이트 디나르는 **1/10** 오차가 난다.

### 날짜

미국만 M/D/Y, 나머지 대부분 D/M/Y [2차]. 해소 단서는 셋뿐이다 — 월의 텍스트 표기(`Mar`), ISO 8601, 숫자 하나가 13 이상.
셋 다 없고 두 자리가 모두 12 이하면 (`03/04/2026`) **원천적으로 로캘 추정 불가**다.

### 검산 공식은 보편적이지 않다

④가 구조적 검산을 주 메커니즘으로 세우는데, 로캘이 그 공식을 흔든다.

| 로캘 | 사실 | 깨지는 가정 |
|---|---|---|
| 프랑스 | 1985년 법으로 `service compris` 의무 포함 [2차] | `총액 = subtotal + tax + tip` |
| EU 소액(100~250유로 이하, 회원국별 상이) | 간이 세금계산서 — 공급가액·세액 **분리 기재 의무 면제** [2차] | "세액 없음 = 하자" |
| 일본(2023.10~ 적격청구서) | 세율별(8%/10%) **구분 기재 의무**, 端數처리도 세율별 1회 [1차, 国税庁] | 단일 세액 필드 |
| 미국 | 연방 통일 서식 없음, 州별 sales tax 라인은 관행일 뿐 [2차] | 세액 위치·존재의 일관성 |

→ 검산은 **보편 공식이 아니라 로캘별 규칙 집합**이다.
규칙을 모르는 로캘에서는 **검산 실패**가 아니라 **검산 불가**로 갈라야 한다. 둘을 합치면 정상 영수증이 하자로 찍힌다.

### 手記 팁

미국식 카드 전표는 인쇄된 `Total` 위에 손으로 팁과 최종 `Total`을 덧쓴다 — 한 장에 **"Total"이 2~3번 서로 다른 값으로** 등장한다 [2차].
카드사가 실제 청구하는 것은 **手記 최종값**이므로, 인쇄값을 잡으면 카드내역 대사가 전부 틀어진다.
프랑스형(`service compris`)은 반대로 팁 란 자체가 없는 것이 정상이다.

비라틴 문자 영수증에 대한 VLM 성능: [근거 없음] — 영수증 특화 벤치마크 SROIE(영어)·CORD(인도네시아어)는 둘 다 라틴 문자다.

---

## ③ 한국 적격증빙 — 지면에서 무엇이 보이는가

법 조문(부가가치세법 §32①, §46③, 시행령 §73⑧, 소득세법 시행령 §211①)은 #18에 이미 확정돼 있다. 여기서는 **이미지에서 판별 가능한 단서**만 적는다.

| 유형 | 결정적 단서 | 근거 |
|---|---|---|
| 세금계산서 | **세액란 존재 + 숫자 기재** | [1차, §32①] |
| 계산서 | **세액란이 서식에 아예 없음**(공급가액만) | [1차, 소득세법 시행령 §211①] |
| 신용카드매출전표 | 공급가액·부가세액이 **별도 항목으로 구분 인쇄** — "합계금액"만 있으면 매입세액 공제 불가 | [1차, §46③·시행령 §73⑧] |
| 현금영수증 | **거래구분란의 `지출증빙` / `소득공제` 문자열** | [1차, 국세청] |
| 간이영수증(비적격) | 사업자등록번호·세액 구분 없는 자유양식 총액 | [2차] |

### 현금영수증의 게이트

법인·사업자가 경비 인정과 매입세액 공제를 받으려면 **반드시 `지출증빙`**이어야 하고, `소득공제`는 근로자 연말정산용이라 사업경비로 인정되지 않는다 [1차, 국세청].
**지면의 문자열 하나가 적격/비적격을 가른다.** 식별번호란도 보조 단서가 된다 — 지출증빙용은 사업자등록번호(`XXX-XX-XXXXX`), 소득공제용은 휴대전화·카드번호다 [2차].
소득공제용으로 오발급돼도 홈택스에서 사후 전환이 가능하지만 **원본 지면 문구는 바뀌지 않는다** [2차] — 즉 지면만 보고 최종 판정할 수 없는 경로가 존재한다.

### 사업자등록번호 체크섬 — 무엇을 보증하고 무엇을 보증하지 않는가

- 구조: `3자리(세무서코드)-2자리(과세유형)-5자리(일련4+검증1)`. 과세유형은 01~79 개인, 81~86 영리법인, 87~89 비영리, 90 국가 [2차].
- 알고리즘: `d1~d9`에 가중치 `[1,3,7,1,3,7,1,3,5]`를 곱해 합산한 뒤 `floor(d9 × 5 / 10)`을 더하고, `check = (10 - (합 mod 10)) mod 10`이 `d10`과 일치하면 유효.
- **국세청 공식 문서로 확인되지 않는다.** 독립 2차 출처 3곳이 동일하게 수렴하는 **업계 통용 비공식 표준**이다 [2차].
- 국세청의 공식 검증은 알고리즘 공개가 아니라 **실시간 진위확인 API**다 [1차, data.go.kr 15081808].

→ **체크섬 통과는 "OCR이 숫자를 잘못 읽지 않았다"까지만 말한다. "이 사업자가 실재한다"는 말하지 않는다.** 둘을 섞으면 ④의 보장이 무너진다.
체크섬은 OCR 오인식을 거르는 2차 필터이지 실재성 검증이 아니다.

**[#6](https://github.com/DHChe/E2EAI_business_proj/issues/6)과 맞물리는 지점**: 가상 회사의 사업자등록번호는 실재하지 않으므로 진위확인 API를 호출할 수 없다.
유효한 체크섬은 생성할 수 있고 API는 원천적으로 쓸 수 없다 — **MVP 경계가 임의 선택이 아니라 설정에서 자연히 그어진다.**

### 전자 vs 종이 세금계산서

전자세금계산서 승인번호는 24자리이고 `앞8(작성연월일)-중8(발급시스템코드: 10 홈택스·20 ARS·41 ASP·42 ERP·50 겸용서식·70 모바일·90 대리발급)-끝8(일련번호)` 구조다 [1차, 원문 직접 대조 실패·스니펫 기반].
다만 **"종이에는 이 형식의 승인번호가 없다"를 명시한 1차 자료는 확보하지 못했다** [근거 없음] — 논리적 추론일 뿐이므로 판정 규칙으로 쓰지 않는다.

### 적격증빙이 아닌 흔한 문서

거래명세서(세액 구분·등록번호 검증 체계 없음), 입금표(자금 이동만 증명, 공급내용·세액 부재), 간이영수증(자유양식), 해외 인보이스(국내 사업자등록번호 체계 적용 불가) [2차].

---

## ④ 불확실성 — 두 경로가 닫히고 하나가 남는다

이 MVP가 보장하기로 한 것은 **"틀렸다는 걸 아는 것"**이다. 그 수단은 셋이 후보였고, 둘이 닫혔다.

### 닫힌 경로 1 — logprobs (부재)

Claude Messages API 공식 문서 전량 검토 결과 `logprobs`·토큰 확률·likelihood 관련 **파라미터와 응답 필드가 전무**하다 [1차].
"토큰 확률로 추출 신뢰도를 추정한다"는 흔한 설계는 **이 스택에서 선택지가 아니라 부재**다.
ConfBench가 보고하는 "첫 토큰 log-prob 집계가 mean/margin보다 우수"도 Claude에는 적용 불가다.

### 닫힌 경로 2 — 자기보고 신뢰도 (단독 사용 금지)

| 근거 | 내용 |
|---|---|
| arXiv 2306.13063 (ICLR'24) | LLM은 verbalized confidence에서 **일관되게 과신**, 인간의 확신 표현 패턴 모방으로 추정 [1차] |
| arXiv 2604.01457 | 회로 수준 분석으로 과신 유발 메커니즘 확인 — **벤치마크 특이 현상이 아님** [1차] |
| arXiv 2410.09724 | **RLHF 학습 과정 자체**가 verbalized overconfidence를 유발 [1차] |
| arXiv 2608.01792 (ConfBench) | VLM 문서추출 특화, 20종 열화·1,346 변형·7만+ 엔티티. 모델별 보정 품질이 **"거의 완벽"부터 "심각한 과신"까지 극단적 편차** [1차] |

→ `confidence: 0.85` 같은 필드를 **단독 게이트로 쓸 수 없다.** 보조 신호로만 둔다.

### 남은 경로 — 구조적 검산

- arXiv 2606.24420 *"Beyond Logprobs: A Multi-Signal Confidence Engine for LLM-Based Document Field Extraction"* — logprob·자기보고 단독은 불충분하며 **필드 간 의미적 일치·교차검증을 포함한 multi-signal이 유의하게 우수**하다고 결론 [1차]. "검산이 자기보고보다 낫다"의 직접 근거.
- arXiv 2510.15727 (인보이스 추출 평가) — 세금·항목 합계 등 **수학적 검산 오류율이 방법론에 따라 5~20%**로 갈린다 [1차].

→ #18의 `공급가액 + 부가세액 = 합계` 검산은 곁가지가 아니라 **주 메커니즘**이다.
단 ②가 보였듯 **검산 공식은 로캘 의존**이므로, 규칙 없는 로캘에서는 "검산 불가"로 따로 표시한다.

### 선택적 다중 샘플링 (2순위)

- CISC(arXiv 2502.06233): 신뢰도 가중 다수결이 단순 self-consistency보다 우수, 동일 정확도에 **필요 샘플 수 40%+ 절감** [1차].
- ReASC(arXiv 2601.02970): 확신 가능한 건은 1회로 종료, 불확실한 건만 추가 샘플링(적응적 정지) [1차].
- 교차 모델 불일치(arXiv 2604.17112): 모델 간 불일치가 **"확신하지만 틀린" 응답 탐지**에 유효 [1차].
- temperature 관계: 다양성 확보에 `temperature > 0`가 필요하다는 점은 자명하나 정량 근거는 [근거 없음].

→ 전건 적용은 비용 과다. **1차 검산에서 실패하거나 애매한 건에만** 적용한다.

### false abstention은 면제되지 않는다

부록 A.5의 공식 권고("required + 명시적 `null`/`unknown`")를 채택하지만, 이것이 과잉 기권을 **면제해 주지는 않는다.**
arXiv 2507.16199는 "Unknown 선택지를 주면 **원래 정답 가능했던 문항까지 기권**"(abstention inflation)을 실증했고 [1차],
필드 추출에서 이것은 **읽을 수 있었던 값에 모델이 `null`을 쓰는 것**으로 그대로 번역된다.
AbstentionBench(arXiv 2506.09038)는 reasoning 파인튜닝이 abstention 성능을 평균 **24% 저하**시킨다고 보고한다 [1차].

→ **false abstention 비율은 측정 대상으로 남긴다.** 그러지 않으면 "못 읽었다"가 늘어나는 것을 안전해진 것으로 착각한다.
I-CALM(arXiv 2604.03904)의 abstention-to-error ratio가 이 측정의 후보 지표다 [1차].

---

## ⑤ 파이프라인 구조

### 단일 호출 vs 다단계

Anthropic 자체 엔지니어링 지침은 prompt chaining을 **"task를 고정 하위작업으로 깔끔히 분해 가능할 때"** 적합하다고 하고, 그 목적을 **"정확도를 위해 지연시간을 희생"**하는 것으로 명시한다. 중간 단계에 **programmatic gate** 삽입을 권한다 [1차].
routing은 **"구별되는 카테고리가 있고 분류가 정확히 가능할 때"** 적합하며, 분리하지 않으면 한 카테고리 최적화가 다른 카테고리 성능을 떨어뜨린다고 경고한다 [1차].

문서추출에서 다단계가 정확도를 올린다는 **정량 벤치마크는 없다** [근거 없음].
그러나 이 MVP에서는 **스키마 상한이 분기를 사실상 강제한다** — 부록 A.5의 optional 24 / union 16 상한 아래에서 세금계산서·계산서·카드전표·현금영수증·해외 인보이스의 필드 합집합을 단일 스키마로 담을 수 없다.

### 프롬프트 캐싱

| 사실 | 함의 |
|---|---|
| 최소 캐시 길이 512~4096 토큰(모델별), 미만이면 **에러 없이 비캐싱 처리** [1차] | 조용히 실패한다 — 캐시 적중을 측정해야 한다 |
| TTL 5분(기본, write 1.25배) / 1시간(옵션, write 2배), read 0.1배 [1차] | 배치는 5분을 넘길 수 있어 **1시간 캐시 권장** [1차] |
| breakpoint 최대 4개, lookback 20블록 [1차] | 3단계 파이프라인에 여유 있음 |
| **이미지·문서 블록은 user turn에서 캐시 가능** [1차] | 다단계에서 **같은 이미지를 3번 보내며 이미지 토큰을 3번 내지 않아도 된다** |
| **이미지 추가/제거는 messages 캐시를 무효화**(시스템·도구 캐시는 유지) [1차] | 영수증마다 이미지가 바뀌므로 **건 간 이미지 캐싱은 불가**. 캐시 이득은 공통 프리픽스와 **한 건 내 다단계**에서 나온다 |

### 배치 API

배치당 최대 100,000건 또는 256MB, 대부분 1시간 내 완료·**최대 24시간**, 미완료 요청은 만료(과금 없음), **표준가 대비 50% 할인**, 결과 29일 보관, **Vision 지원**, 미지원 파라미터는 `stream`·`speed`·`max_tokens:0`뿐이라 **구조화 출력은 배제되지 않는다** [1차].

→ **경로를 둘로 나눈다.** 월말 정산 같은 일괄 처리는 배치(비용 절반), 업로드 즉시 미리보기는 동기 호출. 24시간 지연은 대사 흐름에 부적합하다.

### 실패 분류

| 신호 | 재시도 | 근거 |
|---|---|---|
| 429 `rate_limit_error` | O — `retry-after` 준수, SDK가 기본 2회 지수 백오프 | [1차] |
| 529 `overloaded_error` / 500 `api_error` | O — 지수 백오프 | [1차] |
| 400·401·402·403·404·413 | X — 요청 자체 문제 | [1차] |
| `stop_reason: "max_tokens"` | O — `max_tokens` 상향 후 | [1차] |
| `stop_reason: "refusal"` | **HTTP 200 + `stop_details.category`.** 단순 재시도는 무의미 — 컨텍스트 리셋 또는 fallback 모델 | [1차] |
| "읽었지만 값이 이상함"(합계 음수 등) | API 실패가 아닌 **애플리케이션 검증 문제** — 공식 가이드 없음 | [근거 없음] |

마지막 줄이 이 MVP의 핵심 실패 유형이라는 점에 주의한다. **API가 성공을 반환한 건들 사이에서 갈라야 한다.**

### 중복

Claude API 자체의 이미지 해시·중복 탐지 기능은 **없다** [근거 없음].
업계 관행은 가맹점명 + 금액 + 날짜(+영수증번호)의 **퍼지 매칭**이다 [2차]. 같은 영수증을 다른 각도로 두 번 찍으면 이미지 해시로는 잡히지 않는다.
→ 중복 판정은 **추출된 정규화 값** 위에서 한다. SlipScan의 `findDuplicateOf`/`hasMatchingIdentity`가 이미 이 형태이므로 **골격은 이식 가능**하다.

### 사람 개입과 상태 기계

Anthropic이 Claude Code에서 측정한 수치가 이 MVP 전체에 대한 경고다:

> **승인 프롬프트의 약 93%를 사용자가 승인한다.** "승인을 많이 볼수록 덜 주의 깊게 본다." [1차]

승인 지점을 늘릴수록 사람은 고무도장이 된다. 따라서 **사람에게 보내는 건수 자체가 보장의 분모다** — 불확실한 건을 사람에게 넘기는 것이 보장이 아니라, **구조적 검산으로 최대한 걸러낸 뒤 희소하게 넘기는 것**이 보장이다. ④의 결론과 사용자 결정(사람이 확정 + 감사로그)이 여기서 하나로 만난다.

단방향 상태 기계(`processing → completed | failed`)로 표현할 수 없는 분기가 셋이다:
1. 사람이 **값만 수정하고 재개**(재추출 불필요)
2. **항목별 부분 승인**
3. 승인 대기 **타임아웃 후 에스컬레이션**

→ 순환을 허용하는 상태 기계가 필요하다: `processing → extracted → pending_review ⇄ corrected → reconciled | rejected`.
실무 패턴은 `pending_approval` 상태를 **영속화**해 재시작에도 생존시키고, 타임아웃 시 에스컬레이션 또는 자동 취소를 두는 것이다 [2차].

**[#17](https://github.com/DHChe/E2EAI_business_proj/issues/17)과의 관계 정정**: #18에서 "SlipScan의 상태 전이는 단방향이라 #17과 겹치지 않는다"고 적었다.
SlipScan 코드에 대한 서술로는 지금도 맞지만, **여기서 끌어낸 결론은 틀렸다.** 재설계된 파이프라인은 되돌아가는 전이를 요구하고,
#17이 정의하는 "반려의 후속 상태"와 여기의 "사람 수정 후 재개"는 **같은 순환 위의 두 지점**이다. 두 티켓은 조율돼야 한다.

---

## 부록 A — Claude API가 확정해 주는 제약 (조사자 직접 확인, 전부 [1차])

①②⑤가 반복해서 이 부록을 참조한다. SlipScan이 고른 값들이 우연이 아니었다는 것과,
동시에 그 값이 보장하지 않는 것을 여기서 먼저 못박는다.

### A.1 이미지 해상도 — 2576px는 "모델의 긴 변 상한"이지 "리사이즈 안 됨"이 아니다

공식 문서 [Vision](https://platform.claude.com/docs/en/build-with-claude/vision)는 해상도 티어를 이렇게 정의한다. [1차]

| 티어 | 모델 | 긴 변 상한 | 비주얼 토큰 상한 |
|---|---|---|---|
| High-resolution | Claude 4.7 and later models | **2576 px** | **4784** |
| Standard | All other models | 1568 px | 1568 |

- 비주얼 토큰 = `⌈width / 28⌉ × ⌈height / 28⌉` (28×28 픽셀 패치 1개 = 토큰 1개). [1차]
- 리사이즈 규칙은 [Coordinates and bounding boxes](https://platform.claude.com/docs/en/build-with-claude/vision-coordinates)에 **레퍼런스 구현까지 공개**돼 있다. "Claude finds the largest aspect-preserving size that satisfies **both** of the model's image limits" — 긴 변 제한과 토큰 제한 **둘 다**. [1차]
- 같은 문서: "For nearly all photos and screenshots, **the visual token limit is what determines the final size**. The edge limit takes over only for elongated images such as panoramas or tall phone screenshots." [1차]

**따라서 SlipScan의 긴 변 2576px는 high-resolution 티어의 긴 변 상한과 정확히 일치한다.**
그런데 그것만으로 서버측 리사이즈가 없어지지는 않는다 — 토큰 상한이 먼저 걸릴 수 있기 때문이다.
공개된 알고리즘을 그대로 돌려(레퍼런스 구현의 자체 예제 `resized_size(1075,1520) == (924,1307)`로 검증) 계산하면: [유도]

| 입력 (긴 변 2576) | 가로세로비 | 모델이 실제로 보는 크기 | 리사이즈 여부 |
|---|---|---|---|
| 2576×2576 | 1.00 | 1932×1932 | **축소됨** |
| 1822×2576 (A4 비율) | 1.41 | 1624×2296 | **축소됨** |
| 1610×2576 | 1.60 | 1512×2420 | **축소됨** |
| **1456×2576** | **1.769** | 1456×2576 | 그대로 (토큰 4784, 정확히 상한) |
| 1288×2576 | 2.00 | 1288×2576 | 그대로 |
| 859×2576 | 3.00 | 859×2576 | 그대로 |

→ **가로세로비 1.77:1보다 정사각형에 가까우면 2576px로 맞춰도 서버가 더 줄인다.**
길쭉한 영수증(3:1 이상)은 안전하지만, **A4 세금계산서·인보이스 스캔은 2576으로 보내도 1624×2296으로 축소된다**(긴 변 기준 11% 손실).
적격증빙 대사가 A4 세금계산서를 다루므로 이건 가상의 걱정이 아니다.

### A.2 긴 영수증 — 긴 변 상한이 글자가 있는 쪽(가로)을 깎는다

세로로 아주 긴 영수증은 긴 변 상한이 먼저 걸린다. 높이가 2576으로 고정되면
**가로 해상도는 `원본가로 × 2576/원본높이`로 비례 축소된다.** 글자는 가로로 놓여 있으므로 손실은 전부 글자 쪽으로 간다. [유도]

| 원본 | 모델이 보는 크기 | 가로 보존율 | 비주얼 토큰 |
|---|---|---|---|
| 3024×4032 (12MP 폰 세로, 1:1.33) | 1659×2212 | 54.9% | 4740 |
| 2000×6000 (1:3) | 859×2576 | 43.0% | 2852 |
| 1000×5000 (1:5) | 515×2576 | 51.5% | 1748 |
| 1000×10000 (1:10) | **258×2576** | **25.8%** | 920 |

1:10 영수증은 **가로 258px**로 눌린다. 이게 무슨 뜻인지 물리 단위로 환산하면:
Epson TM-T88V 사양서는 80mm 용지에 **"80mm: 42/56 columns"**, **"Font A: 1.41 x 3.39"**(mm, 가로×세로)라고 적고 있다 [1차, [Epson TM-T88V 제품 사양](https://epson.com/For-Work/POS-System-Devices/POS-Printers/TM-T88V-POS-Receipt-Printer/p/C31CA85084)].
가로 258px를 80mm에 펴면 3.2 px/mm = **약 82 DPI**이고, 폰트 A 한 글자의 가로는 **4.5 px**가 된다. [유도]
반대로 12MP 폰 세로 사진(가로 1659px 보존)은 527 DPI, 글자 가로 29px다.
주목할 점은 **토큰 예산이 남아도는데도**(920 / 4784) 이 일이 벌어진다는 것 — 긴 변 상한이 먼저 걸리기 때문이다.
세로로 3등분해서 3장으로 보내면 가로 1000px을 그대로 유지하면서 토큰은 1748 → 6480으로 늘어난다(3.7배). [유도]
즉 **긴 영수증 문제의 해법은 해상도를 올리는 게 아니라 잘라서 여러 장으로 보내는 것**이고, 값은 토큰으로 낸다.

### A.3 여러 장 보낼 때의 함정

- 요청당 이미지 상한: 200k 컨텍스트 모델 100장, 그 외 600장. 장당 10MB(base64), 요청 전체 32MB. 최대 치수 8000×8000px. [1차]
- **"If a single API request contains more than 20 images, a stricter per-image dimension limit applies to every image in that request."** 20장을 넘기면 "각 변 2000px 이하"로 줄여야 안전하다. [1차]
  → 영수증을 조각내서 보내는 전략과 **여러 건을 한 요청에 묶는 전략은 서로 잡아먹는다.**
- 문서는 여러 장을 보낼 때 `Image 1:` / `Image 2:` 같은 텍스트 라벨을 각 이미지 앞에 붙이라고 권한다. [1차]
- 이미지는 텍스트보다 **앞에** 두는 것을 권장한다. [1차]

### A.4 PDF를 래스터화하지 않고 넘길 때 포기하는 것

[PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support) [1차]:
- 한도: 요청 32MB, **600페이지(컨텍스트 1M 미만이면 100페이지)**, "Standard PDF (**no passwords/encryption**)".
- 비용: "Each page typically uses **1,500–3,000 tokens per page**" + "**because each page is converted into an image**, the same image-based cost calculations are applied." → 텍스트 토큰과 이미지 토큰을 **둘 다** 낸다.
- "Because PDF support relies on Claude's vision capabilities, it is subject to the same limitations and considerations as other vision tasks."
- 공식 권장사항에 **"Rotate pages to proper upright orientation"**, "Ensure text is clear and legible", "Place PDFs before text in your requests"가 그대로 들어 있다.

결정적인 제약은 좌표 문서 쪽에 있다 [1차]:
> "For PDF support, **pages are rasterized to images server-side at dimensions you don't control**, so the returned coordinates **can't be reliably mapped back onto the page**. To work with coordinates on PDF content, rasterize the pages to images yourself and use the pre-resize approach."

그리고 오버사이즈 거부 옵션(`transformations.oversized_image`)도 **`document` 블록은 받지 않는다.** [1차]

→ **PDF를 그대로 넘기면 (a) 래스터 해상도를 제어할 수 없고 (b) 필드를 원본 위치로 되짚는 크롭을 만들 수 없다.**
승인 카드에 "이 금액은 여기서 읽었다"는 근거 이미지를 붙이려면 PDF는 **직접 래스터화**해야 한다.
반대로 근거 크롭이 필요 없다면 그대로 넘기는 편이 코드가 적다 — SlipScan의 선택은 그 조건에서는 합리적이다.

### A.5 구조화 출력이 보장하는 것과 보장하지 않는 것

[Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) [1차]:
- 보장: "Structured outputs guarantee **schema-compliant** responses through constrained decoding: Always valid / Type safe / Reliable." **스키마 적합성이지 값의 정확성이 아니다.**
- **수치 제약은 와이어 스키마에서 지원되지 않는다**: "Numerical constraints (such as `minimum`, `maximum`, `multipleOf`)" is not supported. `minLength`/`maxLength`도 마찬가지.
  SDK(Python/TS/Ruby/PHP)는 이것들을 **스키마에서 떼어내 description에 문장으로 붙이고, 응답을 원래 스키마로 사후 검증**한다: "SDK-validated constraints (stripped from the wire schema, appended to the description, and validated against the response): `minimum`, `maximum`, `multipleOf`, `minLength`, `maxLength`."
  → #18의 "통화별 최소단위 배수" 같은 제약은 **디코딩 단계에서 강제할 수 없다.** zod 이중 검증이 선택이 아니라 필수인 이유가 여기 있다.
- **`pattern`(정규식)은 지원된다**(부분집합): `^...$`, `*`, `+`, `?`, 단순 `{n,m}`, `[]`, `.`, `\d`, `\w`, `\s`, 그룹. 역참조·전후방탐색·`\b`는 **미지원**.
  → 사업자등록번호 `^\d{3}-\d{2}-\d{5}$` 같은 **형식**은 디코딩으로 강제 가능하다. 체크섬은 정규식으로 표현 불가이므로 코드 몫이다(④ 참조).
- **스키마가 깨지는 3가지 경우**를 문서가 명시한다: `stop_reason: "refusal"`, `stop_reason: "max_tokens"`, 그리고 **enum 대소문자 드리프트** — "Structured outputs don't guarantee the capitalization of string `enum` and `const` values... The response completes normally, **with no error and no special `stop_reason`**. Compare enum values case-insensitively."
  → `docType` enum을 넓힐 때(#18 설계 항목 3) **대소문자 무시 비교**가 필요하다.
- **복잡도 상한**이 있다: 요청당 optional 파라미터 **24개**, union 타입(`anyOf` 또는 `["string","null"]`) 파라미터 **16개**, strict 도구 20개. 초과 시 400 "Schema is too complex for compilation". 컴파일 타임아웃 180초.
  → 새 스키마(통화·환율기준일·사업자등록번호·승인번호·공급가액·부가세·증빙유형·품목…)를 전부 **nullable optional**로 잡으면 이 상한에 실제로 닿는다. **"필드를 required로 만들고 모델이 명시적으로 `null`/`"unknown"`을 쓰게 하라"**가 문서의 공식 권고다.
- 첫 호출에 문법 컴파일 지연이 있고, 컴파일된 문법은 **마지막 사용으로부터 24시간** 캐시된다. 스키마 구조를 바꾸면 무효화된다.

### A.6 인용(citations)으로 근거를 붙이는 길은 막혀 있다

[Citations](https://platform.claude.com/docs/en/build-with-claude/citations) [1차]:
- **"Citations cannot be used together with structured outputs. If you enable citations on any user-provided document ... and also include the `output_config.format` parameter ..., the API returns a 400 error."** 이유도 적혀 있다 — 인용은 텍스트 사이에 인용 블록을 끼워 넣어야 하는데 엄격한 JSON 문법과 양립하지 않는다.
- **"Only text citations are currently supported. Image citations are not yet possible."**
- **"PDFs that are scans of documents and do not contain extractable text are not citable."**

→ **영수증 이미지에서는 인용이 애초에 불가능하다.** 구조화 출력을 포기해도 얻을 수 없다.
필드별 출처를 화면에 보이려면 남는 길은 **모델에게 바운딩 박스를 받아 직접 크롭하는 것**뿐이고,
공식 문서는 그 좌표가 **근사치**라고 못박는다: "Claude's coordinate and localization outputs are **approximate**... verify outputs before relying on them." 또 "**Small elements lose precision when an image is downscaled**: for fine targets, crop the region of interest and send the crop." [1차]

### A.7 공식 문서가 인정하는 비전 한계

> "**Accuracy:** Claude might hallucinate or make mistakes when interpreting **low-quality, rotated, or very small images under 200 pixels**."
> "**Counting:** Claude can give approximate counts of objects in an image but might not always be precisely accurate, especially with large numbers of small objects."
> "Always carefully review and verify Claude's image interpretations, especially for high-stakes use cases. **Do not use Claude for tasks requiring perfect precision ... without human oversight.**" [1차]

압축에 대한 경고도 명시적이다: "heavy JPEG compression can make text difficult to read... **Confirm your compression settings are appropriate for the task by inspecting the actual images sent to the API.**" [1차]
→ SlipScan의 sharp JPEG 변환은 품질 파라미터가 **측정 대상**이지 기본값으로 둘 값이 아니다.
