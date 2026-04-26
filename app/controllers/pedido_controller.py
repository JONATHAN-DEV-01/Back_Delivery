import uuid
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.pedido import Pedido, ItemPedido
from app.models.restaurante import Restaurante
from app.models.produto import Produto
from app.models.adicional import Adicional
from app.models.cupom import Cupom
from app.models.usuario import Usuario
from app.utils.auth_utils import require_auth
from decimal import Decimal

pedido_bp = Blueprint('pedido', __name__)

@pedido_bp.route('/orders', methods=['POST'])
@pedido_bp.route('/pedidos', methods=['POST'])
@require_auth
def create_pedido():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Payload inválido'}), 400

    usuario_id = g.usuario_id
    restaurante_id = data.get('restaurant_id')
    if not restaurante_id:
        return jsonify({'error': 'restaurant_id é obrigatório'}), 400

    # 1. Carregar Restaurante e Validar Horário (RN-02)
    restaurante = Restaurante.query.get(restaurante_id)
    if not restaurante:
        return jsonify({'error': 'Restaurante não encontrado'}), 404
    
    if not restaurante.is_open:
        return jsonify({'error': 'O restaurante está fechado no momento.'}), 400

    # 2. Carregar Usuário e Endereço
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Snapshot do endereço do usuário atual
    endereco_snapshot = {
        'logradouro': usuario.logradouro,
        'bairro': usuario.bairro,
        'cidade': usuario.cidade,
        'estado': usuario.estado,
        'numero': usuario.numero,
        'sem_numero': usuario.sem_numero,
        'complemento': usuario.complemento,
        'ponto_referencia': usuario.ponto_referencia
    }

    # Validação de Raio de Entrega (RN-04) - Apenas log ou bypass se não houver coords
    # Futuramente: if usuario.latitude and restaurante.latitude: check distancia_km()

    # 3. Extrair dados de pagamento e outros
    payment_data = data.get('payment', {})
    forma_pagamento = payment_data.get('method', 'UNKNOWN')
    change_for = payment_data.get('change_for')
    
    # Conversão segura para centavos se vier float
    troco_para_centavos = None
    if change_for:
        troco_para_centavos = int(float(change_for) * 100) if '.' in str(change_for) else int(change_for)

    cupom_codigo = data.get('coupon_code')
    observacoes = str(data.get('notes', ''))[:140]
    items_data = data.get('items', [])
    
    if not items_data:
        return jsonify({'error': 'O pedido deve conter pelo menos um item'}), 400

    # Iniciar Transação ACID (RNF-02)
    try:
        subtotal_calculado_centavos = 0
        itens_pedido = []

        # 4. Processar Itens e Validar Preços (RN-06 e Proteção contra Fraudes)
        for item in items_data:
            produto_id = item.get('product_id')
            quantidade = max(1, int(item.get('quantity', 1)))

            produto = Produto.query.get(produto_id)
            if not produto:
                db.session.rollback()
                return jsonify({'error': f'Produto não encontrado: {produto_id}'}), 404
            
            # RN-01: Checar se o produto pertence ao restaurante
            if str(produto.restaurante_id) != str(restaurante_id):
                db.session.rollback()
                return jsonify({'error': 'Todos os itens devem pertencer ao mesmo restaurante'}), 400

            # Definir preço base do produto
            if produto.preco_promocional and float(produto.preco_promocional) > 0:
                preco_base = int(float(produto.preco_promocional) * 100)
            else:
                preco_base = int(float(produto.preco) * 100)

            # Processar adicionais (options)
            opcoes_selecionadas = []
            total_adicionais = 0
            for opt in item.get('options', []):
                adicional_id = opt.get('option_id')
                if adicional_id:
                    adicional_db = Adicional.query.get(adicional_id)
                    # Verificar se o adicional existe e se pertence ao produto (RN-06)
                    if adicional_db and str(adicional_db.produto_id) == str(produto.id):
                        preco_opt_centavos = int(float(adicional_db.preco) * 100)
                        qtd_opt = max(1, int(opt.get('quantity', 1)))
                        
                        opcoes_selecionadas.append({
                            'id': str(adicional_db.id),
                            'nome': adicional_db.nome,
                            'preco_unitario_centavos': preco_opt_centavos,
                            'quantidade': qtd_opt
                        })
                        total_adicionais += (preco_opt_centavos * qtd_opt)

            preco_total_item = (preco_base + total_adicionais) * quantidade
            subtotal_calculado_centavos += preco_total_item

            novo_item = ItemPedido(
                produto_id=produto.id,
                nome_produto=produto.nome,
                quantidade=quantidade,
                preco_unitario_base_centavos=preco_base,
                preco_total_item_centavos=preco_total_item,
                adicionais=opcoes_selecionadas
            )
            itens_pedido.append(novo_item)

        # 5. Valor Mínimo do Pedido (RN-03)
        pedido_minimo = restaurante.pedido_minimo_centavos or 0
        if subtotal_calculado_centavos < pedido_minimo:
            db.session.rollback()
            return jsonify({'error': f'O valor mínimo do pedido é {pedido_minimo/100:.2f}'}), 400

        # 6. Descontos e Taxa de Entrega
        taxa_entrega_centavos = int(float(restaurante.valor_frete) * 100) if restaurante.valor_frete else 0
        desconto_centavos = 0
        
        if cupom_codigo:
            cupom = Cupom.query.filter_by(codigo=cupom_codigo.strip().upper()).first()
            if cupom and cupom.is_valido():
                if subtotal_calculado_centavos >= cupom.valor_minimo_centavos:
                    desconto_centavos = cupom.valor_desconto_centavos

        total_calculado_centavos = subtotal_calculado_centavos + taxa_entrega_centavos - desconto_centavos
        if total_calculado_centavos < 0:
            total_calculado_centavos = 0

        # 7. Criar Registro de Pedido
        novo_pedido = Pedido(
            usuario_id=usuario.id,
            restaurante_id=restaurante.id,
            status='PENDENTE_ACEITACAO',  # RN-05
            forma_pagamento=forma_pagamento,
            troco_para_centavos=troco_para_centavos,
            subtotal_centavos=subtotal_calculado_centavos,
            taxa_entrega_centavos=taxa_entrega_centavos,
            desconto_centavos=desconto_centavos,
            total_centavos=total_calculado_centavos,
            cupom_codigo=cupom_codigo if desconto_centavos > 0 else None,
            observacoes=observacoes,
            endereco_entrega_snapshot=endereco_snapshot
        )
        
        db.session.add(novo_pedido)
        db.session.flush() # Para gerar o ID do pedido
        
        # Adicionar itens
        for item in itens_pedido:
            item.pedido_id = novo_pedido.id
            db.session.add(item)
            
        # Confirmar transação
        db.session.commit()
        
        return jsonify({
            'message': 'Pedido realizado com sucesso!',
            'order_id': str(novo_pedido.id),
            'order': novo_pedido.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        # Em ambiente real, usar logger
        return jsonify({'error': 'Erro ao processar o pedido. A transação foi cancelada.', 'details': str(e)}), 500

@pedido_bp.route('/orders/<order_id>', methods=['GET'])
@pedido_bp.route('/pedidos/<order_id>', methods=['GET'])
@require_auth
def get_pedido(order_id):
    pedido = Pedido.query.get(order_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404
        
    # Validar se o pedido é do usuário ou do restaurante
    if str(pedido.usuario_id) != g.usuario_id:
        return jsonify({'error': 'Acesso negado'}), 403
        
    return jsonify({'order': pedido.to_dict()}), 200
