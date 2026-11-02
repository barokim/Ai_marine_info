"""Day6 연결: BaseModel, Field, Literal, 검증기, 중첩 모델, PATCH."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RegionId = Literal["incheon", "busan", "jeju"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Region(BaseModel):
    id: RegionId
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class TideEvent(BaseModel):
    time: datetime
    kind: Literal["high", "low"]
    height_cm: float


class TideInfo(BaseModel):
    mode: Literal["demo"]
    source_name: str
    note: str
    events: list[TideEvent]


class MarinePoint(BaseModel):
    time: datetime
    wave_height_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sea_surface_temperature_c: float | None = Field(default=None, allow_inf_nan=False)


class MarineInfo(BaseModel):
    mode: Literal["demo", "live"]
    source_name: str
    source_url: str
    note: str
    fetched_at: datetime
    points: list[MarinePoint] = Field(min_length=1)


class DashboardResponse(BaseModel):
    region: Region
    target_date: date
    timezone: str
    tides: TideInfo
    marine: MarineInfo


class Species(BaseModel):
    id: int
    name: str
    scientific_name: str
    group: str
    food_information: str
    source_url: str


class RecordCreate(InputModel):
    title: str = Field(min_length=2, max_length=80)
    region: RegionId
    observed_on: date
    note: str | None = Field(default=None, max_length=500)
    favorite: bool = Field(default=False, strict=True)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        # 길이를 검사하기 전에 공백부터 정리합니다.
        return value.strip() if isinstance(value, str) else value


class RecordOut(RecordCreate):
    id: int


class RecordPatch(InputModel):
    # None 허용 여부는 병합한 최종 RecordOut에서도 다시 검증합니다.
    title: str | None = Field(default=None, min_length=2, max_length=80)
    region: RegionId | None = None
    observed_on: date | None = None
    note: str | None = Field(default=None, max_length=500)
    favorite: bool | None = Field(default=None, strict=True)
