"""
Modelo: IdentidadeSocial
Tabela relacional que vincula um usuário existente a um provedor de login social.

RNF – Transporte em trânsito:
  - Toda comunicação com as Graph APIs do Google e Meta ocorre via HTTPS (TLS 1.2+).
    Os tokens de provider jamais são armazenados; apenas o id_provedor (subject claim)
    é persistido, minimizando a superfície de ataque.
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db


class IdentidadeSocial(db.Model):
    """
    Tabela relacional que armazena os vínculos entre usuários e provedores OAuth.

    Colunas:
        id           – Chave primária serial (auto-incremento).
        usuario_id   – FK para usuarios.id (UUID).
        provedor     – Nome do provedor: 'GOOGLE' ou 'FACEBOOK'.
        id_provedor  – Sub/UserID único retornado pelo provedor.
        data_vinculo – Timestamp do momento em que o vínculo foi criado.
    """

    __tablename__ = "identidades_sociais"

    # RNF – Índice composto (provedor + id_provedor) garante busca O(log n)
    # contribuindo para a meta de latência < 1.2 s na rota de callback.
    __table_args__ = (
        db.UniqueConstraint("provedor", "id_provedor", name="uq_provedor_id_provedor"),
    )

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)

    usuario_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )

    provedor: str = db.Column(
        db.String(20),
        nullable=False,
        # Valores permitidos pela especificação: 'GOOGLE' | 'FACEBOOK'
    )

    id_provedor: str = db.Column(
        db.String(100),
        nullable=False,
        # sub (Google ID Token) ou id (Facebook /me)
    )

    data_vinculo: datetime = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relacionamento de volta para facilitar queries ORM
    usuario = db.relationship("Usuario", backref="identidades_sociais")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_id": str(self.usuario_id),
            "provedor": self.provedor,
            "id_provedor": self.id_provedor,
            "data_vinculo": self.data_vinculo.isoformat(),
        }
