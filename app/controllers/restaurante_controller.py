import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.restaurante import Restaurante
from app.models.horario_funcionamento import HorarioFuncionamento
from app.models.categoria import Categoria
from app.utils.validators import validate_cnpj, validate_phone

restaurante_bp = Blueprint('restaurante', __name__)

UPLOAD_FOLDER = 'uploads/logos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024 # 2MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@restaurante_bp.route('/restaurantes', methods=['POST'])
def create_restaurante():
    data = request.form.to_dict()
    required = ('nome_fantasia', 'razao_social', 'cnpj', 'endereco', 'telefone', 'usuario_id')
    
    if not all(k in data for k in required):
        return jsonify({"error": "Dados obrigatórios ausentes."}), 400

    if not validate_cnpj(data['cnpj']):
        return jsonify({"error": "CNPJ inválido."}), 400
    
    if not validate_phone(data['telefone']):
        return jsonify({"error": "Telefone inválido."}), 400

    # Verifica duplicidade de CNPJ
    if Restaurante.query.filter_by(cnpj=data['cnpj']).first():
        return jsonify({"error": "CNPJ já cadastrado."}), 409

    logotipo_path = None
    if 'logotipo' in request.files:
        file = request.files['logotipo']
        if file and allowed_file(file.filename):
            # Validação de tamanho (RF07)
            file.seek(0, os.SEEK_END)
            size = file.tell()
            if size > MAX_FILE_SIZE:
                return jsonify({"error": "Logotipo excede o tamanho máximo de 2MB."}), 400
            file.seek(0)
            
            filename = secure_filename(f"{data['cnpj']}_{file.filename}")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            logotipo_path = filepath

    novo_restaurante = Restaurante(
        nome_fantasia=data['nome_fantasia'],
        razao_social=data['razao_social'],
        cnpj=data['cnpj'],
        endereco=data['endereco'],
        complemento=data.get('complemento'),
        telefone=data['telefone'],
        descricao=data.get('descricao'),
        logotipo=logotipo_path,
        usuario_id=data['usuario_id'],
        categoria_id=data.get('categoria_id')
    )

    db.session.add(novo_restaurante)
    db.session.commit()

    return jsonify(novo_restaurante.to_dict()), 201

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
