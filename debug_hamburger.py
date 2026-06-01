import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, r"c:\Users\Gamer\Desktop\Back_delivery")

from app import create_app
from app.models.produto import Produto

app = create_app()

with app.app_context():
    produtos = Produto.query.all()
    for p in produtos:
        if p.nome.lower() == 'hamburger':
            print(f"Produto: {p.nome}")
            print(f"Ficha tecnica size: {len(p.ficha_tecnica)}")
            for ficha in p.ficha_tecnica:
                print(f"  Ingrediente ID: {ficha.ingrediente_id}, Nome: {ficha.ingrediente.nome}, Qtd Atual: {ficha.ingrediente.quantidade_atual}, Necessaria: {ficha.quantidade_necessaria}")
            print(f"Quantidade disponivel calculada: {p.quantidade_disponivel}")
