from datetime import datetime
from app.extensions import db


class Cupom(db.Model):
    """Cupom de desconto aplicável ao carrinho."""
    __tablename__ = 'cupons'

    id                    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo                = db.Column(db.String(50), nullable=False, unique=True)
    # 'PERCENTUAL' ou 'FIXO'
    tipo                  = db.Column(db.String(10), nullable=False, default='FIXO')
    # Se PERCENTUAL: valor em % (ex: 10 = 10%). Se FIXO: valor em centavos (ex: 500 = R$5,00)
    valor                 = db.Column(db.Integer, nullable=False)
    valor_minimo_centavos = db.Column(db.Integer, nullable=False, default=0)
    ativo                 = db.Column(db.Boolean, nullable=False, default=True)
    data_expiracao        = db.Column(db.DateTime, nullable=True)
    usos_maximos          = db.Column(db.Integer, nullable=True)
    usos_atuais           = db.Column(db.Integer, nullable=False, default=0)
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def is_valido(self) -> bool:
        if not self.ativo:
            return False
        if self.data_expiracao and datetime.utcnow() > self.data_expiracao:
            return False
        if self.usos_maximos is not None and self.usos_atuais >= self.usos_maximos:
            return False
        return True

    def to_dict(self):
        return {
            'id':                    self.id,
            'codigo':                self.codigo,
            'tipo':                  self.tipo,
            'valor':                 self.valor,
            'valor_minimo_centavos': self.valor_minimo_centavos,
            'ativo':                 self.ativo,
            'data_expiracao':        self.data_expiracao.isoformat() if self.data_expiracao else None,
        }
