import os
import json
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
except Exception:
    genai = None

def generate_questions(pdf_text: str, settings: dict) -> dict:
    """
    Calls Gemini API to generate questions based strictly on the pdf_text.
    Returns a dictionary matching the required question paper structure.
    """
    
    system_prompt = (
        "You are an expert examiner. Your task is to generate an exam paper strictly from the provided text.\n"
        "Do not invent facts. Generate unique questions covering different parts of the text.\n"
        "Distribute marks reasonably among questions so they sum up to the total marks if possible, or just assign appropriate marks per question."
    )
    
    user_prompt = (
        f"Subject: {settings.get('subject')}\n"
        f"Chapter: {settings.get('chapter')}\n"
        f"Difficulty: {settings.get('difficulty')}\n"
        f"Total MCQs: {settings.get('mcq_count')}\n"
        f"Total Short Questions: {settings.get('short_count')}\n"
        f"Total Long Questions: {settings.get('long_count')}\n"
        f"Generate the requested number of questions based on this text:\n\n{pdf_text[:100000]}" # Truncating to avoid passing gigantic files
    )

    schema = {
        "type": "object",
        "properties": {
            "mcqs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "correct_answer": {"type": "string"},
                        "marks": {"type": "number"}
                    },
                    "required": ["question", "options", "correct_answer", "marks"]
                }
            },
            "short_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "expected_answer": {"type": "string"},
                        "marks": {"type": "number"}
                    },
                    "required": ["question", "expected_answer", "marks"]
                }
            },
            "long_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "expected_points": {"type": "string"},
                        "marks": {"type": "number"}
                    },
                    "required": ["question", "expected_points", "marks"]
                }
            }
        },
        "required": ["mcqs", "short_questions", "long_questions"]
    }

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=system_prompt,
            generation_config={
                "temperature": 0.7,
                "response_mime_type": "application/json",
                "response_schema": schema
            }
        )
        
        response = model.generate_content(user_prompt)
        
        result_json = response.text
        return json.loads(result_json)
        
    except Exception as e:
        raise RuntimeError(f"Failed to generate questions using AI: {str(e)}")

def review_resume(resume_data: dict) -> dict:
    """
    Calls Gemini API to review a resume and provide feedback and an ATS score.
    """
    system_prompt = (
        "You are an expert ATS (Applicant Tracking System) and Career Coach. "
        "Analyze the provided resume data and provide constructive feedback to improve it. "
        "Also, calculate an ATS compatibility score out of 100 based on completeness, impact, and professional wording."
    )
    
    user_prompt = f"Please review this resume data:\n\n{json.dumps(resume_data, indent=2)}"

    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "feedback": {"type": "string", "description": "Markdown formatted feedback with suggestions on grammar, action verbs, missing skills, etc."}
        },
        "required": ["score", "feedback"]
    }

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=system_prompt,
            generation_config={
                "temperature": 0.7,
                "response_mime_type": "application/json",
                "response_schema": schema
            }
        )
        
        response = model.generate_content(user_prompt)
        return json.loads(response.text)
        
    except Exception as e:
        raise RuntimeError(f"Failed to review resume using AI: {str(e)}")
