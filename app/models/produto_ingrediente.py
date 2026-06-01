import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class ProdutoIngrediente(db.Model):
    __tablename__ = 'produto_ingredientes'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    produto_id = db.Column(UUID(as_uuid=True), db.ForeignKey('produtos.id'), nullable=False)
    ingrediente_id = db.Column(UUID(as_uuid=True), db.ForeignKey('ingredientes.id'), nullable=False)
    quantidade_necessaria = db.Column(db.Numeric(10, 3), nullable=False)

    # Relacionamento de volta para obter dados do ingrediente facilmente
    ingrediente = db.relationship('Ingrediente', backref='fichas_tecnicas', lazy=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            'produto_id': str(self.produto_id),
            'ingrediente_id': str(self.ingrediente_id),
            'quantidade_necessaria': float(self.quantidade_necessaria),
            'ingrediente_nome': self.ingrediente.nome if self.ingrediente else None,
            'ingrediente_unidade': self.ingrediente.unidade_medida if self.ingrediente else None
        }
