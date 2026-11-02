"""첨부 HWP 가이드 v1.0의 계약을 검증합니다. 키·외부 통신·실제 DB 불필요."""
import unittest
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

import httpx
from fastapi import HTTPException

import services


class KhoaGuideTests(unittest.TestCase):
    def setUp(self):
        self.day = services.today_kst()
        self.region = services.REGIONS["incheon"]

    def test_dotenv_uses_module_directory_and_preserves_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module_dir = root / "app"
            module_dir.mkdir()
            for name in ("services.py", "models.py"):
                shutil.copyfile(Path(__file__).with_name(name), module_dir / name)
            (module_dir / ".env").write_text("KHOA_API_KEY=fixture-file-key\n", encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("KHOA_")}
            code = "import sys; sys.path.insert(0, sys.argv[1]); import services; print(services.api_key('TIDE'))"
            for override, expected in [(None, "fixture-file-key"), ("fixture-environment-key", "fixture-environment-key")]:
                with self.subTest(override=override):
                    child_environment = dict(environment)
                    if override:
                        child_environment["KHOA_API_KEY"] = override
                    result = subprocess.run([sys.executable, "-c", code, str(module_dir)], cwd=root,
                                            env=child_environment, capture_output=True, text=True, check=True)
                    self.assertEqual(result.stdout.strip(), expected)

    def request_xml(self, xml, url=services.OBS_URL):
        def provider(request):
            return httpx.Response(200, text=xml, headers={"content-type": "application/xml"})
        client = httpx.Client(transport=httpx.MockTransport(provider))
        with patch("services.httpx.Client", return_value=client):
            return services.get_json(url)

    def test_observations_request_one_minute_and_tides_omit_min(self):
        empty = {"header": {"resultCode": "00"}, "body": {"totalCount": 0}}
        with patch("services.api_key", return_value="test+key="), patch("services.get_json", return_value=empty) as fetch:
            services.khoa_items(services.OBS_URL, self.region, self.day, "OBSERVATION")
            params = fetch.call_args.args[1]
            self.assertEqual(params, {"serviceKey": "test+key=", "obsCode": "DT_0001",
                                     "reqDate": self.day.strftime("%Y%m%d"), "type": "json",
                                     "pageNo": 1, "numOfRows": 300, "min": 1})
            services.khoa_items(services.TIDE_URL, self.region, self.day, "TIDE")
            self.assertNotIn("min", fetch.call_args.args[1])

    def test_xml_observation_example_through_http_and_parser(self):
        # 가이드의 구조·필드명을 사용하고 날짜·지명만 테스트용으로 바꿉니다.
        xml = f"""<response><header><resultCode>00</resultCode></header><body><items><item>
        <obsvtrNm>인천</obsvtrNm><obsrvnDt>{self.day} 00:00</obsrvnDt>
        <wndrct>344.00</wndrct><wspd>5.0</wspd><maxMmntWspd>5.0</maxMmntWspd>
        <artmp>29.4</artmp><atmpr>999.4</atmpr><wtem>25.90</wtem>
        <bscTdlvHgt>233.00</bscTdlvHgt><slntQty>27.90</slntQty><crdir/><crsp/>
        </item></items><pageNo>1</pageNo><numOfRows>10</numOfRows><totalCount>1</totalCount>
        </body></response>"""
        data = self.request_xml(xml)
        rows, total = services.parse_khoa_page(data)
        self.assertEqual(total, 1)
        self.assertIsNone(rows[0]["crsp"])
        with patch("services.khoa_items", return_value=rows):
            result = services.fetch_observations(self.region, self.day)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.salinity_psu, 27.9)
        self.assertEqual(result.air_pressure_hpa, 999.4)
        self.assertEqual(result.wind_direction_deg, 344)
        self.assertEqual(result.max_gust_speed_ms, 5)
        self.assertEqual(result.observed_at.utcoffset().total_seconds(), 32400)

    def test_tide_minutes_and_all_extreme_codes(self):
        rows = [{"obsvtrNm": "인천", "predcDt": f"{self.day} {hour}:30",
                 "predcTdlvVl": "183.0", "extrSe": str(code)}
                for hour, code in [("02", 1), ("08", 2), ("14", 3), ("20", 4)]]
        with patch("services.khoa_items", return_value=rows):
            result = services.fetch_tides(self.region, self.day)
        self.assertEqual(result.status, "ok")
        self.assertEqual([e.kind for e in result.events], ["high", "low", "high", "low"])
        self.assertEqual(result.events[0].height_cm, 183)

    def test_xml_tide_example(self):
        xml = f"""<response><header><resultCode>00</resultCode></header><body><items><item>
        <obsvtrNm>인천</obsvtrNm><predcDt>{self.day} 00:47</predcDt>
        <predcTdlvVl>190.0</predcTdlvVl><extrSe>2</extrSe></item></items>
        <totalCount>1</totalCount></body></response>"""
        data = self.request_xml(xml, services.TIDE_URL)
        with patch("services.api_key", return_value="test"), patch("services.get_json", return_value=data):
            result = services.fetch_tides(self.region, self.day)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.events[0].kind, "low")

    def test_documented_error_codes_and_no_raw_message_leak(self):
        for code in ["1", "02", "4", "5", "10", "11", "12", "20", "21", "22", "30", "31", "32", "33", "40", "41", "99", "77"]:
            with self.subTest(code=code), self.assertRaises(HTTPException) as caught:
                services.parse_khoa_page({"header": {"resultCode": code, "resultMsg": "private-key"}})
            self.assertNotIn("private-key", caught.exception.detail)
            self.assertEqual(caught.exception.status_code, 429 if code == "22" else 504 if code == "5" else 502)
        for code in [3, "03"]:
            self.assertEqual(services.parse_khoa_page({"header": {"resultCode": code}}), ([], 0))
        for code in [0, "0", "00"]:
            self.assertEqual(services.parse_khoa_page({"header": {"resultCode": code}, "body": {"totalCount": 0}}), ([], 0))

    def test_xml_gateway_auth_error(self):
        data = self.request_xml("""<OpenAPI_ServiceResponse><cmmMsgHeader>
        <returnReasonCode>30</returnReasonCode><returnAuthMsg>private-key</returnAuthMsg>
        </cmmMsgHeader></OpenAPI_ServiceResponse>""")
        with patch("services.api_key", return_value="test"), patch("services.get_json", return_value=data):
            result = services.fetch_observations(self.region, self.day)
        self.assertEqual(result.status, "error")
        self.assertIn("등록되지 않은 인증키", result.note)
        self.assertNotIn("private-key", result.note)

    def test_missing_optional_observations_and_latest_row(self):
        rows = [{"obsvtrNm": "인천", "obsrvnDt": f"{self.day} 00:01", "wtem": "25.9"},
                {"obsvtrNm": "인천", "obsrvnDt": f"{self.day} 00:02", "wtem": "26.1", "slntQty": "", "wndrct": 0}]
        with patch("services.khoa_items", return_value=rows):
            result = services.fetch_observations(self.region, self.day)
        self.assertEqual(result.water_temperature_c, 26.1)
        self.assertIsNone(result.salinity_psu)
        self.assertIsNone(result.air_pressure_hpa)
        self.assertIsNone(result.max_gust_speed_ms)
        self.assertEqual(result.wind_direction_deg, 0)

    def test_invalid_response_does_not_become_success(self):
        for code in [None, "", "bad"]:
            with self.subTest(code=code), self.assertRaises(HTTPException):
                services.parse_khoa_page({"header": {"resultCode": code}, "body": {"totalCount": 0}})
        for text in ["<html>error</html>", "<response>", '<!DOCTYPE response [<!ENTITY x "test">]><response/>']:
            with self.subTest(text=text), self.assertRaises(HTTPException):
                self.request_xml(text)
        with self.assertRaises(HTTPException):
            self.request_xml("<response><header><resultCode>00</resultCode></header></response>", "https://example.test")


if __name__ == "__main__":
    unittest.main()
