from app import app, db, User
with app.app_context():
    users = User.query.all()
    print(f'Total users: {len(users)}')
    for u in users[:5]:
        print(f'  {u.username} | role={u.role} | hash_len={len(u.password_hash)}')
    
    admin = User.query.filter_by(username='admin').first()
    if admin:
        ok = admin.check_password('admin123')
        print(f'\nadmin check_password("admin123"): {ok}')
        print(f'admin hash: {admin.password_hash[:60]}')
    else:
        print('No admin user found!')
    
    paul = User.query.filter_by(username='paul').first()
    if paul:
        ok = paul.check_password('student123')
        print(f'paul check_password("student123"): {ok}')
    
    # Check for parent users
    parents = User.query.filter_by(role='parent').all()
    print(f'\nParent users: {len(parents)}')
    if parents:
        p = parents[0]
        print(f'  {p.username} | check("parent123"): {p.check_password("parent123")}')
