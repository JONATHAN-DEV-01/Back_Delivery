from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID

# Tabela de associação N:N entre Restaurante e Categoria (Req. 7.4)
loja_categorias = db.Table(
    'loja_categorias',
    db.Column('id', db.Integer, primary_key=True, autoincrement=True),
    db.Column(
        'loja_id',
        UUID(as_uuid=True),
        db.ForeignKey('restaurantes.id', ondelete='CASCADE'),
        nullable=False,
    ),
    db.Column(
        'categoria_id',
        db.Integer,
        db.ForeignKey('categorias.id', ondelete='CASCADE'),
        nullable=False,
    ),
    db.UniqueConstraint('loja_id', 'categoria_id', name='uq_loja_categoria'),
)
