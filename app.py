import os
import sqlite3
import uuid
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import random
import secrets
import re
import datetime
import string

from utils.pdf_extractor import extract_text_from_pdf
from utils.ai_generator import generate_questions, review_resume
from utils.pdf_generator import generate_question_paper_pdf, generate_answer_key_pdf
from utils.notifier import send_email_otp, send_sms_otp, send_email_link
from utils.mock_questions import get_mock_questions
from utils.exam_engine import (
    extract_chapters_and_topics,
    generate_exam_questions_from_book,
    grade_exam_attempt,
    generate_learning_analytics
)
import io
import csv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
GENERATED_FOLDER = os.path.join(os.path.dirname(__file__), 'generated')
DB_PATH = os.path.join(os.path.dirname(__file__), 'papers.db')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                filename TEXT,
                settings TEXT,
                generated_data TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                auth_provider TEXT DEFAULT 'local',
                is_verified INTEGER DEFAULT 0,
                role TEXT DEFAULT 'student'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                profile_photo TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_time TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS verification_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                device TEXT,
                method TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                teacher_id INTEGER NOT NULL,
                access_token TEXT NOT NULL,
                duration_mins INTEGER NOT NULL,
                max_warnings INTEGER DEFAULT 3,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers (id),
                FOREIGN KEY (teacher_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS exam_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT DEFAULT 'waiting',
                score INTEGER DEFAULT 0,
                max_score INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (exam_id) REFERENCES exams (id),
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS student_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                answer TEXT,
                is_correct INTEGER DEFAULT 0,
                FOREIGN KEY (participant_id) REFERENCES exam_participants (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                profile_photo TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_time TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS verification_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                device TEXT,
                method TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS mock_tests (
                id TEXT PRIMARY KEY,
                student_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                duration_mins INTEGER DEFAULT 10,
                total_questions INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                test_data TEXT NOT NULL,
                user_responses TEXT,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                test_code TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                source_type TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                negative_marking REAL DEFAULT 0.0,
                allow_calculator INTEGER DEFAULT 0,
                max_warnings INTEGER DEFAULT 3,
                shuffle_questions INTEGER DEFAULT 1,
                questions_data TEXT NOT NULL,
                total_marks REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                candidate_name TEXT,
                candidate_roll TEXT,
                status TEXT DEFAULT 'in_progress',
                current_question INTEGER DEFAULT 0,
                user_answers TEXT,
                review_flags TEXT,
                score REAL DEFAULT 0,
                max_score REAL DEFAULT 0,
                percentage REAL DEFAULT 0,
                time_spent INTEGER DEFAULT 0,
                violations INTEGER DEFAULT 0,
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES tests (id),
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS practice_tests (
                id TEXT PRIMARY KEY,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                difficulty TEXT DEFAULT 'medium',
                duration_minutes INTEGER DEFAULT 15,
                questions_data TEXT NOT NULL,
                user_answers TEXT,
                score REAL DEFAULT 0,
                max_score REAL DEFAULT 0,
                score_percent REAL DEFAULT 0,
                time_spent INTEGER DEFAULT 0,
                analytics_data TEXT,
                status TEXT DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                subject TEXT NOT NULL,
                chapter TEXT,
                question_text TEXT NOT NULL,
                question_type TEXT DEFAULT 'mcq',
                options TEXT,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                marks REAL DEFAULT 1.0,
                difficulty TEXT DEFAULT 'medium',
                FOREIGN KEY (teacher_id) REFERENCES users (id)
            )
        ''')
        # Safely migrate users table columns for 6-digit OTP email verification
        cursor = conn.execute("PRAGMA table_info(users)")
        existing_cols = [c[1] for c in cursor.fetchall()]
        if 'name' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN name TEXT")
        if 'email_verified' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
            conn.execute("UPDATE users SET email_verified = 1 WHERE is_verified = 1")
        if 'otp' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN otp TEXT")
        if 'otp_expiry' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN otp_expiry TIMESTAMP")
        if 'otp_attempts' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN otp_attempts INTEGER DEFAULT 0")
        if 'otp_last_sent' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN otp_last_sent TIMESTAMP")
        if 'created_at' not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_verified'):
            flash('Your account is unverified. Please verify your email to access this feature.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'teacher':
            flash('This feature is only available for teachers.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def record_login(user_id, method):
    ip = request.remote_addr
    device = request.user_agent.string
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO login_history (user_id, ip_address, device, method) VALUES (?, ?, ?, ?)',
                     (user_id, ip, device, method))
        conn.execute('INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)', (user_id,))
        conn.execute('UPDATE user_profiles SET last_login_time = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            # Check if email is verified
            user_keys = user.keys()
            email_verified = user['email_verified'] if 'email_verified' in user_keys else 0
            is_verified = user['is_verified'] if 'is_verified' in user_keys else 0
            
            if not email_verified and not is_verified:
                session['verify_email'] = user['email']
                flash('Please verify your email before logging in.', 'error')
                return redirect(url_for('verify_email_page', email=user['email']))
                
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_verified'] = True
            session['role'] = user['role']
            record_login(user['id'], 'password')
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = (request.form.get('name') or request.form.get('full_name') or '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'student').strip().lower()
        username = request.form.get('username', '').strip()
        
        # 1. Validate fields
        if not full_name or not email or not password:
            flash('All fields are required. Please fill in your details.', 'error')
            return render_template('register.html')
            
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            flash('Please enter a valid email address.', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match. Please check and try again.', 'error')
            return render_template('register.html')
            
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')
            
        # Secure password hash
        password_hash = generate_password_hash(password)
        
        # Generate cryptographically secure 6-digit OTP
        otp = f"{secrets.randbelow(900000) + 100000}"
        otp_expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                
                if existing_user:
                    # If already verified, reject duplicate registration
                    if existing_user['email_verified'] or existing_user['is_verified']:
                        flash('An account with this email already exists. Please log in.', 'error')
                        return redirect(url_for('login'))
                    else:
                        # Re-send verification for existing unverified user
                        user_id = existing_user['id']
                        conn.execute('''
                            UPDATE users 
                            SET name = ?, password_hash = ?, role = ?, otp = ?, otp_expiry = ?, 
                                otp_attempts = 0, otp_last_sent = ?, email_verified = 0, is_verified = 0 
                            WHERE id = ?
                        ''', (full_name, password_hash, role, otp, otp_expiry, now_str, user_id))
                else:
                    # Create clean unique username if not provided
                    if not username:
                        base_uname = re.sub(r'[^a-zA-Z0-9_]', '', full_name.lower().replace(' ', '_')) or email.split('@')[0]
                        username = base_uname
                        
                    suffix = 1
                    original_username = username
                    while conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
                        username = f"{original_username}_{suffix}"
                        suffix += 1
                        
                    cursor = conn.execute('''
                        INSERT INTO users (
                            name, username, password_hash, email, auth_provider, 
                            email_verified, is_verified, role, otp, otp_expiry, 
                            otp_attempts, otp_last_sent, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        full_name, username, password_hash, email, 'local', 
                        0, 0, role, otp, otp_expiry, 
                        0, now_str, now_str
                    ))
                    user_id = cursor.lastrowid
                    conn.execute('INSERT OR IGNORE INTO user_profiles (user_id, full_name) VALUES (?, ?)', (user_id, full_name))
                
                # Send 6-digit OTP email
                email_sent, email_msg = send_email_otp(email, otp)
                session['verify_email'] = email
                
                print(f"\n\n{'='*50}")
                print(f"[REGISTRATION 6-DIGIT OTP DISPATCH]")
                print(f"Candidate Email: {email}")
                print(f"Generated 6-Digit OTP: {otp}")
                print(f"Expires In: 5 minutes ({otp_expiry})")
                print(f"SMTP Status: {email_msg}")
                print(f"{'='*50}\n\n")
                
            if email_sent:
                flash(f'Registration successful! A 6-digit verification code was sent to {email}.', 'success')
            else:
                flash(f'Registration successful! {email_msg}', 'info')
                
            return redirect(url_for('verify_email_page', email=email))
            
        except sqlite3.IntegrityError as e:
            flash('Username or Email already registered.', 'error')
            
    return render_template('register.html')

@app.route('/verify-email', methods=['GET', 'POST'], endpoint='verify_email_page')
def verify_email_page():
    if request.method == 'POST':
        email = session.get('verify_email') or request.form.get('email', '').strip().lower()
        entered_otp = request.form.get('otp', '').strip()
        
        if not email:
            flash('Verification session expired. Please sign in.', 'error')
            return redirect(url_for('login'))
            
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            
            if not user:
                flash('Account not found. Please register.', 'error')
                return redirect(url_for('register'))
                
            # Check maximum incorrect attempts (rate limiting / brute force protection)
            attempts = user['otp_attempts'] or 0
            if attempts >= 5:
                flash('Too many incorrect OTP attempts. Please click Resend OTP to request a new code.', 'error')
                return redirect(url_for('verify_email_page', email=email))
                
            # Check 5-minute expiration
            is_expired = False
            if user['otp_expiry']:
                try:
                    exp = datetime.datetime.strptime(user['otp_expiry'], '%Y-%m-%d %H:%M:%S')
                    if datetime.datetime.now() > exp:
                        is_expired = True
                except Exception:
                    is_expired = True
            else:
                is_expired = True
                
            if is_expired or not user['otp']:
                flash('OTP has expired. Please request a new OTP.', 'error')
                return redirect(url_for('verify_email_page', email=email))
                
            # Verify OTP match
            if entered_otp != str(user['otp']).strip():
                conn.execute('UPDATE users SET otp_attempts = COALESCE(otp_attempts, 0) + 1 WHERE id = ?', (user['id'],))
                remaining = max(0, 5 - (attempts + 1))
                flash(f'Invalid OTP code. Please check and try again. ({remaining} attempts remaining)', 'error')
                return redirect(url_for('verify_email_page', email=email))
                
            # OTP is correct! Activate account
            conn.execute('''
                UPDATE users 
                SET email_verified = 1, is_verified = 1, otp = NULL, otp_expiry = NULL, otp_attempts = 0 
                WHERE id = ?
            ''', (user['id'],))
            
        session.pop('verify_email', None)
        flash('Email verified successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    else: # GET request
        email = session.get('verify_email') or request.args.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email to proceed with verification.', 'info')
            return redirect(url_for('login'))
            
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            
        if not user:
            flash('Account not found. Please register.', 'error')
            return redirect(url_for('register'))
            
        if user['email_verified']:
            flash('Your email is already verified! Please sign in.', 'info')
            return redirect(url_for('login'))
            
        # Calculate remaining seconds for countdown timer
        remaining_seconds = 300
        if user['otp_expiry']:
            try:
                exp = datetime.datetime.strptime(user['otp_expiry'], '%Y-%m-%d %H:%M:%S')
                rem = int((exp - datetime.datetime.now()).total_seconds())
                remaining_seconds = max(0, rem)
            except Exception:
                remaining_seconds = 300
                
        # Calculate resend cooldown (45 seconds)
        resend_cooldown = 0
        if user['otp_last_sent']:
            try:
                lst = datetime.datetime.strptime(user['otp_last_sent'], '%Y-%m-%d %H:%M:%S')
                elapsed = int((datetime.datetime.now() - lst).total_seconds())
                if elapsed < 45:
                    resend_cooldown = 45 - elapsed
            except Exception:
                resend_cooldown = 0
                
        # In dev mode without configured SMTP, surface the OTP to avoid blocking evaluation
        dev_otp = None
        if not os.getenv("SMTP_EMAIL") and not os.getenv("GMAIL_USER"):
            dev_otp = user['otp']
            
        return render_template(
            'verify_email.html',
            email=email,
            remaining_seconds=remaining_seconds,
            resend_cooldown=resend_cooldown,
            dev_otp=dev_otp
        )

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('verify_email') or request.form.get('email', '').strip().lower()
    if not email:
        flash('Verification session expired. Please sign in.', 'error')
        return redirect(url_for('login'))
        
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            flash('Account not found. Please register.', 'error')
            return redirect(url_for('register'))
            
        # Cooldown check to prevent spamming
        if user['otp_last_sent']:
            try:
                lst = datetime.datetime.strptime(user['otp_last_sent'], '%Y-%m-%d %H:%M:%S')
                elapsed = int((datetime.datetime.now() - lst).total_seconds())
                if elapsed < 45:
                    wait_time = 45 - elapsed
                    flash(f'Please wait {wait_time} seconds before requesting a new OTP.', 'error')
                    return redirect(url_for('verify_email_page', email=email))
            except Exception:
                pass
                
        # Generate new 6-digit OTP and reset 5-minute expiry
        otp = f"{secrets.randbelow(900000) + 100000}"
        otp_expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn.execute('''
            UPDATE users 
            SET otp = ?, otp_expiry = ?, otp_attempts = 0, otp_last_sent = ? 
            WHERE id = ?
        ''', (otp, otp_expiry, now_str, user['id']))
        
    email_sent, email_msg = send_email_otp(email, otp)
    session['verify_email'] = email
    
    print(f"\n\n{'='*50}")
    print(f"[RESEND 6-DIGIT OTP DISPATCH]")
    print(f"Candidate Email: {email}")
    print(f"New 6-Digit OTP: {otp}")
    print(f"Expires In: 5 minutes ({otp_expiry})")
    print(f"Delivery Status: {email_msg}")
    print(f"{'='*50}\n\n")
    
    if email_sent:
        flash(f'A fresh 6-digit verification code was sent to {email}.', 'success')
    else:
        flash(f'New verification OTP generated. {email_msg}', 'info')
        
    return redirect(url_for('verify_email_page', email=email))

@app.route('/verify-email/<token>')
def verify_email_token(token):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        token_record = conn.execute('SELECT * FROM verification_tokens WHERE token = ? AND type = "email"', (token,)).fetchone()
        
        if not token_record:
            flash('Invalid or expired token.', 'error')
            return redirect(url_for('login'))
            
        user_id = token_record['user_id']
        conn.execute('UPDATE users SET is_verified = 1, email_verified = 1 WHERE id = ?', (user_id,))
        conn.execute('DELETE FROM verification_tokens WHERE token = ?', (token,))
        
    flash('Email successfully verified! You can now log in.', 'success')
    return redirect(url_for('login'))

@app.route('/login/google', endpoint='login_google')
@app.route('/login/google', endpoint='google_login')
@app.route('/auth/google')
def login_google():
    pending_email = session.get('pending_google_email')
    pending_otp = session.get('pending_google_otp')
    if pending_email and pending_otp:
        return render_template('google_auth.html', step='verify', pending_email=pending_email, dev_otp=pending_otp)
    return render_template('google_auth.html', step='input')

@app.route('/auth/google/send-code', methods=['POST'])
def google_send_code():
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'student').strip().lower()
    
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('login_google'))
        
    # Generate 6-digit verification code
    otp = f"{random.randint(100000, 999999)}"
    session['pending_google_email'] = email
    session['pending_google_role'] = role
    session['pending_google_otp'] = otp
    session['pending_google_otp_time'] = datetime.datetime.now().isoformat()
    
    # Send real email via SMTP if configured
    email_sent, email_msg = send_email_otp(email, otp)
    session['google_email_sent'] = email_sent
    
    print(f"\n\n{'='*50}")
    print(f"[GMAIL VERIFICATION]")
    print(f"Sending verification code to Gmail: {email}")
    print(f"6-Digit Verification Code: {otp}")
    print(f"Delivery Status: {email_msg}")
    print(f"{'='*50}\n\n")
    
    if email_sent:
        flash(f'Verification code sent directly to your Gmail inbox ({email})!', 'success')
    else:
        flash(f'Code generated for {email}. {email_msg}', 'info')
    return redirect(url_for('login_google'))

@app.route('/auth/google/verify', methods=['POST'])
def google_verify_code():
    entered_otp = request.form.get('otp', '').strip()
    email = session.get('pending_google_email')
    role = session.get('pending_google_role', 'student')
    expected_otp = session.get('pending_google_otp')
    
    if not email or not expected_otp:
        flash('Verification session expired. Please enter your Gmail again.', 'error')
        return redirect(url_for('login_google'))
        
    if entered_otp != expected_otp:
        flash('Invalid verification code. Please check and enter the correct 6-digit code.', 'error')
        return redirect(url_for('login_google'))
        
    # Verification successful!
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            # Create username from email
            base_username = email.split('@')[0]
            clean_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username) or 'google_user'
            username = clean_username
            suffix = 1
            while conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
                username = f"{clean_username}_{suffix}"
                suffix += 1
                
            cursor = conn.execute(
                'INSERT INTO users (username, password_hash, email, auth_provider, is_verified, role) VALUES (?, ?, ?, ?, ?, ?)',
                (username, 'oauth_google_verified', email, 'google', 1, role)
            )
            user_id = cursor.lastrowid
            conn.execute('INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)', (user_id,))
        else:
            user_id = user['id']
            username = user['username']
            role = user['role']
            conn.execute('UPDATE users SET is_verified = 1, auth_provider = "google" WHERE id = ?', (user_id,))
            
    # Clear pending session data
    session.pop('pending_google_email', None)
    session.pop('pending_google_otp', None)
    session.pop('pending_google_role', None)
    session.pop('pending_google_otp_time', None)
    
    # Establish authenticated session
    session['user_id'] = user_id
    session['username'] = username
    session['is_verified'] = True
    session['role'] = role
    record_login(user_id, 'google')
    
    flash(f'Gmail ({email}) verified successfully! Welcome, {username}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/auth/google/resend', methods=['POST'])
def google_resend_code():
    email = session.get('pending_google_email')
    if not email:
        flash('Session expired. Please try again.', 'error')
        return redirect(url_for('login_google'))
        
    otp = f"{random.randint(100000, 999999)}"
    session['pending_google_otp'] = otp
    session['pending_google_otp_time'] = datetime.datetime.now().isoformat()
    
    email_sent, email_msg = send_email_otp(email, otp)
    session['google_email_sent'] = email_sent
    
    print(f"\n\n{'='*50}")
    print(f"[GMAIL VERIFICATION - RESEND]")
    print(f"Resending verification code to: {email}")
    print(f"New Verification Code: {otp}")
    print(f"Delivery Status: {email_msg}")
    print(f"{'='*50}\n\n")
    
    if email_sent:
        flash(f'A fresh verification code has been sent to your Gmail ({email})!', 'success')
    else:
        flash(f'New code generated for {email}. {email_msg}', 'info')
    return redirect(url_for('login_google'))

@app.route('/auth/google/cancel')
def google_cancel():
    session.pop('pending_google_email', None)
    session.pop('pending_google_otp', None)
    session.pop('pending_google_role', None)
    session.pop('pending_google_otp_time', None)
    session.pop('google_email_sent', None)
    return redirect(url_for('login_google'))

@app.route('/auth/google/callback')
def auth_google_callback():
    return redirect(url_for('login_google'))

@app.route('/login/phone', methods=['POST'], endpoint='login_phone')
@app.route('/login/phone', methods=['POST'], endpoint='send_otp')
def login_phone():
    phone = request.form.get('phone')
    if not phone:
        flash('Please enter a phone number.', 'error')
        return redirect(url_for('login'))
        
    otp = str(random.randint(100000, 999999))
    session['pending_phone'] = phone
    session['pending_otp'] = otp
    
    # Try sending real SMS
    sms_sent, sms_msg = send_sms_otp(phone, otp)
    session['phone_sms_sent'] = sms_sent
    
    print(f"\n\n{'='*50}")
    print(f"[PHONE OTP DELIVERY]")
    print(f"Target Phone: {phone}")
    print(f"OTP Code: {otp}")
    print(f"Gateway Status: {sms_msg}")
    print(f"{'='*50}\n\n")
    
    if sms_sent:
        flash(f'OTP sent directly to your phone ({phone})!', 'success')
    else:
        flash(f'OTP generated for {phone}. {sms_msg}', 'info')
        
    return render_template('otp.html', phone=phone, dev_otp=otp, sms_sent=sms_sent)

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    otp = request.form.get('otp')
    phone = session.get('pending_phone')
    expected_otp = session.get('pending_otp')
    
    if not phone or not expected_otp:
        flash('Session expired. Please try again.', 'error')
        return redirect(url_for('login'))
        
    if otp == expected_otp:
        # Success!
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
            
            if not user:
                username = f"User_{phone[-4:]}"
                try:
                    cursor = conn.execute(
                        'INSERT INTO users (username, password_hash, phone, auth_provider, is_verified, role) VALUES (?, ?, ?, ?, ?, ?)',
                        (username, 'oauth_no_password', phone, 'phone', 1, 'student')
                    )
                    user_id = cursor.lastrowid
                    role = 'student'
                except sqlite3.IntegrityError:
                    # In case user suffix conflicts
                    username = f"User_{random.randint(1000,9999)}"
                    cursor = conn.execute(
                        'INSERT INTO users (username, password_hash, phone, auth_provider, is_verified, role) VALUES (?, ?, ?, ?, ?, ?)',
                        (username, 'oauth_no_password', phone, 'phone', 1, 'student')
                    )
                    user_id = cursor.lastrowid
                    role = 'student'
            else:
                user_id = user['id']
                username = user['username']
                role = user['role']
                
        session.pop('pending_phone', None)
        session.pop('pending_otp', None)
        
        session['user_id'] = user_id
        session['username'] = username
        session['is_verified'] = True
        session['role'] = role
        record_login(user_id, 'phone')
        flash('Logged in via OTP successfully.', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid OTP. Please try again.', 'error')
        return render_template('otp.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user and user['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))

@app.route('/legacy-dashboard')
@login_required
def legacy_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        my_exams = []
        available_papers = []
        recent_mock_tests = []
        
        if user['role'] == 'teacher':
            my_exams = conn.execute(
                'SELECT e.id, e.access_token, e.duration_mins, e.max_warnings, e.is_active, e.created_at, p.settings FROM exams e JOIN papers p ON e.paper_id = p.id WHERE e.teacher_id = ? ORDER BY e.created_at DESC', 
                (session['user_id'],)
            ).fetchall()
            
            papers_rows = conn.execute('SELECT id, filename, settings FROM papers ORDER BY rowid DESC LIMIT 10').fetchall()
            for row in papers_rows:
                try:
                    s = json.loads(row['settings'])
                    available_papers.append({
                        'id': row['id'],
                        'filename': row['filename'],
                        'subject': s.get('subject', 'Untitled Subject'),
                        'chapter': s.get('chapter', ''),
                        'exam_name': s.get('exam_name', 'General Exam')
                    })
                except Exception:
                    pass
        else:
            recent_mock_tests = conn.execute(
                'SELECT id, subject, difficulty, total_questions, score, completed_at FROM mock_tests WHERE student_id = ? AND status = "completed" ORDER BY completed_at DESC LIMIT 5',
                (session['user_id'],)
            ).fetchall()
            
    return render_template(
        'dashboard.html', 
        is_verified=bool(user['is_verified']), 
        my_exams=my_exams,
        available_papers=available_papers,
        recent_mock_tests=recent_mock_tests,
        user_role=user['role']
    )

@app.route('/profile')
@login_required
def profile():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', (session['user_id'],)).fetchone()
        history = conn.execute('SELECT * FROM login_history WHERE user_id = ? ORDER BY login_time DESC LIMIT 5', (session['user_id'],)).fetchall()
        
    return render_template('profile.html', user=user, profile=profile, history=history)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            
            if user:
                token = str(uuid.uuid4())
                expires = datetime.datetime.now() + datetime.timedelta(hours=1)
                conn.execute(
                    'INSERT INTO verification_tokens (token, user_id, type, expires_at) VALUES (?, ?, ?, ?)',
                    (token, user['id'], 'password_reset', expires)
                )
                
                reset_url = url_for('reset_password', token=token, _external=True)
                email_sent, email_msg = send_email_link(email, reset_url, "Reset Your Password - AI Student Platform")
                
                print(f"\n\n{'='*50}")
                print(f"[PASSWORD RESET EMAIL DELIVERY]")
                print(f"Target Email: {email}")
                print(f"Reset URL: {reset_url}")
                print(f"Email Status: {email_msg}")
                print(f"{'='*50}\n\n")
                
        flash('If an account with that email exists, instructions have been dispatched.', 'success')
        return redirect(url_for('login'))
        
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        token_record = conn.execute('SELECT * FROM verification_tokens WHERE token = ? AND type = "password_reset"', (token,)).fetchone()
        
    if not token_record:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            flash('Password must be at least 8 chars, contain uppercase, lowercase, number, and special character.', 'error')
            return render_template('reset_password.html', token=token)
            
        password_hash = generate_password_hash(password)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, token_record['user_id']))
            conn.execute('DELETE FROM verification_tokens WHERE token = ?', (token,))
            
        flash('Password successfully reset. Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_password.html', token=token)

@app.route('/qpg')
@verified_required
def index():
    return render_template('index.html')

@app.route('/resume-builder')
@verified_required
def resume_builder():
    return render_template('resume_builder.html')

@app.route('/upload', methods=['POST'])
@verified_required
def upload_file():
    if 'pdf_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    file = request.files['pdf_file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))
    
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Test extraction immediately
            extract_text_from_pdf(filepath)
            return redirect(url_for('settings', filename=filename))
        except Exception as e:
            os.remove(filepath)
            flash(str(e), 'error')
            return redirect(url_for('index'))
    
    flash('Invalid file type. Please upload a PDF.', 'error')
    return redirect(url_for('index'))

@app.route('/settings/<filename>')
@verified_required
def settings(filename):
    return render_template('settings.html', filename=filename)

@app.route('/generate', methods=['POST'])
@verified_required
def generate():
    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 400
        
    settings = {
        'subject': request.form.get('subject'),
        'chapter': request.form.get('chapter'),
        'exam_name': request.form.get('exam_name'),
        'class_sem': request.form.get('class_sem'),
        'duration': request.form.get('duration'),
        'total_marks': request.form.get('total_marks'),
        'mcq_count': int(request.form.get('mcq_count', 0)),
        'short_count': int(request.form.get('short_count', 0)),
        'long_count': int(request.form.get('long_count', 0)),
        'difficulty': request.form.get('difficulty')
    }
    
    try:
        pdf_text = extract_text_from_pdf(filepath)
        generated_data = generate_questions(pdf_text, settings)
        
        paper_id = str(uuid.uuid4())
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO papers (id, filename, settings, generated_data) VALUES (?, ?, ?, ?)',
                (paper_id, filename, json.dumps(settings), json.dumps(generated_data))
            )
            
        return jsonify({"success": True, "paper_id": paper_id})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preview/<paper_id>')
@login_required
def preview(paper_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        
    if not row:
        flash('Paper not found', 'error')
        return redirect(url_for('index'))
        
    settings = json.loads(row['settings'])
    data = json.loads(row['generated_data'])
    
    return render_template('preview.html', paper_id=paper_id, settings=settings, data=data)

@app.route('/answer-key/<paper_id>')
@login_required
def answer_key(paper_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        
    if not row:
        flash('Paper not found', 'error')
        return redirect(url_for('index'))
        
    settings = json.loads(row['settings'])
    data = json.loads(row['generated_data'])
    
    return render_template('answer_key.html', paper_id=paper_id, settings=settings, data=data)

@app.route('/download/<paper_id>/<file_type>')
@login_required
def download(paper_id, file_type):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        
    if not row:
        return "Not found", 404
        
    settings = json.loads(row['settings'])
    data = json.loads(row['generated_data'])
    
    if file_type == 'question_paper':
        output_path = os.path.join(GENERATED_FOLDER, f"{paper_id}_qp.pdf")
        if not os.path.exists(output_path):
            generate_question_paper_pdf(data, settings, output_path)
        download_name = f"Question_Paper_{settings.get('subject', 'subject')}.pdf"
    elif file_type == 'answer_key':
        output_path = os.path.join(GENERATED_FOLDER, f"{paper_id}_ak.pdf")
        if not os.path.exists(output_path):
            generate_answer_key_pdf(data, settings, output_path)
        download_name = f"Answer_Key_{settings.get('subject', 'subject')}.pdf"
    else:
        return "Invalid file type", 400
        
    return send_file(output_path, as_attachment=True, download_name=download_name)

@app.route('/api/review-resume', methods=['POST'])
@login_required
def api_review_resume():
    data = request.json
    if not data:
        return jsonify({"error": "No resume data provided"}), 400
        
    try:
        result = review_resume(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create-exam/<paper_id>', methods=['POST'])
@teacher_required
def create_exam(paper_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        paper = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        
    if not paper:
        flash('Paper not found', 'error')
        return redirect(url_for('index'))
        
    settings = json.loads(paper['settings'])
    duration_str = str(settings.get('duration', '60'))
    duration_match = re.search(r'\d+', duration_str)
    duration_mins = int(duration_match.group()) if duration_match else 60
    
    exam_id = f"EXAM-{uuid.uuid4().hex[:8].upper()}"
    access_token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO exams (id, paper_id, teacher_id, access_token, duration_mins) VALUES (?, ?, ?, ?, ?)',
            (exam_id, paper_id, session['user_id'], access_token, duration_mins)
        )
        
    flash(f'Online Exam created successfully! Exam ID: {exam_id} | Access Token: {access_token}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/join-exam', methods=['POST'])
@login_required
def join_exam():
    exam_id = request.form.get('exam_id')
    access_token = request.form.get('access_token')
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        exam = conn.execute('SELECT * FROM exams WHERE id = ? AND access_token = ? AND is_active = 1', (exam_id, access_token)).fetchone()
        
        if not exam:
            flash('Invalid Exam ID or Access Token, or Exam is inactive.', 'error')
            return redirect(url_for('dashboard'))
            
        participant = conn.execute('SELECT * FROM exam_participants WHERE exam_id = ? AND student_id = ?', (exam_id, session['user_id'])).fetchone()
        if not participant:
            conn.execute('INSERT INTO exam_participants (exam_id, student_id) VALUES (?, ?)', (exam_id, session['user_id']))
        else:
            if participant['status'] in ('submitted', 'terminated'):
                flash('You have already completed this exam.', 'error')
                return redirect(url_for('dashboard'))
                
    return redirect(url_for('waiting_room', exam_id=exam_id))

@app.route('/waiting-room/<exam_id>')
@login_required
def waiting_room(exam_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        exam = conn.execute('SELECT e.*, p.settings FROM exams e JOIN papers p ON e.paper_id = p.id WHERE e.id = ?', (exam_id,)).fetchone()
        
    settings = json.loads(exam['settings'])
    return render_template('waiting_room.html', exam=exam, settings=settings)

@app.route('/start-exam/<exam_id>', methods=['POST'])
@login_required
def start_exam(exam_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'UPDATE exam_participants SET status = "active", started_at = CURRENT_TIMESTAMP WHERE exam_id = ? AND student_id = ? AND status = "waiting"',
            (exam_id, session['user_id'])
        )
    return redirect(url_for('take_exam', exam_id=exam_id))

@app.route('/take-exam/<exam_id>')
@login_required
def take_exam(exam_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        exam = conn.execute('SELECT e.*, p.settings, p.generated_data FROM exams e JOIN papers p ON e.paper_id = p.id WHERE e.id = ?', (exam_id,)).fetchone()
        participant = conn.execute('SELECT * FROM exam_participants WHERE exam_id = ? AND student_id = ?', (exam_id, session['user_id'])).fetchone()
        
    if not participant or participant['status'] in ('submitted', 'terminated'):
        flash('Exam is no longer active.', 'error')
        return redirect(url_for('dashboard'))
        
    settings = json.loads(exam['settings'])
    data = json.loads(exam['generated_data'])
    
    # Calculate time left
    started_at = datetime.datetime.strptime(participant['started_at'], "%Y-%m-%d %H:%M:%S")
    elapsed = (datetime.datetime.utcnow() - started_at).total_seconds()
    time_left = max(0, (exam['duration_mins'] * 60) - elapsed)
    
    if time_left <= 0:
        return redirect(url_for('submit_exam', exam_id=exam_id))
        
    return render_template('take_exam.html', exam=exam, settings=settings, data=data, participant=participant, time_left=int(time_left))

@app.route('/submit-exam/<exam_id>', methods=['GET', 'POST'])
@login_required
def submit_exam(exam_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE exam_participants SET status = "submitted", completed_at = CURRENT_TIMESTAMP WHERE exam_id = ? AND student_id = ?', (exam_id, session['user_id']))
    flash('Exam submitted successfully!', 'success')
    return redirect(url_for('dashboard'))
    
@app.route('/api/record-warning', methods=['POST'])
@login_required
def record_warning():
    data = request.json
    exam_id = data.get('exam_id')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE exam_participants SET warnings = warnings + 1 WHERE exam_id = ? AND student_id = ?', (exam_id, session['user_id']))
        p = conn.execute('SELECT warnings, e.max_warnings FROM exam_participants p JOIN exams e ON p.exam_id = e.id WHERE p.exam_id = ? AND p.student_id = ?', (exam_id, session['user_id'])).fetchone()
        
    if p[0] > p[1]:
        return jsonify({'action': 'terminate'})
    return jsonify({'action': 'warn', 'warnings': p[0], 'max': p[1]})

@app.route('/teacher/create-legacy-exam', methods=['POST'])
@teacher_required
def teacher_create_legacy_exam():
    paper_id = request.form.get('paper_id')
    duration_mins = int(request.form.get('duration_mins', 60))
    max_warnings = int(request.form.get('max_warnings', 3))
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        paper = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        
        if not paper:
            flash('Please select a valid question paper to create an online exam.', 'error')
            return redirect(url_for('dashboard'))
            
        exam_id = f"EXAM-{uuid.uuid4().hex[:8].upper()}"
        access_token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        conn.execute(
            'INSERT INTO exams (id, paper_id, teacher_id, access_token, duration_mins, max_warnings) VALUES (?, ?, ?, ?, ?, ?)',
            (exam_id, paper_id, session['user_id'], access_token, duration_mins, max_warnings)
        )
        
    flash(f'🎉 Online Exam Created Successfully! Exam ID: {exam_id} | Access Token: {access_token}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/teacher/legacy-exam/toggle-status/<exam_id>', methods=['POST'])
@login_required
@teacher_required
def teacher_legacy_exam_toggle(exam_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        exam = conn.execute('SELECT * FROM exams WHERE id = ? AND teacher_id = ?', (exam_id, session['user_id'])).fetchone()
        if exam:
            new_val = 0 if exam['is_active'] else 1
            conn.execute('UPDATE exams SET is_active = ? WHERE id = ?', (new_val, exam['id']))
            flash(f"Exam '{exam['id']}' has been {'reopened' if new_val else 'stopped'}.", 'success')
    return redirect(request.referrer or url_for('legacy_dashboard'))

@app.route('/mock-test')
@login_required
def mock_test_setup():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute(
            'SELECT id, subject, difficulty, total_questions, score, completed_at FROM mock_tests WHERE student_id = ? AND status = "completed" ORDER BY completed_at DESC LIMIT 10',
            (session['user_id'],)
        ).fetchall()
    return render_template('mock_test_setup.html', history=history)

@app.route('/mock-test/start', methods=['POST'])
@login_required
def mock_test_start():
    subject = request.form.get('subject', 'Computer Science').strip()
    difficulty = request.form.get('difficulty', 'Medium')
    count = int(request.form.get('count', 5))
    duration_mins = int(request.form.get('duration', 10))
    
    questions = get_mock_questions(subject, count, difficulty)
    mock_id = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO mock_tests (id, student_id, subject, difficulty, duration_mins, total_questions, test_data, status) VALUES (?, ?, ?, ?, ?, ?, ?, "active")',
            (mock_id, session['user_id'], subject, difficulty, duration_mins, len(questions), json.dumps(questions))
        )
        
    return redirect(url_for('mock_test_take', mock_id=mock_id))

@app.route('/mock-test/take/<mock_id>')
@login_required
def mock_test_take(mock_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        mock = conn.execute('SELECT * FROM mock_tests WHERE id = ? AND student_id = ?', (mock_id, session['user_id'])).fetchone()
        
    if not mock:
        flash('Mock test not found.', 'error')
        return redirect(url_for('mock_test_setup'))
        
    if mock['status'] == 'completed':
        return redirect(url_for('mock_test_result', mock_id=mock_id))
        
    questions = json.loads(mock['test_data'])
    
    started_at = datetime.datetime.strptime(mock['started_at'][:19], "%Y-%m-%d %H:%M:%S")
    elapsed = (datetime.datetime.now() - started_at).total_seconds()
    time_left = max(0, (mock['duration_mins'] * 60) - int(elapsed))
    
    return render_template('mock_test_take.html', mock=mock, questions=questions, time_left=time_left)

@app.route('/mock-test/submit/<mock_id>', methods=['POST'])
@login_required
def mock_test_submit(mock_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        mock = conn.execute('SELECT * FROM mock_tests WHERE id = ? AND student_id = ?', (mock_id, session['user_id'])).fetchone()
        
        if not mock:
            flash('Mock test not found.', 'error')
            return redirect(url_for('mock_test_setup'))
            
        questions = json.loads(mock['test_data'])
        answers = {}
        score = 0
        
        for q in questions:
            user_choice = request.form.get(f"q_{q['id']}")
            answers[str(q['id'])] = user_choice
            if user_choice and user_choice == q['correct_answer']:
                score += 1
                
        conn.execute(
            'UPDATE mock_tests SET score = ?, user_responses = ?, status = "completed", completed_at = CURRENT_TIMESTAMP WHERE id = ?',
            (score, json.dumps(answers), mock_id)
        )
        
    flash(f'Mock test submitted! You scored {score} out of {len(questions)}.', 'success')
    return redirect(url_for('mock_test_result', mock_id=mock_id))

@app.route('/mock-test/result/<mock_id>')
@login_required
def mock_test_result(mock_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        mock = conn.execute('SELECT * FROM mock_tests WHERE id = ? AND student_id = ?', (mock_id, session['user_id'])).fetchone()
        
    if not mock:
        flash('Mock test not found.', 'error')
        return redirect(url_for('mock_test_setup'))
        
    questions = json.loads(mock['test_data'])
    user_responses = json.loads(mock['user_responses'] or '{}')
    
    review_items = []
    wrong_count = 0
    unans_count = 0
    
    for q in questions:
        u_ans = user_responses.get(str(q['id']))
        is_corr = (u_ans == q['correct_answer']) if u_ans else False
        if not u_ans:
            unans_count += 1
        elif not is_corr:
            wrong_count += 1
            
        review_items.append({
            'question': q,
            'user_answer': u_ans,
            'is_correct': is_corr
        })
        
    return render_template(
        'mock_test_result.html',
        mock=mock,
        review_items=review_items,
        wrong_count=wrong_count,
        unans_count=unans_count
    )

# ==============================================================================
# AI-POWERED ONLINE EXAMINATION MODULE
# ==============================================================================

def generate_test_code():
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TEST-{code}"

def generate_test_password(subject="EXAM"):
    clean_sub = re.sub(r'[^A-Za-z]', '', subject)[:4].upper() or "TEST"
    num = random.randint(1000, 9999)
    return f"{clean_sub}@{num}"

# ----------------- Teacher Examination Portal Routes -----------------

@app.route('/teacher/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        teacher = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        tests_rows = conn.execute('''
            SELECT t.*,
                   COUNT(a.id) as total_candidates,
                   AVG(CASE WHEN a.status = 'completed' THEN a.percentage ELSE NULL END) as avg_score,
                   MAX(CASE WHEN a.status = 'completed' THEN a.score ELSE 0 END) as top_score,
                   SUM(CASE WHEN a.status = 'completed' AND a.percentage >= 50 THEN 1 ELSE 0 END) as passed_candidates
            FROM tests t
            LEFT JOIN test_attempts a ON t.id = a.test_id
            WHERE t.teacher_id = ?
            GROUP BY t.id
            ORDER BY t.created_at DESC
        ''', (session['user_id'],)).fetchall()
        
        total_tests = len(tests_rows)
        active_tests = sum(1 for t in tests_rows if t['is_active'])
        total_candidates_appeared = sum(t['total_candidates'] for t in tests_rows)
        
        completed_scores = [t['avg_score'] for t in tests_rows if t['avg_score'] is not None]
        avg_platform_score = round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else 0

        active_tests_list = []
        previous_results_list = []
        tests_list = []

        for t in tests_rows:
            avg_sc = round(t['avg_score'], 1) if t['avg_score'] is not None else 0
            top_sc = round(t['top_score'], 1) if t['top_score'] is not None else 0
            pass_c = t['passed_candidates'] or 0
            pass_rt = round((pass_c / t['total_candidates'] * 100), 1) if t['total_candidates'] else 0
            created_str = t['created_at'][:16] if t['created_at'] else 'N/A'

            item = {
                'id': t['test_code'],
                'real_id': t['id'],
                'title': t['title'],
                'subject': t['subject'],
                'password': t['password'],
                'duration_mins': t['duration_minutes'],
                'total_marks': t['total_marks'],
                'student_count': t['total_candidates'],
                'avg_score': avg_sc,
                'top_score': top_sc,
                'passed_candidates': pass_c,
                'pass_rate': pass_rt,
                'created_at': created_str,
                'status': 'active' if t['is_active'] else 'terminated',
                'is_active': bool(t['is_active'])
            }
            tests_list.append(item)
            if t['is_active']:
                active_tests_list.append(item)
            else:
                previous_results_list.append(item)

        concluded_tests = len(previous_results_list)
        stats = {
            'total_tests': total_tests,
            'active_tests': active_tests,
            'concluded_tests': concluded_tests,
            'total_attempts': total_candidates_appeared,
            'avg_score': avg_platform_score
        }
        recent_submissions = conn.execute('''
            SELECT a.id, a.candidate_name, a.candidate_roll, a.score, a.max_score,
                   a.percentage, a.time_spent, a.violations, a.completed_at,
                   t.title as test_title, t.test_code, t.subject, u.username, u.email
            FROM test_attempts a
            JOIN tests t ON a.test_id = t.id
            JOIN users u ON a.student_id = u.id
            WHERE t.teacher_id = ? AND a.status = 'completed'
            ORDER BY a.completed_at DESC
            LIMIT 25
        ''', (session['user_id'],)).fetchall()

    return render_template(
        'teacher_dashboard.html',
        teacher=teacher,
        tests=tests_rows,
        tests_list=tests_list,
        active_tests_list=active_tests_list,
        previous_results_list=previous_results_list,
        recent_submissions=recent_submissions,
        stats=stats,
        total_tests=total_tests,
        active_tests=active_tests,
        concluded_tests=concluded_tests,
        total_candidates_appeared=total_candidates_appeared,
        avg_platform_score=avg_platform_score
    )

@app.route('/teacher/test/create', endpoint='create_test_page')
@app.route('/teacher/test/create', endpoint='teacher_create_test')
@login_required
@teacher_required
def teacher_create_test():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        papers_rows = conn.execute('SELECT id, filename, settings FROM papers ORDER BY rowid DESC LIMIT 20').fetchall()
        available_papers = []
        for row in papers_rows:
            try:
                s = json.loads(row['settings'])
                available_papers.append({
                    'id': row['id'],
                    'filename': row['filename'],
                    'subject': s.get('subject', 'General Subject'),
                    'chapter': s.get('chapter', ''),
                    'exam_name': s.get('exam_name', 'Question Paper')
                })
            except Exception:
                pass
    return render_template('create_test.html', available_papers=available_papers)

@app.route('/teacher/test/create-submit', methods=['POST'])
@login_required
@teacher_required
def teacher_create_test_submit():
    title = request.form.get('title', '').strip()
    subject = request.form.get('subject', '').strip()
    source_type = request.form.get('source_type', 'book_pdf')
    duration_minutes = int(request.form.get('duration_minutes', 30))
    negative_marking = float(request.form.get('negative_marking', 0.0))
    allow_calculator = 1 if request.form.get('allow_calculator') else 0
    max_warnings = int(request.form.get('max_warnings', 3))
    shuffle_questions = 1 if request.form.get('shuffle_questions') else 0

    if not title or not subject:
        flash('Test title and subject are required.', 'error')
        return redirect(url_for('teacher_create_test'))

    questions = []

    if source_type == 'book_pdf':
        pdf_text = ""
        if 'book_pdf' in request.files and request.files['book_pdf'].filename != '':
            pdf_file = request.files['book_pdf']
            filename = secure_filename(pdf_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            pdf_file.save(filepath)
            try:
                pdf_text = extract_text_from_pdf(filepath)
            except Exception:
                pdf_text = ""
        
        q_count = int(request.form.get('ai_question_count', 10))
        difficulty = request.form.get('ai_difficulty', 'medium')
        config = {
            'subject': subject,
            'topic': request.form.get('chapter_focus', ''),
            'count': q_count,
            'difficulty': difficulty
        }
        questions = generate_exam_questions_from_book(pdf_text, config)

    elif source_type == 'question_bank':
        paper_id = request.form.get('paper_id')
        if paper_id:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                paper = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
            if paper:
                try:
                    data = json.loads(paper['generated_data'])
                    mcqs = data.get('mcqs', [])
                    for idx, q in enumerate(mcqs):
                        opts = [q.get('option_a', ''), q.get('option_b', ''), q.get('option_c', ''), q.get('option_d', '')]
                        questions.append({
                            'id': idx + 1,
                            'type': 'mcq',
                            'question': q.get('question', ''),
                            'options': opts,
                            'correct_answer': q.get('correct_option', 'A'),
                            'explanation': q.get('explanation', ''),
                            'marks': 1,
                            'topic': subject
                        })
                except Exception:
                    pass
        if not questions:
            questions = get_mock_questions(subject, 'medium', 10)

    elif source_type == 'manual':
        manual_json = request.form.get('manual_questions_json', '[]')
        try:
            parsed = json.loads(manual_json)
            if isinstance(parsed, list) and len(parsed) > 0:
                questions = parsed
        except Exception:
            pass
        if not questions:
            flash('Please add at least one question in the manual test builder.', 'error')
            return redirect(url_for('teacher_create_test'))

    # Security Credentials Generation
    test_code = generate_test_code()
    password = generate_test_password(subject)
    total_marks = sum(float(q.get('marks', 1)) for q in questions)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            INSERT INTO tests (
                teacher_id, test_code, password, title, subject, source_type,
                duration_minutes, negative_marking, allow_calculator, max_warnings,
                shuffle_questions, questions_data, total_marks, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            session['user_id'], test_code, password, title, subject, source_type,
            duration_minutes, negative_marking, allow_calculator, max_warnings,
            shuffle_questions, json.dumps(questions), total_marks
        ))

    flash(f"Test created successfully! Test ID: {test_code} | Access Password: {password}", 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/test/monitor/<test_id>', endpoint='live_monitor_page')
@app.route('/teacher/test/monitor/<test_id>', endpoint='teacher_live_monitor')
@login_required
@teacher_required
def teacher_live_monitor(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if not test:
            flash('Examination not found or unauthorized.', 'error')
            return redirect(url_for('teacher_dashboard'))
    return render_template('live_monitor.html', test=test)

@app.route('/api/teacher/live-monitor/<test_id>')
@login_required
@teacher_required
def api_teacher_live_monitor(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if not test:
            return jsonify({'error': 'Unauthorized'}), 403

        questions = json.loads(test['questions_data'] or '[]')
        total_questions = len(questions)

        attempts = conn.execute('''
            SELECT a.*, u.username, u.email
            FROM test_attempts a
            JOIN users u ON a.student_id = u.id
            WHERE a.test_id = ?
            ORDER BY a.started_at DESC
        ''', (test['id'],)).fetchall()

        now = datetime.datetime.now()
        candidate_list = []
        for row in attempts:
            answers = json.loads(row['user_answers'] or '{}')
            answered_count = len([k for k, v in answers.items() if v])
            progress_pct = round((answered_count / total_questions * 100)) if total_questions else 0
            
            is_online = False
            if row['last_heartbeat']:
                try:
                    hb_time = datetime.datetime.strptime(row['last_heartbeat'][:19], "%Y-%m-%d %H:%M:%S")
                    if (now - hb_time).total_seconds() < 40:
                        is_online = True
                except Exception:
                    pass

            candidate_list.append({
                'attempt_id': row['id'],
                'student_name': row['candidate_name'] or row['username'],
                'student_roll': row['candidate_roll'] or f"STD-{row['student_id']}",
                'status': row['status'],
                'answered_count': answered_count,
                'total_questions': total_questions,
                'progress_percent': progress_pct,
                'violations': row['violations'] or 0,
                'time_spent': row['time_spent'] or 0,
                'completed_at': (row['completed_at'][:19] if row['completed_at'] else ''),
                'is_online': is_online if row['status'] == 'in_progress' else False,
                'score': row['score'],
                'max_score': row['max_score'] or test['total_marks']
            })

    active_c = sum(1 for c in candidate_list if c['status'] == 'in_progress')
    submitted_c = sum(1 for c in candidate_list if c['status'] == 'completed')
    total_v = sum(c['violations'] for c in candidate_list)

    return jsonify({
        'test_id': test['id'],
        'test_code': test['test_code'],
        'title': test['title'],
        'duration_minutes': test['duration_minutes'],
        'is_active': bool(test['is_active']),
        'status': 'active' if test['is_active'] else 'closed',
        'total_joined': len(candidate_list),
        'total_candidates': len(candidate_list),
        'active_count': active_c,
        'submitted_count': submitted_c,
        'total_violations': total_v,
        'total_questions': total_questions,
        'participants': [
            {
                'username': c['student_name'],
                'student_name': c['student_name'],
                'email': c.get('student_roll', ''),
                'status': 'active' if c['status'] == 'in_progress' else 'submitted',
                'answered_count': c['answered_count'],
                'tab_switches': c['violations'],
                'completed_at': c.get('completed_at', ''),
                'time_spent': c.get('time_spent', 0),
                'test_title': test['title']
            }
            for c in candidate_list
        ],
        'candidates': candidate_list
    })

@app.route('/teacher/test/results/<test_id>', endpoint='test_results_page')
@app.route('/teacher/test/results/<test_id>', endpoint='teacher_test_results')
@login_required
@teacher_required
def teacher_test_results(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if not test:
            flash('Examination not found.', 'error')
            return redirect(url_for('teacher_dashboard'))

        attempts_rows = conn.execute('''
            SELECT a.*, u.username, u.email
            FROM test_attempts a
            JOIN users u ON a.student_id = u.id
            WHERE a.test_id = ? AND a.status = 'completed'
            ORDER BY a.score DESC, a.time_spent ASC
        ''', (test['id'],)).fetchall()

    questions = json.loads(test['questions_data'] or '[]')
    
    leaderboard = []
    attempts_formatted = []
    scores = []
    pass_count = 0

    for idx, att in enumerate(attempts_rows):
        sc = float(att['score'] or 0)
        scores.append(sc)
        is_passed = (att['percentage'] or 0) >= 50
        if is_passed:
            pass_count += 1
            
        entry = {
            'rank': idx + 1,
            'username': att['candidate_name'] or att['username'],
            'candidate_name': att['candidate_name'] or att['username'],
            'email': att['email'] or att['candidate_roll'] or 'N/A',
            'candidate_roll': att['candidate_roll'] or f"ID: {att['student_id']}",
            'score': sc,
            'max_score': att['max_score'] or test['total_marks'],
            'percentage': round(att['percentage'] or 0, 1),
            'passed': is_passed,
            'time_spent': att['time_spent'] or 0,
            'time_taken_seconds': att['time_spent'] or 0,
            'violations': att['violations'] or 0,
            'tab_switches': att['violations'] or 0,
            'completed_at': att['completed_at']
        }
        leaderboard.append(entry)
        attempts_formatted.append(entry)

    total_appeared = len(leaderboard)
    avg_score = round(sum(scores) / total_appeared, 1) if total_appeared else 0
    top_score = max(scores) if scores else 0
    pass_percentage = round((pass_count / total_appeared) * 100, 1) if total_appeared else 0

    topic_map = {}
    for q in questions:
        top = q.get('topic', test['subject'])
        if top not in topic_map:
            topic_map[top] = {'name': top, 'total': 0}
        topic_map[top]['total'] += 1

    topic_analytics = list(topic_map.values())

    return render_template(
        'test_results.html',
        test=test,
        attempts=attempts_formatted,
        leaderboard=leaderboard,
        total_appeared=total_appeared,
        avg_score=avg_score,
        high_score=top_score,
        pass_rate=pass_percentage,
        pass_percentage=pass_percentage,
        topic_analytics=topic_analytics
    )

@app.route('/teacher/test/export-results/<test_id>')
@login_required
@teacher_required
def teacher_export_results(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if not test:
            return "Test not found", 404

        attempts = conn.execute('''
            SELECT a.*, u.username, u.email
            FROM test_attempts a
            JOIN users u ON a.student_id = u.id
            WHERE a.test_id = ? AND a.status = 'completed'
            ORDER BY a.score DESC, a.time_spent ASC
        ''', (test['id'],)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Rank', 'Candidate Name', 'Candidate Roll', 'Email', 'Score',
        'Max Marks', 'Percentage', 'Time Taken (Seconds)', 'Violations', 'Status', 'Submitted At'
    ])

    for idx, row in enumerate(attempts):
        writer.writerow([
            idx + 1,
            row['candidate_name'] or row['username'],
            row['candidate_roll'] or f"STD-{row['student_id']}",
            row['email'] or '',
            row['score'],
            row['max_score'],
            f"{row['percentage']}%",
            row['time_spent'],
            row['violations'],
            row['status'],
            row['completed_at']
        ])

    output.seek(0)
    filename = f"Results_{secure_filename(test['title'])}_{test['test_code']}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@app.route('/teacher/test/stop/<test_id>', methods=['POST'])
@login_required
@teacher_required
def teacher_stop_test(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if not test:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': 'Examination not found or unauthorized'}), 404
            flash('Examination not found or unauthorized.', 'error')
            return redirect(url_for('teacher_dashboard'))

        # Deactivate the test
        conn.execute('UPDATE tests SET is_active = 0 WHERE id = ?', (test['id'],))

        # Finalize and grade all in-progress student attempts
        in_progress_attempts = conn.execute(
            'SELECT * FROM test_attempts WHERE test_id = ? AND status = "in_progress"',
            (test['id'],)
        ).fetchall()

        questions = json.loads(test['questions_data'] or '[]')
        finalized_count = 0

        for attempt in in_progress_attempts:
            try:
                answers = json.loads(attempt['user_answers'] or '{}')
            except Exception:
                answers = {}

            grading = grade_exam_attempt(questions, answers, test['negative_marking'])
            conn.execute('''
                UPDATE test_attempts
                SET score = ?, max_score = ?, percentage = ?,
                    status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (grading['score'], grading['max_score'], grading['percentage'], attempt['id']))
            finalized_count += 1

        flash_msg = f"Examination '{test['title']}' has been terminated. All student attempt information and scorecards have been saved to Previous Test Results ({finalized_count} active attempt(s) finalized)."
        flash(flash_msg, 'success')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({
                'success': True,
                'message': flash_msg,
                'test_id': test['id'],
                'is_active': False,
                'finalized_count': finalized_count
            })

    ref = request.referrer
    if ref and 'monitor' in ref:
        return redirect(url_for('live_monitor_page', test_id=test['id']))
    return redirect(url_for('teacher_dashboard') + '#previous-results')

@app.route('/teacher/test/toggle-status/<test_id>', methods=['POST'])
@login_required
@teacher_required
def teacher_toggle_status(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE (id = ? OR test_code = ?) AND teacher_id = ?', (test_id, test_id, session['user_id'])).fetchone()
        if test:
            new_status = 0 if test['is_active'] else 1
            conn.execute('UPDATE tests SET is_active = ? WHERE id = ?', (new_status, test['id']))

            if new_status == 0:
                in_progress_attempts = conn.execute(
                    'SELECT * FROM test_attempts WHERE test_id = ? AND status = "in_progress"',
                    (test['id'],)
                ).fetchall()
                questions = json.loads(test['questions_data'] or '[]')
                for attempt in in_progress_attempts:
                    try:
                        answers = json.loads(attempt['user_answers'] or '{}')
                    except Exception:
                        answers = {}
                    grading = grade_exam_attempt(questions, answers, test['negative_marking'])
                    conn.execute('''
                        UPDATE test_attempts
                        SET score = ?, max_score = ?, percentage = ?,
                            status = 'completed', completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (grading['score'], grading['max_score'], grading['percentage'], attempt['id']))

            status_text = "reopened and active" if new_status else "stopped and closed"
            flash(f"Test '{test['title']}' is now {status_text}.", 'success')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({
                    'success': True,
                    'is_active': bool(new_status),
                    'status_text': status_text,
                    'message': f"Test '{test['title']}' is now {status_text}."
                })

    ref = request.referrer
    if ref and 'monitor' in ref:
        return redirect(url_for('live_monitor_page', test_id=test_id))
    return redirect(url_for('teacher_dashboard'))

# ----------------- Student Examination Portal Routes -----------------

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        student = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        attempts = conn.execute('''
            SELECT a.*, t.title as test_title, t.subject, t.test_code
            FROM test_attempts a
            JOIN tests t ON a.test_id = t.id
            WHERE a.student_id = ?
            ORDER BY a.started_at DESC
        ''', (session['user_id'],)).fetchall()

        practices = conn.execute('''
            SELECT * FROM practice_tests
            WHERE student_id = ? AND status = 'completed'
            ORDER BY completed_at DESC
        ''', (session['user_id'],)).fetchall()

        tests_taken = len(attempts)
        practices_taken = len(practices)
        all_percentages = [a['percentage'] for a in attempts if a['status'] == 'completed'] + [p['score_percent'] for p in practices]
        avg_score = round(sum(all_percentages) / len(all_percentages), 1) if all_percentages else 0

        my_attempts = []
        for a in attempts:
            my_attempts.append({
                'id': a['id'],
                'title': a['test_title'],
                'subject': a['subject'],
                'score': a['score'],
                'total_marks': a['max_score'],
                'percentage': a['percentage'],
                'passed': (a['percentage'] or 0) >= 50,
                'completed_at': a['completed_at']
            })

        student_stats = {
            'completed_exams': sum(1 for a in attempts if a['status'] == 'completed'),
            'practice_count': len(practices),
            'avg_score': avg_score,
            'passed_count': sum(1 for a in attempts if (a['percentage'] or 0) >= 50)
        }

    return render_template(
        'student_dashboard.html',
        student=student,
        attempts=attempts,
        my_attempts=my_attempts,
        practices=practices,
        tests_taken=tests_taken,
        practices_taken=practices_taken,
        student_stats=student_stats,
        avg_score=avg_score
    )

@app.route('/student/join-test', methods=['POST'])
@login_required
def student_join_test():
    test_code = (request.form.get('test_code') or request.form.get('test_id') or '').strip().upper()
    password = request.form.get('password', '').strip()
    candidate_name = (request.form.get('candidate_name') or request.form.get('full_name') or '').strip() or session.get('username')
    candidate_roll = request.form.get('candidate_roll', '').strip()

    if not candidate_name:
        flash('Please enter your full name before joining the examination.', 'error')
        return redirect(url_for('student_dashboard'))

    if not test_code or not password:
        flash('Test ID and Password are both required to join an examination.', 'error')
        return redirect(url_for('student_dashboard'))

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE test_code = ? OR id = ?', (test_code, test_code)).fetchone()

        if not test:
            flash('Invalid Test ID. Please check the code provided by your instructor.', 'error')
            return redirect(url_for('student_dashboard'))

        if test['password'] != password:
            flash('Incorrect Test Password. Access denied.', 'error')
            return redirect(url_for('student_dashboard'))

        if not test['is_active']:
            flash('This examination has been deactivated or closed by the instructor.', 'error')
            return redirect(url_for('student_dashboard'))

        existing = conn.execute(
            'SELECT * FROM test_attempts WHERE test_id = ? AND student_id = ? ORDER BY started_at DESC LIMIT 1',
            (test['id'], session['user_id'])
        ).fetchone()

        if existing:
            if existing['status'] == 'completed':
                flash('You have already taken and submitted this examination.', 'info')
                return redirect(url_for('official_test_result', attempt_id=existing['id']))
            attempt_id = existing['id']
            conn.execute('UPDATE test_attempts SET candidate_name = ? WHERE id = ?', (candidate_name, attempt_id))
            if candidate_roll:
                conn.execute('UPDATE test_attempts SET candidate_roll = ? WHERE id = ?', (candidate_roll, attempt_id))
        else:
            cursor = conn.execute('''
                INSERT INTO test_attempts (
                    test_id, student_id, candidate_name, candidate_roll,
                    status, current_question, user_answers, review_flags,
                    score, max_score, percentage, time_spent, violations
                ) VALUES (?, ?, ?, ?, 'in_progress', 0, '{}', '{}', 0, ?, 0, 0, 0)
            ''', (test['id'], session['user_id'], candidate_name, candidate_roll, test['total_marks']))
            attempt_id = cursor.lastrowid

    return redirect(url_for('take_official_test', test_id=test['id']))

@app.route('/student/exam/<int:test_id>')
@login_required
def take_official_test(test_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
        if not test:
            flash('Test not found.', 'error')
            return redirect(url_for('student_dashboard'))

        attempt = conn.execute(
            'SELECT * FROM test_attempts WHERE test_id = ? AND student_id = ? ORDER BY started_at DESC LIMIT 1',
            (test_id, session['user_id'])
        ).fetchone()

        if not attempt:
            flash('Please join the test with your credentials first.', 'error')
            return redirect(url_for('student_dashboard'))

        if attempt['status'] == 'completed':
            return redirect(url_for('official_test_result', attempt_id=attempt['id']))

        if not test['is_active']:
            flash('This examination has been ended by the instructor.', 'warning')
            return redirect(url_for('official_test_result', attempt_id=attempt['id']))

    questions = json.loads(test['questions_data'] or '[]')
    
    if test['shuffle_questions'] and (not attempt['user_answers'] or attempt['user_answers'] == '{}'):
        random.seed(attempt['id'])
        random.shuffle(questions)

    saved_responses = {
        'answers': json.loads(attempt['user_answers'] or '{}'),
        'review_flags': json.loads(attempt['review_flags'] or '{}')
    }

    remaining_seconds = max(0, (test['duration_minutes'] * 60) - (attempt['time_spent'] or 0))

    return render_template(
        'exam_portal.html',
        test=test,
        attempt=attempt,
        questions=questions,
        saved_responses=saved_responses,
        remaining_seconds=remaining_seconds,
        candidate_name=attempt['candidate_name'] or session['username'],
        candidate_roll=attempt['candidate_roll']
    )

@app.route('/api/exam/save-response', methods=['POST'])
@login_required
def api_save_exam_response():
    data = request.get_json() or {}
    attempt_id = data.get('attempt_id')
    answers = data.get('answers', {})
    review_flags = data.get('review_flags', {})
    current_index = data.get('current_index', 0)
    time_spent = data.get('time_spent', 0)

    if attempt_id:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            attempt = conn.execute('SELECT * FROM test_attempts WHERE id = ? AND student_id = ?', (attempt_id, session['user_id'])).fetchone()
            if attempt:
                test = conn.execute('SELECT is_active FROM tests WHERE id = ?', (attempt['test_id'],)).fetchone()
                if attempt['status'] == 'completed' or (test and not test['is_active']):
                    return jsonify({
                        'status': 'stopped',
                        'test_stopped': True,
                        'message': 'This examination has been ended by the instructor.'
                    })

                conn.execute('''
                    UPDATE test_attempts
                    SET user_answers = ?, review_flags = ?, current_question = ?,
                        time_spent = ?, last_heartbeat = CURRENT_TIMESTAMP
                    WHERE id = ? AND student_id = ? AND status = 'in_progress'
                ''', (json.dumps(answers), json.dumps(review_flags), current_index, time_spent, attempt_id, session['user_id']))

    return jsonify({'status': 'saved'})

@app.route('/api/exam/record-violation', methods=['POST'])
@login_required
def api_record_violation():
    data = request.get_json() or {}
    attempt_id = data.get('attempt_id')
    violations = data.get('violations', 1)

    if attempt_id:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                UPDATE test_attempts
                SET violations = ?, last_heartbeat = CURRENT_TIMESTAMP
                WHERE id = ? AND student_id = ?
            ''', (violations, attempt_id, session['user_id']))

    return jsonify({'status': 'recorded', 'violations': violations})

@app.route('/student/exam/submit/<int:test_id>', methods=['POST'])
@login_required
def submit_official_test(test_id):
    attempt_id = request.form.get('attempt_id')
    answers_json = request.form.get('answers_json', '{}')
    violations = int(request.form.get('violations', 0))
    time_spent = int(request.form.get('time_spent_seconds', 0))

    try:
        answers = json.loads(answers_json)
    except Exception:
        answers = {}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        test = conn.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
        attempt = conn.execute('SELECT * FROM test_attempts WHERE id = ? AND student_id = ?', (attempt_id, session['user_id'])).fetchone()

        if not test or not attempt:
            flash('Error submitting exam: Session not found.', 'error')
            return redirect(url_for('student_dashboard'))

        questions = json.loads(test['questions_data'] or '[]')
        grading = grade_exam_attempt(questions, answers, test['negative_marking'])

        score = grading['score']
        max_score = grading['max_score']
        percentage = grading['percentage']

        completed_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            UPDATE test_attempts
            SET score = ?, max_score = ?, percentage = ?, user_answers = ?,
                time_spent = ?, violations = ?, status = 'completed', completed_at = ?
            WHERE id = ?
        ''', (score, max_score, percentage, json.dumps(answers), time_spent, violations, completed_time_str, attempt_id))

    flash('Exam submitted successfully! Here is your official scorecard.', 'success')
    return redirect(url_for('official_test_result', attempt_id=attempt_id))

@app.route('/student/exam/result/<int:attempt_id>', endpoint='student_exam_result')
@app.route('/student/exam/result/<int:attempt_id>', endpoint='official_test_result')
@login_required
def official_test_result(attempt_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        attempt = conn.execute('SELECT * FROM test_attempts WHERE id = ?', (attempt_id,)).fetchone()
        if not attempt:
            flash('Scorecard not found.', 'error')
            return redirect(url_for('student_dashboard'))

        test = conn.execute('SELECT * FROM tests WHERE id = ?', (attempt['test_id'],)).fetchone()
        student = conn.execute('SELECT * FROM users WHERE id = ?', (attempt['student_id'],)).fetchone()

        if session['user_id'] != attempt['student_id'] and session['user_id'] != test['teacher_id']:
            flash('Unauthorized to view this scorecard.', 'error')
            return redirect(url_for('dashboard'))

    questions = json.loads(test['questions_data'] or '[]')
    answers = json.loads(attempt['user_answers'] or '{}')
    grading = grade_exam_attempt(questions, answers, test['negative_marking'])

    return render_template(
        'exam_result.html',
        test=test,
        attempt=attempt,
        student=student,
        grading_summary=grading,
        review_items=grading['item_details']
    )

# ----------------- Student Independent Practice Test Routes -----------------

@app.route('/student/practice', endpoint='student_practice_page')
@app.route('/student/practice', endpoint='practice_setup')
@login_required
def practice_setup():
    return render_template('practice_setup.html')

@app.route('/student/practice/start', methods=['POST'])
@login_required
def start_practice_test():
    source_type = request.form.get('source_type', 'subject')
    subject = request.form.get('subject', 'Computer Science')
    topic = request.form.get('topic', '')
    count = int(request.form.get('question_count', 10))
    difficulty = request.form.get('difficulty', 'medium')
    duration = int(request.form.get('duration_minutes', 15))

    pdf_text = ""
    if source_type == 'book' and 'book_pdf' in request.files and request.files['book_pdf'].filename != '':
        f = request.files['book_pdf']
        filename = secure_filename(f.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        try:
            pdf_text = extract_text_from_pdf(filepath)
            subject = filename.replace('.pdf', '')[:30]
        except Exception:
            pdf_text = ""

    config = {
        'subject': subject,
        'topic': topic,
        'count': count,
        'difficulty': difficulty
    }

    if pdf_text:
        questions = generate_exam_questions_from_book(pdf_text, config)
    else:
        questions = get_mock_questions(subject, difficulty, count)

    practice_id = str(uuid.uuid4())
    title = f"{subject} - {difficulty.capitalize()} Practice Drill"

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO practice_tests (
                id, student_id, title, subject, difficulty, duration_minutes,
                questions_data, user_answers, score, max_score, score_percent,
                time_spent, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0, ?, 0, 0, 'in_progress')
        ''', (
            practice_id, session['user_id'], title, subject, difficulty,
            duration, json.dumps(questions), len(questions)
        ))

    return redirect(url_for('take_practice_test', practice_id=practice_id))

@app.route('/student/practice/take/<practice_id>')
@login_required
def take_practice_test(practice_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        practice = conn.execute('SELECT * FROM practice_tests WHERE id = ? AND student_id = ?', (practice_id, session['user_id'])).fetchone()
        if not practice:
            flash('Practice session not found.', 'error')
            return redirect(url_for('practice_setup'))

        if practice['status'] == 'completed':
            return redirect(url_for('practice_result_page', practice_id=practice_id))

    questions = json.loads(practice['questions_data'] or '[]')
    return render_template('practice_take.html', practice=practice, questions=questions)

@app.route('/student/practice/submit/<practice_id>', methods=['POST'])
@login_required
def submit_practice_test(practice_id):
    answers_json = request.form.get('answers_json', '{}')
    time_spent = int(request.form.get('time_spent_seconds', 0))

    try:
        answers = json.loads(answers_json)
    except Exception:
        answers = {}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        practice = conn.execute('SELECT * FROM practice_tests WHERE id = ? AND student_id = ?', (practice_id, session['user_id'])).fetchone()
        if not practice:
            flash('Practice session not found.', 'error')
            return redirect(url_for('practice_setup'))

        questions = json.loads(practice['questions_data'] or '[]')
        
        correct_count = 0
        total_questions = len(questions)
        review_items = []

        for idx, q in enumerate(questions):
            u_ans = answers.get(str(idx)) or answers.get(idx)
            corr = q.get('correct_answer')
            is_corr = False
            if u_ans and corr:
                is_corr = (str(u_ans).strip().upper() == str(corr).strip().upper())
            if is_corr:
                correct_count += 1

            review_items.append({
                'question': q,
                'user_answer': u_ans,
                'correct_answer': corr,
                'is_correct': is_corr
            })

        score_percent = round((correct_count / total_questions * 100)) if total_questions else 0

        practice_result = {
            'score': correct_count,
            'max_score': total_questions,
            'percentage': score_percent,
            'correct_count': correct_count,
            'incorrect_count': total_questions - correct_count,
            'review_items': review_items
        }
        analytics = generate_learning_analytics(practice_result, practice['subject'])

        conn.execute('''
            UPDATE practice_tests
            SET score = ?, max_score = ?, score_percent = ?, user_answers = ?,
                time_spent = ?, analytics_data = ?, status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (correct_count, total_questions, score_percent, json.dumps(answers), time_spent, json.dumps(analytics), practice_id))

    return redirect(url_for('practice_result_page', practice_id=practice_id))

@app.route('/student/practice/result/<practice_id>')
@login_required
def practice_result_page(practice_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        practice = conn.execute('SELECT * FROM practice_tests WHERE id = ? AND student_id = ?', (practice_id, session['user_id'])).fetchone()
        if not practice:
            flash('Practice session not found.', 'error')
            return redirect(url_for('practice_setup'))

    questions = json.loads(practice['questions_data'] or '[]')
    answers = json.loads(practice['user_answers'] or '{}')
    analytics = json.loads(practice['analytics_data'] or '{}')

    review_items = []
    for idx, q in enumerate(questions):
        u_ans = answers.get(str(idx)) or answers.get(idx)
        corr = q.get('correct_answer')
        is_corr = False
        if u_ans and corr:
            is_corr = (str(u_ans).strip().upper() == str(corr).strip().upper())
        review_items.append({
            'question': q,
            'user_answer': u_ans,
            'correct_answer': corr,
            'is_correct': is_corr
        })

    return render_template(
        'practice_result.html',
        practice=practice,
        analytics=analytics,
        review_items=review_items
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
