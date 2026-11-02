# Render HistoryDetail ImportError 수정

2026-10-29 배포 커밋 `5f37c52c461144f11fe9c649c5bada571f9f2b38`을 확인했다.

## 원인

Root Directory 변경 후 최신 `main.py`와 `database.py`가 실행되지만, 같은 `sea_info_dashboard/`의 `models.py`, `services.py`, `requirements.txt`는 예전 메모리 저장·데모 버전이었다. 최신 DB 모듈이 요구하는 `HistoryDetail`이 예전 모델에는 없어 import 중 종료됐다. 이는 포트 감지 이전의 시작 오류다.

`HistoryDetail` 하나만 추가하면 `ObservationInfo`, `SpeciesSearch`, `VisionResult`와 `api_key` 등 다른 누락으로 다시 실패할 수 있다. 세 파일을 서로 맞는 실제 API·SQLite 버전으로 함께 교체한다.

| 파일 | 복구 내용 |
|---|---|
| `sea_info_dashboard/models.py` | 조회 이력·생물 검색·사진 분석·관측 응답 모델과 실제 API 상태 정의 |
| `sea_info_dashboard/services.py` | KHOA 조석·관측 호출, 키 읽기, 예보 통합, JSON/XML·오류 처리 |
| `sea_info_dashboard/requirements.txt` | 기존 4개 외 openai, Pillow, python-multipart, python-dotenv 의존성 복구 |

수정하는 세 파일에 인증키를 넣지 않는다. 로컬 환경 파일 로더는 프로젝트 옆 `.env`를 읽되 운영 환경 변수의 값을 유지한다. Render에서는 Environment의 `KHOA_API_KEY`를 사용한다.

## 검증

배포 커밋에서 내려받은 `main.py`, `database.py`, 이미지·생물 서비스, 정적 화면, 기존 테스트에 수정한 세 파일을 적용한 별도 디렉터리에서 검증했다. `.env`, 기존 개인 DB, 중첩된 예전 앱은 포함하지 않았다.

- 해당 커밋의 자동 테스트 25개 통과.
- Render와 같은 Uvicorn 실행 형식으로 임시 포트에서 시작 성공.
- `/`, `/docs`, `/api/status`, `/static/app.js`, `/static/style.css` HTTP 200.
- 검증용 서버는 종료했다.

이 결과는 로컬 수정본 검증이며 Render의 배포 성공을 뜻하지 않는다. 외부 API를 호출해 키를 재검증하는 작업도 포함하지 않는다. Python 3.12의 깨끗한 Render 빌드에서는 복구된 requirements로 의존성을 다시 설치해야 한다.

## 배포 설정

수정안을 main에 반영한 뒤 아래 설정으로 빌드부터 재배포한다.

```text
Root Directory: sea_info_dashboard
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

성공 기준은 `Application startup complete`, `Uvicorn running ...`와 배포 URL의 홈페이지·`/api/status` 응답이다. 빌드 로그에서 Pillow·python-multipart·openai 등도 설치되는지 확인한다. 기존 4개만 설치된다면 다른 경로나 이전 커밋의 requirements를 쓰는지 확인한다.
