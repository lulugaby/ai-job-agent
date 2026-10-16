
import sqlite3
from pathlib import Path

# Import functions from your other Python files
from job_collector import collect_jobs, relevant_jobs
from resume_parser import read_resume


# Companies to search
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


# STEP 1: Create the database
def create_database():

    Path("data").mkdir(exist_ok=True)

    connection = sqlite3.connect("data/jobs.db")

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

    return connection


# STEP 2: Save jobs into the database
def save_jobs(connection, jobs):

    for job in jobs:

        connection.execute("""
            INSERT OR REPLACE INTO jobs
            (source_id, company, title, location,
             description, url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"greenhouse:{job['company']}:{job['id']}",
            job["company"],
            job["title"],
            job["location"],
            job["description"],
            job["url"]
        ))

    connection.commit()


# STEP 3: Run the AI Job Search Agent
def main():

    print("Starting AI Job Search Agent...\n")

    # Read your resume
    resume_text = read_resume("private/resume.pdf")

    print("Resume loaded successfully!")
    print(f"Resume contains {len(resume_text)} characters.\n")

    # Connect to database
    connection = create_database()

    try:
        # Search each company's job board
        for board in BOARD_TOKENS:

            print(f"Searching {board}...")

            try:
                # Collect all published jobs
                jobs = collect_jobs(board)

                # Filter relevant jobs
                filtered_jobs = relevant_jobs(jobs)

                print(f"Found {len(jobs)} total jobs")
                print(f"Relevant jobs: {len(filtered_jobs)}")

                # Save jobs to database
                save_jobs(connection, filtered_jobs)

            except Exception as error:
                print(f"Error searching {board}: {error}")

        # Count saved jobs
        count = connection.execute(
            "SELECT COUNT(*) FROM jobs"
        ).fetchone()[0]

        print(f"\nTotal jobs in database: {count}")

        # Display saved jobs
        results = connection.execute("""
            SELECT company, title, location
            FROM jobs
            ORDER BY company, title
        """).fetchall()

        print("\n--- SAVED JOBS ---")

        for company, title, location in results:
            print(f"{company} | {title} | {location}")

    finally:
        connection.close()

    print("\nJob collection completed!")


if __name__ == "__main__":
    main()
