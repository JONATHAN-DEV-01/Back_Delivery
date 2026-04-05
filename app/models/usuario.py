import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=True)
    sobrenome = db.Column(db.String(100), nullable=True)
    cpf = db.Column(db.String(14), nullable=True, unique=True)
    email = db.Column(db.String(254), nullable=False, unique=True)
    telefone = db.Column(db.String(15), nullable=True, unique=True)
    perfil = db.Column(db.String(20), default='CLIENTE', nullable=False) # 'CLIENTE' ou 'RESTAURANTE'
    
    # Endereço detalhado (RF-01 a RF-09)
    logradouro = db.Column(db.String(254), nullable=True)
    bairro = db.Column(db.String(100), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    numero = db.Column(db.String(10), nullable=True)
    sem_numero = db.Column(db.Boolean, default=False)
    complemento = db.Column(db.String(100), nullable=True)
    ponto_referencia = db.Column(db.String(100), nullable=True)
    
    # RF-07: URL da foto de perfil (pode ser URL do provedor social ou upload interno)
    foto_url = db.Column(db.Text, nullable=True)

    etapa_registro = db.Column(db.String(50), default='EMAIL_PENDING', nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # Atualizado em cada login bem-sucedido (social ou OTP)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    
    otp_codes = db.relationship('OTPCode', backref='usuario', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'sobrenome': self.sobrenome,
            'cpf': self.cpf,
            'email': self.email,
            'telefone': self.telefone,
            'perfil': self.perfil,
            'endereco': {
                'logradouro': self.logradouro,
                'bairro': self.bairro,
                'cidade': self.cidade,
                'estado': self.estado,
                'numero': self.numero,
                'sem_numero': self.sem_numero,
                'complemento': self.complemento,
                'ponto_referencia': self.ponto_referencia
            },
            'foto_url': self.foto_url,
            'etapa_registro': self.etapa_registro,
            'data_criacao': self.data_criacao.isoformat(),
            'ultimo_login': self.ultimo_login.isoformat() if self.ultimo_login else None,
        }
