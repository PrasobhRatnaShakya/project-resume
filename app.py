import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import streamlit as st
import pandas as pd
import requests # The library for making web requests

# Set the base URL for your FastAPI backend
API_URL = "http://127.0.0.1:8000"

# --- UI Views ---
def student_view():
    st.title("🎓 Student Job Portal")
    
    # Make a GET request to the /jobs/ endpoint
    try:
        response = requests.get(f"{API_URL}/jobs/")
        response.raise_for_status() # Raise an exception for bad status codes
        jobs = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to the backend server. Please ensure it is running. Error: {e}")
        return

    if not jobs:
        st.info("No jobs posted yet.")
        return

    # Application Section
    for job in jobs:
        with st.expander(f"**{job['title']}**"):
            st.markdown("##### Job Description")
            st.write(job['description'])
            st.markdown("---")
            student_name = st.text_input("Your Full Name", key=f"name_{job['id']}")
            student_email = st.text_input("Your Email ID", key=f"email_{job['id']}")
            uploaded_resume = st.file_uploader("Upload your resume:", type=['pdf', 'docx', 'txt'], key=f"resume_{job['id']}")
            
            if st.button("Submit Application", key=f"apply_{job['id']}"):
                if student_name and student_email and uploaded_resume:
                    with st.spinner("Analyzing and submitting..."):
                        # Prepare data for POST request
                        files = {'resume_file': (uploaded_resume.name, uploaded_resume.getvalue(), uploaded_resume.type)}
                        data = {'student_name': student_name, 'student_email': student_email}
                        
                        # Make the POST request to the /apply/{job_id} endpoint
                        apply_response = requests.post(f"{API_URL}/apply/{job['id']}", files=files, data=data)
                        
                        if apply_response.status_code == 200:
                            st.success("Application submitted successfully!")
                        else:
                            st.error(f"Error: {apply_response.json().get('detail', 'An unknown error occurred.')}")
                else:
                    st.warning("Please enter your name, email, and upload a resume.")

    # Status Check Section
    st.write("---")
    st.header("📋 Check Your Application Status")
    student_email_check = st.text_input("Enter your email ID to check applications:")
    if st.button("Check Status"):
        if student_email_check:
            try:
                # Make a GET request to the /student/applications/{email} endpoint
                status_response = requests.get(f"{API_URL}/student/applications/{student_email_check}")
                status_response.raise_for_status()
                student_apps = status_response.json()
                
                if not student_apps:
                    st.info("No applications found for that email address.")
                    return

                for row in student_apps:
                    with st.container(border=True):
                        st.subheader(row['title'])
                        cols = st.columns(3)
                        cols[0].metric("Your Final Score", f"{row['final_score']:.2f}%")
                        cols[1].metric("AI Verdict", row['verdict'])
                        
                        status = row['status']
                        if status == 'Shortlisted': cols[2].success(f"Status: {status} 🎉")
                        elif status == 'Not Shortlisted': cols[2].error(f"Status: {status}")
                        else: cols[2].info(f"Status: {status}")

                        with st.expander("💡 View Detailed Feedback"):
                            st.markdown(row['ai_feedback'])
            except requests.exceptions.RequestException:
                 st.error("Could not connect to the backend server.")
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
        else: st.session_state.password_correct = False

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
                # Make a POST request to the /jobs/new endpoint
                post_response = requests.post(f"{API_URL}/jobs/new", json={"title": job_title, "description": job_description})
                if post_response.status_code == 200:
                    st.success(f"Job '{job_title}' posted successfully!")
                    st.rerun()
                else:
                    st.error("Failed to post job.")
    
    st.write("---")
    st.header("Manage Jobs & View Applications")
    try:
        response = requests.get(f"{API_URL}/jobs/")
        response.raise_for_status()
        jobs = response.json()
    except requests.exceptions.RequestException:
        st.error("Could not fetch jobs from the server.")
        return

    if not jobs:
        st.info("No jobs have been posted.")
        return

    for job in jobs:
         with st.expander(f"**{job['title']}** - View & Manage"):
            if st.button("Delete This Job", key=f"delete_{job['id']}", type="primary"):
                # Make a DELETE request to the /jobs/{job_id} endpoint
                delete_response = requests.delete(f"{API_URL}/jobs/{job['id']}")
                if delete_response.status_code == 200:
                    st.success(f"Job '{job['title']}' deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete job.")

            # Get applications for this job
            apps_response = requests.get(f"{API_URL}/jobs/{job['id']}/applications")
            if apps_response.status_code == 200 and apps_response.json():
                applications = apps_response.json()
                for row in applications:
                    with st.container(border=True, key=f"cont_{row['id']}"):
                        # ... (Displaying candidate info, same as before)
                        cols = st.columns([3, 1, 1, 2])
                        cols[0].markdown(f"**{row['candidate_name']}**\n\n_{row['candidate_email']}_")
                        cols[1].text(f"{row['final_score']:.2f}%")
                        cols[2].text(row['verdict'])
                        status_options = ["Applied", "Shortlisted", "Not Shortlisted"]
                        current_status_index = status_options.index(row['status']) if row['status'] in status_options else 0
                        new_status = cols[3].selectbox("Set Status", options=status_options, index=current_status_index, key=f"status_{row['id']}", label_visibility="collapsed")
                        if new_status != row['status']:
                            # Make a PUT request to update status
                            update_response = requests.put(f"{API_URL}/applications/status", json={"application_id": row['id'], "new_status": new_status})
                            if update_response.status_code == 200:
                                st.rerun()
                            else:
                                st.error("Failed to update status.")
            else:
                st.info("No applications for this job yet.")

# --- Main App ---
st.set_page_config(layout="wide")
st.sidebar.title("👨‍💻 User Role")
user_role = st.sidebar.radio("Select role:", ["Student", "Placement Team"])

if user_role == "Student":
    student_view()
else:
    placement_team_view()