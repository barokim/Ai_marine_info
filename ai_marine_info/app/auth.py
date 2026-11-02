"""수업의 요청별 클라이언트·Bearer 검증 패턴을 공통 의존성으로 확장합니다."""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, AuthApiError, AuthRetryableError
from supabase.client import ClientOptions
from .schemas import Login, Signup, EmailInput, Confirmation, PasswordReset, Message, CurrentUser, TokenResponse

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def make_client(http_client, settings):
    return create_client(settings.url, settings.key, options=ClientOptions(
        persist_session=False, auto_refresh_token=False, httpx_client=http_client))


def raise_auth_error(exc):
    code = exc.code
    if code in {'invalid_credentials', 'bad_jwt', 'session_not_found', 'user_not_found', 'user_banned', 'refresh_token_not_found', 'otp_expired', 'otp_disabled'}:
        raise HTTPException(401, '이메일·비밀번호 또는 인증 코드의 유효기간을 확인하세요.', headers={'WWW-Authenticate': 'Bearer'}) from None
    if code == 'email_not_confirmed':
        raise HTTPException(403, '이메일 확인을 완료한 뒤 로그인하세요.') from None
    if exc.status == 429 or code in {'over_request_rate_limit', 'over_email_send_rate_limit'}:
        raise HTTPException(429, '요청이 많습니다. 잠시 후 다시 시도하세요.') from None
    if exc.status >= 500 or exc.status in (401, 403):
        raise HTTPException(503, '인증 서비스 상태 또는 연결 설정을 확인하세요.') from None
    raise HTTPException(400, '입력 내용과 인증 설정을 확인해 주세요.') from None


@contextmanager
def auth_client(request):
    try:
        with httpx.Client(timeout=10.0) as transport:
            yield make_client(transport, request.app.state.settings)
    except AuthApiError as exc:
        raise_auth_error(exc)
    except (AuthRetryableError, httpx.HTTPError):
        raise HTTPException(503, '인증 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요.') from None


def user_model(user):
    name = str((user.user_metadata or {}).get('name', '')).strip()[:50]
    return CurrentUser(id=str(user.id), email=user.email, name=name or '회원')


@dataclass
class Identity:
    user: CurrentUser
    token: str


def get_current_user(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(401, '로그인이 필요합니다.', headers={'WWW-Authenticate': 'Bearer'})
    token = credentials.credentials
    with auth_client(request) as client:
        result = client.auth.get_user(token)
    if result is None or result.user is None:
        raise HTTPException(401, '로그인이 필요합니다.', headers={'WWW-Authenticate': 'Bearer'})
    # JWT 문자열을 직접 디코딩해서 사용자나 권한을 결정하지 않습니다.
    return Identity(user_model(result.user), token)


Authenticated = Annotated[Identity, Depends(get_current_user)]


@router.get('/me', response_model=CurrentUser)
def me(identity: Authenticated):
    return identity.user


@router.post('/auth/signup', response_model=Message)
def signup(body: Signup, request: Request):
    with auth_client(request) as client:
        try:
            client.auth.sign_up({'email': str(body.email), 'password': body.password.get_secret_value(),
                'options': {'data': {'name': body.name}, 'email_redirect_to': request.app.state.settings.signup_redirect}})
        except AuthApiError as exc:
            if exc.code not in {'user_already_exists', 'email_exists'}:
                raise
    return Message(message='가입 요청을 처리했습니다. 이메일 확인이 필요하면 받은 메일의 인증 코드를 입력해 주세요.')


@router.post('/auth/login', response_model=TokenResponse)
def login(body: Login, request: Request, response: Response):
    with auth_client(request) as client:
        result = client.auth.sign_in_with_password({'email': str(body.email), 'password': body.password.get_secret_value()})
    if result.session is None or result.user is None:
        raise HTTPException(502, '로그인 응답을 확인할 수 없습니다.')
    response.headers['Cache-Control'] = 'no-store'
    return TokenResponse(access_token=result.session.access_token, expires_in=result.session.expires_in,
        expires_at=result.session.expires_at, user=user_model(result.user))


@router.post('/auth/logout', response_model=Message)
def logout(request: Request, identity: Authenticated):
    with auth_client(request) as client:
        # SDK 메서드 이름에 admin이 있지만 /logout은 검증된 사용자 JWT로 호출합니다.
        # 서비스 롤을 쓰지 않으며 sign_out의 오류 자동 무시도 피합니다.
        client.auth.admin.sign_out(identity.token, scope='local')
    return Message(message='로그아웃했습니다.')


@router.post('/auth/forgot-password', response_model=Message)
def forgot_password(body: EmailInput, request: Request):
    with auth_client(request) as client:
        try:
            client.auth.reset_password_for_email(str(body.email), {'redirect_to': request.app.state.settings.reset_redirect})
        except AuthApiError as exc:
            # 계정 존재에 따라 달라질 수 있는 오류·메일 재전송 제한은 같은 안내로 덮습니다.
            if exc.code not in {'user_not_found', 'email_not_found', 'over_email_send_rate_limit'}:
                raise
    return Message(message='입력하신 이메일로 재설정이 가능한 경우 안내 메일을 보냈습니다. 메일함을 확인해 주세요.')


@router.post('/auth/confirm-email', response_model=Message)
def confirm_email(body: Confirmation, request: Request):
    with auth_client(request) as client:
        client.auth.verify_otp({'email': str(body.email), 'token': body.token.get_secret_value(), 'type': 'signup'})
    return Message(message='이메일 확인을 완료했습니다. 로그인해 주세요.')


@router.post('/auth/reset-password', response_model=Message)
def reset_password(body: PasswordReset, request: Request):
    with auth_client(request) as client:
        # 메일의 일회용 코드는 JSON 본문으로만 전달합니다. URL에 토큰이 남지 않습니다.
        result = client.auth.verify_otp({'email': str(body.email), 'token': body.token.get_secret_value(), 'type': 'recovery'})
        if result.session is None or result.user is None:
            raise HTTPException(401, '재설정 인증 코드를 확인하세요.')
        client.auth.update_user({'password': body.password.get_secret_value()})
        try:
            client.auth.admin.sign_out(result.session.access_token, scope='global')
        except (AuthApiError, AuthRetryableError, httpx.HTTPError):
            # 변경 자체는 이미 성공했습니다. 실패로 안내해 예전 비밀번호를 재시도하게 하지 않습니다.
            return Message(message='비밀번호를 변경했습니다. 기존 세션의 로그아웃 처리는 확인하지 못했습니다. 새 비밀번호로 로그인해 주세요.')
    return Message(message='비밀번호를 변경했습니다. 새 비밀번호로 로그인해 주세요.')
