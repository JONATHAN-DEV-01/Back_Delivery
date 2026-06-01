"""
estoque_controller.py
=====================
Módulo de Gerenciamento de Estoque — Zupps Delivery
Referência: Especificação Módulo 10 (RF-01, RF-03, RN-01, RN-02, RN-03, RNF-02)

Rotas expostas:
  GET    /estoque/<restaurante_id>/produtos        → Lista produtos + status (RN-03)
  GET    /estoque/<restaurante_id>/adicionais      → Lista adicionais agrupados (RN-03)
  PATCH  /estoque/produtos/<produto_id>/toggle     → Toggle disponibilidade produto (RF-01)
  PATCH  /estoque/produtos/<produto_id>/quantidade → Atualiza quantidade numérica (RF-01)
  PATCH  /estoque/adicionais/<adicional_id>/toggle → Toggle disponibilidade adicional (RF-03)

Autenticação:
  Todas as rotas de escrita exigem JWT de restaurante via Authorization: Bearer <token>.
  O token é validado e o restaurante_id resolvido pelo decorator @require_restaurante_auth.
"""

import os
import jwt
from functools import wraps
from flask import Blueprint, request, jsonify, g
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.produto import Produto
from app.models.adicional import GrupoAdicionais, Adicional
from app.models.restaurante import Restaurante

estoque_bp = Blueprint('estoque', __name__)


# ─── Decorator de autenticação de restaurante ─────────────────────────────────

def require_restaurante_auth(f):
    """
    RN-02: Valida o JWT de restaurante e disponibiliza g.restaurante_id.
    Compatível com o modelo existente onde restaurantes possuem token JWT próprio
    com claim 'restaurante_id' ou 'user_id' + tipo 'restaurante'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
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

        # Tenta extrair restaurante_id do payload
        # Suporta claims: 'restaurante_id', 'user_id' com tipo 'restaurante'
        restaurante_id_claim = (
            payload.get('restaurante_id')
            or (payload.get('user_id') if payload.get('tipo') == 'restaurante' else None)
        )
        if not restaurante_id_claim:
            return jsonify({'error': 'Token não pertence a um restaurante.'}), 403

        g.restaurante_id = str(restaurante_id_claim)
        return f(*args, **kwargs)

    return decorated


def _verificar_dono_produto(produto: Produto) -> bool:
    """Verifica se o restaurante autenticado (g.restaurante_id) é dono do produto."""
    return str(produto.restaurante_id) == g.restaurante_id


# ─── GET /estoque/<restaurante_id>/produtos ───────────────────────────────────

@estoque_bp.route('/estoque/<uuid:restaurante_id>/produtos', methods=['GET'])
@require_restaurante_auth
def listar_estoque_produtos(restaurante_id):
    """
    RN-03: Retorna TODOS os produtos do restaurante, incluindo os esgotados.
    O frontend exibe os indisponíveis com overlay visual (RF-02).
    """
    # RN-02: Apenas o próprio restaurante acessa seu estoque
    if str(restaurante_id) != g.restaurante_id:
        return jsonify({'error': 'Acesso negado.'}), 403

    produtos = (
        Produto.query
        .filter_by(restaurante_id=restaurante_id)
        .order_by(Produto.nome)
        .all()
    )
    return jsonify([_produto_estoque_dict(p) for p in produtos]), 200


# ─── GET /estoque/<restaurante_id>/adicionais ─────────────────────────────────

@estoque_bp.route('/estoque/<uuid:restaurante_id>/adicionais', methods=['GET'])
@require_restaurante_auth
def listar_estoque_adicionais(restaurante_id):
    """
    RN-03: Retorna TODOS os adicionais agrupados por GrupoAdicionais,
    incluindo os esgotados.
    """
    if str(restaurante_id) != g.restaurante_id:
        return jsonify({'error': 'Acesso negado.'}), 403

    # Subquery com todos os produto_ids do restaurante
    produtos_ids = (
        db.session.query(Produto.id)
        .filter_by(restaurante_id=restaurante_id)
        .subquery()
    )

    grupos = (
        GrupoAdicionais.query
        .filter(GrupoAdicionais.produto_id.in_(produtos_ids))
        .order_by(GrupoAdicionais.nome)
        .all()
    )

    resultado = [
        {
            'grupo_id':   grupo.id,
            'grupo_nome': grupo.nome,
            'produto_id': str(grupo.produto_id),
            'adicionais': [_adicional_estoque_dict(a) for a in grupo.adicionais],
        }
        for grupo in grupos
    ]

    return jsonify(resultado), 200


# ─── PATCH /estoque/produtos/<produto_id>/toggle ─────────────────────────────

@estoque_bp.route('/estoque/produtos/<uuid:produto_id>/toggle', methods=['PATCH'])
@require_restaurante_auth
def toggle_produto_disponibilidade(produto_id):
    """
    RF-01: Pausa rápida de produto com um único clique.
    RN-02: Apenas o dono do restaurante pode alterar.
    RNF-02: Operação dentro de transação ACID.

    Body JSON:
    { "disponivel": true | false }

    Response 200:
    { "message": "...", "produto": { ...campos de estoque... } }
    """
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({'error': 'Produto não encontrado'}), 404

    # RN-02
    if not _verificar_dono_produto(produto):
        return jsonify({'error': 'Acesso negado. Você não é o dono deste produto.'}), 403

    data = request.get_json()
    if data is None or 'disponivel' not in data:
        return jsonify({'error': 'Campo "disponivel" (boolean) é obrigatório no body JSON.'}), 400

    novo_status = bool(data['disponivel'])

    try:
        produto.disponivel = novo_status

        # Sincronizar quantidade se controle numérico estiver ativo
        if produto.quantidade is not None:
            if not novo_status:
                produto.quantidade = 0
            elif novo_status and produto.quantidade <= 0:
                produto.quantidade = 1

        db.session.commit()

        return jsonify({
            'message': f'Produto {"disponibilizado" if novo_status else "esgotado"} com sucesso.',
            'produto': _produto_estoque_dict(produto),
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Erro no banco de dados: {str(e)}'}), 500


# ─── PATCH /estoque/produtos/<produto_id>/quantidade ─────────────────────────

@estoque_bp.route('/estoque/produtos/<uuid:produto_id>/quantidade', methods=['PATCH'])
@require_restaurante_auth
def atualizar_quantidade_produto(produto_id):
    """
    RF-01: Atualiza a quantidade numérica disponível.
    Ao atingir 0, o produto é automaticamente marcado como esgotado.
    Ao subir de 0 para > 0, é automaticamente marcado como disponível.
    RNF-02: Transação ACID.

    Body JSON (um dos dois):
    { "quantidade": 15 }     → valor absoluto
    { "delta": -1 }          → incremento/decremento relativo
    """
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({'error': 'Produto não encontrado'}), 404

    if not _verificar_dono_produto(produto):
        return jsonify({'error': 'Acesso negado.'}), 403

    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Body JSON inválido.'}), 400

    try:
        if 'quantidade' in data:
            nova_qtd = max(0, int(data['quantidade']))
        elif 'delta' in data:
            qtd_atual = produto.quantidade if produto.quantidade is not None else 0
            nova_qtd = max(0, qtd_atual + int(data['delta']))
        else:
            return jsonify({'error': 'Informe "quantidade" (absoluto) ou "delta" (relativo) no body.'}), 400

        produto.quantidade = nova_qtd
        # RNF-02: disponibilidade sincronizada atomicamente com quantidade
        produto.disponivel = nova_qtd > 0

        db.session.commit()

        return jsonify({
            'message': 'Quantidade atualizada com sucesso.',
            'produto': _produto_estoque_dict(produto),
        }), 200

    except (ValueError, TypeError):
        return jsonify({'error': '"quantidade" e "delta" devem ser números inteiros.'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Erro no banco de dados: {str(e)}'}), 500


# ─── PATCH /estoque/adicionais/<adicional_id>/toggle ─────────────────────────

@estoque_bp.route('/estoque/adicionais/<int:adicional_id>/toggle', methods=['PATCH'])
@require_restaurante_auth
def toggle_adicional_disponibilidade(adicional_id):
    """
    RF-03: Esgota/disponibiliza um adicional individualmente sem afetar o produto principal.
    RN-02: Apenas o dono do restaurante pode alterar.
    RNF-02: Transação ACID.

    Body JSON:
    { "disponivel": true | false }
    """
    adicional = Adicional.query.get(adicional_id)
    if not adicional:
        return jsonify({'error': 'Adicional não encontrado.'}), 404

    # Navegar: adicional → grupo → produto → verificar dono
    grupo = GrupoAdicionais.query.get(adicional.grupo_id)
    if not grupo:
        return jsonify({'error': 'Grupo de adicionais não encontrado.'}), 404

    produto = Produto.query.get(grupo.produto_id)
    if not produto:
        return jsonify({'error': 'Produto vinculado não encontrado.'}), 404

    # RN-02
    if not _verificar_dono_produto(produto):
        return jsonify({'error': 'Acesso negado. Você não é o dono deste adicional.'}), 403

    data = request.get_json()
    if data is None or 'disponivel' not in data:
        return jsonify({'error': 'Campo "disponivel" (boolean) é obrigatório no body JSON.'}), 400

    novo_status = bool(data['disponivel'])

    try:
        adicional.disponivel = novo_status
        db.session.commit()

        return jsonify({
            'message': f'Adicional "{adicional.nome}" {"disponibilizado" if novo_status else "esgotado"} com sucesso.',
            'adicional': _adicional_estoque_dict(adicional),
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Erro no banco de dados: {str(e)}'}), 500


# ─── Helpers de serialização ─────────────────────────────────────────────────

def _produto_estoque_dict(produto: Produto) -> dict:
    """Serialização focada nos campos de estoque (resposta leve)."""
    return {
        'id':                str(produto.id),
        'nome':              produto.nome,
        'preco':             float(produto.preco),
        'imagem':            produto.imagem,
        'disponivel':        produto.disponivel,
        'status_disponivel': produto.disponivel,   # Alias para o frontend
        'quantidade':        produto.quantidade,
        'restaurante_id':    str(produto.restaurante_id),
    }


def _adicional_estoque_dict(adicional: Adicional) -> dict:
    """Serialização focada nos campos de estoque de adicionais."""
    return {
        'id':                adicional.id,
        'nome':              adicional.nome,
        'preco':             float(adicional.preco),
        'disponivel':        adicional.disponivel,
        'status_disponivel': adicional.disponivel,  # Alias para o frontend
        'grupo_id':          adicional.grupo_id,
    }
