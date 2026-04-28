import uuid
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.carrinho import Carrinho, ItemCarrinho, ItemAdicionalCarrinho
from app.models.cupom import Cupom
from app.models.produto import Produto
from app.models.adicional import Adicional
from app.models.restaurante import Restaurante
from app.utils.auth_utils import require_auth

carrinho_bp = Blueprint('carrinho', __name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_none(usuario_id: str) -> Carrinho | None:
    return Carrinho.query.filter_by(usuario_id=usuario_id).first()


def _build_fingerprint(produto_id: str, adicionais_ids: list[int], observacao: str) -> str:
    ids_sorted = sorted(str(i) for i in adicionais_ids)
    return f"{produto_id}|{','.join(ids_sorted)}|{observacao.strip()}"


def _preco_centavos(produto: Produto) -> int:
    """Retorna preço efetivo (promocional ou normal) em centavos."""
    if produto.preco_promocional and float(produto.preco_promocional) > 0:
        return int(float(produto.preco_promocional) * 100)
    return int(float(produto.preco) * 100)


# ─── GET /carrinho ─────────────────────────────────────────────────────────────

@carrinho_bp.route('/carrinho', methods=['GET'])
@require_auth
def get_carrinho():
    """Retorna o carrinho completo do usuário autenticado com totais calculados."""
    carrinho = _get_or_none(g.usuario_id)
    if not carrinho:
        return jsonify({'carrinho': None}), 200

    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── POST /carrinho/itens ──────────────────────────────────────────────────────

@carrinho_bp.route('/carrinho/itens', methods=['POST'])
@require_auth
def add_item():
    """
    Adiciona um item ao carrinho.
    - Cria carrinho se não existir
    - Retorna 409 se o restaurante for diferente (conflito)
    - Merges item idêntico (mesmo produto + adicionais + observação)
    """
    data = request.get_json()
    if not data or 'produto_id' not in data or 'restaurante_id' not in data:
        return jsonify({'error': 'produto_id e restaurante_id são obrigatórios.'}), 400

    produto_id     = data['produto_id']
    restaurante_id = data['restaurante_id']
    quantidade     = max(1, int(data.get('quantidade', 1)))
    observacao     = (data.get('observacao') or '')[:200]
    adicionais_ids = [int(i) for i in data.get('adicionais_ids', [])]

    # Valida produto
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({'error': 'Produto não encontrado.'}), 404
    if not produto.disponivel:
        return jsonify({'error': 'Desculpe, este item acabou agora pouco.'}), 422

    # Valida restaurante
    restaurante = Restaurante.query.get(restaurante_id)
    if not restaurante:
        return jsonify({'error': 'Restaurante não encontrado.'}), 404

    # Busca ou cria carrinho
    carrinho = _get_or_none(g.usuario_id)

    if carrinho:
        # Conflito de restaurante
        if str(carrinho.restaurante_id) != str(restaurante_id) and len(carrinho.itens) > 0:
            return jsonify({
                'error': 'conflict',
                'message': 'Você já tem itens de outro restaurante. Deseja limpar o carrinho atual e começar um novo?',
                'restaurante_atual': carrinho.restaurante.nome_fantasia,
            }), 409

        # Descongelar se estava congelado (usuário voltou ao carrinho)
        if carrinho.congelado:
            carrinho.congelado = False
            carrinho.token_checkout = None
    else:
        carrinho = Carrinho(
            usuario_id=g.usuario_id,
            restaurante_id=restaurante_id,
        )
        db.session.add(carrinho)
        db.session.flush()  # Garante que o id seja gerado

    # Snapshot dos adicionais
    adicionais_obj = Adicional.query.filter(Adicional.id.in_(adicionais_ids)).all() if adicionais_ids else []
    adicionais_map = {a.id: a for a in adicionais_obj}

    # Fingerprint para detectar item idêntico
    fp = _build_fingerprint(produto_id, adicionais_ids, observacao)

    # Busca item idêntico
    item_existente = None
    for item in carrinho.itens:
        item_fp = _build_fingerprint(
            str(item.produto_id),
            [a.adicional_id for a in item.adicionais],
            item.observacao or ''
        )
        if item_fp == fp:
            item_existente = item
            break

    if item_existente:
        item_existente.quantidade += quantidade
    else:
        preco = _preco_centavos(produto)
        novo_item = ItemCarrinho(
            carrinho_id=carrinho.id,
            produto_id=produto_id,
            quantidade=quantidade,
            preco_unitario_centavos=preco,
            observacao=observacao,
        )
        db.session.add(novo_item)
        db.session.flush()

        for aid in adicionais_ids:
            adicional = adicionais_map.get(aid)
            if adicional:
                ia = ItemAdicionalCarrinho(
                    item_id=novo_item.id,
                    adicional_id=adicional.id,
                    nome_adicional=adicional.nome,
                    preco_centavos=int(float(adicional.preco) * 100),
                )
                db.session.add(ia)

    db.session.commit()

    # Recarrega para retornar dados atualizados
    db.session.refresh(carrinho)
    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── PUT /carrinho/itens/<item_id> ────────────────────────────────────────────

@carrinho_bp.route('/carrinho/itens/<item_id>', methods=['PUT'])
@require_auth
def update_item(item_id):
    """
    Atualiza a quantidade de um item.
    - Se quantidade <= 0: remove o item
    - Se o carrinho ficar vazio: apaga o carrinho
    """
    data = request.get_json()
    if not data or 'quantidade' not in data:
        return jsonify({'error': 'quantidade é obrigatória.'}), 400

    nova_qtd = int(data['quantidade'])

    carrinho = _get_or_none(g.usuario_id)
    if not carrinho:
        return jsonify({'error': 'Carrinho não encontrado.'}), 404

    item = ItemCarrinho.query.filter_by(id=item_id, carrinho_id=carrinho.id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado no carrinho.'}), 404

    if nova_qtd <= 0:
        db.session.delete(item)
        db.session.flush()

        # Se carrinho ficou vazio, apaga ele
        db.session.refresh(carrinho)
        if len(carrinho.itens) == 0:
            db.session.delete(carrinho)
            db.session.commit()
            return jsonify({'carrinho': None}), 200
    else:
        item.quantidade = nova_qtd

    db.session.commit()
    db.session.refresh(carrinho)
    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── DELETE /carrinho/itens/<item_id> ─────────────────────────────────────────

@carrinho_bp.route('/carrinho/itens/<item_id>', methods=['DELETE'])
@require_auth
def remove_item(item_id):
    """Remove um item do carrinho. Apaga o carrinho se ficar vazio."""
    carrinho = _get_or_none(g.usuario_id)
    if not carrinho:
        return jsonify({'error': 'Carrinho não encontrado.'}), 404

    item = ItemCarrinho.query.filter_by(id=item_id, carrinho_id=carrinho.id).first()
    if not item:
        return jsonify({'error': 'Item não encontrado no carrinho.'}), 404

    db.session.delete(item)
    db.session.flush()

    db.session.refresh(carrinho)
    if len(carrinho.itens) == 0:
        db.session.delete(carrinho)
        db.session.commit()
        return jsonify({'carrinho': None}), 200

    db.session.commit()
    db.session.refresh(carrinho)
    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── DELETE /carrinho ─────────────────────────────────────────────────────────

@carrinho_bp.route('/carrinho', methods=['DELETE'])
@require_auth
def clear_carrinho():
    """Limpa o carrinho inteiro do usuário."""
    carrinho = _get_or_none(g.usuario_id)
    if carrinho:
        db.session.delete(carrinho)
        db.session.commit()

    return jsonify({'message': 'Carrinho limpo com sucesso.'}), 200


# ─── POST /carrinho/cupom ─────────────────────────────────────────────────────

@carrinho_bp.route('/carrinho/cupom', methods=['POST'])
@require_auth
def aplicar_cupom():
    """Valida e aplica um cupom de desconto ao carrinho."""
    data = request.get_json()
    if not data or 'codigo' not in data:
        return jsonify({'error': 'Informe o código do cupom.'}), 400

    carrinho = _get_or_none(g.usuario_id)
    if not carrinho:
        return jsonify({'error': 'Você não tem um carrinho ativo.'}), 404

    codigo = data['codigo'].strip().upper()
    cupom = Cupom.query.filter_by(codigo=codigo).first()

    if not cupom or not cupom.is_valido():
        return jsonify({'error': 'Cupom inválido ou expirado.'}), 404

    subtotal = carrinho.calcular_subtotal()
    if subtotal < cupom.valor_minimo_centavos:
        falta = cupom.valor_minimo_centavos - subtotal
        return jsonify({
            'error': f'Pedido mínimo para este cupom é R$ {cupom.valor_minimo_centavos / 100:.2f}. '
                     f'Faltam R$ {falta / 100:.2f}.'
        }), 422

    carrinho.cupom_id = cupom.id
    db.session.commit()
    db.session.refresh(carrinho)

    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── DELETE /carrinho/cupom ───────────────────────────────────────────────────

@carrinho_bp.route('/carrinho/cupom', methods=['DELETE'])
@require_auth
def remover_cupom():
    """Remove o cupom do carrinho."""
    carrinho = _get_or_none(g.usuario_id)
    if not carrinho:
        return jsonify({'error': 'Carrinho não encontrado.'}), 404

    carrinho.cupom_id = None
    db.session.commit()
    db.session.refresh(carrinho)

    return jsonify({'carrinho': carrinho.to_dict()}), 200


# ─── POST /carrinho/congelar ──────────────────────────────────────────────────

@carrinho_bp.route('/carrinho/congelar', methods=['POST'])
@require_auth
def congelar_carrinho():
    """
    Congela o carrinho para checkout:
    - Verifica restaurante aberto
    - Verifica pedido mínimo
    - Gera token_checkout único
    - Marca carrinho como congelado
    """
    carrinho = _get_or_none(g.usuario_id)
    if not carrinho or len(carrinho.itens) == 0:
        return jsonify({'error': 'Carrinho vazio.'}), 422

    restaurante = carrinho.restaurante
    if not restaurante.is_open_agora:
        return jsonify({
            'error': 'O restaurante fechou. Não é possível continuar com o pedido.'
        }), 409

    subtotal = carrinho.calcular_subtotal()
    pedido_minimo = restaurante.pedido_minimo_centavos or 0
    if subtotal < pedido_minimo:
        falta = pedido_minimo - subtotal
        return jsonify({
            'error': f'Faltam R$ {falta / 100:.2f} para atingir o pedido mínimo de R$ {pedido_minimo / 100:.2f}.'
        }), 422

    # Verificar disponibilidade dos produtos
    for item in carrinho.itens:
        if not item.produto.disponivel:
            return jsonify({
                'error': f'O item "{item.produto.nome}" não está mais disponível.'
            }), 422

    # Gera token único de checkout
    token = str(uuid.uuid4())
    carrinho.congelado = True
    carrinho.token_checkout = token
    db.session.commit()
    db.session.refresh(carrinho)

    return jsonify({
        'message': 'Carrinho congelado. Prossiga para o pagamento.',
        'token_checkout': token,
        'resumo': carrinho.to_dict(),
    }), 200
