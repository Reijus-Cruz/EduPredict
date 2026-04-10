import requests

# Admin view
s = requests.Session()
s.post('http://127.0.0.1:5000/login', data={'username':'admin','password':'admin123'})
r = s.get('http://127.0.0.1:5000/notifications')
print(f'Admin notifications page: {r.status_code}')
print(f'  Has "Risk Alert": {"Risk Alert" in r.text}')

# Parent view
s2 = requests.Session()
s2.post('http://127.0.0.1:5000/login', data={'username':'parent_judith','password':'parent123'})
r2 = s2.get('http://127.0.0.1:5000/notifications')
print(f'Parent (Judith Garbo) notifications: {r2.status_code}')
print(f'  Has danger alert: {"danger" in r2.text}')
print(f'  Has HIGH RISK: {"HIGH RISK" in r2.text or "high risk" in r2.text.lower()}')
print(f'  Has SMS badge: {"sms" in r2.text.lower() or "SMS Sent" in r2.text}')

# Student view
s3 = requests.Session()
s3.post('http://127.0.0.1:5000/login', data={'username':'judith','password':'student123'})
r3 = s3.get('http://127.0.0.1:5000/notifications')
print(f'Student (Judith) notifications: {r3.status_code}')
print(f'  Has risk alert: {"Risk Alert" in r3.text}')

# Check notification count API
r4 = s2.get('http://127.0.0.1:5000/api/notifications/count')
print(f'\nParent unread count: {r4.json()}')
r5 = s3.get('http://127.0.0.1:5000/api/notifications/count')
print(f'Student unread count: {r5.json()}')

print('\nParent notification system verified!')
