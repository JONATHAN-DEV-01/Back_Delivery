import psycopg2
import os

try:
    # Connect using localhost because we are outside the Docker network
    conn = psycopg2.connect('postgresql://admin:admin@localhost:5432/delivery_db')
    cur = conn.cursor()
    
    print("Adding structured address columns to 'restaurantes' table...")
    
    alter_queries = [
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS logradouro VARCHAR(254);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS bairro VARCHAR(100);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS cidade VARCHAR(100);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS estado VARCHAR(2);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS numero VARCHAR(10);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS cep VARCHAR(10);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS ponto_referencia VARCHAR(100);",
        "ALTER TABLE restaurantes ADD COLUMN IF NOT EXISTS sem_numero BOOLEAN DEFAULT FALSE;"
    ]
    
    for query in alter_queries:
        try:
            cur.execute(query)
            print(f"Executed: {query}")
        except Exception as e:
            print(f"Skipped/Error on query '{query}': {str(e)}")
            conn.rollback() # Rollback to continue with other queries
            cur = conn.cursor()
            continue

    conn.commit()
    print("Migration completed successfully!")
    
    cur.close()
    conn.close()
except Exception as e:
    print("Fatal Error:", str(e))
