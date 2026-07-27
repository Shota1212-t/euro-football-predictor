"""Download the historical CSV files required by the prediction batch.

The files are downloaded only in the CI runner/local workspace. data/raw and the
combined data/processed/matches.csv remain excluded from Git.
"""
from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRST_DIR = ROOT / "data" / "raw" / "football_data_co_uk"
SECOND_DIR = ROOT / "data" / "raw" / "football_data_co_uk_second_division"
MATCHES_PATH = ROOT / "data" / "processed" / "matches.csv"

SEASONS = ("2324", "2425", "2526")
FIRST_DIVISIONS = ("E0", "SP1", "I1", "D1", "F1")
SECOND_DIVISIONS = ("E1", "SP2", "I2", "D2", "F2")
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
USER_AGENT = "EuroFootballPredictor/1.0"

REQUIRED_COLUMNS = (
    "Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
    "HS", "AS", "HST", "AST",
)


def download_csv(season: str, division: str, destination: Path) -> None:
    url = BASE_URL.format(season=season, division=division)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Failed to download {url}: {error}") from error

    if len(payload) < 100 or b"HomeTeam" not in payload[:3000]:
        raise RuntimeError(f"Downloaded CSV is invalid or empty: {url}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    print(f"downloaded: {destination.relative_to(ROOT)}")


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
            yield {column: row.get(column, "") for column in REQUIRED_COLUMNS}


def main() -> None:
    first_files: list[Path] = []
    second_files: list[Path] = []

    for season in SEASONS:
        for division in FIRST_DIVISIONS:
            path = FIRST_DIR / f"{division}_{season}.csv"
            download_csv(season, division, path)
            first_files.append(path)
        for division in SECOND_DIVISIONS:
            path = SECOND_DIR / f"{division}_{season}.csv"
            download_csv(season, division, path)
            second_files.append(path)

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


if __name__ == "__main__":
    main()
