import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from analyze_usdinr_returns import DEFAULT_PERIODS, calculate_move_report, write_json, write_rolling_csv
from fetch_usdinr_history import fetch_history, write_outputs


DEFAULT_START_DATE = date(1980, 1, 1)
DEFAULT_SITE_DATA_DIR = Path("site/data")
SOURCE_NAME = "Investing.com financialdata historical API"


def build_manifest(rows: list[dict[str, Any]], generated_at: datetime | None = None) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot build manifest for empty rows")
    generated_at = generated_at or datetime.now(timezone.utc)
    return {
        "asset": "USD/INR",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "row_count": len(rows),
        "source": SOURCE_NAME,
        "status": "ok",
    }


def write_site_data(rows: list[dict[str, Any]], output_dir: Path, generated_at: datetime | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report, rolling_series = calculate_move_report(rows, DEFAULT_PERIODS)

    write_outputs(rows, output_dir / "usd_inr_daily.json", output_dir / "usd_inr_daily.csv")
    write_json(output_dir / "usd_inr_move_analysis.json", report)
    write_json(output_dir / "usd_inr_rolling_moves.json", rolling_series)
    write_rolling_csv(output_dir / "usd_inr_rolling_moves.csv", rolling_series)
    write_json(output_dir / "manifest.json", build_manifest(rows, generated_at))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch USD/INR history and write GitHub Pages data files.")
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SITE_DATA_DIR)
    parser.add_argument("--sleep", type=float, default=0.2)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = fetch_history(args.start_date, args.end_date, args.sleep)
    write_site_data(rows, args.output_dir)
    print(f"Wrote {len(rows)} USD/INR rows and analysis files to {args.output_dir}")


if __name__ == "__main__":
    main()
