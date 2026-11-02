"""개인 기록은 새 SQLite 파일에 저장합니다. 모든 쿼리에 회원 ID를 바인딩합니다."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4
from fastapi import HTTPException


class Storage:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS records_owner ON records(owner_id, created_at);
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL,
                    title TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL, image BLOB);
                CREATE INDEX IF NOT EXISTS history_owner ON history(owner_id, created_at);
            ''')

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def record(row):
        if row is None:
            raise HTTPException(404, '관찰 기록을 찾을 수 없습니다.')
        return {'id': row['id'], **json.loads(row['payload']), 'created_at': row['created_at'], 'updated_at': row['updated_at']}

    def list_records(self, user_id, offset=0, limit=30):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM records WHERE owner_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (user_id, limit, offset)).fetchall()
        return [self.record(row) for row in rows]

    def get_record(self, user_id, record_id):
        with self.connect() as db:
            return self.record(db.execute('SELECT * FROM records WHERE id=? AND owner_id=?', (record_id, user_id)).fetchone())

    def save_record(self, user_id, payload, record_id=None):
        now = self.now()
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.connect() as db:
            if record_id:
                if db.execute('UPDATE records SET payload=?,updated_at=? WHERE id=? AND owner_id=?', (encoded, now, record_id, user_id)).rowcount == 0:
                    raise HTTPException(404, '관찰 기록을 찾을 수 없습니다.')
            else:
                record_id = str(uuid4())
                db.execute('INSERT INTO records VALUES (?,?,?,?,?)', (record_id, user_id, encoded, now, now))
            return self.record(db.execute('SELECT * FROM records WHERE id=? AND owner_id=?', (record_id, user_id)).fetchone())

    def delete_record(self, user_id, record_id):
        with self.connect() as db:
            if db.execute('DELETE FROM records WHERE id=? AND owner_id=?', (record_id, user_id)).rowcount == 0:
                raise HTTPException(404, '관찰 기록을 찾을 수 없습니다.')

    def save_history(self, user_id, kind, title, result, image=None):
        key = str(uuid4())
        with self.connect() as db:
            db.execute('INSERT INTO history VALUES (?,?,?,?,?,?,?)', (key, user_id, kind, title[:160], json.dumps(result, ensure_ascii=False, allow_nan=False), self.now(), image))
        return key

    def list_history(self, user_id, offset, limit):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,kind,title,created_at,image IS NOT NULL AS has_image FROM history WHERE owner_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (user_id, limit, offset))]

    def get_history(self, user_id, key, image=False):
        with self.connect() as db:
            row = db.execute('SELECT * FROM history WHERE id=? AND owner_id=?', (key, user_id)).fetchone()
        if row is None or (image and row['image'] is None):
            raise HTTPException(404, '조회 이력을 찾을 수 없습니다.')
        if image:
            return row['image']
        return {'id': row['id'], 'kind': row['kind'], 'title': row['title'], 'created_at': row['created_at'], 'result': json.loads(row['result']), 'has_image': row['image'] is not None}

    def delete_history(self, user_id, key):
        with self.connect() as db:
            if db.execute('DELETE FROM history WHERE id=? AND owner_id=?', (key, user_id)).rowcount == 0:
                raise HTTPException(404, '조회 이력을 찾을 수 없습니다.')
