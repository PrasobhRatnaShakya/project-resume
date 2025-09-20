import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import re
import io

# Import your existing logic from the 'core' folder
from core.database import init_db, add_job, get_all_jobs, add_application, get_applications_for_job, get_student_applications, shortlist_candidates, update_candidate_status, delete_job
from core.document_processor import read_pdf, read_docx, read_txt
from core.llm_analyzer import load_spacy_model, load_transformer_model, improved_extract_keywords, generate_ai_feedback_langchain, calculate_hybrid_score, extract_projects, map_projects_to_jd
from langchain_google_genai import ChatGoogleGenerativeAI
import streamlit as st # Used to access secrets

# --- Initialize App and Load Models ---
app = FastAPI(title="Resume Analyzer API")

nlp = load_spacy_model()
semantic_model = load_transformer_model()
try:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=st.secrets["GOOGLE_API_KEY"],
                                 convert_system_message_to_human=True)
except Exception as e:
    print(f"Error loading LLM: {e}")
    llm = None

# Initialize the database on startup
init_db()

# --- Pydantic Models for Request Bodies ---
class JobPost(BaseModel):
    title: str
    description: str

class StatusUpdate(BaseModel):
    application_id: int
    new_status: str

# --- API Endpoints ---

# For Students
@app.get("/jobs/")
def read_jobs():
    jobs_df = get_all_jobs()
    return jobs_df.to_dict('records')

@app.get("/student/applications/{email}")
def read_student_applications(email: str):
    apps_df = get_student_applications(email)
    return apps_df.to_dict('records')

@app.post("/apply/{job_id}")
async def apply_for_job(job_id: int, 
                        student_name: str = Form(...), 
                        student_email: str = Form(...), 
                        resume_file: UploadFile = File(...)):
    
    resume_contents = await resume_file.read()
    resume_text = ""
    # Use io.BytesIO to treat the byte string like a file
    if resume_file.filename.endswith('.pdf'): resume_text = read_pdf(io.BytesIO(resume_contents))
    elif resume_file.filename.endswith('.docx'): resume_text = read_docx(io.BytesIO(resume_contents))
    else: resume_text = read_txt(io.BytesIO(resume_contents))

    if "Error reading" in resume_text:
        raise HTTPException(status_code=400, detail="Could not read the uploaded resume file.")

    all_jobs_df = get_all_jobs()
    job_series = all_jobs_df[all_jobs_df['id'] == job_id]
    if job_series.empty:
        raise HTTPException(status_code=404, detail="Job not found.")
    job_description = job_series.iloc[0]['description']

    jd_keywords = improved_extract_keywords(job_description, nlp)
    missing_keywords = [kw for kw in jd_keywords if kw not in resume_text.lower()]
    raw_feedback = generate_ai_feedback_langchain(job_description, resume_text, missing_keywords, llm)
    
    llm_score, verdict, ai_feedback_text = 0.0, "N/A", raw_feedback
    verdict_match = re.search(r"\*\*Verdict:\*\*\s*(.*)", raw_feedback)
    if verdict_match: verdict = verdict_match.group(1).strip()
    score_match = re.search(r"\*\*Overall Score:\*\*\s*(\d{1,3})", raw_feedback)
    if score_match: llm_score = float(score_match.group(1))
    feedback_match = re.search(r"\*\*Actionable Feedback:\*\*(.*)", raw_feedback, re.DOTALL)
    if feedback_match: ai_feedback_text = feedback_match.group(1).strip()
    
    jd_embedding = semantic_model.encode(job_description, convert_to_tensor=True)
    final_score, hard_score, soft_score = calculate_hybrid_score(jd_embedding, resume_text, jd_keywords, llm_score, semantic_model)
    scores = {'final': final_score, 'semantic': soft_score, 'keyword': hard_score, 'llm': llm_score}
    
    projects = extract_projects(resume_text)
    project_mappings = map_projects_to_jd(projects, jd_keywords)
    
    success = add_application(job_id, student_name, student_email, scores, ai_feedback_text, verdict, projects, project_mappings, missing_keywords)
    
    if not success:
        raise HTTPException(status_code=409, detail="You have already applied for this job with this email address.")
        
    return {"message": "Application submitted successfully!", "score": final_score}

# For Placement Team
@app.post("/jobs/new")
def create_job(job: JobPost):
    add_job(job.title, job.description)
    return {"message": "Job created successfully"}

@app.delete("/jobs/{job_id}")
def remove_job(job_id: int):
    delete_job(job_id)
    return {"message": f"Job {job_id} deleted successfully"}

@app.get("/jobs/{job_id}/applications")
def read_job_applications(job_id: int):
    apps_df = get_applications_for_job(job_id)
    return apps_df.to_dict('records')
    
@app.post("/applications/shortlist/{job_id}")
def apply_bulk_shortlist(job_id: int, threshold: int = Form(...)):
    shortlist_candidates(job_id, threshold)
    return {"message": "Bulk shortlist applied successfully"}

@app.put("/applications/status")
def change_candidate_status(update: StatusUpdate):
    update_candidate_status(update.application_id, update.new_status)
    return {"message": "Status updated successfully"}