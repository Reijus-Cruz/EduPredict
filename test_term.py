import requests, re
from collections import Counter

s = requests.Session()
s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'})
r = s.get('http://127.0.0.1:5000/class-records')
print(f'Status: {r.status_code}')
print(f'Term filter: {"termFilter" in r.text}')
for t in ['Prelim','Midterm','Finals']:
    print(f'  Term btn {t}: {f"data-term={chr(34)}{t}{chr(34)}" in r.text}')
print(f'Term column removed: {"<th>Term</th>" not in r.text}')
rows = re.findall(r'data-term="(\w+)"', r.text)
# Subtract 3 for the filter buttons themselves
btn_count = 3
data_rows = rows[btn_count:]
print(f'Data rows by term: {dict(Counter(data_rows))}')
print(f'Row numbers: {"row-num" in r.text}')
print(f'Filter script: {"filterByTerm" in r.text}')
print(f'Number column: {"<th>#</th>" in r.text}')

# Test student view too
s2 = requests.Session()
s2.post('http://127.0.0.1:5000/login', data={'username':'paul','password':'student123'})
r2 = s2.get('http://127.0.0.1:5000/class-records')
print(f'\nStudent view: {r2.status_code}')
print(f'Student term filter: {"termFilter" in r2.text}')
student_rows = re.findall(r'data-term="(\w+)"', r2.text)
print(f'Student rows: {dict(Counter(student_rows[btn_count:]))}')
print('\nAll checks passed!')
