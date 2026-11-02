"""공식 제공자 응답 → 앱 모델. 실패 시 가짜 데이터로 대체하지 않습니다."""
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError, model_validator

from models import DashboardResponse, MarineInfo, MarinePoint, ObservationInfo, Region, TideEvent, TideInfo


# 실행 디렉터리와 관계없이 이 프로젝트의 키를 읽고, 운영 환경 변수는 유지합니다.
def _load_project_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)


_load_project_env(Path(__file__).resolve().with_name(".env"))

KST = timezone(timedelta(hours=9))
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
MARINE_DOCS = "https://open-meteo.com/en/docs/marine-weather-api"
TIDE_URL = "https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService"
OBS_URL = "https://apis.data.go.kr/1192136/dtRecent/GetDTRecentApiService"
TIDE_DOCS = "https://www.data.go.kr/data/15156018/openapi.do"
OBS_DOCS = "https://www.data.go.kr/data/15155508/openapi.do"
# 활용가이드의 min 기본값 1분을 명시해 최신 관측 시각의 해상도를 유지합니다.
OBSERVATION_INTERVAL_MINUTES = 1
KHOA_ERROR_MESSAGES = {
    "1": "제공기관의 애플리케이션 오류입니다.",
    "2": "제공기관의 데이터베이스 오류입니다.",
    "4": "제공기관의 HTTP 처리 오류입니다.",
    "5": "제공기관 서비스 연결 시간이 초과되었습니다. 잠시 후 다시 조회하세요.",
    "10": "요청 변수의 지점 코드·날짜·시간 간격을 확인하세요.",
    "11": "필수 요청 변수(serviceKey, obsCode)를 확인하세요.",
    "12": "요청한 API가 없거나 폐기되었습니다. 서비스 주소를 확인하세요.",
    "20": "서비스 접근이 거부되었습니다. 해당 API의 활용승인을 확인하세요.",
    "21": "인증키를 일시적으로 사용할 수 없습니다. 제공기관 공지를 확인하세요.",
    "22": "API 요청 한도를 초과했습니다. 호출을 멈추고 이용 한도를 확인하세요.",
    "30": "등록되지 않은 인증키입니다. 발급받은 키와 활용승인을 확인하세요.",
    "31": "인증키의 사용 기한이 만료되었습니다. 이용 기간을 확인하세요.",
    "32": "등록되지 않은 IP입니다. 활용신청의 허용 IP를 확인하세요.",
    "33": "서명되지 않은 호출입니다. 제공기관 인증 설정을 확인하세요.",
    "40": "선택한 관측소의 서비스가 일시 중지되었습니다.",
    "41": "관측 항목의 서비스가 일시 중지되었습니다.",
    "99": "제공기관에서 알 수 없는 오류가 발생했습니다.",
}
REGIONS = {
    "incheon": Region(id="incheon", name="인천 연안", latitude=37.40, longitude=126.45, station_code="DT_0001", station_name="인천"),
    "busan": Region(id="busan", name="부산 연안", latitude=35.05, longitude=129.10, station_code="DT_0005", station_name="부산"),
    "jeju": Region(id="jeju", name="제주 연안", latitude=33.55, longitude=126.50, station_code="DT_0004", station_name="제주"),
}


def today_kst() -> date:
    return datetime.now(KST).date()


def api_key(service: str) -> str:
    return unquote(os.getenv(f"KHOA_{service}_API_KEY", "") or os.getenv("KHOA_API_KEY", "")).strip()


def parse_time(value) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=KST) if parsed.tzinfo is None else parsed.astimezone(KST)


def numeric(value) -> float | None:
    if value is None or str(value).strip().lower() in {"", "-", "null", "none"}:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("유한한 수치가 아닙니다.")
    return None if result in {-99, -999, -9999} else result


def get_json(url: str, params: dict | None = None):
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except ValueError:
                # type=json을 요청해도 XML 본문이 오는 경우 KHOA에 한해 해석합니다.
                if url not in {TIDE_URL, OBS_URL}:
                    raise
                return parse_khoa_xml(response.text)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "외부 API 응답 시간이 초과되었습니다.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        # str(exc)는 인증키를 포함한 요청 URL을 노출할 수 있으므로 사용하지 않습니다.
        raise HTTPException(502, "외부 API에서 올바른 데이터를 받지 못했습니다. 연결 상태와 활용신청을 확인하세요.") from exc


def parse_khoa_xml(text: str) -> dict:
    """가이드 XML 예제와 포털 XML 오류를 기존 JSON 파서용 구조로 변환합니다."""
    try:
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/엔티티는 지원하지 않습니다.")
        root = ElementTree.fromstring(text)
        for node in root.iter():
            node.tag = node.tag.rsplit("}", 1)[-1]
        if root.tag == "OpenAPI_ServiceResponse":
            header = root.find("cmmMsgHeader")
            code = header.findtext("returnReasonCode") if header is not None else None
            if code is None or code.strip() in {"0", "00"}:
                raise ValueError("오류 코드가 없습니다.")
            return {"header": {"resultCode": code}}
        if root.tag != "response":
            raise ValueError("예상한 XML 루트가 아닙니다.")
        header, body = root.find("header"), root.find("body")
        result = {"header": {"resultCode": header.findtext("resultCode") if header is not None else None}}
        if body is not None:
            result["body"] = {name: body.findtext(name) for name in ("totalCount", "pageNo", "numOfRows")
                              if body.find(name) is not None}
            result["body"]["items"] = {"item": [
                {field.tag: field.text for field in item} for item in body.findall("items/item")
            ]}
        return result
    except (ElementTree.ParseError, ValueError) as exc:
        raise HTTPException(502, "국립해양조사원 XML 응답 형식이 올바르지 않습니다.") from exc


def khoa_items(url: str, region: Region, target_date: date, service: str) -> list[dict]:
    key = api_key(service)
    if not key:
        raise HTTPException(503, "국립해양조사원 API 키 설정이 필요합니다. .env의 KHOA_API_KEY를 설정하세요.")
    collected = []
    for page in range(1, 11):
        params = {"serviceKey": key, "obsCode": region.station_code,
                  "reqDate": target_date.strftime("%Y%m%d"), "type": "json",
                  "pageNo": page, "numOfRows": 300}
        if service == "OBSERVATION":
            params["min"] = OBSERVATION_INTERVAL_MINUTES
        data = get_json(url, params)
        items, total = parse_khoa_page(data)
        collected.extend(items)
        if len(collected) >= total:
            return collected
        if not items:
            raise HTTPException(502, "관측 데이터 페이지가 누락되었습니다.")
    raise HTTPException(502, "응답 페이지 수가 예상 범위를 넘었습니다. 일부 자료만 반환하지 않습니다.")


def parse_khoa_page(data) -> tuple[list[dict], int]:
    if not isinstance(data, dict):
        raise HTTPException(502, "국립해양조사원 응답 구조를 확인할 수 없습니다.")
    response = data.get("response", data)
    if not isinstance(response, dict):
        raise HTTPException(502, "국립해양조사원 응답 구조가 다릅니다.")
    header = response.get("header")
    if not isinstance(header, dict):
        raise HTTPException(502, "국립해양조사원 응답 헤더가 올바르지 않습니다.")
    raw_code = str(header.get("resultCode", "")).strip()
    if not raw_code.isascii() or not raw_code.isdigit():
        raise HTTPException(502, "국립해양조사원 응답 코드가 올바르지 않습니다.")
    code = raw_code.lstrip("0") or "0"
    if code == "3":
        return [], 0
    if code != "0":
        # 제공자의 원문 resultMsg는 키·요청 URL이 섞일 수 있어 노출하지 않습니다.
        message = KHOA_ERROR_MESSAGES.get(code, "국립해양조사원에서 정상 응답을 받지 못했습니다.")
        raise HTTPException(429 if code == "22" else 504 if code == "5" else 502, message)
    body = response.get("body")
    if not isinstance(body, dict):
        raise HTTPException(502, "국립해양조사원 응답 본문이 올바르지 않습니다.")
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item") or []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise HTTPException(502, "관측 데이터 목록 형식이 다릅니다.")
    try:
        total = int(body.get("totalCount", len(items)))
        if total < len(items):
            raise ValueError("총 건수가 항목 수보다 작습니다.")
    except (ValueError, TypeError) as exc:
        raise HTTPException(502, "관측 데이터 총 건수가 올바르지 않습니다.") from exc
    return items, total


def check_station(item: dict, region: Region):
    name = str(item.get("obsvtrNm", "")).strip()
    if not name or name != region.station_name:
        raise ValueError("선택한 관측소와 응답의 관측소가 다릅니다.")


def fetch_tides(region: Region, target_date: date) -> TideInfo:
    base = dict(source_name="국립해양조사원 조석예보(고, 저조)", source_url=TIDE_DOCS,
                station_code=region.station_code, station_name=region.station_name)
    try:
        items = khoa_items(TIDE_URL, region, target_date, "TIDE")
        events = []
        for item in items:
            check_station(item, region)
            moment = parse_time(item["predcDt"])
            kind = int(item["extrSe"])
            height = numeric(item.get("predcTdlvVl"))
            if moment.date() != target_date or kind not in {1, 2, 3, 4} or height is None:
                raise ValueError("조석 예보의 날짜·극치 구분·조위를 확인할 수 없습니다.")
            events.append(TideEvent(time=moment, kind="high" if kind in {1, 3} else "low", height_cm=height))
        return TideInfo(**base, status="ok" if events else "no_data",
                        note="공식 고·저조 예보 · 현장 출입 가능 시간을 뜻하지 않습니다." if events else "선택일의 조석 예보가 없습니다.",
                        events=sorted(events, key=lambda e: e.time))
    except HTTPException as exc:
        return TideInfo(**base, status="not_configured" if exc.status_code == 503 else "error", note=str(exc.detail))
    except (ValueError, KeyError, TypeError):
        return TideInfo(**base, status="error", note="조석 예보의 관측소·날짜·응답 필드 검증에 실패했습니다.")


def fetch_observations(region: Region, target_date: date) -> ObservationInfo:
    base = dict(station_code=region.station_code, station_name=region.station_name, fetched_at=datetime.now(KST))
    if target_date > today_kst():
        return ObservationInfo(**base, status="no_data", note="미래 날짜의 실측 관측값은 없습니다.")
    try:
        items = khoa_items(OBS_URL, region, target_date, "OBSERVATION")
        if not items:
            return ObservationInfo(**base, status="no_data", note="선택일에 수신된 관측값이 없습니다.")
        for item in items:
            check_station(item, region)
            if parse_time(item["obsrvnDt"]).date() != target_date:
                raise ValueError("관측일이 다릅니다.")
        latest = max(items, key=lambda i: parse_time(i["obsrvnDt"]))
        moment = parse_time(latest["obsrvnDt"])
        stale = target_date == today_kst() and datetime.now(KST) - moment > timedelta(hours=2)
        return ObservationInfo(**base, status="ok", observed_at=moment,
                               water_temperature_c=numeric(latest.get("wtem")),
                               tide_height_cm=numeric(latest.get("bscTdlvHgt")),
                               wind_speed_ms=numeric(latest.get("wspd")),
                               air_temperature_c=numeric(latest.get("artmp")),
                               salinity_psu=numeric(latest.get("slntQty")),
                               air_pressure_hpa=numeric(latest.get("atmpr")),
                               wind_direction_deg=numeric(latest.get("wndrct")),
                               max_gust_speed_ms=numeric(latest.get("maxMmntWspd")), stale=stale,
                               note="선택일의 마지막 수신 관측값입니다. 미제공 항목은 —로 표시합니다." + (" 관측 시각이 2시간 이상 지났습니다." if stale else ""))
    except HTTPException as exc:
        return ObservationInfo(**base, status="not_configured" if exc.status_code == 503 else "error", note=str(exc.detail))
    except (ValueError, KeyError, TypeError):
        return ObservationInfo(**base, status="error", note="실측 데이터의 관측소·날짜·응답 필드 검증에 실패했습니다.")


class ExternalHourly(BaseModel):
    time: list[datetime]
    wave_height: list[float | None]
    sea_surface_temperature: list[float | None]

    @model_validator(mode="after")
    def check_lengths(self):
        if not self.time or not (len(self.time) == len(self.wave_height) == len(self.sea_surface_temperature)):
            raise ValueError("시간과 값 개수가 다릅니다.")
        return self


class ExternalMarine(BaseModel):
    utc_offset_seconds: int
    hourly_units: dict[str, str]
    hourly: ExternalHourly

    @model_validator(mode="after")
    def check_units(self):
        if self.utc_offset_seconds != 32400 or self.hourly_units.get("wave_height") != "m" or self.hourly_units.get("sea_surface_temperature") != "°C":
            raise ValueError("시간 기준 또는 단위가 다릅니다.")
        return self


def fetch_live_marine(region: Region, target_date: date) -> MarineInfo:
    base = dict(source_name="Open-Meteo Marine Weather API", source_url=MARINE_DOCS, fetched_at=datetime.now(KST))
    if not today_kst() <= target_date <= today_kst() + timedelta(days=3):
        return MarineInfo(**base, status="no_data", note="이 화면의 모델 예보는 오늘~3일 뒤까지 지원합니다.")
    try:
        external = ExternalMarine.model_validate(get_json(MARINE_URL, {
            "latitude": region.latitude, "longitude": region.longitude,
            "hourly": "wave_height,sea_surface_temperature", "timezone": "Asia/Seoul",
            "start_date": target_date.isoformat(), "end_date": target_date.isoformat(), "cell_selection": "sea"}))
        points = []
        for index, moment in enumerate(external.hourly.time):
            moment = parse_time(moment)
            if moment.date() != target_date:
                raise ValueError("조회일과 다릅니다.")
            points.append(MarinePoint(time=moment, wave_height_m=external.hourly.wave_height[index],
                                     sea_surface_temperature_c=external.hourly.sea_surface_temperature[index]))
        if not any(p.wave_height_m is not None or p.sea_surface_temperature_c is not None for p in points):
            return MarineInfo(**base, status="no_data", note="사용 가능한 예보값이 없습니다.")
        return MarineInfo(**base, status="ok", points=points,
                          note="대표 해역의 모델 예보이며 국립해양조사원 실측값과 다릅니다.")
    except HTTPException as exc:
        return MarineInfo(**base, status="error", note=str(exc.detail))
    except (ValidationError, ValueError, TypeError):
        return MarineInfo(**base, status="error", note="해양 예보의 형식·시간·단위 검증에 실패했습니다.")


def get_dashboard(region_id: str, target_date: date) -> DashboardResponse:
    region = REGIONS[region_id]
    with ThreadPoolExecutor(max_workers=3) as executor:
        tides = executor.submit(fetch_tides, region, target_date)
        marine = executor.submit(fetch_live_marine, region, target_date)
        observations = executor.submit(fetch_observations, region, target_date)
        return DashboardResponse(region=region, target_date=target_date, timezone="Asia/Seoul",
                                 tides=tides.result(), marine=marine.result(), observations=observations.result())

MBRIS_URL = (
    "https://apis.data.go.kr/B553482/"
    "mbrisdataview3/taxonlist3"
)


def get_mbris_page(korean_name: str, page_no: int = 1, num_of_rows: int = 20) -> dict:
    # CommKorNm은 국명 포함 검색입니다. 첫 20건만 받고 끝내지 않도록 페이지도 전달합니다.
    korean_name = korean_name.strip()
    if not korean_name:
        raise ValueError("검색어를 1글자 이상 입력해 주세요.")
    key = unquote(os.getenv("MBRIS_API_KEY", "").strip())
    if not key:
        raise RuntimeError("MBRIS_API_KEY 설정이 필요합니다.")

    try:
        response = httpx.get(
            MBRIS_URL,
            params={
                "serviceKey": key,
                "CommKorNm": korean_name,
                "pageNo": page_no,
                "numOfRows": num_of_rows,
            },
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        # 오류에 인증키가 포함된 요청 URL을 출력하지 않습니다.
        raise RuntimeError("해양생물종 API 통신에 실패했습니다.") from None

    try:
        # 오류 1: ET라는 별칭을 import하지 않아 NameError가 발생했습니다.
        # 상단에서 가져온 이름인 ElementTree로 XML 응답을 읽습니다.
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError:
        # 오류 2: except에서도 미정의 이름 ET를 사용하면 XML 오류를 처리하지 못합니다.
        # ElementTree.ParseError를 잡아 잘못된 XML을 안내 메시지로 바꿉니다.
        raise RuntimeError("XML 응답을 읽지 못했습니다.") from None

    code = (
        root.findtext(".//ResultCode")
        or root.findtext(".//resultCode")
    )
    if code not in {"0", "00"}:
        raise RuntimeError("API 인증·활용승인·요청 한도를 확인하세요.")

    items = [
        {
            "mbris_id": item.findtext("SpcTxnId"),
            "korean_name": item.findtext("CommKorNm"),
            "scientific_name": item.findtext("SpcScitfNmShort")
            or item.findtext("SpcScitfNm"),
            "description": item.findtext("ABST"),
        }
        for item in root.findall(".//item")
    ]
    raw_total = root.findtext(".//totalCount")
    total_count = None
    if raw_total is not None:
        try:
            total_count = int(raw_total)
            if total_count < 0:
                raise ValueError
        except ValueError:
            raise RuntimeError("검색 결과 총 건수를 읽지 못했습니다.") from None
    return {"items": items, "page_no": page_no, "num_of_rows": num_of_rows,
            "total_count": total_count,
            "has_more": page_no * num_of_rows < total_count if total_count is not None else len(items) == num_of_rows}


def search_mbris(korean_name: str) -> list[dict]:
    # 앞서 작성한 단독 실행·학습 코드는 첫 페이지 목록을 계속 받을 수 있습니다.
    return get_mbris_page(korean_name)["items"]


if __name__ == "__main__":
    for species in search_mbris("바지락"):
        print(species)
