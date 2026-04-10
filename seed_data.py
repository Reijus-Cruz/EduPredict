"""Seed database with 15 students from FOR TESTING FINAL.xlsx.
Section: BSIT 3E | Subject: IT Elective 2 | Only Prelim data (no exam yet)."""
import random
from app import (app, db, User, Student, Subject, ClassRecord,
                 Topic, QuizScore, StudentActivity, Notification)

random.seed(42)

# 15 students from FOR TESTING FINAL.xlsx (BSIT 3E, IT Elective 2, Prelim)
# Exam = 50 placeholder (no exam taken yet). Grade = CS*0.2 + TP*0.3 + Exam*0.5
# (name, cs_equiv, tp_equiv, exam_equiv, prelim_grade, attendance_pct)
EXCEL_DATA = [
    ('Paul Andre Antolo',              66,  100, 50, 68.2,  100),
    ('Hero Lloyd Arellano',            90,  100, 50, 73.0,  100),
    ('John Nico Lawrence Batisla-on',  90,  100, 50, 73.0,  100),
    ('Rasheed Carvajal',               86,  100, 50, 72.2,   80),
    ('John Michael Celis',             92,  100, 50, 73.4,  100),
    ('Samantha De Asis',               98,  100, 50, 74.6,  100),
    ('Kevin Decrepito',                98,  100, 50, 74.6,  100),
    ('Reydian Delagao',                52,  100, 50, 65.4,   50),
    ('Omega Jirah Depalubos',         100,  100, 50, 75.0,  100),
    ('Kyl Remiel Edaño',               86,  100, 50, 72.2,   90),
    ('Emmanuel Kay John Estorco',      88,  100, 50, 72.6,  100),
    ('Civrel Marlynette Fetalino',     88,  100, 50, 72.6,  100),
    ('Shane Francisco',                88,  100, 50, 72.6,   50),
    ('Judith Garbo',                   50,   50, 50, 50.0,  100),
    ('Bennie Genovia',                 90,  100, 50, 73.0,  100),
]

SUBJECTS_TOPICS = {
    'IT Elective 2': ('Advanced IT topics and emerging technologies',
                      ['Cloud Computing', 'IoT', 'AI/ML Basics', 'Cybersecurity']),
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

        # Students – all BSIT 3E, Year 3
        student_objs = []
        for idx, (name, cs, tp, exam, grade, att) in enumerate(EXCEL_DATA):
            first = name.split()[0].lower()
            last = name.split()[-1].lower().replace('-', '')
            email = f'{first}.{last}@school.edu'
            parent_first = PARENT_FIRST_NAMES[idx % len(PARENT_FIRST_NAMES)]
            parent_last = name.split()[-1]
            phone = f'+63917{random.randint(1000000, 9999999)}'
            s = Student(
                name=name, section='BSIT 3E', year_level=3,
                email=email, is_scholar=(idx % 5 == 0),
                is_working_student=(idx % 7 == 0),
                parent_phone=phone, parent_name=f'{parent_first} {parent_last}',
            )
            db.session.add(s)
            student_objs.append(s)

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

        # Class Records – Prelim ONLY (no exam taken yet, exam_equiv=50 placeholder)
        for s_idx, student in enumerate(student_objs):
            name, cs, tp, exam, grade, att = EXCEL_DATA[s_idx]
            subject = subject_objs[0]

            rec = ClassRecord(
                student_id=student.id, subject_id=subject.id, term='Prelim',
                class_standing=round(cs, 2),
                exam_score=round(exam, 2),
                task_performance=round(tp, 2),
                attendance=round(att, 2),
                final_grade=round(grade, 2),
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
        print(f'Seeded {len(student_objs)} students, 1 subject, '
              f'{len(student_objs)} Prelim records (no exam taken).')
        print('Section: BSIT 3E | Year Level: 3')
        print('Users: admin/admin123 | teacher/teacher123')

        # Student user accounts
        for s in student_objs:
            first_name = s.name.split()[0].lower()
            username = first_name
            existing = User.query.filter_by(username=username).first()
            if existing:
                username = f'{first_name}{s.id}'
            u = User(username=username, role='student', student_id=s.id)
            u.set_password('student123')
            db.session.add(u)
        db.session.commit()
        print(f'Created {len(student_objs)} student accounts (password: student123)')

        # Parent user accounts
        for s in student_objs:
            first_name = s.name.split()[0].lower()
            parent_username = f'parent_{first_name}'
            existing = User.query.filter_by(username=parent_username).first()
            if existing:
                parent_username = f'parent_{first_name}{s.id}'
            u = User(username=parent_username, role='parent', student_id=s.id)
            u.set_password('parent123')
            db.session.add(u)
        db.session.commit()
        print(f'Created {len(student_objs)} parent accounts (password: parent123)')

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
        for s_idx, student in enumerate(student_objs):
            cs, tp = EXCEL_DATA[s_idx][1], EXCEL_DATA[s_idx][2]
            result = calculate_pre_exam_prediction(cs, tp)
            status = 'ACHIEVABLE' if result['achievable'] else 'NEEDS CONSULTATION'
            print(f'  {student.name}: needs {result["exam_needed"]}% exam → {status}')


if __name__ == '__main__':
    seed()
