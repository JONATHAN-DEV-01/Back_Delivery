import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    sobrenome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    telefone = db.Column(db.String(15), nullable=False, unique=True)
    endereco = db.Column(db.String(254), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    otp_codes = db.relationship('OTPCode', backref='usuario', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'sobrenome': self.sobrenome,
            'email': self.email,
            'telefone': self.telefone,
            'endereco': self.endereco,
            'data_criacao': self.data_criacao.isoformat()
        }
