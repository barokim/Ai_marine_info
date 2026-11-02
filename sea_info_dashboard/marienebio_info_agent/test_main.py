"""입력 검증, CRUD, 외부 API 경계 검증. 실행: python -m unittest -v"""
import unittest
from datetime import timedelta
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import main
from services import today_kst


class DashboardTests(unittest.TestCase):
    def setUp(self):
        main._records.clear()
        main._next_id = 1
        self.client = TestClient(main.app)
        self.payload = {"title": "  갯벌 관찰  ", "region": "incheon",
                        "observed_on": "2026-10-22", "note": "작은 조개를 봤어요."}

    def test_home_static_and_openapi(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/app.js").status_code, 200)
        self.assertIn("/api/dashboard", self.client.get("/openapi.json").json()["paths"])

    def test_demo_is_explicit_and_timezone_aware(self):
        response = self.client.get("/api/dashboard?region=incheon&target_date=2026-10-22")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tides"]["mode"], "demo")
        self.assertEqual(body["marine"]["mode"], "demo")
        self.assertTrue(body["tides"]["events"][0]["time"].endswith("+09:00"))
        self.assertEqual(len(body["marine"]["points"]), 24)

    def test_invalid_query_and_species_search(self):
        self.assertEqual(self.client.get("/api/dashboard?region=unknown").status_code, 422)
        self.assertEqual(self.client.get("/api/dashboard?target_date=invalid").status_code, 422)
        self.assertEqual(self.client.get("/api/dashboard?mode=invalid").status_code, 422)
        self.assertEqual(len(self.client.get("/api/species", params={"q": "바지락"}).json()), 1)
        self.assertEqual(self.client.get("/api/species?q=zzzz").json(), [])

    def test_record_crud_patch_and_null(self):
        response = self.client.post("/api/records", json=self.payload)
        self.assertEqual(response.status_code, 201)
        record = response.json()
        self.assertEqual(record["title"], "갯벌 관찰")
        path = f"/api/records/{record['id']}"
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.patch(path, json={"favorite": True}).json()["title"], "갯벌 관찰")
        self.assertIsNone(self.client.patch(path, json={"note": None}).json()["note"])
        for field in ["title", "favorite", "region", "observed_on"]:
            self.assertEqual(self.client.patch(path, json={field: None}).status_code, 422)
        self.assertTrue(self.client.get(path).json()["favorite"])
        self.assertEqual(self.client.patch(path, json={}).status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_blank_title_strict_bool_and_extra_field(self):
        for extra in [{"title": "   "}, {"favorite": "true"}, {"unexpected": 1}]:
            self.assertEqual(self.client.post("/api/records", json={**self.payload, **extra}).status_code, 422)
        self.assertEqual(self.client.get("/api/records").json(), [])

    def external_response(self, **changes):
        day = today_kst().isoformat()
        body = {"utc_offset_seconds": 32400,
                "hourly_units": {"wave_height": "m", "sea_surface_temperature": "°C"},
                "hourly": {"time": [f"{day}T00:00", f"{day}T01:00"],
                           "wave_height": [None, 0.8], "sea_surface_temperature": [20.1, None]}}
        body.update(changes)
        return body

    def test_live_api_uses_params_and_preserves_nulls(self):
        with patch("services.httpx.Client") as client:
            connection = client.return_value.__enter__.return_value
            connection.get.return_value = httpx.Response(200, json=self.external_response(),
                                                        request=httpx.Request("GET", "https://example.test"))
            response = self.client.get("/api/dashboard?mode=live")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["marine"]["mode"], "live")
        self.assertEqual(data["tides"]["mode"], "demo")
        self.assertIsNone(data["marine"]["points"][0]["wave_height_m"])
        self.assertEqual(connection.get.call_args.kwargs["params"]["timezone"], "Asia/Seoul")

    def test_live_failure_does_not_fallback(self):
        with patch("services.httpx.Client") as client:
            client.return_value.__enter__.return_value.get.side_effect = httpx.ReadTimeout("timeout")
            self.assertEqual(self.client.get("/api/dashboard?mode=live").status_code, 504)
        with patch("services.httpx.Client") as client:
            connection = client.return_value.__enter__.return_value
            malformed = self.external_response(utc_offset_seconds=0)
            connection.get.return_value = httpx.Response(200, json=malformed,
                                                        request=httpx.Request("GET", "https://example.test"))
            self.assertEqual(self.client.get("/api/dashboard?mode=live").status_code, 502)

    def test_live_date_out_of_range(self):
        day = (today_kst() + timedelta(days=30)).isoformat()
        with patch("services.httpx.Client") as client:
            self.assertEqual(self.client.get(f"/api/dashboard?mode=live&target_date={day}").status_code, 422)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
