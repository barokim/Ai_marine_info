# 코드 읽기 안내

## 1. 요청이 처리되는 순서

```text
브라우저 HTML/JS
  → RequestGuard: 본문 크기·인증 요청 횟수 제한
  → Pydantic: 타입·길이·추가 필드 검사
  → 보호 API라면 get_current_user
       → Supabase auth.get_user(access token)
  → 기능별 라우터
       게시판: PostgREST + 사용자 JWT → Postgres RLS
       해양 조회: legacy 어댑터 → 기존 서비스 함수 → 외부 API
       개인 기록: owner_id 조건 → 새 SQLite
  → 공개할 응답 데이터만 반환 + 보안 헤더
  → JavaScript textContent로 화면 표시
```

## 2. 수업 예제와 연결

| 수업 개념 | 이 프로젝트의 위치 | 이유 |
|---|---|---|
| load_dotenv | `app/config.py` | 프로세스 환경변수를 우선하고 `${...}` 치환을 끕니다. 새 폴더의 `.env`만 읽습니다. |
| BaseModel·ConfigDict | `app/schemas.py` | 입력의 형태를 선언하고 `author_id` 같은 허용되지 않은 필드를 거절합니다. |
| EmailStr·SecretStr | 인증 입력 모델 | 이메일 형식을 확인하고 모델 출력에서 비밀번호를 가립니다. 암호화 기능은 아닙니다. |
| RequestValidationError | `app/main.py` | 오류에 원본 비밀번호가 다시 포함되지 않도록 `loc`, `type`만 남깁니다. |
| make_client | `app/auth.py` | 요청마다 독립된 Supabase 클라이언트와 10초 HTTP 통신 설정을 사용합니다. |
| HTTPBearer·Depends | `get_current_user` | 헤더 추출과 토큰 진위 확인을 구분합니다. JWT 문자열만 해석해 믿지 않습니다. |
| owner_id 조건 | `app/posts.py`, `app/storage.py` | 검증된 회원 ID로만 작성하고, 수정·삭제 시 ID와 회원 ID를 함께 비교합니다. |
| SQL 바인딩 | `app/storage.py` | SQLite 값은 `?` 매개변수로 전달합니다. PostgREST는 SDK의 구조화된 필터를 사용합니다. |

## 3. 인증 코드에서 볼 부분

`auth_client()`는 context manager입니다. 요청이 끝나면 HTTP 연결을 닫고 Auth 오류를 한국어 HTTP 응답으로 변환합니다. `AuthApiError.code`를 먼저 비교하므로 비밀번호 오류와 프로젝트 설정 오류를 같은 401로 취급하지 않습니다.

`Identity`는 검증된 `CurrentUser`와 요청 토큰을 서버 내부에서만 묶는 자료형입니다. `/me` 응답은 사용자 정보만 반환하며 토큰은 포함하지 않습니다. 로그인 성공 응답에만 access token을 제공합니다.

회원가입은 `options.data.name`으로 이름을 저장합니다. 입력 모델에 비밀번호 확인 필드는 없으며, JS가 두 입력을 비교한 뒤 필요한 세 값만 API로 전송합니다.

비밀번호 재설정은 로그인 토큰을 URL로 전달하지 않습니다. 사용자가 메일 인증 코드를 POST 본문에 입력하고 SDK가 `recovery` 용도로 검증한 후 **같은 요청의 SDK 세션**으로 비밀번호를 바꿉니다. 인증 코드는 일회용이므로 비밀번호 정책 오류로 변경이 거절되면 새 메일이 필요할 수 있습니다.

## 4. 게시판에서 두 번 권한을 검사하는 이유

브라우저에서 수정 버튼을 숨기는 것만으로는 직접 API 호출을 막을 수 없습니다. 서버는 사용자 ID 조건을 붙여 수정·삭제하고 결과 행이 없으면 404를 반환합니다. 회원 모두의 읽기는 허용하므로 목록·상세 조회에는 본인 ID 필터를 붙이지 않습니다.

`client.postgrest.auth(identity.token)`은 PostgREST의 Authorization 헤더를 사용자 JWT로 설정합니다. 이 단계가 없으면 publishable 키를 사용하는 요청은 익명 역할로 처리되어 RLS 정책과 맞지 않습니다. 설치한 SDK 2.33.0의 실제 HTTP 요청을 모의 테스트로 검사했습니다.

`schema.sql`은 다음 세 가지를 함께 설정합니다.

1. 테이블 권한: anon/PUBLIC 권한 제거, authenticated의 필요한 작업만 허용
2. RLS: 회원 읽기·본인 쓰기 조건
3. 트리거/열 권한: 작성자 이름을 메타데이터에서 결정, 작성자·작성일 변경 방지, 수정일 자동 갱신

트리거의 `SECURITY DEFINER`는 DB 안에서 `auth.users`의 이름을 읽기 위한 것이며 서버에서 서비스 롤을 사용하는 것과 다릅니다. 함수는 검색 경로를 비워 고정하고 공개 실행 권한을 제거했습니다.

## 5. 기존 코드를 지우거나 복사하지 않는 연결

기존 파일들은 `from models import ...`처럼 실행 폴더를 기준으로 import합니다. 새 앱도 단순히 `import main`을 하면 이름 충돌·기존 라우트 노출·원본 DB 초기화 문제가 생길 수 있습니다.

`legacy.py`는 다음 네 파일만 별도 모듈 이름으로 읽습니다.

```text
models.py → services.py → species_service.py → image_service.py
```

원본 파일을 실행 가능한 모듈로 로딩하되, 그 모듈 안의 import를 전용 로더로 연결합니다. `sys.path`나 공용 `models` 모듈을 덮어쓰지 않습니다. 기존 `services.py`의 최상위 `_load_project_env(...)` 호출만 메모리의 AST에서 제외하여 원본 `.env`를 읽지 않게 합니다. 원본 파일 내용은 바꾸지 않습니다.

이 방식은 기존 코드 보존을 우선한 어댑터입니다. `SEA_INFO_SOURCE`는 운영자가 설정하는 신뢰한 로컬 Python 코드 경로여야 하며 요청 본문에서 받지 않습니다. 원본 파일의 함수 이름·모델이 변경되면 어댑터 회귀 테스트를 다시 실행해야 합니다. 이후 원본을 패키지로 정리할 허가가 생기면 상대 import 방식으로 단순화할 수 있습니다.

전국 조회에서는 원본의 `RegionId = Literal['incheon','busan','jeju']`를 억지로 우회해 사용자 입력을 통과시키지 않습니다. 새 지역 목록에서 ID를 검증한 뒤, 기존 `fetch_tides`, `fetch_observations`, `fetch_live_marine`이 필요로 하는 속성만 가진 요청별 객체를 전달합니다. 새 응답은 기존의 3개 지역 전용 DashboardResponse와 분리합니다.

## 6. 데이터와 화면의 구분

- 조석: 공식 예보이며 관측 실측과 다릅니다. 첫 만조·간조는 해당 날짜의 첫 사건입니다.
- 수온: 관측소의 최신 수신값과 수신 시각을 표시합니다. 모델 해수면 온도를 실측 대신 넣지 않습니다.
- 파고·모델 온도: 시·군·구 대표 해역의 모델 예보입니다. 관측소 위치를 의미하지 않습니다.
- 생물: MBRIS와 WoRMS 식별자를 섞지 않습니다. MBRIS는 검색 결과 설명, WoRMS는 분류·분포 상세를 보여줍니다.
- 사진: 원본 서비스의 크기·이미지 형식·픽셀 검증과 EXIF 제거를 재사용합니다. 로그인과 외부 전송 동의를 확인한 후 분석합니다.

## 7. 프론트엔드 읽는 순서

`app/static/app.js`의 주요 함수입니다.

| 함수 | 역할 |
|---|---|
| `api` | Bearer 헤더·JSON·타임아웃·한국어 오류를 공통 처리 |
| `currentUser`, `renderAccount` | 서버의 `/me`로 회원 확인 후 이름·로그아웃 표시 |
| `authPage` | 폼 종류에 맞는 인증 API 호출, 비밀번호 확인, 안전한 내부 이동 |
| `setupRegions`, `updateCities`, `updateStations` | 시·도 → 시·군·구 → 지점의 종속 선택 |
| `resetMarine`, `loadMarine` | 선택 변경 시 이전 수치를 지우고 늦게 도착한 응답을 무시 |
| `board` | 목록 페이지·글 읽기·본인 글 편집·삭제 |
| `speciesPage`, `photoPage` | 생물 검색·상세·사진 분석 |
| `recordsPage`, `historyPage` | 본인의 기록과 과거 조회 결과 관리 |

사용자 문자열에는 `innerHTML`을 사용하지 않습니다. 외부 링크도 고정된 공식 URL이나 검증된 숫자 식별자를 조합합니다. 인증 성공 후 이동할 경로는 내부 경로 허용 목록으로 제한합니다.

CSS는 별도 파일이며 폰트·아이콘 CDN을 사용하지 않습니다. 로고와 바다 배경은 직접 제작한 SVG/CSS입니다. 공통 레이아웃은 `base.html`, 기능 화면은 `page.html`, 지역 필터는 `region_filter.html`입니다.

## 8. 실행·검증의 경계

앱 팩토리 `create_app()`은 FastAPI 객체를 만들 뿐 TCP 서버를 열지 않습니다. 실제 서버는 README의 uvicorn 명령을 사용자가 실행해야 시작됩니다. 테스트에서는 TestClient로 메모리 안에서 요청을 처리하고 HTTPTransport를 대체했습니다.

모의 테스트는 API의 요청 방식과 소유권 조건을 검증합니다. 원격 Postgres의 RLS가 실제 설치되었는지, 이메일이 실제 배달되는지, 관측소의 현재 데이터가 오는지는 별개입니다. 이번 작업에서는 요청에 따라 확인하지 않았습니다.
