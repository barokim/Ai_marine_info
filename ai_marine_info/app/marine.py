"""전국 선택을 기존 외부 API 함수에 전달합니다. 원본의 3개 지역 Literal은 변경하지 않습니다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import re
import os
from types import SimpleNamespace
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool
from .auth import Authenticated, bearer, get_current_user
from .schemas import RecordInput
from .regions import CATALOG, CITIES, STATIONS, ALIASES, city_by_id, select, selection_label

router = APIRouter()


def optional_user(request: Request, credentials=Depends(bearer)):
    if request.headers.get('authorization'):
        return get_current_user(request, credentials)
    return None


OptionalUser = Annotated[object, Depends(optional_user)]


def remember(request, identity, kind, title, result, image=None):
    # 공개 조회는 익명으로 가능합니다. 로그인 회원의 결과만 본인 이력에 저장합니다.
    if identity:
        result['history_id'] = request.app.state.storage.save_history(identity.user.id, kind, title, result, image)
    return result


@router.get('/api/regions')
def regions():
    return CATALOG


@router.get('/api/status')
def status():
    # 실제 값과 상세 네트워크 응답은 노출하지 않고 설정 유무만 반환합니다.
    return {'khoa_tides_configured': bool(os.getenv('KHOA_TIDE_API_KEY') or os.getenv('KHOA_API_KEY')),
            'khoa_observations_configured': bool(os.getenv('KHOA_OBSERVATION_API_KEY') or os.getenv('KHOA_API_KEY')),
            'mbris_configured': bool(os.getenv('MBRIS_API_KEY')),
            'image_analysis_configured': bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),
            'note': '키 설정 여부이며 실제 인증 성공이나 자료 수신을 보증하지 않습니다.'}


@router.get('/api/dashboard')
def dashboard(request: Request, identity: OptionalUser, city_id: str = 'p02-c01', station_id: str | None = None,
              target_date: date | None = None, region: str | None = None):
    # 기존 3개 region 쿼리도 같은 지점으로 연결합니다.
    if region is not None:
        # 구버전의 고정 지역 alias와 새 시·군·구 선택을 한 요청에 섞으면
        # 화면의 선택과 실제 조회 지점이 달라질 수 있으므로 명시적으로 거절합니다.
        if 'city_id' in request.query_params or 'station_id' in request.query_params:
            raise HTTPException(422, '기존 region 값과 전국 지역 선택을 함께 보낼 수 없습니다.')
        if region not in ALIASES:
            raise HTTPException(422, '지역 선택을 확인하세요.')
        city_id, station_id = ALIASES[region]
    city, station = select(city_id, station_id)
    service = request.app.state.legacy.marine
    day = target_date or service.today_kst()
    forecast_region = SimpleNamespace(latitude=city['latitude'], longitude=city['longitude'])
    no_data = {'status': 'no_data', 'note': '해당 지역의 등록된 관측 자료가 없습니다. 다른 지역 관측소를 직접 선택할 수 있습니다.'}
    tides = {**no_data, 'events': []}
    observations = {**no_data, 'water_temperature_c': None, 'observed_at': None}
    # 요청마다 선택 객체를 만들어 다른 사용자의 지역 선택과 섞이지 않게 합니다.
    with ThreadPoolExecutor(max_workers=3) as pool:
        marine_future = pool.submit(service.fetch_live_marine, forecast_region, day)
        tide_future = obs_future = None
        if station and station['tides']:
            target = SimpleNamespace(station_code=station['id'], station_name=station['tide_name'])
            tide_future = pool.submit(service.fetch_tides, target, day)
        if station and station['observations']:
            target = SimpleNamespace(station_code=station['id'], station_name=station['observation_name'])
            obs_future = pool.submit(service.fetch_observations, target, day)
        if tide_future:
            tides = tide_future.result().model_dump(mode='json')
        if obs_future:
            observations = obs_future.result().model_dump(mode='json')
        marine_data = marine_future.result().model_dump(mode='json')
    result = {'selection': selection_label(city, station), 'city': city, 'station': station,
        'target_date': day.isoformat(), 'timezone': 'Asia/Seoul', 'tides': tides,
        'observations': observations, 'marine': marine_data, 'coordinate_note': CATALOG['coordinate_note']}
    return remember(request, identity, 'dashboard', result['selection']['requested_area'] + ' · ' + day.isoformat(), result)


@router.get('/api/species')
def species(request: Request, identity: OptionalUser, q: str = Query(min_length=1, max_length=80),
            provider: Literal['auto', 'mbris', 'worms'] = 'auto', page: int = Query(1, ge=1, le=5000)):
    q = q.strip()
    if not q:
        raise HTTPException(422, '검색어를 입력하세요.')
    legacy = request.app.state.legacy
    if provider == 'mbris' or (provider == 'auto' and re.search('[가-힣]', q)):
        try:
            data = legacy.marine.get_mbris_page(q, page_no=page)
        except RuntimeError:
            raise HTTPException(503, '국명 검색을 처리할 수 없습니다. MBRIS 키·활용승인·연결을 확인하세요.') from None
        result = {'query': q, 'provider': 'mbris', 'source_name': '국립해양생물자원관 MBRIS', **data}
    else:
        result = legacy.species.search_species(q).model_dump(mode='json')
        result['provider'] = 'worms'
    return remember(request, identity, 'species_search', '생물 검색: ' + q, result)


@router.get('/api/species/{aphia_id}')
def species_detail(aphia_id: int, request: Request, identity: OptionalUser):
    if aphia_id < 1:
        raise HTTPException(422, '생물 식별자를 확인하세요.')
    result = request.app.state.legacy.species.species_detail(aphia_id).model_dump(mode='json')
    return remember(request, identity, 'species_detail', result['species']['scientific_name'], result)


@router.post('/api/analyze')
async def analyze(request: Request, identity: Authenticated, file: UploadFile = File(...), consent: bool = Form(...)):
    try:
        if not consent:
            raise HTTPException(400, '사진의 외부 AI 전송과 개인 이력 저장에 동의해 주세요.')
        raw = await file.read(10 * 1024 * 1024 + 1)
    finally:
        await file.close()
    result, jpeg = await run_in_threadpool(request.app.state.legacy.image.analyze_photo, raw)
    return await run_in_threadpool(remember, request, identity, 'image_analysis', '해양생물 사진 분석', result.model_dump(mode='json'), jpeg)


@router.get('/api/records')
def records(request: Request, identity: Authenticated, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    return request.app.state.storage.list_records(identity.user.id, offset, limit)


def validate_record(body):
    city = city_by_id(body.city)
    if city['province_id'] != body.province:
        raise HTTPException(422, '시·도와 시·군·구 선택이 일치하지 않습니다.')


@router.post('/api/records', status_code=201)
def create_record(body: RecordInput, request: Request, identity: Authenticated):
    validate_record(body)
    return request.app.state.storage.save_record(identity.user.id, body.model_dump(mode='json'))


@router.get('/api/records/{record_id}')
def read_record(record_id: UUID, request: Request, identity: Authenticated):
    return request.app.state.storage.get_record(identity.user.id, str(record_id))


@router.put('/api/records/{record_id}')
def update_record(record_id: UUID, body: RecordInput, request: Request, identity: Authenticated):
    validate_record(body)
    return request.app.state.storage.save_record(identity.user.id, body.model_dump(mode='json'), str(record_id))


@router.delete('/api/records/{record_id}', status_code=204)
def delete_record(record_id: UUID, request: Request, identity: Authenticated):
    request.app.state.storage.delete_record(identity.user.id, str(record_id))
    return Response(status_code=204)


@router.get('/api/history')
def history(request: Request, identity: Authenticated, offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
    return request.app.state.storage.list_history(identity.user.id, offset, limit)


@router.get('/api/history/{history_id}')
def read_history(history_id: UUID, request: Request, identity: Authenticated):
    return request.app.state.storage.get_history(identity.user.id, str(history_id))


@router.get('/api/history/{history_id}/image')
def history_image(history_id: UUID, request: Request, identity: Authenticated):
    image = request.app.state.storage.get_history(identity.user.id, str(history_id), image=True)
    return Response(image, media_type='image/jpeg')


@router.delete('/api/history/{history_id}', status_code=204)
def delete_history(history_id: UUID, request: Request, identity: Authenticated):
    request.app.state.storage.delete_history(identity.user.id, str(history_id))
    return Response(status_code=204)
