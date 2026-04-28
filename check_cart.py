import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:3CVF5nG96O2GeKjZ@db.tfqruazyqcldldlxbyzm.supabase.co:5432/postgres'

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    r = db.session.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    ))
    tables = [x[0] for x in r]

    needed = ['carrinhos', 'itens_carrinho', 'itens_adicionais_carrinho', 'cupons']
    all_ok = True
    for n in needed:
        ok = n in tables
        if not ok:
            all_ok = False
        print(('OK' if ok else 'FALTANDO') + ': ' + n)

    c = db.session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='restaurantes' AND column_name='pedido_minimo_centavos'"
    )).fetchone()
    ok = c is not None
    if not ok:
        all_ok = False
    print(('OK' if ok else 'FALTANDO') + ': restaurantes.pedido_minimo_centavos')

    print('')
    print('RESULTADO: ' + ('TUDO CERTO NO SUPABASE!' if all_ok else 'EXISTEM PROBLEMAS!'))
