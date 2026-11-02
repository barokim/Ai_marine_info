"""MBRIS 정상 XML과 잘못된 XML 처리 검증. 실제 인증키·외부 호출은 사용하지 않습니다."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import main
import services


class MbrisXmlTests(unittest.TestCase):
    def test_valid_xml_returns_species(self):
        xml = """<response><header><ResultCode>00</ResultCode></header>
        <body><items><item><SpcTxnId>270000024900</SpcTxnId>
        <CommKorNm>바지락</CommKorNm>
        <SpcScitfNmShort>Ruditapes philippinarum</SpcScitfNmShort>
        <ABST>테스트용 설명</ABST></item></items></body></response>"""
        response = httpx.Response(200, text=xml, request=httpx.Request("GET", services.MBRIS_URL))
        with patch.dict(os.environ, {"MBRIS_API_KEY": "test-key"}), patch("services.httpx.get", return_value=response):
            result = services.search_mbris("바지락")
        self.assertEqual(result, [{"mbris_id": "270000024900", "korean_name": "바지락",
                                   "scientific_name": "Ruditapes philippinarum", "description": "테스트용 설명"}])

    def test_malformed_xml_returns_readable_error(self):
        response = httpx.Response(200, text="<response>", request=httpx.Request("GET", services.MBRIS_URL))
        with patch.dict(os.environ, {"MBRIS_API_KEY": "test-key"}), patch("services.httpx.get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "XML 응답을 읽지 못했습니다"):
                services.search_mbris("바지락")


class MbrisRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "SEA_INFO_DB_PATH": str(Path(self.temporary.name) / "mbris.sqlite3"),
            "MBRIS_API_KEY": "test-key",
        })
        self.environment.start()
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.environment.stop()
        self.temporary.cleanup()

    def test_search_route_calls_mbris_and_preserves_identifiers_in_history(self):
        xml = """<response><header><ResultCode>00</ResultCode></header><body><items>
        <item><SpcTxnId>270000024900</SpcTxnId><CommKorNm>바지락</CommKorNm>
        <SpcScitfNmShort>Ruditapes philippinarum</SpcScitfNmShort></item>
        </items></body></response>"""
        external = httpx.Response(200, text=xml, request=httpx.Request("GET", services.MBRIS_URL))
        with patch("services.httpx.get", return_value=external) as request:
            response = self.client.get("/api/mbris/species", params={"q": "바지락"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.call_args.kwargs["params"]["CommKorNm"], "바지락")
        result = response.json()
        self.assertEqual(result["items"][0]["mbris_id"], "270000024900")
        self.assertNotIn("id", result["items"][0])
        detail = self.client.get(f"/api/history/{result['history_id']}").json()
        self.assertEqual(detail["query"]["provider"], "mbris")
        self.assertEqual(detail["result"]["items"], result["items"])
        self.assertNotIn("test-key", str(detail))

    def test_missing_key_is_reported_without_external_request(self):
        with patch.dict(os.environ, {"MBRIS_API_KEY": ""}), patch("services.httpx.get") as request:
            status = self.client.get("/api/status").json()
            response = self.client.get("/api/mbris/species", params={"q": "바지락"})
        self.assertFalse(status["mbris_configured"])
        self.assertEqual(response.status_code, 503)
        self.assertIn("MBRIS_API_KEY", response.json()["detail"])
        request.assert_not_called()

    def test_api_failure_is_saved_and_not_treated_as_empty_results(self):
        external = httpx.Response(200, text="<response>", request=httpx.Request("GET", services.MBRIS_URL))
        with patch("services.httpx.get", return_value=external):
            response = self.client.get("/api/mbris/species", params={"q": "바지락"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get("/api/history").json()[0]["status"], "error")

    def test_blank_query_and_valid_empty_response(self):
        with patch("services.httpx.get") as request:
            self.assertEqual(self.client.get("/api/mbris/species", params={"q": "  "}).status_code, 422)
            request.assert_not_called()
        external = httpx.Response(200, text="<response><header><ResultCode>00</ResultCode></header><body><items/></body></response>",
                                 request=httpx.Request("GET", services.MBRIS_URL))
        with patch("services.httpx.get", return_value=external):
            response = self.client.get("/api/mbris/species", params={"q": "미등록국명"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_one_character_auto_search_and_keyword_pagination(self):
        # 한 글자가 Query 검증을 통과하고, 기존 /api/species도 MBRIS를 호출해야 합니다.
        xml = """<response><header><ResultCode>00</ResultCode></header><body><items>
        <item><SpcTxnId>one</SpcTxnId><CommKorNm>참김</CommKorNm></item>
        <item><SpcTxnId>two</SpcTxnId><CommKorNm>갈래잎돌김</CommKorNm></item>
        </items><totalCount>45</totalCount></body></response>"""
        external = httpx.Response(200, text=xml, request=httpx.Request("GET", services.MBRIS_URL))
        with patch("services.httpx.get", return_value=external) as request, patch("species_service.search_species") as worms:
            response = self.client.get("/api/species", params={"q": "김", "page": 2})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual([item["korean_name"] for item in result["items"]], ["참김", "갈래잎돌김"])
        self.assertEqual(result["total_count"], 45)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["page_no"], 2)
        self.assertEqual(request.call_args.kwargs["params"]["CommKorNm"], "김")
        self.assertEqual(request.call_args.kwargs["params"]["pageNo"], 2)
        worms.assert_not_called()
        history = self.client.get(f"/api/history/{result['history_id']}").json()
        self.assertEqual(history["query"]["page"], 2)

    def test_direct_one_character_search_and_explicit_provider(self):
        xml = """<response><header><ResultCode>00</ResultCode></header><body>
        <items/><totalCount>0</totalCount></body></response>"""
        external = httpx.Response(200, text=xml, request=httpx.Request("GET", services.MBRIS_URL))
        with patch("services.httpx.get", return_value=external):
            response = self.client.get("/api/mbris/species", params={"q": "게"})
            forced = self.client.get("/api/species", params={"q": "Ruditapes", "provider": "mbris"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["has_more"])
        self.assertEqual(forced.status_code, 200)
        self.assertEqual(forced.json()["source_name"], "MBRIS · 국립해양생물자원관")
        self.assertEqual(self.client.get("/api/species", params={"q": "김", "page": 0}).status_code, 422)

    def test_auto_search_with_missing_mbris_key_does_not_fallback_to_worms(self):
        with patch.dict(os.environ, {"MBRIS_API_KEY": ""}), patch("species_service.search_species") as worms:
            response = self.client.get("/api/species", params={"q": "김"})
        self.assertEqual(response.status_code, 503)
        worms.assert_not_called()


if __name__ == "__main__":
    unittest.main()
