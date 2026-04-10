import requests
s = requests.Session()
s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'})

r = s.get('http://127.0.0.1:5000/class-records')
print(f'Class Records: {r.status_code}')
print(f'  IT Elective 2: {"IT Elective 2" in r.text}')
for old in ['Programming', 'Database Management', 'Web Development', 'Networking']:
    if old in r.text:
        print(f'  WARNING: {old} still present!')
    else:
        print(f'  {old} removed: OK')

r2 = s.get('http://127.0.0.1:5000/dashboard')
print(f'Dashboard: {r2.status_code}')

r3 = s.get('http://127.0.0.1:5000/student/1')
print(f'Student Profile: {r3.status_code}')

print('\nDone!')
