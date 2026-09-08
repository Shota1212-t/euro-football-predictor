"""Download historical match CSVs from a GitHub-hosted mirror.

GitHub Actionsからfootball-data.co.ukへ直接アクセスすると、
HTTP 503が継続するため、GitHub上の公開ミラーを使用する。

Downloaded raw files and generated matches.csv remain excluded from Git.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]

FIRST_DIR = ROOT / "data" / "raw" / "football_data_co_uk"
SECOND_DIR = (
    ROOT
    / "data"
    / "raw"
    / "football_data_co_uk_second_division"
)


MATCHES_PATH = ROOT / "data" / "processed" / "matches.csv"

SEASONS = ("2324", "2425", "2526")

LEAGUES = {
    "E0": "premier-league",
    "SP1": "la-liga",
    "I1": "serie-a",
    "D1": "bundesliga",
    "F1": "ligue-1",
}
SECOND_DIVISIONS = (
    "E1",
    "D2",
    "F2",
)

SECOND_BASE_URL = (
    "https://raw.githubusercontent.com/"
    "wlrwx/football-engine/main/data/historical/"
    "football_data/{division}_{season}.csv"
)

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "datasets/football-datasets/main/datasets/"
    "{league}/season-{season}.csv"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
)

SOURCE_REQUIRED_COLUMNS = (
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "HS",
    "AS",
    "HST",
    "AST",
)

OUTPUT_COLUMNS = (
    "Div",
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "HS",
    "AS",
    "HST",
    "AST",
)




def download_csv(
    season: str,
    division: str,
    league: str,
    destination: Path,
) -> bool:
    """Download one season CSV from the GitHub mirror."""

    url = BASE_URL.format(
        league=league,
        season=season,
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv,text/plain,*/*",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except HTTPError as error:
        print(
            f"HTTPError {error.code} downloading {url}: "
            f"{error}. Skipping."
        )
        return False
    except (URLError, TimeoutError) as error:
        print(f"Failed to download {url}: {error}. Skipping.")
        return False

    if len(payload) < 100 or b"HomeTeam" not in payload[:3000]:
        print(f"Downloaded CSV is invalid or empty: {url}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)

    print(f"Downloaded: {destination.relative_to(ROOT)}")
    return True

def download_second_division_csv(
    season: str,
    division: str,
    destination: Path,
) -> bool:
    """Download one second-division CSV from the GitHub mirror."""

    url = SECOND_BASE_URL.format(
        division=division,
        season=season,
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv,text/plain,*/*",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except HTTPError as error:
        print(
            f"HTTPError {error.code} downloading {url}: "
            f"{error}. Skipping."
        )
        return False
    except (URLError, TimeoutError) as error:
        print(f"Failed to download {url}: {error}. Skipping.")
        return False

    if len(payload) < 100 or b"HomeTeam" not in payload[:3000]:
        print(f"Downloaded second-division CSV is invalid: {url}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(".csv.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)

    print(f"Downloaded: {destination.relative_to(ROOT)}")
    return True

def normalize_match_date(value: str, path: Path) -> str:
    """Normalize known date formats to YYYY-MM-DD."""

    text = (value or "").strip()

    for date_format in (
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(
                text,
                date_format,
            ).date().isoformat()
        except ValueError:
            continue

    raise RuntimeError(
        f"Unsupported match date {text!r}: {path}"
    )


def reduced_rows(path: Path, division: str):
    """Read a mirror CSV and return only required model columns."""

    raw = path.read_bytes().decode(
        "utf-8-sig",
        errors="replace",
    )

    reader = csv.DictReader(io.StringIO(raw))

    if not reader.fieldnames:
        raise RuntimeError(f"CSV has no header: {path}")

    missing = (
        set(SOURCE_REQUIRED_COLUMNS)
        - set(reader.fieldnames)
    )

    if missing:
        raise RuntimeError(
            f"CSV is missing columns {sorted(missing)}: {path}"
        )

    for row in reader:
        if not (
            row.get("Date")
            and row.get("HomeTeam")
            and row.get("AwayTeam")
            and row.get("FTR")
        ):
            continue

        reduced = {
            column: row.get(column, "")
            for column in SOURCE_REQUIRED_COLUMNS
        }

        reduced["Div"] = division
        reduced["Date"] = normalize_match_date(
            row["Date"],
            path,
        )

        yield {
            column: reduced.get(column, "")
            for column in OUTPUT_COLUMNS
        }


def main() -> None:
    downloaded_files: list[tuple[Path, str]] = []
    failures: list[str] = []

    for season in SEASONS:
        for division, league in LEAGUES.items():
            path = FIRST_DIR / f"{division}_{season}.csv"

            success = download_csv(
                season=season,
                division=division,
                league=league,
                destination=path,
            )

            if success:
                downloaded_files.append((path, division))
            else:
                failures.append(f"{division}_{season}")
        second_division_files: list[Path] = []

    for season in SEASONS:
        for division in SECOND_DIVISIONS:
            path = SECOND_DIR / f"{division}_{season}.csv"

            success = download_second_division_csv(
                season=season,
                division=division,
                destination=path,
            )

            if success:
                second_division_files.append(path)
            else:
                failures.append(f"{division}_{season}")

    expected_second_division_files = (
        len(SEASONS) * len(SECOND_DIVISIONS)
    )

    if len(second_division_files) != expected_second_division_files:
        raise RuntimeError(
            "Second-division CSV download is incomplete: "
            f"expected={expected_second_division_files}, "
            f"actual={len(second_division_files)}"
        )           

    all_rows = []

    for path, division in downloaded_files:
        all_rows.extend(
            reduced_rows(
                path,
                division,
            )
        )

    if not all_rows:
        raise RuntimeError(
            "No first-division match rows were downloaded"
        )

    MATCHES_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = MATCHES_PATH.with_suffix(".csv.tmp")

    with temporary.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_COLUMNS,
        )
        writer.writeheader()
        writer.writerows(all_rows)

    temporary.replace(MATCHES_PATH)

    print(f"Downloaded files: {len(downloaded_files)}")
    print(f"Second-division files: {len(second_division_files)}")
    print(f"Combined matches: {len(all_rows)}")
    print(f"Saved: {MATCHES_PATH.relative_to(ROOT)}")

    if failures:
        print(
            f"Skipped files: {len(failures)} "
            f"{failures}"
        )


if __name__ == "__main__":
    main()
