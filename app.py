# New imports for email, PDF, and analytics
from flask_mail import Mail, Message
from dotenv import load_dotenv
from xhtml2pdf import pisa
from io import BytesIO
from flask import send_file
import os
import datetime
import sqlite3
from collections import defaultdict

# Load environment variables
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session
from database import *

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# Add this near the top of app.py, after your imports
def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
init_database()

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if verify_admin(username, password):
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    """Admin dashboard to add students"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        # Get student details
        roll_number = request.form['roll_number']
        name = request.form['name']
        student_class = request.form['class']
        password = request.form['password']
        
        # Add student to database
        student_id = add_student(roll_number, name, student_class, password)
        
        if student_id:
            # Add marks
            subjects_marks = {
                'Math': request.form['math'],
                'Science': request.form['science'],
                'English': request.form['english'],
                'Hindi': request.form['hindi'],
                'Computer': request.form['computer']
            }
            add_marks(student_id, subjects_marks)
            message = f"Student {name} added successfully!"
        else:
            message = "Roll number already exists!"
        
        students = get_all_students()
        return render_template('admin_dashboard.html', students=students, message=message)
    
    students = get_all_students()
    return render_template('admin_dashboard.html', students=students)

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin', None)
    return redirect(url_for('index'))

# ==================== STUDENT ROUTES (UPDATED - WITHOUT enter_roll) ====================

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """Combined student login and roll number entry (Steps 5 & 6 combined)"""
    if request.method == 'POST':
        roll_number = request.form['roll_number']
        password = request.form['password']
        
        # Get student from database
        student = get_student_by_roll(roll_number)
        
        if student and student['password'] == password:
            session['student_roll'] = roll_number
            return redirect(url_for('view_result', roll_number=roll_number))
        else:
            return render_template('student_login.html', error='Invalid roll number or password')
    
    return render_template('student_login.html')

@app.route('/student/result/<roll_number>')
def view_result(roll_number):
    """Display student result"""
    if 'student_roll' not in session or session['student_roll'] != roll_number:
        return redirect(url_for('student_login'))
    
    student = get_student_by_roll(roll_number)
    if student:
        marks = get_student_marks(student['id'])
        total_marks = sum(mark['marks'] for mark in marks)
        percentage = (total_marks / 500) * 100
        
        # Determine grade based on percentage
        if percentage >= 90:
            grade = 'A+'
        elif percentage >= 80:
            grade = 'A'
        elif percentage >= 70:
            grade = 'B+'
        elif percentage >= 60:
            grade = 'B'
        elif percentage >= 50:
            grade = 'C'
        elif percentage >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        return render_template('result.html', 
                             student=student, 
                             marks=marks, 
                             total=total_marks, 
                             percentage=round(percentage, 2),
                             grade=grade)
    
    return redirect(url_for('student_login'))

@app.route('/student/logout')
def student_logout():
    """Student logout"""
    session.pop('student_roll', None)
    return redirect(url_for('index'))

# ==================== FEATURE 1: ANALYTICS DASHBOARD ====================

@app.route('/admin/analytics')
def admin_analytics():
    """Show performance analytics with charts"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Get all students
    students = conn.execute('SELECT * FROM students').fetchall()
    
    if not students:
        conn.close()
        return render_template('analytics.html', 
                             grade_distribution={},
                             subject_averages={},
                             top_students=[],
                             total_students=0)
    
    # Prepare data
    subject_totals = defaultdict(list)
    grade_distribution = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    student_data = []
    
    for student in students:
        marks = conn.execute('SELECT subject, marks FROM marks WHERE student_id = ?', 
                           (student['id'],)).fetchall()
        
        if not marks:
            continue
            
        total = sum(m['marks'] for m in marks)
        percentage = total / 5
        
        # Grade calculation
        if percentage >= 90:
            grade = 'A+'
        elif percentage >= 80:
            grade = 'A'
        elif percentage >= 70:
            grade = 'B+'
        elif percentage >= 60:
            grade = 'B'
        elif percentage >= 50:
            grade = 'C'
        elif percentage >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        grade_distribution[grade] += 1
        
        # Subject-wise collection
        for mark in marks:
            subject_totals[mark['subject']].append(mark['marks'])
        
        student_data.append({
            'name': student['name'],
            'roll': student['roll_number'],
            'percentage': round(percentage, 2),
            'grade': grade
        })
    
    # Calculate subject averages
    subject_averages = {}
    for subject, marks in subject_totals.items():
        subject_averages[subject] = round(sum(marks) / len(marks), 2) if marks else 0
    
    # Sort students by percentage for top performers
    top_students = sorted(student_data, key=lambda x: x['percentage'], reverse=True)[:5]
    
    conn.close()
    
    return render_template('analytics.html',
                         grade_distribution=grade_distribution,
                         subject_averages=subject_averages,
                         top_students=top_students,
                         total_students=len(students))

# ==================== FEATURE 2: EMAIL RESULTS ====================

@app.route('/admin/send-result/<int:student_id>', methods=['POST'])
def send_result_email(student_id):
    """Send simple email result to student"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    email = request.form['email']
    
    # Get student data
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    marks = conn.execute('SELECT subject, marks FROM marks WHERE student_id = ?', 
                        (student_id,)).fetchall()
    conn.close()
    
    # Calculate total and percentage
    total = sum(m['marks'] for m in marks)
    percentage = total / 5
    
    # Create email content
    subject = f"📚 Your Exam Results - {student['name']}"
    
    body = f"""
STUDENT RESULTS PORTAL

Dear {student['name']},

Your exam results are now available.

📋 STUDENT DETAILS
• Roll Number: {student['roll_number']}
• Class: {student['class']}

📊 YOUR MARKS
"""
    
    for mark in marks:
        body += f"• {mark['subject']}: {mark['marks']}/100\n"
    
    body += f"""
📈 SUMMARY
• Total Marks: {total}/500
• Percentage: {percentage:.1f}%
• Result: {'PASS' if percentage >= 33 else 'FAIL'}

You can view your result online at:
http://localhost:5000/student/result/{student['roll_number']}

Best regards,
Student Results Portal
"""
    
    try:
        msg = Message(subject, 
                      sender=app.config['MAIL_USERNAME'], 
                      recipients=[email])
        msg.body = body
        mail.send(msg)
        
        return redirect(url_for('admin_dashboard', 
                                message=f"✅ Email sent to {email}"))
    
    except Exception as e:
        return redirect(url_for('admin_dashboard', 
                                message=f"❌ Error: {str(e)}"))

# ==================== FEATURE 3: LEADERBOARD ====================

@app.route('/leaderboard')
def leaderboard():
    """Public leaderboard showing top performers"""
    
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    
    leaderboard_data = []
    
    for student in students:
        marks = conn.execute('SELECT marks FROM marks WHERE student_id = ?', 
                           (student['id'],)).fetchall()
        
        if not marks:
            continue
            
        total = sum(m['marks'] for m in marks)
        percentage = total / 5
        
        # Grade calculation
        if percentage >= 90:
            grade = 'A+'
        elif percentage >= 80:
            grade = 'A'
        elif percentage >= 70:
            grade = 'B+'
        elif percentage >= 60:
            grade = 'B'
        elif percentage >= 50:
            grade = 'C'
        elif percentage >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        leaderboard_data.append({
            'name': student['name'],
            'roll': student['roll_number'],
            'class': student['class'],
            'total': total,
            'percentage': round(percentage, 2),
            'grade': grade
        })
    
    # Sort by percentage
    leaderboard_data.sort(key=lambda x: x['percentage'], reverse=True)
    
    # Add ranks
    for i, student in enumerate(leaderboard_data, 1):
        student['rank'] = i
    
    conn.close()
    
    return render_template('leaderboard.html', students=leaderboard_data[:50])
    
# ==================== FEATURE 4: PDF GENERATION ====================

@app.route('/student/download-pdf/<roll_number>')
def download_result_pdf(roll_number):
    """Download result as PDF"""
    if 'student_roll' not in session or session['student_roll'] != roll_number:
        return redirect(url_for('student_login'))
    
    # Get student data
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE roll_number = ?', 
                          (roll_number,)).fetchone()
    marks = conn.execute('SELECT subject, marks FROM marks WHERE student_id = ?', 
                        (student['id'],)).fetchall()
    conn.close()
    
    # Calculate totals and grade
    total = sum(m['marks'] for m in marks)
    percentage = total / 5
    
    if percentage >= 90:
        grade = 'A+'
    elif percentage >= 80:
        grade = 'A'
    elif percentage >= 70:
        grade = 'B+'
    elif percentage >= 60:
        grade = 'B'
    elif percentage >= 50:
        grade = 'C'
    elif percentage >= 33:
        grade = 'D'
    else:
        grade = 'F'
    
    # Get current date
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    
    # Render HTML template for PDF
    html = render_template('result_pdf.html', 
                         student=student,
                         marks=marks,
                         total=total,
                         percentage=round(percentage, 2),
                         grade=grade,
                         date=current_date)
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('UTF-8')), result)
    
    if not pdf.err:
        result.seek(0)
        return send_file(
            result,
            as_attachment=True,
            download_name=f"Result_{student['roll_number']}.pdf",
            mimetype='application/pdf'
        )
    
    return "Error generating PDF", 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return "Internal Server Error", 500

# ==================== DELETE STUDENT ROUTE ====================

@app.route('/admin/delete-student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """Delete a student and their marks"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First delete marks (because of foreign key constraint)
        cursor.execute('DELETE FROM marks WHERE student_id = ?', (student_id,))
        
        # Then delete the student
        cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
        
        conn.commit()
        message = "Student deleted successfully!"
    except Exception as e:
        message = f"Error deleting student: {str(e)}"
    finally:
        conn.close()
    
    return redirect(url_for('admin_dashboard', message=message))

# ==================== EDIT STUDENT ROUTE ====================

@app.route('/admin/edit-student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    """Edit student details and marks"""
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get updated data from form
        name = request.form['name']
        student_class = request.form['class']
        password = request.form['password']
        
        # Update student details
        conn.execute('''
            UPDATE students 
            SET name = ?, class = ?, password = ?
            WHERE id = ?
        ''', (name, student_class, password, student_id))
        
        # Update marks for each subject
        subjects = ['Math', 'Science', 'English', 'Hindi', 'Computer']
        for subject in subjects:
            marks = request.form[subject.lower()]
            conn.execute('''
                UPDATE marks 
                SET marks = ? 
                WHERE student_id = ? AND subject = ?
            ''', (marks, student_id, subject))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('admin_dashboard', message="Student updated successfully!"))
    
    # GET request - show edit form
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    marks = conn.execute('SELECT subject, marks FROM marks WHERE student_id = ?', (student_id,)).fetchall()
    conn.close()
    
    # Convert marks to dictionary for easy access
    marks_dict = {mark['subject']: mark['marks'] for mark in marks}
    
    return render_template('edit_student.html', student=student, marks=marks_dict)

if __name__ == '__main__':
    app.run(debug=True, port=5000)