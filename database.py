import sqlite3
import os

def get_db_connection():
    """Create connection to SQLite database"""
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create admin table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    
    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            class TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Create marks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            marks INTEGER NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')
    
    # Insert default admin (username: admin, password: admin123)
    try:
        cursor.execute('''
            INSERT INTO admin (username, password) 
            VALUES (?, ?)
        ''', ('admin', 'admin123'))
    except:
        pass  # Admin already exists
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def add_student(roll_number, name, student_class, password):
    """Add a new student to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO students (roll_number, name, class, password) 
            VALUES (?, ?, ?, ?)
        ''', (roll_number, name, student_class, password))
        student_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return student_id
    except Exception as e:
        conn.close()
        return None

def add_marks(student_id, subjects_marks):
    """Add marks for a student"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for subject, marks in subjects_marks.items():
        cursor.execute('''
            INSERT INTO marks (student_id, subject, marks) 
            VALUES (?, ?, ?)
        ''', (student_id, subject, marks))
    
    conn.commit()
    conn.close()

def get_student_by_roll(roll_number):
    """Get student details by roll number"""
    conn = get_db_connection()
    student = conn.execute('''
        SELECT * FROM students WHERE roll_number = ?
    ''', (roll_number,)).fetchone()
    conn.close()
    return student

def get_student_marks(student_id):
    """Get marks for a student"""
    conn = get_db_connection()
    marks = conn.execute('''
        SELECT subject, marks FROM marks WHERE student_id = ?
    ''', (student_id,)).fetchall()
    conn.close()
    return marks

def verify_admin(username, password):
    """Verify admin credentials"""
    conn = get_db_connection()
    admin = conn.execute('''
        SELECT * FROM admin WHERE username = ? AND password = ?
    ''', (username, password)).fetchone()
    conn.close()
    return admin is not None

def get_all_students():
    """Get all students (for admin view)"""
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return students