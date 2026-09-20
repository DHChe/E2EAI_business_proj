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
