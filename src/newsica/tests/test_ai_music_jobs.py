import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from newsica.audio.ai_music_jobs import (
    enqueue_job,
    get_next_pending_job,
    list_jobs,
    mark_done,
    mark_running,
)


class TestAiMusicJobs(unittest.TestCase):
    def test_enqueue_job_deduplicates_active_rotation_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs_file = Path(tmp) / "ai_music_jobs.json"

            first_job, first_created = enqueue_job(
                job_type="rotation_fill",
                source="director",
                dedupe_key="rotation_fill",
                path=jobs_file,
            )
            second_job, second_created = enqueue_job(
                job_type="rotation_fill",
                source="dashboard",
                dedupe_key="rotation_fill",
                path=jobs_file,
            )

            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(first_job["id"], second_job["id"])
            self.assertEqual(len(list_jobs(path=jobs_file)), 1)

    def test_completed_job_allows_next_rotation_fill_enqueue(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs_file = Path(tmp) / "ai_music_jobs.json"

            job, created = enqueue_job(
                job_type="rotation_fill",
                source="director",
                dedupe_key="rotation_fill",
                path=jobs_file,
            )
            self.assertTrue(created)

            mark_running(job["id"], path=jobs_file)
            mark_done(job["id"], audio_path="/tmp/track.wav", title="Track", path=jobs_file)

            next_job, next_created = enqueue_job(
                job_type="rotation_fill",
                source="director",
                dedupe_key="rotation_fill",
                path=jobs_file,
            )

            self.assertTrue(next_created)
            self.assertNotEqual(job["id"], next_job["id"])

    def test_get_next_pending_job_returns_oldest_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs_file = Path(tmp) / "ai_music_jobs.json"

            first_job, _ = enqueue_job(
                job_type="chat_request",
                source="chat",
                request_id="chatreq_1",
                dedupe_key="chatreq_1",
                path=jobs_file,
            )
            enqueue_job(
                job_type="chat_request",
                source="chat",
                request_id="chatreq_2",
                dedupe_key="chatreq_2",
                path=jobs_file,
            )

            pending = get_next_pending_job(path=jobs_file)

            self.assertIsNotNone(pending)
            self.assertEqual(first_job["id"], pending["id"])


if __name__ == "__main__":
    unittest.main()
