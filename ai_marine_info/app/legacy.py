"""기존 서비스 소스를 복사·변경하지 않고 독립 네임스페이스에서 읽습니다.

기존 파일은 `from models import ...` 같은 최상위 import를 쓰므로 단순 패키지
import가 불가능합니다. 원본 모듈 내부의 import만 연결하며 sys.path를 바꾸지 않습니다.
기존 .env 자동 로딩 호출만 AST에서 제외하여 새 프로젝트의 설정이 유일한 기준이 됩니다.
"""
import ast
import builtins
from pathlib import Path
from types import ModuleType
import sys


class LegacyServices:
    ALLOWED = {'models', 'services', 'species_service', 'image_service'}

    def __init__(self, source: Path):
        self.source = source
        self.modules = {}
        for name in ('models', 'services', 'species_service', 'image_service'):
            self.load(name)

    def load(self, name):
        if name in self.modules:
            return self.modules[name]
        path = self.source / (name + '.py')
        if not path.is_file():
            raise RuntimeError('SEA_INFO_SOURCE 경로에 기존 대시보드 서비스 파일이 필요합니다.')
        qualified = f'_ai_marine_legacy_{id(self)}_{name}'
        module = ModuleType(qualified)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': self.import_module}
        self.modules[name] = module
        sys.modules[qualified] = module
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        if name == 'services':
            tree.body = [node for node in tree.body if not (
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == '_load_project_env')]
        exec(compile(tree, str(path), 'exec'), module.__dict__)
        return module

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in self.ALLOWED:
            return self.load(name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    @property
    def marine(self):
        return self.modules['services']

    @property
    def species(self):
        return self.modules['species_service']

    @property
    def image(self):
        return self.modules['image_service']
