# 02. 오픈 API 연결과 검증

작성일 기준 공식 자료를 참고한 연결 계획이다. 아래 우선순위는 이 프로젝트를 위한 제안이다. 신청 승인·호출 한도·이용 조건은 실제 연결 시 다시 확인한다.

## 1. 연결 순서와 데이터 역할

| 순서 | 출처 | 앱에서의 역할 | 현재 상태·인증 | 공식 자료 |
|---|---|---|---|---|
| 1 | WoRMS | 학명·분류·동의어 확인 | 연결 코드 있음, 공개 REST | [REST](https://www.marinespecies.org/rest/) |
| 2 | Open-Meteo Marine | 시간별 파고·해수면 온도 모델 예보 | 연결 코드 있음, 공개 API 이용 조건 확인 | [Marine 문서](https://open-meteo.com/en/docs/marine-weather-api) |
| 3 | 국립해양조사원 조석예보 | 만조·간조 시각·조위 | 연결 코드 있음, 별도 활용신청·키 필요 | [조석예보](https://www.data.go.kr/data/15156018/openapi.do) |
| 4 | 국립해양조사원 관측 | 관측소 수온·조위·바람 등 | 연결 코드 있음, 별도 활용신청·키 필요 | [최신 관측데이터](https://www.data.go.kr/data/15155508/openapi.do) |
| 5 | 식품영양성분 데이터 | 김 등 식품의 영양성분 비교 | 미구현, 데이터셋·인증 방식 선정 필요 | [표준데이터](https://www.data.go.kr/data/15100064/standard.do), [공식 Open API 안내](https://various.foodsafetykorea.go.kr/nutrient/industry/openApi/info.do) |
| 6 | MBRIS | 국내 해양생물 자료 보강 | 조사 후보, 구체 API·재사용 조건 미확정 | [시스템 소개](https://www.mbris.kr/pub/about/mbrisis/mbrisis.do) |

WoRMS는 학명·분류를 확인하는 자료다. 식용 가능성·개체의 독소 상태를 보증하는 데이터로 사용하지 않는다. Open-Meteo의 모델 예보와 국립해양조사원 관측값은 위치와 생산 방식이 다르므로 카드와 설명을 구분한다. 공개 API라도 상업 이용·출처 표시·요청량 조건은 제공자 문서를 확인한다.

기상특보는 후속 조사 대상으로 둔다. 기상청의 [공식 데이터 제공목록](https://www.weather.go.kr/down/public_data/public_data_list.pdf)에서 필요한 특보·해양 자료를 선정한 뒤 서비스 상세 명세를 확인한다. 현재 문서에서는 미확정 엔드포인트나 변수를 실행 가능한 코드처럼 제시하지 않는다.

## 2. 국립해양조사원 연결 작업

1. 위 조석예보와 관측데이터 상세 페이지에서 **두 서비스를 각각** 활용신청한다.
2. 승인 상태와 상세 페이지의 최신 명세를 확인한다.
3. 프로젝트의 `.env.example`을 확인하고, `.env`가 없을 때만 복사한다.
4. 로컬 `.env`의 `KHOA_API_KEY`에 본인 키를 입력한다. 두 키가 다르면 `KHOA_TIDE_API_KEY`, `KHOA_OBSERVATION_API_KEY`를 사용한다. 현재 코드는 Decoding 키 사용을 권장하고 Encoding 키는 한 번 디코딩한다.
5. 서버를 재시작한다. `/api/status`의 설정 여부와 실제 `/api/dashboard` 응답을 각각 확인한다.

```powershell
Set-Location C:\KBR\sea_info_dashboard
if (!(Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

패키지가 설치되지 않았다면 기존 프로젝트 README의 설치 절차를 먼저 따른다. 실행 후 [API 문서](http://127.0.0.1:8001/docs)에서 `GET /api/dashboard`를 선택하고 `region=incheon`, `target_date=오늘의 YYYY-MM-DD`로 실행한다. `--reload`는 개발할 때 사용한다.

현재 코드의 요청 주소는 `services.py`의 `TIDE_URL`, `OBS_URL`이다. 요청 변수는 `serviceKey`, `obsCode`, `reqDate`, `type`, `pageNo`, `numOfRows`이며, 화면 날짜를 `YYYYMMDD`로 변환한다. 이 내용은 **현재 구현 설명**이다. 실응답이 다르면 공식 명세와 비교한 후 파서를 수정한다.

## 3. 정상 연결의 확인 기준

| 확인 항목 | 완료 기준 |
|---|---|
| 인증 | 키 입력 표시뿐 아니라 제공자의 실제 정상 응답 확인 |
| 지점 | 요청 관측소와 응답 지점이 일치 |
| 날짜·시간 | 요청 날짜와 자료 날짜 일치, 화면에 KST 표시 |
| 단위 | 조위 cm, 파고 m, 온도 °C 등 원문과 화면 일치 |
| 결측 | 누락·결측 코드를 0으로 표시하지 않음 |
| 부분 실패 | 물때 오류 시에도 생물 검색·기록 CRUD 가능 |
| 보관 | 키를 제외한 결과·조회 조건·조회 시각 기록 |

첫 실호출은 한 지점·한 날짜만 비교한다. 정상 응답 확인 뒤 부산·제주를 추가 점검한다. 성공한 응답에서 키와 민감 정보를 제거한 표본을 별도 테스트용 자료로 만들면 응답 변경에 대응하기 쉽다.

## 4. 오류를 좁히는 순서

- `not_configured`: 로컬 환경 변수 이름, `.env` 위치, 서버 재시작 여부 확인.
- 인증 거절: 해당 서비스 활용승인과 키 인코딩 확인. 공통 키라도 두 서비스 모두 승인되었는지 확인.
- HTTP 200인데 오류 본문: 제공자의 결과 코드와 본문을 검사. HTTP 성공만으로 데이터 정상 판정 금지.
- `no_data`: 날짜 범위·관측소·제공 지연 확인. 미래 실측을 요구했는지 확인.
- 시간 초과: 제공자 공지와 네트워크 확인. 제한된 재시도와 사용자 재조회 버튼 설계.
- 예보와 실측 차이: 지점·시각·수심·변수 정의를 비교. 곧바로 오류로 간주하지 않음.

현재 `get_json()`에는 시간 제한이 있으나 자동 재시도와 캐시는 후속 작업이다. 우선 GET 요청에 한해 짧은 재시도 횟수를 정하고, 제공자별 제한을 확인한 뒤 적용한다. 유료 사진 분석은 중복 과금 가능성을 고려해 무조건 재시도하지 않는다.

## 5. 식품영양성분 연결의 작은 실습

공식 DB는 [검색](https://www.foodsafetykorea.go.kr/fcdb/detail/search/list.do)과 [다운로드](https://various.foodsafetykorea.go.kr/nutrient/general/down/list.do)도 제공한다. 먼저 김 관련 항목 5개를 찾아 실제 컬럼과 단위를 확인하고, 이후 API를 선택한다.

저장 후보는 `provider_food_id`, 식품명, 생것/건조/조미 구분, 기준량·단위, 영양성분 값·단위, 제공기관, 데이터 버전, 출처 URL이다. 학명 ID와 식품 ID는 별도 관리한다. 같은 “김”이라는 이름만으로 종·품종·식품 코드를 자동으로 하나에 합치지 않는다.

완료 기준: 생김과 마른김의 식품 항목을 분리하고, 결측을 0으로 처리하지 않으며, 같은 기준으로 비교 가능한 데이터만 나란히 표시한다. 기능성 연구 결과는 일반 영양성분 표와 별도 자료로 관리한다.
