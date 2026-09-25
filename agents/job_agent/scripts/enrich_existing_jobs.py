"""
Database Enrichment Script: Re-evaluates experience_min and experience_max
for all existing jobs in the database.
"""

import os
import sys

# Ensure agents package is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
job_agent_dir = os.path.dirname(current_dir)
agents_dir = os.path.dirname(job_agent_dir)
if agents_dir not in sys.path:
    sys.path.insert(0, agents_dir)

from job_agent.db import get_db
from job_agent.experience import classify_job_seniority, extract_experience_from_text


def enrich_database_jobs():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, title, company, experience_min, experience_max, description FROM jobs")
    jobs = cursor.fetchall()

    updated_count = 0
    stats = {"entry": 0, "growth": 0, "senior": 0}

    for j in jobs:
        jid, title, company, current_min, current_max, desc = j
        exp_min, exp_max = extract_experience_from_text(title, desc)

        # Fix Adzuna bug where company age (e.g. 30 years in business) was set as experience_min
        if current_min is not None and float(current_min) >= 20.0 and exp_min is None:
            current_min = None

        new_min = current_min if current_min is not None else exp_min
        new_max = current_max if current_max is not None else exp_max

        # Classify seniority
        job_dict = {
            "title": title,
            "description": desc,
            "experience_min": new_min,
            "experience_max": new_max,
        }
        seniority = classify_job_seniority(job_dict)
        stats[seniority] = stats.get(seniority, 0) + 1

        if new_min != current_min or new_max != current_max:
            cursor.execute(
                "UPDATE jobs SET experience_min=%s, experience_max=%s WHERE id=%s",
                (new_min, new_max, jid),
            )
            updated_count += 1

    db.commit()
    cursor.close()
    db.close()

    print(f"Total jobs audited: {len(jobs)}")
    print(f"Jobs with updated experience fields: {updated_count}")
    print(f"Seniority distribution -> Entry/Fresher: {stats['entry']}, Mid/Growth: {stats['growth']}, Senior: {stats['senior']}")


if __name__ == "__main__":
    enrich_database_jobs()
