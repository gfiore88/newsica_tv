import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from newsica.web.sources_routes import register_sources_routes


class TestSourcesRoutes(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        register_sources_routes(app)
        self.client = app.test_client()

    def test_registers_expected_sources_endpoints(self):
        rules = {rule.rule for rule in self.client.application.url_map.iter_rules()}
        self.assertIn("/api/sources", rules)
        self.assertIn("/api/sources/<feed_id>", rules)
        self.assertIn("/api/sources/<feed_id>/preview", rules)

    @patch("newsica.web.sources_routes.load_all_sources_detail", return_value=[{"id": "ansa_ultimora", "url": "https://example.com/feed.xml", "category": "breaking"}])
    def test_list_sources_endpoint(self, _mock_sources):
        response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["id"], "ansa_ultimora")

    @patch("newsica.web.sources_routes.add_source", return_value={"url": "https://example.com/feed.xml", "category": "news"})
    def test_add_source_endpoint(self, _mock_add):
        response = self.client.post(
            "/api/sources",
            json={"id": "corriere_news", "url": "https://example.com/feed.xml", "category": "news"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["source"]["id"], "corriere_news")

    @patch("newsica.web.sources_routes.remove_source", return_value=True)
    def test_delete_source_endpoint(self, _mock_remove):
        response = self.client.delete("/api/sources/ansa_ultimora")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["removed"], "ansa_ultimora")

    @patch("newsica.web.sources_routes.requests.get")
    @patch("newsica.web.sources_routes.feedparser.parse")
    @patch("newsica.web.sources_routes.load_all_sources_detail", return_value=[{"id": "ansa_ultimora", "url": "https://example.com/feed.xml", "category": "breaking"}])
    def test_preview_source_endpoint(self, _mock_sources, mock_parse, mock_get):
        mock_get.return_value = SimpleNamespace(content=b"<rss/>", raise_for_status=lambda: None)
        mock_parse.return_value = SimpleNamespace(
            feed=SimpleNamespace(title="Feed di test"),
            entries=[SimpleNamespace(title="Titolo", link="https://example.com/a", published="oggi", summary="summary")],
        )

        response = self.client.get("/api/sources/ansa_ultimora/preview")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["feed_title"], "Feed di test")
        self.assertEqual(len(payload["items"]), 1)


if __name__ == "__main__":
    unittest.main()
