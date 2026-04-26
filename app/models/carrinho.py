import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class Carrinho(db.Model):
    """Carrinho ativo de um usuário (máximo 1 por usuário)."""
    __tablename__ = 'carrinhos'

    id               = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id       = db.Column(UUID(as_uuid=True), db.ForeignKey('usuarios.id'), nullable=False, unique=True)
    restaurante_id   = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)
    congelado        = db.Column(db.Boolean, default=False, nullable=False)
    token_checkout   = db.Column(db.String(36), nullable=True, unique=True)
    cupom_id         = db.Column(db.Integer, db.ForeignKey('cupons.id'), nullable=True)
    data_criacao     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relacionamentos
    itens      = db.relationship('ItemCarrinho', backref='carrinho', lazy=True, cascade='all, delete-orphan')
    restaurante = db.relationship('Restaurante', lazy=True)
    cupom       = db.relationship('Cupom', lazy=True)

    def calcular_subtotal(self):
        """Calcula subtotal em centavos (sem frete e sem cupom)."""
        total = 0
        for item in self.itens:
            preco_item = item.preco_unitario_centavos
            preco_adicionais = sum(a.preco_centavos for a in item.adicionais)
            total += (preco_item + preco_adicionais) * item.quantidade
        return total

    def calcular_desconto(self, subtotal: int) -> int:
        """Calcula o desconto do cupom em centavos."""
        if not self.cupom or not self.cupom.ativo:
            return 0
        if subtotal < self.cupom.valor_minimo_centavos:
            return 0
        if self.cupom.tipo == 'PERCENTUAL':
            return int(subtotal * self.cupom.valor / 100)
        return self.cupom.valor  # FIXO

    def to_dict(self):
        subtotal  = self.calcular_subtotal()
        frete     = int((self.restaurante.valor_frete or 0) * 100) if self.restaurante else 0
        desconto  = self.calcular_desconto(subtotal)
        total     = subtotal + frete - desconto

        pedido_minimo = self.restaurante.pedido_minimo_centavos if self.restaurante else 0
        falta_minimo  = max(0, pedido_minimo - subtotal)

        return {
            'id':               str(self.id),
            'usuario_id':       str(self.usuario_id),
            'restaurante_id':   str(self.restaurante_id),
            'congelado':        self.congelado,
            'token_checkout':   self.token_checkout,
            'cupom':            self.cupom.to_dict() if self.cupom else None,
            'restaurante': {
                'id':                    str(self.restaurante.id),
                'nome_fantasia':         self.restaurante.nome_fantasia,
                'logotipo':              self.restaurante.logotipo,
                'is_open':               self.restaurante.is_open,
                'pedido_minimo_centavos': pedido_minimo,
                'valor_frete_centavos':  frete,
            },
            'itens':            [i.to_dict() for i in self.itens],
            'subtotal_centavos': subtotal,
            'frete_centavos':    frete,
            'desconto_centavos': desconto,
            'total_centavos':    total,
            'falta_minimo_centavos': falta_minimo,
            'data_criacao':      self.data_criacao.isoformat(),
            'data_atualizacao':  self.data_atualizacao.isoformat(),
        }


class ItemCarrinho(db.Model):
    """Linha de item dentro de um carrinho."""
    __tablename__ = 'itens_carrinho'

    id                      = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carrinho_id             = db.Column(UUID(as_uuid=True), db.ForeignKey('carrinhos.id'), nullable=False)
    produto_id              = db.Column(UUID(as_uuid=True), db.ForeignKey('produtos.id'), nullable=False)
    quantidade              = db.Column(db.Integer, nullable=False, default=1)
    # Snapshot de preço no momento da adição (em centavos)
    preco_unitario_centavos = db.Column(db.Integer, nullable=False)
    observacao              = db.Column(db.String(200), nullable=True, default='')

    # Relacionamentos
    adicionais = db.relationship('ItemAdicionalCarrinho', backref='item', lazy=True, cascade='all, delete-orphan')
    produto    = db.relationship('Produto', lazy=True)

    def fingerprint(self) -> str:
        """Identificador único para detectar itens idênticos."""
        ids_adicionais = sorted(str(a.adicional_id) for a in self.adicionais)
        obs = (self.observacao or '').strip()
        return f"{self.produto_id}|{','.join(ids_adicionais)}|{obs}"

    def to_dict(self):
        return {
            'id':                      str(self.id),
            'produto_id':              str(self.produto_id),
            'nome':                    self.produto.nome if self.produto else None,
            'descricao':               self.produto.descricao if self.produto else None,
            'imagem':                  self.produto.imagem if self.produto else None,
            'disponivel':              self.produto.disponivel if self.produto else True,
            'preco_unitario_centavos': self.preco_unitario_centavos,
            'quantidade':              self.quantidade,
            'observacao':              self.observacao or '',
            'adicionais':              [a.to_dict() for a in self.adicionais],
        }


class ItemAdicionalCarrinho(db.Model):
    """Adicional selecionado em um item do carrinho (snapshot de nome/preço)."""
    __tablename__ = 'itens_adicionais_carrinho'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id       = db.Column(UUID(as_uuid=True), db.ForeignKey('itens_carrinho.id'), nullable=False)
    adicional_id  = db.Column(db.Integer, db.ForeignKey('adicionais.id'), nullable=False)
    nome_adicional = db.Column(db.String(100), nullable=False)
    preco_centavos = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'id':            self.adicional_id,
            'nome':          self.nome_adicional,
            'preco_centavos': self.preco_centavos,
        }
