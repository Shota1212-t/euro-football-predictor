"""Download the historical CSV files required by the prediction batch.

The files are downloaded only in the CI runner/local workspace. data/raw and the
combined data/processed/matches.csv remain excluded from Git.
"""
from __future__ import annotations

import csv
import io
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
FIRST_DIR = ROOT / "data" / "raw" / "football_data_co_uk"
SECOND_DIR = ROOT / "data" / "raw" / "football_data_co_uk_second_division"
MATCHES_PATH = ROOT / "data" / "processed" / "matches.csv"

SEASONS = ("2324", "2425", "2526", "2627")
FIRST_DIVISIONS = ("E0", "SP1", "I1", "D1", "F1")
SECOND_DIVISIONS = ("E1", "SP2", "I2", "D2", "F2")
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"

REQUIRED_COLUMNS = (
    "Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
    "HS", "AS", "HST", "AST",
)


def download_csv(season: str, division: str, destination: Path) -> bool:
    """Download one CSV file.

    Returns True when a valid file was saved, False when the file was missing or
    could not be retrieved after retries. This avoids failing the whole workflow
    for transient remote errors like HTTP 503.
    """
    url = BASE_URL.format(season=season, division=division)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv,text/plain,*/*",
        "Referer": "https://www.football-data.co.uk/data.php",
    }

    max_attempts = 5

    payload = None
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            break

        except HTTPError as error:
            # 404 means the specific file doesn't exist — skip it rather than
            # failing the entire update. For other HTTP errors (e.g. 503), retry
            # and if still failing after attempts, skip the file.
            if error.code == 404:
                print(f"Not found (404), skipping: {url}")
                return False
            if attempt == max_attempts:
                print(f"HTTPError {error.code} downloading {url}: {error}. Giving up and skipping.")
                return False

            wait_seconds = 15 * attempt
            print(
                f"Download failed: {url}. HTTP {error.code}. Retrying in {wait_seconds} seconds ({attempt}/{max_attempts})"
            )
            time.sleep(wait_seconds)

        except (URLError, TimeoutError) as error:
            if attempt == max_attempts:
                print(f"Failed to download {url} after {max_attempts} attempts: {error}")
                return False

            wait_seconds = 15 * attempt

            print(
                f"Download failed: {url}. Retrying in {wait_seconds} seconds ({attempt}/{max_attempts})"
            )

            time.sleep(wait_seconds)

    if not payload:
        # No payload obtained after retries — skip this file rather than crash.
        print(f"No payload downloaded from {url}, skipping.")
        return False

    if len(payload) < 100 or b"HomeTeam" not in payload[:3000]:
        print(f"Downloaded CSV is invalid or empty: {url}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    print(f"downloaded: {destination.relative_to(ROOT)}")
    return True


def normalize_match_date(value: str, path: Path) -> str:
    text = (value or "").strip()
    for date_format in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    raise RuntimeError(f"Unsupported match date {text!r}: {path}")


def reduced_rows(path: Path):
    raw = path.read_bytes().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise RuntimeError(f"CSV has no header: {path}")
    missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
    if missing:
        raise RuntimeError(f"CSV is missing columns {sorted(missing)}: {path}")
    for row in reader:
        if row.get("Date") and row.get("HomeTeam") and row.get("AwayTeam") and row.get("FTR"):
            reduced = {column: row.get(column, "") for column in REQUIRED_COLUMNS}
            reduced["Date"] = normalize_match_date(row["Date"], path)
            yield reduced


def main() -> None:
    first_files: list[Path] = []
    second_files: list[Path] = []
    failures: list[str] = []

    for season in SEASONS:
        for division in FIRST_DIVISIONS:
            path = FIRST_DIR / f"{division}_{season}.csv"

            ok = download_csv(season, division, path)
            if ok:
                first_files.append(path)
            else:
                failures.append(str(path.relative_to(ROOT)))
        for division in SECOND_DIVISIONS:
            path = SECOND_DIR / f"{division}_{season}.csv"
            ok = download_csv(season, division, path)
            if ok:
                second_files.append(path)
            else:
                failures.append(str(path.relative_to(ROOT)))

    all_rows = []
    for path in first_files:
        all_rows.extend(reduced_rows(path))
    if not all_rows:
        raise RuntimeError("No first-division match rows were downloaded")

    MATCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = MATCHES_PATH.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    temporary.replace(MATCHES_PATH)

    print(f"first-division files: {len(first_files)}")
    print(f"second-division files: {len(second_files)}")
    print(f"combined first-division matches: {len(all_rows)}")
    print(f"saved: {MATCHES_PATH.relative_to(ROOT)}")
    if failures:
        print(f"Some CSV downloads were skipped or failed: {len(failures)} files: {failures}")


if __name__ == "__main__":
    main()
