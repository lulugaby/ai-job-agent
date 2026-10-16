
from resume_parser import read_resume
from job_collector import collect_jobs
from ai_matcher import match_resume_to_job

from database import (
    connect_database,
    save_job,
    already_scored
)

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


def main():
    # Read resume
    resume = read_resume("private/resume.pdf")
    print("Resume loaded successfully!")

    # Connect to SQLite
    connection = connect_database()

    collected = 0
    scored = 0
    skipped = 0

    try:
        for board in BOARD_TOKENS:
            print(f"\nSearching {board}...")

            try:
                jobs = collect_jobs(board)

            except Exception as error:
                print(f"Error collecting {board}: {error}")
                continue

            collected += len(jobs)

            for index, job in enumerate(jobs, start=1):
                print(
                    f"\n{board} — {index}/{len(jobs)}: "
                    f"{job['title']}"
                )

                # Skip jobs already in the database
                if already_scored(connection, job):
                    print("Already scored — skipping")
                    skipped += 1
                    continue

                if not job["description"].strip():
                    print("No description — skipping")
                    skipped += 1
                    continue

                try:
                    # Analyze job against resume
                    match = match_resume_to_job(
                        resume,
                        job["description"]
                    )

                    # Save results immediately
                    save_job(connection, job, match)

                    scored += 1
                    print(
                        f"Saved! Match score: "
                        f"{match['score']}%"
                    )

                except Exception as error:
                    print(f"Error analyzing: {error}")

    finally:
        connection.close()

    print("\n" + "=" * 40)
    print("JOB MATCHING COMPLETE")
    print(f"Jobs collected: {collected}")
    print(f"New jobs scored: {scored}")
    print(f"Jobs skipped: {skipped}")
    print("=" * 40)


if __name__ == "__main__":
    main()
