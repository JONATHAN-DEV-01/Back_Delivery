import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class Restaurante(db.Model):
    __tablename__ = 'restaurantes'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_fantasia = db.Column(db.String(50), nullable=False)
    razao_social = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(14), nullable=False, unique=True)
    logotipo = db.Column(db.String(255), nullable=True) # Caminho da imagem
    capa = db.Column(db.String(255), nullable=True) # Caminho da imagem de capa
    descricao = db.Column(db.String(500), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=True)
    
    # Endereço detalhado (RF06 Mapeamento no banco)
    endereco = db.Column(db.String(254), nullable=False) # Texto completo formatado
    logradouro = db.Column(db.String(254), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    numero = db.Column(db.String(10), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    sem_numero = db.Column(db.Boolean, default=False)
    complemento = db.Column(db.String(100), nullable=True)
    ponto_referencia = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(11), nullable=False)
    
    # Status (RF09)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relacionamentos
    horarios = db.relationship('HorarioFuncionamento', backref='restaurante', lazy=True, cascade='all, delete-orphan')
    produtos = db.relationship('Produto', backref='restaurante', lazy=True, cascade='all, delete-orphan')
    
    # Autenticação e Contato Próprio
    email = db.Column(db.String(254), nullable=False, unique=True)
    
    otp_codes = db.relationship('OTPCode', backref='restaurante', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome_fantasia': self.nome_fantasia,
            'razao_social': self.razao_social,
            'cnpj': self.cnpj,
            'logotipo': self.logotipo,
            'capa': self.capa,
            'descricao': self.descricao,
            'categoria': self.categoria.nome if self.categoria else None,
            'endereco': self.endereco,
            'logradouro': self.logradouro,
            'bairro': self.bairro,
            'cidade': self.cidade,
            'estado': self.estado,
            'numero': self.numero,
            'cep': self.cep,
            'sem_numero': self.sem_numero,
            'complemento': self.complemento,
            'ponto_referencia': self.ponto_referencia,
            'telefone': self.telefone,
            'ativo': self.ativo,
            'email': self.email
        }
