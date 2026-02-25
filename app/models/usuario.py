import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    senha = db.Column(db.String(255), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.senha = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.senha, password)

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'email': self.email,
            'telefone': self.telefone,
            'data_criacao': self.data_criacao.isoformat()
        }
