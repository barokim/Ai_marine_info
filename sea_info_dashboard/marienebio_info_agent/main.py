"""실행: python -m uvicorn main:app --reload --port 8001"""
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from models import DashboardResponse, RecordCreate, RecordOut, RecordPatch, Region, RegionId, Species
from services import REGIONS, get_dashboard, today_kst

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Sea-Info Agent · 학습용 대시보드", version="0.1.0",
              description="Day6의 Pydantic 검증, 외부 API 호출, 중첩 응답, 메모리 CRUD를 연결합니다.")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 실제 사진 분석 결과가 아닌 도감 검색 UI 연습용 항목입니다.
SPECIES = [
    Species(id=1, name="바지락", scientific_name="Ruditapes philippinarum", group="패류",
            food_information="식용 자료 미연결 · 사진 속 개체의 섭취 안전성 판단 불가", source_url="https://www.mbris.kr/"),
    Species(id=2, name="꽃게", scientific_name="Portunus trituberculatus", group="갑각류",
            food_information="식용 자료 미연결 · 사진 속 개체의 섭취 안전성 판단 불가", source_url="https://www.mbris.kr/"),
    Species(id=3, name="돌기해삼", scientific_name="Apostichopus japonicus", group="극피동물",
            food_information="식용 자료 미연결 · 사진 속 개체의 섭취 안전성 판단 불가", source_url="https://www.mbris.kr/"),
]

# 수업 자료처럼 메모리에만 저장합니다. 재시작하면 초기화되므로 로컬 단일 사용자용입니다.
_records: dict[int, RecordOut] = {}
_next_id = 1
_lock = Lock()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/regions", response_model=list[Region], tags=["조회"])
def list_regions():
    return list(REGIONS.values())


@app.get("/api/dashboard", response_model=DashboardResponse, tags=["조회"])
def dashboard(region: RegionId = "incheon", target_date: date | None = None,
              mode: Literal["demo", "live"] = "demo"):
    return get_dashboard(region, target_date or today_kst(), mode)


@app.get("/api/species", response_model=list[Species], tags=["도감"])
def search_species(q: str = Query(default="", max_length=80)):
    keyword = q.strip().casefold()
    return [item for item in SPECIES if keyword in f"{item.name} {item.scientific_name} {item.group}".casefold()]


@app.get("/api/records", response_model=list[RecordOut], tags=["관찰 기록 CRUD"])
def list_records():
    with _lock:
        return sorted(_records.values(), key=lambda item: item.id, reverse=True)


@app.get("/api/records/{record_id}", response_model=RecordOut, tags=["관찰 기록 CRUD"])
def get_record(record_id: int):
    with _lock:
        if record_id not in _records:
            raise HTTPException(404, "관찰 기록을 찾을 수 없습니다.")
        return _records[record_id]


@app.post("/api/records", response_model=RecordOut, status_code=201, tags=["관찰 기록 CRUD"])
def create_record(payload: RecordCreate):
    global _next_id
    with _lock:
        record = RecordOut(id=_next_id, **payload.model_dump())
        _records[record.id] = record
        _next_id += 1
        return record


@app.patch("/api/records/{record_id}", response_model=RecordOut, tags=["관찰 기록 CRUD"])
def patch_record(record_id: int, payload: RecordPatch):
    with _lock:
        if record_id not in _records:
            raise HTTPException(404, "관찰 기록을 찾을 수 없습니다.")
        changes = payload.model_dump(exclude_unset=True)
        merged = {**_records[record_id].model_dump(), **changes}
        try:
            updated = RecordOut.model_validate(merged)
        except ValidationError as exc:
            # ValueError 자체를 담는 ctx는 JSON 응답에서 제외합니다.
            raise HTTPException(422, exc.errors(include_context=False)) from exc
        _records[record_id] = updated
        return updated


@app.delete("/api/records/{record_id}", status_code=204, tags=["관찰 기록 CRUD"])
def delete_record(record_id: int):
    with _lock:
        if record_id not in _records:
            raise HTTPException(404, "관찰 기록을 찾을 수 없습니다.")
        del _records[record_id]
    return Response(status_code=204)
