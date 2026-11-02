
"""
Daily Greenhouse Job Database Refresh

Collects:
- Job ID
- Company
- Job title
- Location
- Description
- Application URL
- Original publication date
- Last updated date
- Last seen date

Preserves existing AI matching scores.

Run:
    python refresh_jobs.py
"""

import html
import sqlite3
import time

from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# =====================================================
# CONFIGURATION
# =====================================================

ROOT = Path(__file__).resolve().parent

DB_PATH = ROOT / "data" / "jobs.db"

API_ROOT = "https://boards-api.greenhouse.io/v1/boards"

BOARD_TOKENS = [
    "anthropic",
    "discord",
    "databricks",
    "stripe",
    "airbnb",
    "figma",
    "robinhood",
    "figureai",
    "sigmacomputing",
    "hackerrank",
    "instawork",
]


# =====================================================
# DATE FORMATTING
# =====================================================

def utc_iso(raw):
    """
    Convert an API timestamp into ISO-8601 UTC.
    Return None if the date is missing or invalid.
    """

    if not raw:
        return None

    try:
        value = datetime.fromisoformat(
            str(raw).replace("Z", "+00:00")
        )

        if value.tzinfo is None:
            return None

        return value.astimezone(
            timezone.utc
        ).isoformat()

    except (TypeError, ValueError):
        return None


# =====================================================
# CLEAN JOB DESCRIPTIONS
# =====================================================

def clean_description(raw):
    """
    Convert Greenhouse HTML into readable text.
    """

    decoded = html.unescape(
        html.unescape(raw or "")
    )

    return BeautifulSoup(
        decoded,
        "html.parser"
    ).get_text(" ", strip=True)


# =====================================================
# CREATE / UPDATE DATABASE STRUCTURE
# =====================================================

def prepare_database(connection):

    # Create the jobs table if it doesn't exist
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

    # Check existing columns
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
            + ", ".join(
                sorted(required - existing)
            )
        )

    # Add date columns without deleting existing data
    date_columns = [
        "first_published",
        "updated_at",
        "last_seen_at",
    ]

    for column in date_columns:

        if column not in existing:

            connection.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {column} TEXT
                """
            )

            print(f"Added database column: {column}")

    # Create posting date table for Streamlit
    connection.execute("""
        CREATE TABLE IF NOT EXISTS job_sources (
            source_id TEXT PRIMARY KEY,
            posted_at TEXT
        )
    """)

    source_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(job_sources)"
        )
    }

    if not {
        "source_id",
        "posted_at"
    }.issubset(source_columns):

        raise RuntimeError(
            "job_sources must contain "
            "source_id and posted_at."
        )

    connection.commit()


# =====================================================
# GET ORIGINAL POSTING DATE
# =====================================================

def get_first_published(session, board, raw_job):
    """
    Find the original publication timestamp.

    First try the jobs listing.
    If missing, retrieve the individual job.
    """

    first_published = utc_iso(
        raw_job.get("first_published")
        or raw_job.get("first_published_at")
    )

    if first_published:
        return first_published

    job_id = raw_job["id"]

    url = (
        f"{API_ROOT}/{board}/jobs/{job_id}"
    )

    try:

        # Small pause between detail requests
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
            f"Could not retrieve posting date "
            f"for job {job_id}: {error}"
        )

        return None


# =====================================================
# MAIN DATABASE REFRESH
# =====================================================

def main():

    # Ensure data folder exists
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Connect to SQLite
    connection = sqlite3.connect(DB_PATH)

    # Create HTTP session
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

        # Prepare database tables
        prepare_database(connection)

        # Loop through company boards
        for board in BOARD_TOKENS:

            print(
                f"\nCollecting jobs from {board}..."
            )

            try:

                response = session.get(
                    f"{API_ROOT}/{board}/jobs",
                    params={
                        "content": "true"
                    },
                    timeout=40
                )

                response.raise_for_status()

                jobs = response.json()["jobs"]

            except (
                requests.RequestException,
                ValueError,
                KeyError
            ) as error:

                print(
                    f"Board failed: {error}"
                )

                continue

            successful_boards += 1

            # Process each job
            for job in jobs:

                if job.get("id") is None:
                    continue

                # Existing ID format
                source_id = str(job["id"])

                # Preserve previously collected dates
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

                # Read publication date from listing
                first_published = (
                    utc_iso(
                        job.get("first_published")
                        or job.get("first_published_at")
                    )
                    or prior_date
                )

                # Request individual posting if necessary
                if not first_published:

                    first_published = (
                        get_first_published(
                            session,
                            board,
                            job
                        )
                    )

                # Read last modified timestamp
                updated_at = utc_iso(
                    job.get("updated_at")
                )

                # Job location
                location = (
                    (job.get("location") or {})
                    .get("name")
                    or ""
                )

                # Company name
                company = (
                    job.get("company_name")
                    or board.replace("-", " ").title()
                )

                # Insert or update job
                connection.execute(
                    """
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
                    """,
                    (
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
                        seen_at
                    )
                )

                # Save original posting date
                # for Streamlit filtering
                if first_published:

                    connection.execute(
                        """
                        INSERT INTO job_sources (
                            source_id,
                            posted_at
                        )

                        VALUES (?, ?)

                        ON CONFLICT(source_id)
                        DO UPDATE SET
                            posted_at = excluded.posted_at
                        """,
                        (
                            source_id,
                            first_published
                        )
                    )

                    dated += 1

                total += 1

            # Save changes after each company
            connection.commit()

            print(
                f"Saved {len(jobs)} jobs from {board}"
            )

        # Fail if every company request failed
        if successful_boards == 0:

            raise RuntimeError(
                "All Greenhouse boards failed."
            )

        # Print summary
        print("\n" + "=" * 45)

        print("DAILY JOB REFRESH COMPLETE")

        print(f"Jobs processed: {total}")

        print(
            f"Jobs with posting dates: {dated}"
        )

        print(
            f"Boards successfully reached: "
            f"{successful_boards}"
        )

        print(f"Database: {DB_PATH}")

        print("=" * 45)

    finally:

        session.close()

        connection.close()


# =====================================================
# RUN SCRIPT
# =====================================================

if __name__ == "__main__":
    main()
