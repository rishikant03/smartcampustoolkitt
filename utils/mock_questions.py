import json
import random
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MOCK_QUESTION_BANK = {
    "Computer Science": [
        {
            "id": 1,
            "question": "Which data structure follows the Last-In, First-Out (LIFO) principle?",
            "options": ["Queue", "Stack", "Linked List", "Binary Tree"],
            "correct_answer": "Stack",
            "explanation": "A stack is a linear data structure that adheres to the LIFO principle where the last element inserted is the first one removed."
        },
        {
            "id": 2,
            "question": "What is the worst-case time complexity of standard QuickSort?",
            "options": ["O(n log n)", "O(n)", "O(n²)", "O(log n)"],
            "correct_answer": "O(n²)",
            "explanation": "QuickSort exhibits O(n²) worst-case time complexity when the pivot is consistently chosen as the smallest or largest element."
        },
        {
            "id": 3,
            "question": "Which of the following is NOT an ACID property in relational databases?",
            "options": ["Atomicity", "Consistency", "Integrity", "Durability"],
            "correct_answer": "Integrity",
            "explanation": "The ACID properties stand for Atomicity, Consistency, Isolation, and Durability."
        },
        {
            "id": 4,
            "question": "In Python, which built-in data type is mutable?",
            "options": ["Tuple", "String", "List", "Integer"],
            "correct_answer": "List",
            "explanation": "Lists in Python are mutable, meaning their contents can be modified in-place, whereas tuples, strings, and integers are immutable."
        },
        {
            "id": 5,
            "question": "What does HTTP status code 404 represent?",
            "options": ["Unauthorized", "Not Found", "Internal Server Error", "Bad Gateway"],
            "correct_answer": "Not Found",
            "explanation": "HTTP 404 Not Found indicates that the requested resource could not be found on the server."
        },
        {
            "id": 6,
            "question": "Which protocol is primarily used for securely transferring web pages over the internet?",
            "options": ["FTP", "SMTP", "HTTPS", "SNMP"],
            "correct_answer": "HTTPS",
            "explanation": "HTTPS (Hypertext Transfer Protocol Secure) encrypts HTTP traffic using Transport Layer Security (TLS)."
        },
        {
            "id": 7,
            "question": "What is the default port number for DNS queries?",
            "options": ["21", "25", "53", "80"],
            "correct_answer": "53",
            "explanation": "DNS (Domain Name System) typically operates on UDP port 53."
        },
        {
            "id": 8,
            "question": "Which memory type provides the fastest data access speed to the CPU?",
            "options": ["RAM", "SSD", "L1 Cache", "Hard Drive"],
            "correct_answer": "L1 Cache",
            "explanation": "L1 Cache is built directly inside the CPU processor core and provides the fastest access latency."
        }
    ],
    "General Science": [
        {
            "id": 1,
            "question": "What is the powerhouse of the cell?",
            "options": ["Nucleus", "Ribosome", "Mitochondria", "Endoplasmic Reticulum"],
            "correct_answer": "Mitochondria",
            "explanation": "Mitochondria generate most of the chemical energy needed to power the cell's biochemical reactions via ATP."
        },
        {
            "id": 2,
            "question": "What is the chemical symbol for Gold?",
            "options": ["Ag", "Au", "Fe", "Pb"],
            "correct_answer": "Au",
            "explanation": "The chemical symbol Au comes from the Latin word for gold, 'Aurum'."
        },
        {
            "id": 3,
            "question": "What is the acceleration due to gravity on Earth's surface approximately?",
            "options": ["7.8 m/s²", "9.8 m/s²", "11.2 m/s²", "15.0 m/s²"],
            "correct_answer": "9.8 m/s²",
            "explanation": "Standard acceleration due to Earth's gravity is approximately 9.80665 m/s²."
        },
        {
            "id": 4,
            "question": "Which gas is most abundant in Earth's atmosphere?",
            "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Argon"],
            "correct_answer": "Nitrogen",
            "explanation": "Nitrogen makes up approximately 78% of Earth's atmosphere by volume."
        },
        {
            "id": 5,
            "question": "What is the pH level of pure water at 25°C?",
            "options": ["5", "7", "9", "14"],
            "correct_answer": "7",
            "explanation": "Pure neutral water has a pH of exactly 7.0 at 25°C."
        },
        {
            "id": 6,
            "question": "Light year is a unit of measurement for:",
            "options": ["Time", "Distance", "Speed", "Intensity"],
            "correct_answer": "Distance",
            "explanation": "A light-year is the astronomical distance that light travels in a vacuum in one Julian year (approx. 9.46 trillion km)."
        }
    ],
    "Mathematics": [
        {
            "id": 1,
            "question": "What is the value of π (Pi) rounded to two decimal places?",
            "options": ["3.12", "3.14", "3.16", "3.18"],
            "correct_answer": "3.14",
            "explanation": "Pi is the ratio of a circle's circumference to its diameter, approximately 3.14159..."
        },
        {
            "id": 2,
            "question": "What is the derivative of sin(x) with respect to x?",
            "options": ["-cos(x)", "cos(x)", "tan(x)", "-sin(x)"],
            "correct_answer": "cos(x)",
            "explanation": "The derivative of sin(x) is cos(x)."
        },
        {
            "id": 3,
            "question": "If 2x + 5 = 15, what is the value of x?",
            "options": ["3", "5", "7", "10"],
            "correct_answer": "5",
            "explanation": "Subtracting 5 from both sides gives 2x = 10, so x = 5."
        },
        {
            "id": 4,
            "question": "What is the sum of angles in any Euclidean triangle?",
            "options": ["90°", "180°", "270°", "360°"],
            "correct_answer": "180°",
            "explanation": "The sum of interior angles of any triangle in planar geometry is always 180 degrees."
        },
        {
            "id": 5,
            "question": "What is the square root of 256?",
            "options": ["14", "15", "16", "18"],
            "correct_answer": "16",
            "explanation": "16 multiplied by 16 equals 256."
        }
    ],
    "English": [
        {
            "id": 1,
            "question": "Which of the following is an example of an oxymoron?",
            "options": ["As brave as a lion", "Deafening silence", "Time flies", "The wind whispered"],
            "correct_answer": "Deafening silence",
            "explanation": "An oxymoron combines two contradictory terms, like 'deafening' and 'silence'."
        },
        {
            "id": 2,
            "question": "Identify the conjunction in this sentence: 'She wanted to go, but it was raining.'",
            "options": ["She", "wanted", "but", "raining"],
            "correct_answer": "but",
            "explanation": "'But' is a coordinating conjunction connecting two independent clauses."
        },
        {
            "id": 3,
            "question": "What is the antonym of 'Benevolent'?",
            "options": ["Generous", "Malevolent", "Affectionate", "Sympathetic"],
            "correct_answer": "Malevolent",
            "explanation": "Benevolent means kind and well-meaning; malevolent means wishing to do evil to others."
        },
        {
            "id": 4,
            "question": "Choose the correctly spelled word:",
            "options": ["Accomodate", "Acommodate", "Accommodate", "Acomodate"],
            "correct_answer": "Accommodate",
            "explanation": "The correct spelling is 'Accommodate' with double 'c' and double 'm'."
        }
    ]
}

def get_mock_questions(subject: str = "Computer Science", count: int = 5, difficulty: str = "Medium") -> list[dict]:
    """
    Returns a curated set of questions for the mock test.
    Handles flexible argument ordering: (subject, count, difficulty) or (subject, difficulty, count).
    """
    if isinstance(count, str) and not count.isdigit():
        actual_difficulty = count
        actual_count = int(difficulty) if (isinstance(difficulty, int) or (isinstance(difficulty, str) and difficulty.isdigit())) else 5
        difficulty = actual_difficulty
        count = actual_count
    else:
        try:
            count = int(count)
        except Exception:
            count = 5

    bank = MOCK_QUESTION_BANK.get(subject)
    
    if bank and len(bank) >= count:
        sample = random.sample(bank, min(count, len(bank)))
        # Randomize options order
        results = []
        for idx, q in enumerate(sample, 1):
            opts = list(q["options"])
            random.shuffle(opts)
            results.append({
                "id": idx,
                "question": q["question"],
                "options": opts,
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
                "marks": 1
            })
        return results

    # If subject in bank but fewer questions or not in bank, try Gemini if key exists
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                f"Generate {count} multiple choice questions (MCQs) for subject '{subject}' at '{difficulty}' level.\n"
                f"Return ONLY valid JSON array of objects with keys: id (number), question (string), options (array of 4 strings), correct_answer (string), explanation (string).\n"
                f"No markdown formatting."
            )
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```"):
                clean_text = clean_text.split("\n", 1)[1]
            if clean_text.endswith("```"):
                clean_text = clean_text.rsplit("\n", 1)[0]
            questions = json.loads(clean_text)
            for idx, q in enumerate(questions, 1):
                q["id"] = idx
                q["marks"] = 1
            return questions
        except Exception as e:
            print(f"[Mock Generator] Gemini fallback: {e}")

    # Fallback to combined bank questions
    all_qs = []
    for s_qs in MOCK_QUESTION_BANK.values():
        all_qs.extend(s_qs)
    sample = random.sample(all_qs, min(count, len(all_qs)))
    results = []
    for idx, q in enumerate(sample, 1):
        opts = list(q["options"])
        random.shuffle(opts)
        results.append({
            "id": idx,
            "question": q["question"],
            "options": opts,
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "marks": 1
        })
    return results
