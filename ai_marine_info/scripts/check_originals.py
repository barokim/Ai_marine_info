"""연결 대상 원본이 구현 시점의 참조 버전과 같은지 확인합니다. 어떤 파일도 수정하지 않습니다."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'docs/legacy_manifest.json').read_text(encoding='utf-8'))
source = (ROOT / manifest['relative_source']).resolve()
changed = []
for name, digest in manifest['files'].items():
    path = source / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        changed.append(name)
if changed:
    print('참조 버전과 다른 원본 파일: ' + ', '.join(changed))
    sys.exit(1)
print(f'원본 참조 파일 {len(manifest["files"])}개 일치. 원본에 쓰기 작업을 하지 않았습니다.')
