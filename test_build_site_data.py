import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from build_site_data import build_manifest, write_site_data


class BuildSiteDataTests(unittest.TestCase):
    def test_build_manifest_reports_generated_data_contract(self):
        rows = [
            {"date": "1980-01-02", "close": 8.0},
            {"date": "2026-05-19", "close": 96.694},
        ]
        generated_at = datetime(2026, 5, 19, 12, 30, tzinfo=timezone.utc)

        manifest = build_manifest(rows, generated_at)

        self.assertEqual(
            manifest,
            {
                "asset": "USD/INR",
                "generated_at": "2026-05-19T12:30:00+00:00",
                "start_date": "1980-01-02",
                "end_date": "2026-05-19",
                "row_count": 2,
                "source": "Investing.com financialdata historical API",
                "status": "ok",
            },
        )

    def test_write_site_data_creates_pages_ready_files(self):
        rows = [
            {"date": "2024-01-01", "open": 80.0, "high": 80.0, "low": 80.0, "close": 80.0, "change_percent": 0.0, "volume": 0},
            {"date": "2024-01-02", "open": 81.0, "high": 81.0, "low": 81.0, "close": 81.0, "change_percent": 1.25, "volume": 0},
            {"date": "2024-01-03", "open": 82.0, "high": 82.0, "low": 82.0, "close": 82.0, "change_percent": 1.23, "volume": 0},
        ]

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_site_data(rows, output_dir, generated_at=datetime(2026, 5, 19, tzinfo=timezone.utc))

            expected_names = {
                "manifest.json",
                "usd_inr_daily.json",
                "usd_inr_daily.csv",
                "usd_inr_move_analysis.json",
                "usd_inr_rolling_moves.json",
                "usd_inr_rolling_moves.csv",
            }
            self.assertEqual({path.name for path in output_dir.iterdir()}, expected_names)

            report = json.loads((output_dir / "usd_inr_move_analysis.json").read_text(encoding="utf-8"))
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(report["metadata"]["move_type"], "simple close-to-close USD/INR move")
            self.assertEqual(report["metadata"]["input_observations"], 3)
            self.assertEqual(manifest["start_date"], "2024-01-01")
            self.assertEqual(manifest["end_date"], "2024-01-03")
            self.assertEqual(manifest["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
