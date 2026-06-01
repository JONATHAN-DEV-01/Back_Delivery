import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.services.supabase_storage import upload_file_to_supabase, delete_file_from_supabase
from app.models.produto import Produto
from app.models.adicional import Adicional
from app.models.produto_ingrediente import ProdutoIngrediente
import json

produto_bp = Blueprint('produto', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../uploads/produtos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 1. GET /produtos
@produto_bp.route('/produtos', methods=['GET'])
def get_produtos():
    restaurante_id = request.args.get('restaurante_id')
    if not restaurante_id:
        return jsonify({"message": "O parâmetro restaurante_id é obrigatório."}), 400
    
    produtos = Produto.query.filter_by(restaurante_id=restaurante_id).all()
    # Retorna JSON com array enumerando propriedades chaves
    return jsonify([p.to_dict() for p in produtos]), 200

# 2. GET /produtos/<id>
@produto_bp.route('/produtos/<uuid:id>', methods=['GET'])
def get_produto(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404
        
    return jsonify(produto.to_dict()), 200

# 3. POST /produtos
@produto_bp.route('/produtos', methods=['POST'])
def create_produto():
    data = request.form.to_dict()
    
    nome = data.get('nome')
    preco = data.get('preco')
    restaurante_id = data.get('restaurante_id')
    categoria_input = data.get('categoria_id') or data.get('categoria') # Pode vir com o name da categoria do select/text
    
    if not nome or not preco or not restaurante_id or not categoria_input:
        return jsonify({"message": "Campos cruciais como Nome, Preço, Categoria e Restaurante são obrigatórios."}), 400
        
    try:
        if restaurante_id in ('undefined', 'null'):
            return jsonify({"message": "restaurante_id não está sendo enviado corretamente pelo Frontend."}), 400
            
        uuid.UUID(str(restaurante_id)) # Valida se é um UUID correto
        
        # Trata vírgulas antes de converter para float para evitar ValueErrors comuns
        preco_float = float(str(preco).replace(',', '.'))
        
        disponivel_str = str(data.get('disponivel', 'true')).lower()
        disponivel = disponivel_str in ('true', '1', 'yes')
        
        imagem_filename = None
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and allowed_file(file.filename):
                # O filename customizado com UUID para evitar colisão pode ser feito setando o nome do arquivo,
                # e o upload_file_to_supabase vai utilizar o secure_filename nele
                ext = file.filename.rsplit('.', 1)[1].lower()
                file.filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                imagem_filename = upload_file_to_supabase(file, folder='produtos')

        # Lidar com categoria enviada como string ou ID
        cat_id = None
        from app.models.categoria import Categoria
        if str(categoria_input).isdigit():
            cat_id = int(categoria_input)
        else:
            categoria_nome_limpo = str(categoria_input).strip()
            categoria = Categoria.query.filter(Categoria.nome.ilike(categoria_nome_limpo)).first()
            if categoria:
                cat_id = categoria.id
            else:
                nova_cat = Categoria(nome=categoria_nome_limpo.title(), tipo='PRODUTO')
                db.session.add(nova_cat)
                db.session.flush()
                cat_id = nova_cat.id

        novo_produto = Produto(
            nome=nome.strip(),
            descricao=data.get('descricao', '').strip() if data.get('descricao') else None,
            preco=preco_float,
            imagem=imagem_filename,
            disponivel=disponivel,
            categoria_id=cat_id,
            restaurante_id=restaurante_id
        )

        db.session.add(novo_produto)
        db.session.flush() # Flush to get the ID

        # Tratar Ficha Técnica
        ficha_tecnica_str = data.get('ficha_tecnica')
        if ficha_tecnica_str:
            try:
                ingredientes = json.loads(ficha_tecnica_str)
                for item in ingredientes:
                    pi = ProdutoIngrediente(
                        produto_id=novo_produto.id,
                        ingrediente_id=item['ingrediente_id'],
                        quantidade_necessaria=item['quantidade_necessaria']
                    )
                    db.session.add(pi)
            except Exception as e:
                pass # Ignora erro de JSON se for malformado

        db.session.commit()
    
        return jsonify({"message": "Produto criado com sucesso", "produto": novo_produto.to_dict()}), 201

    except ValueError as e:
        return jsonify({"message": f"Erro de conversão numérico ou UUID inválido: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno (Verifique se o backend tem a tabela Categoria): {str(e)}"}), 500

# 4. PATCH /produtos/<id>
@produto_bp.route('/produtos/<uuid:id>', methods=['PATCH'])
def update_produto(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404

    data = request.form.to_dict()

    try:
        if 'nome' in data:
            produto.nome = data['nome'].strip()
        if 'descricao' in data:
            produto.descricao = data['descricao'].strip() if data['descricao'] else None
        if 'preco' in data:
            preco_formatado = str(data['preco']).replace(',', '.')
            produto.preco = float(preco_formatado)

        categoria_input = data.get('categoria_id') or data.get('categoria')
        if categoria_input:
            from app.models.categoria import Categoria
            if str(categoria_input).isdigit():
                produto.categoria_id = int(categoria_input)
            else:
                categoria_nome_limpo = str(categoria_input).strip()
                categoria = Categoria.query.filter(Categoria.nome.ilike(categoria_nome_limpo)).first()
                if categoria:
                    produto.categoria_id = categoria.id
                else:
                    nova_cat = Categoria(nome=categoria_nome_limpo.title(), tipo='PRODUTO')
                    db.session.add(nova_cat)
                    db.session.flush()
                    produto.categoria_id = nova_cat.id

        if 'disponivel' in data:
            disponivel_str = str(data['disponivel']).lower()
            produto.disponivel = disponivel_str in ('true', '1', 'yes')

        # RF-01: Sincronizar campo quantidade se enviado
        if 'quantidade' in data:
            try:
                nova_qtd = max(0, int(data['quantidade']))
                produto.quantidade = nova_qtd
                # Sincronizar disponibilidade automaticamente
                if nova_qtd == 0:
                    produto.disponivel = False
                elif nova_qtd > 0 and not produto.disponivel:
                    produto.disponivel = True
            except (ValueError, TypeError):
                pass  # Campo inválido — ignorar silenciosamente

        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and allowed_file(file.filename):
                if produto.imagem:
                    delete_file_from_supabase(produto.imagem, folder='produtos')
                ext = file.filename.rsplit('.', 1)[1].lower()
                file.filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                produto.imagem = upload_file_to_supabase(file, folder='produtos')

        # Tratar Ficha Técnica
        ficha_tecnica_str = data.get('ficha_tecnica')
        if ficha_tecnica_str:
            try:
                ingredientes = json.loads(ficha_tecnica_str)
                # Remove ingredientes antigos
                ProdutoIngrediente.query.filter_by(produto_id=produto.id).delete()
                # Adiciona novos
                for item in ingredientes:
                    pi = ProdutoIngrediente(
                        produto_id=produto.id,
                        ingrediente_id=item['ingrediente_id'],
                        quantidade_necessaria=item['quantidade_necessaria']
                    )
                    db.session.add(pi)
            except Exception as e:
                pass # Ignora erro de JSON se for malformado

        db.session.commit()
        return jsonify({"message": "Produto atualizado com sucesso", "produto": produto.to_dict()}), 200

    except ValueError as e:
        return jsonify({"message": f"Erro de conversão numérico ou dado inválido: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno: {str(e)}"}), 500

# 5. DELETE /produtos/<id>
@produto_bp.route('/produtos/<uuid:id>', methods=['DELETE'])
def delete_produto(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404

    try:
        # Remove a imagem do Supabase Storage antes de deletar o produto
        if produto.imagem:
            delete_file_from_supabase(produto.imagem)

        db.session.delete(produto)
        db.session.commit()
        
        return jsonify({"message": "Produto excluído com sucesso."}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno ao deletar produto: {str(e)}"}), 500

# 6. GET /produtos/<id>/adicionais
@produto_bp.route('/produtos/<uuid:id>/adicionais', methods=['GET'])
def get_adicionais_produto(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404
        
    return jsonify([a.to_dict() for a in produto.adicionais]), 200

# 7. POST /produtos/<id>/adicionais
@produto_bp.route('/produtos/<uuid:id>/adicionais', methods=['POST'])
def sync_adicionais_produto(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404

    # Recebe array de IDs de adicionais
    data = request.get_json()
    if data is None or not isinstance(data, list):
        return jsonify({"message": "Esperado um JSON Array com os IDs dos adicionais."}), 400

    try:
        # Busca os adicionais no BD
        adicionais_db = Adicional.query.filter(Adicional.id.in_(data)).all()
        
        # Atualiza a relação
        produto.adicionais = adicionais_db
        db.session.commit()
        
        return jsonify({"message": "Sucesso", "adicionais_sincronizados": len(produto.adicionais)}), 200

    except SQLAlchemyError as db_err:
        db.session.rollback()
        return jsonify({"message": f"Erro no banco de dados durante a sincronização: {str(db_err)}"}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno ao sincronizar: {str(e)}"}), 500
