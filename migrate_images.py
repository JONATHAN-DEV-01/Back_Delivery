import os
import requests
import mimetypes
from dotenv import load_dotenv

load_dotenv()

# Inicializamos a aplicação para poder trocar registros no banco de dados local
from app import create_app
from app.extensions import db
from app.models.restaurante import Restaurante
from app.models.produto import Produto

app = create_app()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "Imagens"


def migrar_arquivo(local_path, supabase_folder):
    """Lê um arquivo local e envia para o bucket do Supabase"""
    # Formata caminhos do Windows
    local_path = local_path.replace('\\', '/')
    
    if not os.path.exists(local_path):
        print(f"Arquivo ignorado pois não existe no HD: {local_path}")
        return None
        
    filename = os.path.basename(local_path)
    path_in_bucket = f"{supabase_folder}/{filename}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{path_in_bucket}"
    
    mime_type, _ = mimetypes.guess_type(local_path)
    
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": mime_type if mime_type else "application/octet-stream"
    }

    try:
        with open(local_path, 'rb') as f:
            response = requests.post(url, headers=headers, data=f)
            
        if response.status_code in [200, 201] or "Duplicate" in response.text:
            # Retorna URL pública
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path_in_bucket}"
            return public_url
        else:
            print(f"Falha Supabase ({response.status_code}) ao upar {local_path}: {response.text}")
            return None
    except Exception as e:
        print(f"Erro ao migrar {local_path}: {e}")
        return None

if __name__ == "__main__":
    with app.app_context():
        print("Iniciando migração de imagens locais para o Supabase Storage...")
        
        atualizados = 0

        # 1. Migrar Imagens de Restaurantes (Logotipo e Capa)
        restaurantes = Restaurante.query.all()
        for rest in restaurantes:
            if rest.logotipo and 'supabase.co' not in rest.logotipo:
                novo_url = migrar_arquivo(rest.logotipo, 'logos')
                if novo_url:
                    rest.logotipo = novo_url
                    atualizados += 1

            if rest.capa and 'supabase.co' not in rest.capa:
                novo_url = migrar_arquivo(rest.capa, 'logos')
                if novo_url:
                    rest.capa = novo_url
                    atualizados += 1
                    
        # 2. Migrar Imagens de Produtos
        produtos = Produto.query.all()
        for prod in produtos:
            if prod.imagem and 'supabase.co' not in prod.imagem:
                novo_url = migrar_arquivo(prod.imagem, 'produtos')
                if novo_url:
                     prod.imagem = novo_url
                     atualizados += 1

        db.session.commit()
        print(f"Migração finalizada! {atualizados} links atualizados com sucesso no banco principal.")
