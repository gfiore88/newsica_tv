import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from newsica.generation.worker import HttpJobBackend


class TestGenerationWorkerHttpBackend(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "NEWSICA_REMOTE_GENERATION_URL": "https://vps.example.invalid",
            "NEWSICA_REMOTE_GENERATION_TOKEN": "token",
        },
        clear=False,
    )
    @patch("newsica.generation.worker.requests.post")
    def test_http_backend_claims_job_with_bearer_token(self, mock_post):
        response = MagicMock()
        response.json.return_value = {"status": "OK", "job": {"id": "job1"}}
        mock_post.return_value = response

        job = HttpJobBackend().claim_next_job("worker-a")

        self.assertEqual(job["id"], "job1")
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer token")
        self.assertEqual(mock_post.call_args.kwargs["json"]["worker_id"], "worker-a")

    @patch.dict(
        os.environ,
        {
            "NEWSICA_REMOTE_GENERATION_URL": "https://vps.example.invalid",
            "NEWSICA_REMOTE_GENERATION_TOKEN": "token",
        },
        clear=False,
    )
    @patch("newsica.generation.worker.requests.post")
    def test_http_backend_uploads_artifact_with_portable_manifest(self, mock_post):
        response = MagicMock()
        response.json.return_value = {"status": "OK", "artifact_manifest": {"ready_dir": "/ready/1000"}}
        mock_post.return_value = response

        path = Path("/tmp/newsica-test-audio.wav")
        path.write_bytes(b"audio")
        try:
            result = HttpJobBackend().upload_artifact(
                {"id": "job1"},
                "worker-a",
                {
                    "kind": "slot_audio",
                    "slot_time": "10:00",
                    "character": "news",
                    "title": "Morning News",
                    "audio_files": [str(path)],
                },
            )
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(result["artifact_manifest"]["ready_dir"], "/ready/1000")
        self.assertIn('"audio_files": ["newsica-test-audio.wav"]', mock_post.call_args.kwargs["data"]["manifest_json"])


if __name__ == "__main__":
    unittest.main()
