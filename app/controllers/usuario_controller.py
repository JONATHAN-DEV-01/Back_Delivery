from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.usuario import Usuario
from app.utils.validators import validate_name, format_name, validate_email, validate_phone, sanitize_phone

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    required_fields = ("nome", "sobrenome", "email", "telefone", "endereco")
    
    if not data or not all(k in data for k in required_fields):
        return jsonify({"error": "Dados incompletos"}), 400

    nome = data['nome'].strip()
    sobrenome = data['sobrenome'].strip()
    email = data['email'].strip().lower()
    telefone = data['telefone'].strip()
    endereco = data['endereco'].strip()

    if not validate_name(nome, 3, 50):
        return jsonify({"error": "Nome inválido. Deve ter entre 3 e 50 caracteres e conter apenas letras."}), 400
        
    if not validate_name(sobrenome, 2, 50):
        return jsonify({"error": "Sobrenome inválido. Deve ter entre 2 e 50 caracteres."}), 400
        
    if not validate_email(email):
        return jsonify({"error": "E-mail com formato inválido ou excedeu 254 caracteres."}), 400

    if not validate_phone(telefone):
        return jsonify({"error": "Telefone inválido. Formato aceito: (11) 99999-9999 e sem +55."}), 400
        
    telefone_clean = sanitize_phone(telefone)

    if Usuario.query.filter_by(email=email).first() or Usuario.query.filter_by(telefone=telefone_clean).first():
        return jsonify({"error": "Email ou Telefone já cadastrado"}), 409

    novo_usuario = Usuario(
        nome=format_name(nome),
        sobrenome=format_name(sobrenome),
        email=email,
        telefone=telefone_clean,
        endereco=endereco
    )

    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify(novo_usuario.to_dict()), 201

@users_bp.route('/users', methods=['GET'])
def get_users():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios]), 200

@users_bp.route('/users/<uuid:user_id>', methods=['GET'])
def get_user(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuário não encontrado"}), 404
    return jsonify(usuario.to_dict()), 200

@users_bp.route('/users/<uuid:user_id>', methods=['PUT'])
def update_user(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuário não encontrado"}), 404

    data = request.get_json()
    
    if 'endereco' in data:
        usuario.endereco = data['endereco'].strip()
        
    if 'telefone' in data:
        telefone = data['telefone'].strip()
        if not validate_phone(telefone):
             return jsonify({"error": "Telefone inválido."}), 400
        novo_tel = sanitize_phone(telefone)
        if Usuario.query.filter_by(telefone=novo_tel).filter(Usuario.id != user_id).first():
            return jsonify({"error": "Telefone já em uso"}), 409
        usuario.telefone = novo_tel
        
    db.session.commit()
    return jsonify(usuario.to_dict()), 200

@users_bp.route('/users/<uuid:user_id>', methods=['DELETE'])
def delete_user(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({"error": "Usuário não encontrado"}), 404

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"message": "Usuário deletado com sucesso"}), 200
