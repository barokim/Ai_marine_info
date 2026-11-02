# AI-marine info

전국 해안 지역의 물때·실측 수온·해양 예보와 생물 도감을 조회하고, 로그인 회원이 게시판·사진 분석·개인 기록을 이용하는 FastAPI 학습 프로젝트입니다.

**이번 작업은 코드 구현까지만 완료했습니다. 서버는 실행하지 않았고, Supabase SQL 실행·회원 생성·메일 발송·실제 외부 API 조회도 하지 않았습니다.** 아래 실행 명령은 사용자가 나중에 실행하기 위한 안내입니다.

## 구성과 기존 프로젝트 관계

- Python 3.12, FastAPI, Jinja2, HTML/CSS/바닐라 JavaScript
- Supabase Auth + Postgres 게시판(RLS), 개인 기록용 새 SQLite
- 11개 시·도 → 74개 해안 시·군·구 → 113개 등록 관측·예보 지점
- 기존 `C:\KBR\sea_info_dashboard`의 서비스 함수를 **소스 복사 없이** 연결
- 원본 Python·HTML·JS·CSS·SQLite는 수정하지 않았습니다.
- 기존 관찰 기록과 사진 이력을 새 회원에게 자동으로 귀속시키거나 공개하지 않습니다.

```text
ai_marine_info/
├─ app/
│  ├─ main.py              앱·페이지·보안 헤더·요청 제한
│  ├─ config.py            .env 로딩과 시작 시 검증
│  ├─ schemas.py           요청/응답 Pydantic 모델
│  ├─ auth.py              회원가입·로그인·현재 회원·메일 인증
│  ├─ posts.py             사용자 JWT를 전달하는 PostgREST CRUD
│  ├─ marine.py            전국 조회·생물·사진·개인 기록 API
│  ├─ regions.py           지역·관측소 선택 검증
│  ├─ legacy.py            기존 서비스 모듈 연결
│  ├─ storage.py           회원별 SQLite 쿼리
│  ├─ templates/           공통 헤더·푸터와 각 화면
│  └─ static/              JS·CSS·직접 제작한 SVG 로고
├─ data/regions.json       행정구역·지점 연결과 예보 대표 좌표
├─ data/station_sources.json  활용가이드의 공식 코드·이름 목록
├─ supabase/              SQL·회원가입/재설정 메일 템플릿
├─ scripts/               지점 데이터 생성·원본 버전 확인 도구
├─ tests/                 네트워크 없는 모의 테스트
└─ docs/                  코드 설명·지역 관리·검증 결과
```

읽는 순서: [코드 설명](docs/CODE_GUIDE.md) → [지역 데이터 관리](docs/REGION_DATA.md) → [검증 결과](docs/TEST_REPORT.md).

## 나중에 설치·실행할 때

새 폴더에 Python 3.12 가상환경과 검증한 패키지를 준비했습니다. 다른 PC에서는 아래 설치 과정을 먼저 실행하세요.

```powershell
cd C:\KBR\ai_marine_info
# .venv가 없는 경우에만 생성합니다.
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 이미 있는 .env를 덮어쓰지 않습니다.
if (!(Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

`.env` 설정과 아래 Supabase 설정을 끝낸 뒤, 서버를 구동하기로 결정했을 때 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

- 홈: <http://127.0.0.1:8002/>
- API 안내: <http://127.0.0.1:8002/docs>
- API 명세: <http://127.0.0.1:8002/openapi.json>
- 종료: 실행 터미널에서 `Ctrl+C`

현재 프로세스를 시작하는 자동 스크립트·백그라운드 서비스는 만들지 않았습니다. `python app/main.py` 대신 위 uvicorn 명령을 사용합니다.

## 환경변수

**새 프로젝트의 `.env`만 읽습니다.** 부모 폴더나 기존 대시보드의 `.env`를 자동으로 읽거나 복사하지 않습니다. 필요한 해양 API 키도 새 `.env`에 직접 입력하세요. 실제 키는 채팅·출력·Git에 넣지 않습니다.

| 변수 | 설정 |
|---|---|
| `SUPABASE_URL` | 새 프로젝트의 `https://...supabase.co` 주소, 필수 |
| `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_`로 시작하는 키, 필수 |
| `APP_ORIGIN` | 로컬은 `http://127.0.0.1:8002`, 운영은 HTTPS origin |
| `SUPABASE_RESET_REDIRECT_URL` | 위 origin + `/reset-password` |
| `SUPABASE_SIGNUP_REDIRECT_URL` | 위 origin + `/confirm-email` |
| `SEA_INFO_SOURCE` | 기본 `../sea_info_dashboard`, 새 프로젝트 루트 기준 |
| `KHOA_API_KEY` | 국립해양조사원 공통 Decoding 인증키 |
| `KHOA_TIDE_API_KEY` | 조석 API 키가 별도인 경우에만 지정 |
| `KHOA_OBSERVATION_API_KEY` | 관측 API 키가 별도인 경우에만 지정 |
| `MBRIS_API_KEY` | 국명 검색용 키 |
| `OPENAI_API_KEY` | 사진 분석용 서버 키 |
| `OPENAI_MODEL` | 이미지 입력·구조화 출력을 지원하는 접근 가능한 모델 이름 |

서비스 롤·`sb_secret_`·Postgres 직접 접속 비밀번호는 사용하지 않습니다. URL/키 형식이 잘못되면 앱을 시작하지 않습니다. 해양 API 키가 없으면 해당 정보에 설정 필요 상태를 표시합니다. 예시 물때나 수온으로 채우지 않습니다.

서버 밖으로 배포할 때에도 새 폴더와 기존 대시보드 폴더를 함께 배치하거나 `SEA_INFO_SOURCE`를 올바른 경로로 설정해야 합니다. 이 폴더만 복사하면 기존 서비스 코드가 없어 시작할 수 없습니다.

## Supabase에서 사용자가 해야 할 설정

1. 새 프로젝트의 SQL Editor에서 [schema.sql](supabase/schema.sql)을 실행합니다. 기존 다른 프로젝트의 테이블에 적용하지 마세요. 앱은 SQL을 자동 실행하지 않습니다.
2. Email 인증을 활성화하고 회원가입을 허용합니다. 익명 로그인은 사용하지 않습니다.
3. 이메일 확인 옵션을 결정합니다. **확인 켜짐을 권장**하며, 이 경우 가입 후 인증 코드를 확인해야 로그인할 수 있습니다. 꺼져 있으면 가입 후 로그인 화면으로 이동해 로그인합니다.
4. Authentication의 URL Configuration에서 Site URL을 `APP_ORIGIN`과 같게 지정합니다.
5. Redirect URLs에 아래 주소를 **정확히** 등록합니다. 와일드카드를 사용할 필요가 없습니다.

```text
http://127.0.0.1:8002/confirm-email
http://127.0.0.1:8002/reset-password
```

운영 도메인이 정해지면 다음 형태의 실제 HTTPS 주소를 추가하고 `.env`의 세 URL도 함께 변경합니다.

```text
https://실제-운영-도메인/confirm-email
https://실제-운영-도메인/reset-password
```

`localhost`와 `127.0.0.1`은 서로 다른 origin입니다. 다른 표기를 사용하려면 환경변수와 Supabase 설정을 함께 바꾸세요.

6. 이메일 템플릿을 반드시 설정합니다.
   - Confirm signup: [email_signup.html](supabase/email_signup.html) 내용
   - Reset password: [email_reset.html](supabase/email_reset.html) 내용
   - 링크는 `{{ .RedirectTo }}`, 코드 표시는 `{{ .Token }}`입니다.
   - **이 앱에서는 `{{ .ConfirmationURL }}`이나 `{{ .TokenHash }}`를 URL에 넣는 템플릿을 사용하지 않습니다.** 기본 템플릿을 그대로 두면 이 앱의 인증 코드 흐름과 맞지 않습니다.
7. 메일 발신 설정·SMTP·발송 제한·테스트 수신 가능 주소를 확인합니다. 실제 발송 가능 여부는 프로젝트 설정에 따라 다릅니다.
8. 비밀번호 강도, OTP 만료 시간, JWT 만료 시간을 확인합니다. 앱의 비밀번호 입력은 8~128자이며 프로젝트의 추가 정책도 적용됩니다.

### 비밀번호 재설정 흐름

`이메일 입력 → reset_password_for_email → 메일의 페이지 링크 클릭 → 이메일·메일 인증 코드·새 비밀번호 입력 → verify_otp(type='recovery') → update_user → 새 비밀번호 로그인`

Supabase Python 2.33.0의 `reset_password_for_email`은 PKCE challenge를 자동 전송하지 않습니다. 따라서 URL에 토큰을 넣지 않는 **메일 인증 코드 입력 방식**으로 구현했습니다. 메일 링크에 개인정보·access token·OTP를 넣지 않아 다른 기기에서도 코드로 확인할 수 있습니다. 계정이 없거나 계정별 재발송 제한이 걸린 경우에도 같은 안내를 반환합니다. IP별 과도한 요청은 공통 429로 제한합니다.

## 권한·저장 방식

| 기능 | 비로그인 | 로그인 |
|---|---|---|
| 홈·물때·수온·예보·생물 검색 | 조회 가능 | 조회 가능, 본인 이력 저장 |
| 게시판 목록·상세 | 로그인 안내, API 401 | 회원 모두 조회 |
| 글 작성 | 불가 | 가능 |
| 글 수정·삭제 | 불가 | 본인만 가능, 타인 글은 404 |
| 사진 분석·관찰 기록·조회 이력 | 로그인 필요 | 본인 자료만 접근 |

- access token은 탭의 `sessionStorage`에만 보관합니다. 새로고침·페이지 이동 시 유지되며 로그아웃 시 제거합니다. localStorage나 URL에는 저장하지 않습니다. refresh token은 프론트에 전달하지 않으며 만료 후 재로그인합니다.
- sessionStorage는 JavaScript에서 읽을 수 있습니다. 이를 보완하기 위해 CSP, 외부 스크립트 미사용, `textContent` 출력, 입력 검증을 적용했습니다. HttpOnly 쿠키의 XSS 내성과 같지는 않습니다.
- 로그아웃은 Supabase 세션의 refresh token을 폐기합니다. **이미 발급된 access JWT는 만료 전까지 유효할 수 있습니다.** 서버의 사용자 검증만으로 즉시 JWT 폐기가 보장되는 것은 아닙니다.
- 게시판은 사용자 JWT를 PostgREST에 전달하고 SQL RLS를 적용합니다. 직접 REST로 호출해도 `anon`은 접근할 수 없고 다른 회원 글은 변경할 수 없습니다.
- `author_name`은 작성 당시 메타데이터의 이름이며 실명 인증이 아닙니다. DB 트리거가 이름을 설정하고 작성자·생성일 변조를 막습니다.
- 개인 SQLite는 `data/private/member.sqlite3`에 서버 최초 실행 시 생성합니다. 이번 코드 작업에서는 실제 개인 DB를 만들지 않았으며 테스트는 임시 DB를 사용했습니다.
- SQLite 개인 자료는 Supabase RLS가 아닌 서버의 `owner_id` 조건과 파일 접근 권한으로 보호합니다. 원본 SQLite는 연결하지 않습니다.
- API·인증 응답은 `no-store`, 검증 오류에는 원본 입력·비밀번호·토큰을 넣지 않습니다.
- 인증 요청 제한은 프로세스별 IP/경로 기준 분당 10회입니다. 다중 프로세스로 운영할 때 공유 제한 저장소는 별도로 구성해야 합니다.

## 서버 없는 검증

테스트 도구는 앱 실행 의존성과 분리했습니다. 처음 한 번 개발용 패키지를 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
cd C:\KBR\ai_marine_info
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend.test.cjs
node --check app/static/app.js
```

pytest는 예상 가능한 잘못된 이메일·짧은 비밀번호·누락/잘못된 Bearer·게시판 본문 길이 초과·알 수 없는 지역·도시와 시·도 불일치·로그인 요청 과다·요청 크기 초과·잘못된 게시글 ID를 검사합니다. 별도 smoke test는 임시 SQLite와 동적 loopback 포트에서 실제 uvicorn 서버를 시작해 홈·전국 지역·미로그인 게시판·큰 요청 거절을 HTTP로 확인한 뒤 자동 종료합니다. 테스트를 위해 Supabase나 해양 API에 접속하지 않습니다. 실제 계정·이메일·RLS 동작은 Supabase 설정 후에만 확인할 수 있습니다.

## 참고

- [Supabase Python 비밀번호 재설정](https://supabase.com/docs/reference/python/auth-resetpasswordforemail)
- [Supabase 이메일 템플릿](https://supabase.com/docs/guides/auth/auth-email-templates)
- [Supabase Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls)
- [국립해양생물자원관](https://www.mabik.re.kr/): 공공 포털의 구조·분위기만 참고했습니다. 로고·사진·문구·소스는 복사하지 않았습니다.
