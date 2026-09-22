# ADR-0009 — 근거 표시는 바운딩 박스 크롭 + 원본 토글이고, PDF는 직접 래스터화한다

- **상태**: Accepted
- **날짜**: 2026-09-21
- **맥락 티켓**: #18 (결정), #19 (근거, 부록 A), #13 (승인 카드 본문)

## 맥락

승인 카드의 본문은 자연어 요약이 아니라 **구조화 필드 + 정책 원문 인용**이다(CONTEXT §3, #13).
그러면 "이 금액은 지면의 어디서 읽었는가"를 화면에서 보여야 하고, 사람이 수기 확정할 때도 그 자리를 봐야 한다.

가장 자연스러운 수단인 **citations는 세 겹으로 막혀 있다** `[1차, #19 부록 A.6]`:

> "Citations cannot be used together with structured outputs. (…) the API returns a 400 error."
> "**Only text citations are currently supported. Image citations are not yet possible.**"
> "PDFs that are scans of documents and do not contain extractable text are **not citable**."

구조화 출력을 포기해도 이미지에서는 얻을 수 없다. 남는 길은 **모델에게 바운딩 박스를 받아 직접 크롭하는 것**뿐이고,
공식 문서는 그 좌표의 성질을 못박는다 — "Claude's coordinate and localization outputs are **approximate**",
"**Small elements lose precision when an image is downscaled**" `[1차, A.6]`.

## 결정

1. **근거 표시 = 바운딩 박스 크롭을 기본 화면으로, 원본 전체를 항상 한 번의 동작으로 펼칠 수 있게 둔다.**
   수기 확정 화면과 승인 카드 양쪽에 같은 규칙을 적용한다.
2. **파생 결정: PDF는 직접 래스터화한다.** `document` 블록으로 넘기지 않는다.
3. 좌표는 **우리가 보낸 이미지의 픽셀 좌표**로 받고, 서버가 다시 줄이지 않도록 **우리가 먼저 최종 크기로 줄여서** 보낸다(pre-resize).
4. 좌표가 없는 근거도 있다 — `absent`(지면에 없음)에 기대는 판정은 크롭이 불가능하므로 **원본 전체를 근거로 제시**한다.
5. 크롭 패딩은 값을 정하지 않는다. 0으로 두고 원본 토글을 안전장치로 삼으며, 패딩은 측정으로 정한다.
6. 사람이 확정할 때 **원본을 펼쳤는지 여부를 감사 로그에 남긴다**(`originalViewed`).

## 근거

**왜 크롭만으로는 안 되는가.** 좌표가 근사치이므로 빗나갈 수 있고, 크롭만 보여 주면 사람이 **엉뚱한 곳을 보고 확정**하게 된다.
그 오류는 감사 로그에 `사람이 확인함`으로 남아 되짚을 수 없게 된다.
근사치인 좌표 위에 사람의 최종 책임을 얹으려면 원본이 한 번의 동작 거리에 있어야 한다.

**왜 원본만으로는 안 되는가.** 승인자가 30건을 훑는 화면에서 전체 이미지를 매번 훑게 하면 아무도 보지 않는다.
#19가 경고한 93% 문제는 "보여 줬다"가 아니라 "보게 만들었다"로만 막힌다.

**왜 PDF를 직접 래스터화하는가.** 좌표 문서가 직접 답한다 `[1차, A.4]`:

> "For PDF support, **pages are rasterized to images server-side at dimensions you don't control**, so the returned coordinates **can't be reliably mapped back onto the page**. To work with coordinates on PDF content, rasterize the pages to images yourself and use the pre-resize approach."

`slipscan`은 PDF를 base64 `document` 블록으로 그대로 넘긴다(`slipscan:lib/claude/extract.ts:142-149`).
**근거 크롭이 필요 없다는 조건에서 그 선택은 코드가 적어 합리적이었다.** 이 MVP는 그 조건이 아니므로 승계하지 않는다.
덤으로 따라오는 것도 있다 — `document` 블록은 오버사이즈 거부 옵션(`transformations.oversized_image`)을 받지 않고 `[1차, A.4]`,
페이지당 텍스트 토큰과 이미지 토큰을 둘 다 낸다 `[1차, A.4]`.

**왜 pre-resize가 이 결정의 일부인가.** 서버는 긴 변 상한과 토큰 상한을 **둘 다** 만족하는 최대 크기로 줄인다 `[1차, A.1]`.
우리가 2576px로 보내도 A4 스캔은 1624×2296으로 줄어든다. 그 사실을 모르면 좌표계가 어긋나
크롭이 조금씩 빗나가고, 원인을 찾을 수 없다. 우리가 먼저 그 크기로 만들어 보내면 좌표가 1:1이 된다.

**왜 패딩 값을 지금 정하지 않는가.** 좌표 오차의 크기를 말해 주는 1차 자료가 없다 `[근거 없음]`.
"근사치"라는 문장만 있고 분포가 없다. 값을 지어내는 대신 라벨된 정답 영역의 **포함률**을 패딩별로 재는 측정을 설계했고,
표본점에 시각 토큰 격자의 단위인 28px을 넣는다(설계 문서 §11.3).

## 결과

- 전처리에 래스터화·조각내기·좌표 역변환이 들어온다. `slipscan:lib/pipeline/image.ts`의 한 줄짜리 리사이즈로는 부족하다.
- 스키마에 좌표 배열이 들어온다. 필드마다 nullable 박스를 두면 union 예산이 절반으로 줄어들기 때문에
  **필드 키 + 인덱스 + 박스의 배열**로 받는다(설계 문서 §3.2).
- 크롭이 빗나갔을 때의 책임 경로가 생긴다 — `originalViewed`가 거짓인 확정이 반복되면 그 자체가 지표다(#11).
- PDF 처리 비용이 늘어난다(우리 쪽 래스터화 + 페이지 수만큼의 이미지). 20페이지 상한은 유지하되
  근거가 "함수 시간"이 아니라 **요청당 20장을 넘기면 모든 이미지에 더 엄격한 치수 제한이 붙는다**로 바뀐다 `[1차, A.3]`.
- 승인 카드와 수기 확정 화면의 부품이 같아진다(크롭 · 원본 토글 · 출처 표시). ~~화면 설계는 #9·#10이 이어받는다.~~ **정정(#23, 2026-09-22)**: 두 화면의 설계는 #8의 소관이었다(`docs/PRD.md:172`). #8은 승인 카드의 형태를 정하고 닫혔으나(<https://github.com/DHChe/E2EAI_business_proj/issues/8#issuecomment-5769586450>), 수기 확정 화면의 설계는 그 결과에 없다 — #25가 추적한다.
