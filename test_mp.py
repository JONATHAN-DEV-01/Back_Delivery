import requests

MP_ACCESS_TOKEN = "TEST-94413540544618-042615-43a35b126f756bdddb3dec2355edf6db-1740413380"
MP_URL = "https://api.mercadopago.com/v1"
HEADERS = {
    "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def test_mp_connection():
    print("Testando conexão com a API do Mercado Pago...")
    try:
        res = requests.get(f"{MP_URL}/payment_methods", headers=HEADERS)
        if res.status_code == 200:
            print("Conexão bem-sucedida!")
            methods = res.json()
            pix_found = any(m.get('id') == 'pix' for m in methods)
            print(f"Métodos de pagamento carregados: {len(methods)}")
            print(f"Pix suportado: {'Sim' if pix_found else 'Não'}")
        else:
            print(f"Erro ao conectar (Status Code {res.status_code}):")
            print(res.json())
    except Exception as e:
        print(f"Falha na requisição: {e}")

if __name__ == "__main__":
    test_mp_connection()
