# Sea-Info Agent v0.2 · 실제 API + SQLite

Render에서 `No open ports detected`가 나오면 [Render 배포 설정](docs/Render_배포설정.md)의 Root Directory와 Start Command를 확인하세요. 기본 실행 명령은 `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`입니다.

가짜 물때·로컬 생물 목록을 제거하고, 실제 외부 API와 SQLite 영구 저장을 연결한 FastAPI 대시보드입니다. 로컬 단일 사용자 학습용입니다.

**2026-10-27 실제 연결 검증 완료:** 사용자 제공 KHOA 인증키를 로컬 `.env`에 설정하고, 누락되어 있던 `.env` 로딩 코드를 추가했습니다. 인천·부산·제주의 조석·관측, 해양 모델 예보, 조회 이력 저장을 실제 응답으로 확인했습니다. 테스트 26개와 JavaScript 구문 검사도 통과했습니다. 아래의 2026-10-23 기록은 당시 결과이며, 최신 결과는 [실제 API 검증 보고서](docs/KHOA_실제API_검증결과_2026-10-27.md)를 참고하세요. 사진 분석용 키의 실제 검증은 별개입니다.

## 지금 사용할 수 있는 기능

| 기능 | 데이터 출처 | 필요한 설정 |
|---|---|---|
| 만조·간조 시각과 조위 | 국립해양조사원 조석예보(고, 저조) | 공공데이터포털 활용신청·인증키 |
| 실측 수온·조위·풍속·기온 | 국립해양조사원 조위관측소 최신 관측데이터 | 해당 API 활용신청·인증키 |
| 시간별 파고·해수면 온도 예보 | Open-Meteo Marine API | 비상업 학습용 공개 API, 별도 키 없음 |
| 해양생물 검색·상세 | WoRMS 해양생물 DB | 공개 API, 별도 키 없음 |
| 사진 분석·학명 대조 | OpenAI 이미지 분석 + WoRMS | OpenAI API 키·지원 모델 |
| 관찰 기록·검색 이력·분석 사진 | 로컬 SQLite | 자동 생성 |

인증키가 없거나 데이터 수신에 실패하면 상태 메시지를 보여주며 예시 데이터로 바꾸지 않습니다. 키가 없어도 공개 생물 검색·해양 모델 예보·SQLite 저장을 사용할 수 있습니다. 키가 필요하다는 상태를 포함한 부분 조회 결과도 조회 당시의 상태로 저장됩니다.

## 1. 설치 및 실행

PowerShell:

```powershell
cd C:\KBR\sea_info_dashboard
# 기존 .venv가 없다면 생성합니다.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 기존 .env를 덮어쓰지 않고 처음에만 만듭니다.
if (!(Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

기존 가상환경이 있으면 `python -m venv .venv`는 생략합니다. 이번 작업에서는 필요한 패키지를 프로젝트 `.venv`에 설치했습니다.

- 대시보드: http://127.0.0.1:8001
- API 문서: http://127.0.0.1:8001/docs
- 연결 설정 상태: http://127.0.0.1:8001/api/status

`.env`는 서버 시작 시 읽습니다. 값을 변경한 뒤에는 터미널의 서버를 Ctrl+C로 종료하고 다시 실행하세요. 화면의 '키 설정됨'은 키가 입력되었다는 뜻이며 실제 활용승인이나 인증 성공을 보증하지 않습니다.

## 2. 국립해양조사원 API 키 발급

공공데이터포털에 로그인해 다음 **두 API를 각각 활용신청**합니다.

1. [조석예보(고, 저조)](https://www.data.go.kr/data/15156018/openapi.do)
2. [조위관측소 최신 관측데이터](https://www.data.go.kr/data/15155508/openapi.do)

각 상세 페이지의 '활용신청'에서 개발 목적과 활용 내용을 입력하고 승인 상태를 확인합니다. 이후 마이페이지의 활용 중인 Open API에서 인증키를 확인해 `.env`에 입력합니다. 현재 포털 화면의 메뉴 이름은 계정·페이지 개편에 따라 달라질 수 있습니다.

```dotenv
KHOA_API_KEY=본인의_일반인증키_Decoding
```

두 서비스의 키가 다른 경우에만 다음 항목을 사용합니다. 빈 값이면 공통 `KHOA_API_KEY`를 사용합니다.

```dotenv
KHOA_TIDE_API_KEY=조석예보용_키
KHOA_OBSERVATION_API_KEY=최신관측용_키
```

Decoding 키를 권장합니다. Encoding 키를 입력하면 코드가 URL 디코딩을 한 번 적용하고 HTTP 클라이언트가 파라미터를 인코딩합니다. 동일한 키라도 해당 API의 활용신청이 승인되지 않았으면 호출이 거부될 수 있습니다. 키를 채팅·Git·화면 JavaScript에 넣지 마세요. `.env`와 `data/`는 `.gitignore`에 포함했습니다.

### 공식 요청·응답 연결

- 조석: `https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService`
- 관측: `https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService`
- 공통 요청: `serviceKey`, `obsCode`, `reqDate=yyyyMMdd`, `type=json`, `pageNo`, `numOfRows`(최대 300)
- 관측 API에만 `min=1`을 명시합니다(가이드 기본값 1분, 최대 60분). 조석 API에는 보내지 않습니다.
- 조석 필드: `obsvtrNm`, `predcDt`, `predcTdlvVl`(cm), `extrSe`
- `extrSe`: 1·3 고조, 2·4 저조. 이 숫자를 조위나 시각 크기로 추측하지 않습니다.
- 관측 필드: `obsvtrNm`, `obsrvnDt`, `wtem`(°C), `bscTdlvHgt`(cm), `wspd`(m/s), `artmp`(°C)
- 추가 관측 필드: `slntQty`(psu), `atmpr`(hPa), `wndrct`(deg), `maxMmntWspd`(m/s). 미제공 항목은 `null`로 반환하고 화면에 `—`를 표시합니다.

공식 공개 Swagger 명세를 확인해 구현했습니다. JSON의 `response` 래퍼 유무, item 단건/목록, 페이지 구분을 처리합니다. 선택한 날짜·관측소 이름이 응답과 다르면 잘못된 지역 자료를 보여주지 않고 오류 상태를 반환합니다.

2026-10-26 첨부 HWP 활용가이드 두 종(v1.0, 배포일 2025-12-12)을 대조했습니다. 기존 주소·조석 필드·극치 구분은 일치했습니다. `min` 명시, 추가 관측 필드, XML 응답 처리, 오류 코드별 안내를 보완했습니다. 상세 변경 이유와 키 설정 후 점검 방법은 [문서 분석·코드 수정 내역](docs/KHOA_활용가이드_분석과수정내역.md)을 참고하세요. `type=json`을 기본으로 요청하고, KHOA에서 XML 본문을 반환하면 XML 예제 구조 또는 포털 오류 구조를 해석합니다. 인증 오류·요청 한도 초과·관측소/항목 일시 중지를 구분하며 제공자의 오류 원문은 그대로 노출하지 않습니다.

| 화면 지역 | 관측소·예보지점 코드 | 이름 |
|---|---|---|
| 인천 | DT_0001 | 인천 |
| 부산 | DT_0005 | 부산 |
| 제주 | DT_0004 | 제주 |

관측값은 선택일의 마지막 수신 시각과 함께 표시합니다. 오늘 자료가 2시간 이상 지연된 경우 표시하며, 미래 날짜의 실측 자료는 제공하지 않습니다. 모델 예보 대표 좌표와 관측소 위치는 다른 기준입니다. 만조·간조는 첫 번째 사건을 표시하며 '지금 이후 다음 만조'를 뜻하지 않습니다.

## 3. 실제 생물 DB 검색

[WoRMS](https://www.marinespecies.org/)는 해양생물의 학명·분류·동의어·인정 학명 등을 제공하는 실제 DB입니다. 이 프로젝트는 [공식 REST API](https://www.marinespecies.org/rest/)를 호출합니다.

- 학명: `AphiaRecordsByName/{ScientificName}`
- 일반명: `AphiaRecordsByVernacular/{Vernacular}`
- 상세: `AphiaRecordByAphiaID/{ID}`
- 일반명·분포: `AphiaVernacularsByAphiaID/{ID}`, `AphiaDistributionsByAphiaID/{ID}`

검색 예: `바지락`, `꽃게`, `돌기해삼`, `고등어`, `Ruditapes`, `Haliotis`. 결과의 상세 버튼을 누르면 분류 체계·인정 학명·일반명·분포를 보고 원문 링크로 이동할 수 있습니다. DB에 등록되지 않은 추가 정보는 생성하지 않습니다.

WoRMS는 국문 생태도감 전체가 아니라 해양생물 분류 DB입니다. 한국어 일반명의 등록 범위가 제한되어 있어 일부 국명은 `species_service.py`의 검색어 사전에서 학명으로 변환합니다. 이것은 결과를 로컬에서 꾸며내는 것이 아니라 **변환한 학명으로 실제 API를 검색하는 보조 기능**입니다. 예를 들어 전복→Haliotis는 상위 분류군 검색이며 특정 종 확정이 아닙니다. 검색은 최대 20건을 표시합니다. `accepted`와 `unaccepted` 상태 및 인정 학명도 확인하세요.

이 DB는 식용 허가·무독성 보증 DB가 아닙니다. 생태 설명·종 사진은 제공자가 공개한 원문을 확인하는 방식이며 앱에서 자동 생성하지 않습니다. 완전한 국문 도감이 필요하면 추후 국내 기관의 별도 API를 연결해야 합니다.

## 4. 사진 업로드 분석 설정

[OpenAI API 키 관리 화면](https://platform.openai.com/api-keys)에서 본인 계정의 서버용 키를 발급해 `.env`에 입력합니다. API 이용에 필요한 결제·사용 한도는 본인 계정에서 확인합니다. ChatGPT 구독과 API 사용량은 별개입니다.

```dotenv
OPENAI_API_KEY=본인의_API_키
OPENAI_MODEL=gpt-4.1-mini
```

모델 이름은 예시입니다. 계정에서 사용 가능하고 이미지 입력 및 Responses 구조화 출력을 지원하는 모델을 설정하세요. 문서: [이미지 입력](https://developers.openai.com/api/docs/guides/images-vision), [구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs).

화면에서 사진을 선택하고 외부 전송·SQLite 저장 동의를 체크한 뒤 '사진 분석하기'를 누릅니다. 사진을 선택하는 것만으로 외부 전송하지 않습니다.

```text
10 MiB / 2천만 픽셀 / 실제 이미지 형식 검사
→ 회전 보정·최대 2048px·메타데이터 없는 JPEG 변환
→ OpenAI에 전달해 종 후보·특징·식별 한계를 구조화된 JSON으로 받음
→ 후보 학명의 WoRMS 등록 여부를 정확히 대조
→ 결과 JSON + 변환한 JPEG + SHA-256을 SQLite에 저장
```

지원 파일은 정적 JPEG/PNG/WEBP입니다. multipart 전체 요청도 11 MiB로 제한합니다. 흐린 사진이나 특징이 부족한 경우 식별을 보류하며, 모델이 제시하는 외형 일치 수준은 검증된 정확도 확률이 아닙니다. WoRMS에 학명이 있다는 사실은 사진 속 개체의 종 판별이 정확하다는 검증이 아닙니다.

`store=False`로 API를 호출하지만 외부 API 처리나 제공자의 정책상 로그 보존이 사라진다는 뜻은 아닙니다. 분석 사진은 EXIF를 제거한 JPEG로 로컬 SQLite에 저장되며 원본 바이트·원본 파일명·API 키는 저장하지 않습니다. 사진만으로 독소·오염·부패 등 개체의 섭취 안전성을 판정하지 않습니다.

## 5. SQLite 저장 구조

기본 DB: **`C:\KBR\sea_info_dashboard\data\sea_info.sqlite3`**

첫 서버 시작 시 자동 생성됩니다. 관찰 기록과 조회 이력은 서버를 재시작해도 유지됩니다. 학습용 로컬 파일이므로 사용자 계정별 접근 제어는 포함하지 않았습니다.

| 테이블 | 저장 내용 |
|---|---|
| `records` | 관찰 제목·지역·날짜·메모·즐겨찾기 |
| `history` | 조회 종류·검색 조건·조회 시각·결과 JSON·상태·분석용 JPEG |

다음 작업을 자동 저장합니다: 바다 정보 조회, 생물 검색, 생물 상세 조회, 성공한 사진 분석. 생물 검색 오류도 상태를 남깁니다. 저장 이력에서 '열기'를 누르면 당시 응답을 다시 확인합니다. 이력 조회는 외부 API를 재호출하지 않습니다. 저장된 예보는 조회 당시 자료이며 현재 예보로 취급하지 않습니다. SQLite를 재사용하거나 파일을 옮길 때 사진과 메모도 포함된다는 점을 고려하세요.

확인용 SQL:

```sql
SELECT id, kind, title, status, created_at FROM history ORDER BY id DESC;
SELECT id, payload FROM records ORDER BY id DESC;
SELECT id, length(image_jpeg) AS jpeg_bytes FROM history WHERE image_jpeg IS NOT NULL;
```

SQL은 파라미터 바인딩으로 작성했습니다. 사진 base64나 인증키를 결과 JSON에 저장하지 않습니다. 관찰 기록 PATCH는 기존 값과 변경분을 병합하고 Pydantic으로 재검증한 뒤 트랜잭션으로 저장합니다.

## 6. 코드 읽는 순서

```text
models.py          데이터 규칙과 응답 모델
services.py        국립해양조사원·해양 예보 API 요청과 파싱
species_service.py WoRMS 검색·상세·분류 정보
image_service.py   이미지 검증·OpenAI 분석·DB 대조
database.py        SQLite 초기화·CRUD·조회 이력 저장
main.py            API 주소·서비스·저장 연결
static/            화면과 fetch 요청
```

수업 개념은 `BaseModel`/`Field`→요청 검증, 중첩 모델→통합 대시보드 응답, `model_validator`→외부 배열·단위 검사, `model_dump`→JSON 직렬화, `exclude_unset`→부분 수정, `sqlite3`→영구 저장으로 이어집니다.

주요 API:

| 메서드 | 경로 | 역할 |
|---|---|---|
| GET | `/api/status` | 키 설정 여부·저장 방식 |
| GET | `/api/dashboard?region=incheon&target_date=2026-10-23` | 공식 물때·실측·모델 예보와 이력 저장 |
| GET | `/api/species?q=바지락` | 실제 DB 검색과 이력 저장 |
| GET | `/api/species/231750` | WoRMS 상세와 이력 저장 |
| POST | `/api/analyze` | multipart `file` + `consent=true` |
| GET | `/api/history?limit=10&offset=0` | 저장 이력 목록 |
| GET | `/api/history/{id}` | 당시 결과 JSON |
| GET | `/api/history/{id}/image` | 저장된 분석용 JPEG |
| GET/POST | `/api/records` | 관찰 기록 목록·생성 |
| GET/PATCH/DELETE | `/api/records/{id}` | 단건 조회·수정·삭제 |

## 검증 및 현재 한계

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

실제 WoRMS 바지락 검색·상세와 Open-Meteo 예보 호출을 확인했습니다. SQLite는 연결과 앱을 다시 연 뒤에도 기록·이력이 유지되는지 테스트합니다. 국립해양조사원은 **사용자 인증키가 아직 없어 공개 Swagger 계약과 모의 응답으로 검증**했습니다. 실제 인증·관측 데이터 수신 확인은 키 설정 뒤 필요합니다. OpenAI도 **사용자 키가 없어 모의 응답으로 업로드·분석 결과·이미지 저장 흐름을 검증**했으며 실제 사진 식별 정확도와 유료 API 인증은 아직 검증하지 못했습니다.

외부 API 오류를 정상 데이터로 보이지 않게 상태를 분리했습니다. 다수 데이터 제공자가 서로 다른 시각·좌표를 쓰므로 하나의 '현재 바다 안전도' 점수로 합치지 않습니다. 공공 데이터와 WoRMS·Open-Meteo의 이용·출처표시 조건은 각 공식 사이트를 따르세요. 외부 공개 서비스로 운영할 경우 사용자 인증·사용량 제한·데이터 보관 정책을 추가해야 합니다.

2026-10-23 검증 결과: 테스트 17개 및 JavaScript 구문 검사 통과. 브라우저에서 실제 바지락 검색·분류/일반명/분포 상세·저장 이력 열기를 확인했고 서버를 재시작한 뒤 기존 이력이 남아 있음을 확인했습니다. `preview-live.png`는 실제 WoRMS 검색 화면입니다. 물때·관측과 OpenAI의 실제 인증 검증은 키 발급 이후 남아 있습니다.
