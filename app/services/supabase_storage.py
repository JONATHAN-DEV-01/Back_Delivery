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
    Retorna a URL pública do arquivo ou None em caso de falha.
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
        "Content-Type": file.content_type if file.content_type else "application/octet-stream",
    }

    # Lê os bytes da imagem
    file_bytes = file.read()
    file.seek(0)  # Retorna o ponteiro caso o arquivo precise ser lido de novo

    response = None
    try:
        response = requests.post(url, headers=headers, data=file_bytes)
        response.raise_for_status()  # Lança erro se não for 200/201

        # Se sucesso, retorna a URL pública pra salvarmos no banco de dados
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{path_in_bucket}"
        return public_url
    except Exception as e:
        print(f"Erro ao enviar arquivo para Supabase: {e}")
        if response is not None:
            print(f"Detalhes do erro Supabase: {response.text}")
        return None


def delete_file_from_supabase(public_url: str) -> bool:
    """
    Remove um arquivo do Supabase Storage dado sua URL pública completa
    (exatamente como está salva no banco de dados).

    Extrai o path relativo dentro do bucket e chama o endpoint DELETE da API REST
    do Supabase. Nunca lança exceção — retorna False em caso de falha.

    Exemplo de URL esperada:
        https://xxx.supabase.co/storage/v1/object/public/Imagens/produtos/abc.jpg
    """
    if not public_url or not SUPABASE_URL or not SUPABASE_KEY:
        return False

    # Extrai o path relativo a partir da URL pública
    marker = f"/public/{BUCKET_NAME}/"
    if marker not in public_url:
        # URL não é do Supabase ou não segue o formato esperado — ignora com segurança
        return False

    path_in_bucket = public_url.split(marker)[-1]
    delete_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{path_in_bucket}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
    }

    try:
        response = requests.delete(delete_url, headers=headers)
        if response.status_code in [200, 204]:
            return True
        print(
            f"Aviso: Falha ao deletar '{path_in_bucket}' do Supabase "
            f"({response.status_code}): {response.text}"
        )
        return False
    except Exception as e:
        print(f"Erro ao deletar arquivo do Supabase: {e}")
        return False
