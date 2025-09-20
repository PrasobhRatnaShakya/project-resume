import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import streamlit as st
import pandas as pd
import re

# --- IMPORTANT: Import your refactored code ---
from core.database import init_db, add_job, get_all_jobs, add_application, get_applications_for_job, get_student_applications, shortlist_candidates, update_candidate_status, delete_job
from core.document_processor import read_pdf, read_docx, read_txt
from core.llm_analyzer import load_spacy_model, load_transformer_model, improved_extract_keywords, generate_ai_feedback_langchain, calculate_hybrid_score, extract_projects, map_projects_to_jd

# --- LangChain Imports and Configuration ---
from langchain_google_genai import ChatGoogleGenerativeAI
os.environ["LANGCHAIN_TRACING_V2"] = st.secrets.get("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_ENDPOINT"] = st.secrets.get("LANGCHAIN_ENDPOINT", "")
os.environ["LANGCHAIN_API_KEY"] = st.secrets.get("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = st.secrets.get("LANGCHAIN_PROJECT", "")

# --- Load Models ---
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=st.secrets["GOOGLE_API_KEY"],
                                 convert_system_message_to_human=True)
except Exception as e:
    st.error(f"Error configuring LangChain LLM: {e}")
    llm = None

# Load models separately to prevent conflicts
nlp = load_spacy_model()
semantic_model = load_transformer_model()
init_db()

# --- UI Views ---
def student_view():
    st.title("🎓 Student Job Portal")
    jobs_df = get_all_jobs()
    if jobs_df.empty:
        st.info("No jobs posted yet.")
        return

    # Application Section
    for index, job in jobs_df.iterrows():
        with st.expander(f"**{job['title']}**"):
            st.markdown("##### Job Description")
            st.write(job['description'])
            st.markdown("---")
            student_name = st.text_input("Your Full Name", key=f"name_{job['id']}")
            student_email = st.text_input("Your Email ID", key=f"email_{job['id']}")
            uploaded_resume = st.file_uploader("Upload your resume:", type=['pdf', 'docx', 'txt'], key=f"resume_{job['id']}")
            
            if st.button("Submit Application", key=f"apply_{job['id']}"):
                if student_name and student_email and uploaded_resume:
                    with st.spinner("Analyzing your resume... This may take a moment."):
                        resume_text = ""
                        if uploaded_resume.name.endswith('.pdf'): resume_text = read_pdf(uploaded_resume)
                        elif uploaded_resume.name.endswith('.docx'): resume_text = read_docx(uploaded_resume)
                        else: resume_text = read_txt(uploaded_resume)

                        jd_keywords = improved_extract_keywords(job['description'], nlp)
                        missing_keywords = [kw for kw in jd_keywords if kw not in resume_text.lower()]
                        raw_feedback = generate_ai_feedback_langchain(job['description'], resume_text, missing_keywords, llm)
                        
                        llm_score, verdict, ai_feedback_text = 0.0, "N/A", raw_feedback
                        verdict_match = re.search(r"\*\*Verdict:\*\*\s*(.*)", raw_feedback)
                        if verdict_match: verdict = verdict_match.group(1).strip()
                        score_match = re.search(r"\*\*Overall Score:\*\*\s*(\d{1,3})", raw_feedback)
                        if score_match: llm_score = float(score_match.group(1))
                        feedback_match = re.search(r"\*\*Actionable Feedback:\*\*(.*)", raw_feedback, re.DOTALL)
                        if feedback_match: ai_feedback_text = feedback_match.group(1).strip()
                        
                        jd_embedding = semantic_model.encode(job['description'], convert_to_tensor=True)
                        final_score, hard_score, soft_score = calculate_hybrid_score(jd_embedding, resume_text, jd_keywords, llm_score, semantic_model)
                        scores = {'final': final_score, 'semantic': soft_score, 'keyword': hard_score, 'llm': llm_score}
                        
                        projects = extract_projects(resume_text)
                        project_mappings = map_projects_to_jd(projects, jd_keywords)
                        
                        success = add_application(job['id'], student_name, student_email, scores, ai_feedback_text, verdict, projects, project_mappings, missing_keywords)
                        
                        if success:
                            st.success(f"Application submitted for {job['title']}!")
                        else:
                            st.error("Submission failed. You have already applied for this job with this email address.")
                else:
                    st.warning("Please enter your name, email, and upload a resume.")

    # Status Check Section
    st.write("---")
    st.header("📋 Check Your Application Status")
    student_email_check = st.text_input("Enter your email ID to check applications:")
    if st.button("Check Status"):
        if student_email_check:
            student_apps = get_student_applications(student_email_check)
            if not student_apps.empty:
                for _, row in student_apps.iterrows():
                    with st.container(border=True):
                        st.subheader(row['title'])
                        
                        cols = st.columns(3)
                        cols[0].metric("Your Final Score", f"{row['final_score']:.2f}%")
                        cols[1].metric("AI Verdict", row['verdict'])
                        
                        status = row['status']
                        if status == 'Shortlisted':
                            cols[2].success(f"Status: {status} 🎉")
                        elif status == 'Not Shortlisted':
                            cols[2].error(f"Status: {status}")
                        else:
                            cols[2].info(f"Status: {status}")

                        with st.expander("💡 View Detailed Feedback"):
                            st.markdown(row['ai_feedback'])
            else:
                st.info("No applications found for that email address.")
        else:
            st.warning("Please enter your email ID to check your application status.")

def placement_team_view():
    st.title("💼 Placement Team Dashboard")
    if 'password_correct' not in st.session_state:
        st.session_state.password_correct = False

    def check_password():
        if st.session_state["password"] == st.secrets["PLACEMENT_PASSWORD"]:
            st.session_state.password_correct = True
            del st.session_state["password"]
        else:
            st.session_state.password_correct = False

    if not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=check_password, key="password")
        if "password" in st.session_state and not st.session_state["password_correct"]:
                 st.error("Wrong password.")
        return
    
    with st.expander("Post a New Job", expanded=False):
        job_title = st.text_input("Job Title")
        job_description = st.text_area("Job Description", height=200)
        if st.button("Post Job"):
            if job_title and job_description:
                add_job(job_title, job_description)
                st.success(f"Job '{job_title}' posted successfully!")
                st.rerun()

    st.write("---")
    st.header("Manage Jobs & View Applications")
    jobs_df = get_all_jobs()
    if not jobs_df.empty:
        for _, job in jobs_df.iterrows():
             with st.expander(f"**{job['title']}** - View & Manage"):
                # Delete Job button
                if st.button("Delete This Job", key=f"delete_{job['id']}", type="primary"):
                    delete_job(job['id'])
                    st.success(f"Job '{job['title']}' and all its applications have been deleted.")
                    st.rerun()

                applications_df = get_applications_for_job(job['id'])
                if not applications_df.empty:
                    st.markdown("---")
                    
                    # Interactive list of candidates
                    for _, row in applications_df.iterrows():
                        with st.container(border=True, key=f"cont_{row['id']}"):
                            cols = st.columns([3, 1, 1, 2])
                            cols[0].markdown(f"**{row['candidate_name']}**\n\n_{row['candidate_email']}_")
                            cols[1].text(f"{row['final_score']:.2f}%")
                            cols[2].text(row['verdict'])
                            
                            status_options = ["Applied", "Shortlisted", "Not Shortlisted"]
                            current_status_index = status_options.index(row['status']) if row['status'] in status_options else 0
                            
                            new_status = cols[3].selectbox(
                                "Set Status",
                                options=status_options,
                                index=current_status_index,
                                key=f"status_{row['id']}",
                                label_visibility="collapsed"
                            )
                            
                            if new_status != row['status']:
                                update_candidate_status(row['id'], new_status)
                                st.rerun()

                    st.markdown("---")
                    st.subheader("Bulk Shortlisting Tool")
                    score_threshold = st.slider("Set shortlist score threshold:", 0, 100, 75, key=f"slider_{job['id']}")
                    if st.button("Apply Bulk Shortlist", key=f"bulk_{job['id']}"):
                        shortlist_candidates(job['id'], score_threshold)
                        st.success("Bulk shortlist has been applied to all 'Applied' candidates. Refreshing...")
                        st.rerun()
                else:
                    st.info("No applications have been submitted for this job yet.")
    else:
        st.info("No jobs have been posted. Please post a job to view applications.")

# --- Main App ---
st.set_page_config(layout="wide")
st.sidebar.title("👨‍💻 User Role")
user_role = st.sidebar.radio("Select role:", ["Student", "Placement Team"])

if user_role == "Student":
    student_view()
else:
    placement_team_view()

