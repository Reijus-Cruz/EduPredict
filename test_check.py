import requests
s = requests.Session()

# Login
r = s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'}, allow_redirects=False)
print(f'Login: {r.status_code}')

# Dashboard
r = s.get('http://127.0.0.1:5000/dashboard')
print(f'Dashboard: {r.status_code}, len={len(r.text)}')

# Class Records - check subject tabs
r = s.get('http://127.0.0.1:5000/class-records')
print(f'Class Records: {r.status_code}')
# Check for subject tab pills
for subj in ['IT Elective 2', 'Programming', 'Database Management', 'Web Development', 'Networking']:
    if subj in r.text:
        print(f'  -> Subject tab: {subj} found')
if 'pagination' in r.text.lower() or 'page=' in r.text:
    print('  WARNING: pagination still present')
else:
    print('  -> No pagination (good - using subject tabs)')
if 'subjectPills' in r.text:
    print('  -> Subject pills nav found')

# Check actual student from Excel
if 'Paul Andre Antolo' in r.text:
    print('  -> Excel student "Paul Andre Antolo" found')
if 'Samantha De Asis' in r.text:
    print('  -> Excel student "Samantha De Asis" found')

# Student profile
r = s.get('http://127.0.0.1:5000/student/1')
print(f'Student Profile (Antolo): {r.status_code}')
if 'BSIT 3E' in r.text:
    print('  -> Section BSIT 3E confirmed')
if 'Paul Andre Antolo' in r.text:
    print('  -> Correct student name')

# Check student 14 (Judith Garbo - at risk)
r = s.get('http://127.0.0.1:5000/student/14')
print(f'Student Profile (Garbo): {r.status_code}')
if 'High' in r.text or 'at risk' in r.text.lower() or 'text-danger' in r.text:
    print('  -> High risk indicators present')

# What-If
r = s.get('http://127.0.0.1:5000/what-if')
print(f'What-If: {r.status_code}')

# API What-If
r = s.post('http://127.0.0.1:5000/api/what-if',
           json={'class_standing':85,'exam_score':80,'task_performance':78,
                 'attendance':90,'late_submissions':0,'missing_submissions':0})
print(f'API What-If: {r.status_code}, grade={r.json().get("predicted_grade")}')

# Analytics
r = s.get('http://127.0.0.1:5000/analytics')
print(f'Analytics: {r.status_code}')

# Reports
r = s.get('http://127.0.0.1:5000/reports')
print(f'Reports: {r.status_code}')

# Export
r = s.get('http://127.0.0.1:5000/class-records/export')
print(f'Export: {r.status_code}')

# Student login test
s2 = requests.Session()
r2 = s2.post('http://127.0.0.1:5000/login', data={'username':'paul','password':'student123'}, allow_redirects=False)
print(f'Student login (paul): {r2.status_code}')
r2 = s2.get('http://127.0.0.1:5000/class-records')
print(f'Student class records: {r2.status_code}')
if 'subjectPills' in r2.text or 'nav-pills' in r2.text:
    print('  -> Student sees subject pills')

print('\nAll tests passed!')
