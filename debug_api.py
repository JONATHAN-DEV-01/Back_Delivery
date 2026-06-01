import psycopg2
from psycopg2.extras import DictCursor
import requests
import json
import jwt

DATABASE_URL = "postgresql://postgres:3CVF5nG96O2GeKjZ@db.tfqruazyqcldldlxbyzm.supabase.co:5432/postgres"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=DictCursor)
    
    cur.execute("SELECT id, restaurante_id FROM produtos WHERE nome ILIKE '%Hamburger%'")
    produto = cur.fetchone()
    if not produto:
        print("Produto não encontrado")
        return
        
    restaurante_id = str(produto['restaurante_id'])
    print(f"Restaurante ID: {restaurante_id}")
    
    # Generate token
    token = jwt.encode({'restaurante_id': restaurante_id}, 'zupps-secret-key', algorithm='HS256')
    
    res = requests.get(
        f'https://back-delivery-4aj5.onrender.com/estoque/{restaurante_id}/produtos',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    print("Status:", res.status_code)
    try:
        data = res.json()
        for p in data:
            if p.get('nome') == 'Hamburger':
                print("Hamburger data from API:")
                print(json.dumps(p, indent=2))
    except Exception as e:
        print("Error parsing json:", e)
        print(res.text)

if __name__ == '__main__':
    main()
