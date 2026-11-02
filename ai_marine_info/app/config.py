"""실제 설정값을 출력하지 않고 시작 전에 형식만 검사합니다."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
# load_dotenv는 `python-dotenv` 패키지가 제공하는 함수입니다.
# requirements.txt에 의존성을 기록했으므로 프로젝트 가상환경으로 설치하고,
# IDE에서도 ai_marine_info/.venv 인터프리터를 선택해야 이 import 경고가 사라집니다.
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    url: str
    key: str
    origin: str
    reset_redirect: str
    signup_redirect: str
    source: Path
    database: Path


def load_settings() -> Settings:
    # 작업 폴더가 아니라 이 config.py가 있는 프로젝트 루트의 .env만 읽습니다.
    # python-dotenv가 없으면 조용히 건너뛰지 않고 ImportError를 내어 잘못된
    # 가상환경으로 실행한 문제를 드러냅니다. README의 프로젝트 전용 Python을 쓰세요.
    load_dotenv(ROOT / '.env', override=False, interpolate=False)
    url = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '').strip()
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise RuntimeError('SUPABASE_URL에 올바른 https Project URL을 설정하세요.')
    if not key.startswith('sb_publishable_'):
        raise RuntimeError('SUPABASE_PUBLISHABLE_KEY에 publishable 키를 설정하세요.')
    origin = os.getenv('APP_ORIGIN', 'http://127.0.0.1:8002').rstrip('/')
    op = urlparse(origin)
    if not op.hostname or op.username or op.query or op.fragment or op.path:
        raise RuntimeError('APP_ORIGIN에는 경로 없는 사이트 주소를 설정하세요.')
    if op.scheme != 'https' and not (op.scheme == 'http' and op.hostname in {'127.0.0.1', 'localhost'}):
        raise RuntimeError('운영 사이트 주소는 HTTPS여야 합니다.')
    reset = os.getenv('SUPABASE_RESET_REDIRECT_URL', origin + '/reset-password')
    signup = os.getenv('SUPABASE_SIGNUP_REDIRECT_URL', origin + '/confirm-email')
    if reset != origin + '/reset-password' or signup != origin + '/confirm-email':
        raise RuntimeError('Redirect URL은 APP_ORIGIN의 /reset-password, /confirm-email로 설정하세요.')
    source = (ROOT / os.getenv('SEA_INFO_SOURCE', '../sea_info_dashboard')).resolve()
    return Settings(url, key, origin, reset, signup, source, ROOT / 'data/private/member.sqlite3')
