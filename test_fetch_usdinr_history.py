import csv
import json
import unittest
from datetime import date

from fetch_usdinr_history import build_date_windows, normalize_rows, write_outputs


class FetchUsdInrHistoryTests(unittest.TestCase):
    def test_build_date_windows_uses_one_year_windows_until_end_date(self):
        windows = build_date_windows(date(2020, 2, 29), date(2022, 3, 1))

        self.assertEqual(
            windows,
            [
                (date(2020, 2, 29), date(2021, 2, 27)),
                (date(2021, 2, 28), date(2022, 2, 27)),
                (date(2022, 2, 28), date(2022, 3, 1)),
            ],
        )

    def test_normalize_rows_deduplicates_and_sorts_oldest_first(self):
        api_rows = [
            {
                "rowDateTimestamp": "2026-05-19T00:00:00Z",
                "rowDate": "May 19, 2026",
                "last_close": "96.703",
                "last_open": "96.268",
                "last_max": "96.934",
                "last_min": "96.205",
                "change_precent": "0.37",
            },
            {
                "rowDateTimestamp": "2026-05-18T00:00:00Z",
                "rowDate": "May 18, 2026",
                "last_close": "96.350",
                "last_open": "96.170",
                "last_max": "96.393",
                "last_min": "96.120",
                "change_precent": "0.40",
            },
            {
                "rowDateTimestamp": "2026-05-19T00:00:00Z",
                "rowDate": "May 19, 2026",
                "last_close": "96.703",
                "last_open": "96.268",
                "last_max": "96.934",
                "last_min": "96.205",
                "change_precent": "0.37",
            },
        ]

        rows = normalize_rows(api_rows)

        self.assertEqual(
            rows,
            [
                {
                    "date": "2026-05-18",
                    "open": 96.17,
                    "high": 96.393,
                    "low": 96.12,
                    "close": 96.35,
                    "change_percent": 0.4,
                    "volume": None,
                },
                {
                    "date": "2026-05-19",
                    "open": 96.268,
                    "high": 96.934,
                    "low": 96.205,
                    "close": 96.703,
                    "change_percent": 0.37,
                    "volume": None,
                },
            ],
        )

    def test_write_outputs_creates_json_and_csv(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        rows = [
            {
                "date": "2026-05-18",
                "open": 96.17,
                "high": 96.393,
                "low": 96.12,
                "close": 96.35,
                "change_percent": 0.4,
                "volume": None,
            }
        ]

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            json_path = tmp_path / "usd_inr_daily.json"
            csv_path = tmp_path / "usd_inr_daily.csv"

            write_outputs(rows, json_path, csv_path)

            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), rows)
            with csv_path.open(newline="", encoding="utf-8") as handle:
                self.assertEqual(
                    list(csv.DictReader(handle)),
                    [
                        {
                            "date": "2026-05-18",
                            "open": "96.17",
                            "high": "96.393",
                            "low": "96.12",
                            "close": "96.35",
                            "change_percent": "0.4",
                            "volume": "",
                        }
                    ],
                )


if __name__ == "__main__":
    unittest.main()
