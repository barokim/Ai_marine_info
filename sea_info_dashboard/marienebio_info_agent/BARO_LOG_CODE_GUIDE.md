# BARO.LOG 코드 설명서

이 문서는 **「BARO.LOG · 바다와 AI 사이」**의 소스 코드를 직접 읽고 수정할 수 있도록 설명한 자료입니다. 2026년 10월 26일 배포한 버전 1을 기준으로 작성했습니다.

## 1. 이 사이트는 어떻게 만들어졌나요?

이 사이트는 **브라우저에서 동작하는 정적 웹사이트**입니다. HTML로 내용을 배치하고, CSS로 디자인하고, JavaScript로 버튼과 회고 입력 기능을 연결합니다.

| 기술 | 이 사이트에서 하는 일 |
| --- | --- |
| HTML | 소개 문구, 프로젝트 카드, 탐구 노트, 회고 입력창 구성 |
| CSS | 바다색·종이색 테마, 화면 배치, 모바일 대응 |
| JavaScript | 프로젝트 필터, 팝업, KPT·4L 회고, 자동 저장, 파일 다운로드 |
| SVG | 파도 로고, 등고선 그림, 프로젝트 소개용 그래픽 |
| `localStorage` | 현재 브라우저에 회고 초안 저장 |
| Sites | 정적 파일 호스팅과 비공개 접근 제어 |

React·Vue 같은 프레임워크나 npm 패키지는 사용하지 않습니다. 이 개인 사이트를 실행하는 데 FastAPI·SQLite·OpenAI API 키도 필요하지 않습니다. 페이지에 소개된 **Sea-Info와 작은 방명록은 별도 프로젝트**이며, 이 폴더에는 그 서버 코드가 들어 있지 않습니다.

### 페이지가 열리는 순서

1. 브라우저가 `dist/index.html`을 읽습니다.
2. HTML에서 연결한 `styles.css`로 디자인을 적용합니다.
3. `defer`로 연결한 `app.js`가 HTML 분석 이후 실행됩니다.
4. 등고선 그림을 그리고, 버튼 이벤트를 연결하고, 저장된 회고 초안을 읽어 입력창을 준비합니다.

HTML의 연결 부분은 다음과 같습니다.

```html
<link rel="stylesheet" href="styles.css">
<script src="app.js" defer></script>
```

## 2. 폴더와 파일의 역할

| 파일 | 읽을 때 살펴볼 내용 |
| --- | --- |
| [dist/index.html](dist/index.html) | 어떤 정보가 어느 화면에 놓이는지 |
| [dist/styles.css](dist/styles.css) | 색상 변수, 레이아웃, 미디어 쿼리 |
| [dist/app.js](dist/app.js) | 이벤트 연결, 콘텐츠 객체, 회고 저장·내보내기 |
| [dist/favicon.svg](dist/favicon.svg) | 파도 모양 아이콘의 벡터 경로 |
| [.openai/hosting.json](.openai/hosting.json) | 기존 사이트 ID와 배포할 정적 파일 폴더 |
| [ORIGINAL_README.md](ORIGINAL_README.md) | 최초 제작 당시 콘텐츠 기준과 확인 기록 |
| [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) | 원본 커밋과 복사한 파일의 SHA-256 |

`dist`는 이 사이트에서 **실제로 브라우저에 제공하는 파일이 들어 있는 폴더**입니다. 보통 다른 프로젝트에서는 빌드 결과 폴더라는 뜻으로 쓰기도 하지만, 여기서는 직접 작성한 HTML·CSS·JS를 그대로 넣어 사용합니다.

## 3. index.html — 화면의 뼈대

### 3-1. 주요 화면 구역

| 구역·ID | 표시하는 내용 |
| --- | --- |
| `.header` | 로고, 페이지 내 메뉴, GitHub 링크 |
| `.hero` | 김바로 소개, 대표 문구, 바다 등고선 표지 |
| `#projects` | Sea-Info·작은 방명록 카드와 분류 버튼 |
| `#notes` | 쿠키·인증, 데이터 검증, 영구 저장에 관한 탐구 노트 |
| `#reflection` | 회고 소개와 작성창을 여는 버튼 |
| `.about` | 짧은 자기소개 |
| `.footer` | GitHub·블로그·맨 위로 이동 링크 |
| `#detail-dialog` | 프로젝트·노트 상세 내용을 보여주는 공용 팝업 |
| `#reflection-dialog` | KPT·4L 회고 작성 팝업 |
| `#toast` | 저장·내보내기 등에 관한 짧은 알림 |

메뉴의 `href="#projects"`는 다른 페이지를 여는 대신 현재 페이지에서 `id="projects"`인 구역으로 이동합니다.

### 3-2. data 속성으로 버튼과 기능 연결하기

HTML의 `data-*` 속성은 JavaScript가 어떤 동작을 해야 하는지 구분하는 표식입니다.

```html
<button data-filter="ocean">해양 데이터</button>
<button data-project="sea">Sea-Info 해양 대시보드</button>
<button data-note="cookie">쿠키 관련 탐구 노트</button>
```

이 코드는 작동 방식을 설명하기 위해 원본에서 필요한 부분만 간추린 예시입니다. 실제 파일에는 디자인용 클래스와 접근성 속성도 들어 있습니다.

| 속성 | JavaScript가 해석하는 뜻 |
| --- | --- |
| `data-filter="all"` | 모든 프로젝트 표시 |
| `data-filter="ocean"` | 해양 데이터 프로젝트만 표시 |
| `data-filter="web"` | 웹 백엔드 프로젝트만 표시 |
| `data-category` | 각 프로젝트 카드가 속한 분류 |
| `data-project="sea"` | `projectContent.sea`를 상세창에 표시 |
| `data-note="cookie"` | `noteContent.cookie`를 상세창에 표시 |
| `data-close` | 해당 팝업 닫기 |

## 4. styles.css — 디자인과 모바일 대응

### 4-1. 색상과 서체

파일 앞부분의 `:root`에 반복해서 사용할 색상을 변수로 모아두었습니다.

```css
:root {
  --paper: #f5f4ee;
  --ink: #253d3b;
  --green: #285b52;
  --clay: #ad6e4f;
}
```

| 변수 | 용도 |
| --- | --- |
| `--paper` | 종이를 연상시키는 전체 배경색 |
| `--ink` | 기본 글자색 |
| `--muted` | 설명 문장에 쓰는 보조 글자색 |
| `--green` | 주요 버튼과 강조색 |
| `--line` | 구분선 색상 |
| `--clay` | 작은 강조 요소의 갈색 계열 |
| `--sans` | 본문과 제목의 기본 서체 묶음 |
| `--serif` | 표지 영문 제목과 KPT 영문 제목의 명조 계열 서체 |
| `--mono` | 번호·기술명·보조 라벨의 고정폭 서체 |

Google Fonts에서 `DM Sans`, `Noto Sans KR`을 불러옵니다. 네트워크 연결이 없으면 뒤에 지정한 시스템 서체를 사용하므로 화면은 계속 표시되지만 글자 모양과 줄바꿈이 달라질 수 있습니다.

### 4-2. 배치와 반응형 규칙

`.hero`, `.project-grid`, `.notes-layout`, `.reflection-panel` 등에 CSS Grid를 사용합니다. 넓은 화면에서는 좌우로 나누고, 작은 화면에서는 세로로 쌓습니다.

| 조건 | 주요 조정 |
| --- | --- |
| 기본 | 넓은 화면의 2열 중심 배치 |
| `min-width: 1450px` | 큰 화면의 제목 크기와 여백 조정 |
| `max-width: 1100px` | 중간 화면의 글자·카드·간격 조정 |
| `max-width: 760px` | 모바일의 1열 배치, 팝업과 입력창 너비 조정 |
| `max-width: 380px` | 작은 화면에서 로고와 메뉴 크기 추가 조정 |
| `prefers-reduced-motion: reduce` | 스크롤 애니메이션과 전환 효과 최소화 |

원본 CSS는 여러 규칙을 긴 줄에 모아 작성한 형태입니다. 편집기의 자동 줄바꿈 기능을 켜면 읽기 편합니다. 이번 모음에서는 배포된 원본과 일치하도록 파일 내용 자체를 재정렬하지 않았습니다.

## 5. app.js — 화면의 동작

### 5-1. 바다 등고선 그림

`#contours` 안에 SVG `path` 요소를 28개 만듭니다. 각 경로에서 각도에 따라 좌표를 계산하고, `sin`·`cos`를 사용해 울퉁불퉁한 곡선을 그립니다.

```javascript
const path = document.createElementNS(
  'http://www.w3.org/2000/svg',
  'path'
);
```

이 그림은 디자인을 위한 **개념적 일러스트**입니다. 실제 수심·해도·해양 관측 데이터를 표시하지 않습니다. 별도 이미지 파일을 다운로드하지 않고 JavaScript와 SVG로 만듭니다.

### 5-2. 프로젝트 필터

`[data-filter]` 버튼을 클릭하면 두 작업을 합니다.

1. 선택한 버튼에 `active` 클래스를 적용하고 `aria-pressed` 값을 바꿉니다.
2. 카드의 `data-category`가 선택한 분류와 다르면 `hidden`을 적용합니다.

새 API를 요청하거나 새 페이지를 불러오지 않습니다. 이미 HTML에 있는 카드의 표시 여부만 바꿉니다.

### 5-3. 프로젝트와 노트 상세창

상세 글은 `app.js`의 다음 객체에 들어 있습니다.

| 객체 | 키 | 내용 |
| --- | --- | --- |
| `projectContent` | `sea`, `guest` | 두 프로젝트의 상세 설명 |
| `noteContent` | `cookie`, `api`, `db` | 세 개 탐구 노트의 본문 |

버튼의 `dataset.project` 또는 `dataset.note` 값을 읽어 해당 HTML 문자열을 `#detail-content`에 넣습니다.

```javascript
document.getElementById('detail-content').innerHTML =
  projectContent[button.dataset.project];
```

이 부분의 `innerHTML`에는 코드 작성자가 미리 넣은 고정 콘텐츠를 사용합니다. 회고 작성자의 입력값은 여기에 넣지 않습니다. 나중에 외부 서비스나 사용자 입력을 상세 글로 연결한다면, 그 값을 그대로 `innerHTML`에 넣는 방식은 피하고 별도의 처리가 필요합니다.

`openDialog()`는 브라우저의 `<dialog>` 요소에 `showModal()`을 호출하고 배경 스크롤을 막습니다. 닫기 버튼, 바깥 영역 클릭, 브라우저가 제공하는 Escape 키 동작으로 팝업을 닫을 수 있습니다.

### 5-4. 주요 함수와 역할

| 함수 | 하는 일 |
| --- | --- |
| `openDialog(dialog)` | 전달받은 팝업 열기 |
| `updateDraftStatus()` | 메인 화면에 회고 초안 상태 표시 |
| `saveDraft()` | 현재 입력값을 초안 객체와 `localStorage`에 저장 |
| `renderFields()` | KPT 또는 4L에 맞는 입력란 생성 |
| `toast(message)` | 화면 아래에 약 3.5초간 짧은 알림 표시 |
| 회고 폼의 `submit` 이벤트 처리 | 빈 내용 검사 후 Markdown 파일 생성·다운로드 실행 |

## 6. 회고 초안의 구조와 저장 방식

### 6-1. KPT와 4L 정의

`fieldDefinitions`가 입력창의 종류·제목·설명·힌트를 정의합니다.

| 방식 | 저장 키 | 항목 |
| --- | --- | --- |
| KPT | `keep`, `problem`, `try` | 유지할 점, 문제, 다음 시도 |
| 4L | `liked`, `learned`, `lacked`, `longed` | 좋았던 경험, 배운 점, 부족했던 점, 바라는 것 |

`renderFields()`는 현재 선택한 방식에 맞춰 `<label>`과 `<textarea>`를 만듭니다. 형식을 바꾸어도 서로 다른 저장 키를 쓰므로 기존 입력값을 남겨둡니다.

### 6-2. 초안 데이터 예시

다음은 **구조 설명용 예시**이며 실제 작성한 회고가 아닙니다.

```json
{
  "date": "2026-10-26",
  "title": "이번 주의 작은 실험",
  "format": "KPT",
  "values": {
    "keep": "직접 실행해서 동작을 확인하기",
    "problem": "저장 위치를 혼동했던 상황",
    "try": "다음 실행에서 같은 기록이 남는지 확인하기"
  },
  "updatedAt": "2026-10-26T13:00:00.000Z"
}
```

| 속성 | 의미 |
| --- | --- |
| `date` | 사용자가 고른 기록 날짜. 최초 기본값은 서울 시간 기준 오늘 |
| `title` | 회고 제목. 최대 120자 |
| `format` | `KPT` 또는 `4L` |
| `values` | 항목별 회고 내용. 각 항목 최대 4,000자 |
| `updatedAt` | 저장할 때 생성하는 시각 문자열 |

### 6-3. 저장과 복원

저장 키는 다음과 같습니다.

```javascript
const STORAGE_KEY = 'baro-logbook-reflection-v1';
```

입력 이벤트가 발생하면 `JSON.stringify()`로 초안을 문자열로 바꿔 저장합니다.

```javascript
localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
```

페이지를 다시 열면 `JSON.parse()`로 복원합니다. 문자열의 자료형과 길이, 형식 등의 일부 조건을 확인한 뒤 입력창에 적용합니다. 저장·읽기 과정이 실패할 때는 `try...catch`로 처리합니다.

### 6-4. 사용자가 알아야 할 범위

- 초안은 **하나**입니다. 날짜별로 여러 회고를 보관하는 목록 기능은 없습니다.
- 날짜를 바꾸면 같은 초안의 날짜가 바뀝니다. 새 주에 쓰기 전 기존 기록을 파일로 내려받아 보관하는 방식입니다.
- `localStorage`는 사이트 출처에 따라 구분됩니다. 배포 주소와 로컬 주소의 초안은 서로 공유되지 않습니다. 로컬 서버의 주소나 포트가 바뀌어도 기존 초안이 보이지 않을 수 있습니다.
- 다른 브라우저·기기와 동기화되지 않습니다. 브라우저 데이터를 지우거나 시크릿 창을 닫으면 저장이 사라질 수 있습니다.
- 초안을 서버나 티스토리로 전송하지 않습니다. 따라서 이 코드 폴더에는 실제 회고 데이터가 들어 있지 않습니다.

## 7. Markdown 내보내기

회고 폼의 `submit` 이벤트에서 다음 순서로 동작합니다.

1. `event.preventDefault()`로 일반 폼 제출과 페이지 이동을 막습니다.
2. 제목과 현재 선택한 방식의 항목이 모두 비어 있으면 입력 안내를 표시합니다.
3. 현재 초안을 저장하고 제목·날짜·작성자·항목을 Markdown 문자열로 만듭니다.
4. UTF-8 텍스트 `Blob`을 생성합니다.
5. `URL.createObjectURL(blob)`로 임시 주소를 만듭니다.
6. `<a download>`를 만들어 클릭하고, 잠시 뒤 임시 주소를 해제합니다.

파일명은 `baro-kpt-2026-10-26.md` 또는 `baro-4l-2026-10-26.md`처럼 만들어집니다. 선택한 방식의 항목만 내보내며, 빈 항목은 `(아직 작성하지 않음)`으로 표시합니다.

원래 제작 환경에서는 내보내기 코드 실행과 안내 표시까지 확인했습니다. 브라우저 다운로드 이벤트가 전달되지 않아 수신한 파일의 바이트 확인은 완료하지 못했습니다. 이번 코드 모음은 해당 원본 로직을 그대로 담고 있습니다.

## 8. 직접 수정할 때 찾아갈 위치

| 바꾸고 싶은 것 | 수정할 위치 |
| --- | --- |
| 메인 소개와 큰 제목 | `index.html`의 `.hero-copy` |
| GitHub·티스토리 주소 | `index.html`의 링크와 `app.js` 상세 글의 링크 |
| 프로젝트 카드의 제목·설명·태그 | `index.html`의 `#projects` |
| 프로젝트 상세 설명 | `app.js`의 `projectContent` |
| 탐구 노트의 목록 제목 | `index.html`의 `#notes` |
| 탐구 노트 본문 | `app.js`의 `noteContent` |
| 배경색·강조색 | `styles.css`의 `:root` |
| 모바일 배치 | `styles.css`의 `@media` 규칙 |
| 회고 입력 힌트 | `app.js`의 `fieldDefinitions` |
| 내보낸 회고의 작성자 이름 | `app.js` 제출 처리의 `작성자: 김바로` 문자열 |
| 탭 제목·검색 설명 | `index.html`의 `<title>`, `<meta name="description">` |
| 탭 아이콘 | `favicon.svg` |

프로젝트를 추가하려면 카드, 분류 값, 상세 콘텐츠 키를 함께 맞춥니다. 예를 들어 카드 버튼에 `data-project="new-project"`를 넣었다면 `projectContent['new-project']`도 정의해야 합니다. 프로젝트 개수 표시는 고정 문자열이므로 필요할 때 HTML에서 직접 수정해야 합니다.

## 9. 로컬 실행과 확인

ZIP을 풀고 이 문서가 있는 폴더에서 실행합니다. Python은 정적 파일을 제공하는 용도로만 사용합니다.

### Windows PowerShell

```powershell
py -m http.server 8000 --bind 127.0.0.1 --directory dist
```

`py` 명령을 찾지 못하면 다음을 사용합니다.

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory dist
```

### macOS·Linux

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

브라우저에서 http://127.0.0.1:8000/ 을 엽니다. 서버를 종료할 때는 터미널에서 `Ctrl+C`를 누릅니다. `index.html`을 바로 열어 볼 수도 있지만, 회고 저장 출처를 일관되게 다루려면 위처럼 로컬 HTTP 서버를 사용하는 편이 좋습니다.

Node.js가 이미 있다면 JavaScript 문법을 다음 명령으로 확인할 수 있습니다. Node.js는 사이트 실행에 반드시 필요한 프로그램은 아닙니다.

```bash
node --check dist/app.js
```

| 확인 항목 | 기대 결과 |
| --- | --- |
| 프로젝트 분류 버튼 클릭 | 선택한 분류의 카드만 표시 |
| 프로젝트·노트 클릭 | 해당 상세창 표시 |
| 닫기 버튼·Escape | 팝업 닫힘 |
| 회고 입력 후 새로고침 | 같은 브라우저·같은 출처에서 초안 복원 |
| KPT → 4L → KPT 전환 | 앞서 작성한 KPT 내용 유지 |
| 내용 없이 내보내기 | 먼저 내용을 쓰라는 안내 |
| 내용을 입력하고 내보내기 | `.md` 파일 다운로드 시작 |
| 화면 너비 줄이기 | 주요 영역이 세로로 배치됨 |

이 문서와 파일을 모으는 작업에서는 원본 일치 여부, JavaScript 문법, HTML 참조, ZIP 무결성을 확인했습니다. 원본 코드를 변경하지 않았으므로 기존 사이트를 다시 배포하지 않았습니다.

## 10. 호스팅 설정과 외부 서비스

`.openai/hosting.json`의 `static.directory`는 `dist`입니다. `project_id`는 현재 BARO.LOG 사이트의 ID이며, 로컬 실행에서는 이 설정 파일을 읽지 않습니다. 별도의 새 사이트로 배포하려면 새 호스팅 프로젝트에 맞게 설정해야 합니다.

현재 호스팅 주소의 ChatGPT 로그인·소유자 전용 접근 제어는 **Sites가 제공하는 기능**입니다. 이 HTML·JS 안에 로그인 서버가 들어 있지는 않습니다. 다른 정적 호스팅에 올릴 때 같은 접근 제한이 자동으로 따라가는 것은 아닙니다.

외부 연결은 Google Fonts 서체 로딩과 GitHub·티스토리 링크입니다. 이 개인 사이트가 Sea-Info의 API를 직접 호출하거나 방명록의 DB에 접속하지는 않습니다. 페이지에 표시되는 프로젝트 검증 상태는 작성 당시 설명이며 자동 갱신되지 않습니다.

## 11. 원본과 이번에 추가한 파일 구분

| 구분 | 해당 파일 |
| --- | --- |
| 배포된 사이트 코드 그대로 | `dist/index.html`, `dist/styles.css`, `dist/app.js`, `dist/favicon.svg` |
| 기존 호스팅 설정 그대로 | `.openai/hosting.json` |
| 기존 안내 문서 그대로 | `ORIGINAL_README.md` |
| 이번에 추가한 설명 자료 | `README.md`, `BARO_LOG_CODE_GUIDE.md`, `SOURCE_MANIFEST.json` |

`SOURCE_MANIFEST.json`은 복사한 원본 파일의 SHA-256을 기록합니다. 코드 내용과 설정은 배포 버전과 비교해 일치하는지 확인했습니다. Git 관리 폴더, 배포용 압축파일, 임시 테스트 페이지, 인증 토큰과 브라우저 초안은 코드 모음에 포함하지 않았습니다.
