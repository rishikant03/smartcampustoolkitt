import re
from pypdf import PdfReader

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a given PDF file using pypdf.
    Cleans up unnecessary whitespaces.
    Returns the extracted text.
    Raises ValueError if no selectable text is found.
    """
    text_content = []
    
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)
    except Exception as e:
        raise RuntimeError(f"Failed to read PDF file: {str(e)}")
        
    full_text = "\n".join(text_content)
    
    # Clean up whitespace
    full_text = re.sub(r'\n+', '\n', full_text)
    full_text = re.sub(r'[ \t]+', ' ', full_text)
    full_text = full_text.strip()
    
    if not full_text:
        raise ValueError("The uploaded PDF contains no selectable text. Please upload a text-based PDF (OCR is not supported).")
        
    return full_text
