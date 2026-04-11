"""add_search_and_category_fields

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-08 01:13:00.000000

Alterações:
  - categorias: + imagem_url, + is_highlight
  - restaurantes: + is_open, + nota_avaliacao, + tempo_entrega_minutos,
                  + valor_frete, + latitude, + longitude, + (colunas de endereço faltantes)
  - produtos: + preco_promocional
  - NOVA tabela: loja_categorias (N:N restaurantes x categorias)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _add_column_if_not_exists(table, column_name, column_ddl):
    """Adiciona coluna somente se não existir (PostgreSQL-safe)."""
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column_name} {column_ddl};"
    )


def upgrade():
    # ── 1. Novos campos em categorias ─────────────────────────
    _add_column_if_not_exists('categorias', 'imagem_url',   'TEXT')
    _add_column_if_not_exists('categorias', 'is_highlight', 'BOOLEAN NOT NULL DEFAULT FALSE')

    # ── 2. Novos campos operacionais/comerciais em restaurantes ─
    _add_column_if_not_exists('restaurantes', 'is_open',               'BOOLEAN NOT NULL DEFAULT FALSE')
    _add_column_if_not_exists('restaurantes', 'nota_avaliacao',        'NUMERIC(3,2)')
    _add_column_if_not_exists('restaurantes', 'tempo_entrega_minutos', 'INTEGER')
    _add_column_if_not_exists('restaurantes', 'valor_frete',           'NUMERIC(10,2)')
    _add_column_if_not_exists('restaurantes', 'latitude',              'NUMERIC(10,7)')
    _add_column_if_not_exists('restaurantes', 'longitude',             'NUMERIC(10,7)')

    # ── 2b. Colunas de endereço que podem ter ficado fora da migração base
    _add_column_if_not_exists('restaurantes', 'logradouro',       'VARCHAR(254)')
    _add_column_if_not_exists('restaurantes', 'bairro',           'VARCHAR(100)')
    _add_column_if_not_exists('restaurantes', 'cidade',           'VARCHAR(100)')
    _add_column_if_not_exists('restaurantes', 'estado',           'VARCHAR(2)')
    _add_column_if_not_exists('restaurantes', 'numero',           'VARCHAR(10)')
    _add_column_if_not_exists('restaurantes', 'cep',              'VARCHAR(10)')
    _add_column_if_not_exists('restaurantes', 'sem_numero',       'BOOLEAN DEFAULT FALSE')
    _add_column_if_not_exists('restaurantes', 'ponto_referencia', 'VARCHAR(100)')
    _add_column_if_not_exists('restaurantes', 'capa',             'VARCHAR(255)')

    # ── 3. Novo campo em produtos ─────────────────────────────
    _add_column_if_not_exists('produtos', 'preco_promocional', 'NUMERIC(10,2)')

    # ── 4. Nova tabela loja_categorias (N:N) ──────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS loja_categorias (
            id           SERIAL PRIMARY KEY,
            loja_id      UUID    NOT NULL REFERENCES restaurantes(id) ON DELETE CASCADE,
            categoria_id INTEGER NOT NULL REFERENCES categorias(id)   ON DELETE CASCADE,
            CONSTRAINT uq_loja_categoria UNIQUE (loja_id, categoria_id)
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS loja_categorias;")

    op.execute("ALTER TABLE produtos DROP COLUMN IF EXISTS preco_promocional;")

    for col in ('longitude', 'latitude', 'valor_frete',
                'tempo_entrega_minutos', 'nota_avaliacao', 'is_open'):
        op.execute(f"ALTER TABLE restaurantes DROP COLUMN IF EXISTS {col};")

    op.execute("ALTER TABLE categorias DROP COLUMN IF EXISTS is_highlight;")
    op.execute("ALTER TABLE categorias DROP COLUMN IF EXISTS imagem_url;")
