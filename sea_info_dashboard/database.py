"""표준 라이브러리 sqlite3만 사용합니다. 연결은 요청마다 열고 반드시 닫습니다."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from models import HistoryDetail, HistorySummary, RecordCreate, RecordOut, RecordPatch

DEFAULT_DB = Path(__file__).parent / "data" / "sea_info.sqlite3"


@contextmanager
def connect():
    path = Path(os.getenv("SEA_INFO_DB_PATH", str(DEFAULT_DB)))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                query_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                image_jpeg BLOB
            );
            CREATE INDEX IF NOT EXISTS history_created ON history(id DESC);
        """)


def create_record(payload: RecordCreate) -> RecordOut:
    with connect() as db:
        cursor = db.execute("INSERT INTO records(payload) VALUES (?)", (payload.model_dump_json(),))
        return RecordOut(id=cursor.lastrowid, **payload.model_dump())


def record_from_row(row) -> RecordOut:
    if row is None:
        raise HTTPException(404, "관찰 기록을 찾을 수 없습니다.")
    return RecordOut(id=row["id"], **json.loads(row["payload"]))


def list_records() -> list[RecordOut]:
    with connect() as db:
        return [record_from_row(row) for row in db.execute("SELECT id,payload FROM records ORDER BY id DESC")]


def get_record(record_id: int) -> RecordOut:
    with connect() as db:
        return record_from_row(db.execute("SELECT id,payload FROM records WHERE id=?", (record_id,)).fetchone())


def update_record(record_id: int, patch: RecordPatch) -> RecordOut:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        stored = record_from_row(db.execute("SELECT id,payload FROM records WHERE id=?", (record_id,)).fetchone())
        merged = {**stored.model_dump(), **patch.model_dump(exclude_unset=True)}
        try:
            updated = RecordOut.model_validate(merged)
        except ValidationError as exc:
            raise HTTPException(422, exc.errors(include_context=False)) from exc
        db.execute("UPDATE records SET payload=? WHERE id=?", (updated.model_dump_json(exclude={"id"}), record_id))
        return updated


def delete_record(record_id: int):
    with connect() as db:
        if db.execute("DELETE FROM records WHERE id=?", (record_id,)).rowcount == 0:
            raise HTTPException(404, "관찰 기록을 찾을 수 없습니다.")


def save_history(kind: str, title: str, query: dict, result: dict,
                 status: str = "ok", image_jpeg: bytes | None = None) -> int:
    # 호출자는 허용한 검색 조건만 전달합니다. API 키·요청 URL·base64는 저장하지 않습니다.
    created = datetime.now(timezone(timedelta(hours=9))).isoformat()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO history(kind,title,status,created_at,query_json,result_json,image_jpeg) VALUES (?,?,?,?,?,?,?)",
            (kind, title[:160], status, created, json.dumps(query, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False, allow_nan=False), image_jpeg))
        return cursor.lastrowid


def list_history(limit: int = 30, offset: int = 0) -> list[HistorySummary]:
    with connect() as db:
        rows = db.execute("SELECT id,kind,title,status,created_at FROM history ORDER BY id DESC LIMIT ? OFFSET ?",
                          (limit, offset)).fetchall()
        return [HistorySummary(**dict(row)) for row in rows]


def get_history(history_id: int) -> HistoryDetail:
    with connect() as db:
        row = db.execute("SELECT id,kind,title,status,created_at,query_json,result_json,image_jpeg IS NOT NULL AS has_image FROM history WHERE id=?",
                         (history_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "저장된 조회 이력을 찾을 수 없습니다.")
    return HistoryDetail(id=row["id"], kind=row["kind"], title=row["title"], status=row["status"],
                         created_at=row["created_at"], query=json.loads(row["query_json"]),
                         result=json.loads(row["result_json"]), has_image=bool(row["has_image"]))


def get_history_image(history_id: int) -> bytes:
    with connect() as db:
        row = db.execute("SELECT image_jpeg FROM history WHERE id=?", (history_id,)).fetchone()
    if row is None or row["image_jpeg"] is None:
        raise HTTPException(404, "저장된 이미지가 없습니다.")
    return row["image_jpeg"]
