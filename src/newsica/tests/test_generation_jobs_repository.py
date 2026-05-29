import os
import tempfile
import unittest

from newsica.storage import database
from newsica.storage.repositories import generation_jobs_repository as repo


class TestGenerationJobsRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "newsica_test.db")
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_schema()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_enqueue_job_dedupes_active_job(self):
        first, created_first = repo.enqueue_job(
            "slot_audio",
            slot_time="10:00",
            character="news",
            title="Morning News",
            dedupe_key="slot_audio:1000:news:morning",
            payload={"hello": "world"},
        )
        second, created_second = repo.enqueue_job(
            "slot_audio",
            slot_time="10:00",
            character="news",
            title="Morning News",
            dedupe_key="slot_audio:1000:news:morning",
            payload={"hello": "world"},
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["payload"], {"hello": "world"})

    def test_claim_next_job_is_atomic_by_status(self):
        job, _ = repo.enqueue_job("ai_music", priority=10, payload={"theme": "rock"})

        claimed = repo.claim_next_job("worker-a")
        second_claim = repo.claim_next_job("worker-b")

        self.assertEqual(claimed["id"], job["id"])
        self.assertEqual(claimed["status"], "claimed")
        self.assertEqual(claimed["worker_id"], "worker-a")
        self.assertIsNone(second_claim)

    def test_owned_updates_require_same_worker(self):
        job, _ = repo.enqueue_job("ai_music")
        claimed = repo.claim_next_job("worker-a")

        repo.mark_running(claimed["id"], "worker-b")
        unchanged = repo.get_job(job["id"])
        self.assertEqual(unchanged["status"], "claimed")

        updated = repo.mark_running(claimed["id"], "worker-a")
        self.assertEqual(updated["status"], "running")

    def test_expire_stale_jobs_returns_running_job_to_pending(self):
        job, _ = repo.enqueue_job("ai_music")
        claimed = repo.claim_next_job("worker-a")
        repo.mark_running(claimed["id"], "worker-a")

        with database.get_connection() as conn:
            conn.execute(
                "UPDATE generation_jobs SET heartbeat_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
                (job["id"],),
            )
            conn.commit()

        result = repo.expire_stale_jobs(stale_seconds=60)
        recovered = repo.get_job(job["id"])

        self.assertEqual(result["reset"], 1)
        self.assertEqual(recovered["status"], "pending")
        self.assertIsNone(recovered["worker_id"])

    def test_get_summary_groups_statuses_and_workers(self):
        repo.enqueue_job("ai_music")
        repo.enqueue_job("slot_audio")
        claimed = repo.claim_next_job("worker-a")
        repo.mark_running(claimed["id"], "worker-a")

        summary = repo.get_summary()

        self.assertEqual(summary["counts"]["pending"], 1)
        self.assertEqual(summary["counts"]["running"], 1)
        self.assertEqual(summary["active_workers"][0]["worker_id"], "worker-a")


if __name__ == "__main__":
    unittest.main()
