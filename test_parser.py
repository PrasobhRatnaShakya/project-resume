# Import the function you need from your other file
from core.document_processor import get_text_from_pdf

# --- IMPORTANT ---
# Change these paths to match the names of your two PDF files
PDF_FILE_1 = "data/resumes/Internship_Resume.pdf" 
PDF_FILE_2 = "data/resumes/Prasobh_Ratna_Shakya_Resume.pdf"

# --- Test the first PDF ---
print(f"--- Testing PDF File 1: {PDF_FILE_1} ---")
pdf_text_1 = get_text_from_pdf(PDF_FILE_1)
if pdf_text_1:
    # Print only the first 300 characters to keep the output clean
    print(pdf_text_1[:300])
else:
    print("Could not read the file. Check the path and filename.")

# --- Test the second PDF ---
print(f"\n--- Testing PDF File 2: {PDF_FILE_2} ---")
pdf_text_2 = get_text_from_pdf(PDF_FILE_2)
if pdf_text_2:
    print(pdf_text_2[:300])
else:
    print("Could not read the file. Check the path and filename.")