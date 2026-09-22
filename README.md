# AI Question Paper Generator

A complete, modern web application that allows users to upload a chapter or topic PDF, automatically extracts its text, and utilizes the OpenAI API to strictly generate professional question papers and answer keys based on the provided content.

## Features

- **PDF Upload**: Drag-and-drop interface with loading states.
- **Text Extraction**: Uses `PyMuPDF` to accurately extract selectable text from uploaded PDFs.
- **Customizable Exams**: Users can configure subject, chapter, difficulty, total marks, and the specific count of MCQs, short, and long questions.
- **AI-Powered Generation**: Leverages OpenAI API (gpt-4o-mini) with Structured Outputs to strictly adhere to the requested format and source content.
- **PDF Export**: Generates beautifully formatted Question Papers and Answer Keys for download using `ReportLab`.
- **Modern UI**: Sleek, responsive frontend built with custom CSS.

## Project Structure

```
question-paper-generator/
├── app.py                  # Main Flask application and SQLite database logic
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment variables
├── README.md               # Project documentation
│
├── uploads/                # Directory for temporary uploaded PDFs
├── generated/              # Directory for generated question paper PDFs
│
├── templates/              # HTML templates
│   ├── index.html          # Upload page
│   ├── settings.html       # Exam settings configuration
│   ├── preview.html        # Question paper HTML preview
│   └── answer_key.html     # Answer key HTML preview
│
├── static/
│   ├── css/style.css       # Custom styling (glassmorphism, typography)
│   └── js/script.js        # Drag-and-drop logic and AJAX form submissions
│
└── utils/                  # Core modules
    ├── pdf_extractor.py    # PyMuPDF logic for text extraction
    ├── ai_generator.py     # OpenAI API integration
    └── pdf_generator.py    # ReportLab PDF creation
```

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- An OpenAI API Key

### 2. Create a Virtual Environment
Open your terminal in the project directory and run:
```bash
python -m venv venv
```

Activate it:
- **Windows**: `.\venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
Copy `.env.example` to a new file named `.env` and add your OpenAI API key:
```env
OPENAI_API_KEY=your_actual_api_key_here
FLASK_SECRET_KEY=any_random_string_for_security
```

### 5. Run the Application
```bash
python app.py
```
Visit `http://localhost:5000` in your web browser.

## Error Handling Included
- **No Text in PDF**: Gracefully informs the user if a scanned (OCR-required) PDF is uploaded.
- **AI Failure**: Handles and displays OpenAI API timeouts or structural errors.
- **Security**: Uploaded files are checked for the `.pdf` extension, sized limited, and processed securely using `secure_filename`.

## Technology Stack
- **Frontend**: HTML5, CSS3 (Custom), Vanilla JavaScript
- **Backend**: Python, Flask, SQLite
- **PDF Handling**: PyMuPDF (`fitz`), ReportLab
- **AI Model**: OpenAI GPT-4o-mini (JSON Schema Mode)
