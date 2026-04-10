import requests

s = requests.Session()
r = s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'}, allow_redirects=True)
print(f'Admin login -> {r.url} (status {r.status_code})')
print(f'  Landed on dashboard: {"dashboard" in r.url}')

s2 = requests.Session()
r2 = s2.post('http://127.0.0.1:5000/login', data={'username':'paul','password':'student123'}, allow_redirects=True)
print(f'Student login -> {r2.url} (status {r2.status_code})')
print(f'  Landed on profile: {"student" in r2.url}')

s3 = requests.Session()
r3 = s3.post('http://127.0.0.1:5000/login', data={'username':'parent_paul','password':'parent123'}, allow_redirects=True)
print(f'Parent login -> {r3.url} (status {r3.status_code})')
print(f'  Landed on profile: {"student" in r3.url}')

# Verify session persists across requests
r4 = s.get('http://127.0.0.1:5000/dashboard')
print(f'\nAdmin session persists: {r4.status_code == 200 and "dashboard" in r4.url}')
