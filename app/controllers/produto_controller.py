import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.produto import Produto
from app.models.adicional import GrupoAdicionais, Adicional
from app.models.categoria import Categoria

produto_bp = Blueprint('produto', __name__)

UPLOAD_FOLDER = 'uploads/produtos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024 # Variável não mais usada para limite forte

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@produto_bp.route('/produtos', methods=['POST'])
def create_produto():
    data = request.form.to_dict()
    required = ('nome', 'preco', 'categoria_id', 'restaurante_id')
    
    if not all(k in data for k in required):
        return jsonify({"error": "Dados obrigatórios ausentes."}), 400

    imagem_path = None
    if 'imagem' in request.files:
        file = request.files['imagem']
        if file and allowed_file(file.filename):
            # Validação de tamanho removida a pedido do usuário
            
            filename = secure_filename(f"p_{data['restaurante_id']}_{file.filename}")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            imagem_path = filepath

    novo_produto = Produto(
        nome=data['nome'],
        descricao=data.get('descricao'),
        preco=data['preco'],
        imagem=imagem_path,
        categoria_id=data['categoria_id'],
        restaurante_id=data['restaurante_id']
    )

    db.session.add(novo_produto)
    db.session.commit()

    return jsonify(novo_produto.to_dict()), 201

@produto_bp.route('/produtos/<uuid:id>/disponibilidade', methods=['PATCH'])
def update_disponibilidade(id):
    produto = Produto.query.get(id)
    if not produto:
        return jsonify({"error": "Produto não encontrado."}), 404
        
    data = request.get_json()
    if 'disponivel' not in data:
        return jsonify({"error": "Informe a disponibilidade (true/false)."}), 400
        
    produto.disponivel = bool(data['disponivel'])
    db.session.commit()
    
    return jsonify({"message": "Disponibilidade atualizada.", "disponivel": produto.disponivel}), 200

@produto_bp.route('/produtos/<uuid:produto_id>/grupos-adicionais', methods=['POST'])
def add_grupo_adicionais(produto_id):
    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({"error": "Produto não encontrado."}), 404
        
    data = request.get_json()
    # Expects {nome, min_quantidade, max_quantidade, adicionais: [{nome, preco}]}
    if not data or 'nome' not in data:
         return jsonify({"error": "Dados do grupo ausentes."}), 400
         
    novo_grupo = GrupoAdicionais(
        nome=data['nome'],
        min_quantidade=data.get('min_quantidade', 0),
        max_quantidade=data.get('max_quantidade', 1),
        produto_id=produto_id
    )
    db.session.add(novo_grupo)
    db.session.flush() # Para pegar o ID do grupo
    
    if 'adicionais' in data:
        for a in data['adicionais']:
            novo_adicional = Adicional(
                nome=a['nome'],
                preco=a.get('preco', 0.0),
                grupo_id=novo_grupo.id
            )
            db.session.add(novo_adicional)
            
    db.session.commit()
    return jsonify(novo_grupo.to_dict()), 201
