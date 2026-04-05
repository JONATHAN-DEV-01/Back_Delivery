import unicodedata
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, func, case
from app.extensions import db
from app.models.produto import Produto
from app.models.categoria import Categoria
from app.models.restaurante import Restaurante

busca_bp = Blueprint('busca', __name__)

# ──────────────────────────────────────────────
# Utilitário: normaliza string (remove acentos + lower)
# RF-03 | Normalização de Caracteres
# ──────────────────────────────────────────────
def normalizar(texto: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()


# ──────────────────────────────────────────────
# GET /busca?q=<termo>&restaurante_id=<uuid>&categoria_id=<int>
#           &disponivel=<bool>&preco_min=<float>&preco_max=<float>
#           &page=<int>&per_page=<int>
# ──────────────────────────────────────────────
@busca_bp.route('/busca', methods=['GET'])
def buscar_produtos():
    """
    Motor de busca de produtos (Zupps).

    Query params obrigatórios:
        q            – termo de busca (mín. 3 caracteres – RN-02)

    Query params opcionais (filtros):
        restaurante_id  – filtra por restaurante específico
        categoria_id    – filtra por categoria
        disponivel      – true/false (padrão: true)
        preco_min       – preço mínimo
        preco_max       – preço máximo
        page            – página (padrão: 1)
        per_page        – itens por página (padrão: 20, máx: 50)
    """

    # ── 1. Parâmetro de busca ──────────────────
    q = request.args.get('q', '').strip()

    # RN-02: mínimo 3 caracteres
    if len(q) < 3:
        return jsonify({
            "message": "O parâmetro 'q' deve conter no mínimo 3 caracteres.",
            "results": [],
            "total": 0
        }), 400

    termo_normalizado = normalizar(q)

    # ── 2. Filtros opcionais ───────────────────
    restaurante_id = request.args.get('restaurante_id')
    categoria_id   = request.args.get('categoria_id')
    disponivel_str = request.args.get('disponivel', 'true').lower()
    disponivel     = disponivel_str in ('true', '1', 'yes')
    preco_min      = request.args.get('preco_min', type=float)
    preco_max      = request.args.get('preco_max', type=float)

    # ── 3. Paginação ───────────────────────────
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 20))))
    except ValueError:
        page, per_page = 1, 20

    # ── 4. Construção da query base ────────────
    # RF-01: varre nome e descrição
    # RF-03: usa unaccent via Python (normalização prévia) ou ILIKE no banco
    #        Usando ILIKE + REPLACE para compatibilidade máxima com PostgreSQL
    #        sem extensão unaccent obrigatória.
    like_nome = f"%{q}%"
    like_desc = f"%{q}%"

    match_nome = func.lower(
        func.replace(func.replace(func.replace(func.replace(func.replace(
            Produto.nome,
            'ã', 'a'), 'á', 'a'), 'â', 'a'), 'à', 'a'), 'ä', 'a')
    ).contains(termo_normalizado)

    match_desc = func.lower(
        func.replace(func.replace(func.replace(func.replace(func.replace(
            func.coalesce(Produto.descricao, ''),
            'ã', 'a'), 'á', 'a'), 'â', 'a'), 'à', 'a'), 'ä', 'a')
    ).contains(termo_normalizado)

    # RN-01: Scoring – peso 2 para nome, peso 1 para descrição
    score = case(
        (match_nome, 2),
        (match_desc, 1),
        else_=0
    )

    query = (
        db.session.query(Produto, score.label('score'))
        .filter(or_(match_nome, match_desc))
        .filter(Produto.disponivel == disponivel)  # RF-02 (disponibilidade)
    )

    # Filtros adicionais
    if restaurante_id:
        query = query.filter(Produto.restaurante_id == restaurante_id)

    if categoria_id:
        try:
            query = query.filter(Produto.categoria_id == int(categoria_id))
        except ValueError:
            pass

    if preco_min is not None:
        query = query.filter(Produto.preco >= preco_min)

    if preco_max is not None:
        query = query.filter(Produto.preco <= preco_max)

    # RN-01: ordena por score desc (nome > descrição)
    query = query.order_by(score.desc())

    # ── 5. Total + paginação ───────────────────
    total   = query.count()
    results = query.offset((page - 1) * per_page).limit(per_page).all()

    # ── 6. Serialização ────────────────────────
    # RF-04: inclui metadados do restaurante em cada produto
    produtos_json = []
    for produto, s in results:
        p = produto.to_dict()
        p['_score'] = s  # útil para debug

        # Metadados da loja (RF-04)
        restaurante = produto.restaurante if hasattr(produto, 'restaurante') else None
        if restaurante:
            p['restaurante'] = {
                'id':                    str(restaurante.id),
                'nome':                  restaurante.nome,
                'nota_avaliacao':        getattr(restaurante, 'nota_avaliacao', None),
                'tempo_entrega_minutos': getattr(restaurante, 'tempo_entrega_minutos', None),
                'valor_frete':           float(getattr(restaurante, 'valor_frete', 0) or 0),
            }
        else:
            p['restaurante'] = None

        # RF-05: preço promocional
        preco_promocional = getattr(produto, 'preco_promocional', None)
        if preco_promocional and float(preco_promocional) > 0:
            p['preco_original']     = float(produto.preco)
            p['preco_promocional']  = float(preco_promocional)
            p['em_promocao']        = True
        else:
            p['em_promocao'] = False

        produtos_json.append(p)

    # ── 7. Fallback (RN-03) ────────────────────
    fallback = None
    if total == 0:
        # 7a. Categorias mais acessadas (simplificado: top 5 com mais produtos)
        top_cats = (
            db.session.query(Categoria, func.count(Produto.id).label('qtd'))
            .join(Produto, Produto.categoria_id == Categoria.id)
            .filter(Categoria.tipo == 'PRODUTO')
            .group_by(Categoria.id)
            .order_by(func.count(Produto.id).desc())
            .limit(5)
            .all()
        )

        # 7b. Lojas abertas próximas (is_open = true quando disponível no model)
        lojas_abertas = (
            db.session.query(Restaurante)
            .filter(getattr(Restaurante, 'is_open', True) == True)  # noqa: E712
            .limit(5)
            .all()
        )

        fallback = {
            "sugestoes_categorias": [c.to_dict() for c, _ in top_cats],
            "lojas_proximas": [
                {
                    "id":   str(r.id),
                    "nome": r.nome,
                }
                for r in lojas_abertas
            ]
        }

    # ── 8. Resposta final ──────────────────────
    response = {
        "q":        q,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page if total > 0 else 0,
        "results":  produtos_json,
    }

    if fallback:
        response["fallback"] = fallback
        response["message"]  = "Nenhum produto encontrado. Confira as sugestões abaixo."

    return jsonify(response), 200