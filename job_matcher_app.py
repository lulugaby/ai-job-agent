
import sqlite3
from pathlib import Path
import streamlit as st

# Use the same database as your matching application
DB_PATH = Path(__file__).resolve().parent / "data" / "jobs.db"


@st.cache_data(ttl=900)
def get_available_roles(database_modified_at):
    """Return job titles and their posting counts."""
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT
                TRIM(title) AS job_title,
                COUNT(*) AS job_count
            FROM jobs
            WHERE title IS NOT NULL
              AND TRIM(title) != ''
            GROUP BY LOWER(TRIM(title))
            ORDER BY job_count DESC, job_title
        """).fetchall()

    return dict(rows)


# ROLES THAT INTEREST YOU PAGE

st.subheader("Roles That Interest You")

st.write(
    "Choose the types of positions you're interested in. "
    "These options come directly from our job database."
)

if not DB_PATH.is_file():
    st.error("Job database not found.")
    st.stop()

# File modification time helps refresh the cached options
available_roles = get_available_roles(
    DB_PATH.stat().st_mtime_ns
)

if not available_roles:
    st.warning("No job titles are available yet.")
    st.stop()

selected_roles = st.multiselect(
    "Search and select job titles",
    options=list(available_roles.keys()),
    format_func=lambda role: (
        f"{role} ({available_roles[role]} jobs)"
    ),
    placeholder="Search for Data Engineer, Product Manager...",
    key="selected_job_roles"
)

if selected_roles:
    matching_job_count = sum(
        available_roles[role]
        for role in selected_roles
    )

    st.success(
        f"{len(selected_roles)} roles selected · "
        f"{matching_job_count} available job postings"
    )
