"""WoRMS 실제 DB 검색. 한국어 별칭은 검색어 변환만 하며 결과는 API에서 받습니다."""
import re
from urllib.parse import quote
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from models import Species, SpeciesDetail, SpeciesSearch
from services import get_json

WORMS = "https://www.marinespecies.org/rest"
KOREAN_SEARCH_ALIASES = {
    "바지락": "Ruditapes philippinarum", "꽃게": "Portunus trituberculatus",
    "돌기해삼": "Apostichopus japonicus", "자주복": "Takifugu rubripes",
    "고등어": "Scomber japonicus", "참굴": "Magallana gigas",
    "전복": "Haliotis", "문어": "Octopoda", "해파리": "Scyphozoa",
}


class AphiaRecord(BaseModel):
    AphiaID: int = Field(gt=0)
    scientificname: str
    isMarine: int | None = None
    rank: str | None = None
    status: str | None = None
    valid_name: str | None = None
    valid_AphiaID: int | None = None
    authority: str | None = None
    kingdom: str | None = None
    phylum: str | None = None
    class_name: str | None = Field(default=None, alias="class")
    order: str | None = None
    family: str | None = None
    genus: str | None = None


def to_species(raw: dict, requested_name: str = "") -> Species:
    try:
        r = AphiaRecord.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(502, "WoRMS 생물 정보 응답을 검증하지 못했습니다.") from exc
    common = requested_name if KOREAN_SEARCH_ALIASES.get(requested_name) == r.scientificname else r.scientificname
    taxonomy = {k: v for k, v in {"계": r.kingdom, "문": r.phylum, "강": r.class_name,
                                  "목": r.order, "과": r.family, "속": r.genus}.items() if v}
    return Species(id=r.AphiaID, name=common, scientific_name=r.scientificname,
                   group=r.class_name or r.phylum or "분류 정보 없음", rank=r.rank,
                   taxonomic_status=r.status, accepted_name=r.valid_name, accepted_id=r.valid_AphiaID,
                   authority=r.authority, taxonomy=taxonomy,
                   food_information="이 분류 DB는 해당 개체의 식용 안전성을 판정하지 않습니다.",
                   source_url=f"https://www.marinespecies.org/aphia.php?p=taxdetails&id={r.AphiaID}")


def scientific_records(query: str, exact: bool = False) -> list[dict]:
    result = get_json(f"{WORMS}/AphiaRecordsByName/{quote(query, safe='')}",
                      {"like": "false" if exact else "true", "marine_only": "true", "offset": 1})
    if result is None:
        return []
    if not isinstance(result, list) or any(not isinstance(r, dict) for r in result):
        raise HTTPException(502, "WoRMS 검색 결과 형식이 다릅니다.")
    return result


def search_species(query: str) -> SpeciesSearch:
    query = query.strip()
    if len(query) < 1:
        raise HTTPException(422, "생물 이름을 1글자 이상 입력해 주세요.")
    resolved = KOREAN_SEARCH_ALIASES.get(query, query)
    if re.search("[가-힣]", resolved):
        raw = get_json(f"{WORMS}/AphiaRecordsByVernacular/{quote(resolved, safe='')}", {"like": "true", "offset": 1}) or []
    else:
        raw = scientific_records(resolved)
        if not raw:
            raw = get_json(f"{WORMS}/AphiaRecordsByVernacular/{quote(resolved, safe='')}", {"like": "true", "offset": 1}) or []
    if not isinstance(raw, list) or any(not isinstance(r, dict) for r in raw):
        raise HTTPException(502, "WoRMS 검색 결과가 올바르지 않습니다.")
    items = [to_species(item, query) for item in raw if item.get("isMarine") == 1][:20]
    return SpeciesSearch(query=query, resolved_query=resolved, items=items,
                         note="실제 WoRMS 분류 DB 검색 결과입니다. 최대 20건. 한국어 일반명은 등록 범위가 제한되며, 일부 이름은 학명 검색어로 변환합니다. 도감 전체나 식용 허가 DB는 아닙니다.")


def species_detail(aphia_id: int) -> SpeciesDetail:
    raw = get_json(f"{WORMS}/AphiaRecordByAphiaID/{aphia_id}")
    if not raw:
        raise HTTPException(404, "WoRMS에 해당 생물 정보가 없습니다.")
    if not isinstance(raw, dict) or raw.get("isMarine") != 1:
        raise HTTPException(404, "해양생물로 등록된 항목이 아닙니다.")
    species = to_species(raw)
    vernaculars, distributions = [], []
    note = "분류 상태·인정 학명과 동의어를 함께 확인하세요. 생태 설명이나 사진은 원문 자료를 참고하세요."
    try:
        names = get_json(f"{WORMS}/AphiaVernacularsByAphiaID/{aphia_id}") or []
        places = get_json(f"{WORMS}/AphiaDistributionsByAphiaID/{aphia_id}") or []
        if not isinstance(names, list) or not isinstance(places, list):
            raise HTTPException(502, "추가 정보 형식이 다릅니다.")
        vernaculars = [{"name": str(n.get("vernacular", "")), "language": str(n.get("language", ""))}
                       for n in names[:30] if isinstance(n, dict)]
        distributions = list(dict.fromkeys(str(d["locality"]) for d in places
                                           if isinstance(d, dict) and d.get("locality")
                                           and d.get("recordStatus") == "valid"))[:30]
    except HTTPException:
        note += " 일부 일반명·분포 추가 정보는 받지 못했습니다."
    return SpeciesDetail(species=species, vernaculars=vernaculars, distributions=distributions, note=note)
