"""Seed database with 45 students across BSIT 3E, 3F, 3G sections.
Surname-first name format | 1st Semester | AY 2025-2026."""
import random
from datetime import date
from app import (app, db, User, Student, Subject, ClassRecord,
                 Topic, QuizScore, StudentActivity, Notification,
                 AttendanceRecord)

random.seed(42)

# ── Section data: (surname_first_name, cs_equiv, tp_equiv, exam_equiv, prelim_grade, attendance_pct) ──

SECTION_3E = [
    ('Antolo, Paul Andre',              66,  100, 72, 0,  100),
    ('Arellano, Hero Lloyd',            90,  100, 85, 0,  100),
    ('Batisla-on, John Nico Lawrence',  90,  100, 80, 0,  100),
    ('Carvajal, Rasheed',               86,  100, 78, 0,   80),
    ('Celis, John Michael',             92,  100, 88, 0,  100),
    ('De Asis, Samantha',               98,  100, 92, 0,  100),
    ('Decrepito, Kevin',                98,  100, 90, 0,  100),
    ('Delagao, Reydian',                40,   55, 30, 0,   50),
    ('Depalubos, Omega Jirah',         100,  100, 95, 0,  100),
    ('Edaño, Kyl Remiel',               86,  100, 76, 0,   90),
    ('Estorco, Emmanuel Kay John',      88,  100, 82, 0,  100),
    ('Fetalino, Civrel Marlynette',     88,  100, 84, 0,  100),
    ('Francisco, Shane',                55,   65, 45, 0,   50),
    ('Garbo, Judith',                   68,   70, 55, 0,   75),
    ('Genovia, Bennie',                 60,   70, 58, 0,   70),
]

SECTION_3F = [
    ('Alvarez, Maria Cristina',         78,   92, 75, 0,   90),
    ('Bautista, Carlo Miguel',          94,   98, 88, 0,  100),
    ('Cabaluna, Denise Joy',            62,   85, 60, 0,   70),
    ('Dela Cruz, Jhon Mark',            88,   96, 82, 0,  100),
    ('Espino, Angela Marie',            72,   88, 70, 0,   80),
    ('Flores, Ricky James',             96,  100, 90, 0,  100),
    ('Gonzales, Patricia Ann',          84,   94, 80, 0,   90),
    ('Hernandez, Louie Jay',            58,   78, 48, 0,   60),
    ('Ilagan, Sophia Grace',            92,   96, 86, 0,  100),
    ('Jacinto, Mark Anthony',           76,   90, 72, 0,   80),
    ('Kawasaki, Aira Mae',              98,  100, 94, 0,  100),
    ('Lim, Bryan Keith',                70,   82, 65, 0,   70),
    ('Mendoza, Cherry Ann',             82,   96, 78, 0,   90),
    ('Navarro, Daniel Jose',            90,   94, 84, 0,  100),
    ('Ocampo, Justine Mae',             68,   88, 66, 0,   80),
]

SECTION_3G = [
    ('Padilla, Ken Marcus',             74,   86, 70, 0,   80),
    ('Quiambao, Anna Liza',             96,   98, 90, 0,  100),
    ('Ramos, Christian Jay',            60,   80, 55, 0,   60),
    ('Santos, Marian Grace',            92,   96, 85, 0,  100),
    ('Torres, James Carlo',             80,   92, 76, 0,   90),
    ('Umali, Bianca Marie',             98,  100, 92, 0,  100),
    ('Valdez, Erwin John',              66,   84, 62, 0,   70),
    ('Wong, Michelle Anne',             88,   94, 80, 0,  100),
    ('Ybañez, Carl Angelo',             54,   72, 48, 0,   50),
    ('Zamora, Rica Joy',                94,   98, 88, 0,  100),
    ('Aguilar, Lance Daryl',            82,   90, 78, 0,   90),
    ('Buenaventura, Trisha Mae',        76,   88, 72, 0,   80),
    ('Castillo, Jerico Paul',           70,   82, 64, 0,   70),
    ('Dizon, Althea Nicole',            86,   96, 82, 0,   90),
    ('Enriquez, Ralph Vincent',         90,  100, 86, 0,  100),
]

ALL_SECTIONS = [
    ('BSIT 3E', SECTION_3E),
    ('BSIT 3F', SECTION_3F),
    ('BSIT 3G', SECTION_3G),
]

SUBJECTS_TOPICS = {
    'IT Elective 2': ('Advanced IT topics and emerging technologies',
                      ["Ohm's Law", 'Resistor Color Coding', 'Arduino', 'Wokwi Simulator']),
}

PARENT_FIRST_NAMES = ['Pedro', 'Maria', 'Roberto', 'Elena', 'Manuel', 'Rosa',
                       'Antonio', 'Linda', 'Ricardo', 'Teresa', 'David', 'Gloria',
                       'Miguel', 'Carmen', 'Lucia']


def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Staff users
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)

        teacher = User(username='teacher', role='teacher')
        teacher.set_password('teacher123')
        db.session.add(teacher)

        # Subject & Topics
        subject_objs = []
        topic_map = {}
        for sname, (desc, topic_names) in SUBJECTS_TOPICS.items():
            sub = Subject(name=sname, description=desc)
            db.session.add(sub)
            subject_objs.append(sub)
            db.session.flush()
            topics = []
            for tname in topic_names:
                t = Topic(subject_id=sub.id, name=tname)
                db.session.add(t)
                topics.append(t)
            topic_map[sname] = topics
        db.session.flush()

        # Students across all sections
        all_student_objs = []
        all_student_data = []
        global_idx = 0

        for section_name, section_data in ALL_SECTIONS:
            for idx, (name, cs, tp, exam, grade, att) in enumerate(section_data):
                surname = name.split(',')[0].strip().lower().replace(' ', '').replace('-', '')
                first_part = name.split(',')[1].strip().split()[0].lower() if ',' in name else name.split()[0].lower()
                email = f'{first_part}.{surname}@school.edu'
                parent_first = PARENT_FIRST_NAMES[global_idx % len(PARENT_FIRST_NAMES)]
                parent_last = name.split(',')[0].strip()
                phone = f'+63917{random.randint(1000000, 9999999)}'
                s = Student(
                    name=name, section=section_name, year_level=3,
                    semester='1st Semester', school_year='AY 2025-2026',
                    email=email, is_scholar=(global_idx % 5 == 0),
                    is_working_student=(global_idx % 7 == 0),
                    parent_phone=phone, parent_name=f'{parent_first} {parent_last}',
                )
                db.session.add(s)
                all_student_objs.append(s)
                all_student_data.append((name, cs, tp, exam, grade, att))
                global_idx += 1

        db.session.flush()

        # Class Records – Prelim ONLY (1st Semester only, 2nd Semester has no data yet)
        for s_idx, student in enumerate(all_student_objs):
            name, cs, tp, exam, grade, att = all_student_data[s_idx]
            subject = subject_objs[0]
            final_grade = round(cs * 0.20 + tp * 0.30 + exam * 0.50, 2)

            rec = ClassRecord(
                student_id=student.id, subject_id=subject.id, term='Prelim',
                semester='1st Semester', school_year='AY 2025-2026',
                class_standing=round(cs, 2),
                exam_score=round(exam, 2),
                task_performance=round(tp, 2),
                attendance=round(att, 2),
                final_grade=final_grade,
            )
            db.session.add(rec)

            # Quiz scores for topics
            for topic in topic_map[subject.name]:
                score = max(50, min(100, cs + random.uniform(-10, 10)))
                db.session.add(QuizScore(
                    student_id=student.id, topic_id=topic.id,
                    score=round(score, 2), max_score=100, term='Prelim',
                ))

        db.session.commit()

        # Attendance Records – 5 meetings per term (Prelim)
        # Use attendance_pct to determine present count out of 5
        meeting_dates = [date(2025, 8, 4), date(2025, 8, 11), date(2025, 8, 18),
                         date(2025, 8, 25), date(2025, 9, 1)]
        for s_idx, student in enumerate(all_student_objs):
            att_pct = all_student_data[s_idx][5]  # attendance percentage
            # Map pct to present count: <65->1, 65-74->2, 75-84->3, 85-94->4, 95+->5
            if att_pct >= 95:
                n_present = 5
            elif att_pct >= 85:
                n_present = 4
            elif att_pct >= 75:
                n_present = 3
            elif att_pct >= 65:
                n_present = 2
            else:
                n_present = 1
            # Pick which meetings are absent
            absent_meetings = set(random.sample(range(5), 5 - n_present))
            for m_idx in range(5):
                status = 'Absent' if m_idx in absent_meetings else 'Present'
                db.session.add(AttendanceRecord(
                    student_id=student.id, term='Prelim',
                    meeting_number=m_idx + 1, date=meeting_dates[m_idx],
                    status=status, room='Room 301',
                ))
        db.session.commit()
        print(f'Created attendance records: {len(all_student_objs)} students x 5 meetings (Prelim)')

        print(f'Seeded {len(all_student_objs)} students across 3 sections, 1 subject, '
              f'{len(all_student_objs)} Prelim records (1st Semester only).')
        print('Sections: BSIT 3E (15), BSIT 3F (15), BSIT 3G (15)')
        print('Semesters: 1st Semester, 2nd Semester | School Year: AY 2025-2026')
        print('Users: admin/admin123 | teacher/teacher123')

        # Student user accounts
        for s in all_student_objs:
            surname = s.name.split(',')[0].strip().lower().replace(' ', '')
            username = surname
            existing = User.query.filter_by(username=username).first()
            if existing:
                username = f'{surname}{s.id}'
            u = User(username=username, role='student', student_id=s.id)
            u.set_password('student123')
            db.session.add(u)
        db.session.commit()
        print(f'Created {len(all_student_objs)} student accounts (password: student123)')

        # Parent user accounts
        for s in all_student_objs:
            surname = s.name.split(',')[0].strip().lower().replace(' ', '')
            parent_username = f'parent_{surname}'
            existing = User.query.filter_by(username=parent_username).first()
            if existing:
                parent_username = f'parent_{surname}{s.id}'
            u = User(username=parent_username, role='parent', student_id=s.id)
            u.set_password('parent123')
            db.session.add(u)
        db.session.commit()
        print(f'Created {len(all_student_objs)} parent accounts (password: parent123)')

        # Run ML predictions
        from ml_engine import predict_all
        n = predict_all(db.session)
        print(f'Generated predictions for {n} student-subject pairs.')

        # Generate risk notifications for at-risk students
        from app import _create_risk_notifications, Prediction
        at_risk_students = db.session.query(Prediction.student_id).filter(
            Prediction.risk_level.in_(['High', 'Medium'])
        ).distinct().all()
        for (sid,) in at_risk_students:
            _create_risk_notifications(sid)
        notif_count = Notification.query.count()
        print(f'Generated {notif_count} risk notifications for {len(at_risk_students)} at-risk students.')

        # Show pre-exam predictions
        from ml_engine import calculate_pre_exam_prediction
        print('\n--- Pre-Exam Predictions (min exam needed to pass 75) ---')
        for s_idx, student in enumerate(all_student_objs):
            cs, tp = all_student_data[s_idx][1], all_student_data[s_idx][2]
            result = calculate_pre_exam_prediction(cs, tp)
            status = 'ACHIEVABLE' if result['achievable'] else 'NEEDS CONSULTATION'
            print(f'  {student.name}: needs {result["exam_needed"]}% exam -> {status}')


if __name__ == '__main__':
    seed()
