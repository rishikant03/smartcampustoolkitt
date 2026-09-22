import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

def generate_question_paper_pdf(data: dict, settings: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=10
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=12,
        spaceAfter=20
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )
    
    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=8,
        spaceAfter=4,
        alignment=TA_JUSTIFY
    )
    
    option_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        spaceAfter=2
    )

    story = []
    
    # Header
    story.append(Paragraph(settings.get('exam_name', 'QUESTION PAPER').upper(), title_style))
    story.append(Paragraph(f"Subject: {settings.get('subject')} | Chapter: {settings.get('chapter')}", header_style))
    story.append(Paragraph(f"Time: {settings.get('duration')} | Maximum Marks: {settings.get('total_marks')}", header_style))
    story.append(Spacer(1, 20))
    
    q_num = 1
    
    # MCQs
    if data.get('mcqs'):
        story.append(Paragraph("SECTION A — Multiple Choice Questions", section_style))
        for q in data['mcqs']:
            story.append(Paragraph(f"{q_num}. {q['question']} ({q['marks']} Marks)", question_style))
            labels = ['A', 'B', 'C', 'D']
            for idx, opt in enumerate(q.get('options', [])):
                label = labels[idx] if idx < len(labels) else '*'
                story.append(Paragraph(f"{label}. {opt}", option_style))
            q_num += 1
            story.append(Spacer(1, 5))
            
    # Short Questions
    if data.get('short_questions'):
        story.append(Paragraph("SECTION B — Short Answer Questions", section_style))
        for q in data['short_questions']:
            story.append(Paragraph(f"{q_num}. {q['question']} ({q['marks']} Marks)", question_style))
            q_num += 1
            story.append(Spacer(1, 25)) # space for writing
            
    # Long Questions
    if data.get('long_questions'):
        story.append(Paragraph("SECTION C — Long Answer Questions", section_style))
        for q in data['long_questions']:
            story.append(Paragraph(f"{q_num}. {q['question']} ({q['marks']} Marks)", question_style))
            q_num += 1
            story.append(Spacer(1, 40)) # space for writing

    doc.build(story)


def generate_answer_key_pdf(data: dict, settings: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=10
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )
    
    answer_style = ParagraphStyle(
        'AnswerStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=8,
        spaceAfter=8,
        alignment=TA_JUSTIFY
    )

    story = []
    
    # Header
    story.append(Paragraph(f"ANSWER KEY: {settings.get('exam_name', 'EXAM').upper()}", title_style))
    story.append(Spacer(1, 20))
    
    q_num = 1
    
    if data.get('mcqs'):
        story.append(Paragraph("SECTION A — MCQs", section_style))
        for q in data['mcqs']:
            story.append(Paragraph(f"<b>{q_num}.</b> {q['correct_answer']}", answer_style))
            q_num += 1
            
    if data.get('short_questions'):
        story.append(Paragraph("SECTION B — Short Answer Expected Points", section_style))
        for q in data['short_questions']:
            story.append(Paragraph(f"<b>{q_num}.</b> {q['expected_answer']}", answer_style))
            q_num += 1
            
    if data.get('long_questions'):
        story.append(Paragraph("SECTION C — Long Answer Key Points", section_style))
        for q in data['long_questions']:
            story.append(Paragraph(f"<b>{q_num}.</b> {q['expected_points']}", answer_style))
            q_num += 1

    doc.build(story)
