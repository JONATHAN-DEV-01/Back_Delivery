import psycopg2
import os

try:
    conn = psycopg2.connect('postgresql://admin:admin@localhost:5432/delivery_db')
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'grupos_adicionais'")
    cols = cur.fetchall()
    print("Columns in grupos_adicionais:", [c[0] for c in cols])
    
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'adicionais'")
    cols_adicionais = cur.fetchall()
    print("Columns in adicionais:", [c[0] for c in cols_adicionais])
    
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", str(e))
