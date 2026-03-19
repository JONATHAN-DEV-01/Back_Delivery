import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailService:
    @staticmethod
    def send_otp(to_email: str, nome: str, codigo: str = None, link: str = None) -> bool:
        """Envia o código OTP e/ou link de acesso via e-mail utilizando SendGrid."""
        sg_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('SENDGRID_FROM_EMAIL')

        if not sg_api_key or not from_email:
            print("AVISO: Chaves do SendGrid não configuradas.")
            return False

        content = f"Aqui está o seu código de verificação: {codigo}" if codigo else ""
        if link:
            content += f"<br><br><a href='{link}' style='display: inline-block; padding: 10px 20px; background-color: #E74C3C; color: white; text-decoration: none; border-radius: 5px;'>Acessar Agora</a>"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2>Olá, {nome}!</h2>
            <p>Clique no botão abaixo ou use o código para acessar sua conta:</p>
            {f'<h1 style="letter-spacing: 5px; color: #E74C3C;">{codigo}</h1>' if codigo else ''}
            {f"<p><a href='{link}' style='color: #E74C3C;'>Clique aqui para acessar via link</a></p>" if link else ''}
            <p>⏱️ Este acesso é válido por <strong>exatos 15 minutos</strong>.</p>
            <p style="font-size: 12px; color: #777;">Se você não solicitou isso, por favor, ignore este e-mail.</p>
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
