import PyPDF2
import docx

def read_pdf(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        return "".join([page.extract_text() for page in pdf_reader.pages])
    except Exception as e: return f"Error reading PDF: {e}"

def read_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e: return f"Error reading DOCX: {e}"

def read_txt(file):
    return file.read().decode('utf-8')