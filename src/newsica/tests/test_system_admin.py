import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsica.agents.system_admin import SystemAdminAgent


class TestSystemAdminAgent(unittest.TestCase):
    def test_reconcile_asset_slots_handles_missing_schedule_entry_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets_dir = Path(tmp) / "assets"
            (assets_dir / "ready").mkdir(parents=True, exist_ok=True)
            (assets_dir / "preparing").mkdir(parents=True, exist_ok=True)
            (assets_dir / "archive").mkdir(parents=True, exist_ok=True)

            row = {
                "slot_time": "09:00",
                "character": "flash_60s",
                "title": "Mondo in 60 Secondi",
                "status": "ready",
            }

            with patch("newsica.agents.system_admin.ASSETS_DIR", assets_dir), patch(
                "newsica.agents.system_admin.asset_slots_repository.list_slots",
                return_value=[row],
            ), patch(
                "newsica.agents.system_admin.asset_slots_repository.delete_slot"
            ) as mock_delete:
                agent = SystemAdminAgent()
                agent.reconcile_asset_slots({})

            mock_delete.assert_called_once_with("09:00", "flash_60s")


if __name__ == "__main__":
    unittest.main()
