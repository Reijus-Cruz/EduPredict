from app import app, db, Notification, User, Prediction, Student

with app.app_context():
    # Check predictions
    preds = Prediction.query.all()
    high = [p for p in preds if p.risk_level == 'High']
    med = [p for p in preds if p.risk_level == 'Medium']
    print(f'Predictions: {len(preds)} total, {len(high)} High, {len(med)} Medium')
    
    # Check notifications
    notifs = Notification.query.all()
    print(f'Notifications: {len(notifs)}')
    for n in notifs[:5]:
        u = User.query.get(n.user_id)
        print(f'  -> user={u.username}({u.role}) type={n.type} sms={n.sms_sent} title={n.title[:50]}')
    
    # Check parent users exist with student_id
    parents = User.query.filter_by(role='parent').all()
    print(f'\nParent users: {len(parents)}')
    for p in parents[:3]:
        s = Student.query.get(p.student_id)
        print(f'  {p.username} -> student={s.name}, phone={s.parent_phone}')
    
    # Check if at-risk students have notifications for their parents
    if high:
        h = high[0]
        s = Student.query.get(h.student_id)
        parent_user = User.query.filter_by(role='parent', student_id=h.student_id).first()
        parent_notifs = Notification.query.filter_by(user_id=parent_user.id if parent_user else -1).all()
        print(f'\nSample: {s.name} is HIGH risk')
        print(f'  Parent user: {parent_user.username if parent_user else "NONE"}')
        print(f'  Parent notifications: {len(parent_notifs)}')
