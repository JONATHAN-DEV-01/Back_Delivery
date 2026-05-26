import os
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, case
from app.extensions import db
from app.models.pedido import Pedido, ItemPedido
from app.models.restaurante import Restaurante

dashboard_bp = Blueprint('dashboard', __name__)


def require_restaurante_auth(f):
    """Decorator that requires a restaurant JWT token."""
    from functools import wraps
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

        restaurante_id = payload.get('restaurante_id')
        if not restaurante_id:
            return jsonify({'error': 'Token não contém identidade de restaurante.'}), 401

        g.restaurante_id = restaurante_id
        return f(*args, **kwargs)

    return decorated


@dashboard_bp.route('/dashboard/restaurantes', methods=['GET'])
@require_restaurante_auth
def listar_restaurantes():
    """Lista todos os restaurantes (para o filtro do dashboard)."""
    restaurantes = Restaurante.query.filter_by(ativo=True).all()
    return jsonify([
        {'id': str(r.id), 'nome': r.nome_fantasia}
        for r in restaurantes
    ]), 200


@dashboard_bp.route('/dashboard/kpis', methods=['GET'])
@require_restaurante_auth
def kpis():
    """
    Retorna KPIs agregados de pedidos para um período.
    Query params:
      - periodo: 7 | 30 | 90 (dias). Default: 30
      - restaurante_id: UUID ou 'all'. Default: 'all' (todos)
      - data_inicio: ISO date string (opcional, para período personalizado)
      - data_fim:    ISO date string (opcional)
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    # Calcular intervalo de datas
    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    # Base query de pedidos com status PAGO ou ENTREGUE
    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )

    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.all()

    total_pedidos = len(pedidos)
    receita_bruta = sum(p.total_centavos for p in pedidos) / 100.0
    ticket_medio = (receita_bruta / total_pedidos) if total_pedidos > 0 else 0.0

    # Taxa de cancelamento: pedidos cancelados / (pedidos válidos + cancelados)
    query_cancel = Pedido.query.filter(
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query_cancel = query_cancel.filter(Pedido.restaurante_id == restaurante_id)

    total_geral = query_cancel.count()
    cancelados = query_cancel.filter(Pedido.status == 'CANCELADO').count()
    taxa_cancelamento = (cancelados / total_geral * 100) if total_geral > 0 else 0.0

    return jsonify({
        'total_pedidos': total_pedidos,
        'receita_bruta': round(receita_bruta, 2),
        'ticket_medio': round(ticket_medio, 2),
        'taxa_cancelamento': round(taxa_cancelamento, 2),
        'periodo_inicio': data_inicio.isoformat(),
        'periodo_fim': data_fim.isoformat(),
    }), 200


@dashboard_bp.route('/dashboard/evolucao', methods=['GET'])
@require_restaurante_auth
def evolucao_faturamento():
    """
    Retorna evolução diária do faturamento no período.
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.all()

    # Agrupar por dia
    from collections import defaultdict
    por_dia = defaultdict(float)
    for p in pedidos:
        dia = p.data_criacao.strftime('%d/%m')
        por_dia[dia] += p.total_centavos / 100.0

    # Gerar todos os dias no intervalo
    resultado = []
    delta = data_fim - data_inicio
    for i in range(delta.days + 1):
        dia = (data_inicio + timedelta(days=i)).strftime('%d/%m')
        resultado.append({'dia': dia, 'valor': round(por_dia.get(dia, 0), 2)})

    return jsonify(resultado), 200


@dashboard_bp.route('/dashboard/top-produtos', methods=['GET'])
@require_restaurante_auth
def top_produtos():
    """
    Retorna top 8 produtos mais vendidos no período.
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']

    # Join ItemPedido -> Pedido para filtrar por período e restaurante
    query = db.session.query(
        ItemPedido.nome_produto,
        func.sum(ItemPedido.quantidade).label('qtd'),
        func.sum(ItemPedido.preco_total_item_centavos).label('receita_centavos')
    ).join(Pedido, ItemPedido.pedido_id == Pedido.id).filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )

    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    resultados = query.group_by(ItemPedido.nome_produto)\
                      .order_by(func.sum(ItemPedido.quantidade).desc())\
                      .limit(8).all()

    return jsonify([
        {
            'nome': r.nome_produto,
            'qtd': int(r.qtd),
            'receita': round(r.receita_centavos / 100.0, 2)
        }
        for r in resultados
    ]), 200


@dashboard_bp.route('/dashboard/horarios', methods=['GET'])
@require_restaurante_auth
def horarios_pico():
    """
    Retorna volume de pedidos por hora do dia.
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.all()

    from collections import defaultdict
    por_hora = defaultdict(int)
    for p in pedidos:
        hora = p.data_criacao.hour
        por_hora[hora] += 1

    resultado = []
    for h in range(7, 24):
        resultado.append({
            'hora': f'{str(h).zfill(2)}h',
            'pedidos': por_hora.get(h, 0)
        })

    return jsonify(resultado), 200


@dashboard_bp.route('/dashboard/ultimas-transacoes', methods=['GET'])
@require_restaurante_auth
def ultimas_transacoes():
    """
    Retorna as últimas 10 transações (pedidos) do período.
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.order_by(Pedido.data_criacao.desc()).limit(10).all()

    METODO_LABELS = {
        'PIX': 'Pix',
        'CASH': 'Dinheiro',
        'CARD_MACHINE': 'Maquininha',
        'CREDIT_CARD': 'Cartão',
        'DEBIT_CARD': 'Débito',
    }

    return jsonify([
        {
            'id': f'#{str(p.id)[:8].upper()}',
            'data': p.data_criacao.strftime('%d/%m %H:%M'),
            'metodo': METODO_LABELS.get(p.forma_pagamento, p.forma_pagamento),
            'valor': round(p.total_centavos / 100.0, 2),
            'status': p.status,
        }
        for p in pedidos
    ]), 200


@dashboard_bp.route('/dashboard/regioes', methods=['GET'])
@require_restaurante_auth
def regioes():
    """
    Agrega pedidos por bairro a partir do endereco_entrega_snapshot.
    Retorna top 10 regiões por receita.
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.all()

    from collections import defaultdict
    regioes_map = defaultdict(lambda: {'pedidos': 0, 'receita': 0.0, 'cidade': ''})

    for p in pedidos:
        snap = p.endereco_entrega_snapshot or {}
        bairro = snap.get('bairro') or 'Não informado'
        cidade = snap.get('cidade') or ''
        regioes_map[bairro]['pedidos'] += 1
        regioes_map[bairro]['receita'] += p.total_centavos / 100.0
        if not regioes_map[bairro]['cidade']:
            regioes_map[bairro]['cidade'] = cidade

    resultado = sorted(
        [
            {
                'bairro': bairro,
                'cidade': dados['cidade'],
                'pedidos': dados['pedidos'],
                'receita': round(dados['receita'], 2),
            }
            for bairro, dados in regioes_map.items()
        ],
        key=lambda x: x['receita'],
        reverse=True
    )[:10]

    return jsonify(resultado), 200


@dashboard_bp.route('/dashboard/heatmap', methods=['GET'])
@require_restaurante_auth
def heatmap():
    """
    Retorna matriz dia_semana x hora para o mapa de calor.
    Formato: { "Dom": [c0, c1, ..., c23], "Seg": [...], ... }
    """
    periodo = request.args.get('periodo', '30')
    restaurante_id = request.args.get('restaurante_id', 'all')
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    now = datetime.utcnow()
    if data_inicio_str and data_fim_str:
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = datetime.fromisoformat(data_fim_str) + timedelta(days=1)
        except ValueError:
            data_inicio = now - timedelta(days=30)
            data_fim = now
    else:
        dias = int(periodo) if periodo.isdigit() else 30
        data_inicio = now - timedelta(days=dias)
        data_fim = now

    STATUS_VALIDOS = ['PAGO', 'ENTREGUE', 'A_CAMINHO', 'SAIU_ENTREGA']
    query = Pedido.query.filter(
        Pedido.status.in_(STATUS_VALIDOS),
        Pedido.data_criacao >= data_inicio,
        Pedido.data_criacao <= data_fim
    )
    if restaurante_id != 'all':
        query = query.filter(Pedido.restaurante_id == restaurante_id)

    pedidos = query.all()

    # weekday: 0=Mon..6=Sun in Python; we want Dom=0, Seg=1, ..., Sab=6
    DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
    matrix = {d: [0] * 24 for d in DIAS}

    for p in pedidos:
        # Python weekday: Mon=0 .. Sun=6; convert to Dom=0..Sab=6
        py_day = p.data_criacao.weekday()  # 0=Mon..6=Sun
        dia_idx = (py_day + 1) % 7         # Mon->1, ..., Sun->0
        hora = p.data_criacao.hour
        matrix[DIAS[dia_idx]][hora] += 1

    # Also return tabela consolidada (hour totals across all days)
    tabela = []
    for h in range(24):
        total = sum(matrix[d][h] for d in DIAS)
        tabela.append({'horario': f'{str(h).zfill(2)}:00', 'pedidos': total})

    return jsonify({'matrix': matrix, 'tabela': tabela}), 200
