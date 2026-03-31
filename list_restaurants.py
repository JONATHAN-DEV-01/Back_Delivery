import psycopg2
import os

try:
    # Tentando conectar ao localhost (assumindo que as portas do Docker estão mapeadas)
    conn = psycopg2.connect('postgresql://admin:admin@localhost:5432/delivery_db')
    cur = conn.cursor()
    
    cur.execute("SELECT id, nome_fantasia, ativo, categoria_id FROM restaurantes")
    restaurantes = cur.fetchall()
    
    print(f"Encontrados {len(restaurantes)} restaurantes no banco:")
    for r in restaurantes:
        print(f"ID: {r[0]} | Nome: {r[1]} | Ativo: {r[2]} | Cat ID: {r[3]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print("Erro ao acessar banco:", str(e))
