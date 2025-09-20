import spacy
import re
from collections import Counter
from sentence_transformers import SentenceTransformer, util
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import streamlit as st

# --- Model Loading (Kept separated to prevent conflicts) ---
@st.cache_resource
def load_spacy_model():
    """Loads only the spaCy model."""
    print("Loading spaCy model...")
    return spacy.load("en_core_web_sm")

@st.cache_resource
def load_transformer_model():
    """Loads only the SentenceTransformer model."""
    print("Loading SentenceTransformer model...")
    return SentenceTransformer('all-MiniLM-L6-v2')

# --- Helper Functions ---
def improved_extract_keywords(text, nlp_model):
    custom_stop_words = ['experience', 'work', 'skill', 'skills', 'knowledge', 'plus', 'candidate', 'track', 'record', 'ideal', 'platform', 'platforms']
    doc = nlp_model(text.lower())
    keywords = [token.lemma_ for token in doc if (not token.is_stop and not token.is_punct and token.pos_ in ['PROPN', 'NOUN', 'ADJ'] and token.lemma_ not in custom_stop_words)]
    return [word for word, freq in Counter(keywords).most_common(15)]

@st.cache_data
def generate_ai_feedback_langchain(_jd_text, _resume_text, _missing_keywords, llm_model):
    if not llm_model: return "LLM not configured."
    prompt_template = """
    You are an expert career coach providing feedback on a resume for a specific job description.
    Your response MUST follow this structure EXACTLY, with each section header on a new line:

    **Verdict:** [A short, one-line verdict like "Excellent Match", "Good Fit", "Needs Improvement", or "Poor Match"]
    **Overall Score:** [A single integer score from 0 to 100 representing the resume's alignment with the job description]
    **Actionable Feedback:**
    * **Strengths:** [1-2 concise bullet points on what the resume does well in relation to the job.]
    * **Areas for Improvement:** [2-3 specific, actionable bullet points on how to better tailor the resume to this job. Suggest how to incorporate some of the missing keywords naturally.]

    Analyze the resume against the job description below. Be professional, constructive, and encouraging.
    **Job Description:** {jd}
    **Resume Text:** {resume}
    **Missing Keywords to consider:** {missing_keywords}
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    parser = StrOutputParser()
    chain = prompt | llm_model | parser
    try:
        return chain.invoke({"missing_keywords": ", ".join(_missing_keywords), "jd": _jd_text, "resume": _resume_text})
    except Exception as e:
        return f"Could not generate AI feedback: {e}"

def calculate_hybrid_score(jd_embedding, resume_text, jd_keywords, llm_score, semantic_model_instance):
    resume_lower = resume_text.lower()
    matched_keywords = [kw for kw in jd_keywords if kw in resume_lower]
    hard_score = (len(matched_keywords) / len(jd_keywords)) * 100 if jd_keywords else 0
    resume_embedding = semantic_model_instance.encode(resume_text, convert_to_tensor=True)
    soft_score = util.pytorch_cos_sim(jd_embedding, resume_embedding).item() * 100
    final_score = (0.3 * hard_score) + (0.5 * soft_score) + (0.2 * llm_score)
    return final_score, hard_score, soft_score

def extract_projects(resume_text):
    projects = []
    lines = resume_text.split("\n")
    capture = False
    for line in lines:
        if re.search(r"(projects|experience)", line.lower()):
            capture = True
            continue
        if capture:
            if line.strip() == "" or re.match(r"^\s*[A-Z ]{3,}$", line):
                capture = False
            else:
                projects.append(line.strip())
    return projects

def map_projects_to_jd(projects, jd_keywords):
    mappings = {}
    for project in projects:
        matched = [kw for kw in jd_keywords if kw.lower() in project.lower()]
        if matched:
            mappings[project] = matched
    return mappings