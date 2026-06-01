import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

# Tabela associativa entre Produto e Adicional (N:N)
produto_adicionais = db.Table('produto_adicionais',
    db.Column('produto_id', UUID(as_uuid=True), db.ForeignKey('produtos.id'), primary_key=True),
    db.Column('adicional_id', db.Integer, db.ForeignKey('adicionais.id'), primary_key=True)
)

class Adicional(db.Model):
    __tablename__ = 'adicionais'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    quantidade_atual = db.Column(db.Numeric(10, 3), default=0.0, nullable=False)
    
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)

    @property
    def disponivel(self):
        return float(self.quantidade_atual) > 0

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'preco': float(self.preco),
            'quantidade_atual': float(self.quantidade_atual),
            'disponivel': self.disponivel,
            'restaurante_id': str(self.restaurante_id)
        }
