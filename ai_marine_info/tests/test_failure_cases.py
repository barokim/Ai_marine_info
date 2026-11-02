"""pytest로 예상 가능한 입력·권한·설정 오류 응답을 독립 사례로 검사합니다."""
from dataclasses import replace
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import os

import pytest
from fastapi.testclient import TestClient
import httpx
import uvicorn

# 테스트 프로젝트용 공개 키만 사용합니다. 실제 Auth 요청은 매개변수화한 부분에서
# 검증 전에 반환되므로 테스트 결과가 Supabase 네트워크 연결에 의존하지 않습니다.
os.environ['SUPABASE_URL'] = 'https://example.supabase.co'
os.environ['SUPABASE_PUBLISHABLE_KEY'] = 'sb_publishable_pytest_only'
from app.config import load_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def mock_supabase_http(monkeypatch):
    """예상 오류 테스트도 실제 Auth 검증 서버나 Postgres에 연결하지 않습니다."""
    def respond(_transport, request):
        if request.url.path == '/auth/v1/user' and request.method == 'GET':
            if request.headers.get('authorization') == 'Bearer token':
                return httpx.Response(200, json={
                    'id':'11111111-1111-4111-8111-111111111111', 'aud':'authenticated',
                    'role':'authenticated', 'email':'test@example.com', 'created_at':'2026-10-30T00:00:00+00:00',
                    'app_metadata':{'provider':'email'}, 'user_metadata':{'name':'테스트 회원'}})
            return httpx.Response(401, json={'code':'bad_jwt','msg':'invalid'}, headers={'x-supabase-api-version':'2024-01-01'})
        raise AssertionError('예상 오류 검증에서 차단되지 않은 외부 HTTP 요청: '+request.url.path)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', respond)


@pytest.fixture
def portal():
    with TemporaryDirectory() as temporary:
        settings = replace(load_settings(), database=Path(temporary) / 'member.sqlite3')
        app = create_app(settings)
        with TestClient(app) as client:
            yield app, client


@pytest.mark.parametrize('payload', [
    {'email': 'not-an-email', 'password': 'long-enough-password', 'name': '회원'},
    {'email': 'user@example.com', 'password': 'short', 'name': '회원'},
    {'email': 'user@example.com', 'password': 'long-enough-password', 'name': '   '},
    {'email': 'user@example.com', 'password': 'long-enough-password', 'name': '회원', 'author_id': 'forged'},
])
def test_signup_rejects_invalid_email_password_name_or_unknown_field(portal, payload):
    _, client = portal
    response = client.post('/auth/signup', json=payload)
    assert response.status_code == 422
    assert 'long-enough-password' not in response.text
    assert 'input' not in response.json()


@pytest.mark.parametrize('authorization', [None, 'Basic not-a-bearer', 'Bearer'])
def test_me_rejects_missing_or_malformed_bearer_without_auth_request(portal, authorization):
    _, client = portal
    headers = {} if authorization is None else {'Authorization': authorization}
    response = client.get('/me', headers=headers)
    assert response.status_code == 401
    assert 'Bearer' in response.headers.get('www-authenticate', '')


@pytest.mark.parametrize('query', [
    {'city_id': 'not-a-region'},
    {'city_id': 'p01-c01', 'station_id': 'not-an-official-station'},
    {'city_id': 'p01-c01', 'region': 'incheon'},
])
def test_dashboard_rejects_unknown_or_conflicting_region_selection(portal, query):
    _, client = portal
    response = client.get('/api/dashboard', params=query)
    assert response.status_code == 422
    assert 'server' not in response.text.lower()


@pytest.mark.parametrize('body,expected', [
    ({'title': '', 'content': '본문'}, 422),
    ({'title': '제목', 'content': '   '}, 422),
    ({'title': '제목', 'content': '본문', 'author_id': 'forged'}, 422),
    ({'title': 'x' * 101, 'content': '본문'}, 422),
    ({'title': '제목', 'content': 'x' * 5001}, 422),
])
def test_posts_reject_blank_oversized_or_spoofed_input(portal, body, expected):
    _, client = portal
    response = client.post('/posts', headers={'Authorization': 'Bearer token'}, json=body)
    assert response.status_code == expected


@pytest.mark.parametrize('owner', [
    {'province': 'p01', 'city': 'p03-c01'},
    {'province': 'p01', 'city': 'p99-c01'},
])
def test_personal_record_rejects_wrong_or_unknown_province_city_pair(portal, owner):
    _, client = portal
    payload = {'title': '관찰', 'observed_on': '2026-10-31', 'note': '', 'favorite': False, **owner}
    response = client.post('/api/records', headers={'Authorization': 'Bearer token'}, json=payload)
    assert response.status_code == 422


def test_auth_rate_limit_returns_retry_after_and_no_store(portal):
    _, client = portal
    # 잘못된 본문도 보호되지 않은 외부 호출 전에 제한 버킷을 소비합니다.
    responses = [client.post('/auth/login', json={}) for _ in range(10)]
    limited = client.post('/auth/login', json={})
    assert all(r.status_code == 422 for r in responses)
    assert limited.status_code == 429
    assert limited.headers['retry-after'] == '60'
    assert limited.headers['cache-control'] == 'no-store'


def test_invalid_publishable_configuration_fails_before_app_start(monkeypatch):
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_secret_forbidden')
    with pytest.raises(RuntimeError, match='publishable'):
        load_settings()


def test_env_example_never_contains_real_credentials():
    example = (Path(__file__).resolve().parents[1] / '.env.example').read_text(encoding='utf-8')
    protected = {'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'KHOA_API_KEY',
                 'KHOA_TIDE_API_KEY', 'KHOA_OBSERVATION_API_KEY', 'MBRIS_API_KEY', 'OPENAI_API_KEY'}
    configured = {}
    for line in example.splitlines():
        key, separator, value = line.partition('=')
        if separator and key in protected:
            configured[key] = value.strip()
    assert protected <= configured.keys()
    assert all(not configured[key] for key in protected)
    assert '.env' in (Path(__file__).resolve().parents[1] / '.gitignore').read_text(encoding='utf-8').splitlines()


def test_large_request_is_rejected_before_json_validation(portal):
    _, client = portal
    response = client.post('/auth/login', content=b'x' * (64 * 1024 + 1))
    assert response.status_code == 413
    assert '요청 크기' in response.json()['detail']


def test_invalid_post_identifier_returns_validation_error(portal):
    _, client = portal
    response = client.get('/posts/not-a-uuid', headers={'Authorization': 'Bearer token'})
    assert response.status_code == 422


def test_loopback_uvicorn_live_http_smoke():
    """임시 DB와 동적 loopback 포트로 실제 TCP 요청을 보내고 서버를 종료합니다."""
    async def run():
        with TemporaryDirectory() as temporary:
            settings = replace(load_settings(), database=Path(temporary) / 'live.sqlite3')
            app = create_app(settings)
            server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0,
                log_level='critical', access_log=False))
            task = asyncio.create_task(server.serve())
            try:
                for _ in range(300):
                    if server.started:
                        break
                    if task.done():
                        raise RuntimeError('로컬 임시 서버가 시작되지 않았습니다.')
                    await asyncio.sleep(0.01)
                assert server.started
                port = server.servers[0].sockets[0].getsockname()[1]
                async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', timeout=5.0) as client:
                    home = await client.get('/')
                    regions = await client.get('/api/regions')
                    board = await client.get('/posts')
                    oversized = await client.post('/auth/login', content=b'x' * (64 * 1024 + 1))
                assert home.status_code == 200 and 'AI-marine info' in home.text
                assert regions.status_code == 200 and len(regions.json()['cities']) == 74
                assert board.status_code == 401
                assert oversized.status_code == 413
            finally:
                server.should_exit = True
                await asyncio.wait_for(task, timeout=5.0)
    asyncio.run(run())
