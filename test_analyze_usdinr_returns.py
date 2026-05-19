import unittest

from analyze_usdinr_returns import (
    calculate_daily_return_stats,
    calculate_max_drawdown,
    calculate_rolling_return_summary,
)


class AnalyzeUsdInrReturnsTests(unittest.TestCase):
    def test_calculate_daily_return_stats_reports_compound_and_daily_metrics(self):
        rows = [
            {"date": "2024-01-01", "close": 100.0},
            {"date": "2024-01-02", "close": 110.0},
            {"date": "2024-01-03", "close": 99.0},
        ]

        stats = calculate_daily_return_stats(rows)

        self.assertEqual(stats["start_date"], "2024-01-01")
        self.assertEqual(stats["end_date"], "2024-01-03")
        self.assertAlmostEqual(stats["total_return"], -0.01)
        self.assertAlmostEqual(stats["average_daily_return"], 0.0)
        self.assertAlmostEqual(stats["median_daily_return"], 0.0)
        self.assertAlmostEqual(stats["positive_day_pct"], 0.5)
        self.assertAlmostEqual(stats["negative_day_pct"], 0.5)
        self.assertEqual(stats["best_day"]["date"], "2024-01-02")
        self.assertAlmostEqual(stats["best_day"]["return"], 0.1)
        self.assertEqual(stats["worst_day"]["date"], "2024-01-03")
        self.assertAlmostEqual(stats["worst_day"]["return"], -0.1)

    def test_calculate_max_drawdown_reports_peak_trough_and_recovery(self):
        rows = [
            {"date": "2024-01-01", "close": 100.0},
            {"date": "2024-01-02", "close": 120.0},
            {"date": "2024-01-03", "close": 90.0},
            {"date": "2024-01-04", "close": 110.0},
            {"date": "2024-01-05", "close": 125.0},
        ]

        drawdown = calculate_max_drawdown(rows)

        self.assertEqual(drawdown["peak_date"], "2024-01-02")
        self.assertEqual(drawdown["trough_date"], "2024-01-03")
        self.assertEqual(drawdown["recovery_date"], "2024-01-05")
        self.assertAlmostEqual(drawdown["max_drawdown"], -0.25)
        self.assertEqual(drawdown["days_to_trough"], 1)
        self.assertEqual(drawdown["days_to_recovery"], 3)

    def test_calculate_rolling_return_summary_reports_distribution_and_extremes(self):
        rows = [
            {"date": "2024-01-01", "close": 100.0},
            {"date": "2024-01-02", "close": 110.0},
            {"date": "2024-01-03", "close": 121.0},
            {"date": "2024-01-04", "close": 108.9},
        ]

        summary, series = calculate_rolling_return_summary(rows, "2D", 2)

        self.assertEqual(summary["label"], "2D")
        self.assertEqual(summary["trading_days"], 2)
        self.assertEqual(summary["observations"], 2)
        self.assertAlmostEqual(summary["average_return"], 0.1)
        self.assertAlmostEqual(summary["median_return"], 0.1)
        self.assertAlmostEqual(summary["min_return"], -0.01)
        self.assertAlmostEqual(summary["max_return"], 0.21)
        self.assertAlmostEqual(summary["positive_period_pct"], 0.5)
        self.assertEqual(summary["latest"]["end_date"], "2024-01-04")
        self.assertAlmostEqual(summary["latest"]["return"], -0.01)
        self.assertEqual(summary["best"]["start_date"], "2024-01-01")
        self.assertAlmostEqual(summary["best"]["return"], 0.21)
        self.assertEqual(summary["worst"]["start_date"], "2024-01-02")
        self.assertAlmostEqual(summary["worst"]["return"], -0.01)
        self.assertEqual(len(series), 2)


if __name__ == "__main__":
    unittest.main()
