import os, json, io
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_file
from markupsafe import Markup
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'edupredict-dev-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'students.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ── Models ──────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='teacher')
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)

    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    @property
    def is_staff(self): return self.role in ('admin', 'teacher')
    @property
    def is_parent(self): return self.role == 'parent'
    def get_id(self): return str(self.id)
    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(20))
    year_level = db.Column(db.Integer)
    semester = db.Column(db.String(30))
    school_year = db.Column(db.String(30))
    email = db.Column(db.String(100))
    is_scholar = db.Column(db.Boolean, default=False)
    is_working_student = db.Column(db.Boolean, default=False)
    parent_phone = db.Column(db.String(20))
    parent_name = db.Column(db.String(100))
    records = db.relationship('ClassRecord', backref='student', lazy=True)
    predictions = db.relationship('Prediction', backref='student', lazy=True)
    activities = db.relationship('StudentActivity', backref='student', lazy=True)
    quiz_scores = db.relationship('QuizScore', backref='student', lazy=True)
    notifications = db.relationship('Notification', backref='student', lazy=True)


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    records = db.relationship('ClassRecord', backref='subject', lazy=True)
    topics = db.relationship('Topic', backref='subject', lazy=True)


class Topic(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    quiz_scores = db.relationship('QuizScore', backref='topic', lazy=True)


class QuizScore(db.Model):
    __tablename__ = 'quiz_scores'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    score = db.Column(db.Float, default=0)
    max_score = db.Column(db.Float, default=100)
    term = db.Column(db.String(20))


class ClassRecord(db.Model):
    __tablename__ = 'class_records'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    term = db.Column(db.String(20))
    semester = db.Column(db.String(30))
    school_year = db.Column(db.String(30))
    class_standing = db.Column(db.Float, default=0)     # Equiv % (weight 20%)
    exam_score = db.Column(db.Float, default=0)          # Equiv % (weight 50%)
    task_performance = db.Column(db.Float, default=0)    # Equiv % (weight 30%)
    attendance = db.Column(db.Float, default=100)         # Tracked separately, not in grade
    final_grade = db.Column(db.Float, default=0)          # CS*0.20 + TP*0.30 + Exam*0.50


class StudentActivity(db.Model):
    __tablename__ = 'student_activities'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    activity_type = db.Column(db.String(30))
    date = db.Column(db.String(10))
    notes = db.Column(db.Text)
    subject = db.relationship('Subject')


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    term = db.Column(db.String(20), default='Prelim')  # Prelim / Midterm / Finals
    meeting_number = db.Column(db.Integer, nullable=False)  # 1-5
    date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(10), nullable=False, default='Present')  # Present / Absent
    room = db.Column(db.String(50))
    student = db.relationship('Student', backref='attendance_records')


def _calc_attendance_grade(present_count):
    """Attendance grade: base 50 + 10 per present (max 5 meetings = 100)."""
    return min(100, 50 + present_count * 10)


def _get_attendance_grade(student_id, term='Prelim'):
    """Get attendance grade for a student in a given term."""
    records = AttendanceRecord.query.filter_by(student_id=student_id, term=term).all()
    present = sum(1 for r in records if r.status == 'Present')
    return _calc_attendance_grade(present)


def _attendance_risk_level(att_grade):
    """Risk level from attendance grade: 50-60=High, 70-80=Medium, 90-100=Low."""
    if att_grade <= 60:
        return 'High'
    elif att_grade <= 80:
        return 'Medium'
    return 'Low'


class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    risk_level = db.Column(db.String(10))
    predicted_grade = db.Column(db.Float)
    confidence = db.Column(db.Float)
    feature_importance = db.Column(db.Text)
    cluster_label = db.Column(db.String(30))
    recommendations = db.relationship('Recommendation', backref='prediction', lazy=True)
    subject = db.relationship('Subject')

    @property
    def max_possible_grade(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('max_possible_grade')
        return None

    @property
    def exam_needed(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('exam_needed')
        return None

    @property
    def exam_needed_raw(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('exam_needed_raw')
        return None

    @property
    def exam_max_items(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('exam_max_items', 50)
        return 50

    @property
    def high_risk_flags(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('high_risk_flags', [])
        return []

    @property
    def medium_risk_flags(self):
        if self.feature_importance:
            data = json.loads(self.feature_importance)
            return data.get('medium_risk_flags', [])
        return []


class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'), nullable=False)
    message = db.Column(db.Text)
    strategy_type = db.Column(db.String(50))
    topic_name = db.Column(db.String(100))
    interventions = db.relationship('InterventionLog', backref='recommendation', lazy=True)


class InterventionLog(db.Model):
    __tablename__ = 'intervention_log'
    id = db.Column(db.Integer, primary_key=True)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('recommendations.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    outcome = db.Column(db.String(20))
    notes = db.Column(db.Text)
    followed_up_at = db.Column(db.String(20))


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='warning')  # warning, info, success
    is_read = db.Column(db.Boolean, default=False)
    sms_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notifications')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _auto_predict_student(student_id):
    from ml_engine import predict_for_student
    predict_for_student(db.session, student_id)
    _create_risk_notifications(student_id)
    _check_attendance_notifications(student_id)


def _check_attendance_notifications(student_id):
    """Auto-notify student and parent when attendance grade indicates risk (5-meeting system)."""
    student = db.session.get(Student, student_id)
    if not student:
        return
    att_grade = _get_attendance_grade(student_id, 'Prelim')
    att_risk = _attendance_risk_level(att_grade)
    if att_risk == 'Low':
        return

    records = AttendanceRecord.query.filter_by(student_id=student_id, term='Prelim').all()
    present = sum(1 for r in records if r.status == 'Present')
    absent = len(records) - present

    title = f'Attendance Alert: {student.name}'
    message = (
        f'{student.name} has {present} present out of {len(records)} meetings (Prelim). '
        f'Attendance Grade: {att_grade}. Risk Level: {att_risk}. '
    )
    if att_risk == 'High':
        message += 'Immediate consultation with the instructor is needed.'
    else:
        message += 'Please coordinate with the instructor to improve attendance.'

    student_user = User.query.filter_by(student_id=student_id, role='student').first()
    parent_user = User.query.filter_by(student_id=student_id, role='parent').first()

    for user in [student_user, parent_user]:
        if not user:
            continue
        existing = Notification.query.filter_by(
            user_id=user.id, student_id=student_id, title=title, is_read=False
        ).first()
        if existing:
            continue
        notif = Notification(
            user_id=user.id, student_id=student_id,
            title=title, message=message,
            type='danger' if att_risk == 'High' else 'warning',
        )
        db.session.add(notif)

    db.session.commit()


def _create_risk_notifications(student_id):
    """Create in-app notifications for student & parent when at risk."""
    student = db.session.get(Student, student_id)
    if not student:
        return
    high_preds = Prediction.query.filter_by(student_id=student_id, risk_level='High').all()
    medium_preds = Prediction.query.filter_by(student_id=student_id, risk_level='Medium').all()
    at_risk = high_preds + medium_preds
    if not at_risk:
        return

    # Build percentage indicator from prediction data
    from ml_engine import calculate_pre_exam_prediction
    subject_details = []
    for p in at_risk:
        record = ClassRecord.query.filter_by(
            student_id=student_id, subject_id=p.subject_id
        ).order_by(ClassRecord.id.desc()).first()
        if record:
            pre = calculate_pre_exam_prediction(record.class_standing, record.task_performance)
            max_poss = pre['max_possible_grade']
            raw = pre['exam_needed_raw']
            max_items = pre['exam_max_items']
            subj_name = p.subject.name if p.subject else 'Unknown'
            if p.risk_level == 'High':
                subject_details.append(
                    f'{subj_name} – max possible grade: {max_poss:.1f}% (cannot pass even with a perfect {max_items}/{max_items} exam)'
                )
            else:
                subject_details.append(
                    f'{subj_name} – needs at least {raw}/{max_items} on the exam to pass'
                )

    high_subjects = [p.subject.name for p in high_preds if p.subject]

    # Find student and parent user accounts
    student_user = User.query.filter_by(student_id=student_id, role='student').first()
    parent_user = User.query.filter_by(student_id=student_id, role='parent').first()

    title = f'Risk Alert: {student.name}'
    if high_preds:
        message = (f'{student.name} is at HIGH RISK of failing even after taking the exam. '
                   f'{"; ".join(subject_details)}. '
                   f'Consultation with instructor is needed.')
    else:
        message = (f'{student.name} needs a high exam score to pass. '
                   f'{"; ".join(subject_details)}. '
                   f'Please review the recommendations.')

    for user in [student_user, parent_user]:
        if not user:
            continue
        existing = Notification.query.filter_by(
            user_id=user.id, student_id=student_id, title=title, is_read=False
        ).first()
        if existing:
            continue
        notif = Notification(
            user_id=user.id, student_id=student_id,
            title=title, message=message,
            type='danger' if high_preds else 'warning',
        )
        db.session.add(notif)

    # SMS notification for parent ONLY when high risk (can't pass even with exam)
    if parent_user and high_subjects and student.parent_phone:
        record = ClassRecord.query.filter_by(student_id=student_id).order_by(ClassRecord.id.desc()).first()
        if record:
            pre = calculate_pre_exam_prediction(record.class_standing, record.task_performance)
            sms_msg = (f'EduPredict Alert: {student.name} is HIGH RISK – max possible grade is '
                       f'{pre["max_possible_grade"]:.1f}% even with a perfect exam. '
                       f'Consultation with instructor is needed. Please login to view details.')
        else:
            sms_msg = (f'EduPredict Alert: {student.name} is HIGH RISK of failing in '
                       f'{", ".join(high_subjects)}. Please login to view details.')
        _send_sms(student.parent_phone, sms_msg)
        latest_notif = Notification.query.filter_by(
            user_id=parent_user.id, student_id=student_id
        ).order_by(Notification.id.desc()).first()
        if latest_notif:
            latest_notif.sms_sent = True

    db.session.commit()


def _send_sms(phone_number, message):
    """Send SMS notification. In production, integrate with Twilio/Semaphore API.
    Currently logs the message for demo purposes."""
    print(f'[SMS] To: {phone_number} | Message: {message}')
    # To enable real SMS, install twilio and configure:
    # from twilio.rest import Client
    # client = Client(TWILIO_SID, TWILIO_TOKEN)
    # client.messages.create(body=message, from_=TWILIO_PHONE, to=phone_number)


def staff_required(f):
    """Decorator: allow only admin and teacher roles."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_staff:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'student' and user.student_id:
                return redirect(url_for('student_profile', student_id=user.student_id))
            if user.role == 'parent' and user.student_id:
                return redirect(url_for('student_profile', student_id=user.student_id))
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@staff_required
def dashboard():
    total_students = Student.query.count()
    high_risk = Prediction.query.filter_by(risk_level='High').count()
    medium_risk = Prediction.query.filter_by(risk_level='Medium').count()
    low_risk = Prediction.query.filter_by(risk_level='Low').count()
    pending_interventions = InterventionLog.query.filter_by(status='pending').count()

    # Top 3 high-risk students
    high_risk_students = (
        db.session.query(Prediction, Student)
        .join(Student).filter(Prediction.risk_level == 'High')
        .order_by(Prediction.id.desc()).limit(3).all()
    )
    # Top 3 medium-risk students
    medium_risk_students = (
        db.session.query(Prediction, Student)
        .join(Student).filter(Prediction.risk_level == 'Medium')
        .order_by(Prediction.id.desc()).limit(3).all()
    )
    # Top 3 students with highest grades
    top_performers = (
        db.session.query(ClassRecord, Student)
        .join(Student, ClassRecord.student_id == Student.id)
        .order_by(ClassRecord.final_grade.desc()).limit(3).all()
    )

    return render_template('dashboard.html',
                           total_students=total_students,
                           high_risk=high_risk,
                           medium_risk=medium_risk,
                           low_risk=low_risk,
                           pending_interventions=pending_interventions,
                           high_risk_students=high_risk_students,
                           medium_risk_students=medium_risk_students,
                           top_performers=top_performers)


@app.route('/students')
@staff_required
def students():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    section_filter = request.args.get('section', '')
    semester_filter = request.args.get('semester', '')
    sy_filter = request.args.get('school_year', '')
    query = Student.query
    if section_filter:
        query = query.filter_by(section=section_filter)
    if semester_filter:
        query = query.filter_by(semester=semester_filter)
    if sy_filter:
        query = query.filter_by(school_year=sy_filter)
    pagination = query.order_by(Student.name).paginate(page=page, per_page=per_page, error_out=False)
    all_students = pagination.items
    predictions_map = {}
    for s in all_students:
        pred = Prediction.query.filter_by(student_id=s.id).order_by(Prediction.id.desc()).first()
        predictions_map[s.id] = pred
    sections = [r[0] for r in db.session.query(Student.section).distinct().order_by(Student.section).all() if r[0]]
    semesters = [r[0] for r in db.session.query(Student.semester).distinct().all() if r[0]]
    school_years = [r[0] for r in db.session.query(Student.school_year).distinct().all() if r[0]]
    return render_template('students.html', students=all_students, predictions=predictions_map,
                           pagination=pagination, sections=sections, semesters=semesters,
                           school_years=school_years, current_section=section_filter,
                           current_semester=semester_filter, current_sy=sy_filter)


@app.route('/students/add', methods=['POST'])
@staff_required
def add_student():
    try:
        name = request.form.get('name', '').strip()
        section = request.form.get('section', '').strip()
        year_level = int(request.form.get('year_level', 1))
        semester = request.form.get('semester', '').strip()
        school_year = request.form.get('school_year', '').strip()
        email = request.form.get('email', '').strip()
        is_scholar = request.form.get('is_scholar') == 'on'
        is_working = request.form.get('is_working_student') == 'on'
        parent_name = request.form.get('parent_name', '').strip()
        parent_phone = request.form.get('parent_phone', '').strip()
        if not name:
            flash('Student name is required.', 'danger')
            return redirect(url_for('students'))
        student = Student(
            name=name, section=section, year_level=year_level,
            semester=semester, school_year=school_year,
            email=email, is_scholar=is_scholar, is_working_student=is_working,
            parent_name=parent_name, parent_phone=parent_phone,
        )
        db.session.add(student)
        db.session.flush()
        # Create student user account
        username = name.lower().replace(' ', '_')
        base_username = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f'{base_username}_{counter}'
            counter += 1
        user = User(username=username, role='student', student_id=student.id)
        user.set_password('student123')
        db.session.add(user)
        db.session.commit()
        flash(f'Student "{name}" added. Login: {username} / student123', 'success')
    except (ValueError, KeyError) as e:
        flash(f'Error adding student: {str(e)}', 'danger')
    return redirect(url_for('students'))


@app.route('/students/delete/<int:student_id>', methods=['POST'])
@staff_required
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    name = student.name
    # Delete related records in dependency order
    prediction_ids = [p.id for p in Prediction.query.filter_by(student_id=student_id).all()]
    if prediction_ids:
        rec_ids = [r.id for r in Recommendation.query.filter(Recommendation.prediction_id.in_(prediction_ids)).all()]
        if rec_ids:
            InterventionLog.query.filter(InterventionLog.recommendation_id.in_(rec_ids)).delete(synchronize_session=False)
            Recommendation.query.filter(Recommendation.id.in_(rec_ids)).delete(synchronize_session=False)
        Prediction.query.filter_by(student_id=student_id).delete()
    QuizScore.query.filter_by(student_id=student_id).delete()
    ClassRecord.query.filter_by(student_id=student_id).delete()
    StudentActivity.query.filter_by(student_id=student_id).delete()
    AttendanceRecord.query.filter_by(student_id=student_id).delete()
    Notification.query.filter_by(student_id=student_id).delete()
    User.query.filter_by(student_id=student_id).delete()
    db.session.delete(student)
    db.session.commit()
    flash(f'Student "{name}" and all related data removed.', 'success')
    return redirect(url_for('students'))


@app.route('/student/<int:student_id>')
@login_required
def student_profile(student_id):
    if current_user.role == 'student' and current_user.student_id != student_id:
        abort(403)
    if current_user.role == 'parent' and current_user.student_id != student_id:
        abort(403)
    student = db.session.get(Student, student_id)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students') if current_user.is_staff else url_for('login'))
    records = ClassRecord.query.filter_by(student_id=student_id).all()
    predictions = Prediction.query.filter_by(student_id=student_id).all()
    activities = StudentActivity.query.filter_by(student_id=student_id).order_by(StudentActivity.id.desc()).limit(20).all()

    weak_topics = (
        db.session.query(Topic.name, func.avg(QuizScore.score / QuizScore.max_score * 100).label('avg_pct'))
        .join(QuizScore, QuizScore.topic_id == Topic.id)
        .filter(QuizScore.student_id == student_id)
        .group_by(Topic.id)
        .having(func.avg(QuizScore.score / QuizScore.max_score * 100) < 75)
        .all()
    )

    fi_data = {}
    for p in predictions:
        if p.feature_importance:
            fi_data[p.subject.name] = json.loads(p.feature_importance)

    # Pre-exam prediction: min exam score needed per subject
    from ml_engine import calculate_pre_exam_prediction
    pre_exam_data = []
    subjects_seen = set()
    for r in sorted(records, key=lambda x: x.id, reverse=True):
        if r.subject_id in subjects_seen:
            continue
        subjects_seen.add(r.subject_id)
        subj = db.session.get(Subject, r.subject_id)
        pred_info = calculate_pre_exam_prediction(r.class_standing, r.task_performance)
        pred_info['subject_name'] = subj.name if subj else f'Subject {r.subject_id}'
        pred_info['term'] = r.term
        pred_info['class_standing'] = r.class_standing
        pred_info['task_performance'] = r.task_performance
        pred_info['attendance'] = r.attendance
        pre_exam_data.append(pred_info)

    # Attendance present count for parent view (5-meeting system)
    att_present = 0
    att_total = 0
    att_records = AttendanceRecord.query.filter_by(student_id=student_id, term='Prelim').all()
    if att_records:
        att_present = sum(1 for r in att_records if r.status == 'Present')
        att_total = len(att_records)

    return render_template('student_profile.html',
                           student=student, records=records,
                           predictions=predictions, activities=activities,
                           weak_topics=weak_topics, fi_data=fi_data,
                           pre_exam_data=pre_exam_data,
                           att_present=att_present, att_total=att_total)


@app.route('/class-records', methods=['GET', 'POST'])
@login_required
def class_records():
    if request.method == 'POST' and not current_user.is_staff:
        abort(403)
    if request.method == 'POST':
        try:
            student_id = int(request.form['student_id'])
            cs = float(request.form.get('class_standing', 0))
            tp = float(request.form.get('task_performance', 0))
            exam = float(request.form.get('exam_score', 0))
            final = cs * 0.20 + tp * 0.30 + exam * 0.50
            record = ClassRecord(
                student_id=student_id,
                subject_id=int(request.form['subject_id']),
                term=request.form['term'],
                semester=request.form.get('semester', ''),
                school_year=request.form.get('school_year', ''),
                class_standing=cs,
                exam_score=exam,
                task_performance=tp,
                attendance=float(request.form.get('attendance', 100)),
                final_grade=round(final, 2),
            )
            db.session.add(record)
            db.session.commit()
            _auto_predict_student(student_id)
            flash('Class record saved & predictions updated automatically.', 'success')
        except (ValueError, KeyError):
            flash('Invalid data. Please check all fields.', 'danger')
        return redirect(url_for('class_records'))

    query = (
        db.session.query(ClassRecord, Student, Subject)
        .join(Student, ClassRecord.student_id == Student.id)
        .join(Subject, ClassRecord.subject_id == Subject.id)
    )
    if current_user.role == 'student' and current_user.student_id:
        query = query.filter(ClassRecord.student_id == current_user.student_id)
    if current_user.role == 'parent' and current_user.student_id:
        query = query.filter(ClassRecord.student_id == current_user.student_id)
    all_records = query.order_by(Subject.name, Student.name, ClassRecord.term).all()

    # Group records by subject for tab-based display
    records_by_subject = {}
    for rec, student, subject in all_records:
        records_by_subject.setdefault(subject.name, []).append((rec, student, subject))

    all_students = Student.query.order_by(Student.name).all()
    all_subjects = Subject.query.order_by(Subject.name).all()
    sections = [r[0] for r in db.session.query(Student.section).distinct().order_by(Student.section).all() if r[0]]
    return render_template('class_records.html',
                           records_by_subject=records_by_subject,
                           students=all_students, subjects=all_subjects,
                           sections=sections)


@app.route('/class-records/<int:record_id>/edit', methods=['POST'])
@staff_required
def edit_class_record(record_id):
    record = db.session.get(ClassRecord, record_id)
    if not record:
        flash('Record not found.', 'danger')
        return redirect(url_for('class_records'))
    try:
        record.class_standing = float(request.form.get('class_standing', record.class_standing))
        record.exam_score = float(request.form.get('exam_score', record.exam_score))
        record.task_performance = float(request.form.get('task_performance', record.task_performance))
        record.attendance = float(request.form.get('attendance', record.attendance))
        record.final_grade = round(record.class_standing * 0.20 + record.task_performance * 0.30 + record.exam_score * 0.50, 2)
        db.session.commit()
        _auto_predict_student(record.student_id)
        flash('Record updated & predictions refreshed.', 'success')
    except (ValueError, TypeError) as e:
        flash(f'Invalid data: {str(e)}', 'danger')
    return redirect(url_for('class_records'))


@app.route('/api/class-records')
@staff_required
def api_class_records():
    """Return JSON list of class records for a given subject and term."""
    subject_id = request.args.get('subject_id', type=int)
    term = request.args.get('term', '')
    section = request.args.get('section', '')
    if not subject_id or not term:
        return jsonify({'records': []})
    query = (
        db.session.query(ClassRecord, Student)
        .join(Student, ClassRecord.student_id == Student.id)
        .filter(ClassRecord.subject_id == subject_id, ClassRecord.term == term)
    )
    if section:
        query = query.filter(Student.section == section)
    rows = query.order_by(Student.name).all()
    records = []
    for rec, student in rows:
        records.append({
            'id': rec.id,
            'student_name': student.name,
            'class_standing': rec.class_standing,
            'task_performance': rec.task_performance,
            'exam_score': rec.exam_score,
            'attendance': rec.attendance,
            'final_grade': rec.final_grade,
        })
    return jsonify({'records': records})


@app.route('/class-records/bulk-exam', methods=['POST'])
@staff_required
def bulk_exam_scores():
    """Update exam scores for multiple students at once."""
    record_ids = request.form.getlist('record_ids')
    exam_scores = request.form.getlist('exam_scores')
    updated = 0
    student_ids = set()
    for rid, score_str in zip(record_ids, exam_scores):
        score_str = score_str.strip()
        if not score_str:
            continue
        try:
            record = db.session.get(ClassRecord, int(rid))
            if not record:
                continue
            exam_val = float(score_str)
            if exam_val < 0 or exam_val > 100:
                continue
            record.exam_score = round(exam_val, 2)
            record.final_grade = round(
                record.class_standing * 0.20 + record.task_performance * 0.30 + record.exam_score * 0.50, 2
            )
            updated += 1
            student_ids.add(record.student_id)
        except (ValueError, TypeError):
            continue
    db.session.commit()
    for sid in student_ids:
        _auto_predict_student(sid)
    flash(f'Updated exam scores for {updated} student(s). Predictions refreshed.', 'success')
    return redirect(url_for('class_records'))


@app.route('/predict', methods=['POST'])
@staff_required
def run_prediction():
    from ml_engine import predict_all
    results = predict_all(db.session)
    # Generate notifications for all at-risk students
    at_risk_student_ids = (
        db.session.query(Prediction.student_id)
        .filter(Prediction.risk_level.in_(['High', 'Medium']))
        .distinct().all()
    )
    for (sid,) in at_risk_student_ids:
        _create_risk_notifications(sid)
    flash(f'Predictions generated for {results} students.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/reports')
@staff_required
def reports():
    risk_filter = request.args.get('risk', 'all')
    query = (
        db.session.query(Prediction, Student, Subject)
        .join(Student, Prediction.student_id == Student.id)
        .join(Subject, Prediction.subject_id == Subject.id)
    )
    if risk_filter in ('High', 'Medium', 'Low'):
        query = query.filter(Prediction.risk_level == risk_filter)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Student.name).paginate(page=page, per_page=per_page, error_out=False)
    data = pagination.items
    return render_template('reports.html', data=data, risk_filter=risk_filter, pagination=pagination)


# ── Analytics ──────────────────────────────────────────────────────────────

@app.route('/analytics')
@staff_required
def analytics():
    subject_risks = (
        db.session.query(Subject.name, Prediction.risk_level, func.count())
        .join(Prediction, Prediction.subject_id == Subject.id)
        .group_by(Subject.name, Prediction.risk_level).all()
    )
    subject_data = {}
    for subj, risk, cnt in subject_risks:
        subject_data.setdefault(subj, {'High': 0, 'Medium': 0, 'Low': 0})[risk] = cnt

    section_data = (
        db.session.query(Student.section, func.avg(ClassRecord.final_grade))
        .join(ClassRecord, ClassRecord.student_id == Student.id)
        .group_by(Student.section).all()
    )

    intervention_stats = (
        db.session.query(InterventionLog.outcome, func.count())
        .filter(InterventionLog.outcome.isnot(None))
        .group_by(InterventionLog.outcome).all()
    )
    intervention_data = {r[0]: r[1] for r in intervention_stats}

    cluster_dist = (
        db.session.query(Prediction.cluster_label, func.count())
        .filter(Prediction.cluster_label.isnot(None))
        .group_by(Prediction.cluster_label).all()
    )

    return render_template('analytics.html',
                           subject_data=subject_data, section_data=section_data,
                           intervention_data=intervention_data, cluster_dist=cluster_dist)


# ── Interventions ──────────────────────────────────────────────────────────

@app.route('/interventions')
@staff_required
def interventions():
    status_filter = request.args.get('status', 'all')
    section_filter = request.args.get('section', '')
    risk_filter = request.args.get('risk', '')
    search_q = request.args.get('q', '').strip()
    selected_student_id = request.args.get('student_id', 0, type=int)

    # Students list for selection (filtered)
    student_query = db.session.query(Student).join(
        Prediction, Prediction.student_id == Student.id
    )
    if section_filter:
        student_query = student_query.filter(Student.section == section_filter)
    if risk_filter in ('High', 'Medium'):
        student_query = student_query.filter(Prediction.risk_level == risk_filter)
    if search_q:
        student_query = student_query.filter(Student.name.ilike(f'%{search_q}%'))
    at_risk_students = student_query.distinct().order_by(Student.name).all()

    # Selected student details
    selected_student = None
    student_topics = []
    student_interventions = []
    student_prediction = None
    if selected_student_id:
        selected_student = db.session.get(Student, selected_student_id)
        if selected_student:
            student_prediction = Prediction.query.filter_by(
                student_id=selected_student_id
            ).order_by(Prediction.id.desc()).first()
            # Get topics for the student's subject
            topics = Topic.query.join(Subject).join(
                Prediction, Prediction.subject_id == Subject.id
            ).filter(Prediction.student_id == selected_student_id).all()
            student_topics = topics if topics else Topic.query.all()
            # Existing interventions for this student
            student_interventions = (
                db.session.query(InterventionLog, Recommendation, Prediction)
                .join(Recommendation, InterventionLog.recommendation_id == Recommendation.id)
                .join(Prediction, Recommendation.prediction_id == Prediction.id)
                .filter(Prediction.student_id == selected_student_id)
                .order_by(InterventionLog.id.desc()).all()
            )

    sections = [r[0] for r in db.session.query(Student.section).distinct().order_by(Student.section).all() if r[0]]
    return render_template('interventions.html',
                           at_risk_students=at_risk_students,
                           selected_student=selected_student,
                           selected_student_id=selected_student_id,
                           student_topics=student_topics,
                           student_interventions=student_interventions,
                           student_prediction=student_prediction,
                           sections=sections,
                           status_filter=status_filter,
                           current_section=section_filter,
                           current_risk=risk_filter,
                           search_q=search_q)


@app.route('/intervention/<int:log_id>/update', methods=['POST'])
@staff_required
def update_intervention(log_id):
    log = db.session.get(InterventionLog, log_id)
    if not log:
        flash('Intervention not found.', 'danger')
        return redirect(url_for('interventions'))
    new_status = request.form.get('status', log.status)
    outcome = request.form.get('outcome')
    notes = request.form.get('notes', '')
    if new_status in ('pending', 'in_progress', 'completed', 'ignored'):
        log.status = new_status
    if outcome in ('improved', 'no_change', 'declined'):
        log.outcome = outcome
    if notes:
        log.notes = notes
    log.followed_up_at = date.today().isoformat()
    db.session.commit()
    flash('Intervention updated.', 'success')
    student_id = request.form.get('student_id', 0, type=int)
    if student_id:
        return redirect(url_for('interventions', student_id=student_id))
    return redirect(url_for('interventions'))


@app.route('/intervention/assign', methods=['POST'])
@staff_required
def assign_intervention():
    """Assign Special Quiz or Counseling interventions per topic for a student."""
    student_id = request.form.get('student_id', 0, type=int)
    topic_ids = request.form.getlist('topic_ids')
    intervention_types = request.form.getlist('intervention_types')

    if not student_id or not topic_ids:
        flash('Please select at least one topic.', 'danger')
        return redirect(url_for('interventions', student_id=student_id))

    student = db.session.get(Student, student_id)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('interventions'))

    prediction = Prediction.query.filter_by(
        student_id=student_id
    ).order_by(Prediction.id.desc()).first()
    if not prediction:
        flash('No prediction found for this student. Run predictions first.', 'warning')
        return redirect(url_for('interventions', student_id=student_id))

    count = 0
    assigned_topics = []
    for topic_id, itype in zip(topic_ids, intervention_types):
        if itype not in ('Special Quiz', 'Counseling'):
            continue
        topic = db.session.get(Topic, int(topic_id))
        if not topic:
            continue
        # Create recommendation + intervention log
        rec = Recommendation(
            prediction_id=prediction.id,
            strategy_type=itype,
            message=f'[{topic.subject.name}] Assigned {itype} for topic "{topic.name}" as part of counseling plan.',
            topic_name=topic.name,
        )
        db.session.add(rec)
        db.session.flush()
        log = InterventionLog(recommendation_id=rec.id, status='pending')
        db.session.add(log)
        assigned_topics.append(f'{topic.name} ({itype})')
        count += 1

    # Send notification to the student
    if count:
        student_user = User.query.filter_by(student_id=student_id, role='student').first()
        if student_user:
            notif_title = f'New Intervention Assigned: {student.name}'
            notif_message = (
                f'Your teacher has assigned {count} intervention(s) as part of your counseling plan: '
                f'{", ".join(assigned_topics)}. '
                f'Please check your interventions and prepare accordingly.'
            )
            notif = Notification(
                user_id=student_user.id, student_id=student_id,
                title=notif_title, message=notif_message, type='info',
            )
            db.session.add(notif)

    db.session.commit()
    if count:
        flash(f'Assigned {count} intervention(s) for {student.name}.', 'success')
    else:
        flash('No interventions assigned. Please select topics and types.', 'warning')
    return redirect(url_for('interventions', student_id=student_id))


# ── Notifications ──────────────────────────────────────────────────────────

@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    pagination = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    notifs = pagination.items
    return render_template('notifications.html', notifications=notifs, pagination=pagination)


@app.route('/notification/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(url_for('notifications'))


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))


@app.route('/api/notifications/count')
@login_required
def api_notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


# ── Parent Contact Info ────────────────────────────────────────────────────

@app.route('/parent/contact', methods=['GET', 'POST'])
@login_required
def parent_contact():
    if current_user.role != 'parent':
        abort(403)
    student = db.session.get(Student, current_user.student_id)
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        name = request.form.get('parent_name', '').strip()
        if phone:
            # Basic phone validation
            cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
            if len(cleaned) >= 10:
                student.parent_phone = cleaned
                student.parent_name = name or student.parent_name
                db.session.commit()
                flash('Contact information updated successfully.', 'success')
            else:
                flash('Please enter a valid phone number (at least 10 digits).', 'danger')
        else:
            flash('Phone number is required for SMS notifications.', 'warning')
        return redirect(url_for('parent_contact'))
    return render_template('parent_contact.html', student=student)


# ── Excel Upload / Export ──────────────────────────────────────────────────

@app.route('/class-records/upload', methods=['POST'])
@staff_required
def upload_class_records():
    file = request.files.get('excel_file')
    if not file or not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload a valid Excel file (.xlsx).', 'danger')
        return redirect(url_for('class_records'))

    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active

        # --- Detect format: reference (class record) or simple flat ---
        is_reference_format = False
        subject_name_from_file = None
        term_from_file = None

        # Scan first 15 rows for reference format markers
        header_rows = []
        for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
            header_rows.append([str(c or '').strip() for c in row])

        for i, row in enumerate(header_rows):
            row_text = ' '.join(row).upper()
            if 'CLASS STANDING' in row_text and 'TASK PERFORMANCE' in row_text:
                is_reference_format = True
                break

        if is_reference_format:
            # --- Reference format (class record) ---
            # Find subject from header rows (look for pattern like "CODE: Subject Name")
            for row in header_rows:
                for cell in row:
                    if ':' in cell and len(cell) > 3:
                        # Could be "ENGR1035: IT Elective 2"
                        parts = cell.split(':', 1)
                        if len(parts) == 2 and parts[1].strip():
                            subject_name_from_file = cell.strip()
                            break
                if subject_name_from_file:
                    break

            # Find term from header rows (PRELIM/MIDTERM/FINALS)
            for row in header_rows:
                for cell in row:
                    cell_upper = cell.upper()
                    for t in ['PRELIM', 'MIDTERM', 'FINALS']:
                        if t in cell_upper:
                            term_from_file = t.capitalize()
                            break
                    if term_from_file:
                        break
                if term_from_file:
                    break
            if not term_from_file:
                term_from_file = 'Prelim'

            # Find or create the subject
            subject = None
            if subject_name_from_file:
                subject = Subject.query.filter(Subject.name.ilike(f'%{subject_name_from_file}%')).first()
                if not subject:
                    # Try just the part after the colon
                    short_name = subject_name_from_file.split(':', 1)[-1].strip()
                    subject = Subject.query.filter(Subject.name.ilike(f'%{short_name}%')).first()
                if not subject:
                    subject = Subject(name=subject_name_from_file, description='Imported from Excel')
                    db.session.add(subject)
                    db.session.flush()

            if not subject:
                subject = Subject.query.first()
                if not subject:
                    subject = Subject(name='Imported Subject', description='Auto-created')
                    db.session.add(subject)
                    db.session.flush()

            # Find the category header row with weights and the data start
            # Category row has CLASS STANDING, weights row has 0.2/0.3/0.5
            cat_row_idx = None
            for i, row in enumerate(header_rows):
                row_text = ' '.join(row).upper()
                if 'CLASS STANDING' in row_text:
                    cat_row_idx = i
                    break

            # Find column positions: look for NAME column and equiv columns
            # The data starts 3 rows after category header (cat_row + sub-header + max scores + data)
            data_start_row = cat_row_idx + 4  # 0-indexed, so actual Excel row = data_start_row + 1

            # Find column indices by scanning sub-header and category rows
            # We need: B=NAME, G=CS_EQUIV, P=TP_EQUIV, S=EXAM_EQUIV, U=PRELIM_GRADE
            # But column positions may vary, so find them dynamically
            name_col = 1  # B (0-indexed)

            # Find EQUIV columns: look in sub-header row (cat_row_idx + 1)
            sub_header_row = header_rows[cat_row_idx + 1] if cat_row_idx + 1 < len(header_rows) else []

            # Find all positions where the category row has weights
            cat_row = header_rows[cat_row_idx]
            cs_weight_col = None
            tp_weight_col = None
            exam_weight_col = None

            for ci, cell in enumerate(cat_row):
                val = cell.replace(' ', '')
                if val == '0.2' or val == '0.20':
                    cs_weight_col = ci
                elif val == '0.3' or val == '0.30':
                    tp_weight_col = ci
                elif val == '0.5' or val == '0.50':
                    exam_weight_col = ci

            # The EQUIV column is typically just before the weight column
            cs_equiv_col = (cs_weight_col - 1) if cs_weight_col else 6   # default G
            tp_equiv_col = (tp_weight_col - 1) if tp_weight_col else 15  # default P
            exam_equiv_col = (exam_weight_col - 1) if exam_weight_col else 18  # default S
            exam_raw_col = (exam_equiv_col - 1) if exam_equiv_col else 17  # raw exam SCORE
            grade_col = (exam_weight_col + 1) if exam_weight_col else 20  # default U

            imported = 0
            errors = []
            imported_student_ids = set()
            pre_exam_mode = False
            exam_raw_values = []

            # First pass: check if exam raw scores exist
            for row in ws.iter_rows(min_row=data_start_row + 1, values_only=True):
                row_list = list(row)
                if len(row_list) <= name_col:
                    continue
                student_name = str(row_list[name_col] or '').strip()
                if not student_name or student_name.upper() in ('', 'NAME', 'TOTAL'):
                    continue
                try:
                    row_num_val = row_list[0]
                    if row_num_val is None or str(row_num_val).strip() == '':
                        continue
                    int(float(str(row_num_val)))
                except (ValueError, TypeError):
                    continue
                raw_val = row_list[exam_raw_col] if exam_raw_col < len(row_list) else None
                exam_raw_values.append(raw_val)

            # If all exam raw scores are empty/None, it's pre-exam mode
            if exam_raw_values and all(v is None or str(v).strip() == '' for v in exam_raw_values):
                pre_exam_mode = True

            # Second pass: import data
            for row in ws.iter_rows(min_row=data_start_row + 1, values_only=True):
                try:
                    # Check if this is a data row (has a number in first col and name in second)
                    row_list = list(row)
                    if len(row_list) <= name_col:
                        continue
                    student_name = str(row_list[name_col] or '').strip()
                    if not student_name or student_name.upper() in ('', 'NAME', 'TOTAL'):
                        continue

                    # Try to get the number column — skip non-data rows
                    try:
                        row_num_val = row_list[0]
                        if row_num_val is None or str(row_num_val).strip() == '':
                            continue
                        int(float(str(row_num_val)))
                    except (ValueError, TypeError):
                        continue

                    student = Student.query.filter(Student.name.ilike(student_name)).first()
                    if not student:
                        # Try partial match (last name)
                        last_name = student_name.split(',')[0].strip() if ',' in student_name else student_name.split()[-1]
                        student = Student.query.filter(Student.name.ilike(f'%{last_name}%')).first()
                    if not student:
                        errors.append(f'Student "{student_name}" not found')
                        continue

                    # Read equivalents
                    def safe_float(val, default=0):
                        try:
                            return float(val) if val is not None else default
                        except (ValueError, TypeError):
                            return default

                    cs_equiv = safe_float(row_list[cs_equiv_col] if cs_equiv_col < len(row_list) else None)
                    tp_equiv = safe_float(row_list[tp_equiv_col] if tp_equiv_col < len(row_list) else None)
                    exam_equiv = safe_float(row_list[exam_equiv_col] if exam_equiv_col < len(row_list) else None)
                    final_grade = safe_float(row_list[grade_col] if grade_col < len(row_list) else None)

                    # If final_grade is 0 but we have components, calculate it
                    if final_grade == 0 and (cs_equiv > 0 or tp_equiv > 0 or exam_equiv > 0):
                        final_grade = round(cs_equiv * 0.20 + tp_equiv * 0.30 + exam_equiv * 0.50, 2)

                    # Count attendance from remaining columns (P=present, L=late)
                    att_total = 0
                    att_present = 0
                    if grade_col + 1 < len(row_list):
                        for att_val in row_list[grade_col + 1:]:
                            att_str = str(att_val or '').strip().upper()
                            if att_str in ('P', 'L', ''):
                                if att_str in ('P', 'L'):
                                    att_total += 1
                                    att_present += 1
                                elif att_str == '':
                                    # Could be absent or empty column
                                    pass
                            elif att_str == 'A' or att_str == 'ABSENT':
                                att_total += 1

                    attendance_pct = (att_present / att_total * 100) if att_total > 0 else 100

                    record = ClassRecord(
                        student_id=student.id,
                        subject_id=subject.id,
                        term=term_from_file,
                        class_standing=round(cs_equiv, 2),
                        exam_score=round(exam_equiv, 2),
                        task_performance=round(tp_equiv, 2),
                        attendance=round(attendance_pct, 2),
                        final_grade=round(final_grade, 2),
                    )
                    db.session.add(record)
                    imported += 1
                    imported_student_ids.add(student.id)
                except (ValueError, TypeError, IndexError) as e:
                    errors.append(f'Row error: {str(e)}')

            db.session.commit()
            for sid in imported_student_ids:
                _auto_predict_student(sid)

            msg = f'Imported {imported} records from reference format ({subject.name} – {term_from_file}).'
            if errors:
                msg += f' {len(errors)} error(s): ' + '; '.join(errors[:5])
            flash(msg, 'success' if imported > 0 else 'warning')

            # Pre-exam prediction when exam raw scores are missing
            if pre_exam_mode and imported_student_ids:
                from ml_engine import calculate_pre_exam_prediction
                consultation_needed = []
                prediction_results = []
                for sid in imported_student_ids:
                    student = Student.query.get(sid)
                    record = ClassRecord.query.filter_by(
                        student_id=sid, subject_id=subject.id, term=term_from_file
                    ).first()
                    if not record:
                        continue
                    result = calculate_pre_exam_prediction(record.class_standing, record.task_performance)
                    prediction_results.append({
                        'name': student.name,
                        'exam_needed': result['exam_needed'],
                        'exam_needed_raw': result['exam_needed_raw'],
                        'exam_max_items': result['exam_max_items'],
                        'achievable': result['achievable'],
                        'max_possible': result['max_possible_grade'],
                    })
                    if not result['achievable']:
                        consultation_needed.append(student)
                        # Create consultation notification for student user
                        student_user = User.query.filter_by(student_id=sid).first()
                        if student_user:
                            notif = Notification(
                                user_id=student_user.id,
                                type='warning',
                                message=f'{student.name} cannot achieve passing grade even with a perfect exam score '
                                        f'(max possible: {result["max_possible_grade"]}%). Consultation with instructor is needed.',
                            )
                            db.session.add(notif)
                        # Notify parent too
                        parent_user = User.query.filter_by(role='parent').filter(
                            User.student_id == sid
                        ).first()
                        if parent_user:
                            notif = Notification(
                                user_id=parent_user.id,
                                type='warning',
                                message=f'Your child {student.name} needs instructor consultation. '
                                        f'Max possible grade is {result["max_possible_grade"]}% (below passing).',
                            )
                            db.session.add(notif)

                db.session.commit()

                # Build summary flash
                if prediction_results:
                    lines = ['<strong>Pre-Exam Prediction (no exam scores detected):</strong><br>']
                    prediction_results.sort(key=lambda x: x['exam_needed'], reverse=True)
                    for p in prediction_results:
                        if not p['achievable']:
                            lines.append(f'⚠ {p["name"]}: Cannot pass (max possible {p["max_possible"]:.1f}%) – <strong>consultation needed</strong><br>')
                        elif p['exam_needed'] > 90:
                            lines.append(f'⚡ {p["name"]}: Needs {p["exam_needed_raw"]}/{p["exam_max_items"]} on exam ({p["exam_needed"]:.1f}%) – <strong>critical</strong><br>')
                        else:
                            lines.append(f'✓ {p["name"]}: Needs {p["exam_needed_raw"]}/{p["exam_max_items"]} on exam ({p["exam_needed"]:.1f}%)<br>')
                    if consultation_needed:
                        lines.append(f'<br><strong>{len(consultation_needed)} student(s) need consultation</strong> (notifications sent).')
                    flash(Markup(''.join(lines)), 'info')

        else:
            # --- Simple flat format ---
            headers = [str(c.value or '').strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]
            required = {'student name', 'subject', 'term', 'class standing', 'exam score',
                         'task performance', 'final grade'}
            if not required.issubset(set(headers)):
                flash(f'Missing columns. Required: {", ".join(sorted(required))}. Found: {", ".join(headers)}', 'danger')
                return redirect(url_for('class_records'))

            col = {h: i for i, h in enumerate(headers)}
            imported = 0
            errors = []
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    student_name = str(row[col['student name']] or '').strip()
                    subject_name = str(row[col['subject']] or '').strip()
                    term = str(row[col['term']] or '').strip()
                    if not student_name or not subject_name or not term:
                        continue

                    student = Student.query.filter(Student.name.ilike(student_name)).first()
                    subject_obj = Subject.query.filter(Subject.name.ilike(subject_name)).first()
                    if not student:
                        errors.append(f'Row {row_num}: Student "{student_name}" not found')
                        continue
                    if not subject_obj:
                        errors.append(f'Row {row_num}: Subject "{subject_name}" not found')
                        continue

                    cs = float(row[col['class standing']] or 0)
                    tp = float(row[col['task performance']] or 0)
                    exam = float(row[col['exam score']] or 0)
                    final = float(row[col.get('final grade', 0)] or 0)
                    if final == 0:
                        final = round(cs * 0.20 + tp * 0.30 + exam * 0.50, 2)

                    record = ClassRecord(
                        student_id=student.id,
                        subject_id=subject_obj.id,
                        term=term,
                        class_standing=cs,
                        exam_score=exam,
                        task_performance=tp,
                        attendance=float(row[col.get('attendance', col.get('attendance (%)', 0))] or 100) if col.get('attendance', col.get('attendance (%)')) is not None else 100,
                        final_grade=final,
                    )
                    db.session.add(record)
                    imported += 1
                except (ValueError, TypeError, IndexError) as e:
                    errors.append(f'Row {row_num}: {str(e)}')

            db.session.commit()
            student_ids = db.session.query(ClassRecord.student_id).distinct().all()
            for (sid,) in student_ids:
                _auto_predict_student(sid)

            msg = f'Successfully imported {imported} records.'
            if errors:
                msg += f' {len(errors)} error(s): ' + '; '.join(errors[:5])
                if len(errors) > 5:
                    msg += f'... and {len(errors) - 5} more'
            flash(msg, 'success' if imported > 0 else 'warning')
    except Exception as e:
        flash(f'Error processing Excel file: {str(e)}', 'danger')

    return redirect(url_for('class_records'))


@app.route('/class-records/export')
@login_required
def export_class_records():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Class Records'

    # Styling
    header_font = Font(bold=True, color='FFFFFF', size=10)
    header_fill = PatternFill(start_color='4F46E5', end_color='4F46E5', fill_type='solid')
    cat_fill = PatternFill(start_color='E8E4F0', end_color='E8E4F0', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    bold_font = Font(bold=True, size=10)

    # Row 1: School name
    ws.merge_cells('A1:J1')
    ws['A1'] = 'University Name'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    # Row 2: College
    ws.merge_cells('A2:J2')
    ws['A2'] = 'College of Information Technology'
    ws['A2'].font = Font(bold=True, size=11)
    ws['A2'].alignment = Alignment(horizontal='center')

    # Row 3: blank
    # Row 4: Category headers
    row = 4
    cats = ['NO.', 'NAME', 'CLASS STANDING (20%)', '', '', 'TASK PERFORMANCE (30%)', '', '',
            'EXAMINATION (50%)', '', 'GRADE', 'ATTENDANCE']
    col_widths = [5, 25, 15, 15, 8, 15, 15, 8, 15, 8, 12, 12]
    for ci, (label, w) in enumerate(zip(cats, col_widths), 1):
        cell = ws.cell(row=row, column=ci, value=label)
        cell.font = bold_font
        cell.fill = cat_fill
        cell.alignment = center
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = w

    # Merge category headers
    ws.merge_cells(start_row=4, start_column=3, end_row=4, end_column=5)   # CLASS STANDING
    ws.merge_cells(start_row=4, start_column=6, end_row=4, end_column=8)   # TASK PERFORMANCE
    ws.merge_cells(start_row=4, start_column=9, end_row=4, end_column=10)  # EXAMINATION

    # Row 5: Sub-headers
    sub = ['', '', 'EQUIV', 'WEIGHTED', '0.20', 'EQUIV', 'WEIGHTED', '0.30', 'SCORE', '0.50', '', '%']
    for ci, label in enumerate(sub, 1):
        cell = ws.cell(row=5, column=ci, value=label)
        cell.font = Font(bold=True, size=9)
        cell.alignment = center
        cell.border = thin_border

    # Data query (scoped for students)
    query = (
        db.session.query(ClassRecord, Student, Subject)
        .join(Student, ClassRecord.student_id == Student.id)
        .join(Subject, ClassRecord.subject_id == Subject.id)
    )
    if current_user.role == 'student' and current_user.student_id:
        query = query.filter(ClassRecord.student_id == current_user.student_id)
    elif current_user.role == 'parent' and current_user.student_id:
        query = query.filter(ClassRecord.student_id == current_user.student_id)
    records = query.order_by(Student.name, Subject.name, ClassRecord.id).all()

    for row_idx, (rec, student, subject) in enumerate(records, 6):
        cs_weighted = round(rec.class_standing * 0.20, 2)
        tp_weighted = round(rec.task_performance * 0.30, 2)
        exam_weighted = round(rec.exam_score * 0.50, 2)

        data = [
            row_idx - 5,            # NO.
            student.name,           # NAME
            rec.class_standing,     # CS EQUIV
            cs_weighted,            # CS WEIGHTED
            0.20,                   # weight
            rec.task_performance,   # TP EQUIV
            tp_weighted,            # TP WEIGHTED
            0.30,                   # weight
            rec.exam_score,         # EXAM SCORE
            0.50,                   # weight
            rec.final_grade,        # GRADE
            rec.attendance,         # ATTENDANCE
        ]
        for col_idx, value in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            if col_idx >= 3:
                cell.alignment = Alignment(horizontal='center')
            # Color-code final grade
            if col_idx == 11:
                if value < 75:
                    cell.font = Font(bold=True, color='EF4444')
                elif value < 80:
                    cell.font = Font(bold=True, color='F59E0B')
                else:
                    cell.font = Font(bold=True, color='10B981')

    # Formula note at bottom
    last_row = len(records) + 7
    ws.merge_cells(start_row=last_row, start_column=1, end_row=last_row, end_column=12)
    ws.cell(row=last_row, column=1, value='Grade = Class Standing(20%) + Task Performance(30%) + Examination(50%)').font = Font(italic=True, size=9, color='666666')

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'class_records_{date.today().isoformat()}.xlsx'
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/class-records/template')
@staff_required
def download_template():
    """Download an Excel template for class record uploads."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Class Records Template'
    headers = ['Student Name', 'Subject', 'Term', 'Class Standing', 'Exam Score',
               'Task Performance', 'Attendance', 'Late Submissions', 'Missing Submissions', 'Final Grade']
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4F46E5', end_color='4F46E5', fill_type='solid')
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    # Example row (grade = 85*0.20 + 78*0.30 + 82*0.50 = 17+23.4+41 = 81.4)
    example = ['Juan Dela Cruz', 'Mathematics', 'Prelim', 85.0, 82.0, 78.0, 95.0, 1, 0, 81.4]
    for col_idx, val in enumerate(example, 1):
        ws.cell(row=2, column=col_idx, value=val)
    # Formula note
    ws.cell(row=4, column=1, value='Grade Formula: Class Standing(20%) + Task Performance(30%) + Examination(50%)')
    ws.cell(row=4, column=1).font = Font(italic=True, size=9, color='666666')
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='class_records_template.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ── Attendance Module (5-Meeting System) ───────────────────────────────────

@app.route('/attendance')
@staff_required
def attendance():
    section_filter = request.args.get('section', '')
    term_filter = request.args.get('term', 'Prelim')

    sections = [r[0] for r in db.session.query(Student.section).distinct().order_by(Student.section).all() if r[0]]

    students_list = []
    if section_filter:
        students_list = Student.query.filter_by(section=section_filter).order_by(Student.name).all()

    # Build attendance grid: student_id -> {meeting_number: record}
    attendance_grid = {}
    student_stats = {}
    if section_filter and students_list:
        for s in students_list:
            records = AttendanceRecord.query.filter_by(
                student_id=s.id, term=term_filter
            ).order_by(AttendanceRecord.meeting_number).all()
            meetings = {r.meeting_number: r for r in records}
            attendance_grid[s.id] = meetings
            present = sum(1 for r in records if r.status == 'Present')
            att_grade = _calc_attendance_grade(present)
            att_risk = _attendance_risk_level(att_grade)
            student_stats[s.id] = {
                'present': present, 'absent': len(records) - present,
                'total': len(records), 'grade': att_grade, 'risk': att_risk,
            }

    return render_template('attendance.html',
                           sections=sections,
                           current_section=section_filter,
                           current_term=term_filter,
                           students=students_list,
                           attendance_grid=attendance_grid,
                           student_stats=student_stats)


@app.route('/attendance/save', methods=['POST'])
@staff_required
def save_attendance():
    section = request.form.get('section', '')
    term = request.form.get('term', 'Prelim')
    student_ids = request.form.getlist('student_ids')
    saved = 0

    for sid_str in student_ids:
        sid = int(sid_str)
        for m in range(1, 6):
            status = request.form.get(f'meeting_{sid}_{m}', '')
            if not status:
                continue  # not set yet
            date_val = request.form.get(f'date_{m}', '')
            date_obj = date.fromisoformat(date_val) if date_val else None
            room = request.form.get(f'room_{m}', '')

            existing = AttendanceRecord.query.filter_by(
                student_id=sid, term=term, meeting_number=m
            ).first()
            if existing:
                existing.status = status
                existing.date = date_obj or existing.date
                existing.room = room or existing.room
            else:
                rec = AttendanceRecord(
                    student_id=sid, term=term, meeting_number=m,
                    date=date_obj, status=status, room=room,
                )
                db.session.add(rec)
            saved += 1

    db.session.commit()

    # Sync attendance grade into ClassRecord and re-predict
    for sid_str in student_ids:
        sid = int(sid_str)
        att_grade = _get_attendance_grade(sid, term)
        class_records = ClassRecord.query.filter_by(student_id=sid, term=term).all()
        for cr in class_records:
            cr.attendance = att_grade
        if not class_records:
            for cr in ClassRecord.query.filter_by(student_id=sid).all():
                cr.attendance = att_grade
        db.session.commit()
        _auto_predict_student(sid)

    # Check attendance risk notifications + individual absence alerts
    for sid_str in student_ids:
        sid = int(sid_str)
        _check_attendance_risk_notifications(sid, term)
        # Send per-meeting absence alerts to parents
        for m in range(1, 6):
            status = request.form.get(f'meeting_{sid}_{m}', '')
            if status == 'Absent':
                date_val = request.form.get(f'date_{m}', '')
                _notify_absence(sid, term, m, date_val)

    flash(f'Attendance saved for {len(student_ids)} student(s), {term} term.', 'success')
    return redirect(url_for('attendance', section=section, term=term))


def _check_attendance_risk_notifications(student_id, term='Prelim'):
    """Auto-notify student + parent when attendance grade indicates High Risk."""
    student = db.session.get(Student, student_id)
    if not student:
        return
    att_grade = _get_attendance_grade(student_id, term)
    att_risk = _attendance_risk_level(att_grade)
    if att_risk == 'Low':
        return

    records = AttendanceRecord.query.filter_by(student_id=student_id, term=term).all()
    present = sum(1 for r in records if r.status == 'Present')
    absent = len(records) - present

    title = f'Attendance Alert: {student.name}'
    message = (
        f'{student.name} has {present} present out of {len(records)} meetings ({term}). '
        f'Attendance Grade: {att_grade}. Risk Level: {att_risk}. '
    )
    if att_risk == 'High':
        message += 'Immediate consultation with the instructor is needed.'
    else:
        message += 'Please coordinate with the instructor to improve attendance.'

    student_user = User.query.filter_by(student_id=student_id, role='student').first()
    parent_user = User.query.filter_by(student_id=student_id, role='parent').first()

    for user in [student_user, parent_user]:
        if not user:
            continue
        existing = Notification.query.filter_by(
            user_id=user.id, student_id=student_id, title=title, is_read=False
        ).first()
        if existing:
            continue
        notif = Notification(
            user_id=user.id, student_id=student_id,
            title=title, message=message,
            type='danger' if att_risk == 'High' else 'warning',
        )
        db.session.add(notif)

    db.session.commit()


def _notify_absence(student_id, term, meeting_number, date_str=''):
    """Notify parent when their child is marked absent for a specific meeting."""
    student = db.session.get(Student, student_id)
    if not student:
        return
    parent_user = User.query.filter_by(student_id=student_id, role='parent').first()
    if not parent_user:
        return

    date_display = date_str if date_str else f'Meeting {meeting_number}'
    title = f'Absence Alert: {student.name} – {term} Meeting {meeting_number}'

    # Don't duplicate
    existing = Notification.query.filter_by(
        user_id=parent_user.id, student_id=student_id, title=title
    ).first()
    if existing:
        return

    message = (
        f'Your child {student.name} was marked Absent on {date_display} '
        f'({term}, Meeting {meeting_number}). '
        f'Please monitor their attendance and coordinate with their instructor if needed.'
    )
    notif = Notification(
        user_id=parent_user.id, student_id=student_id,
        title=title, message=message, type='info',
    )
    db.session.add(notif)
    db.session.commit()


@app.route('/api/attendance/stats/<int:student_id>')
@login_required
def api_attendance_stats(student_id):
    term = request.args.get('term', 'Prelim')
    records = AttendanceRecord.query.filter_by(student_id=student_id, term=term).all()
    present = sum(1 for r in records if r.status == 'Present')
    att_grade = _calc_attendance_grade(present)
    att_risk = _attendance_risk_level(att_grade)
    return jsonify({
        'present': present, 'absent': len(records) - present,
        'total': len(records), 'grade': att_grade, 'risk': att_risk,
    })


# ── Parent Attendance Portal ───────────────────────────────────────────────

@app.route('/parent/attendance')
@login_required
def parent_attendance():
    if current_user.role != 'parent' or not current_user.student_id:
        abort(403)
    student = db.session.get(Student, current_user.student_id)
    if not student:
        abort(404)

    term_filter = request.args.get('term', 'Prelim')

    records = AttendanceRecord.query.filter_by(
        student_id=student.id, term=term_filter
    ).order_by(AttendanceRecord.meeting_number).all()

    meetings = []
    for r in records:
        meetings.append({
            'number': r.meeting_number,
            'date': r.date.strftime('%b %d, %Y') if r.date else '—',
            'status': r.status,
        })

    present = sum(1 for r in records if r.status == 'Present')
    absent = len(records) - present
    att_grade = _calc_attendance_grade(present)
    att_risk = _attendance_risk_level(att_grade)

    return render_template('parent_attendance.html',
                           student=student,
                           current_term=term_filter,
                           meetings=meetings,
                           present=present,
                           absent=absent,
                           total=len(records),
                           grade=att_grade,
                           risk=att_risk)


# ── What-If Simulator ──────────────────────────────────────────────────────

@app.route('/what-if')
@login_required
def what_if():
    all_students = Student.query.order_by(Student.name).all()
    return render_template('what_if.html', students=all_students)


@app.route('/api/what-if', methods=['POST'])
@login_required
def api_what_if():
    from ml_engine import simulate_what_if
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result = simulate_what_if(
        db.session,
        class_standing=float(data.get('class_standing', 75)),
        exam_score=float(data.get('exam_score', 75)),
        task_performance=float(data.get('task_performance', 75)),
        attendance=float(data.get('attendance', 90)),
    )
    return jsonify(result)


# ── API Endpoints ──────────────────────────────────────────────────────────

@app.route('/api/student/<int:student_id>/grades')
@login_required
def api_student_grades(student_id):
    if current_user.role == 'student' and current_user.student_id != student_id:
        return jsonify({'error': 'Forbidden'}), 403
    records = (
        ClassRecord.query.filter_by(student_id=student_id)
        .order_by(ClassRecord.subject_id, ClassRecord.id).all()
    )
    subjects = {}
    for r in records:
        subj = db.session.get(Subject, r.subject_id)
        name = subj.name if subj else f'Subject {r.subject_id}'
        subjects.setdefault(name, []).append({
            'term': r.term, 'grade': r.final_grade,
            'class_standing': r.class_standing, 'exam': r.exam_score,
            'task_performance': r.task_performance, 'attendance': r.attendance,
        })
    return jsonify(subjects)


@app.route('/api/dashboard/risk-distribution')
@staff_required
def api_risk_distribution():
    high = Prediction.query.filter_by(risk_level='High').count()
    medium = Prediction.query.filter_by(risk_level='Medium').count()
    low = Prediction.query.filter_by(risk_level='Low').count()
    return jsonify({'High': high, 'Medium': medium, 'Low': low})


@app.route('/api/analytics/subject-risks')
@staff_required
def api_subject_risks():
    rows = (
        db.session.query(Subject.name, Prediction.risk_level, func.count())
        .join(Prediction, Prediction.subject_id == Subject.id)
        .group_by(Subject.name, Prediction.risk_level).all()
    )
    result = {}
    for subj, risk, cnt in rows:
        result.setdefault(subj, {'High': 0, 'Medium': 0, 'Low': 0})[risk] = cnt
    return jsonify(result)


@app.route('/api/analytics/section-comparison')
@staff_required
def api_section_comparison():
    rows = (
        db.session.query(Student.section, func.avg(ClassRecord.final_grade))
        .join(ClassRecord, ClassRecord.student_id == Student.id)
        .group_by(Student.section).all()
    )
    return jsonify({s: round(a, 2) for s, a in rows})


@app.route('/api/analytics/cluster-distribution')
@staff_required
def api_cluster_distribution():
    rows = (
        db.session.query(Prediction.cluster_label, func.count())
        .filter(Prediction.cluster_label.isnot(None))
        .group_by(Prediction.cluster_label).all()
    )
    return jsonify({l: c for l, c in rows})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    @app.errorhandler(403)
    def forbidden(e):
        flash('You do not have permission to access this page.', 'danger')
        if current_user.is_authenticated and current_user.role == 'student' and current_user.student_id:
            return redirect(url_for('student_profile', student_id=current_user.student_id))
        if current_user.is_authenticated and current_user.role == 'parent' and current_user.student_id:
            return redirect(url_for('student_profile', student_id=current_user.student_id))
        return redirect(url_for('login'))

    app.run(debug=True, port=5000)
