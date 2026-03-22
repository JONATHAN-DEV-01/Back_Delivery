import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class OTPCode(db.Model):
    __tablename__ = 'otp_codes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(6), nullable=True)
    link_token = db.Column(db.String(100), nullable=True, unique=True)
    data_expiracao = db.Column(db.DateTime, nullable=False)
    tentativas = db.Column(db.Integer, default=0, nullable=False)
    
    usuario_id = db.Column(UUID(as_uuid=True), db.ForeignKey('usuarios.id'), nullable=True) # Nulo se for restaurante
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=True) # Nulo se for usuário

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'data_expiracao': self.data_expiracao.isoformat(),
            'tentativas': self.tentativas,
            'usuario_id': str(self.usuario_id) if self.usuario_id else None,
            'restaurante_id': str(self.restaurante_id) if self.restaurante_id else None
        }
