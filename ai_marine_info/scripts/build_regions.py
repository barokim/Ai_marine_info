"""행정구역과 공식 지점 코드를 결합합니다. 좌표는 예보용 대표 해역이며 관측소 측량 좌표가 아닙니다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 시·군·구 | 대표 해역 위도 | 경도 | 공식 가이드에 실린 지점 이름
GROUPS = {
 '경기도': '''김포시|37.72|126.52|
시흥시|37.33|126.65|
안산시|37.20|126.55|안산
화성시|37.10|126.62|궁평항,국화도
평택시|36.96|126.80|평택''',
 '인천광역시': '''제물포구|37.45|126.55|인천
영종구|37.43|126.40|소무의도,영종왕산,잠진도,영종대교
미추홀구|37.42|126.60|
연수구|37.36|126.60|인천송도
서해구|37.57|126.57|경인항
강화군|37.70|126.35|강화대교,교동대교,강화외포,강화하리,어류정항
옹진군|37.22|126.13|덕적도,영흥도,백령도,연평도,선재도,자월도,승봉도,울도
남동구|37.37|126.69|
검단구|37.62|126.53|''',
 '강원특별자치도': '''고성군|38.42|128.48|거진항,공현진항,아야진항
속초시|38.21|128.64|속초
양양군|38.08|128.70|수산항
강릉시|37.83|128.91|사천진항
동해시|37.53|129.15|묵호,동해항
삼척시|37.39|129.24|호산항,장호항,임원항,덕산항,원평항''',
 '충청남도': '''아산시|36.93|126.91|
당진시|37.00|126.63|
서산시|37.02|126.40|대산,삼길포항
태안군|36.68|126.08|태안,안흥,방포항,어은돌항
홍성군|36.56|126.43|
보령시|36.31|126.43|보령,무창포항,외연도항
서천군|36.10|126.47|장항,서천마량''',
 '전북특별자치도': '''군산시|35.96|126.48|군산,어청도,말도
부안군|35.63|126.40|위도,격포항,상왕등도
고창군|35.43|126.40|구시포항''',
 '전라남도': '''영광군|35.30|126.29|영광,향화도,향화도항,계마항,안마도,낙월도,송이도
함평군|35.08|126.36|
무안군|34.95|126.30|
목포시|34.77|126.32|목포
신안군|34.75|126.03|흑산도,우이도,신안옥도,만재도,상태도
영암군|34.73|126.39|
해남군|34.34|126.47|어란진항
진도군|34.42|126.16|진도,서거차도,벽파진,서망항,독거도
완도군|34.26|126.76|완도,여서도,청산도
강진군|34.43|126.79|사초항
장흥군|34.44|126.98|회진항
보성군|34.67|127.09|율포항
고흥군|34.45|127.40|고흥발포,여호항,나로도,녹동항,남열항
여수시|34.61|127.76|여수,거문도,초도,안도항,연도항
순천시|34.83|127.49|
광양시|34.88|127.77|광양''',
 '경상남도': '''하동군|34.94|127.84|
남해군|34.73|127.95|미조항
사천시|34.90|128.06|삼천포
고성군|34.92|128.35|
통영시|34.78|128.43|통영
거제시|34.77|128.67|거제도,고현항
창원시|35.10|128.63|마산,진해''',
 '부산광역시': '''강서구|35.00|128.82|가덕도,부산항신항
사하구|35.02|128.96|다대포항
서구|35.06|129.01|
중구|35.10|129.05|부산
동구|35.12|129.06|
영도구|35.05|129.09|
남구|35.10|129.12|
수영구|35.14|129.14|
해운대구|35.15|129.19|해운대
기장군|35.24|129.25|대변항''',
 '울산광역시': '''울주군|35.35|129.37|
남구|35.48|129.40|울산
동구|35.50|129.46|
북구|35.61|129.48|정자항''',
 '경상북도': '''경주시|35.78|129.51|감포항
포항시|36.05|129.47|포항,구룡포항,호미곶
영덕군|36.42|129.44|강구항,축산항
울진군|36.99|129.45|후포
울릉군|37.48|130.93|울릉도''',
 '제주특별자치도': '''제주시|33.55|126.50|제주,추자도
서귀포시|33.20|126.55|서귀포,성산포,모슬포,화순항''',
}


def build():
    sources = json.loads((ROOT / 'data/station_sources.json').read_text(encoding='utf-8'))
    tides, observations = sources['tides']['codes'], sources['observations']['codes']
    names = {name: code for code, name in tides.items()}
    names.update({name: code for code, name in observations.items()})
    provinces, cities, stations, unknown = [], [], [], []
    for pindex, (province, lines) in enumerate(GROUPS.items(), 1):
        pid = f'p{pindex:02}'
        provinces.append({'id': pid, 'name': province})
        for cindex, line in enumerate(lines.splitlines(), 1):
            city, lat, lon, labels = line.split('|')
            cid = f'{pid}-c{cindex:02}'
            cities.append({'id': cid, 'province_id': pid, 'name': city, 'latitude': float(lat), 'longitude': float(lon)})
            for name in filter(None, labels.split(',')):
                if name not in names:
                    unknown.append(name)
                    continue
                code = names[name]
                stations.append({'id': code, 'name': name, 'province_id': pid, 'city_id': cid,
                    'tides': code in tides, 'observations': code in observations,
                    'tide_name': tides.get(code), 'observation_name': observations.get(code)})
    result = {'version': '2026-10-30', 'coordinate_note': '시·군·구 대표 해역의 모델 예보 좌표입니다. 관측소의 공식 위치 좌표가 아닙니다.',
        'sources': ['https://www.data.go.kr/data/15156018/openapi.do', 'https://www.data.go.kr/data/15155508/openapi.do'],
        'provinces': provinces, 'cities': cities, 'stations': stations}
    (ROOT / 'data/regions.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print({'provinces': len(provinces), 'cities': len(cities), 'stations': len(stations), 'not_in_guide_excluded': unknown})


if __name__ == '__main__':
    build()
