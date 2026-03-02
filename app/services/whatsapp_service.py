import os
from twilio.rest import Client

class WhatsAppService:
    @staticmethod
    def send_otp(telefone: str, nome: str, codigo: str) -> bool:
        """Envia o código OTP via WhatsApp utilizando Twilio."""
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

        if not account_sid or not auth_token or not from_number:
            print("AVISO: Chaves do Twilio não configuradas.")
            return False

        # Garante que o número destino esteja no formato `whatsapp:+55XXXXX...`
        if not telefone.startswith("whatsapp:"):
            # O sistema sanitiza para 10/11 digitos, o Twilio precisa do DDI
            telefone_com_ddi = f"+55{telefone}"
            to_number = f"whatsapp:{telefone_com_ddi}"
        else:
            to_number = telefone

        body_content = f"""Olá, *{nome}*! 🍔

Seu código de acesso é: *{codigo}*

⏱️ Ele é válido por exatos 5 minutos.
⚠️ Nunca compartilhe este código com ninguém."""

        try:
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                from_=from_number,
                body=body_content,
                to=to_number
            )
            return bool(message.sid)
        except Exception as e:
            print(f"Erro ao enviar WhatsApp via Twilio: {str(e)}")
            return False
