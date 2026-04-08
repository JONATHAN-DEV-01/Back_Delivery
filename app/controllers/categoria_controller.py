import math
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.categoria import Categoria
from app.models.restaurante import Restaurante
from app.models.loja_categoria import loja_categorias

categoria_bp = Blueprint('categoria', __name__)


# ──────────────────────────────────────────────────────────────
# GET /categorias
# RF-01 Req.7 – Lista todas as categorias (grade de exploração)
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/categorias', methods=['GET'])
def list_categorias():
    """
    Lista todas as categorias cadastradas.

    Query params opcionais:
        tipo   – filtra por 'COZINHA' ou 'PRODUTO'
    """
    tipo = request.args.get('tipo', '').strip().upper()

    query = Categoria.query
    if tipo:
        query = query.filter(Categoria.tipo == tipo)

    categorias = query.order_by(Categoria.is_highlight.desc(), Categoria.nome).all()
    return jsonify([c.to_dict() for c in categorias]), 200


# ──────────────────────────────────────────────────────────────
# GET /categorias/destaques
# RF-02 Req.7 – Carrossel da Home (is_highlight = true)
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/categorias/destaques', methods=['GET'])
def list_categorias_destaque():
    """Retorna apenas categorias marcadas como destaque para o carrossel da Home."""
    tipo = request.args.get('tipo', 'COZINHA').strip().upper()

    categorias = (
        Categoria.query
        .filter(Categoria.is_highlight == True, Categoria.tipo == tipo)  # noqa: E712
        .order_by(Categoria.nome)
        .all()
    )
    return jsonify([c.to_dict() for c in categorias]), 200


# ──────────────────────────────────────────────────────────────
# POST /categorias
# Criação de categoria (admin)
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/categorias', methods=['POST'])
def create_categoria():
    """Cria uma nova categoria. RN-01: nome único."""
    data = request.get_json(silent=True) or {}

    nome = (data.get('nome') or '').strip()
    tipo = (data.get('tipo') or 'COZINHA').strip().upper()

    if not nome:
        return jsonify({"error": "O campo 'nome' é obrigatório."}), 400

    if Categoria.query.filter(Categoria.nome.ilike(nome)).first():
        return jsonify({"error": "Já existe uma categoria com este nome."}), 409

    nova = Categoria(
        nome=nome.title(),
        tipo=tipo,
        imagem_url=data.get('imagem_url'),
        is_highlight=bool(data.get('is_highlight', False)),
    )
    db.session.add(nova)
    db.session.commit()
    return jsonify(nova.to_dict()), 201


# ──────────────────────────────────────────────────────────────
# PATCH /categorias/<id>
# Atualização de categoria (admin)
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/categorias/<int:categoria_id>', methods=['PATCH'])
def update_categoria(categoria_id):
    """Atualiza campos de uma categoria."""
    categoria = Categoria.query.get(categoria_id)
    if not categoria:
        return jsonify({"error": "Categoria não encontrada."}), 404

    data = request.get_json(silent=True) or {}

    if 'nome' in data:
        novo_nome = data['nome'].strip().title()
        existente = Categoria.query.filter(Categoria.nome.ilike(novo_nome)).first()
        if existente and existente.id != categoria_id:
            return jsonify({"error": "Já existe uma categoria com este nome."}), 409
        categoria.nome = novo_nome

    if 'tipo' in data:
        categoria.tipo = data['tipo'].strip().upper()
    if 'imagem_url' in data:
        categoria.imagem_url = data['imagem_url']
    if 'is_highlight' in data:
        categoria.is_highlight = bool(data['is_highlight'])

    db.session.commit()
    return jsonify(categoria.to_dict()), 200


# ──────────────────────────────────────────────────────────────
# GET /restaurantes/por-categoria/<categoria_id>
# RF-04 Req.7 – Filtra restaurantes por categoria + geolocalização
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/restaurantes/por-categoria/<int:categoria_id>', methods=['GET'])
def restaurantes_por_categoria(categoria_id):
    """
    Lista restaurantes de uma categoria, ordenados por abertura e proximidade.

    Query params opcionais:
        lat   – latitude do usuário (float)
        lon   – longitude do usuário (float)
    """
    categoria = Categoria.query.get(categoria_id)
    if not categoria:
        return jsonify({"error": "Categoria não encontrada."}), 404

    # Coordenadas do usuário (opcionais)
    try:
        user_lat = float(request.args.get('lat')) if request.args.get('lat') else None
        user_lon = float(request.args.get('lon')) if request.args.get('lon') else None
    except (ValueError, TypeError):
        user_lat = user_lon = None

    # RF-04: restaurantes ativos que pertencem à categoria via tabela N:N ou campo legado
    from sqlalchemy import or_

    restaurantes = (
        db.session.query(Restaurante)
        .outerjoin(loja_categorias, loja_categorias.c.loja_id == Restaurante.id)
        .filter(
            or_(
                loja_categorias.c.categoria_id == categoria_id,
                Restaurante.categoria_id == categoria_id
            ),
            Restaurante.ativo == True  # noqa: E712
        )
        .distinct()
        .all()
    )

    # Condicional Req.7.3: nenhum resultado encontrado
    if not restaurantes:
        return jsonify({
            "message": "Nenhum restaurante encontrado para esta categoria na sua região.",
            "categoria": categoria.to_dict(),
            "results": [],
            "total": 0,
        }), 200

    # Serializa + calcula distância
    lista = []
    for r in restaurantes:
        d = r.to_dict()
        if user_lat is not None and user_lon is not None:
            d['distancia_km'] = r.distancia_km(user_lat, user_lon)
        else:
            d['distancia_km'] = None
        lista.append(d)

    # RF-06 Req.7 + RN-01 Req.7: abertos primeiro, depois por distância
    lista.sort(key=lambda x: (
        0 if x.get('is_open') else 1,
        x['distancia_km'] if x['distancia_km'] is not None else float('inf'),
    ))

    return jsonify({
        "categoria": categoria.to_dict(),
        "total":    len(lista),
        "results":  lista,
    }), 200


# ──────────────────────────────────────────────────────────────
# POST /restaurantes/<loja_id>/categorias
# Vincula restaurante a uma ou mais categorias (N:N)
# ──────────────────────────────────────────────────────────────
@categoria_bp.route('/restaurantes/<uuid:loja_id>/categorias', methods=['POST'])
def vincular_categorias(loja_id):
    """
    Vincula o restaurante às categorias informadas.
    Body JSON: { "categoria_ids": [1, 2, 3] }
    """
    restaurante = Restaurante.query.get(loja_id)
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404

    data = request.get_json(silent=True) or {}
    ids = data.get('categoria_ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "'categoria_ids' deve ser uma lista não vazia."}), 400

    categorias = Categoria.query.filter(Categoria.id.in_(ids)).all()
    if not categorias:
        return jsonify({"error": "Nenhuma categoria válida encontrada."}), 404

    # Substitui a lista (idempotente)
    restaurante.categorias = categorias
    db.session.commit()

    return jsonify({
        "message": f"{len(categorias)} categoria(s) vinculada(s) com sucesso.",
        "categorias": [c.to_dict() for c in restaurante.categorias],
    }), 200
