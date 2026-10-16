
import requests
from bs4 import BeautifulSoup

# STEP 1: Define the job titles we're interested in
TARGET_ROLES = [
    "data engineer",
    "analytics engineer",
    "business intelligence",
    "business systems analyst",
    "data analyst",
]


# STEP 2: Filter jobs based on their titles
def relevant_jobs(jobs):
    return [
        job for job in jobs
        if any(
            role in job["title"].lower()
            for role in TARGET_ROLES
        )
    ]


# STEP 3: Collect jobs from Greenhouse
def collect_jobs(board_token):
    url = (
        "https://boards-api.greenhouse.io/"
        f"v1/boards/{board_token}/jobs"
    )

    response = requests.get(
        url,
        params={"content": "true"},
        timeout=20
    )
    response.raise_for_status()

    jobs = []

    for job in response.json().get("jobs", []):
        description = BeautifulSoup(
            job.get("content") or "",
            "html.parser"
        ).get_text(" ", strip=True)

        jobs.append({
            "id": str(job["id"]),
            "company": board_token,
            "title": job["title"],
            "location": job.get(
                "location", {}
            ).get("name", ""),
            "description": description,
            "url": job["absolute_url"]
        })

    return jobs


# STEP 4: Run the job search automatically
if __name__ == "__main__":

    BOARD_TOKENS = [
        "cloudflare",
        # Add more company board tokens here
    ]

    all_jobs = []

    for board in BOARD_TOKENS:
        print(f"\nSearching {board}...")

        try:
            # Collect all jobs
            jobs = collect_jobs(board)

            # Filter for relevant positions
            filtered_jobs = relevant_jobs(jobs)

            all_jobs.extend(filtered_jobs)

            print(f"Total jobs: {len(jobs)}")
            print(f"Matching jobs: {len(filtered_jobs)}")

        except requests.RequestException as error:
            print(f"Error searching {board}: {error}")

    print(f"\nTotal relevant jobs: {len(all_jobs)}")

    for job in all_jobs:
        print(
            job["company"],
            "|",
            job["title"],
            "|",
            job["location"]
        )
