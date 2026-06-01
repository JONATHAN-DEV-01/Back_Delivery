import psycopg2
from psycopg2.extras import DictCursor

DATABASE_URL = "postgresql://postgres:3CVF5nG96O2GeKjZ@db.tfqruazyqcldldlxbyzm.supabase.co:5432/postgres"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=DictCursor)
    
    print("Fetching Hamburger...")
    cur.execute("SELECT id, nome FROM produtos WHERE nome ILIKE '%Hamburger%'")
    produto = cur.fetchone()
    if not produto:
        print("Produto não encontrado")
        return
        
    print(f"Produto: {produto['nome']} (ID: {produto['id']})")
    
    cur.execute('''
        SELECT pi.quantidade_necessaria, i.nome, i.quantidade_atual, i.unidade_medida
        FROM produto_ingredientes pi
        JOIN ingredientes i ON pi.ingrediente_id = i.id
        WHERE pi.produto_id = %s
    ''', (produto['id'],))
    
    fichas = cur.fetchall()
    print(f"Fichas: {len(fichas)}")
    for f in fichas:
        print(f" - {f['nome']}: atual={f['quantidade_atual']} nec={f['quantidade_necessaria']} ({f['unidade_medida']})")

    conn.close()

if __name__ == '__main__':
    main()
