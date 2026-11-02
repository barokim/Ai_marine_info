# Render 포트 감지 오류 해결

작성일: 2026-10-29

`No open ports detected`는 Render가 수신 중인 웹 서버의 포트를 찾지 못했다는 뜻이다. 이 메시지만으로는 원인을 확정할 수 없다. 서버 시작 명령·바인딩 주소를 먼저 확인하고, 메시지 위쪽의 실행 명령과 Python 오류를 함께 확인한다.

## 2026-10-29 실제 배포 로그에서 확인한 원인

Render가 체크아웃한 `barokim/sea-info_dashboard`의 커밋 `a857dc14a4327a0a3e27e1ab900ce022a6d4f920`을 GitHub에서 확인했다. 로그의 실행 파일은 `marienebio_info_agent/main.py`이며 그 옆에는 `static/`가 없다. 앱을 불러오는 시점에 `RuntimeError: Directory .../marienebio_info_agent/static does not exist`가 발생해 서버가 종료됐다. 포트 감지 실패는 그 결과다.

같은 커밋의 `sea_info_dashboard/`에는 최신 앱의 `main.py`, `requirements.txt`, `database.py`, `image_service.py`, `species_service.py`, `static/index.html`, `static/app.js`, `static/style.css`, `static/live.css`가 있다. 이 배포에 적용할 값은 다음과 같다.

| 설정 | 값 |
|---|---|
| Repository | `barokim/sea-info_dashboard` |
| Branch | `main` |
| Root Directory | `sea_info_dashboard` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m uvicorn main:app --host 0.0.0.0 --port $PORT` |

Root Directory를 `marienebio_info_agent`에서 `sea_info_dashboard`로 변경하고 빌드부터 재배포한다. 이때 최신 앱에 필요한 Pillow·python-multipart·python-dotenv·openai 등도 새 작업 디렉터리의 requirements에서 설치되어야 한다. 이번 해결을 위해 빈 static 폴더를 만들거나 예전 앱의 경로를 다른 앱 화면으로 바꾸지 않는다.

위 설정은 확인된 GitHub 커밋 구조에 따른 안내이며 Render 계정의 설정을 직접 변경한 것은 아니다. 로컬 서버는 시작하지 않았다.

## Render 설정

서비스 유형은 Python Web Service로 선택한다. FastAPI가 있는 디렉터리를 Root Directory로 지정한다.

| GitHub 저장소의 구성 | Root Directory |
|---|---|
| 저장소 최상위에 최신 `main.py`, `requirements.txt`, `static/`가 있음 | 비워 둠 |
| 저장소 안 `sea_info_dashboard/`에 위 파일들이 있음 | `sea_info_dashboard` |

현재 로컬의 `marienebio_info_agent/`에는 별도의 예전 앱 파일도 있다. 최신 API·SQLite 앱을 배포하려면 `database.py`, `image_service.py`, `species_service.py`와 `static/`를 포함한 현재 `sea_info_dashboard/` 내용을 사용한다. 기존 GitHub 저장소의 상태와 Render 설정을 자동 확인하거나 변경한 것은 아니다.

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

Render의 Start Command 입력란에 넣는 Linux 명령이다. 로컬 PowerShell에서 그대로 실행하는 명령이 아니다. 운영 실행에는 `--reload`를 붙이지 않는다. Health Check Path가 필요하면 외부 API를 호출하지 않는 `/api/status`를 사용한다. 이 경로의 키 설정 표시는 인증 성공과는 별개다.

공식 문서: [Render Web Services — Port binding](https://render.com/docs/web-services#port-binding). `0.0.0.0`에서 수신해야 하며 `PORT` 환경 변수 사용을 권장한다. 기본 포트는 10000이다.

## 이번 코드 변경

기존 `main.py`는 `python main.py` 실행 시 앱만 정의하고 종료했다. 파일 마지막에 직접 실행 진입점을 추가했다.

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
```

이제 `python main.py`도 서버를 시작하고 `PORT`를 따른다. Render에서는 위의 명시적인 Uvicorn Start Command를 권장한다. 기존 `python -m uvicorn main:app ...` 방식은 계속 사용할 수 있다.

## 환경 변수와 데이터

로컬 `.env`는 Git에서 제외되므로 Render에 자동 전달되지 않는다. Render의 Environment에서 `KHOA_API_KEY`를 설정한다. 두 서비스 키가 다르면 서비스별 키를 설정한다. 사진 분석을 쓸 때만 `OPENAI_API_KEY`, `OPENAI_MODEL`도 설정한다. 키를 Git에 올리거나 명령에 직접 붙이지 않는다.

기본 SQLite는 프로젝트의 `data/sea_info.sqlite3`다. Render의 영속 디스크를 연결한 경우 해당 경로 안으로 `SEA_INFO_DB_PATH`를 설정한다. 디스크를 연결하지 않은 상태의 로컬 파일은 재배포·재시작 시 보존을 기대하지 않는다. 영속 저장소 조건은 [Render 공식 문서](https://render.com/docs/disks)에서 확인한다. 키 설정·디스크 설정 자체는 포트 바인딩과 별도 작업이다.

설정 저장과 최신 코드 반영 후 재배포해 `Uvicorn running on http://0.0.0.0:...`와 `Application startup complete`를 확인한다. 계속 실패하면 `Running ...` 줄부터 첫 Python 오류까지의 로그와 Root Directory·Start Command를 확인해야 한다. 이 문서는 Render에 직접 접속해 배포 성공을 검증한 결과가 아니다.
