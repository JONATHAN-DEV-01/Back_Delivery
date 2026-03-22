from app import create_app
from app.models.restaurante import Restaurante
import urllib.request
import json

app = create_app()

with app.app_context():
    rest = Restaurante.query.first()
    if not rest:
        print("NO RESTAURANT IN DB")
    else:
        print("Testing with email:", rest.email)
        url = "http://localhost:5000/auth/restaurant/request-otp"
        data = json.dumps({"email": rest.email}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        try:
            with urllib.request.urlopen(req) as response:
                print("STATUS CODE:", response.status)
                print("TEXT:", response.read().decode('utf-8')[:2000])
        except urllib.error.HTTPError as e:
            print("HTTP FAILED", e.code)
            print("TEXT:", e.read().decode('utf-8')[:2000])
