import urllib.request
import json
from app import create_app
from app.models.restaurante import Restaurante
from app.models.otp_code import OTPCode

app = create_app()

with app.app_context():
    rest = Restaurante.query.first()
    if not rest:
        print("NO RESTAURANT IN DB")
    else:
        # Pega o ultimo OTP gerado agorinha
        otp = OTPCode.query.filter_by(restaurante_id=rest.id).order_by(OTPCode.id.desc()).first()
        if not otp:
            print("NO OTP IN DB")
        else:
            print("Testing verify-otp with email:", rest.email, "code:", otp.codigo)
            url = "http://localhost:5000/auth/restaurant/verify-otp"
            data = json.dumps({"email": rest.email, "codigo": otp.codigo}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

            try:
                with urllib.request.urlopen(req) as response:
                    print("STATUS CODE:", response.status)
                    print("TEXT:", response.read().decode('utf-8')[:2000])
            except urllib.error.HTTPError as e:
                print("HTTP FAILED", e.code)
                print("TEXT:", e.read().decode('utf-8')[:2000])
