"""
Enhanced ML Engine – Student Performance Prediction
- Random Forest with feature importance
- K-Means clustering into behavior profiles
- Per-subject grade trend with weighted recency
- Topic-specific recommendations
- What-if simulator
"""

import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


FEATURE_NAMES = ['class_standing', 'exam_score', 'task_performance', 'attendance',
                 'grade_trend']

CLUSTER_NAMES = {
    0: 'Consistent Performer',
    1: 'Declining Performer',
    2: 'Improving Performer',
    3: 'Chronic Low Performer',
    4: 'Disengaged Learner',
}


def _label(grade):
    if grade < 75:
        return 'High'
    if grade < 80:
        return 'Medium'
    return 'Low'


def _compute_trend(records):
    if len(records) < 2:
        return 0.0
    grades = [r.final_grade for r in records]
    return float(np.polyfit(range(len(grades)), grades, 1)[0])


def _build_features_single(record, trend, weight=1.0):
    return [
        record.class_standing * weight,
        record.exam_score * weight,
        record.task_performance * weight,
        record.attendance * weight,
        trend,
    ]


def _build_features_all(session):
    from app import ClassRecord
    all_records = session.query(ClassRecord).all()
    if not all_records:
        return np.array([]), np.array([]), all_records

    grouped = {}
    for r in all_records:
        key = (r.student_id, r.subject_id)
        grouped.setdefault(key, []).append(r)

    X, y = [], []
    for key, recs in grouped.items():
        recs.sort(key=lambda r: r.id)
        trend = _compute_trend(recs)
        weights = [0.5] * max(0, len(recs) - 2) + ([0.7] if len(recs) > 1 else []) + [1.0]
        for r, w in zip(recs, weights):
            X.append(_build_features_single(r, trend, w))
            y.append(_label(r.final_grade))

    return np.array(X), np.array(y), all_records


def _assign_clusters(X):
    if len(X) < 5:
        return ['Consistent Performer'] * len(X)
    n_clusters = min(5, len(X))
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    return [CLUSTER_NAMES.get(l, f'Cluster {l}') for l in labels]


def _get_weak_topics(session, student_id, subject_id):
    from app import QuizScore, Topic
    results = (
        session.query(Topic.name, (QuizScore.score / QuizScore.max_score * 100))
        .join(QuizScore, QuizScore.topic_id == Topic.id)
        .filter(QuizScore.student_id == student_id, Topic.subject_id == subject_id)
        .all()
    )
    topic_scores = {}
    for name, pct in results:
        topic_scores.setdefault(name, []).append(pct)
    weak = []
    for name, scores in topic_scores.items():
        avg = sum(scores) / len(scores)
        if avg < 75:
            weak.append((name, round(avg, 1)))
    return weak


def _generate_recommendations(session, student_id, subject_id, risk_level,
                               class_standing, exam, task_performance, attendance,
                               trend, cluster):
    from app import Subject, AttendanceRecord, _calc_attendance_grade
    subject = session.get(Subject, subject_id)
    subj_name = subject.name if subject else 'this subject'
    recs = []

    # Use AttendanceRecord for actual attendance data (5-meeting system)
    att_records = session.query(AttendanceRecord).filter_by(student_id=student_id).all()
    att_present = sum(1 for r in att_records if r.status == 'Present')
    att_grade = _calc_attendance_grade(att_present)

    weak = _get_weak_topics(session, student_id, subject_id)
    for topic_name, avg_pct in weak:
        recs.append(('Special Quiz',
                      f'[{subj_name}] Weak in "{topic_name}" (avg {avg_pct}%%). Assign a special quiz and targeted review exercises for this topic.',
                      topic_name))

    if att_grade <= 80:
        recs.append(('Counseling',
                      f'[{subj_name}] Attendance grade is low ({att_grade}, {att_present}/5 meetings present). Schedule attendance counseling and notify parent/guardian immediately.',
                      None))

    if class_standing < 75:
        recs.append(('Special Quiz',
                      f'[{subj_name}] Class Standing is below passing ({class_standing:.1f}). Assign a special quiz and review drills specifically for {subj_name}.',
                      None))

    if exam < 75:
        recs.append(('Special Quiz',
                      f'[{subj_name}] Exam score below passing ({exam:.1f}). Schedule a special remedial quiz or exam preparation session for {subj_name}.',
                      None))

    if task_performance < 75:
        recs.append(('Special Quiz',
                      f'[{subj_name}] Task Performance is low ({task_performance:.1f}). Provide a special quiz and guided practice exercises for {subj_name}.',
                      None))

    if trend < -2:
        recs.append(('Counseling',
                      f'[{subj_name}] Grade trend is declining sharply (slope: {trend:.1f}). Immediate academic counseling and intervention plan needed for {subj_name}.',
                      None))

    if cluster == 'Disengaged Learner' and not any(r[0] == 'Counseling' for r in recs):
        recs.append(('Counseling',
                      f'[{subj_name}] Student shows disengagement patterns. Consider motivational counseling and interest-based {subj_name} activities.',
                      None))

    if cluster == 'Declining Performer' and trend < 0:
        recs.append(('Counseling',
                      f'[{subj_name}] Student was performing well but is declining. Schedule counseling to address the decline in {subj_name}.',
                      None))

    # Pre-exam: minimum exam grade recommendation for at-risk students
    if risk_level in ('High', 'Medium'):
        pre_exam = calculate_pre_exam_prediction(class_standing, task_performance)
        if not pre_exam['achievable']:
            recs.append(('Special Quiz',
                          f'[{subj_name}] Even a perfect exam score (100) would only yield {pre_exam["max_possible_grade"]:.1f}. '
                          f'Schedule special quizzes, make-up work, and additional assessments to recover grades.',
                          None))
        elif pre_exam['exam_needed'] > 90:
            recs.append(('Counseling',
                          f'[{subj_name}] Needs at least {pre_exam["exam_needed"]:.1f} on the exam to pass. '
                          f'Schedule counseling/consultation and take practice exams.',
                          None))
        elif pre_exam['exam_needed'] > 75:
            recs.append(('Special Quiz',
                          f'[{subj_name}] Needs at least {pre_exam["exam_needed"]:.1f} on the exam to pass. '
                          f'Take a special review quiz and attend consultation sessions.',
                          None))

    if risk_level == 'High' and not recs:
        recs.append(('Counseling',
                      f'[{subj_name}] Overall performance is critically low. Recommend immediate academic counseling and a comprehensive intervention plan for {subj_name}.',
                      None))

    if risk_level == 'Medium' and not recs:
        recs.append(('Counseling',
                      f'[{subj_name}] Performance is borderline. Schedule counseling and regular progress check-ins for {subj_name}.',
                      None))

    return recs


def _run_prediction(session, model, feature_importances, pairs_data, use_ml):
    from app import Prediction, Recommendation, InterventionLog

    all_features = [d['features'] for d in pairs_data]
    if all_features:
        clusters = _assign_clusters(np.array(all_features))
    else:
        clusters = []

    count = 0
    for i, d in enumerate(pairs_data):
        student_id = d['student_id']
        subject_id = d['subject_id']
        latest = d['latest']
        feat = np.array([d['features']])
        trend = d['trend']
        cluster = clusters[i] if i < len(clusters) else 'Consistent Performer'

        if use_ml:
            risk_level = model.predict(feat)[0]
            probas = model.predict_proba(feat)[0]
            confidence = float(max(probas))
        else:
            risk_level = _label(latest.final_grade)
            confidence = 0.85

        predicted_grade = (
            latest.class_standing * 0.20 + latest.exam_score * 0.50 +
            latest.task_performance * 0.30
        )
        predicted_grade += trend
        predicted_grade = max(0, min(100, predicted_grade))

        # Multi-factor risk classification
        # Uses: attendance grade (5-meeting system), class standing (quiz),
        #       task performance (lab), exam score, and pre-exam achievability
        from app import AttendanceRecord, _calc_attendance_grade, _attendance_risk_level
        att_records = session.query(AttendanceRecord).filter_by(student_id=student_id).all()
        att_present = sum(1 for r in att_records if r.status == 'Present')
        att_grade = _calc_attendance_grade(att_present)
        att_risk = _attendance_risk_level(att_grade)

        pre_exam = calculate_pre_exam_prediction(latest.class_standing, latest.task_performance)
        max_possible = pre_exam['max_possible_grade']
        exam_needed = pre_exam['exam_needed']

        # High Risk: any critical factor
        #   - Attendance grade <= 60 (0-1 present out of 5 meetings)
        #   - Class Standing (quiz) < 65 (consistently low)
        #   - Task Performance (lab) < 65 (incomplete labs)
        #   - Exam score < 60 (very low exam)
        #   - Max possible grade < 75 (can't pass even with perfect exam)
        high_flags = []
        if att_grade <= 60:
            high_flags.append(f'attendance_grade={att_grade} ({att_present}/5 present)')
        if latest.class_standing < 65:
            high_flags.append(f'quiz={latest.class_standing:.0f}')
        if latest.task_performance < 65:
            high_flags.append(f'lab={latest.task_performance:.0f}')
        if latest.exam_score < 60:
            high_flags.append(f'exam={latest.exam_score:.0f}')
        if max_possible < 75:
            high_flags.append(f'max_possible={max_possible:.1f}')

        # Medium Risk: borderline factors
        #   - Attendance grade 70-80 (2-3 present out of 5 meetings)
        #   - Class Standing 65-74 (average quiz)
        #   - Task Performance 65-74 (some incomplete labs)
        #   - Exam score 60-74 (borderline exam)
        #   - Needs exam > 85 to pass
        medium_flags = []
        if 70 <= att_grade <= 80:
            medium_flags.append(f'attendance_grade={att_grade} ({att_present}/5 present)')
        if 65 <= latest.class_standing < 75:
            medium_flags.append(f'quiz={latest.class_standing:.0f}')
        if 65 <= latest.task_performance < 75:
            medium_flags.append(f'lab={latest.task_performance:.0f}')
        if 60 <= latest.exam_score < 75:
            medium_flags.append(f'exam={latest.exam_score:.0f}')
        if exam_needed > 85 and max_possible >= 75:
            medium_flags.append(f'exam_needed={exam_needed:.0f}%')

        if high_flags:
            risk_level = 'High'
        elif medium_flags:
            risk_level = 'Medium'
        else:
            risk_level = 'Low'

        fi_dict = {}
        if feature_importances is not None:
            for name, imp in zip(FEATURE_NAMES, feature_importances):
                fi_dict[name] = round(float(imp), 4)
        # Store pre-exam and risk factor data
        fi_dict['max_possible_grade'] = round(max_possible, 2)
        fi_dict['exam_needed'] = round(max(0, exam_needed), 2)
        fi_dict['exam_needed_raw'] = pre_exam['exam_needed_raw']
        fi_dict['exam_max_items'] = pre_exam['exam_max_items']
        fi_dict['attendance_pct'] = round(att_grade, 1)
        fi_dict['high_risk_flags'] = high_flags
        fi_dict['medium_risk_flags'] = medium_flags

        old = session.query(Prediction).filter_by(
            student_id=student_id, subject_id=subject_id
        ).all()
        for o in old:
            for rec in o.recommendations:
                session.query(InterventionLog).filter_by(recommendation_id=rec.id).delete()
            session.query(Recommendation).filter_by(prediction_id=o.id).delete()
            session.delete(o)

        pred = Prediction(
            student_id=student_id, subject_id=subject_id,
            risk_level=risk_level,
            predicted_grade=round(predicted_grade, 2),
            confidence=round(confidence, 2),
            feature_importance=json.dumps(fi_dict) if fi_dict else None,
            cluster_label=cluster,
        )
        session.add(pred)
        session.flush()

        recs = _generate_recommendations(
            session, student_id, subject_id, risk_level,
            latest.class_standing, latest.exam_score, latest.task_performance,
            latest.attendance,
            trend, cluster,
        )
        for strategy, message, topic_name in recs:
            rec = Recommendation(
                prediction_id=pred.id, message=message,
                strategy_type=strategy, topic_name=topic_name,
            )
            session.add(rec)
            session.flush()
            session.add(InterventionLog(recommendation_id=rec.id, status='pending'))

        count += 1

    session.commit()
    return count


def predict_all(session):
    from app import ClassRecord

    X_all, y_all, all_records = _build_features_all(session)
    if len(X_all) == 0:
        return 0

    use_ml = len(X_all) >= 10 and len(set(y_all)) >= 2
    model, feature_importances = None, None

    if use_ml:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_all, y_all)
        feature_importances = model.feature_importances_

    pairs = session.query(ClassRecord.student_id, ClassRecord.subject_id).distinct().all()
    pairs_data = []
    for student_id, subject_id in pairs:
        records = (
            session.query(ClassRecord)
            .filter_by(student_id=student_id, subject_id=subject_id)
            .order_by(ClassRecord.id).all()
        )
        if not records:
            continue
        latest = records[-1]
        trend = _compute_trend(records)
        features = _build_features_single(latest, trend)
        pairs_data.append({
            'student_id': student_id, 'subject_id': subject_id,
            'latest': latest, 'trend': trend, 'features': features,
        })

    return _run_prediction(session, model, feature_importances, pairs_data, use_ml)


def predict_for_student(session, student_id):
    from app import ClassRecord

    X_all, y_all, _ = _build_features_all(session)
    use_ml = len(X_all) >= 10 and len(set(y_all)) >= 2
    model, feature_importances = None, None

    if use_ml:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_all, y_all)
        feature_importances = model.feature_importances_

    subject_ids = [
        r[0] for r in
        session.query(ClassRecord.subject_id)
        .filter_by(student_id=student_id).distinct().all()
    ]

    pairs_data = []
    for subject_id in subject_ids:
        records = (
            session.query(ClassRecord)
            .filter_by(student_id=student_id, subject_id=subject_id)
            .order_by(ClassRecord.id).all()
        )
        if not records:
            continue
        latest = records[-1]
        trend = _compute_trend(records)
        features = _build_features_single(latest, trend)
        pairs_data.append({
            'student_id': student_id, 'subject_id': subject_id,
            'latest': latest, 'trend': trend, 'features': features,
        })

    return _run_prediction(session, model, feature_importances, pairs_data, use_ml)


def calculate_pre_exam_prediction(class_standing, task_performance, passing_grade=75, exam_max_items=50):
    """Calculate minimum exam score needed to pass.
    Grade formula: final = class_standing*0.20 + task_performance*0.30 + exam*0.50
    Transmutation: EQUIV = 50 + (RAW / MAX) * 50
    """
    current_contribution = class_standing * 0.20 + task_performance * 0.30
    exam_needed = (passing_grade - current_contribution) / 0.50
    max_possible = current_contribution + 100 * 0.50

    # Convert equiv % to raw score: RAW = (EQUIV - 50) / 50 * MAX_ITEMS
    import math
    raw_needed = max(0, (exam_needed - 50) / 50 * exam_max_items)
    raw_needed_ceil = math.ceil(raw_needed)  # round up since you can't get half an item

    return {
        'exam_needed': round(max(0, exam_needed), 2),
        'exam_needed_raw': min(raw_needed_ceil, exam_max_items),
        'exam_max_items': exam_max_items,
        'achievable': exam_needed <= 100,
        'current_contribution': round(current_contribution, 2),
        'max_possible_grade': round(max_possible, 2),
    }


def simulate_what_if(session, class_standing, exam_score, task_performance,
                     attendance):
    """attendance param = attendance grade (50-100, from 5-meeting system)."""
    X_all, y_all, _ = _build_features_all(session)
    use_ml = len(X_all) >= 10 and len(set(y_all)) >= 2

    trend = 0
    feat = np.array([[class_standing, exam_score, task_performance, attendance,
                      trend]])

    if use_ml:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_all, y_all)
        risk_level = model.predict(feat)[0]
        probas = model.predict_proba(feat)[0]
        confidence = float(max(probas))
        fi = {name: round(float(imp), 4) for name, imp in zip(FEATURE_NAMES, model.feature_importances_)}
    else:
        predicted = class_standing * 0.20 + task_performance * 0.30 + exam_score * 0.50
        risk_level = _label(predicted)
        confidence = 0.85
        fi = {}

    # Override risk with multi-factor logic
    from app import _attendance_risk_level
    att_risk = _attendance_risk_level(attendance)

    pre_exam = calculate_pre_exam_prediction(class_standing, task_performance)

    high_flags = []
    if att_risk == 'High':
        high_flags.append(f'attendance_grade={attendance}')
    if class_standing < 65:
        high_flags.append(f'quiz={class_standing:.0f}')
    if task_performance < 65:
        high_flags.append(f'lab={task_performance:.0f}')
    if exam_score < 60:
        high_flags.append(f'exam={exam_score:.0f}')
    if pre_exam['max_possible_grade'] < 75:
        high_flags.append(f'max_possible={pre_exam["max_possible_grade"]:.1f}')

    medium_flags = []
    if att_risk == 'Medium':
        medium_flags.append(f'attendance_grade={attendance}')
    if 65 <= class_standing < 75:
        medium_flags.append(f'quiz={class_standing:.0f}')
    if 65 <= task_performance < 75:
        medium_flags.append(f'lab={task_performance:.0f}')
    if 60 <= exam_score < 75:
        medium_flags.append(f'exam={exam_score:.0f}')

    if high_flags:
        risk_level = 'High'
    elif medium_flags:
        risk_level = 'Medium'
    else:
        risk_level = 'Low'

    predicted_grade = class_standing * 0.20 + task_performance * 0.30 + exam_score * 0.50
    predicted_grade = max(0, min(100, round(predicted_grade, 2)))

    tips = []
    if attendance <= 80:
        present = max(0, (attendance - 50) // 10)
        tips.append(f'Attendance grade is {attendance} ({int(present)}/5 meetings). Attending more meetings improves risk level.')
    if class_standing < 75:
        tips.append('Raising Class Standing above 75 through quizzes would contribute to passing (20% weight).')
    if exam_score < 75:
        tips.append('Improving exam scores through tutoring would have the highest impact (50% weight).')
    if task_performance < 75:
        tips.append('Improving Task Performance through labs and activities would boost the grade (30% weight).')

    return {
        'risk_level': risk_level,
        'predicted_grade': predicted_grade,
        'confidence': round(confidence, 2),
        'feature_importance': fi,
        'tips': tips,
    }
