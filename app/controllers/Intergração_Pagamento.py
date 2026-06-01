import os
import pytz
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
from app.services.email_service import EmailService

pagamento_bp = Blueprint('pagamento', __name__)

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
MP_URL = "https://api.mercadopago.com/v1"

def get_mp_headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }


def _montar_dados_nota(pedido: Pedido, usuario: Usuario, restaurante: Restaurante) -> dict:
    """Monta o dicionário de dados para a nota fiscal a partir dos objetos do banco."""
    endereco = pedido.endereco_entrega_snapshot or {}
    itens_nf = []
    for item in pedido.itens:
        itens_nf.append({
            "nome": item.nome_produto,
            "quantidade": item.quantidade,
            "preco_unitario_centavos": item.preco_unitario_base_centavos,
            "adicionais": [
                {
                    "nome": ad.get("nome", ""),
                    "preco_unitario_centavos": ad.get("preco_unitario_centavos", 0)
                }
                for ad in (item.adicionais or [])
            ]
        })

    return {
        "numero_pedido": str(pedido.id),
        "data_emissao": datetime.utcnow(),
        "forma_pagamento": pedido.forma_pagamento,
        "tipo_entrega": getattr(pedido, "tipo_entrega", "MOTO"),
        "status_pagamento": "APROVADO",
        "cliente": {
            "nome": usuario.nome or "",
            "sobrenome": usuario.sobrenome or "",
            "cpf": usuario.cpf or "",
            "email": usuario.email or ""
        },
        "endereco_entrega": {
            "logradouro": endereco.get("logradouro", ""),
            "numero": endereco.get("numero", ""),
            "bairro": endereco.get("bairro", ""),
            "cidade": endereco.get("cidade", ""),
            "estado": endereco.get("estado", ""),
            "complemento": endereco.get("complemento", "")
        },
        "restaurante": {
            "nome_fantasia": restaurante.nome_fantasia or "",
            "razao_social": restaurante.razao_social or "",
            "cnpj": restaurante.cnpj or "",
            "logradouro": restaurante.logradouro or "",
            "numero": restaurante.numero or "",
            "bairro": restaurante.bairro or "",
            "cidade": restaurante.cidade or "",
            "estado": restaurante.estado or "",
            "cep": restaurante.cep or "",
            "telefone": restaurante.telefone or "",
            "email": restaurante.email or ""
        },
        "itens": itens_nf,
        "subtotal_centavos": pedido.subtotal_centavos,
        "taxa_entrega_centavos": pedido.taxa_entrega_centavos,
        "taxa_moto_flash_centavos": getattr(pedido, "taxa_moto_flash_centavos", 0),
        "desconto_centavos": pedido.desconto_centavos,
        "total_centavos": pedido.total_centavos
    }


def _enviar_nota_fiscal(pedido: Pedido, usuario: Usuario, restaurante: Restaurante):
    """Envia a nota fiscal por email. Erros são capturados sem interromper o fluxo."""
    try:
        dados = _montar_dados_nota(pedido, usuario, restaurante)
        EmailService.send_nota_fiscal(usuario.email, dados)
    except Exception as e:
        print(f"[NOTA FISCAL] Erro ao enviar para {getattr(usuario, 'email', '?')}: {e}")


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

    restaurante = Restaurante.query.get(pedido.restaurante_id)
    if not restaurante.is_open_agora:
        return jsonify({'error': 'O restaurante está fechado no momento.'}), 400

    if expected_price is not None and int(expected_price) != pedido.total_centavos:
        return jsonify({'error': 'Ocorreu uma alteração no preço do pedido. Por favor, revise seu carrinho.'}), 400

    usuario = Usuario.query.get(g.usuario_id)
    email = payer.get('email')
    customer_id = None

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
            res_card = requests.post(f"{MP_URL}/customers/{customer_id}/cards", json={"token": token}, headers=get_mp_headers())
            if res_card.status_code in [200, 201]:
                card_data = res_card.json()
                mp_card_id = card_data.get('id')
                
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

    transaction_amount = float(pedido.total_centavos) / 100.0

    pm_id = payment_method_id.lower().strip()
    if pm_id == 'mastercard':
        pm_id = 'master'
    elif pm_id == 'american express':
        pm_id = 'amex'
    elif pm_id == 'diners club':
        pm_id = 'diners'

    payload = {
        "transaction_amount": transaction_amount,
        "token": token,
        "description": f"Pedido {pedido.id}",
        "installments": installments,
        "payment_method_id": pm_id,
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

    # Envia nota fiscal se pagamento aprovado
    if status == 'approved':
        _enviar_nota_fiscal(pedido, usuario, restaurante)

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

    restaurante = Restaurante.query.get(pedido.restaurante_id)
    if not restaurante.is_open_agora:
        return jsonify({'error': 'O restaurante está fechado no momento.'}), 400

    if expected_price is not None and int(expected_price) != pedido.total_centavos:
        return jsonify({'error': 'Ocorreu uma alteração no preço do pedido. Por favor, revise seu carrinho.'}), 400

    usuario = Usuario.query.get(g.usuario_id)
    transaction_amount = float(pedido.total_centavos) / 100.0

    cpf_payer = payer.get('identification', {}).get('number', '')
    if not cpf_payer:
        cpf_payer = getattr(usuario, 'cpf', None) or ''
    cpf_payer = cpf_payer.replace('.', '').replace('-', '').strip()

    email_payer = payer.get('email') or usuario.email or 'pagador@zuppseats.com'

    expiracao = (
        datetime.now(pytz.timezone('America/Sao_Paulo')) + timedelta(minutes=30)
    ).strftime('%Y-%m-%dT%H:%M:%S.000-03:00')

    payload = {
        "transaction_amount": transaction_amount,
        "payment_method_id": "pix",
        "description": f"Pedido {pedido.id}",
        "payer": {
            "email": email_payer,
            "first_name": payer.get('first_name') or (usuario.nome or 'Cliente'),
            "last_name": payer.get('last_name') or (usuario.sobrenome or 'Zupps'),
            "identification": {
                "type": "CPF",
                "number": cpf_payer
            }
        },
        "date_of_expiration": expiracao
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

    # PIX aprovado instantaneamente (raro, mas possível em sandbox)
    if status == 'approved':
        _enviar_nota_fiscal(pedido, usuario, restaurante)

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
    data_id = request.args.get('data.id')
    if not data_id:
        json_data = request.get_json() or {}
        data_id = json_data.get('data', {}).get('id')

    if not data_id:
        return jsonify({'status': 'ignored'}), 200

    res = requests.get(f"{MP_URL}/payments/{data_id}", headers=get_mp_headers())
    if res.status_code == 200:
        pay_data = res.json()
        mp_status = pay_data.get('status')
        
        pagamento = Pagamento.query.filter_by(mercado_pago_id=int(data_id)).first()
        if pagamento:
            pagamento.status = mp_status
            
            pedido = Pedido.query.get(pagamento.pedido_id)
            if pedido:
                foi_aprovado_agora = (pedido.status != 'PAGO' and mp_status == 'approved')

                if mp_status == 'approved':
                    pedido.status = 'PAGO'
                elif mp_status in ['rejected', 'cancelled']:
                    pedido.status = 'PAGAMENTO_REJEITADO'
            
            db.session.commit()

            # Envia nota fiscal quando o webhook confirma aprovação do PIX
            if pedido and foi_aprovado_agora:
                try:
                    usuario = Usuario.query.get(pedido.usuario_id)
                    restaurante = Restaurante.query.get(pedido.restaurante_id)
                    if usuario and restaurante:
                        _enviar_nota_fiscal(pedido, usuario, restaurante)
                except Exception as e:
                    print(f"[WEBHOOK] Erro ao enviar nota fiscal: {e}")

    return jsonify({'status': 'ok'}), 200


@pagamento_bp.route('/usuarios/cartoes', methods=['GET'])
@require_auth
def listar_cartoes():
    cartoes = CartaoCliente.query.filter_by(usuario_id=g.usuario_id).all()
    return jsonify({'cartoes': [c.to_dict() for c in cartoes]}), 200

@pagamento_bp.route('/pagamentos/<pedido_id>/status', methods=['GET'])
@require_auth
def status_pagamento(pedido_id):
    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404
        
    if str(pedido.usuario_id) != str(g.usuario_id):
        return jsonify({'error': 'Acesso negado'}), 403
        
    pagamento = Pagamento.query.filter_by(pedido_id=pedido.id).order_by(Pagamento.data_criacao.desc()).first()
    if not pagamento:
        return jsonify({'status': 'Nenhum pagamento encontrado para este pedido'}), 404
        
    if pagamento.status in ['pending', 'in_process'] and pagamento.mercado_pago_id:
        try:
            res = requests.get(f"{MP_URL}/payments/{pagamento.mercado_pago_id}", headers=get_mp_headers())
            if res.status_code == 200:
                pay_data = res.json()
                mp_status = pay_data.get('status')
                if mp_status and mp_status != pagamento.status:
                    pagamento.status = mp_status
                    foi_aprovado_agora = (pedido.status != 'PAGO' and mp_status == 'approved')
                    if mp_status == 'approved':
                        pedido.status = 'PAGO'
                    elif mp_status in ['rejected', 'cancelled']:
                        pedido.status = 'PAGAMENTO_REJEITADO'
                    
                    db.session.commit()
                    
                    if foi_aprovado_agora:
                        restaurante = Restaurante.query.get(pedido.restaurante_id)
                        usuario = Usuario.query.get(pedido.usuario_id)
                        if restaurante and usuario:
                            _enviar_nota_fiscal(pedido, usuario, restaurante)
        except Exception as e:
            print(f"Erro ao verificar MP direto: {e}")
            
    return jsonify({
        'pedido_id': str(pedido.id),
        'pagamento_id': str(pagamento.id),
        'metodo': pagamento.metodo,
        'status': pagamento.status,
        'status_pedido': pedido.status
    }), 200


    # Endpoint para testes de integração ao mercado pago devem ser colocados aqui ao final das rotas oficiais.
