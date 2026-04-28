import os
import requests
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.pedido import Pedido
from app.models.restaurante import Restaurante
from app.models.usuario import Usuario
from app.models.pagamento import Pagamento
from app.models.cartoes_clientes import CartaoCliente
from app.utils.auth_utils import require_auth

pagamento_bp = Blueprint('pagamento', __name__)

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
MP_URL = "https://api.mercadopago.com/v1"

def get_mp_headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }

@pagamento_bp.route('/pagamentos/cartao', methods=['POST'])
@require_auth
def pagar_cartao():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Payload inválido'}), 400

    pedido_id = data.get('pedido_id')
    token = data.get('token')
    payment_method_id = data.get('payment_method_id')
    payer = data.get('payer', {})
    device_id = data.get('device_id')
    installments = data.get('installments', 1)
    issuer_id = data.get('issuer_id')
    save_card = data.get('save_card', False)
    expected_price = data.get('expected_price_centavos')

    if not all([pedido_id, token, payment_method_id, payer]):
        return jsonify({'error': 'Dados obrigatórios ausentes: pedido_id, token, payment_method_id e payer são necessários.'}), 400

    if not payer.get('email') or not payer.get('identification'):
        return jsonify({'error': 'O objeto payer deve conter email e identification (documento) obrigatórios para o antifraude.'}), 400

    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404

    # RN: Verificar se o restaurante está aberto
    restaurante = Restaurante.query.get(pedido.restaurante_id)
    if not restaurante.is_open_agora:
        return jsonify({'error': 'O restaurante está fechado no momento.'}), 400

    # RN: Verificar alteração de preço
    if expected_price is not None and int(expected_price) != pedido.total_centavos:
        return jsonify({'error': 'Ocorreu uma alteração no preço do pedido. Por favor, revise seu carrinho.'}), 400

    usuario = Usuario.query.get(g.usuario_id)
    email = payer.get('email')
    customer_id = None

    # Implementar tokenização e criação de Customer para armazenamento seguro
    if save_card or data.get('mp_card_id'):
        res_cust = requests.get(f"{MP_URL}/customers/search?email={email}", headers=get_mp_headers())
        cust_results = res_cust.json().get('results', [])
        
        if cust_results:
            customer_id = cust_results[0]['id']
        else:
            res_create = requests.post(f"{MP_URL}/customers", json={"email": email}, headers=get_mp_headers())
            if res_create.status_code in [200, 201]:
                customer_id = res_create.json().get('id')

        if save_card and customer_id and not data.get('mp_card_id'):
            # Salvar o cartão vinculando o token ao customer
            res_card = requests.post(f"{MP_URL}/customers/{customer_id}/cards", json={"token": token}, headers=get_mp_headers())
            if res_card.status_code in [200, 201]:
                card_data = res_card.json()
                mp_card_id = card_data.get('id')
                
                # Armazenar no banco de dados local
                existe = CartaoCliente.query.filter_by(mp_card_id=mp_card_id).first()
                if not existe:
                    novo_cartao = CartaoCliente(
                        usuario_id=usuario.id,
                        mp_customer_id=customer_id,
                        mp_card_id=mp_card_id,
                        ultimos_digitos=card_data.get('last_four_digits'),
                        bandeira=card_data.get('payment_method', {}).get('id')
                    )
                    db.session.add(novo_cartao)
                    db.session.commit()

    # Conversão de centavos para decimal exigida pela API
    transaction_amount = float(pedido.total_centavos) / 100.0

    payload = {
        "transaction_amount": transaction_amount,
        "token": token,
        "description": f"Pedido {pedido.id}",
        "installments": installments,
        "payment_method_id": payment_method_id,
        "payer": payer
    }

    if customer_id:
        payload["payer"]["id"] = customer_id
    if device_id:
        payload["additional_info"] = {"device_id": device_id}
    if issuer_id:
        payload["issuer_id"] = issuer_id

    res_pay = requests.post(f"{MP_URL}/payments", json=payload, headers=get_mp_headers())
    pay_data = res_pay.json()

    if res_pay.status_code not in [200, 201]:
        return jsonify({'error': 'Erro ao processar pagamento com cartão', 'details': pay_data}), 400

    status = pay_data.get('status', 'pending')
    novo_pagamento = Pagamento(
        pedido_id=pedido.id,
        mercado_pago_id=pay_data.get('id'),
        metodo='cartao',
        status=status,
        valor_centavos=pedido.total_centavos
    )
    db.session.add(novo_pagamento)

    if status == 'approved':
        pedido.status = 'PAGO'
    elif status in ['rejected', 'cancelled']:
        pedido.status = 'PAGAMENTO_REJEITADO'

    db.session.commit()

    return jsonify({
        'message': 'Pagamento processado com sucesso',
        'status': status,
        'pagamento_id': str(novo_pagamento.id),
        'mercado_pago_id': novo_pagamento.mercado_pago_id
    }), 200


@pagamento_bp.route('/pagamentos/pix', methods=['POST'])
@require_auth
def pagar_pix():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Payload inválido'}), 400

    pedido_id = data.get('pedido_id')
    payer = data.get('payer', {})
    expected_price = data.get('expected_price_centavos')

    if not pedido_id:
        return jsonify({'error': 'pedido_id é obrigatório'}), 400

    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404

    # RN: Verificar se o restaurante está aberto
    restaurante = Restaurante.query.get(pedido.restaurante_id)
    if not restaurante.is_open_agora:
        return jsonify({'error': 'O restaurante está fechado no momento.'}), 400

    # RN: Verificar alteração de preço
    if expected_price is not None and int(expected_price) != pedido.total_centavos:
        return jsonify({'error': 'Ocorreu uma alteração no preço do pedido. Por favor, revise seu carrinho.'}), 400

    usuario = Usuario.query.get(g.usuario_id)
    transaction_amount = float(pedido.total_centavos) / 100.0
    
    # CPF de teste para Mercado Pago sandbox (aceito em ambiente de testes)
    cpf_usuario = getattr(usuario, 'cpf', None) or '19119119100'

    payload = {
        "transaction_amount": transaction_amount,
        "payment_method_id": "pix",
        "description": f"Pedido {pedido.id}",
        "payer": {
            "email": payer.get('email', usuario.email),
            "first_name": payer.get('first_name', usuario.nome or 'Cliente'),
            "last_name": payer.get('last_name', usuario.sobrenome or 'Zupps'),
            "identification": {
                "type": "CPF",
                "number": cpf_usuario.replace('.','').replace('-','')
            }
        },
        "date_of_expiration": (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"
    }

    res_pay = requests.post(f"{MP_URL}/payments", json=payload, headers=get_mp_headers())
    pay_data = res_pay.json()

    if res_pay.status_code not in [200, 201]:
        return jsonify({'error': 'Erro ao gerar Pix', 'details': pay_data, 'mp_status': res_pay.status_code}), 400

    poi = pay_data.get('point_of_interaction', {}).get('transaction_data', {})
    qr_code = poi.get('qr_code')
    qr_code_base64 = poi.get('qr_code_base64')
    status = pay_data.get('status', 'pending')

    novo_pagamento = Pagamento(
        pedido_id=pedido.id,
        mercado_pago_id=pay_data.get('id'),
        metodo='pix',
        status=status,
        valor_centavos=pedido.total_centavos,
        pix_qr_code=qr_code,
        pix_qr_code_base64=qr_code_base64
    )
    db.session.add(novo_pagamento)
    
    if status == 'approved':
        pedido.status = 'PAGO'
    elif status in ['rejected', 'cancelled']:
        pedido.status = 'PAGAMENTO_REJEITADO'

    db.session.commit()

    return jsonify({
        'message': 'Pix gerado com sucesso',
        'status': status,
        'pagamento_id': str(novo_pagamento.id),
        'mercado_pago_id': novo_pagamento.mercado_pago_id,
        'pix_qr_code': qr_code,
        'pix_qr_code_base64': qr_code_base64
    }), 200


@pagamento_bp.route('/webhooks/mercado-pago', methods=['POST'])
def webhook_mp():
    # Mercado Pago envia o ID do pagamento de diferentes formas (action e data.id no query params ou JSON)
    data_id = request.args.get('data.id')
    if not data_id:
        json_data = request.get_json() or {}
        data_id = json_data.get('data', {}).get('id')

    if not data_id:
        return jsonify({'status': 'ignored'}), 200

    # Busca status atualizado do pagamento na API
    res = requests.get(f"{MP_URL}/payments/{data_id}", headers=get_mp_headers())
    if res.status_code == 200:
        pay_data = res.json()
        mp_status = pay_data.get('status')
        
        pagamento = Pagamento.query.filter_by(mercado_pago_id=int(data_id)).first()
        if pagamento:
            # Mapear e atualizar os status oficiais (approved, rejected, in_process, cancelled)
            pagamento.status = mp_status
            
            pedido = Pedido.query.get(pagamento.pedido_id)
            if pedido:
                if mp_status == 'approved':
                    pedido.status = 'PAGO'
                elif mp_status in ['rejected', 'cancelled']:
                    pedido.status = 'PAGAMENTO_REJEITADO'
            
            db.session.commit()
            # Lógica de WebSockets pode ser disparada aqui via evento (ex: Socket.IO)
            # socketio.emit('payment_status_update', {'pedido_id': str(pedido.id), 'status': mp_status}, room=str(pedido.usuario_id))

    return jsonify({'status': 'ok'}), 200


@pagamento_bp.route('/usuarios/cartoes', methods=['GET'])
@require_auth
def listar_cartoes():
    cartoes = CartaoCliente.query.filter_by(usuario_id=g.usuario_id).all()
    return jsonify({'cartoes': [c.to_dict() for c in cartoes]}), 200

@pagamento_bp.route('/pagamentos/<pedido_id>/status', methods=['GET'])
@require_auth
def status_pagamento(pedido_id):
    # Endpoint para suportar polling do frontend para atualização do status (especialmente Pix)
    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404
        
    if str(pedido.usuario_id) != str(g.usuario_id):
        return jsonify({'error': 'Acesso negado'}), 403
        
    pagamento = Pagamento.query.filter_by(pedido_id=pedido.id).order_by(Pagamento.data_criacao.desc()).first()
    if not pagamento:
        return jsonify({'status': 'Nenhum pagamento encontrado para este pedido'}), 404
        
    return jsonify({
        'pedido_id': str(pedido.id),
        'pagamento_id': str(pagamento.id),
        'metodo': pagamento.metodo,
        'status': pagamento.status,
        'status_pedido': pedido.status
    }), 200


    # Endpoint para testes de integração ao mercado pago devem ser colocados aqui ao final das rotas oficiais.
    
