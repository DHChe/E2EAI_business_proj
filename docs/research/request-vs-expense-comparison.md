# 사전 신청과 사후 정산의 대조 — 출장·경비 제품 1차 자료 확인

> 조사 계기: PRD 그릴링(2026-09-21) — [PRD](../PRD.md)의 차별점 C2 · 선행 이슈: [#7](https://github.com/DHChe/E2EAI_business_proj/issues/7) · 부모 map: #1
> 조사 시점: 2026-09-21
> 이 문서는 한 가지 질문에만 답한다 — **출장·경비 제품이 사전 신청(사전승인)과 사후 정산을 총액보다 세밀하게 대조해 승인자에게 보여 주는가.**
> 선행 조사(#3·#13)는 Ramp(거래 단위 정책 에이전트)만 봤고, 출장관리 제품의 사전 신청과 정산의 연결은 보지 않았다(`ax-competitive-landscape.md:212-213`). 이 문서는 그 구멍만 메운다.

## 이 문서를 읽는 법 — 증거 등급

등급 표기는 용어집(`CONTEXT.md` 출처 등급)을 따르고, 용어집의 `[2차]`는 누가 낸 자료인지를 붙여 적는다.

| 태그 | 뜻 |
| --- | --- |
| `[1차·벤더]` | 벤더의 공식 도움말·제품 문서·설정 가이드 본문을 직접 읽었다 |
| `[1차·스니펫]` | 본문 직접 확인에 실패하고 검색 스니펫만 확보했다. `[1차·벤더]`와 섞지 않는다 |
| `[2차·고객사]` · `[2차·파트너]` | 벤더가 아니라 그 제품을 쓰는 기관(고객사)이나 벤더의 구현 파트너가 공개한 글 |

Navan·Emburse·Certify·Perk 도움말은 자바스크립트로 그리는 페이지라, 각 도움말 센터의 공개 콘텐츠 API로 본문을 읽었다. 인용은 원문 그대로 영어로 둔다.

---

## 1. SAP Concur — Request와 Expense

| 항목 | 답 | 근거 |
| --- | --- | --- |
| 연결 | 한다 | "Users can associate a travel request with an expense report multiple ways" — [Request Overview Guide](https://community.concur.com/marav43842/attachments/marav43842/RelatedProducts/1734/1/SG_Req_Overview.pdf) `[1차·벤더]` |
| 대조 단위 | 총액, 그리고 신청의 경비유형별·세그먼트별 **금액** | "Exceeds Request Amount: …total of all expenses exceeds the total amount authorized for the request" / "Exceeds Entry Request Amount: …exceed the amount pre-approved for the related request expense type" / "total expenses against the hotel segment entry of a travel request exceed the pre-approved amount of that segment" — [Audit Rules Setup Guide](https://community.concur.com/marav43842/attachments/marav43842/ConcurExpense/25514/1/Exp_SG_Audit_Rules.pdf) `[1차·벤더]`. 기본 제공 룰 "Request - Expense Entry Amount exceeds approved Request Entry Amount" — [SAP Learning](https://learning.sap.com/courses/integrating-concur-request-with-concur-expense-professional-configuration/explaining-audit-rules) `[1차·스니펫]` |
| 승인자 노출과 정책 근거 | 예외(exception)로 노출된다. 누구에게 보일지는 룰마다 설정한다(사용자·승인자·처리자 / 승인자·처리자 / 처리자만). 문구는 관리자가 쓰는 자유 텍스트이고 정책 조항과 구조적으로 이어지지 않는다 | "the exception text (message) appears to the user, approver, and processor" — 세 가지 노출 방식 중 하나, 위 Audit Rules Setup Guide `[1차·벤더]` |
| 인접 기능 | 정산을 Concur Travel의 **예약**과 대조한다. 제공 룰은 금액을 비교하고, 가이드 예시에는 예약 출발일과 구매일의 날짜 비교(항공권 사전 구매 규정)가 있다. 신청 쪽 값과의 비교는 없다 | 제공 룰 "Travel Actual vs Booked"의 문구 "The expense is greater than the estimated expense in the travel reservation." / 룰 필드 "Class of Service (Booked)", "Start Date (Booked)" / 예시 "Start Date (Booked) is compared against the Transaction Date – 1 month" — 위 가이드 `[1차·벤더]` |

## 2. Navan

| 항목 | 답 | 근거 |
| --- | --- | --- |
| 연결 | 한다(정산용 trip) | "your manager or Expense admin may need to approve the trip before your expenses are approved" — [Help: creating-trips](https://app.navan.com/app/helpcenter/articles/expense/myself/managing-my-expenses/creating-trips) `[1차·벤더]` |
| 대조 단위 | 임계값만 있다. 무엇을 기준으로 한 임계값인지 적혀 있지 않다 | "the associated expenses will either also be auto-approved or require further review by an admin if spend surpasses the allowed threshold" — 위 글 `[1차·벤더]` |
| trip proposal(예약 전 승인) | 승인자는 추정 비용을 본다. 제안과 실제 예약·정산을 대조한다는 서술은 없다 | 검토 화면 항목 "Estimated total cost", "In-policy price maximums" / "All bookings made will still go through the standard approval process" — 도움말 "How do I manage trip proposals?" `[1차·벤더]`. 경로는 도움말의 카테고리 연결에서 끌어낸 추정이다 — `app.navan.com/app/helpcenter/articles/travel/myself/manager-dashboard/responding-to-trip-proposals` |

## 3. Emburse — Enterprise(Chrome River)와 Professional(Certify)

| 항목 | 답 | 근거 |
| --- | --- | --- |
| 연결 | 한다 | "You may link a pre-approval to an expense report at any time during expense-report creation." — [Chrome River 도움말](https://help.chromeriver.com/hc/en-us/articles/15295598155277-Attach-a-Pre-Approval-to-an-Expense-Report) `[1차·벤더]` |
| 대조 단위 | Chrome River는 경비유형별 **금액**을 승인액과 대조한다. Certify는 총액을 대조하고, 항목별(Itemized) 요청일 때만 유형별 지출을 나눠 보여 준다 — 유형별 승인액과 대조한다는 서술은 없다 | "The Expense Summary shows the remaining amounts available for each type of expense. … The Spent amount is displayed in red if it exceeds the original approved amount." — 위 글(제출자 화면) `[1차·벤더]`. Certify: "The Spend Tracker visualizes your spend against the pre-approved amount from the spend request." / "When an Itemized spend request is linked…, the user will be able to expand the Spend Tracker to see a breakdown of spend by expense type." — [Certify 도움말](https://help.certify.com/hc/en-us/articles/15458279098765-Linking-Expenses-to-Spend-Requests) `[1차·벤더]` |
| 승인자 노출과 정책 근거 | 일반적인 가시성 서술과 총액 수준의 컴플라이언스 룰 | "Pre-Approvals are then linked to the actual expense report thus providing approvers and auditors with visibility into whether the actual spend was aligned with approved costs." — [Implementation toolkit](https://www.emburse.com/enterprise/implementation-toolkit/pre-approval) `[1차·벤더]`. 룰 속성 "Check whether the expense report total exceeds the remaining balance…", "Determine whether an expense report's Submit Date is the specified number of days after the End Date of the attached pre-approval." — [Rule Builder Attributes](https://help.chromeriver.com/hc/en-us/articles/15668058663821-Rule-Builder-Attributes) `[1차·벤더]`. 이 페이지는 "some of the most popular attributes"만 나열하므로, 여기 없다는 것은 없다는 근거로 약하다 |

## 4. 그 밖의 제품 — 짧게 확인

| 제품 | 연결 · 대조 단위 · 승인자 노출 | 근거 |
| --- | --- | --- |
| Oracle Fusion Expenses | 승인 건을 정산의 헤더나 라인에 붙이고(설정에 따라), 매니저·감사자가 추정액과 실제액을 **비교한다**. 금액·예산 기준이고, 위반은 매니저에게 보인다 | "allows managers and expense auditors to compare approved estimated expenses against incurred expenses… Such violations are visible to the manager and the expense auditor"(예산 통제를 켰을 때) — [Implementing Expenses 26C 6장](https://docs.oracle.com/en/cloud/saas/financials/26c/faiex/implementing-expenses.pdf) `[1차·벤더]` |
| Workday | commitment accounting을 켰을 때 잔액 차감 방식으로 연결한다. 자동 대조는 찾지 못했다. 고객사 안내에는 승인자가 회계 속성(worktag)을 **손으로** 대조하는 절차가 있다 — 금액이 아닌 속성의 대조이지만 수동이고, 여행 속성이 아니라 회계 속성이다 | "If you enable commitment accounting, you can link an approved spend authorization to multiple expense reports until its balance equals zero." — [doc.workday.com](https://doc.workday.com/admin-guide/en-us/financial-management/expenses/spend-authorizations/dan1370797493663.html) `[1차·벤더]`. "…select the See in New Tab option… From here, compare the worktags and…" — [Howard University](https://research.howard.edu/sites/research.howard.edu/files/2023-08/02%20HU%20-%20SA_ER%20Approver%20JA_Final.pdf) `[2차·고객사]` |
| Coupa | 금액 수준으로 연결한다. API 스키마로만 확인했다 | 필드 "amount", "available-amount" — [Expense Report Preapproval API](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/the-coupa-core-api/resources/transactional-resources/expenses-api-(expense_reports)/expense-report-preapproval-api) / 라인 필드 "estimated_amount", "requested_amount" — [Expense Preapproval Line API](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/the-coupa-core-api/resources/transactional-resources/expenses-api-(expense_reports)/expense-preapproval-line-api) `[1차·벤더]`. 화면과 승인자 뷰는 확인하지 못했다 |
| Perk | 사전승인은 자유 텍스트(closed beta)이고 대조가 없다. 별도로, Travel approval policy로 예약 전·예약 시점에 승인된 여행의 예약 비용은 매니저 검토 없이 자동 승인된다(기본값으로 켜진 것은 2026-04-02 이후 만든 계정) | "What you're deciding is whether the trip should happen at all—not whether a particular flight is within policy." — [How trip pre-approvals work](https://support.perk.com/hc/en-us/articles/29444373436956-How-trip-pre-approvals-work) / "Perk also automatically approves the expense, skipping manager review, unless your account has its own custom approval workflow set up." — [How travel expenses are automatically submitted and approved](https://support.perk.com/hc/en-us/articles/30209604657436-How-travel-expenses-are-automatically-submitted-and-approved) `[1차·벤더]` |
| 비즈플레이 | 점검 결과를 결재자와 공유한다. 점검 범위는 한도·결재선·코스트센터·계정 검증이고, 계획서와 정산서의 대조는 없다 | "점겸[sic] 결과를 결재자와 공유하여…", 범위 "직원별 숙박비 한도, 일별 식대 한도, 출장 계정 과목 검증…", "본 서비스는 맞춤 개발이 필요한 영역…" — [bizplay docs](https://docs.bizplay.co.kr/uses_case/travel_mgmt/business-trip-management/business-trip-audit) `[1차·벤더]` |
| 더존 Amaranth10 · 자비스 | 1차 자료를 찾지 못했다 | — |

## 5. 확인하지 못한 것

- **Concur 승인자 화면에서 신청과 정산이 나란히 보이는지** — SAP Help Portal은 자바스크립트로 그리는 페이지라 읽지 못했고 SAP Learning 페이지는 404였다. 감사 룰의 "Request related Reports" 데이터 객체 필드는 가이드 안 스크린샷에만 있어 판독하지 못했다.
- **"Concur Joule 정산 에이전트가 예약된 여행으로 정산 라인을 검증한다"** — 이 주장의 출처는 파트너 블로그다: "Uses booked travel (flights, hotels, car rentals) as context to validate that expense line items are consistent with the travel undertaken" — [SAVIC Technologies](https://www.savictech.com/insights/sap-concur-fusion-2026-joule-expense-agents-india-cleartrip/) `[2차·파트너]`. 벤더 1차 자료는 그만큼 말하지 않는다 — [SAP News 2026-03](https://news.sap.com/2026/03/sap-concur-fusion-2026-ai-capabilities-integrated-travel-expense-enhancements-global-partnerships/)은 "automatically creates and populates expense reports", "validates receipts and flags discrepancies"까지이고, [concur.com 블로그](https://www.concur.com/blog/article/agentic-ai-travel-expense-management)는 영수증과 경비의 불일치를 말하며 일정은 주소를 채우는 데만 쓴다. [Joule FAQ](https://community.concur.com/marav43842/attachments/marav43842/EventsHub/342/1/WW%20EXTERNAL%20FAQ%20-%20Joule%20with%20SAP%20Concur%20solutions.pdf)는 "does not… validate receipt accuracy"라고 적는다 `[1차·벤더]`. 두 에이전트 모두 Early Adopter Care 단계다. 파트너의 주장이 맞더라도 비교 대상은 **신청이 아니라 예약**이고, 좌석 등급·날짜를 대조한다는 말은 없다.
- **Emburse의 유형별 요약(빨간 표시)과 Certify Spend Tracker가 승인자 화면에도 보이는지** — 문서는 제출자 화면만 설명한다.
- Navan의 "allowed threshold"가 무엇을 기준으로 하는지, Coupa의 화면.

## 6. 결론

1. **확인한 제품은 모두 사전 신청을 정산에 연결한다.** 그중 Concur(경비유형별·세그먼트별 룰)와 Emburse Chrome River(경비유형별 표시)는 이미 **총액보다 세밀하게 금액을** 대조하고, Oracle은 승인 건을 정산의 헤더나 라인에 붙여 매니저가 비교하게 한다. "총액 비교만으로는 놓친다"는 대비는 사실과 맞지 않는다.
2. **신청과 정산 사이의 여행 속성 — 좌석 등급, 숙박 박수, 일정, 행선지, 동행, 사적 일정 — 을 대조하는 기능은 읽은 1차 자료 어디에도 없다.** 가까운 것이 셋 있지만 모두 이것이 아니다. Concur의 속성 룰은 비교 대상이 신청이 아니라 **예약**이다(예약 출발일과 구매일의 비교, §1). Emburse의 날짜 룰은 여행 속성이 아니라 **제출 시점**을 본다(§3). Workday 고객사 안내의 worktag 대조는 **회계 속성**을 승인자가 **손으로** 대조하는 절차다(§4). Joule 주장은 2차 파트너 자료뿐이다(§5).
3. **차이는 관리자가 문구를 쓰는 일반 예외나 컴플라이언스 플래그로 승인자에게 간다.** 차이 하나하나를 정책 조항에 이어 보여 주는 제품은 찾지 못했다. 가장 가까운 것은 Joule의 "In-workflow policy clarity that explains alerts… in plain language"인데, 제출 전 제출자 화면용이고 조항과 이어지지 않는다 — [Joule FAQ](https://community.concur.com/marav43842/attachments/marav43842/EventsHub/342/1/WW%20EXTERNAL%20FAQ%20-%20Joule%20with%20SAP%20Concur%20solutions.pdf) `[1차·벤더]`. 이 인용은 아래 검수 범위(§1~§4) 밖이다.

부수 발견 — **기한 경과를 규칙으로 잡는 제품은 있다.** Emburse Rule Builder의 "Determine whether an expense report's Submit Date is the specified number of days after the End Date of the attached pre-approval"(§3)이 그것이다. 이 규칙은 관리자가 설정한 속성이지 규정 조항의 인용이 아니고, 승인 큐의 정렬 축도 아니다.

**검수**: 작성자가 아닌 에이전트가 §1~§4의 인용을 원문(PDF 텍스트, 도움말 공개 API, 원시 HTML)과 모두 대조했다(2026-09-21). 이어 붙이거나 지어낸 인용은 없었다. 빠진 한정어 네 곳(Concur 노출 대상, Certify Itemized, Workday commitment accounting, Perk 적용 범위)과 Coupa 출처 URL 하나를 고쳤고, 결론 2의 "그마저 금액을 비교한다"를 지우고 예외 셋을 드러냈다.
