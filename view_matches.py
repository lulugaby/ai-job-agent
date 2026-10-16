
import sqlite3
import json
from pathlib import Path
from database import DATABASE
from datetime import datetime

# STEP 1: Connect to SQLite
connection = sqlite3.connect(DATABASE)

# STEP 2: Retrieve ALL scored jobs
jobs = connection.execute("""
    SELECT
        company,
        title,
        location,
        match_score,
        strengths,
        missing_skills,
        ai_explanation,
        url
    FROM jobs
    WHERE match_score IS NOT NULL
    ORDER BY match_score DESC, company, title
""").fetchall()

# STEP 3: Get all companies in the database
companies = connection.execute("""
    SELECT
        company,
        COUNT(*) AS total_jobs,
        SUM(
            CASE WHEN match_score IS NOT NULL
            THEN 1 ELSE 0 END
        ) AS scored_jobs
    FROM jobs
    GROUP BY company
    ORDER BY company
""").fetchall()

connection.close()

# STEP 4: Set the output location
output_path = Path("data/all_job_matches_oct1226.txt")
output_path.parent.mkdir(parents=True, exist_ok=True)

# STEP 5: Write the TXT report
with open(output_path, "w", encoding="utf-8") as file:

    file.write("=" * 70 + "\n")
    file.write("AI JOB SEARCH AGENT - ALL JOB MATCHES\n")
    file.write("=" * 70 + "\n")
    file.write(
        f"Report Generated: "
        f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
    )
    file.write(f"Total Companies: {len(companies)}\n")
    file.write(f"Total Scored Jobs: {len(jobs)}\n\n")

    # COMPANY SUMMARY
    file.write("=" * 70 + "\n")
    file.write("COMPANIES AVAILABLE IN DATABASE\n")
    file.write("=" * 70 + "\n\n")

    for index, (company, total, scored) in enumerate(
        companies, start=1
    ):
        file.write(
            f"{index}. {company} "
            f"| Total Jobs: {total} "
            f"| Scored Jobs: {scored}\n"
        )

    # ALL RANKED JOB MATCHES
    file.write("\n\n" + "=" * 70 + "\n")
    file.write("ALL JOB MATCHES - HIGHEST TO LOWEST\n")
    file.write("=" * 70 + "\n\n")

    for rank, job in enumerate(jobs, start=1):
        (
            company,
            title,
            location,
            score,
            strengths,
            missing_skills,
            explanation,
            url
        ) = job

        strengths_list = json.loads(strengths or "[]")
        missing_list = json.loads(missing_skills or "[]")

        file.write(f"#{rank} | MATCH SCORE: {score}%\n")
        file.write("-" * 70 + "\n")
        file.write(f"Job Title: {title}\n")
        file.write(f"Company: {company}\n")
        file.write(f"Location: {location}\n\n")

        file.write("Matching Skills:\n")
        for skill in strengths_list:
            file.write(f"  + {skill}\n")

        file.write("\nMissing Qualifications:\n")
        for skill in missing_list:
            file.write(f"  - {skill}\n")

        file.write(
            f"\nAI Explanation:\n"
            f"{explanation or 'Not available'}\n"
        )

        file.write(f"\nApplication Link: {url}\n")
        file.write("\n" + "=" * 70 + "\n\n")

    file.write(f"Total Results: {len(jobs)}\n")

# STEP 6: Confirm export
print("\nAI Job Report Exported Successfully!")
print(f"Companies found: {len(companies)}")
print(f"Scored jobs exported: {len(jobs)}")
print(f"File saved to: {output_path.resolve()}")
