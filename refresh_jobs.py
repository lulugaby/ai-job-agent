
import sqlite3
import requests
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/greenhouse.db")

# Replace or expand with verified Greenhouse board tokens
COMPANIES = [
    "greenhouse",
]

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

conn.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    company TEXT NOT NULL,
    job_id TEXT NOT NULL,
    title TEXT,
    location TEXT,
    url TEXT,
    description TEXT,
    last_seen TEXT,
    PRIMARY KEY (company, job_id)
)
""")

now = datetime.now(timezone.utc).isoformat()

for company in COMPANIES:
    try:
        response = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs",
            params={"content": "true"},
            timeout=30
        )
        response.raise_for_status()

        jobs = response.json().get("jobs", [])

        for job in jobs:
            conn.execute("""
                INSERT INTO jobs
                (company, job_id, title, location,
                 url, description, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company, job_id)
                DO UPDATE SET
                    title = excluded.title,
                    location = excluded.location,
                    url = excluded.url,
                    description = excluded.description,
                    last_seen = excluded.last_seen
            """, (
                company,
                str(job["id"]),
                job.get("title"),
                job.get("location", {}).get("name"),
                job.get("absolute_url"),
                job.get("content"),
                now
            ))

        conn.commit()
        print(f"{company}: {len(jobs)} jobs collected")

    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"Failed to refresh {company}: {error}")

conn.close()
print("Database refresh complete")
