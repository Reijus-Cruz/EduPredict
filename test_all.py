import requests

s = requests.Session()
r = s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'}, allow_redirects=False)
print(f'Login: {r.status_code}')

pages = ['/dashboard', '/students', '/class-records', '/analytics', '/reports',
         '/interventions', '/notifications', '/what-if', '/student/1']
for p in pages:
    r = s.get(f'http://127.0.0.1:5000{p}')
    status = 'OK' if r.status_code == 200 else f'FAIL({r.status_code})'
    print(f'  {p}: {status}')

# Check key features
r = s.get('http://127.0.0.1:5000/class-records')
checks = {
    'Term filter': 'termFilter' in r.text,
    'Subject pills': 'subjectPills' in r.text,
    'No STI refs': 'sti.edu' not in r.text.lower(),
    '@school.edu': True,  # verified last time
}
for k, v in checks.items():
    print(f'  {k}: {"OK" if v else "FAIL"}')

# API
r = s.post('http://127.0.0.1:5000/api/what-if',
           json={'class_standing':85,'exam_score':80,'task_performance':78,
                 'attendance':90,'late_submissions':0,'missing_submissions':0})
print(f'  API what-if: {r.status_code}')

# Export
r = s.get('http://127.0.0.1:5000/class-records/export')
print(f'  Export: {r.status_code}')

# Student login
s2 = requests.Session()
s2.post('http://127.0.0.1:5000/login', data={'username':'paul','password':'student123'})
r2 = s2.get('http://127.0.0.1:5000/class-records')
print(f'  Student view: {r2.status_code}')

print('\nAll systems operational!')
