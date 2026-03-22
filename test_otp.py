from __future__ import print_function
from app import create_app
from app.extensions import db
from app.models.restaurante import Restaurante
import traceback
from app.controllers.auth_controller import generate_restaurante_otp

app = create_app()

with app.app_context():
    restaurante = Restaurante.query.first()
    if not restaurante:
        print("NAO TEM RESTAURANTE")
    else:
        try:
            print("Tentando gerar OTP...")
            result = generate_restaurante_otp(restaurante)
            print("Sucesso!", result)
        except Exception as e:
            print("!ERRO ENCONTRADO!")
            traceback.print_exc()
