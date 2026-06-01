import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class Produto(db.Model):
    __tablename__ = 'produtos'

    id                = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome              = db.Column(db.String(100), nullable=False)
    descricao         = db.Column(db.String(500), nullable=True)
    preco             = db.Column(db.Numeric(10, 2), nullable=False)
    preco_promocional = db.Column(db.Numeric(10, 2), nullable=True)   # RF-05 Req.6
    imagem            = db.Column(db.String(255), nullable=True)
    disponivel        = db.Column(db.Boolean, default=True, nullable=False)

    # RF-01: Quantidade numérica em estoque (NULL = sem controle numérico, apenas toggle)
    quantidade        = db.Column(db.Integer, nullable=True, default=None)

    categoria_id   = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    restaurante_id = db.Column(UUID(as_uuid=True), db.ForeignKey('restaurantes.id'), nullable=False)

    # Adicionais Flat
    from app.models.adicional import produto_adicionais
    adicionais = db.relationship('Adicional', secondary=produto_adicionais, lazy=True)
    
    # Ficha Técnica (Ingredientes)
    ficha_tecnica = db.relationship('ProdutoIngrediente', backref='produto', lazy=True, cascade='all, delete-orphan')

    @property
    def quantidade_disponivel(self):
        """Calcula a quantidade máxima de produtos que podem ser feitos com os ingredientes atuais."""
        if not self.ficha_tecnica:
            # Se não tem ficha técnica, não controla estoque por ingredientes. Retorna um número grande (infinito prático)
            # ou depende do campo `quantidade` legado. Como foi pedido para refletir ingredientes, 
            # se não tiver ficha, assumimos disponibilidade baseada no antigo booleano.
            return 999 if self.disponivel else 0
        
        quantidades_possiveis = []
        for ficha in self.ficha_tecnica:
            qtd_ingrediente = float(ficha.ingrediente.quantidade_atual)
            qtd_necessaria = float(ficha.quantidade_necessaria)
            if qtd_necessaria > 0:
                quantidades_possiveis.append(int(qtd_ingrediente // qtd_necessaria))
        
        return min(quantidades_possiveis) if quantidades_possiveis else 0

    def to_dict(self):
        em_promocao = bool(self.preco_promocional and float(self.preco_promocional) > 0)
        result = {
            'id':                str(self.id),
            'nome':              self.nome,
            'descricao':         self.descricao,
            'preco':             float(self.preco),
            'imagem':            self.imagem,
            'disponivel':        self.disponivel,
            'status_disponivel': self.disponivel,   # Alias — compatibilidade com frontend EstoquePage
            'quantidade':        self.quantidade,   # RF-01: controle numérico opcional
            'categoria_id':      self.categoria_id,
            'categoria':         self.categoria.nome if self.categoria else None,
            'restaurante_id':    str(self.restaurante_id),
            'adicionais':        [a.to_dict() for a in self.adicionais],
            'em_promocao':       em_promocao,
            'ficha_tecnica':     [f.to_dict() for f in self.ficha_tecnica],
            'quantidade_disponivel': self.quantidade_disponivel,
        }
        if em_promocao:
            result['preco_original']    = float(self.preco)
            result['preco_promocional'] = float(self.preco_promocional)
        return result
