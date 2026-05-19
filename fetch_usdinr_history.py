import argparse
import csv
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any


API_URL = "https://api.investing.com/api/financialdata/historical/160"
DEFAULT_START_DATE = date(2000, 3, 9)
DEFAULT_JSON_PATH = Path("usd_inr_daily.json")
DEFAULT_CSV_PATH = Path("usd_inr_daily.csv")
CSV_FIELDS = ["date", "open", "high", "low", "close", "change_percent", "volume"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.investing.com/",
    "domain-id": "www",
    "Origin": "https://www.investing.com",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def add_one_year(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, month=2, day=28)


def build_date_windows(start_date: date, end_date: date) -> list[tuple[date, date]]:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    windows = []
    current_start = start_date
    while current_start <= end_date:
        current_end = min(add_one_year(current_start) - timedelta(days=1), end_date)
        windows.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return windows


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(str(value).replace(",", ""))


def parse_volume(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


def normalize_rows(api_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_date: dict[str, dict[str, Any]] = {}

    for row in api_rows:
        timestamp = row.get("rowDateTimestamp")
        if not timestamp:
            continue
        trade_date = str(timestamp).split("T", 1)[0]
        rows_by_date[trade_date] = {
            "date": trade_date,
            "open": parse_float(row.get("last_openRaw", row.get("last_open"))),
            "high": parse_float(row.get("last_maxRaw", row.get("last_max"))),
            "low": parse_float(row.get("last_minRaw", row.get("last_min"))),
            "close": parse_float(row.get("last_closeRaw", row.get("last_close"))),
            "change_percent": parse_float(row.get("change_precentRaw", row.get("change_precent"))),
            "volume": parse_volume(row.get("volumeRaw", row.get("volume"))),
        }

    return [rows_by_date[key] for key in sorted(rows_by_date)]


def decode_response_body(raw_body: bytes, encoding: str | None) -> str:
    if encoding == "gzip":
        raw_body = gzip.decompress(raw_body)
    elif encoding == "deflate":
        raw_body = zlib.decompress(raw_body)
    return raw_body.decode("utf-8")


def fetch_window(start_date: date, end_date: date) -> list[dict[str, Any]]:
    params = {
        "start-date": start_date.isoformat(),
        "end-date": end_date.isoformat(),
        "time-frame": "Daily",
        "add-missing-rows": "false",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=HEADERS, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = decode_response_body(response.read(), response.headers.get("Content-Encoding"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {exc.code} for {start_date} to {end_date}: {error_body[:500]}") from exc

    payload = json.loads(body)
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError(f"Unexpected API response for {start_date} to {end_date}: missing data list")
    return data


def fetch_history(start_date: date, end_date: date, sleep_seconds: float = 0.2) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    windows = build_date_windows(start_date, end_date)
    for index, (window_start, window_end) in enumerate(windows, start=1):
        print(f"[{index}/{len(windows)}] Fetching {window_start} to {window_end}")
        all_rows.extend(fetch_window(window_start, window_end))
        if sleep_seconds > 0 and index < len(windows):
            time.sleep(sleep_seconds)

    return normalize_rows(all_rows)


def write_outputs(rows: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch daily USD/INR historical rates from Investing.com in one-year windows."
    )
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to wait between API requests. Use 0 to disable.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = fetch_history(args.start_date, args.end_date, args.sleep)
    write_outputs(rows, args.json_out, args.csv_out)
    print(f"Wrote {len(rows)} rows to {args.json_out} and {args.csv_out}")


if __name__ == "__main__":
    main()
