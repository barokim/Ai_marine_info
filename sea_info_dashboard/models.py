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
    station_code: str
    station_name: str


class TideEvent(BaseModel):
    time: datetime
    kind: Literal["high", "low"]
    height_cm: float


class TideInfo(BaseModel):
    mode: Literal["live"] = "live"
    status: Literal["ok", "not_configured", "error", "no_data"]
    source_name: str
    source_url: str
    station_code: str
    station_name: str
    note: str
    events: list[TideEvent] = Field(default_factory=list)


class MarinePoint(BaseModel):
    time: datetime
    wave_height_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sea_surface_temperature_c: float | None = Field(default=None, allow_inf_nan=False)


class MarineInfo(BaseModel):
    mode: Literal["live"] = "live"
    status: Literal["ok", "error", "no_data"] = "ok"
    source_name: str
    source_url: str
    note: str
    fetched_at: datetime
    points: list[MarinePoint] = Field(default_factory=list)


class ObservationInfo(BaseModel):
    status: Literal["ok", "not_configured", "error", "no_data"]
    source_name: str = "국립해양조사원 조위관측소 최신 관측데이터"
    source_url: str = "https://www.data.go.kr/data/15155508/openapi.do"
    station_code: str
    station_name: str
    observed_at: datetime | None = None
    fetched_at: datetime
    water_temperature_c: float | None = None
    tide_height_cm: float | None = None
    wind_speed_ms: float | None = None
    air_temperature_c: float | None = None
    salinity_psu: float | None = None
    air_pressure_hpa: float | None = None
    wind_direction_deg: float | None = None
    max_gust_speed_ms: float | None = None
    stale: bool = False
    note: str


class DashboardResponse(BaseModel):
    region: Region
    target_date: date
    timezone: str
    tides: TideInfo
    marine: MarineInfo
    observations: ObservationInfo
    history_id: int | None = None


class Species(BaseModel):
    id: int
    name: str
    scientific_name: str
    group: str
    food_information: str
    source_url: str
    rank: str | None = None
    taxonomic_status: str | None = None
    accepted_name: str | None = None
    accepted_id: int | None = None
    authority: str | None = None
    taxonomy: dict[str, str] = Field(default_factory=dict)


class SpeciesSearch(BaseModel):
    query: str
    resolved_query: str
    source_name: str = "WoRMS · World Register of Marine Species"
    source_url: str = "https://www.marinespecies.org/rest/"
    note: str
    items: list[Species]
    history_id: int | None = None


class SpeciesDetail(BaseModel):
    species: Species
    vernaculars: list[dict[str, str]] = Field(default_factory=list)
    distributions: list[str] = Field(default_factory=list)
    note: str
    history_id: int | None = None


class MbrisSpecies(BaseModel):
    # MBRIS 종 식별자는 WoRMS의 정수 AphiaID와 다른 값이므로 별도로 보관합니다.
    mbris_id: str | None = None
    korean_name: str | None = None
    scientific_name: str | None = None
    description: str | None = None


class MbrisSearch(BaseModel):
    query: str
    source_name: str = "MBRIS · 국립해양생물자원관"
    source_url: str = "https://www.data.go.kr/data/15094770/openapi.do"
    note: str = "공식 API의 국명 포함 검색 결과입니다. 페이지당 20건이며, 검색 결과가 없는 국명도 있습니다."
    items: list[MbrisSpecies]
    page_no: int = 1
    num_of_rows: int = 20
    total_count: int | None = None
    has_more: bool = False
    history_id: int | None = None


class HistorySummary(BaseModel):
    id: int
    kind: Literal["dashboard", "species_search", "species_detail", "image_analysis"]
    title: str
    status: str
    created_at: datetime


class HistoryDetail(HistorySummary):
    query: dict
    result: dict
    has_image: bool = False


class VisionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scientific_name: str
    common_name_ko: str
    visual_match: Literal["low", "medium", "high"]
    visible_features: list[str]
    distinguishing_limits: list[str]


class VisionIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["candidates_found", "uncertain", "no_marine_life"]
    image_quality: Literal["poor", "usable", "good"]
    candidates: list[VisionCandidate] = Field(max_length=3)
    explanation: str
    suggested_photos: list[str]


class VisionResult(BaseModel):
    identification: VisionIdentification
    database_matches: list[Species] = Field(default_factory=list)
    database_note: str
    specimen_edibility: str = "사진으로 해당 개체의 식용 안전성을 판단할 수 없습니다."
    source_name: str = "OpenAI 이미지 분석 + WoRMS 학명 대조"
    model: str
    image_sha256: str
    history_id: int | None = None


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
