
from pathlib import Path
from database import connect_database
from job_collector import collect_jobs

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
    Path("data").mkdir(exist_ok=True)

    connection = connect_database()

    total_collected = 0
    total_updated = 0
    successful_boards = 0

    try:
        for board in BOARD_TOKENS:
            print(f"\nRefreshing {board}...")

            try:
                jobs = collect_jobs(board)
            except Exception as error:
                print(f"Collection failed for {board}: {error}")
                continue

            successful_boards += 1
            total_collected += len(jobs)

            for job in jobs:
                if not job.get("id"):
                    continue

                # Keep IDs consistent with the existing database
                source_id = str(
                    job.get("source_id") or job["id"]
                )

                connection.execute(
                    """
                    INSERT INTO jobs (
                        source_id,
                        company,
                        title,
                        location,
                        description,
                        url
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id)
                    DO UPDATE SET
                        company = excluded.company,
                        title = excluded.title,
                        location = excluded.location,
                        description = excluded.description,
                        url = excluded.url
                    """,
                    (
                        source_id,
                        job.get("company") or board,
                        job.get("title") or "",
                        job.get("location") or "",
                        job.get("description") or "",
                        job.get("url") or "",
                    ),
                )

                total_updated += 1

            connection.commit()
            print(f"Processed {len(jobs)} jobs from {board}")

        if successful_boards == 0:
            raise RuntimeError(
                "All Greenhouse board requests failed."
            )

        print("\nDATABASE REFRESH COMPLETE")
        print(f"Jobs collected: {total_collected}")
        print(f"Jobs inserted or updated: {total_updated}")
        print(f"Boards reached: {successful_boards}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
