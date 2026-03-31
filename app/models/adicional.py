import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class GrupoAdicionais(db.Model):
    __tablename__ = 'grupos_adicionais'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    min_selecao = db.Column(db.Integer, default=0, nullable=False)
    max_selecao = db.Column(db.Integer, default=1, nullable=False)
    obrigatorio = db.Column(db.Boolean, default=False, nullable=False)
    
    produto_id = db.Column(UUID(as_uuid=True), db.ForeignKey('produtos.id'), nullable=False)
    adicionais = db.relationship('Adicional', backref='grupo', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'min_selecao': self.min_selecao,
            'max_selecao': self.max_selecao,
            'obrigatorio': self.obrigatorio,
            'adicionais': [a.to_dict() for a in self.adicionais]
        }

class Adicional(db.Model):
    __tablename__ = 'adicionais'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    disponivel = db.Column(db.Boolean, default=True, nullable=False)
    
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupos_adicionais.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'preco': float(self.preco),
            'disponivel': self.disponivel
        }
