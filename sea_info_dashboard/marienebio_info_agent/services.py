"""외부 API 경계. 예시 데이터와 실제 예보를 조용히 바꿔치기하지 않습니다."""
import math
from datetime import date, datetime, time, timedelta, timezone

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from models import DashboardResponse, MarineInfo, MarinePoint, Region, TideEvent, TideInfo

KST = timezone(timedelta(hours=9))
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
MARINE_DOCS = "https://open-meteo.com/en/docs/marine-weather-api"

# 지역 대표 좌표입니다. 사용자의 정확한 위치나 특정 갯벌 관측소가 아닙니다.
REGIONS = {
    "incheon": Region(id="incheon", name="인천 연안", latitude=37.40, longitude=126.45),
    "busan": Region(id="busan", name="부산 연안", latitude=35.05, longitude=129.10),
    "jeju": Region(id="jeju", name="제주 연안", latitude=33.55, longitude=126.50),
}


def today_kst() -> date:
    return datetime.now(KST).date()


def demo_tides(target_date: date) -> TideInfo:
    # 실제 관측/예보값이 아닌 화면 연습용 고정값입니다.
    events = [("00:10", "low", 120), ("06:20", "high", 760),
              ("12:30", "low", 150), ("18:40", "high", 740)]
    return TideInfo(
        mode="demo", source_name="직접 작성한 학습용 예시",
        note="실제 물때가 아닙니다. 국립해양조사원 API 연결 전의 자리표시 데이터입니다.",
        events=[TideEvent(time=datetime.combine(target_date, time.fromisoformat(t), KST),
                          kind=kind, height_cm=height) for t, kind, height in events],
    )


def demo_marine(target_date: date, region_id: str) -> MarineInfo:
    offset = list(REGIONS).index(region_id) * 0.2
    points = [MarinePoint(
        time=datetime.combine(target_date, time(hour=hour), KST),
        wave_height_m=round(0.6 + offset + 0.22 * math.sin(hour / 4), 2),
        sea_surface_temperature_c=round(19.4 + offset + 0.5 * math.sin(hour / 5), 1),
    ) for hour in range(24)]
    return MarineInfo(mode="demo", source_name="직접 작성한 학습용 예시",
                      source_url=MARINE_DOCS, fetched_at=datetime.now(KST), points=points,
                      note="실제 예보가 아닌 화면 연습용 데이터입니다.")


class ExternalHourly(BaseModel):
    time: list[datetime]
    wave_height: list[float | None]
    sea_surface_temperature: list[float | None]

    @model_validator(mode="after")
    def check_lengths(self):
        if not self.time or not (len(self.time) == len(self.wave_height) == len(self.sea_surface_temperature)):
            raise ValueError("외부 API의 시간과 값 개수가 일치하지 않습니다.")
        return self


class ExternalMarine(BaseModel):
    # 제공자가 덧붙이는 메타데이터는 허용하고, 필요한 부분은 검증합니다.
    model_config = ConfigDict(extra="ignore")
    utc_offset_seconds: int
    hourly_units: dict[str, str]
    hourly: ExternalHourly

    @model_validator(mode="after")
    def check_units(self):
        if self.utc_offset_seconds != 32400:
            raise ValueError("한국 시간 기준 응답이 아닙니다.")
        if self.hourly_units.get("wave_height") != "m" or self.hourly_units.get("sea_surface_temperature") != "°C":
            raise ValueError("예상한 단위가 아닙니다.")
        return self


def fetch_live_marine(region: Region, target_date: date) -> MarineInfo:
    # 처음에는 오늘~3일 뒤로 제한해 예보 범위를 이해하기 쉽게 합니다.
    if not today_kst() <= target_date <= today_kst() + timedelta(days=3):
        raise HTTPException(422, "실제 API 조회는 한국 시간 기준 오늘부터 3일 뒤까지 지원합니다.")
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.get(MARINE_URL, params={
                "latitude": region.latitude, "longitude": region.longitude,
                "hourly": "wave_height,sea_surface_temperature", "timezone": "Asia/Seoul",
                "start_date": target_date.isoformat(), "end_date": target_date.isoformat(),
                "cell_selection": "sea",
            })
            response.raise_for_status()
            external = ExternalMarine.model_validate(response.json())
        points = []
        for index, forecast_time in enumerate(external.hourly.time):
            if forecast_time.tzinfo is None:
                forecast_time = forecast_time.replace(tzinfo=KST)
            if forecast_time.astimezone(KST).date() != target_date:
                raise ValueError("요청한 날짜와 다른 예보가 들어왔습니다.")
            points.append(MarinePoint(time=forecast_time,
                                     wave_height_m=external.hourly.wave_height[index],
                                     sea_surface_temperature_c=external.hourly.sea_surface_temperature[index]))
        if not any(p.wave_height_m is not None or p.sea_surface_temperature_c is not None for p in points):
            raise ValueError("사용 가능한 예보값이 없습니다.")
        return MarineInfo(mode="live", source_name="Open-Meteo Marine Weather API",
                          source_url=MARINE_DOCS, fetched_at=datetime.now(KST), points=points,
                          note="지역 대표 좌표에 대한 모델 예보입니다. 현장 실측이나 출입 안전 판정이 아닙니다.")
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "외부 해양 예보 API의 응답 시간이 초과되었습니다.") from exc
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        raise HTTPException(502, "외부 해양 예보를 받거나 검증하지 못했습니다. 예시로 자동 대체하지 않습니다.") from exc


def get_dashboard(region_id: str, target_date: date, mode: str) -> DashboardResponse:
    region = REGIONS[region_id]
    marine = fetch_live_marine(region, target_date) if mode == "live" else demo_marine(target_date, region_id)
    return DashboardResponse(region=region, target_date=target_date, timezone="Asia/Seoul",
                             tides=demo_tides(target_date), marine=marine)
