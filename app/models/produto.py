import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class Produto(db.Model):
    __tablename__ = 'produtos'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(500), nullable=True)
    preco = db.Column(db.Numeric(10, 2), nullable=False) # RF10
    imagem = db.Column(db.String(255), nullable=True) # RF11
    disponivel = db.Column(db.Boolean, default=True, nullable=False) # RF12
    
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)
    
    # Grupos de Adicionais (RF13)
    grupos_adicionais = db.relationship('GrupoAdicionais', backref='produto', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'descricao': self.descricao,
            'preco': float(self.preco),
            'imagem': self.imagem,
            'disponivel': self.disponivel,
            'categoria_id': self.categoria_id,
            'categoria': self.categoria.nome if self.categoria else None,
            'restaurante_id': str(self.restaurante_id),
            'grupos_adicionais': [g.to_dict() for g in self.grupos_adicionais]
        }
