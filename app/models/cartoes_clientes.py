import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class CartaoCliente(db.Model):
    __tablename__ = 'cartoes_clientes'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = db.Column(UUID(as_uuid=True), db.ForeignKey('usuarios.id'), nullable=False)
    
    mp_customer_id = db.Column(db.String(100), nullable=False)
    mp_card_id = db.Column(db.String(100), nullable=False)
    
    ultimos_digitos = db.Column(db.String(4), nullable=True)
    bandeira = db.Column(db.String(50), nullable=True)
    
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    usuario = db.relationship('Usuario', backref=db.backref('cartoes_salvos', lazy=True, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': str(self.id),
            'usuario_id': str(self.usuario_id),
            'mp_card_id': self.mp_card_id,
            'ultimos_digitos': self.ultimos_digitos,
            'bandeira': self.bandeira,
            'data_criacao': self.data_criacao.isoformat()
        }
