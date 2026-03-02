import random
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.usuario import Usuario
from app.models.otp_code import OTPCode
from app.services.email_service import EmailService
from app.services.whatsapp_service import WhatsAppService
from app.utils.validators import sanitize_phone

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/auth/request-otp', methods=['POST'])
def request_otp():
    data = request.get_json()
    
    if not data or ('email' not in data and 'telefone' not in data):
        return jsonify({"error": "Informe o email ou telefone para login."}), 400

    usuario = None
    metodo = None

    if 'email' in data:
        email = data['email'].strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        metodo = 'email'
    elif 'telefone' in data:
        telefone = sanitize_phone(data['telefone'].strip())
        usuario = Usuario.query.filter_by(telefone=telefone).first()
        metodo = 'telefone'

    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    # Invalida OTPs anteriores deste usuário
    OTPCode.query.filter_by(usuario_id=usuario.id).delete()
    
    # Gera novo código de 6 dígitos
    codigo = f"{random.randint(0, 999999):06d}"
    data_expiracao = datetime.utcnow() + timedelta(minutes=5)
    
    novo_otp = OTPCode(
        codigo=codigo,
        data_expiracao=data_expiracao,
        usuario_id=usuario.id
    )
    
    db.session.add(novo_otp)
    db.session.commit()

    sucesso = False
    
    if metodo == 'email':
        sucesso = EmailService.send_otp(usuario.email, usuario.nome, codigo)
    else:
        sucesso = WhatsAppService.send_otp(usuario.telefone, usuario.nome, codigo)

    if sucesso:
        return jsonify({"message": f"Código enviado com sucesso via {metodo}."}), 200
    else:
        # Reverte se o envio falhou
        db.session.delete(novo_otp)
        db.session.commit()
        return jsonify({"error": f"Falha ao enviar código via {metodo}."}), 500

@auth_bp.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    
    if not data or 'codigo' not in data or ('email' not in data and 'telefone' not in data):
        return jsonify({"error": "Informe o código e o email/telefone."}), 400

    codigo_informado = data['codigo'].strip()
    usuario = None

    if 'email' in data:
        email = data['email'].strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
    elif 'telefone' in data:
        telefone = sanitize_phone(data['telefone'].strip())
        usuario = Usuario.query.filter_by(telefone=telefone).first()

    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    # Busca o último OTP
    otp = OTPCode.query.filter_by(usuario_id=usuario.id).order_by(OTPCode.id.desc()).first()

    if not otp:
        return jsonify({"error": "Nenhum código ativo encontrado para este usuário."}), 400

    if datetime.utcnow() > otp.data_expiracao:
        db.session.delete(otp)
        db.session.commit()
        return jsonify({"error": "Código expirado. Solicite um novo."}), 400

    if otp.codigo != codigo_informado:
        otp.tentativas += 1
        db.session.commit()
        
        if otp.tentativas >= 4:
            db.session.delete(otp)
            db.session.commit()
            return jsonify({"error": "Limite máximo de tentativas excedido. Solicite um novo código."}), 403
            
        tentativas_restantes = 4 - otp.tentativas
        return jsonify({"error": f"Código incorreto. Você tem mais {tentativas_restantes} tentativas."}), 401

    # Sucesso: Invalida o OTP após uso (opcionalmente retornaria JWT aqui)
    db.session.delete(otp)
    db.session.commit()

    return jsonify({
        "message": "Login realizado com sucesso!",
        "user": usuario.to_dict()
    }), 200
