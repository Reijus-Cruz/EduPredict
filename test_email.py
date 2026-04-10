import requests
s = requests.Session()
s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'})

# Check email changed
r = s.get('http://127.0.0.1:5000/students')
assert '@school.edu' in r.text, 'school.edu email not found'
assert '@sti.edu.ph' not in r.text, 'sti.edu.ph still present!'
print('Emails: @school.edu OK')

# Check class records page
r = s.get('http://127.0.0.1:5000/class-records')
assert 'STI' not in r.text, 'STI reference still in class records'
print('Class records: no STI references')

# Check export
r = s.get('http://127.0.0.1:5000/class-records/export')
assert r.status_code == 200
print(f'Export: {r.status_code} OK')

# Check term filter still works
assert 'termFilter' in s.get('http://127.0.0.1:5000/class-records').text
print('Term filter: present')

print('\nAll OK!')
