from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.usuario import Usuario

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or not all(k in data for k in ("nome", "email", "senha", "telefone")):
        return jsonify({"error": "Dados incompletos"}), 400

    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email já cadastrado"}), 409

    novo_usuario = Usuario(
        nome=data['nome'],
        email=data['email'],
        telefone=data['telefone']
    )
    novo_usuario.set_password(data['senha'])

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
    if 'nome' in data:
        usuario.nome = data['nome']
    if 'telefone' in data:
        usuario.telefone = data['telefone']
    if 'senha' in data:
        usuario.set_password(data['senha'])
        
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
