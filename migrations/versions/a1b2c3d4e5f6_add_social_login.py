"""Add social login: identidades_sociais table, foto_url and ultimo_login to usuarios

Revision ID: a1b2c3d4e5f6
Revises: f6aeb541c077
Create Date: 2026-04-05 18:00:00.000000

Mudanças:
- Cria tabela `identidades_sociais` com FK para `usuarios.id`
- Adiciona coluna `foto_url` (TEXT, nullable) em `usuarios`
- Adiciona coluna `ultimo_login` (DATETIME, nullable) em `usuarios`
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f6aeb541c077'
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # 1. Adicionar colunas novas na tabela usuarios (PostgreSQL-compatible)
    # ------------------------------------------------------------------
    try:
        op.add_column('usuarios', sa.Column('foto_url', sa.Text(), nullable=True))
    except Exception:
        pass  # coluna já existe

    try:
        op.add_column('usuarios', sa.Column('ultimo_login', sa.DateTime(), nullable=True))
    except Exception:
        pass  # coluna já existe

    # ------------------------------------------------------------------
    # 2. Criar tabela identidades_sociais (se ainda não existir)
    # ------------------------------------------------------------------
    op.create_table(
        'identidades_sociais',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('provedor', sa.String(length=20), nullable=False),
        sa.Column('id_provedor', sa.String(length=100), nullable=False),
        sa.Column('data_vinculo', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provedor', 'id_provedor', name='uq_provedor_id_provedor'),
    )


def downgrade():
    # ------------------------------------------------------------------
    # Desfaz na ordem inversa
    # ------------------------------------------------------------------
    op.drop_table('identidades_sociais')

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('ultimo_login')
        batch_op.drop_column('foto_url')
