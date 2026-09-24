# 공개 영수증·인보이스 이미지 데이터셋 조사 (이슈 #11 평가 계획, 출처 (3) 후보)

- 접근일: 2026-09-24 (모든 URL 동일)
- 표기: [1차] = 데이터셋 논문·공식 저장소·공식 데이터 카드에서 직접 읽음. [1차·육안] = 공개 샘플 이미지를 직접 열어 확인. [2차] = 제3자 미러·요약 (참고만). [확인 못함] = 1차 출처에서 확인하지 못함.
- 범위: PRD S9·S12가 이미지 출처를 셋(실물 촬영·자체 렌더링·공개 데이터셋)으로 가르라고 했고(`docs/PRD.md:159`, `:162`), 이 문서는 세 번째 출처의 후보를 모은 사실 수집이다. #11 그릴링(2026-09-24) 중 코디네이터의 조사 서브에이전트가 썼다. 권고는 하지 않고 관찰만 끝에 적었다. 어느 데이터셋을 쓸지는 #11이 정한다.

---

## 1. CORD (Clova AI, 인도네시아)

- URL: https://github.com/clovaai/cord , https://huggingface.co/datasets/naver-clova-ix/cord-v2
- 인용: Park et al., "CORD: A Consolidated Receipt Dataset for Post-OCR Parsing", Document Intelligence Workshop at NeurIPS 2019 (논문 https://openreview.net/pdf?id=SJl3z659UH ). [1차: GitHub README 인용 블록]
- 라이선스: "Creative Commons Attribution 4.0 International License" (CC BY 4.0). [1차: GitHub README] HF 카드 메타데이터 `license: cc-by-4.0`. [1차: HF API]
  - 상업 이용, 재배포, 공개 데모 표시 모두 저작자 표시 조건으로 허용된다(CC BY 4.0 조문 해석).
- 규모: 공개본 1,000장 (train 800 / dev 100 / test 100), v0·v1·v2 모두 동일. 전체 수집량은 "over 11,000 Indonesian receipts"지만 공개는 1,000장. [1차: README]
- 지역·언어: 인도네시아 영수증, "collected from shops and restaurants". [1차: README]
- 촬영 방식: README에 사진인지 스캔인지 명시 없음. [확인 못함] (논문 PDF는 OpenReview가 자동 수집을 막아 읽지 못함)
- 라벨: 5개 상위 클래스·42개 하위 클래스 정의(일부 취소선). 메뉴(이름·수량·단가·가격·할인), subtotal(소계·할인·봉사료·세금 `subtotal.tax_price`), total(`total.total_price`, 현금·거스름돈·`total.creditcardprice` = 카드 결제 금액, e-money). 단어 단위 quad 박스, `row_id`, `group_id`, `is_key`, `roi`. [1차: README]
  - **가맹점명·주소·날짜 라벨 없음**: "`store_info`, `payment_info`, and `etc` fields have been removed ... due to Indonesian legal issues." [1차: README, 2019-12-12 업데이트]
- 대상 국가(한·베·멕·독·일) 포함: 없음.
- 카드 끝 4자리: `payment_info` 클래스가 제거됐고 카드 번호 라벨은 없다. 카드 결제 금액 라벨(`total.creditcardprice`)만 있다. 이미지에 카드번호가 찍혀 있는지는 [확인 못함].
- 주의: HF 카드 README 본문은 비어 있다. WebFetch 요약기가 "Indonesian, Thai, English"라고 답했지만 1차 근거가 없어 채택하지 않았다.

## 2. SROIE (ICDAR 2019 Robust Reading Challenge on Scanned Receipts OCR and IE)

- URL: https://rrc.cvc.uab.es/?ch=13 (Overview/Tasks/Downloads)
- 인용: Huang et al., "ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction", ICDAR 2019, pp.1516-1520, doi:10.1109/ICDAR.2019.00244 (arXiv 2103.10213). [1차: 논문 PDF]
- 라이선스: **RRC Overview, Tasks, Downloads 페이지와 논문 어디에도 라이선스 문구가 없다.** [1차로 부재 확인] 다운로드에는 RRC 가입이 필요하다: "You will need to register to get access to the download section." [1차: Downloads 페이지]
  - OpenMMLab MMOCR의 metafile은 SROIE를 `CC BY 4.0`으로 적었다 (https://raw.githubusercontent.com/open-mmlab/mmocr/main/dataset_zoo/sroie/metafile.yml ). Voxel51 HF 미러도 cc-by-4.0이다. 둘 다 [2차]이므로 이 표기만 보고 라이선스를 확정하면 안 된다.
- 규모: "1000 whole scanned receipt images"이며 trainval 600, test 400으로 나뉜다. [1차: Tasks 페이지, 논문] 한편 같은 RRC 사이트의 SVRD 2023 소개문은 "SROIE (973)"로 적는다. [1차: https://rrc.cvc.uab.es/?ch=21 ] 따라서 실제로 배포된 수는 1,000장보다 적을 수 있다.
- 지역·언어: "The text annotated in the dataset mainly consists of digits and English characters." 중국어 문자가 섞여 있으면 무시하라는 공지도 있다. [1차] 수집 국가는 공식 문서에 없다. [확인 못함] (말레이시아라는 통설은 [2차])
- 촬영 방식: 스캔이다. "low resolution scanner and scanning distortion; folded invoices" [1차]
- 개인정보: "some sensitive fields (such as name, address and contact number etc) of the receipts are blurred." [1차: Overview]
- 라벨: Task 1·2는 단어 단위 4꼭짓점 박스와 전사. Task 3은 `company`, `date`, `address`, `total` 4개 필드. [1차: Tasks] 품목, 세금, 카드 필드 라벨은 없다.
- 대상 국가 포함: 없음. 카드 끝 4자리: 라벨 없음, 이미지 여부 [확인 못함].

## 3. WildReceipt (OpenMMLab / SenseTime)

- URL: https://download.openmmlab.com/mmocr/data/wildreceipt.tar (MMOCR dataset_zoo)
- 인용: Sun et al., "Spatial Dual-Modality Graph Reasoning for Key Information Extraction", arXiv 2103.14470. [1차: 논문]
- 라이선스: MMOCR metafile에 `License: Type: N/A, Link: N/A`로 적혀 있다. [1차: https://raw.githubusercontent.com/open-mmlab/mmocr/main/dataset_zoo/wildreceipt/metafile.yml , 배포처가 곧 저자 그룹] 논문에도 라이선스는 없다. → **라이선스 없음**
- 출처 문제: "We searched receipt images on search engines with related key-words, such as receipt, invoice ... downloaded about 4300 document images." 여러 장이 겹친 이미지, 판독 불가 이미지, **비영어** 이미지는 수작업으로 제거했다. [1차: 논문 IV.A] → 웹에서 긁어온 이미지이므로 원 저작권이 불명확하다.
- 규모: 본문은 "1740 receipt images, 68975 text bounding boxes"이고 train 1268 / test 472로 나뉜다. 그런데 Table I은 1768로 적어 **논문 안에서 수치가 맞지 않는다**. [1차]
- 촬영 방식: 실사진("captured in the wild ... non-front views and possibly with folds"). [1차]
- 라벨: 25개 key/value 범주. Store name, Store addr, Tel, Date, Time, Prod item/qty/price, Subtotal, Tax, Tips, Total 각각의 key/value와 Others. 모든 텍스트 박스에 범주가 붙는다. [1차: Table III]
- 대상 국가 포함: 영어만. 한국 식당 이름이 영문으로 찍힌 사례("CHOEUN KOREANRESTAURANT")는 샘플 주석에 보인다. [1차: MMOCR sample_anno.md] 카드: [확인 못함]

## 4. MC-OCR 2021 (RIVF 2021, 베트남)

- URL: https://rivf2021-mc-ocr.vietnlp.com/ 는 **현재 DNS가 풀리지 않는다**(2026-09-24). 내용은 Wayback 사본으로 확인했다: http://web.archive.org/web/20251214132642/https://www.rivf2021-mc-ocr.vietnlp.com/dataset . 데이터 배포처는 Codalab https://competitions.codalab.org/competitions/27798 .
- 인용: Vu et al., "MC-OCR Challenge: Mobile-Captured Image Document Recognition for Vietnamese Receipts", RIVF 2021 (IEEE, https://ieeexplore.ieee.org/document/9642077 ; 저자 preprint https://people.cs.umu.se/sonvx/files/MCOCR_Preprint.pdf ). [1차]
- 라이선스: "License Agreement: This is a dataset of VNDAG for research purposes only. You need to sign this user agreement form and send to vndag@vietnlp.com to register before using any data from VNDAG." [1차: Dataset 탭, Wayback] → **연구 목적 한정, 서명 필요, 공개 데모 표시 불가로 판단**.
- 규모: 2,436장. "contributed by nearly 50 active data collectors over two months ... took a photo of the receipt using their mobile phone." [1차: preprint]
- 촬영 방식: 휴대폰 실사진. 전처리 없이 원본 그대로 배포된다. [1차]
- 라벨: `SELLER`, `SELLER_ADDRESS`, `TIMESTAMP`, `TOTAL_COST` 4개 필드의 폴리곤과 텍스트, 이미지 품질 점수(0~1). [1차] 품목과 세금 라벨은 없다.
- 대상 국가: **베트남** (포함). 카드 끝 4자리: [확인 못함].

## 5. XFUND (Microsoft, 다국어 양식 — 영수증 아님)

- URL: https://github.com/doc-analysis/XFUND (릴리스 v1.0)
- 인용: Xu et al., "XFUND: A Benchmark Dataset for Multilingual Visually Rich Form Understanding", Findings of ACL 2022, doi:10.18653/v1/2022.findings-acl.253. [1차]
- 라이선스: "Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)" [1차: README] → 비상업·동일조건 조건이다. 상업 데모에는 쓸 수 없고, 비상업 포트폴리오에 표시할 수 있는지는 해석에 따라 갈린다.
- 규모: 7개 언어(ZH, JA, ES, FR, IT, DE, PT), 언어당 199장(train 149 / test 50), 합계 1,393장. [1차: 논문]
- 생성 방식: 인터넷에서 **양식 템플릿**을 모은 뒤 사람이 **가짜(synthetic) 정보를 채워 넣고**(타이핑 또는 손글씨) 스캔했다. "To avoid the privacy and sensitive information issue with real-world documents ... fill in synthetic information manually." [1차: 논문 §2.1-2.2]
- 라벨: header / question / answer / other 엔티티와 key-value 관계(SER, RE). [1차]
- 대상 국가: 일본어·독일어·스페인어(스페인어가 멕시코 것인지는 [확인 못함]) 양식이 있다. 다만 **영수증이 아니고 내용도 합성**이다. 카드: 해당 없음.

## 6. SVRD (ICDAR 2023, HUST-CELL / Baidu-FEST)

- URL: https://rrc.cvc.uab.es/?ch=21
- 내용: HUST-CELL은 "collected from public websites ... receipt, certificate, and license ... mainly Chinese, along with a small portion of English", 30개 범주에 4k장 이상이다. Baidu-FEST는 카드, 영수증, 양식 위주이며 종류당 약 60장이다. [1차: 소개·Tasks 페이지]
- 라이선스: 페이지에 없음. [확인 못함] 대상 국가(한·베·멕·독·일): 없음(중국어 위주).

## 7. JaWildText — Receipt KIE 서브셋 (일본)

- URL: https://huggingface.co/datasets/llm-jp/jawildtext (config `receipt_kie`)
- 인용: Maeda & Okazaki, "JaWildText: A Benchmark for Vision-Language Models on Japanese Scene Text Understanding", ICDAR 2026 (to appear), arXiv 2603.27942. [1차]
- 라이선스: "JaWildText, including both annotations/metadata and images, is released under the Apache License 2.0." 단 "the license does not grant trademark rights or imply endorsement by any third-party entities visible in the images." [1차: HF 카드] Out-of-scope에 "identifying individuals, writers, stores, or customers"가 있다. 카드에 "TODO: add contact / takedown address"가 남아 있다. [1차]
- 규모: receipt_kie 1,151장(같은 매장 영수증 중복 불가, 같은 체인의 다른 지점은 허용), 텍스트 영역 56,095개. 배포 split은 `train` 하나지만 평가 전용 벤치마크로 의도됐다. [1차: 논문 §3.2, HF 카드]
- 촬영 방식: 일본에서 "photographs of consumer receipts from everyday transactions rather than flatbed scans"이며 구김, 접힘, 손에 든 기울기를 그대로 두었다. 촬영과 주석은 전문 데이터 수집 업체가 맡았다. [1차: 논문]
- 라벨: `store_name`, `store_address`, `receipt_id`, `date`, `time`, `total_amount`, `tax_amount`, `line_items`(item_name, item_price, item_quantity). 필드마다 값과 사각형 박스가 있고, 영수증에 없는 필드는 명시적으로 null이다. 채움률은 store_name·date 100%, total 99.8%, time 98.3%, tax 95.2%, receipt_id 92.0%, store_address 48.9%다. [1차: 논문 Table 3]
- 대상 국가: **일본** (포함).
- 카드 끝 4자리: **"We excluded images containing non-public personally identifiable information, such as faces, vehicle license plates, or credit card numbers"** [1차: 논문 §3.4] → 카드번호가 찍힌 영수증은 설계상 빠졌다. 마스킹된 번호까지 빠졌는지는 [확인 못함]. 어느 쪽이든 카드 끝자리 대조 검증에는 쓸 수 없다고 보는 편이 안전하다.

## 8. Japanese-Mobile-Receipt-OCR-1.3K (일본)

- 출처: TechRxiv preprint doi:10.36227/techrxiv.175616889.90325672 (자동 수집 시 403이라 본문은 [확인 못함])
- 저자 모델 카드(https://huggingface.co/sabaridsnfuji/Japanese-Receipt-VL-3B-JSON )에는 "Japanese-Mobile-Receipt-OCR-1K ... Custom collected real-world Japanese receipts ... 1,147 collected images"라고 되어 있다(이름의 1.3K와 불일치). [1차: 모델 카드]
- **데이터셋 자체는 공개 저장소를 찾지 못했다.** 저자의 HF 데이터셋 목록에도 없다. [1차로 부재 확인] 라이선스: [확인 못함]

## 9. ReceiptSense / CORU (아랍어·영어, 이집트 DISCO 앱)

- URL: https://github.com/Update-For-Integrated-Business-AI/CORU , https://huggingface.co/datasets/abdoelsayed/CORU
- 인용: Abdallah et al., "ReceiptSense: Beyond Traditional OCR -- A Dataset for Receipt Understanding", arXiv 2406.04493. [1차]
- 라이선스: README는 "This dataset is released under the MIT License"이고 HF 메타데이터도 `license:mit`이다. [1차] 다만 README가 가리키는 LICENSE 파일은 저장소에 없다(404). arXiv 페이지의 CC BY 4.0은 **논문 원고의 라이선스**이므로 데이터 라이선스와 구분해야 한다.
- 규모: key-info detection 20,000장, OCR 30,000장, 품목 IE 10,000건, Receipt QA 1,265장. 언어 비율은 아랍어 53.6%, 영어 26.2%, 혼합 20.3%. "All receipts collected with explicit user consent through the DISCO application", 4단계 PII 가림 처리. [1차: README]
- 라벨: 가맹점명, 날짜, 영수증 번호, 품목, 합계(검출 박스), 품목 단위 속성, QA. [1차]
- 대상 국가: 없음.

## 10. HumynLabs/Korean_Receipts_Dataset (한국) — 유일한 한국 공개 샘플

- URL: https://huggingface.co/datasets/HumynLabs/Korean_Receipts_Dataset
- 라이선스: CC BY 4.0. [1차: HF 카드] 다만 카드의 Out-of-Scope에 "Commercial misuse of store or brand data without consent"가 있다.
- 규모: **공개 파일은 JPEG 20장과 README뿐이다**(`Kgen_Korean Receipts_1005_1..20.JPEG`). 태그는 `1K<n<10K`지만 실제 파일은 20장이다. [1차: HF tree API] **주석 파일 없음.**
- 출처 서술: "Field collection, simulated receipts, and crowdsourced images ... photographed or scanned. All personal identifiers (names, addresses, payment info) were removed or anonymized." [1차: 카드] → 실물과 모의(simulated) 영수증이 섞였다고 스스로 밝힌다.
- [1차·육안] 2장(#1 스타필드 코엑스 유니클로 2025-10-03, #7 현대백화점 압구정 2025-10-05)은 탁자 위에서 찍은 **실물 감열지 사진**이다. 사업자번호, 과세물품가액, 부가세, 합계, 승인번호가 찍혀 있다.
- 카드번호 표기(육안): `55986996****800*`, `95000032****517*`. 앞 8자리는 보이고 9~12번째와 **마지막 자리가 가려져 있다**. 즉 이 두 장에서는 "끝 4자리"가 온전히 찍히지 않았다. PRD의 "영수증 양식이 결과를 정한다"는 논점을 뒷받침하는 실물 예다(두 장만 본 관찰이므로 일반화는 [확인 못함]).
- 세금계산서, 계산서, 간이영수증 포함 여부: [확인 못함](20장 전부를 보지는 않았다).

## 11. ExpressExpense SRD (미국 식당)

- URL: https://expressexpense.com/blog/free-receipt-images-ocr-machine-learning-dataset/ , 파일 `large-receipt-image-dataset-SRD.zip` (md5 c8eb0f2d286da5ab742e7a5b59f15147, 받은 파일과 일치)
- 라이선스: "This dataset is free for use under The MIT License (MIT). If you use or reference this dataset, please cite our website as the source: ExpressExpense.com" [1차]
- 규모: 식당 영수증 200장. zip에는 jpg 200개만 있고 **주석 파일은 없다**. [1차: zip 목록]
- 촬영 방식: 페이지는 "scanned images"라고 쓴다. 그런데 [1차·육안] 2장(#1000 Long Beach CA 2016, #1099 San Jose CA 2017)은 **손에 들거나 테이블에 놓고 찍은 실사진**이다. 이 회사가 영수증 생성기(receipt maker) 업체이기도 해서, 200장 전체가 실물인지는 [확인 못함].
- 대상 국가: 미국. #1099는 멕시칸 식당이지만 미국 영수증이다. 카드: 본 2장에는 없음.

## 12. 독일 — 공개 실물 영수증 라벨셋은 찾지 못함. 합성 인보이스만 있음

- **BelegBench** https://huggingface.co/datasets/keyvan-ai/belegbench : Apache-2.0. CH/DE/AT 10,002건이며 "100 % synthetisch". A4 인보이스·Kleinbetragsrechnung(DE ≤250 €) 렌더링과 스캔 열화판, 35개 필드 GT(가맹점, VAT ID, 날짜, 품목, VAT 내역, 합계, IBAN, QR). "Die Ground Truth enthält nur, was auf dem Beleg gedruckt ist"라서 없는 필드는 null이고 환각률을 측정한다. [1차: HF 카드] → 감열지 영수증이 아니고 합성이다.
- **laterrr/belege-de-invoices-sample**: `license: other`(belege-sample-licence), 합성 독일 인보이스 1,000건 중 무료 샘플 40건. [1차: 카드 frontmatter와 본문]
- **albertobarnabo/synthetic-receipts-ocr**: Apache-2.0. "32,000 synthetic thermal receipts across 5 locales (US/UK/DE/IT/FR)"이며, 렌더본마다 사진처럼 열화한 짝과 단어 박스, KIE 필드가 있다. [1차: HF 카드]
- 위 셋은 모두 **합성**이다. 따라서 PRD가 말한 "자체 렌더링만으로는 주장을 입증할 수 없다"는 한계를 그대로 안는다(남이 만든 합성일 뿐이다).

## 13. 멕시코·스페인어 — 공개 실물 영수증 라벨셋은 찾지 못함

- **CUTIE**(Zhao et al., arXiv 1903.12363)는 "self-built dataset contains 4,484 annotated scanned Spanish receipt documents, including taxi receipts, meals entertainment (ME) receipts, and hotel receipts" + 9개 클래스(VendorName, VendorTaxID, InvoiceDate, InvoiceNumber, ExpenseAmount, BaseAmount, TaxAmount, TaxRate)다. [1차: 논문] 출장 경비 도메인과 가장 가깝지만 **배포 링크가 없다**(자체 구축, 비공개로 판단). 국가(스페인/멕시코)는 [확인 못함].
- **BuroIdentidadDigital/recibos_telmex** 등: `license: c-uda`, README 본문 비어 있음. 멕시코 통신사(Telmex) **요금 고지서** 이미지로 보이며 영수증이 아니다. 출처와 개인정보 처리가 불명확하다. [1차: HF API 메타]
- 도미니카 합성 인보이스(puruchinera/FacturaRD-Synth)와 아르헨티나 facturas가 HF에 있지만 멕시코가 아니거나 합성이다. 세부는 [확인 못함].

## 14. AI Hub (한국, NIA)

- 영수증 전용 데이터셋: 카탈로그에서 "영수증"을 검색하면 2건이 나온다(2026-09-24). "동남아시아 고품질 OCR 데이터"(태국어·캄보디아어 손글씨, 설명의 활용 예에 영수증이 한 번 나올 뿐)와 "민원(콜센터) 질의-응답"이며 **영수증 이미지 데이터셋은 없다**. [1차: https://aihub.or.kr/aihubdata/data/list.do?searchKeyword=영수증 , dataSetSn=71956]
- 가까운 것: "OCR 데이터(금융 및 물류)" dataSetSn=71301(2022, 금융 50,000장은 은행 신고서·신청서·확인서·위임장, 보험 서류 / 물류 107,919장은 선하증권, 4점 폴리곤)와 "금융업 특화 문서 OCR 데이터" dataSetSn=632(2021, "금융기관 문서양식에 직접 작성 후 촬영", 50,000장). 둘 다 **영수증·카드전표·세금계산서가 아니다**. [1차: 각 dataSetSn 페이지. "영수증/매출전표/세금계산서" 언급 0회]
- 이용정책(https://aihub.or.kr/intrcn/guid/usagepolicy.do ) [1차]:
  - "국외에 소재하는 법인, 단체 또는 개인이 AI데이터 등을 이용하기 위해서는 수행기관 등 및 한국지능정보사회진흥원과 별도로 합의가 필요합니다."
  - "본 AI데이터 등의 국외 반출을 위해서는 ... 별도로 합의가 필요합니다."
  - "본 AI데이터는 인공지능 학습모델의 학습용으로만 사용할 수 있습니다."
  - "제공 받은 AI데이터 등을 수행기관 등과 한국지능정보사회진흥원의 승인을 받지 않은 다른 법인, 단체 또는 개인에게 **열람하게 하거나** 제공, 양도, 대여, 판매하여서는 안됩니다." → **공개 데모에 이미지를 보여주는 것은 승인 없이 불가**하다.
  - 출처 표기 의무: "반드시 한국지능정보사회진흥원의 사업결과임을 밝혀야".
  - "내국인만 신청 가능" 문구는 이 정책 페이지에서 찾지 못했다. [확인 못함] 국외 소재자는 별도 합의가 필요하다는 조항만 [1차]로 확인했다.

## 15. 기타 (간단)

- **UIT-MLReceipts**(베트남·영어 2,147장, 가게 영수증과 소셜미디어 이미지): 논문(ResearchGate)과 배포처를 1차로 열지 못했다. 라이선스와 배포 여부는 [확인 못함]. 수치는 ReceiptSense README 비교표 기준 [2차].
- **UniqueData/ocr-receipts-text-detection**: CC BY-NC-ND 4.0, 판매 데이터의 샘플("For Commercial Usage ... buy the dataset"), 식료품점 영수증 사진과 박스. [1차: 카드] 대상 국가: [확인 못함].
- **Voxel51/scanned_receipts**(SROIE 712 샘플 FiftyOne 미러, cc-by-4.0 표기): [2차] 미러이므로 라이선스 근거로 쓰면 안 된다.
- 호텔 폴리오, 항공 e-ticket, 택시 영수증을 따로 모은 공개셋은 찾지 못했다(CUTIE의 taxi/hotel 영수증은 비공개).

---

## 평가 계획에 걸리는 관찰 (사실 요약, 권고 아님)

1. **대상 5개국 중 공개·주석 있는 실물 영수증이 있는 곳은 일본(JaWildText)과 베트남(MC-OCR, 연구 한정)뿐이다.** 한국은 주석 없는 20장, 독일은 합성뿐이고, 멕시코는 찾지 못했다.
2. **한국 세금계산서, 계산서, 신용카드 매출전표를 주석과 함께 제공하는 공개셋은 찾지 못했다.** AI Hub에도 영수증 데이터셋이 없고, 있더라도 열람 제한 때문에 공개 데모에 쓸 수 없다.
3. **카드 끝 4자리 검증에 쓸 수 있는 공개셋이 없다.** CORD는 payment_info를 뺐고, SROIE는 4개 필드뿐이며, JaWildText는 카드번호가 찍힌 이미지를 제외했다. HumynLabs 한국 실물 2장은 카드번호가 `앞8자리 + **** + 3자리 + *` 형식이라 끝 4자리가 온전히 찍히지 않았다. 이 점은 PRD의 "양식이 결과를 정한다"를 실물로 보여 준다.
4. 공개 데모에 이미지를 표시해도 되는 라이선스: CORD(CC BY 4.0), JaWildText(Apache-2.0), ExpressExpense(MIT), ReceiptSense(MIT, LICENSE 파일 없음), HumynLabs(CC BY 4.0). 이 가운데 JaWildText와 HumynLabs에는 상표와 개인 식별에 관한 자체 주의 문구가 있다. 불가 또는 불명: SROIE(라이선스 없음), WildReceipt(N/A, 웹 스크랩), MC-OCR(연구 한정·서명), XFUND(NC-SA), AI Hub(열람 금지).
5. 수치 불일치 기록: SROIE 1,000(논문) vs 973(RRC SVRD 페이지), WildReceipt 1,740(본문) vs 1,768(Table I), Japanese-Mobile-Receipt "1.3K" vs 1,147(모델 카드).

---

## 요약표

| 데이터셋 | 라이선스 | 지역/언어 | 규모 | 라벨 | 실물/합성 | 대상국 | 공개 데모 표시 |
|---|---|---|---|---|---|---|---|
| CORD v2 | CC BY 4.0 [1차] | 인도네시아 | 1,000 | 메뉴·소계·세금·합계·결제수단 금액, 박스 (가맹점·날짜 없음) | 실물(촬영 방식 확인 못함) | 없음 | yes |
| SROIE | 명시 없음 [1차 부재], 가입 필요 | 영어(국가 확인 못함) | 1,000 (973 표기도) | company·date·address·total + 단어 박스 | 실물 스캔 | 없음 | unclear |
| WildReceipt | N/A [1차] | 영어 | 1,740 / 1,768 | 25 key/value 범주(세금·팁·품목 포함) + 박스 | 실물(웹 스크랩) | 없음 | unclear(사실상 no) |
| MC-OCR 2021 | 연구 한정, 서명 필요 [1차] | 베트남 | 2,436 | seller·address·timestamp·total + 품질 점수 | 실물 휴대폰 촬영 | 베트남 | no |
| XFUND | CC BY-NC-SA 4.0 [1차] | zh/ja/es/fr/it/de/pt | 1,393 (언어당 199) | 양식 key-value(SER/RE) | 합성 내용 채운 양식 스캔 (영수증 아님) | 일본·독일·스페인어(양식) | unclear(비상업이면 가능) |
| SVRD (HUST-CELL) | 확인 못함 | 중국어 위주 | 4k+ | 엔티티 연결·라벨 | 웹 수집 | 없음 | unclear |
| JaWildText receipt_kie | Apache-2.0 [1차] | 일본 | 1,151 | store·address·receipt_id·date·time·total·tax·line_items + 박스, null 명시 | 실물 휴대폰 촬영 | 일본 | yes (상표·식별 주의) |
| Japanese-Mobile-Receipt-OCR-1.3K | 확인 못함 | 일본 | 1,147? | 확인 못함 | 실물 | 일본 | no(공개 저장소 없음) |
| ReceiptSense/CORU | MIT [1차, LICENSE 파일 없음] | 아랍어·영어(이집트) | 20k / 30k / 1,265 QA | 가맹점·날짜·번호·품목·합계 박스, QA | 실물(동의·PII 가림) | 없음 | yes |
| HumynLabs Korean Receipts | CC BY 4.0 [1차] | 한국 | 20(공개 파일) | 없음 | 실물+모의 혼합(자체 서술) | 한국 | yes (주석 없음) |
| ExpressExpense SRD | MIT [1차] | 미국 식당 | 200 | 없음 | 실물 사진(2장 육안) | 없음 | yes |
| BelegBench | Apache-2.0 [1차] | DE/AT/CH | 10,002 | 35필드 GT, null 규칙 | 100% 합성 인보이스 | 독일(합성) | yes |
| CUTIE Spanish receipts | 비공개 | 스페인어 | 4,484 | vendor·taxID·date·number·amount·tax | 실물 스캔 | 확인 못함 | no |
| AI Hub 금융 OCR (71301/632) | AI Hub 정책: 열람·제공 금지, 국외 별도 합의 [1차] | 한국 | 50k / 158k | 4점 폴리곤·텍스트 | 은행·보험 서류 (영수증 아님) | 한국(영수증 아님) | no |
