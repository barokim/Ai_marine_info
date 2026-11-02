"""앱 팩토리는 테스트에 사용하고 실제 서버 실행은 사용자가 별도로 결정합니다."""
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from threading import Lock
import time
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
try:
    from fastapi.templating import Jinja2Templates
except ImportError as exc:
    # 새 앱을 marine_identifier 같은 다른 가상환경으로 실행하면 그 환경에서
    # Jinja2를 찾지 못합니다. 프로젝트 전용 실행 명령을 알려 오류 원인을 분명히 합니다.
    if 'jinja2' in str(exc).lower():
        raise ImportError(
            'Jinja2가 없습니다. C:\\KBR\\ai_marine_info에서 '
            '.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt를 실행한 뒤 '
            '.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002로 시작하세요.'
        ) from None
    raise
from . import auth, marine, posts
from .config import ROOT, load_settings
from .legacy import LegacyServices
from .storage import Storage


class RequestGuard:
    """본문을 제한한 후 파싱해 큰 multipart 요청도 메모리를 무한히 사용하지 않게 합니다."""
    def __init__(self, app):
        self.app = app
        self.buckets = OrderedDict()
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope['path']
        if path.startswith('/auth/') and scope['method'] == 'POST':
            # 프록시가 임의로 전달한 X-Forwarded-For를 신뢰하지 않습니다.
            key = ((scope.get('client') or ('unknown', 0))[0], path)
            now = time.monotonic()
            with self.lock:
                bucket = self.buckets.setdefault(key, deque())
                while bucket and bucket[0] < now-60:
                    bucket.popleft()
                blocked = len(bucket) >= 10
                if not blocked:
                    bucket.append(now)
                self.buckets.move_to_end(key)
                while len(self.buckets) > 4096:
                    self.buckets.popitem(last=False)
            if blocked:
                return await JSONResponse({'detail': '요청이 많습니다. 1분 후 다시 시도하세요.'}, 429,
                    headers={'Retry-After': '60', 'Cache-Control': 'no-store'})(scope, receive, send)
        if scope['method'] in {'POST', 'PUT', 'PATCH'}:
            maximum = 11 * 1024 * 1024 if path == '/api/analyze' else 64 * 1024
            chunks, total = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                part = message.get('body', b'')
                total += len(part)
                if total > maximum:
                    return await JSONResponse({'detail': '요청 크기가 너무 큽니다. 사진은 10 MiB 이하로 선택하세요.'}, 413)(scope, receive, send)
                chunks.append(part)
                if not message.get('more_body', False):
                    break
            consumed = False

            async def buffered_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return await receive()

            return await self.app(scope, buffered_receive, send)
        return await self.app(scope, receive, send)


PAGES = {
    '/': ('home', '바다의 오늘을 읽다'), '/tides': ('tides', '지역별 물때'),
    '/ocean': ('ocean', '수온·해양 예보'), '/species': ('species', '해양생물 도감'),
    '/photo': ('photo', 'AI 사진 분석'), '/records': ('records', '나의 관찰 기록'),
    '/history': ('history', '나의 조회 이력'), '/board': ('board', '회원 게시판'),
    '/login': ('login', '로그인'), '/signup': ('signup', '회원가입'),
    '/forgot-password': ('forgot', '비밀번호 찾기'), '/reset-password': ('reset', '비밀번호 재설정'),
    '/confirm-email': ('confirm', '이메일 확인'), '/about': ('about', '서비스 소개'),
    '/privacy': ('privacy', '개인정보 안내'),
}


def create_app(settings=None, legacy=None):
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.storage.initialize()
        yield

    app = FastAPI(title='AI-marine info', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.storage = Storage(settings.database)
    app.state.legacy = legacy or LegacyServices(settings.source)
    app.add_middleware(RequestGuard)

    @app.middleware('http')
    async def security_headers(request, call_next):
        # 쿠키 인증은 사용하지 않지만 인증 폼의 타 사이트 요청도 차단합니다.
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin != settings.origin:
            response = JSONResponse({'detail': '허용되지 않은 요청 출처입니다.'}, 403)
        else:
            try:
                response = await call_next(request)
            except Exception:
                # SDK 예외의 URL·본문·키를 서버 기본 traceback으로 유출하지 않습니다.
                response = JSONResponse({'detail': '요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.'}, 500)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if settings.origin.startswith('https://'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc):
        return JSONResponse({'detail': '입력 형식을 확인해 주세요.',
            'errors': [{'loc': error['loc'], 'type': error['type']} for error in exc.errors()]}, status_code=422)

    app.include_router(auth.router)
    app.include_router(posts.router)
    app.include_router(marine.router)
    app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
    templates = Jinja2Templates(directory=ROOT / 'app/templates')

    # docs의 기본 CDN 스크립트는 CSP에서 막힙니다. 읽기 쉬운 로컬 API 안내로 제공합니다.
    @app.get('/docs', response_class=HTMLResponse, include_in_schema=False)
    def api_docs(request: Request):
        return templates.TemplateResponse(request=request, name='page.html', context={'page': 'api', 'title': 'API 안내'})

    def page_endpoint(page, title):
        async def endpoint(request: Request):
            return templates.TemplateResponse(request=request, name='page.html', context={'page': page, 'title': title})
        return endpoint

    for path, (page, title) in PAGES.items():
        app.add_api_route(path, page_endpoint(page, title), methods=['GET'], response_class=HTMLResponse, include_in_schema=False)
    return app


# Uvicorn은 모듈을 불러오는 순간 아래 app을 만들기 때문에 환경 설정도 이때 검사됩니다.
# 설정이 없으면 main.py 자체 오류처럼 보일 수 있어, .env 설정 문제임을 구분해 안내합니다.
try:
    _default_settings = load_settings()
except RuntimeError as exc:
    raise RuntimeError(
        f'{exc} .env.example을 .env로 복사한 뒤 SUPABASE_URL과 '
        'SUPABASE_PUBLISHABLE_KEY 등 필요한 값을 채워 주세요.'
    ) from None

# 설정을 한 번 읽어 주입해 중복 검증을 피하고, 테스트에서는 create_app(settings)를 그대로 사용합니다.
app = create_app(settings=_default_settings)
