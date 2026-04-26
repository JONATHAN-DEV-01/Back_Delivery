import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from app.extensions import db

class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = db.Column(UUID(as_uuid=True), db.ForeignKey('usuarios.id'), nullable=False)
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)
    
    status = db.Column(db.String(50), default='PENDENTE_ACEITACAO', nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    troco_para_centavos = db.Column(db.Integer, nullable=True)

    subtotal_centavos = db.Column(db.Integer, nullable=False)
    taxa_entrega_centavos = db.Column(db.Integer, nullable=False, default=0)
    desconto_centavos = db.Column(db.Integer, nullable=False, default=0)
    total_centavos = db.Column(db.Integer, nullable=False)
    
    cupom_codigo = db.Column(db.String(50), nullable=True)
    observacoes = db.Column(db.String(140), nullable=True)
    
    # Snapshot do endereço na hora do pedido para evitar mudanças retroativas
    # Usando JSONB no Postgres ou JSON. Usaremos db.JSON para portabilidade ou JSONB se importado.
    endereco_entrega_snapshot = db.Column(MutableDict.as_mutable(JSONB), nullable=True)

    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relacionamentos
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True, cascade='all, delete-orphan')
    usuario = db.relationship('Usuario', backref='pedidos_feitos', lazy=True)
    restaurante = db.relationship('Restaurante', backref='pedidos_recebidos', lazy=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            'usuario_id': str(self.usuario_id),
            'restaurante_id': str(self.restaurante_id),
            'restaurante_nome': self.restaurante.nome_fantasia if self.restaurante else None,
            'status': self.status,
            'forma_pagamento': self.forma_pagamento,
            'troco_para_centavos': self.troco_para_centavos,
            'subtotal_centavos': self.subtotal_centavos,
            'taxa_entrega_centavos': self.taxa_entrega_centavos,
            'desconto_centavos': self.desconto_centavos,
            'total_centavos': self.total_centavos,
            'cupom_codigo': self.cupom_codigo,
            'observacoes': self.observacoes,
            'endereco_entrega': self.endereco_entrega_snapshot,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat(),
            'itens': [item.to_dict() for item in self.itens]
        }


class ItemPedido(db.Model):
    __tablename__ = 'itens_pedido'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = db.Column(UUID(as_uuid=True), db.ForeignKey('pedidos.id'), nullable=False)
    produto_id = db.Column(UUID(as_uuid=True), db.ForeignKey('produtos.id'), nullable=True)
    
    nome_produto = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    preco_unitario_base_centavos = db.Column(db.Integer, nullable=False)
    preco_total_item_centavos = db.Column(db.Integer, nullable=False)
    
    # Lista de adicionais com seus respectivos preços no momento da compra
    adicionais = db.Column(MutableList.as_mutable(JSONB), nullable=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            'produto_id': str(self.produto_id) if self.produto_id else None,
            'nome_produto': self.nome_produto,
            'quantidade': self.quantidade,
            'preco_unitario_base_centavos': self.preco_unitario_base_centavos,
            'preco_total_item_centavos': self.preco_total_item_centavos,
            'adicionais': self.adicionais
        }
