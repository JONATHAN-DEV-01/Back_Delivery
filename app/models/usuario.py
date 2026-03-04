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
    endereco = db.Column(db.String(254), nullable=True)
    etapa_registro = db.Column(db.String(50), default='EMAIL_PENDING', nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    otp_codes = db.relationship('OTPCode', backref='usuario', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'sobrenome': self.sobrenome,
            'cpf': self.cpf,
            'email': self.email,
            'telefone': self.telefone,
            'endereco': self.endereco,
            'etapa_registro': self.etapa_registro,
            'data_criacao': self.data_criacao.isoformat()
        }
