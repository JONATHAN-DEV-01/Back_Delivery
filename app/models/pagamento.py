import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, BIGINT
from app.extensions import db

class Pagamento(db.Model):
    __tablename__ = 'pagamentos'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = db.Column(UUID(as_uuid=True), db.ForeignKey('pedidos.id'), nullable=False)
    mercado_pago_id = db.Column(BIGINT, nullable=True, unique=True)
    
    metodo = db.Column(db.String(50), nullable=False) # 'cartao', 'pix'
    status = db.Column(db.String(50), default='pending', nullable=False) # approved, rejected, in_process, cancelled
    valor_centavos = db.Column(db.Integer, nullable=False)
    
    pix_qr_code = db.Column(db.Text, nullable=True)
    pix_qr_code_base64 = db.Column(db.Text, nullable=True)
    
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    pedido = db.relationship('Pedido', backref=db.backref('pagamentos', lazy=True))

    def to_dict(self):
        return {
            'id': str(self.id),
            'pedido_id': str(self.pedido_id),
            'mercado_pago_id': self.mercado_pago_id,
            'metodo': self.metodo,
            'status': self.status,
            'valor_centavos': self.valor_centavos,
            'pix_qr_code': self.pix_qr_code,
            'pix_qr_code_base64': self.pix_qr_code_base64,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }
