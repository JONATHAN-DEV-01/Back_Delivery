import random
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.usuario import Usuario
from app.models.otp_code import OTPCode
from app.services.email_service import EmailService
from app.services.whatsapp_service import WhatsAppService
from app.utils.validators import sanitize_phone, validate_email, validate_phone, validate_cpf

auth_bp = Blueprint('auth', __name__)

def generate_and_send_otp(usuario, metodo):
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

    if metodo == 'email':
        return EmailService.send_otp(usuario.email, usuario.nome or "Usuário", codigo)
    else:
        return WhatsAppService.send_otp(usuario.telefone, usuario.nome or "Usuário", codigo)

@auth_bp.route('/auth/register/start', methods=['POST'])
def register_start():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"error": "Informe o email."}), 400

    email = data['email'].strip().lower()
    if not validate_email(email):
        return jsonify({"error": "Email inválido."}), 400

    usuario = Usuario.query.filter_by(email=email).first()
    
    if usuario:
        if usuario.etapa_registro == 'COMPLETED':
            return jsonify({"error": "Este email já está cadastrado e validado. Faça login."}), 409
        # Se o usuário já existe mas não completou, reenviamos o OTP para continuar
    else:
        usuario = Usuario(email=email, etapa_registro='EMAIL_PENDING')
        db.session.add(usuario)
        db.session.commit()

    if generate_and_send_otp(usuario, 'email'):
        return jsonify({"message": "Código de verificação enviado para o seu email.", "user_id": str(usuario.id)}), 200
    else:
        return jsonify({"error": "Falha ao enviar e-mail de verificação."}), 500

@auth_bp.route('/auth/register/phone', methods=['POST'])
def register_phone():
    data = request.get_json()
    if not data or 'user_id' not in data or 'telefone' not in data:
        return jsonify({"error": "Dados incompletos."}), 400

    usuario = Usuario.query.get(data['user_id'])
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    if usuario.etapa_registro != 'PHONE_PENDING' and usuario.etapa_registro != 'EMAIL_VERIFIED':
        # Permite transição se o email já foi verificado
        pass 

    telefone = data['telefone'].strip()
    if not validate_phone(telefone):
        return jsonify({"error": "Telefone inválido."}), 400
    
    telefone_clean = sanitize_phone(telefone)
    
    # Verifica duplicidade
    existente = Usuario.query.filter_by(telefone=telefone_clean).first()
    if existente and existente.id != usuario.id:
        return jsonify({"error": "Telefone já cadastrado."}), 409

    usuario.telefone = telefone_clean
    usuario.etapa_registro = 'PHONE_PENDING'
    db.session.commit()

    if generate_and_send_otp(usuario, 'telefone'):
        return jsonify({"message": "Código de verificação enviado via WhatsApp."}), 200
    else:
        return jsonify({"error": "Falha ao enviar código via WhatsApp."}), 500

@auth_bp.route('/auth/register/data', methods=['POST'])
def register_data():
    data = request.get_json()
    required = ('user_id', 'nome', 'sobrenome', 'cpf')
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Dados incompletos."}), 400

    usuario = Usuario.query.get(data['user_id'])
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    if usuario.etapa_registro != 'DATA_PENDING':
        return jsonify({"error": "Etapa de registro inválida."}), 400

    nome = data['nome'].strip()
    sobrenome = data['sobrenome'].strip()
    cpf = data['cpf'].strip()

    if not validate_cpf(cpf):
        return jsonify({"error": "CPF inválido."}), 400
    
    cpf_clean = re.sub(r'\D', '', cpf)
    if Usuario.query.filter_by(cpf=cpf_clean).filter(Usuario.id != usuario.id).first():
        return jsonify({"error": "CPF já cadastrado."}), 409

    usuario.nome = nome
    usuario.sobrenome = sobrenome
    usuario.cpf = cpf_clean
    usuario.etapa_registro = 'ADDRESS_PENDING'
    db.session.commit()

    return jsonify({"message": "Dados pessoais salvos com sucesso.", "next_step": "ADDRESS"}), 200

@auth_bp.route('/auth/register/address', methods=['POST'])
def register_address():
    data = request.get_json()
    if not data or 'user_id' not in data or 'endereco' not in data:
        return jsonify({"error": "Dados incompletos."}), 400

    usuario = Usuario.query.get(data['user_id'])
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    if usuario.etapa_registro != 'ADDRESS_PENDING':
        return jsonify({"error": "Etapa de registro inválida."}), 400

    usuario.endereco = data['endereco'].strip()
    usuario.etapa_registro = 'COMPLETED'
    db.session.commit()

    return jsonify({
        "message": "Cadastro finalizado com sucesso!",
        "user": usuario.to_dict()
    }), 200

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

    if not usuario or usuario.etapa_registro != 'COMPLETED':
        return jsonify({"error": "Usuário não encontrado ou cadastro incompleto."}), 404

    if generate_and_send_otp(usuario, metodo):
        return jsonify({"message": f"Código enviado com sucesso via {metodo}."}), 200
    else:
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

    # Sucesso: Invalida o OTP após uso
    db.session.delete(otp)
    
    # Lógica de Transição de Cadastro
    proxima_etapa = None
    if usuario.etapa_registro == 'EMAIL_PENDING':
        usuario.etapa_registro = 'EMAIL_VERIFIED'
        proxima_etapa = 'PHONE'
    elif usuario.etapa_registro == 'PHONE_PENDING':
        usuario.etapa_registro = 'DATA_PENDING'
        proxima_etapa = 'DATA'
    
    db.session.commit()

    return jsonify({
        "message": "Código verificado com sucesso!",
        "proxima_etapa": proxima_etapa,
        "user": usuario.to_dict()
    }), 200
