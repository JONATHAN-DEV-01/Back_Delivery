import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.restaurante import Restaurante
from app.models.horario_funcionamento import HorarioFuncionamento
from app.models.categoria import Categoria
from app.utils.validators import validate_cnpj, validate_phone, validate_email
from app.services.supabase_storage import upload_file_to_supabase

restaurante_bp = Blueprint('restaurante', __name__)

UPLOAD_FOLDER = 'uploads/logos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@restaurante_bp.route('/restaurantes', methods=['POST'])
def create_restaurante():
    data = request.form.to_dict()
    required = ('nome_fantasia', 'razao_social', 'cnpj', 'endereco', 'telefone', 'email')
    
    if not all(k in data for k in required):
        return jsonify({"error": "Dados obrigatórios ausentes."}), 400

    if not validate_cnpj(data['cnpj']):
        return jsonify({"error": "CNPJ inválido."}), 400
    
    if not validate_phone(data['telefone']):
        return jsonify({"error": "Telefone inválido."}), 400
        
    if not validate_email(data['email']):
        return jsonify({"error": "Email inválido."}), 400

    # Verifica duplicidades
    orig_email = data['email'].strip().lower()
    if Restaurante.query.filter_by(cnpj=data['cnpj']).first():
        return jsonify({"error": "CNPJ já cadastrado."}), 409
    if Restaurante.query.filter_by(email=orig_email).first():
        return jsonify({"error": "Email já cadastrado."}), 409

    logotipo_path = None
    if 'logotipo' in request.files:
        file = request.files['logotipo']
        if file and allowed_file(file.filename):
            logotipo_path = upload_file_to_supabase(file, folder='logos')

    cat_id = None
    categoria_nome = data.get('categoria_id')
    if categoria_nome:
        categoria = Categoria.query.filter(Categoria.nome.ilike(categoria_nome)).first()
        if categoria:
            cat_id = categoria.id
        else:
            nova_cat = Categoria(nome=categoria_nome.title(), tipo='COZINHA')
            db.session.add(nova_cat)
            db.session.flush()
            cat_id = nova_cat.id

    novo_restaurante = Restaurante(
        nome_fantasia=data['nome_fantasia'],
        razao_social=data['razao_social'],
        cnpj=data['cnpj'],
        endereco=data['endereco'], # Texto formatado vindo do front
        logradouro=data.get('logradouro'),
        bairro=data.get('bairro'),
        cidade=data.get('cidade'),
        estado=data.get('estado'),
        numero=data.get('numero'),
        cep=data.get('cep'),
        sem_numero=data.get('sem_numero') == 'true',
        complemento=data.get('complemento'),
        ponto_referencia=data.get('ponto_referencia'),
        telefone=data['telefone'],
        descricao=data.get('descricao'),
        logotipo=logotipo_path,
        email=orig_email,
        categoria_id=cat_id
    )

    try:
        db.session.add(novo_restaurante)
        db.session.commit()
        return jsonify(novo_restaurante.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erro interno ao criar restaurante: {str(e)}"}), 500

@restaurante_bp.route('/restaurantes/<uuid:id>/status', methods=['PATCH'])
def update_status(id):
    restaurante = Restaurante.query.get(id)
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404
    
    data = request.get_json()
    if 'ativo' not in data:
        return jsonify({"error": "Informe o status ativo (true/false)."}), 400
    
    restaurante.ativo = bool(data['ativo'])
    db.session.commit()
    
    return jsonify({"message": "Status atualizado.", "ativo": restaurante.ativo}), 200

@restaurante_bp.route('/restaurantes/<uuid:id>/horarios', methods=['POST'])
def add_horario(id):
    restaurante = Restaurante.query.get(id)
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404
        
    data = request.get_json()
    # Expects list of {dia_semana, abertura, fechamento}
    if not isinstance(data, list):
         return jsonify({"error": "Formato inválido. Envie uma lista de horários."}), 400
         
    # Limpa horários anteriores
    HorarioFuncionamento.query.filter_by(restaurante_id=id).delete()
    
    from datetime import datetime
    try:
        for h in data:
            novo_h = HorarioFuncionamento(
                dia_semana=h['dia_semana'],
                abertura=datetime.strptime(h['abertura'], '%H:%M').time(),
                fechamento=datetime.strptime(h['fechamento'], '%H:%M').time(),
                restaurante_id=id
            )
            db.session.add(novo_h)
            
        db.session.commit()
        return jsonify({"message": "Horários configurados com sucesso."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erro ao adicionar horários: {str(e)}"}), 500

@restaurante_bp.route('/restaurantes/<uuid:id>/horarios', methods=['GET'])
def get_horarios(id):
    restaurante = Restaurante.query.get(id)
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404
        
    horarios = HorarioFuncionamento.query.filter_by(restaurante_id=id).all()
    return jsonify([h.to_dict() for h in horarios]), 200

@restaurante_bp.route('/restaurantes/<uuid:id>', methods=['PATCH'])
def update_restaurante(id):
    restaurante = Restaurante.query.get(id)
    if not restaurante:
        return jsonify({"error": "Restaurante não encontrado."}), 404
        
    data = request.form.to_dict()

    if 'cnpj' in data and data['cnpj'] != restaurante.cnpj:
        if not validate_cnpj(data['cnpj']):
            return jsonify({"error": "CNPJ inválido."}), 400
        if Restaurante.query.filter_by(cnpj=data['cnpj']).first():
            return jsonify({"error": "CNPJ já cadastrado."}), 409
        restaurante.cnpj = data['cnpj']
            
    if 'email' in data and data['email'].strip().lower() != restaurante.email:
        orig_email = data['email'].strip().lower()
        if not validate_email(orig_email):
            return jsonify({"error": "Email inválido."}), 400
        if Restaurante.query.filter_by(email=orig_email).first():
            return jsonify({"error": "Email já cadastrado."}), 409
        restaurante.email = orig_email
        
    if 'telefone' in data:
        if not validate_phone(data['telefone']):
            return jsonify({"error": "Telefone inválido."}), 400
        restaurante.telefone = data['telefone']

    if 'nome_fantasia' in data:
        restaurante.nome_fantasia = data['nome_fantasia']
    if 'razao_social' in data:
        restaurante.razao_social = data['razao_social']
    if 'endereco' in data:
        restaurante.endereco = data['endereco']
    if 'logradouro' in data:
        restaurante.logradouro = data['logradouro']
    if 'bairro' in data:
        restaurante.bairro = data['bairro']
    if 'cidade' in data:
        restaurante.cidade = data['cidade']
    if 'estado' in data:
        restaurante.estado = data['estado']
    if 'numero' in data:
        restaurante.numero = data['numero']
    if 'cep' in data:
        restaurante.cep = data['cep']
    if 'ponto_referencia' in data:
        restaurante.ponto_referencia = data['ponto_referencia']
    if 'sem_numero' in data:
        restaurante.sem_numero = data['sem_numero'] == 'true'
    if 'complemento' in data:
        restaurante.complemento = data['complemento']
    if 'descricao' in data:
        restaurante.descricao = data['descricao']

    categoria_nome = data.get('categoria_id')
    if categoria_nome:
        categoria = Categoria.query.filter(Categoria.nome.ilike(categoria_nome)).first()
        if categoria:
            restaurante.categoria_id = categoria.id
        else:
            nova_cat = Categoria(nome=categoria_nome.title(), tipo='COZINHA')
            db.session.add(nova_cat)
            db.session.flush()
            restaurante.categoria_id = nova_cat.id

    if 'logotipo' in request.files:
        file = request.files['logotipo']
        if file and allowed_file(file.filename):
            restaurante.logotipo = upload_file_to_supabase(file, folder='logos')

    if 'capa' in request.files:
        file = request.files['capa']
        if file and allowed_file(file.filename):
            restaurante.capa = upload_file_to_supabase(file, folder='logos')

    try:
        db.session.commit()
        return jsonify(restaurante.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erro interno ao atualizar restaurante: {str(e)}"}), 500

@restaurante_bp.route('/restaurantes', methods=['GET'])
def list_restaurantes():
    try:
        rest_id = request.args.get('id')
        usuario_id = request.args.get('usuario_id') # manter compatibilidade se quiser usar
        target_id = rest_id or usuario_id
        
        if target_id:
            restaurantes = Restaurante.query.filter_by(id=target_id).all()
        else:
            # Busca apenas restaurantes ativos por padrão na listagem pública
            restaurantes = Restaurante.query.filter_by(ativo=True).all()
            
        return jsonify([r.to_dict() for r in restaurantes]), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao listar restaurantes: {str(e)}"}), 500

