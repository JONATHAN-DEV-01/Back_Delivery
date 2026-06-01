import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class Ingrediente(db.Model):
    __tablename__ = 'ingredientes'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    quantidade_atual = db.Column(db.Numeric(10, 3), nullable=False, default=0.0)
    unidade_medida = db.Column(db.String(10), nullable=False) # 'g', 'ml', 'un'
    custo_unitario = db.Column(db.Numeric(10, 2), nullable=True) # opcional
    
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'quantidade_atual': float(self.quantidade_atual),
            'unidade_medida': self.unidade_medida,
            'custo_unitario': float(self.custo_unitario) if self.custo_unitario is not None else None,
            'restaurante_id': str(self.restaurante_id),
            'status_disponivel': float(self.quantidade_atual) > 0
        }
