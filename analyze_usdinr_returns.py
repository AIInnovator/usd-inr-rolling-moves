import argparse
import csv
import json
import math
import statistics
from datetime import date
from pathlib import Path
from typing import Any


TRADING_DAYS_PER_YEAR = 252
DEFAULT_INPUT_PATH = Path("usd_inr_daily.json")
DEFAULT_SUMMARY_PATH = Path("usd_inr_return_analysis.json")
DEFAULT_ROLLING_JSON_PATH = Path("usd_inr_rolling_returns.json")
DEFAULT_ROLLING_CSV_PATH = Path("usd_inr_rolling_returns.csv")
DEFAULT_PERIODS = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
    "2Y": 504,
    "3Y": 756,
    "5Y": 1260,
    "10Y": 2520,
}


def clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for row in rows:
        close = row.get("close")
        if close is None:
            continue
        cleaned.append({"date": str(row["date"]), "close": float(close)})
    return sorted(cleaned, key=lambda item: item["date"])


def load_rows(path: Path) -> list[dict[str, Any]]:
    return clean_rows(json.loads(path.read_text(encoding="utf-8")))


def round_metric(value: Any, digits: int = 10) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, digits)
    return value


def safe_mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def safe_median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def safe_stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def calendar_years(start_date: str, end_date: str) -> float:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = (end - start).days
    return days / 365.25 if days > 0 else 0.0


def calculate_daily_returns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    returns = []
    for previous, current in zip(rows, rows[1:]):
        returns.append(
            {
                "date": current["date"],
                "previous_date": previous["date"],
                "return": current["close"] / previous["close"] - 1,
            }
        )
    return returns


def calculate_daily_return_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 2:
        raise ValueError("At least two rows are required to calculate returns")

    daily_returns = calculate_daily_returns(rows)
    values = [item["return"] for item in daily_returns]
    total_return = rows[-1]["close"] / rows[0]["close"] - 1
    years = calendar_years(rows[0]["date"], rows[-1]["date"])
    cagr = (rows[-1]["close"] / rows[0]["close"]) ** (1 / years) - 1 if years > 0 else None
    daily_volatility = safe_stdev(values)
    annualized_volatility = daily_volatility * math.sqrt(TRADING_DAYS_PER_YEAR) if daily_volatility else None
    average_daily_return = safe_mean(values)
    annualized_average_daily_return = (
        (1 + average_daily_return) ** TRADING_DAYS_PER_YEAR - 1 if average_daily_return is not None else None
    )
    annualized_sharpe_zero_rf = (
        annualized_average_daily_return / annualized_volatility
        if annualized_average_daily_return is not None and annualized_volatility
        else None
    )
    best_day = max(daily_returns, key=lambda item: item["return"])
    worst_day = min(daily_returns, key=lambda item: item["return"])

    return {
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "start_close": round_metric(rows[0]["close"]),
        "end_close": round_metric(rows[-1]["close"]),
        "observations": len(rows),
        "daily_return_observations": len(values),
        "total_return": round_metric(total_return),
        "cagr": round_metric(cagr),
        "average_daily_return": round_metric(average_daily_return),
        "median_daily_return": round_metric(safe_median(values)),
        "annualized_average_daily_return": round_metric(annualized_average_daily_return),
        "daily_volatility": round_metric(daily_volatility),
        "annualized_volatility": round_metric(annualized_volatility),
        "annualized_sharpe_zero_rf": round_metric(annualized_sharpe_zero_rf),
        "positive_day_pct": round_metric(sum(1 for value in values if value > 0) / len(values)),
        "negative_day_pct": round_metric(sum(1 for value in values if value < 0) / len(values)),
        "flat_day_pct": round_metric(sum(1 for value in values if value == 0) / len(values)),
        "best_day": {
            "date": best_day["date"],
            "previous_date": best_day["previous_date"],
            "return": round_metric(best_day["return"]),
        },
        "worst_day": {
            "date": worst_day["date"],
            "previous_date": worst_day["previous_date"],
            "return": round_metric(worst_day["return"]),
        },
    }


def calculate_max_drawdown(rows: list[dict[str, Any]]) -> dict[str, Any]:
    peak = rows[0]
    worst = {
        "max_drawdown": 0.0,
        "peak_date": rows[0]["date"],
        "trough_date": rows[0]["date"],
        "recovery_date": rows[0]["date"],
        "days_to_trough": 0,
        "days_to_recovery": 0,
    }

    for index, row in enumerate(rows):
        if row["close"] > peak["close"]:
            peak = row

        drawdown = row["close"] / peak["close"] - 1
        if drawdown < worst["max_drawdown"]:
            recovery_date = None
            for recovery_row in rows[index + 1 :]:
                if recovery_row["close"] >= peak["close"]:
                    recovery_date = recovery_row["date"]
                    break

            worst = {
                "max_drawdown": drawdown,
                "peak_date": peak["date"],
                "trough_date": row["date"],
                "recovery_date": recovery_date,
                "days_to_trough": (date.fromisoformat(row["date"]) - date.fromisoformat(peak["date"])).days,
                "days_to_recovery": (
                    (date.fromisoformat(recovery_date) - date.fromisoformat(peak["date"])).days
                    if recovery_date
                    else None
                ),
            }

    return {key: round_metric(value) for key, value in worst.items()}


def annualize_return(period_return: float, trading_days: int) -> float:
    return (1 + period_return) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1


def calculate_rolling_return_summary(
    rows: list[dict[str, Any]], label: str, trading_days: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if trading_days <= 0:
        raise ValueError("trading_days must be positive")

    series = []
    for index in range(trading_days, len(rows)):
        start_row = rows[index - trading_days]
        end_row = rows[index]
        period_return = end_row["close"] / start_row["close"] - 1
        series.append(
            {
                "label": label,
                "trading_days": trading_days,
                "start_date": start_row["date"],
                "end_date": end_row["date"],
                "start_close": round_metric(start_row["close"]),
                "end_close": round_metric(end_row["close"]),
                "return": round_metric(period_return),
                "annualized_return": round_metric(annualize_return(period_return, trading_days)),
            }
        )

    if not series:
        return (
            {
                "label": label,
                "trading_days": trading_days,
                "observations": 0,
                "message": "Not enough rows for this period",
            },
            [],
        )

    values = [item["return"] for item in series]
    annualized_values = [item["annualized_return"] for item in series]
    best = max(series, key=lambda item: item["return"])
    worst = min(series, key=lambda item: item["return"])
    latest = series[-1]

    summary = {
        "label": label,
        "trading_days": trading_days,
        "observations": len(series),
        "average_return": round_metric(safe_mean(values)),
        "median_return": round_metric(safe_median(values)),
        "average_annualized_return": round_metric(safe_mean(annualized_values)),
        "median_annualized_return": round_metric(safe_median(annualized_values)),
        "std_dev": round_metric(safe_stdev(values)),
        "min_return": round_metric(min(values)),
        "percentile_5": round_metric(percentile(values, 0.05)),
        "percentile_25": round_metric(percentile(values, 0.25)),
        "percentile_75": round_metric(percentile(values, 0.75)),
        "percentile_95": round_metric(percentile(values, 0.95)),
        "max_return": round_metric(max(values)),
        "positive_period_pct": round_metric(sum(1 for value in values if value > 0) / len(values)),
        "negative_period_pct": round_metric(sum(1 for value in values if value < 0) / len(values)),
        "latest": latest,
        "best": best,
        "worst": worst,
    }
    return summary, series


def calculate_all_rolling_returns(
    rows: list[dict[str, Any]], periods: dict[str, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries = []
    all_series = []
    for label, trading_days in periods.items():
        summary, series = calculate_rolling_return_summary(rows, label, trading_days)
        summaries.append(summary)
        all_series.extend(series)
    return summaries, all_series


def calculate_report(rows: list[dict[str, Any]], periods: dict[str, int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = clean_rows(rows)
    rolling_summary, rolling_series = calculate_all_rolling_returns(rows, periods)
    report = {
        "metadata": {
            "asset": "USD/INR",
            "return_type": "simple close-to-close returns",
            "trading_days_per_year": TRADING_DAYS_PER_YEAR,
            "input_observations": len(rows),
        },
        "performance_summary": calculate_daily_return_stats(rows),
        "drawdown_summary": calculate_max_drawdown(rows),
        "rolling_return_summary": rolling_summary,
    }
    return report, rolling_series


def calculate_move_report(rows: list[dict[str, Any]], periods: dict[str, int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report, rolling_series = calculate_report(rows, periods)
    report["metadata"]["move_type"] = "simple close-to-close USD/INR move"
    report["metadata"].pop("return_type", None)
    return report, rolling_series


def parse_periods(values: list[str] | None) -> dict[str, int]:
    if not values:
        return DEFAULT_PERIODS

    periods = {}
    for value in values:
        label, days = value.split("=", 1)
        periods[label] = int(days)
    return periods


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_rolling_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "label",
        "trading_days",
        "start_date",
        "end_date",
        "start_close",
        "end_close",
        "return",
        "annualized_return",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze USD/INR daily history and rolling returns.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--rolling-json-out", type=Path, default=DEFAULT_ROLLING_JSON_PATH)
    parser.add_argument("--rolling-csv-out", type=Path, default=DEFAULT_ROLLING_CSV_PATH)
    parser.add_argument(
        "--period",
        action="append",
        help="Rolling window as LABEL=TRADING_DAYS. Can be repeated. Defaults: 1M,3M,6M,1Y,2Y,3Y,5Y,10Y.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = load_rows(args.input)
    periods = parse_periods(args.period)
    report, rolling_series = calculate_report(rows, periods)
    write_json(args.summary_out, report)
    write_json(args.rolling_json_out, rolling_series)
    write_rolling_csv(args.rolling_csv_out, rolling_series)
    print(f"Wrote summary report to {args.summary_out}")
    print(f"Wrote {len(rolling_series)} rolling return rows to {args.rolling_json_out} and {args.rolling_csv_out}")


if __name__ == "__main__":
    main()
