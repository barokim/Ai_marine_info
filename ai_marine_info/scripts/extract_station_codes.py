"""활용가이드에서 지점 코드·이름만 추출합니다. 예제 인증키는 저장하지 않습니다.
개발 보조: pip install olefile 후 python scripts/extract_station_codes.py <가이드 폴더>
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib
import olefile


def paragraphs(path):
    with olefile.OleFileIO(path) as document:
        compressed = struct.unpack('<I', document.openstream('FileHeader').read()[36:40])[0] & 1
        for name in document.listdir():
            if name[0] != 'BodyText':
                continue
            data = document.openstream(name).read()
            if compressed:
                data = zlib.decompress(data, -15)
            offset = 0
            while offset + 4 <= len(data):
                header = struct.unpack_from('<I', data, offset)[0]
                offset += 4
                size = header >> 20
                if size == 4095:
                    size = struct.unpack_from('<I', data, offset)[0]
                    offset += 4
                if header & 1023 == 67:
                    yield data[offset:offset+size].decode('utf-16le', errors='replace').strip()
                offset += size


def extract(folder, destination):
    result = {}
    for kind, name in [('tides', '오픈API 활용가이드_조석예보(고, 저조).hwp'),
                       ('observations', '오픈API 활용가이드_조위관측소 최신 관측데이터.hwp')]:
        path = folder / name
        lines = list(paragraphs(path))
        codes = {}
        for index, value in enumerate(lines[:-1]):
            if re.fullmatch(r'(DT|SO|IE)_\d{4}', value):
                label = lines[index+1]
                if re.fullmatch(r'[가-힣A-Za-z0-9()· ,.-]{1,30}', label) and '코드' not in label:
                    codes.setdefault(value, label)
        result[kind] = {'source': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'codes': codes}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print({key: len(value['codes']) for key, value in result.items()})


if __name__ == '__main__':
    extract(Path(sys.argv[1]), Path(__file__).resolve().parents[1] / 'data/station_sources.json')
