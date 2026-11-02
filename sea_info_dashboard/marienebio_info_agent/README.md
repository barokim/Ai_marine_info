# BARO.LOG — 사이트 코드 모음

김바로의 개인 웹사이트 **「BARO.LOG · 바다와 AI 사이」**를 구성하는 코드와 설명서를 모은 폴더입니다.

- 사이트: https://baro-ocean-logbook.aio-4-9335.chatgpt.site
- 기준: 2026년 10월 26일 배포 버전 1
- 원본 커밋: `accfb84880eb212cf77f3e7d4bbbe52518bfccc8`

## 먼저 읽을 문서

**[BARO_LOG_CODE_GUIDE.md](BARO_LOG_CODE_GUIDE.md)**에 파일별 코드 설명, 기능별 동작 흐름, 수정 방법, 저장 방식과 현재 한계를 정리했습니다.

## 파일 구성

| 경로 | 역할 |
| --- | --- |
| `dist/index.html` | 페이지의 내용과 화면 구조 |
| `dist/styles.css` | 색상·서체·배치·모바일 화면 디자인 |
| `dist/app.js` | 필터, 상세 팝업, 회고 입력·저장·내보내기 |
| `dist/favicon.svg` | 브라우저 탭에 표시하는 아이콘 |
| `.openai/hosting.json` | 기존 Sites 프로젝트와 정적 파일 폴더 설정 |
| `BARO_LOG_CODE_GUIDE.md` | 한국어 코드 설명서 |
| `ORIGINAL_README.md` | 사이트 제작 당시의 원본 README |
| `SOURCE_MANIFEST.json` | 원본 버전과 파일별 SHA-256 확인 정보 |

HTML·CSS·JavaScript·SVG 원본과 호스팅 설정은 배포 당시 파일을 그대로 복사했습니다. 이 README, 코드 설명서, 파일 확인 정보는 이번 다운로드용으로 추가했습니다. Git 이력과 인증 자격 증명은 포함하지 않았습니다.

## Windows에서 실행하기

ZIP 압축을 푼 뒤, 이 README가 있는 `baro-logbook-source` 폴더를 PowerShell에서 엽니다. Python이 설치되어 있다면 다음 명령을 실행합니다.

```powershell
py -m http.server 8000 --bind 127.0.0.1 --directory dist
```

`py` 명령이 없다면 `python`으로 바꿔 실행합니다. 브라우저에서 **http://127.0.0.1:8000/** 을 열면 됩니다. 종료할 때는 PowerShell에서 `Ctrl+C`를 누릅니다.

macOS·Linux에서는 다음 명령을 사용할 수 있습니다.

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

패키지 설치, API 키, 별도 빌드 과정은 필요하지 않습니다. Google Fonts를 불러오지 못하면 시스템 서체를 사용합니다.

## 실행할 때 알아둘 점

- 이 코드는 **BARO.LOG 개인 사이트**입니다. 소개된 Sea-Info·방명록의 FastAPI 서버 코드는 각 GitHub 저장소에 별도로 있습니다.
- 회고 초안은 브라우저의 `localStorage`에 하나만 저장합니다. 서버 저장이나 기기 간 동기화는 하지 않습니다.
- 날짜를 바꾸어도 같은 초안을 수정합니다. 이전 기록을 남기려면 Markdown으로 먼저 내려받으세요.
- 호스팅된 사이트의 로그인·비공개 접근은 Sites가 제공합니다. 로컬 실행에는 그 로그인 기능이 포함되지 않습니다.
- `.openai/hosting.json`의 `project_id`는 기존 사이트를 가리킵니다. 새 사이트를 만들 때 기존 ID를 그대로 사용하지 마세요.
