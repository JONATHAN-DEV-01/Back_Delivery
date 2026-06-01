import uuid
from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.adicional import Adicional
from app.models.produto import Produto
from app.controllers.estoque_controller import require_restaurante_auth

adicional_bp = Blueprint('adicionais', __name__)

@adicional_bp.route('/adicionais', methods=['GET'])
@require_restaurante_auth
def listar_adicionais():
    adicionais = Adicional.query.filter_by(restaurante_id=g.restaurante_id).order_by(Adicional.nome).all()
    return jsonify([a.to_dict() for a in adicionais]), 200

@adicional_bp.route('/adicionais', methods=['POST'])
@require_restaurante_auth
def criar_adicional():
    data = request.get_json()
    if not data or not data.get('nome'):
        return jsonify({'error': 'O campo nome é obrigatório.'}), 400

    novo = Adicional(
        nome=data['nome'],
        preco=data.get('preco', 0.0),
        quantidade_atual=data.get('quantidade_atual', 0.0),
        restaurante_id=g.restaurante_id
    )
    try:
        db.session.add(novo)
        db.session.commit()
        return jsonify(novo.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@adicional_bp.route('/adicionais/<int:id>', methods=['PUT', 'PATCH'])
@require_restaurante_auth
def atualizar_adicional(id):
    adicional = Adicional.query.filter_by(id=id, restaurante_id=g.restaurante_id).first()
    if not adicional:
        return jsonify({'error': 'Adicional não encontrado.'}), 404

    data = request.get_json()
    if 'nome' in data:
        adicional.nome = data['nome']
    if 'preco' in data:
        adicional.preco = data['preco']
    if 'quantidade_atual' in data:
        adicional.quantidade_atual = data['quantidade_atual']

    try:
        db.session.commit()
        return jsonify(adicional.to_dict()), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@adicional_bp.route('/adicionais/<int:id>', methods=['DELETE'])
@require_restaurante_auth
def deletar_adicional(id):
    adicional = Adicional.query.filter_by(id=id, restaurante_id=g.restaurante_id).first()
    if not adicional:
        return jsonify({'error': 'Adicional não encontrado.'}), 404

    try:
        db.session.delete(adicional)
        db.session.commit()
        return '', 204
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
