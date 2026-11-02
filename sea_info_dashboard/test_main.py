"""실제 인증키·API 비용 없이 공식 응답 계약과 SQLite 영속성을 검증합니다."""
import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image

import database
import image_service
import main
import services
from models import VisionCandidate, VisionIdentification

APHIA = {"AphiaID": 231750, "scientificname": "Ruditapes philippinarum", "isMarine": 1,
         "rank": "Species", "status": "accepted", "valid_name": "Ruditapes philippinarum",
         "valid_AphiaID": 231750, "class": "Bivalvia", "phylum": "Mollusca"}


def small_png():
    output = io.BytesIO()
    Image.new("RGB", (20, 20), "blue").save(output, "PNG")
    return output.getvalue()


class LiveDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "test.sqlite3")
        self.env = patch.dict(os.environ, {"SEA_INFO_DB_PATH": self.db_path,
            "KHOA_API_KEY": "test-key-not-real", "KHOA_TIDE_API_KEY": "", "KHOA_OBSERVATION_API_KEY": "",
            "OPENAI_API_KEY": "", "OPENAI_MODEL": ""})
        self.env.start()
        self.day = services.today_kst().isoformat()
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.payload = {"title": "  갯벌 관찰  ", "region": "incheon", "observed_on": self.day, "note": "작은 조개"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def provider(self, url, params=None):
        if url == services.TIDE_URL:
            return {"response": {"header": {"resultCode": "00"}, "body": {"totalCount": 2, "items": {"item": [
                {"obsvtrNm": "인천", "predcDt": self.day + " 06:20:00", "predcTdlvVl": "760", "extrSe": 1},
                {"obsvtrNm": "인천", "predcDt": self.day + " 12:30:00", "predcTdlvVl": 150, "extrSe": 4}]}}}}
        if url == services.OBS_URL:
            return {"header": {"resultCode": "00"}, "body": {"totalCount": 1, "items": {"item": {
                "obsvtrNm": "인천", "obsrvnDt": self.day + " 00:01:00", "wtem": "19.2", "wspd": "-999", "bscTdlvHgt": "200",
                "slntQty": "27.90", "atmpr": "999.4", "wndrct": "344.00", "maxMmntWspd": "5.0"}}}}
        if url == services.MARINE_URL:
            return {"utc_offset_seconds": 32400, "hourly_units": {"wave_height": "m", "sea_surface_temperature": "°C"},
                    "hourly": {"time": [self.day + "T00:00", self.day + "T01:00"],
                               "wave_height": [None, 0.8], "sea_surface_temperature": [20.1, None]}}
        if "AphiaRecordByAphiaID/" in url:
            return APHIA
        if "AphiaRecordsByName/" in url:
            return [APHIA]
        if "AphiaVernacularsByAphiaID" in url:
            return [{"vernacular": "Manila clam", "language": "English"}]
        if "AphiaDistributionsByAphiaID" in url:
            return [{"locality": "Korea", "recordStatus": "valid"},
                    {"locality": "Unverified locality", "recordStatus": "invalid"}]
        return []

    def test_home_and_schema(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/guide").status_code, 200)
        self.assertEqual(self.client.get("/static/live.css").status_code, 200)
        self.assertIn("/api/analyze", self.client.get("/openapi.json").json()["paths"])

    def test_dashboard_official_contract_and_history(self):
        with patch("services.get_json", side_effect=self.provider):
            response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tides"]["status"], "ok")
        self.assertEqual([x["kind"] for x in data["tides"]["events"]], ["high", "low"])
        self.assertTrue(data["tides"]["events"][0]["time"].endswith("+09:00"))
        self.assertEqual(data["observations"]["water_temperature_c"], 19.2)
        self.assertIsNone(data["observations"]["wind_speed_ms"])
        self.assertEqual(data["observations"]["salinity_psu"], 27.9)
        self.assertEqual(data["observations"]["air_pressure_hpa"], 999.4)
        self.assertEqual(data["observations"]["wind_direction_deg"], 344.0)
        self.assertEqual(data["observations"]["max_gust_speed_ms"], 5.0)
        self.assertIsNone(data["marine"]["points"][0]["wave_height_m"])
        detail = self.client.get(f"/api/history/{data['history_id']}").json()
        self.assertEqual(detail["kind"], "dashboard")
        self.assertEqual(detail["result"]["observations"]["salinity_psu"], 27.9)
        self.assertNotIn("test-key-not-real", json.dumps(detail))

    def test_missing_keys_yields_partial_without_sample(self):
        with patch.dict(os.environ, {"KHOA_API_KEY": ""}), patch("services.get_json", side_effect=self.provider):
            data = self.client.get("/api/dashboard").json()
        self.assertEqual(data["tides"]["status"], "not_configured")
        self.assertEqual(data["tides"]["events"], [])
        self.assertEqual(data["observations"]["status"], "not_configured")
        self.assertEqual(data["marine"]["status"], "ok")

    def test_khoa_params_and_encoded_key(self):
        with patch.dict(os.environ, {"KHOA_API_KEY": "key%2Bvalue%3D"}), patch("services.get_json", side_effect=self.provider) as fetch:
            services.fetch_tides(services.REGIONS["incheon"], services.today_kst())
        params = fetch.call_args.args[1]
        self.assertEqual(params["serviceKey"], "key+value=")
        self.assertEqual(params["obsCode"], "DT_0001")
        self.assertEqual(params["reqDate"], self.day.replace("-", ""))

    def test_wrong_station_or_day_rejected(self):
        data = self.provider(services.TIDE_URL)
        data["response"]["body"]["items"]["item"][0]["obsvtrNm"] = "부산"
        with patch("services.get_json", return_value=data):
            result = services.fetch_tides(services.REGIONS["incheon"], services.today_kst())
        self.assertEqual(result.status, "error")
        self.assertEqual(result.events, [])

    def test_khoa_pagination_and_malformed_envelope(self):
        first = self.provider(services.OBS_URL)
        first["body"]["totalCount"] = 2
        with patch("services.get_json", side_effect=[first, first]) as fetch:
            rows = services.khoa_items(services.OBS_URL, services.REGIONS["incheon"], services.today_kst(), "OBSERVATION")
        self.assertEqual(len(rows), 2)
        self.assertEqual(fetch.call_args.args[1]["pageNo"], 2)
        for malformed in [{"header": "bad"}, {"header": {"resultCode": "00"}, "body": []}]:
            with self.assertRaises(main.HTTPException):
                services.parse_khoa_page(malformed)

    def test_provider_exception_sanitized(self):
        with patch("services.httpx.Client") as client:
            connection = client.return_value.__enter__.return_value
            connection.get.side_effect = httpx.ConnectError("url contains private-key")
            with self.assertRaises(main.HTTPException) as error:
                services.get_json("https://example.test")
        self.assertNotIn("private-key", str(error.exception.detail))

    def test_observations_future_and_forecast_out_of_range(self):
        day = services.today_kst() + timedelta(days=30)
        with patch("services.get_json") as fetch:
            self.assertEqual(services.fetch_observations(services.REGIONS["incheon"], day).status, "no_data")
            self.assertEqual(services.fetch_live_marine(services.REGIONS["incheon"], day).status, "no_data")
            fetch.assert_not_called()

    def test_record_crud_and_patch_revalidation(self):
        record = self.client.post("/api/records", json=self.payload)
        self.assertEqual(record.status_code, 201)
        path = f"/api/records/{record.json()['id']}"
        self.assertEqual(record.json()["title"], "갯벌 관찰")
        self.assertEqual(self.client.patch(path, json={"favorite": True}).json()["title"], "갯벌 관찰")
        self.assertIsNone(self.client.patch(path, json={"note": None}).json()["note"])
        for key in ["title", "region", "observed_on", "favorite"]:
            self.assertEqual(self.client.patch(path, json={key: None}).status_code, 422)
        self.assertTrue(self.client.get(path).json()["favorite"])
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_persistence_after_reopening_app_and_db(self):
        record = self.client.post("/api/records", json=self.payload).json()
        identifier = database.save_history("species_search", "persisted", {"q": "clam"}, {"items": []})
        self.client.__exit__(None, None, None)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.assertEqual(self.client.get(f"/api/records/{record['id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/history/{identifier}").json()["title"], "persisted")
        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM history").fetchone()[0], 1)
        finally:
            connection.close()

    def test_input_constraints(self):
        for changes in [{"title": "   "}, {"favorite": "true"}, {"extra": 1}]:
            self.assertEqual(self.client.post("/api/records", json={**self.payload, **changes}).status_code, 422)
        self.assertEqual(self.client.get("/api/dashboard?region=unknown").status_code, 422)
        self.assertEqual(self.client.get("/api/history?limit=200").status_code, 422)
        self.assertEqual(self.client.get("/api/species?q=%20%20").status_code, 422)

    def test_worms_search_detail_and_save(self):
        with patch("species_service.get_json", side_effect=self.provider):
            search = self.client.get("/api/species", params={"q": "바지락", "provider": "worms"}).json()
            detail = self.client.get("/api/species/231750").json()
        self.assertEqual(search["items"][0]["id"], 231750)
        self.assertEqual(search["resolved_query"], "Ruditapes philippinarum")
        self.assertEqual(detail["vernaculars"][0]["name"], "Manila clam")
        self.assertEqual(detail["distributions"], ["Korea"])
        self.assertEqual(len(self.client.get("/api/history").json()), 2)

    def test_species_empty_and_failure_are_not_local_fallback(self):
        with patch("species_service.get_json", return_value=None):
            self.assertEqual(self.client.get("/api/species?q=unknown").json()["items"], [])
        with patch("species_service.get_json", side_effect=main.HTTPException(502, "외부 검색 오류")):
            self.assertEqual(self.client.get("/api/species?q=unknown").status_code, 502)
        self.assertEqual(self.client.get("/api/history").json()[0]["status"], "error")

    def test_photo_consent_format_and_missing_key(self):
        photo = {"file": ("fish.png", small_png(), "image/png")}
        self.assertEqual(self.client.post("/api/analyze", files=photo, data={"consent": "false"}).status_code, 400)
        self.assertEqual(self.client.post("/api/analyze", files={"file": ("fake.jpg", b"text", "image/jpeg")}, data={"consent": "true"}).status_code, 400)
        self.assertEqual(self.client.post("/api/analyze", files=photo, data={"consent": "true"}).status_code, 503)
        self.assertEqual(self.client.get("/api/history").json(), [])

    def test_photo_analysis_stores_normalized_image_and_result(self):
        identification = VisionIdentification(status="candidates_found", image_quality="usable", candidates=[
            VisionCandidate(scientific_name="Ruditapes philippinarum", common_name_ko="바지락",
                            visual_match="medium", visible_features=["시험용 특징"], distinguishing_limits=["유사종 구분 필요"])],
            explanation="모의 분석 결과", suggested_photos=[])
        with patch("image_service.identify", return_value=identification), patch("image_service.scientific_records", return_value=[APHIA]):
            response = self.client.post("/api/analyze", files={"file": ("fish.png", small_png(), "image/png")}, data={"consent": "true"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["database_matches"][0]["id"], 231750)
        history = self.client.get(f"/api/history/{data['history_id']}").json()
        self.assertTrue(history["has_image"])
        self.assertNotIn("base64", json.dumps(history))
        image = self.client.get(f"/api/history/{data['history_id']}/image")
        self.assertEqual(image.headers["content-type"], "image/jpeg")
        self.assertEqual(Image.open(io.BytesIO(image.content)).format, "JPEG")

    def test_openai_adapter_schema_and_poor_quality_abstention(self):
        result = VisionIdentification(status="candidates_found", image_quality="poor", candidates=[], explanation="흐림", suggested_photos=[])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "not-a-real-key", "OPENAI_MODEL": "configured-model"}), patch("openai.OpenAI") as client:
            response = client.return_value.__enter__.return_value.responses.parse.return_value
            response.status, response.output_parsed = "completed", result
            identification = image_service.identify(b"jpeg")
            call = client.return_value.__enter__.return_value.responses.parse.call_args
        self.assertEqual(identification.status, "uncertain")
        self.assertFalse(call.kwargs["store"])
        self.assertIs(call.kwargs["text_format"], VisionIdentification)

    def test_image_limits(self):
        with patch("image_service.MAX_IMAGE_BYTES", 20):
            response = self.client.post("/api/analyze", files={"file": ("big.png", b"x" * 21)}, data={"consent": "true"})
            self.assertEqual(response.status_code, 413)
        with patch("image_service.MAX_PIXELS", 10):
            with self.assertRaises(main.HTTPException) as error:
                image_service.prepare_image(small_png())
            self.assertEqual(error.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
