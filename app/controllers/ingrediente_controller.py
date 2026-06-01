from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.ingrediente import Ingrediente
from app.models.restaurante import Restaurante
import os
import jwt
from functools import wraps

ingrediente_bp = Blueprint('ingredientes', __name__)

# Reusing the require_restaurante_auth logic (ideally this should be in auth_utils, but following the pattern in estoque_controller)
def require_restaurante_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return '', 204

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autenticação não informado.'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET', 'zupps-secret-key'),
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado. Faça login novamente.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido.'}), 401

        restaurante_id_claim = (
            payload.get('restaurante_id')
            or (payload.get('user_id') if payload.get('tipo') == 'restaurante' else None)
        )
        if not restaurante_id_claim:
            return jsonify({'error': 'Token não pertence a um restaurante.'}), 403

        g.restaurante_id = str(restaurante_id_claim)
        return f(*args, **kwargs)

    return decorated

@ingrediente_bp.route('/ingredientes', methods=['GET'])
@require_restaurante_auth
def listar_ingredientes():
    ingredientes = Ingrediente.query.filter_by(restaurante_id=g.restaurante_id).order_by(Ingrediente.nome).all()
    return jsonify([i.to_dict() for i in ingredientes]), 200

@ingrediente_bp.route('/ingredientes', methods=['POST'])
@require_restaurante_auth
def criar_ingrediente():
    data = request.get_json()
    if not data or not data.get('nome') or not data.get('unidade_medida'):
        return jsonify({'error': 'Nome e unidade_medida são obrigatórios'}), 400

    try:
        novo = Ingrediente(
            nome=data['nome'],
            quantidade_atual=data.get('quantidade_atual', 0.0),
            unidade_medida=data['unidade_medida'],
            custo_unitario=data.get('custo_unitario'),
            restaurante_id=g.restaurante_id
        )
        db.session.add(novo)
        db.session.commit()
        return jsonify(novo.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@ingrediente_bp.route('/ingredientes/<uuid:id>', methods=['PATCH'])
@require_restaurante_auth
def atualizar_ingrediente(id):
    ingrediente = Ingrediente.query.get(id)
    if not ingrediente or str(ingrediente.restaurante_id) != g.restaurante_id:
        return jsonify({'error': 'Ingrediente não encontrado'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados inválidos'}), 400

    try:
        if 'nome' in data:
            ingrediente.nome = data['nome']
        if 'quantidade_atual' in data:
            # Pode ser enviada quantidade absoluta
            ingrediente.quantidade_atual = max(0.0, float(data['quantidade_atual']))
        elif 'delta' in data:
            # Ou alteração relativa (entrada/saída manual)
            ingrediente.quantidade_atual = max(0.0, float(ingrediente.quantidade_atual) + float(data['delta']))
        
        if 'unidade_medida' in data:
            ingrediente.unidade_medida = data['unidade_medida']
        if 'custo_unitario' in data:
            ingrediente.custo_unitario = data['custo_unitario']

        db.session.commit()
        return jsonify(ingrediente.to_dict()), 200
    except (ValueError, TypeError):
        return jsonify({'error': 'Valores numéricos inválidos'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@ingrediente_bp.route('/ingredientes/<uuid:id>', methods=['DELETE'])
@require_restaurante_auth
def excluir_ingrediente(id):
    ingrediente = Ingrediente.query.get(id)
    if not ingrediente or str(ingrediente.restaurante_id) != g.restaurante_id:
        return jsonify({'error': 'Ingrediente não encontrado'}), 404

    try:
        db.session.delete(ingrediente)
        db.session.commit()
        return jsonify({'message': 'Ingrediente removido com sucesso'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': 'Erro ao excluir (pode estar vinculado a uma ficha técnica)'}), 500
