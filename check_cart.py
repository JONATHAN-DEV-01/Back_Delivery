from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    ))
    tables = [r[0] for r in result]
    print("=== Tabelas no banco ===")
    for t in tables:
        print(f"  - {t}")

    expected = ['carrinhos', 'itens_carrinho', 'itens_adicionais_carrinho', 'cupons']
    print("\n=== Verificação das novas tabelas ===")
    for e in expected:
        status = "✓ OK" if e in tables else "✗ FALTANDO"
        print(f"  {status}: {e}")

    # Verifica coluna adicionada
    col_result = db.session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='restaurantes' AND column_name='pedido_minimo_centavos'"
    ))
    col = col_result.fetchone()
    print(f"\n  {'✓ OK' if col else '✗ FALTANDO'}: restaurantes.pedido_minimo_centavos")
