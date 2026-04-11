import os
import requests
from werkzeug.utils import secure_filename

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "Imagens"

def upload_file_to_supabase(file, folder=""):
    """
    Substitui o salvamento local enviando o arquivo (Werkzeug FileStorage) 
    direto para o Supabase Storage via REST.
    """
    if not file:
        return None
        
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Aviso: Chaves do Supabase não configuradas no ambiente.")
        return None

    filename = secure_filename(file.filename)
    # Define o caminho dentro do bucket (ex: logos/foto.jpg)
    path_in_bucket = f"{folder}/{filename}" if folder else filename

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{path_in_bucket}"
    
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": file.content_type if file.content_type else "application/octet-stream"
    }

    # Lê os bytes da imagem
    file_bytes = file.read()
    file.seek(0) # Retorna o ponteiro caso o arquivo precise ser lido de novo

    try:
        response = requests.post(url, headers=headers, data=file_bytes)
        response.raise_for_status() # Lança erro se não for 200/201
        
        # Se sucesso, retorna a URL pública pra salvarmos no banco de dados
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path_in_bucket}"
        return public_url
    except Exception as e:
        print(f"Erro ao enviar arquivo para Supabase: {e}")
        if response is not None:
             print(f"Detalhes do erro Supabase: {response.text}")
        return None
