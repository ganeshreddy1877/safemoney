import urllib.request, urllib.parse, json

# Test standard form data
try:
    data = urllib.parse.urlencode({'username': 'admin', 'password': 'adminpassword'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:8000/auth/login', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    res = urllib.request.urlopen(req)
    print("Standard form-urlencoded:", res.status, res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Standard form-urlencoded ERROR:", e.code, e.read().decode('utf-8'))

# Test JSON (expecting 422)
try:
    req = urllib.request.Request('http://127.0.0.1:8000/auth/login', data=json.dumps({'username': 'admin', 'password': 'adminpassword'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    print("JSON body:", res.status, res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("JSON body ERROR:", e.code, e.read().decode('utf-8'))
