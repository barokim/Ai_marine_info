"""선택한 시·군·구와 관측소를 별개로 검증해 다른 지역 자료의 오표시를 막습니다."""
import json
from fastapi import HTTPException
from .config import ROOT

CATALOG = json.loads((ROOT / 'data/regions.json').read_text(encoding='utf-8'))
CITIES = {city['id']: city for city in CATALOG['cities']}
STATIONS = {station['id']: station for station in CATALOG['stations']}
PROVINCES = {province['id']: province for province in CATALOG['provinces']}
ALIASES = {'incheon': ('p02-c01', 'DT_0001'), 'busan': ('p08-c04', 'DT_0005'), 'jeju': ('p11-c01', 'DT_0004')}


def city_by_id(city_id):
    if city_id not in CITIES:
        raise HTTPException(422, '지원하는 해안 시·군·구를 선택하세요.')
    return CITIES[city_id]


def select(city_id, station_id=None):
    city = city_by_id(city_id)
    if station_id:
        if station_id not in STATIONS:
            raise HTTPException(422, '관측소 선택을 확인하세요.')
        station = STATIONS[station_id]
    else:
        station = next((s for s in STATIONS.values() if s['city_id'] == city_id), None)
    return city, station


def selection_label(city, station):
    label = PROVINCES[city['province_id']]['name'] + ' ' + city['name']
    if station:
        actual = CITIES[station['city_id']]
        source = PROVINCES[actual['province_id']]['name'] + ' ' + actual['name']
        return {'requested_area': label, 'station_area': source, 'station_name': station['name'],
                'is_other_area': actual['id'] != city['id']}
    return {'requested_area': label, 'station_area': None, 'station_name': None, 'is_other_area': False}
