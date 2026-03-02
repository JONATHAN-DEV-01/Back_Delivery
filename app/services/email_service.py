import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailService:
    @staticmethod
    def send_otp(to_email: str, nome: str, codigo: str) -> bool:
        """Envia o código OTP via e-mail utilizando SendGrid."""
        sg_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('SENDGRID_FROM_EMAIL')

        if not sg_api_key or not from_email:
            print("AVISO: Chaves do SendGrid não configuradas.")
            return False

        html_content = f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2>Olá, {nome}!</h2>
            <p>Aqui está o seu código de verificação para acessar o aplicativo:</p>
            <h1 style="letter-spacing: 5px; color: #E74C3C;">{codigo}</h1>
            <p>⏱️ Este código é válido por <strong>exatos 5 minutos</strong>.</p>
            <p style="font-size: 12px; color: #777;">Se você não solicitou este código, por favor, ignore este e-mail.</p>
        </div>
        """

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject='Seu código de acesso ao App',
            html_content=html_content
        )

        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            return response.status_code in [200, 202]
        except Exception as e:
            print(f"Erro ao enviar e-mail via SendGrid: {str(e)}")
            return False
