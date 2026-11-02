"""서버 소유권 조건과 Postgres RLS를 모두 적용합니다."""
from contextlib import contextmanager
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request, Response
from postgrest.exceptions import APIError
from .auth import Authenticated, auth_client
from .schemas import PostInput, PostResponse, PostPage

router = APIRouter()
logger = logging.getLogger(__name__)
FIELDS = 'id,author_id,author_name,title,content,created_at,updated_at'


@contextmanager
def posts_table(request, identity):
    try:
        with auth_client(request) as client:
            # publishable 키만 쓰면 anon입니다. 반드시 이 요청 사용자의 JWT를 설정합니다.
            client.postgrest.auth(identity.token)
            yield client.table('posts')
    except APIError as exc:
        code = str(exc.code or 'unknown')
        # 오류 코드만 기록합니다. 원본 오류에는 DB 응답·요청 정보가 섞일 수 있어
        # 전체 예외 문자열이나 토큰, URL은 로그에 남기지 않습니다.
        logger.warning('Supabase 게시판 요청 실패 (PostgREST code=%s)', code)
        if code in {'PGRST301', 'PGRST302', 'PGRST303'}:
            raise HTTPException(401, '로그인이 만료되었습니다. 다시 로그인해 주세요.') from None
        if code == '42501':
            raise HTTPException(403, '게시글 접근 권한이 없습니다.') from None
        if code in {'PGRST204', 'PGRST205', '42P01', '42703'}:
            # 테이블·열이 없거나 PostgREST 스키마 캐시가 SQL과 맞지 않는 경우입니다.
            # schema.sql 적용 또는 스키마 변경 반영이 필요한 상황을 일반 연결 오류와 구분합니다.
            raise HTTPException(503,
                '게시판 DB 구조를 찾지 못했습니다. Supabase SQL Editor에서 supabase/schema.sql 적용 여부를 확인하세요.') from None
        raise HTTPException(503, '게시판을 처리할 수 없습니다. DB 설정과 연결을 확인하세요.') from None


def one(result):
    if not result.data:
        # 없는 글과 다른 회원의 글을 구분하지 않습니다.
        raise HTTPException(404, '게시글을 찾을 수 없습니다.')
    return result.data[0]


@router.get('/posts', response_model=PostPage)
def list_posts(request: Request, identity: Authenticated, limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0, le=100000)):
    with posts_table(request, identity) as table:
        result = table.select('id,author_id,author_name,title,created_at,updated_at', count='exact').order('created_at', desc=True).order('id', desc=True).range(offset, offset+limit-1).execute()
    return {'items': result.data, 'total': result.count, 'limit': limit, 'offset': offset}


@router.get('/posts/{post_id}', response_model=PostResponse)
def read_post(post_id: UUID, request: Request, identity: Authenticated):
    with posts_table(request, identity) as table:
        return one(table.select(FIELDS).eq('id', str(post_id)).limit(1).execute())


@router.post('/posts', status_code=201, response_model=PostResponse)
def create_post(body: PostInput, request: Request, identity: Authenticated):
    with posts_table(request, identity) as table:
        return one(table.insert({**body.model_dump(), 'author_id': identity.user.id, 'author_name': identity.user.name}).execute())


@router.put('/posts/{post_id}', response_model=PostResponse)
def update_post(post_id: UUID, body: PostInput, request: Request, identity: Authenticated):
    with posts_table(request, identity) as table:
        return one(table.update(body.model_dump()).eq('id', str(post_id)).eq('author_id', identity.user.id).execute())


@router.delete('/posts/{post_id}', status_code=204)
def delete_post(post_id: UUID, request: Request, identity: Authenticated):
    with posts_table(request, identity) as table:
        one(table.delete().eq('id', str(post_id)).eq('author_id', identity.user.id).execute())
    return Response(status_code=204)
