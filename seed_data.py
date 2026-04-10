"""Seed database with students from BSIT 3E, 3F, and 3G sections.
Subject: IT Elective 2 | Only Prelim data (no exam yet).
School Year: AY 2025-2026 | Semester: 1st Semester"""
import random
from app import (app, db, User, Student, Subject, ClassRecord,
                 Topic, QuizScore, StudentActivity, Notification)

random.seed(42)

# Students per section (Surname, First Name format)
# (name, cs_equiv, tp_equiv, exam_equiv, prelim_grade, attendance_pct)

SECTION_3E = [
    ('Antolo, Paul Andre',              66,  100, 50, 68.2,  100),
    ('Arellano, Hero Lloyd',            90,  100, 50, 73.0,  100),
    ('Batisla-on, John Nico Lawrence',  90,  100, 50, 73.0,  100),
    ('Carvajal, Rasheed',               86,  100, 50, 72.2,   80),
    ('Celis, John Michael',             92,  100, 50, 73.4,  100),
    ('De Asis, Samantha',               98,  100, 50, 74.6,  100),
    ('Decrepito, Kevin',                98,  100, 50, 74.6,  100),
    ('Delagao, Reydian',                52,  100, 50, 65.4,   50),
    ('Depalubos, Omega Jirah',         100,  100, 50, 75.0,  100),
    ('Edaño, Kyl Remiel',               86,  100, 50, 72.2,   90),
    ('Estorco, Emmanuel Kay John',      88,  100, 50, 72.6,  100),
    ('Fetalino, Civrel Marlynette',     88,  100, 50, 72.6,  100),
    ('Francisco, Shane',                88,  100, 50, 72.6,   50),
    ('Garbo, Judith',                   50,   50, 50, 50.0,  100),
    ('Genovia, Bennie',                 90,  100, 50, 73.0,  100),
]

SECTION_3F = [
    ('Aguirre, Marc Daniel',            78,  95, 50, 69.1,   90),
    ('Bautista, Rina Mae',              92,  98, 50, 72.8,  100),
    ('Cabaluna, Jethro',                85,  88, 50, 68.4,   80),
    ('Dalisay, Angelica',               74,  90, 50, 66.8,  100),
    ('Enriquez, Rafael',                96,  100, 50, 74.2,  100),
    ('Flores, Maria Cristina',          88,  92, 50, 70.2,   95),
    ('Garcia, John Patrick',            60,  85, 50, 62.5,   70),
    ('Hernandez, Alyssa Joy',           82,  96, 50, 70.2,  100),
    ('Ilagan, Kenneth',                 70,  78, 50, 62.4,   85),
    ('Javier, Trisha Nicole',           94,  100, 50, 73.8,  100),
    ('Lacson, Mark Anthony',            56,  72, 50, 47.8,   60),
    ('Magtibay, Denise',                90,  95, 50, 71.5,  100),
    ('Navarro, Christian James',        84,  88, 50, 70.2,   90),
    ('Ocampo, Bianca',                  76,  82, 50, 64.8,   75),
    ('Padilla, Jerome',                 68,  90, 50, 65.6,  100),
]

SECTION_3G = [
    ('Quinto, Andrea Marie',            82,  94, 50, 69.6,  100),
    ('Reyes, Joshua',                   74,  86, 50, 65.6,   85),
    ('Santos, Kyla Denise',             96,  100, 50, 74.2,  100),
    ('Torres, Miguel Angelo',           58,  78, 50, 60.0,   60),
    ('Uy, Patricia',                    90,  96, 50, 72.8,  100),
    ('Villanueva, Carlo',               80,  88, 50, 68.4,   90),
    ('Wong, Sophia',                    94,  100, 50, 73.8,  100),
    ('Yap, Renzo',                      62,  80, 50, 61.4,   70),
    ('Zamora, Hannah Grace',            88,  92, 50, 70.2,  100),
    ('Almonte, Cedric',                 72,  84, 50, 64.6,   80),
    ('Bueno, Katrina',                  98,  100, 50, 74.6,  100),
    ('Cruz, Daryl',                     66,  76, 50, 60.0,   65),
    ('Dizon, Erica Mae',                86,  94, 50, 71.4,   95),
    ('Espinosa, Francis',               78,  90, 50, 67.6,  100),
    ('Fajardo, Isabella',               84,  96, 50, 70.6,  100),
]

ALL_SECTIONS = [
    ('BSIT 3E', SECTION_3E),
    ('BSIT 3F', SECTION_3F),
    ('BSIT 3G', SECTION_3G),
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

        # Students – all sections, Year 3
        student_objs = []
        all_data = []  # parallel list of tuples
        global_idx = 0
        for section_name, section_data in ALL_SECTIONS:
            for idx, (name, cs, tp, exam, grade, att) in enumerate(section_data):
                # Build email from surname
                surname = name.split(',')[0].strip().lower().replace(' ', '').replace('-', '')
                first = name.split(',')[1].strip().split()[0].lower() if ',' in name else name.split()[0].lower()
                email = f'{first}.{surname}@school.edu'
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
                student_objs.append(s)
                all_data.append((name, cs, tp, exam, grade, att))
                global_idx += 1

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
            name, cs, tp, exam, grade, att = all_data[s_idx]
            subject = subject_objs[0]

            rec = ClassRecord(
                student_id=student.id, subject_id=subject.id, term='Prelim',
                semester='1st Semester', school_year='AY 2025-2026',
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
        total = len(student_objs)
        print(f'Seeded {total} students across 3 sections, 1 subject, '
              f'{total} Prelim records (no exam taken).')
        print('Sections: BSIT 3E (15), BSIT 3F (15), BSIT 3G (15)')
        print('Semester: 1st Semester | School Year: AY 2025-2026')
        print('Users: admin/admin123 | teacher/teacher123')

        # Student user accounts
        for s in student_objs:
            surname = s.name.split(',')[0].strip().lower().replace(' ', '_')
            username = surname
            existing = User.query.filter_by(username=username).first()
            if existing:
                username = f'{surname}{s.id}'
            u = User(username=username, role='student', student_id=s.id)
            u.set_password('student123')
            db.session.add(u)
        db.session.commit()
        print(f'Created {len(student_objs)} student accounts (password: student123)')

        # Parent user accounts
        for s in student_objs:
            surname = s.name.split(',')[0].strip().lower().replace(' ', '_')
            parent_username = f'parent_{surname}'
            existing = User.query.filter_by(username=parent_username).first()
            if existing:
                parent_username = f'parent_{surname}{s.id}'
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
            cs, tp = all_data[s_idx][1], all_data[s_idx][2]
            result = calculate_pre_exam_prediction(cs, tp)
            status = 'ACHIEVABLE' if result['achievable'] else 'NEEDS CONSULTATION'
            print(f'  {student.name}: needs {result["exam_needed"]}% exam → {status}')


if __name__ == '__main__':
    seed()
