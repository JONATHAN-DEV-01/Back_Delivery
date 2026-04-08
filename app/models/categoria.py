from app.extensions import db

class Categoria(db.Model):
    __tablename__ = 'categorias'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome         = db.Column(db.String(50), nullable=False, unique=True)
    tipo         = db.Column(db.String(20), nullable=False)       # 'COZINHA' ou 'PRODUTO'
    imagem_url   = db.Column(db.Text, nullable=True)              # RF-01 Req.7 – ícone WEBP
    is_highlight = db.Column(db.Boolean, default=False, nullable=False)  # RF-02 Req.7 – carrossel home

    # Relacionamento 1:N (via categoria_id FK em restaurantes)
    restaurantes = db.relationship('Restaurante', backref='categoria', lazy=True)
    produtos     = db.relationship('Produto', backref='categoria', lazy=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'nome':         self.nome,
            'tipo':         self.tipo,
            'imagem_url':   self.imagem_url,
            'is_highlight': self.is_highlight,
        }
