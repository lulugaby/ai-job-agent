
"""Daily Greenhouse collector that saves real publication timestamps.

Run locally: python refresh_jobs.py
The script can also be called by your existing GitHub Actions workflow.
It does not call OpenAI or change existing match-score columns.
"""

import html
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "jobs.db"

BOARD_TOKENS = [
    "anthropic", "discord", "databricks", "stripe", "airbnb",
    "figma", "robinhood", "figureai", "sigmacomputing",
    "hackerrank", "instawork",
]

API_ROOT = "https://boards-api.greenhouse.io/v1/boards"


def utc_iso(raw):
    """Normalize actual API dates to sortable ISO-8601 UTC strings."""
    if not raw:
        return None

    try:
        value = datetime.fromisoformat(
            str(raw).replace("Z", "+00:00")
        )

        if value.tzinfo is None:
            return None

        return value.astimezone(timezone.utc).isoformat()

    except (TypeError, ValueError):
        return None


def clean_description(raw):
    """Convert Greenhouse's escaped HTML to readable text."""
    decoded = html.unescape(html.unescape(raw or ""))

    return BeautifulSoup(
        decoded,
        "html.parser"
    ).get_text(" ", strip=True)


def prepare_database(connection):
    """
    Create or update the database schema without
    removing existing jobs or AI scores.
    """

    connection.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            source_id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            location TEXT,
            description TEXT,
            url TEXT
        )
    """)

    existing = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(jobs)"
        )
    }

    required = {
        "source_id",
        "company",
        "title",
        "location",
        "description",
        "url",
    }

    if not required.issubset(existing):
        raise RuntimeError(
            "The jobs table is missing columns: "
            + ", ".join(sorted(required - existing))
        )

    # Add publication and tracking dates
    for field in (
        "first_published",
        "updated_at",
        "last_seen_at",
    ):
        if field not in existing:
            connection.execute(
                f"ALTER TABLE jobs ADD COLUMN {field} TEXT"
            )

    # Supports the Rolematch 48-hour filter
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_sources (
            source_id TEXT PRIMARY KEY,
            posted_at TEXT
        )
    """)

    source_fields = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(job_sources)"
        )
    }

    if not {"source_id", "posted_at"}.issubset(source_fields):
        raise RuntimeError(
            "job_sources must have source_id and posted_at columns"
        )

    connection.commit()


def get_first_published(session, board, raw_job):
    """
    Retrieve the original posting date.

    Use the listing date when available.
    Otherwise request the individual Greenhouse job.
    """

    value = utc_iso(
        raw_job.get("first_published")
        or raw_job.get("first_published_at")
    )

    if value:
        return value

    job_id = raw_job["id"]

    url = f"{API_ROOT}/{board}/jobs/{job_id}"

    try:
        # Avoid sending large bursts of detail requests
        time.sleep(0.1)

        response = session.get(
            url,
            timeout=25
        )

        response.raise_for_status()

        details = response.json()

        return utc_iso(
            details.get("first_published")
            or details.get("first_published_at")
        )

    except (
        requests.RequestException,
        ValueError
    ) as error:
        print(
            f"Could not retrieve publication date "
            f"for {job_id}: {error}"
        )
        return None


def main():

    # Create the data directory
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Open SQLite database
    connection = sqlite3.connect(DB_PATH)

    # Set up HTTP connection
    session = requests.Session()

    session.headers.update({
        "User-Agent": "Rolematch-job-refresh/1.0"
    })

    total = 0
    dated = 0
    successful_boards = 0

    seen_at = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        prepare_database(connection)

        for board in BOARD_TOKENS:

            print(f"\nCollecting {board}...")

            try:
                response = session.get(
                    f"{API_ROOT}/{board}/jobs",
                    params={"content": "true"},
                    timeout=40,
                )

                response.raise_for_status()

                jobs = response.json()["jobs"]

            except (
                requests.RequestException,
                ValueError,
                KeyError
            ) as error:

                print(f"Board failed: {error}")
                continue

            successful_boards += 1

            for job in jobs:

                if job.get("id") is None:
                    continue

                # Keep the same ID convention
                source_id = str(job["id"])

                # Check whether we already know
                # the original publication date
                prior = connection.execute(
                    """
                    SELECT first_published
                    FROM jobs
                    WHERE source_id = ?
                    """,
                    (source_id,)
                ).fetchone()

                prior_date = (
                    prior[0] if prior else None
                )

                # Get original posting timestamp
                first_published = (
                    utc_iso(
                        job.get("first_published")
                        or job.get("first_published_at")
                    )
                    or prior_date
                )

                # Retrieve individual posting if needed
                if not first_published:
                    first_published = get_first_published(
                        session,
                        board,
                        job
                    )

                # Get last updated timestamp
                updated_at = utc_iso(
                    job.get("updated_at")
                )

                # Location
                location = (
                    (job.get("location") or {})
                    .get("name")
                    or ""
                )

                # Company
                company = (
                    job.get("company_name")
                    or board.replace("-", " ").title()
                )

                # Insert new job or update an existing job
                connection.execute("""
                    INSERT INTO jobs (
                        source_id,
                        company,
                        title,
                        location,
                        description,
                        url,
                        first_published,
                        updated_at,
                        last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                    ON CONFLICT(source_id)
                    DO UPDATE SET
                        company = excluded.company,
                        title = excluded.title,
                        location = excluded.location,
                        description = excluded.description,
                        url = excluded.url,

                        first_published = COALESCE(
                            excluded.first_published,
                            jobs.first_published
                        ),

                        updated_at = COALESCE(
                            excluded.updated_at,
                            jobs.updated_at
                        ),

                        last_seen_at = excluded.last_seen_at
                """, (
                    source_id,
                    company,
                    job.get("title") or "",
                    location,
                    clean_description(
                        job.get("content")
                    ),
                    job.get("absolute_url") or "",
                    first_published,
                    updated_at,
                    seen_at,
                ))

                # Store publication date for
                # the Streamlit 48-hour filter
                if first_published:

                    connection.execute("""
                        INSERT INTO job_sources (
                            source_id,
                            posted_at
                        )
                        VALUES (?, ?)

                        ON CONFLICT(source_id)
                        DO UPDATE SET
                            posted_at = excluded.posted_at
                    """, (
                        source_id,
                        first_published
                    ))

                    dated += 1

                total += 1

            # Save after each successful board
            connection.commit()

            print(
                f"Saved {len(jobs)} listings"
            )

        # Stop the workflow if every board failed
        if successful_boards == 0:
            raise RuntimeError(
                "All Greenhouse boards failed to refresh"
            )

        print("\n" + "=" * 45)
        print("GREENHOUSE REFRESH COMPLETE")
        print("=" * 45)

        print(f"Jobs processed: {total}")
        print(f"Jobs with publication dates: {dated}")
        print(f"Successful boards: {successful_boards}")
        print(f"Database: {DB_PATH}")

        print("=" * 45)

    finally:
        session.close()
        connection.close()


if __name__ == "__main__":
    main()
