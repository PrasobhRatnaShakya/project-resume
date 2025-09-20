import psycopg2
import pandas as pd
from datetime import datetime
import streamlit as st

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Use SERIAL PRIMARY KEY for auto-incrementing in PostgreSQL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
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
    cursor.close()
    conn.close()

def add_job(title, description):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Use %s for placeholders in psycopg2
    cursor.execute("INSERT INTO jobs (timestamp, title, description) VALUES (%s, %s, %s)",
                   (datetime.now(), title, description))
    conn.commit()
    cursor.close()
    conn.close()

def delete_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_jobs():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, title, description FROM jobs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def add_application(job_id, candidate_name, candidate_email, scores, feedback, verdict, projects, project_mappings, missing_keywords):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO applications (job_id, timestamp, candidate_name, candidate_email, final_score, semantic_score, keyword_score, llm_score, ai_feedback, verdict, projects, project_mappings, missing_keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (job_id, datetime.now(), candidate_name, candidate_email, scores['final'], scores['semantic'], scores['keyword'], scores['llm'], feedback, verdict, str(projects), str(project_mappings), ", ".join(missing_keywords)))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback() # Rollback the transaction on error
        return False
    finally:
        cursor.close()
        conn.close()

def get_applications_for_job(job_id):
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT id, candidate_name, candidate_email, final_score, verdict, status, missing_keywords FROM applications WHERE job_id = %(job_id)s ORDER BY final_score DESC",
        conn,
        params={'job_id': job_id}
    )
    conn.close()
    return df

def get_student_applications(candidate_email):
    conn = get_db_connection()
    query = """
    SELECT j.title, a.status, a.final_score, a.ai_feedback, a.verdict
    FROM applications a
    JOIN jobs j ON a.job_id = j.id
    WHERE a.candidate_email = %(email)s
    ORDER BY a.timestamp DESC
    """
    df = pd.read_sql_query(query, conn, params={'email': candidate_email})
    conn.close()
    return df

def shortlist_candidates(job_id, threshold):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = 'Shortlisted' WHERE job_id = %s AND final_score >= %s AND status = 'Applied'", (job_id, threshold))
    cursor.execute("UPDATE applications SET status = 'Not Shortlisted' WHERE job_id = %s AND final_score < %s AND status = 'Applied'", (job_id, threshold))
    conn.commit()
    cursor.close()
    conn.close()

def update_candidate_status(application_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = %s WHERE id = %s", (new_status, application_id))
    conn.commit()
    cursor.close()
    conn.close()

