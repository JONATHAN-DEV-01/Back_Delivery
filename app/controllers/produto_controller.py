import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.produto import Produto
from app.models.adicional import GrupoAdicionais, Adicional

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
                ext = file.filename.rsplit('.', 1)[1].lower()
                imagem_filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, imagem_filename)
                file.save(filepath)

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

        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and allowed_file(file.filename):
                # Deleta a imagem antiga se existir
                if produto.imagem:
                    old_path = os.path.join(UPLOAD_FOLDER, produto.imagem)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                imagem_filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, imagem_filename)
                file.save(filepath)
                produto.imagem = imagem_filename

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
        if produto.imagem:
            old_path = os.path.join(UPLOAD_FOLDER, produto.imagem)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception:
                    pass

        db.session.delete(produto)
        db.session.commit()
        
        return jsonify({"message": "Produto excluído com sucesso."}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno ao deletar produto: {str(e)}"}), 500

# 6. GET /produtos/<id>/grupos-adicionais
@produto_bp.route('/produtos/<uuid:id>/grupos-adicionais', methods=['GET'])
def get_grupos_adicionais(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404
        
    grupos = GrupoAdicionais.query.filter_by(produto_id=produto.id).all()
    return jsonify([g.to_dict() for g in grupos]), 200

# 7. POST /produtos/<id>/grupos-adicionais
@produto_bp.route('/produtos/<uuid:id>/grupos-adicionais', methods=['POST'])
def sync_grupos_adicionais(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"message": "Produto não encontrado."}), 404

    # Recebe state completo dos grupos
    data = request.get_json()
    if data is None or not isinstance(data, list):
        return jsonify({"message": "Esperado um JSON Array com os grupos e adicionais."}), 400

    try:
        # Busca os grupos já existentes para esse produto no DB
        grupos_existentes = GrupoAdicionais.query.filter_by(produto_id=produto.id).all()
        grupos_dict = {g.id: g for g in grupos_existentes}

        grupos_recebidos_ids = []

        for grp_data in data:
            grp_id = grp_data.get('id')
            
            # Se já existir o ID, dar Update
            if grp_id and grp_id in grupos_dict:
                grupo = grupos_dict[grp_id]
                grupo.nome = grp_data.get('nome', grupo.nome)
                grupo.min_selecao = int(grp_data.get('min_selecao', grupo.min_selecao))
                grupo.max_selecao = int(grp_data.get('max_selecao', grupo.max_selecao))
                grupo.obrigatorio = bool(grp_data.get('obrigatorio', grupo.obrigatorio))
                grupos_recebidos_ids.append(grp_id)
            else:
                # Insert novo Grupo
                grupo = GrupoAdicionais(
                    nome=grp_data.get('nome', 'Sem nome'),
                    min_selecao=int(grp_data.get('min_selecao', 0)),
                    max_selecao=int(grp_data.get('max_selecao', 1)),
                    obrigatorio=bool(grp_data.get('obrigatorio', False)),
                    produto_id=produto.id
                )
                db.session.add(grupo)
                db.session.flush() # obtemmos novo ID provisório DB sequence
                grupos_recebidos_ids.append(grupo.id)

            # --- Sincronizar Adicionais aninhados no Grupo ---
            # Flush() anterior nos garante que var 'grupo.id' agora vale pro relationship
            adics_existentes = Adicional.query.filter_by(grupo_id=grupo.id).all()
            adics_dict = {a.id: a for a in adics_existentes}
            
            adicionais_recebidos = grp_data.get('adicionais', [])
            adics_recebidos_ids = []
            
            for ad_data in adicionais_recebidos:
                ad_id = ad_data.get('id')
                
                # Update Adicional
                if ad_id and ad_id in adics_dict:
                    adic = adics_dict[ad_id]
                    adic.nome = ad_data.get('nome', adic.nome)
                    adic.preco = float(ad_data.get('preco', adic.preco))
                    adic.disponivel = bool(ad_data.get('disponivel', adic.disponivel))
                    adics_recebidos_ids.append(ad_id)
                else:
                    # Insert Adicional
                    adic = Adicional(
                        nome=ad_data.get('nome', 'Sem nome'),
                        preco=float(ad_data.get('preco', 0.0)),
                        disponivel=bool(ad_data.get('disponivel', True)),
                        grupo_id=grupo.id
                    )
                    db.session.add(adic)
                    db.session.flush()
                    adics_recebidos_ids.append(adic.id)
            
            # Deleta órfãos Adicionais (aqueles no BD q não vieram na listagem para este grupo)
            for old_ad_id, old_ad in adics_dict.items():
                if old_ad_id not in adics_recebidos_ids:
                    db.session.delete(old_ad)

        # Deleta órfãos Grupos (aqueles no BD q não vieram na listagem raiz)
        for old_grp_id, old_grp in grupos_dict.items():
            if old_grp_id not in grupos_recebidos_ids:
                db.session.delete(old_grp)

        db.session.commit()
        return jsonify({"message": "Sucesso", "grupos_sincronizados": len(grupos_recebidos_ids)}), 200

    except SQLAlchemyError as db_err:
        db.session.rollback()
        return jsonify({"message": f"Erro no banco de dados durante a sincronização: {str(db_err)}"}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erro interno ao sincronizar: {str(e)}"}), 500
