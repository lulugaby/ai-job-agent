
import sqlite3
import json
from pathlib import Path

DATABASE = Path(__file__).resolve().parent / "data" / "jobs.db"


def connect_database():
    DATABASE.parent.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE)

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

    # Add columns to your existing Week 1 database
    existing = {
        row[1] for row in connection.execute(
            "PRAGMA table_info(jobs)"
        )
    }

    new_columns = {
        "match_score": "INTEGER",
        "strengths": "TEXT",
        "missing_skills": "TEXT",
        "ai_explanation": "TEXT"
    }

    for name, data_type in new_columns.items():
        if name not in existing:
            connection.execute(
                f"ALTER TABLE jobs ADD COLUMN {name} {data_type}"
            )

    connection.commit()
    return connection


def save_job(connection, job, match):
    source_id = (
        f"greenhouse:{job['company']}:{job['id']}"
    )

    connection.execute("""
        INSERT INTO jobs (
            source_id,
            company,
            title,
            location,
            description,
            url,
            match_score,
            strengths,
            missing_skills,
            ai_explanation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(source_id) DO UPDATE SET
            company = excluded.company,
            title = excluded.title,
            location = excluded.location,
            description = excluded.description,
            url = excluded.url,
            match_score = excluded.match_score,
            strengths = excluded.strengths,
            missing_skills = excluded.missing_skills,
            ai_explanation = excluded.ai_explanation
    """, (
        source_id,
        job["company"],
        job["title"],
        job["location"],
        job["description"],
        job["url"],
        int(match["score"]),
        json.dumps(match["strengths"]),
        json.dumps(match["missing_skills"]),
        match["explanation"]
    ))

    connection.commit()


def already_scored(connection, job):
    source_id = (
        f"greenhouse:{job['company']}:{job['id']}"
    )

    result = connection.execute("""
        SELECT match_score
        FROM jobs
        WHERE source_id = ?
    """, (source_id,)).fetchone()

    return result is not None and result[0] is not None
