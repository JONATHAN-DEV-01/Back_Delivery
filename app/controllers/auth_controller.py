import random
import re
import os
import jwt
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.restaurante import Restaurante
from app.models.otp_code import OTPCode
from app.services.email_service import EmailService
from app.services.whatsapp_service import WhatsAppService
from app.utils.validators import sanitize_phone, validate_email, validate_phone, validate_cpf

auth_bp = Blueprint('auth', __name__)

def generate_jwt(usuario):
    payload = {
        'user_id': str(usuario.id),
        'perfil': usuario.perfil,
        'exp': datetime.utcnow() + timedelta(days=7) # Persistência de sessão (RF05)
    }
    return jwt.encode(payload, os.getenv('JWT_SECRET', 'zupps-secret-key'), algorithm='HS256')

def generate_restaurante_jwt(restaurante):
    payload = {
        'restaurante_id': str(restaurante.id),
        'perfil': 'RESTAURANTE',
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, os.getenv('JWT_SECRET', 'zupps-secret-key'), algorithm='HS256')

def generate_access_link(usuario, token):
    # Simulação de link (RF01)
    base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    return f"{base_url}/auth/verify?token={token}&user_id={usuario.id}"

def generate_and_send_otp(usuario, metodo):
    # Invalida OTPs anteriores deste usuário
    OTPCode.query.filter_by(usuario_id=usuario.id).delete()
    
    # Gera novo código de 6 dígitos (opcional para link, mas mantido para flexibilidade)
    codigo = f"{random.randint(0, 999999):06d}"
    
    # Gera token único para o link (RF01)
    link_token = str(uuid.uuid4())
    
    # RNF 01 - Expiração: 5 min para WhatsApp, 15 min para Email
    minutos_expiracao = 15 if metodo == 'email' else 5
    data_expiracao = datetime.utcnow() + timedelta(minutes=minutos_expiracao)
    
    novo_otp = OTPCode(
        codigo=codigo,
        link_token=link_token,
        data_expiracao=data_expiracao,
        usuario_id=usuario.id
    )
    
    db.session.add(novo_otp)
    db.session.commit()

    link = generate_access_link(usuario, link_token)

    if metodo == 'email':
        return EmailService.send_otp(usuario.email, usuario.nome or "Usuário", codigo, link)
    else:
        # Para WhatsApp, enviamos o código e o link (flexibilidade)
        return WhatsAppService.send_otp(usuario.telefone, usuario.nome or "Usuário", codigo, link)

def generate_restaurante_otp(restaurante):
    OTPCode.query.filter_by(restaurante_id=restaurante.id).delete()
    codigo = f"{random.randint(0, 999999):06d}"
    data_expiracao = datetime.utcnow() + timedelta(minutes=15)
    
    novo_otp = OTPCode(codigo=codigo, data_expiracao=data_expiracao, restaurante_id=restaurante.id)
    db.session.add(novo_otp)
    db.session.commit()

    return EmailService.send_otp(restaurante.email, restaurante.nome_fantasia, codigo, None)

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

    usuario.logradouro = data.get('logradouro', '').strip()
    usuario.bairro = data.get('bairro', '').strip()
    usuario.cidade = data.get('cidade', '').strip()
    usuario.estado = data.get('estado', '').strip()
    usuario.numero = data.get('numero', '').strip()
    usuario.sem_numero = data.get('sem_numero', False)
    usuario.complemento = data.get('complemento', '').strip()
    usuario.ponto_referencia = data.get('ponto_referencia', '').strip()
    
    usuario.etapa_registro = 'COMPLETED'
    db.session.commit()

    return jsonify({
        "message": "Cadastro finalizado com sucesso!",
        "token": generate_jwt(usuario),
        "user": usuario.to_dict()
    }), 200

@auth_bp.route('/auth/resend-link', methods=['POST'])
def resend_link():
    data = request.get_json()
    if not data or ('email' not in data and 'telefone' not in data):
        return jsonify({"error": "Informe o email ou telefone."}), 400

    usuario = None
    metodo = None
    if 'email' in data:
        usuario = Usuario.query.filter_by(email=data['email'].strip().lower()).first()
        metodo = 'email'
    elif 'telefone' in data:
        usuario = Usuario.query.filter_by(telefone=sanitize_phone(data['telefone'].strip())).first()
        metodo = 'telefone'

    if not usuario:
        # Mesma regra de segurança: mensagem genérica
        return jsonify({"message": "Se os dados estiverem corretos, você receberá um novo link em instantes."}), 200

    if generate_and_send_otp(usuario, metodo):
        return jsonify({"message": "Novo link enviado com sucesso."}), 200
    else:
        return jsonify({"error": "Falha ao enviar novo link."}), 500

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

    # Regra de Segurança (Exceção RF01): Se o usuário não existir, mensagem padrão.
    if not usuario or usuario.etapa_registro != 'COMPLETED':
        return jsonify({"message": "Se os dados estiverem corretos, você receberá um link de acesso em instantes"}), 200

    if generate_and_send_otp(usuario, metodo):
        return jsonify({"message": "Se os dados estiverem corretos, você receberá um link de acesso em instantes"}), 200
    else:
        return jsonify({"error": "Falha ao enviar código."}), 500

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

    token = generate_jwt(usuario)

    # Redirecionamento Pós-Login (RF04)
    # O frontend cuidará do redirecionamento baseado no perfil retornado no user
    return jsonify({
        "message": "Código verificado com sucesso!",
        "token": token,
        "proxima_etapa": proxima_etapa,
        "user": usuario.to_dict()
    }), 200

@auth_bp.route('/auth/verify-link/<token>', methods=['GET'])
def verify_link(token):
    # Busca o OTP pelo link_token
    otp = OTPCode.query.filter_by(link_token=token).first()

    if not otp:
        return jsonify({"error": "Link inválido ou já utilizado."}), 400

    if datetime.utcnow() > otp.data_expiracao:
        db.session.delete(otp)
        db.session.commit()
        return jsonify({"error": "Link expirado. Solicite um novo."}), 400

    usuario = Usuario.query.get(otp.usuario_id)
    if not usuario:
        return jsonify({"error": "Usuário não encontrado."}), 404

    # Sucesso: Invalida o OTP após uso
    db.session.delete(otp)
    
    # Atualiza etapa se necessário (ex: login direto)
    if usuario.etapa_registro != 'COMPLETED' and usuario.etapa_registro != 'ADDRESS_PENDING':
        # Se for cadastro, o link pode validar a etapa atual
        if usuario.etapa_registro == 'EMAIL_PENDING':
            usuario.etapa_registro = 'EMAIL_VERIFIED'
        elif usuario.etapa_registro == 'PHONE_PENDING':
            usuario.etapa_registro = 'DATA_PENDING'
    
    db.session.commit()

    # Gera o Token JWT para persistência (RF05)
    jwt_token = generate_jwt(usuario)

    return jsonify({
        "message": "Autenticação via link realizada com sucesso!",
        "token": jwt_token,
        "user": usuario.to_dict()
    }), 200

@auth_bp.route('/auth/validate-token', methods=['POST'])
def validate_token():
    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({"error": "Token não informado."}), 400
    
    try:
        payload = jwt.decode(data['token'], os.getenv('JWT_SECRET', 'zupps-secret-key'), algorithms=['HS256'])
        usuario = Usuario.query.get(payload['user_id'])
        if not usuario:
             return jsonify({"error": "Usuário inválido."}), 401
        
        return jsonify({
            "message": "Token válido.",
            "user": usuario.to_dict()
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido."}), 401

@auth_bp.route('/auth/restaurant/request-otp', methods=['POST'])
def request_restaurant_otp():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({"error": "Informe o email cadastrado do restaurante."}), 400

    email = data['email'].strip().lower()
    restaurante = Restaurante.query.filter_by(email=email).first()

    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado. Verifique o email ou cadastre-se."}), 404

    if generate_restaurante_otp(restaurante):
        return jsonify({"message": "Código enviado para o seu email."}), 200
    else:
        return jsonify({"error": "Falha ao enviar código."}), 500

@auth_bp.route('/auth/restaurant/verify-otp', methods=['POST'])
def verify_restaurant_otp():
    data = request.get_json()
    if not data or 'codigo' not in data or 'email' not in data:
        return jsonify({"error": "Informe o email e o código."}), 400

    email = data['email'].strip().lower()
    codigo_informado = data['codigo'].strip()

    restaurante = Restaurante.query.filter_by(email=email).first()
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404

    otp = OTPCode.query.filter_by(restaurante_id=restaurante.id).order_by(OTPCode.id.desc()).first()
    if not otp:
        return jsonify({"error": "Nenhum código ativo encontrado para este restaurante."}), 400

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
        return jsonify({"error": f"Código incorreto. Você tem mais {4 - otp.tentativas} tentativas."}), 401

    db.session.delete(otp)
    db.session.commit()

    token = generate_restaurante_jwt(restaurante)
    return jsonify({
        "message": "Login de restaurante realizado com sucesso!",
        "token": token,
        "restaurante": restaurante.to_dict()
    }), 200
