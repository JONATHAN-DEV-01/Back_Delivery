from app.extensions import db

class Categoria(db.Model):
    __tablename__ = 'categorias'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False) # 'COZINHA' ou 'PRODUTO'
    
    restaurantes = db.relationship('Restaurante', backref='categoria', lazy=True)
    produtos = db.relationship('Produto', backref='categoria', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'tipo': self.tipo
        }
