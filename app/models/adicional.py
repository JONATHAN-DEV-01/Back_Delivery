import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class GrupoAdicionais(db.Model):
    __tablename__ = 'grupos_adicionais'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    min_quantidade = db.Column(db.Integer, default=0, nullable=False) # RF13
    max_quantidade = db.Column(db.Integer, default=1, nullable=False) # RF13
    
    produto_id = db.Column(UUID(as_uuid=True), db.ForeignKey('produtos.id'), nullable=False)
    adicionais = db.relationship('Adicional', backref='grupo', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'min_quantidade': self.min_quantidade,
            'max_quantidade': self.max_quantidade,
            'adicionais': [a.to_dict() for a in self.adicionais]
        }

class Adicional(db.Model):
    __tablename__ = 'adicionais'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Numeric(10, 2), default=0.00, nullable=False) # RF13
    
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupos_adicionais.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'preco': float(self.preco)
        }
