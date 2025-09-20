import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "placement_portal.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL,
            candidate_name TEXT NOT NULL,
            candidate_email TEXT NOT NULL,
            final_score REAL,
            semantic_score REAL,
            keyword_score REAL,
            llm_score REAL,
            ai_feedback TEXT,
            verdict TEXT, 
            status TEXT DEFAULT 'Applied',
            projects TEXT,
            project_mappings TEXT,
            missing_keywords TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE,
            UNIQUE(job_id, candidate_email)
        )
    """)
    conn.commit()
    conn.close()

def add_job(title, description):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jobs (timestamp, title, description) VALUES (?, ?, ?)",
                   (datetime.now(), title, description))
    conn.commit()
    conn.close()

def delete_job(job_id):
    """Deletes a job and all its associated applications from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

def get_all_jobs():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, title, description FROM jobs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def add_application(job_id, candidate_name, candidate_email, scores, feedback, verdict, projects, project_mappings, missing_keywords):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO applications (job_id, timestamp, candidate_name, candidate_email, final_score, semantic_score, keyword_score, llm_score, ai_feedback, verdict, projects, project_mappings, missing_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, datetime.now(), candidate_name, candidate_email, scores['final'], scores['semantic'], scores['keyword'], scores['llm'], feedback, verdict, str(projects), str(project_mappings), ", ".join(missing_keywords)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_applications_for_job(job_id):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT id, candidate_name, candidate_email, final_score, verdict, status, missing_keywords FROM applications WHERE job_id = ? ORDER BY final_score DESC",
        conn,
        params=(job_id,)
    )
    conn.close()
    return df

def get_student_applications(candidate_email):
    conn = sqlite3.connect(DB_FILE)
    query = """
    SELECT j.title, a.status, a.final_score, a.ai_feedback, a.verdict
    FROM applications a
    JOIN jobs j ON a.job_id = j.id
    WHERE a.candidate_email = ?
    ORDER BY a.timestamp DESC
    """
    df = pd.read_sql_query(query, conn, params=(candidate_email,))
    conn.close()
    return df

def shortlist_candidates(job_id, threshold):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = 'Shortlisted' WHERE job_id = ? AND final_score >= ? AND status = 'Applied'", (job_id, threshold))
    cursor.execute("UPDATE applications SET status = 'Not Shortlisted' WHERE job_id = ? AND final_score < ? AND status = 'Applied'", (job_id, threshold))
    conn.commit()
    conn.close()

def update_candidate_status(application_id, new_status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, application_id))
    conn.commit()
    conn.close()
