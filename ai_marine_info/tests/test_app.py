"""포트를 열지 않고 ASGI 앱과 실제 SDK를 모의 HTTP 응답에 연결해 검증합니다."""
from dataclasses import replace
from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient

# 실제 .env를 만들지 않으며 환경변수 값도 출력하지 않습니다.
os.environ['SUPABASE_URL'] = 'https://example.supabase.co'
os.environ['SUPABASE_PUBLISHABLE_KEY'] = 'sb_publishable_test_only'
from app.config import ROOT, load_settings
from app.main import create_app
from app.regions import CATALOG, STATIONS

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
NOW = '2026-10-30T00:00:00+00:00'


def user(uid=A):
    return {'id': uid, 'aud': 'authenticated', 'role': 'authenticated', 'email': 'a@example.com' if uid == A else 'b@example.com',
            'created_at': NOW, 'app_metadata': {'provider': 'email'}, 'user_metadata': {'name': '가회원' if uid == A else '나회원'}}


def session():
    return {'access_token': 'token-a', 'refresh_token': 'not-persisted', 'expires_in': 3600,
            'expires_at': 4102444800, 'token_type': 'bearer', 'user': user()}


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        settings = replace(load_settings(), database=Path(self.temp.name) / 'member.sqlite3')
        self.app = create_app(settings)
        self.calls = []
        self.post_rows = {}
        self.password = 'test-password-123'
        self.special = None
        # 실제 HTTPTransport만 대체하므로 Supabase SDK·PostgREST 코드는 그대로 실행됩니다.
        self.network = patch.object(httpx.HTTPTransport, 'handle_request', self.transport)
        self.network.start()
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.network.stop()
        self.temp.cleanup()

    @staticmethod
    def headers(uid=A):
        return {'Authorization': 'Bearer token-a' if uid == A else 'Bearer token-b'}

    def transport(self, request):
        self.calls.append(request)
        if self.special:
            result = self.special(request)
            if result is not None:
                result.headers['x-supabase-api-version'] = '2024-01-01'
                return result
        path, method = request.url.path, request.method
        token = request.headers.get('authorization', '')
        uid = A if token == 'Bearer token-a' else B if token == 'Bearer token-b' else None
        if path == '/auth/v1/user' and method == 'GET':
            return httpx.Response(200, json=user(uid)) if uid else httpx.Response(401, json={'code':'bad_jwt','msg':'invalid'}, headers={'x-supabase-api-version':'2024-01-01'})
        if path == '/auth/v1/token':
            if json.loads(request.content)['password'] != self.password:
                return httpx.Response(400, json={'code':'invalid_credentials','msg':'invalid'}, headers={'x-supabase-api-version':'2024-01-01'})
            return httpx.Response(200, json=session())
        if path == '/auth/v1/signup':
            return httpx.Response(200, json=user())
        if path == '/auth/v1/recover':
            return httpx.Response(200, json={})
        if path == '/auth/v1/verify':
            return httpx.Response(200, json=session())
        if path == '/auth/v1/user' and method == 'PUT':
            self.password = json.loads(request.content)['password']
            return httpx.Response(200, json=user())
        if path == '/auth/v1/logout':
            return httpx.Response(204)
        if path == '/rest/v1/posts':
            self.assertIn(token, {'Bearer token-a','Bearer token-b'})
            self.assertTrue(request.headers['apikey'].startswith('sb_publishable_'))
            if method == 'POST':
                body=json.loads(request.content)
                self.assertEqual(body['author_id'], uid)
                row={**body,'id':str(uuid4()),'created_at':NOW,'updated_at':NOW}
                self.post_rows[row['id']]=row
                return httpx.Response(201,json=[row])
            rows=list(self.post_rows.values())
            key=request.url.params.get('id','').removeprefix('eq.')
            if key:
                rows=[row for row in rows if row['id']==key]
            if method in {'PATCH','DELETE'}:
                self.assertEqual(request.url.params.get('author_id'), 'eq.'+uid)
                rows=[row for row in rows if row['author_id']==uid]
                if method=='PATCH':
                    for row in rows: row.update(json.loads(request.content))
                else:
                    for row in rows:self.post_rows.pop(row['id'])
            return httpx.Response(200,json=rows,headers={'content-range':f'0-{max(0,len(rows)-1)}/{len(rows)}'})
        raise AssertionError('모의 응답을 정의하지 않은 외부 요청입니다: '+path)

    def test_pages_render_without_network(self):
        for path in ['/', '/tides','/ocean','/login','/signup','/forgot-password','/reset-password','/confirm-email','/board','/records','/history','/photo','/species','/privacy','/about','/docs']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertIn('AI-marine',response.text)
            self.assertIn('no-store',response.headers['cache-control'])
            self.assertIn("script-src 'self'",response.headers['content-security-policy'])
        self.assertEqual(self.calls,[])

    def test_board_all_routes_require_bearer(self):
        key=str(uuid4())
        for method,path,body in [('GET','/posts',None),('GET','/posts/'+key,None),('POST','/posts',{'title':'글','content':'내용'}),('PUT','/posts/'+key,{'title':'글','content':'내용'}),('DELETE','/posts/'+key,None)]:
            response=self.client.request(method,path,json=body)
            self.assertEqual(response.status_code,401)
        self.assertEqual(self.calls,[])

    def test_invalid_token_is_verified_by_auth(self):
        response=self.client.get('/me',headers={'Authorization':'Bearer forged'})
        self.assertEqual(response.status_code,401)
        self.assertEqual(self.calls[0].url.path,'/auth/v1/user')

    def test_signup_name_and_login(self):
        response=self.client.post('/auth/signup',json={'email':'a@example.com','password':'test-password-123','name':'가회원'})
        self.assertEqual(response.status_code,200,response.text)
        payload=json.loads(self.calls[-1].content)
        self.assertEqual(payload['data']['name'],'가회원')
        response=self.client.post('/auth/login',json={'email':'a@example.com','password':'test-password-123'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['access_token'],'token-a')
        self.assertNotIn('refresh_token',response.json())
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_post_create_read_and_cross_user_mutations(self):
        response=self.client.post('/posts',headers=self.headers(),json={'title':'첫 글','content':'<script>alert(1)</script>'})
        self.assertEqual(response.status_code,201,response.text)
        key=response.json()['id']
        self.assertEqual(self.client.get('/posts',headers=self.headers(B)).json()['total'],1)
        self.assertEqual(self.client.get('/posts/'+key,headers=self.headers(B)).status_code,200)
        self.assertEqual(self.client.put('/posts/'+key,headers=self.headers(B),json={'title':'변경','content':'변경'}).status_code,404)
        self.assertEqual(self.client.delete('/posts/'+key,headers=self.headers(B)).status_code,404)
        self.assertEqual(self.client.put('/posts/'+key,headers=self.headers(),json={'title':'수정','content':'내용'}).status_code,200)
        self.assertEqual(self.client.delete('/posts/'+key,headers=self.headers()).status_code,204)

    def test_owner_spoofing_rejected(self):
        response=self.client.post('/posts',headers=self.headers(),json={'title':'글','content':'내용','author_id':B})
        self.assertEqual(response.status_code,422)
        self.assertFalse(any(r.url.path.startswith('/rest/') for r in self.calls))

    def test_password_not_echoed_in_validation(self):
        secret='exposed-never'
        response=self.client.post('/auth/signup',json={'email':'invalid','password':{'value':secret},'name':'회원'})
        self.assertEqual(response.status_code,422)
        self.assertNotIn(secret,response.text)
        self.assertNotIn('input',response.json())
        self.assertTrue(all(set(error)=={'loc','type'} for error in response.json()['errors']))

    def test_auth_error_codes_precede_http_status(self):
        for code,status,expected in [('invalid_credentials',400,401),('email_not_confirmed',400,403),('unexpected_failure',500,503),('over_request_rate_limit',429,429)]:
            self.special=lambda r,c=code,s=status: httpx.Response(s,json={'code':c,'msg':'sensitive internal information'}) if r.url.path.endswith('/token') else None
            response=self.client.post('/auth/login',json={'email':'a@example.com','password':'password'})
            self.assertEqual(response.status_code,expected)
            self.assertNotIn('sensitive',response.text)

    def test_forgot_password_does_not_reveal_missing_user(self):
        good=self.client.post('/auth/forgot-password',json={'email':'a@example.com'})
        self.special=lambda r:httpx.Response(400,json={'code':'user_not_found','msg':'missing'}) if r.url.path.endswith('/recover') else None
        missing=self.client.post('/auth/forgot-password',json={'email':'missing@example.com'})
        self.assertEqual((good.status_code,good.json()),(missing.status_code,missing.json()))
        for request in self.calls:
            self.assertNotIn('token',request.url.params)

    def test_recovery_verifies_code_then_updates_password(self):
        response=self.client.post('/auth/reset-password',json={'email':'a@example.com','token':'123456','password':'new-password-123'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([r.url.path for r in self.calls],['/auth/v1/verify','/auth/v1/user','/auth/v1/logout'])
        self.assertEqual(json.loads(self.calls[0].content)['type'],'recovery')
        self.assertEqual(json.loads(self.calls[1].content)['password'],'new-password-123')
        self.assertTrue(all('123456' not in str(r.url) for r in self.calls))
        self.assertNotIn('access_token',response.text)
        self.assertEqual(self.client.post('/auth/login',json={'email':'a@example.com','password':'new-password-123'}).status_code,200)
        self.assertEqual(self.client.post('/auth/login',json={'email':'a@example.com','password':'test-password-123'}).status_code,401)

    def test_failed_recovery_never_changes_password(self):
        self.special=lambda r:httpx.Response(403,json={'code':'otp_expired','msg':'expired'}) if r.url.path.endswith('/verify') else None
        response=self.client.post('/auth/reset-password',json={'email':'a@example.com','token':'123456','password':'new-password-123'})
        self.assertEqual(response.status_code,401)
        self.assertFalse(any(r.method=='PUT' for r in self.calls))

    def test_personal_records_and_history_are_isolated(self):
        payload={'title':'관찰','province':'p01','city':'p01-c05','observed_on':'2026-10-30','note':'나의 메모','favorite':True}
        response=self.client.post('/api/records',headers=self.headers(),json=payload)
        self.assertEqual(response.status_code,201,response.text)
        key=response.json()['id']
        self.assertEqual(self.client.get('/api/records',headers=self.headers(B)).json(),[])
        self.assertEqual(self.client.get('/api/records/'+key,headers=self.headers(B)).status_code,404)
        self.assertEqual(self.client.put('/api/records/'+key,headers=self.headers(B),json=payload).status_code,404)
        self.assertEqual(self.client.delete('/api/records/'+key,headers=self.headers(B)).status_code,404)
        hid=self.app.state.storage.save_history(A,'image_analysis','사진',{'safe':True},b'jpeg')
        self.assertEqual(self.client.get('/api/history/'+hid+'/image',headers=self.headers(B)).status_code,404)
        self.assertEqual(self.client.get('/api/history/'+hid,headers=self.headers(B)).status_code,404)
        self.assertEqual(self.client.get('/api/history',headers=self.headers(B)).json(),[])
        self.assertEqual(self.client.get('/api/history/'+hid+'/image',headers=self.headers()).content,b'jpeg')

    def test_regions_codes_match_official_guide(self):
        self.assertEqual(len(CATALOG['provinces']),11)
        self.assertGreaterEqual(len(CATALOG['cities']),70)
        self.assertGreaterEqual(len(CATALOG['stations']),100)
        self.assertEqual(len(STATIONS),len(CATALOG['stations']))
        source=json.loads((ROOT/'data/station_sources.json').read_text(encoding='utf-8'))
        for station in STATIONS.values():
            for feature in ['tides','observations']:
                self.assertEqual(station[feature],station['id'] in source[feature]['codes'])
        self.assertFalse(STATIONS['SO_1268']['observations'])

    def test_public_national_dashboard_and_aliases(self):
        service=self.app.state.legacy.marine
        m=lambda **values:SimpleNamespace(model_dump=lambda **kwargs:values)
        with patch.object(service,'fetch_live_marine',return_value=m(status='ok',points=[],note='모델')), \
             patch.object(service,'fetch_tides',return_value=m(status='ok',events=[],note='공식')) as tide, \
             patch.object(service,'fetch_observations',return_value=m(status='ok',water_temperature_c=20.1,note='실측')):
            for city,station in [('p01-c05','DT_0002'),('p03-c02','DT_0012'),('p05-c01','DT_0018')]:
                response=self.client.get('/api/dashboard',params={'city_id':city,'station_id':station})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(tide.call_args.args[0].station_code,station)
                self.assertNotIn('history_id',response.json())
            for alias in ['incheon','busan','jeju']:
                self.assertEqual(self.client.get('/api/dashboard',params={'region':alias}).status_code,200)
        self.assertEqual(self.calls,[])

    def test_missing_station_and_other_area_are_explicit(self):
        service=self.app.state.legacy.marine
        result=SimpleNamespace(model_dump=lambda **kwargs:{'status':'ok','points':[],'note':'예보'})
        with patch.object(service,'fetch_live_marine',return_value=result), patch.object(service,'fetch_tides',return_value=result), patch.object(service,'fetch_observations',return_value=result):
            response=self.client.get('/api/dashboard',params={'city_id':'p01-c01'})
            self.assertEqual(response.json()['tides']['status'],'no_data')
            response=self.client.get('/api/dashboard',params={'city_id':'p01-c01','station_id':'DT_0012'})
            self.assertTrue(response.json()['selection']['is_other_area'])
        self.assertEqual(self.client.get('/api/dashboard?city_id=unknown').status_code,422)

    def test_request_limits_and_origin(self):
        self.assertEqual(self.client.post('/auth/login',content=b'x'*65537).status_code,413)
        self.assertEqual(self.client.post('/auth/login',headers={'Origin':'https://other.example'},json={}).status_code,403)
        for _ in range(10):
            response=self.client.post('/auth/forgot-password',json={'email':'a@example.com'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post('/auth/forgot-password',json={'email':'a@example.com'}).status_code,429)

    def test_photo_requires_login_and_consent(self):
        self.assertEqual(self.client.post('/api/analyze',files={'file':('x.jpg',b'x','image/jpeg')},data={'consent':'true'}).status_code,401)
        response=self.client.post('/api/analyze',headers=self.headers(),files={'file':('x.jpg',b'x','image/jpeg')},data={'consent':'false'})
        self.assertEqual(response.status_code,400)

    def test_original_env_loader_not_called(self):
        source=ROOT.parent/'sea_info_dashboard'
        # 어댑터는 원본 앱·DB를 로드하지 않고 네 서비스 모듈만 연결합니다.
        self.assertEqual(set(self.app.state.legacy.modules),{'models','services','species_service','image_service'})
        self.assertEqual(self.app.state.legacy.source,source)
        self.assertNotEqual(self.app.state.storage.path,source/'data/sea_info.sqlite3')

    def test_real_marine_parser_with_national_station_fixture(self):
        service=self.app.state.legacy.marine
        target=SimpleNamespace(station_code='DT_0012',station_name='속초')
        tide={'obsvtrNm':'속초','predcDt':'2026-10-30 10:30:00','predcTdlvVl':'32','extrSe':1}
        with patch.object(service,'khoa_items',return_value=[tide]):
            result=service.fetch_tides(target,date(2026,10,30))
            self.assertEqual(result.status,'ok')
            self.assertEqual(result.events[0].height_cm,32)
            self.assertEqual(result.events[0].kind,'high')
        observation={'obsvtrNm':'속초','obsrvnDt':'2026-10-30 09:00:00','wtem':'18.2','bscTdlvHgt':'25','wspd':'1.1','artmp':'17.0'}
        with patch.object(service,'khoa_items',return_value=[observation]), patch.object(service,'today_kst',return_value=date(2026,10,30)):
            result=service.fetch_observations(target,date(2026,10,30))
            self.assertEqual(result.status,'ok')
            self.assertEqual(result.water_temperature_c,18.2)
        with patch.object(service,'khoa_items',return_value=[{**tide,'obsvtrNm':'부산'}]):
            self.assertEqual(service.fetch_tides(target,date(2026,10,30)).status,'error')

    def test_species_and_photo_use_existing_services(self):
        result={'items':[{'mbris_id':'1','korean_name':'김','scientific_name':'Pyropia'}], 'page_no':1,'num_of_rows':20,'total_count':1,'has_more':False}
        with patch.object(self.app.state.legacy.marine,'get_mbris_page',return_value=result):
            response=self.client.get('/api/species?q=김')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['provider'],'mbris')
        vision={'identification':{'status':'uncertain','candidates':[]},'database_matches':[],'database_note':'대조','specimen_edibility':'미판정'}
        with patch.object(self.app.state.legacy.image,'analyze_photo',return_value=(SimpleNamespace(model_dump=lambda **kwargs:vision),b'clean-jpeg')):
            response=self.client.post('/api/analyze',headers=self.headers(),files={'file':('photo.jpg',b'fixture','image/jpeg')},data={'consent':'true'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(self.app.state.storage.list_history(A,0,10)),1)
            self.assertEqual(self.app.state.storage.list_history(B,0,10),[])

    def test_startup_rejects_secret_key_and_non_https(self):
        with patch.dict(os.environ,{'SUPABASE_PUBLISHABLE_KEY':'sb_secret_not_allowed'}):
            with self.assertRaises(RuntimeError):load_settings()
        with patch.dict(os.environ,{'SUPABASE_URL':'http://example.com'}):
            with self.assertRaises(RuntimeError):load_settings()

    def test_confirm_email_and_logout(self):
        response=self.client.post('/auth/confirm-email',json={'email':'a@example.com','token':'123456'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(json.loads(self.calls[-1].content)['type'],'signup')
        response=self.client.post('/auth/logout',headers=self.headers())
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.calls[-1].headers['authorization'],'Bearer token-a')
        self.assertEqual(self.calls[-1].url.params['scope'],'local')


if __name__ == '__main__':
    unittest.main()
