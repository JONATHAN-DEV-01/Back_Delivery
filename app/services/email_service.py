import os
import pytz
from datetime import datetime
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
            <p>Este acesso é válido por <strong>exatos 15 minutos</strong>.</p>
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

    @staticmethod
    def send_nota_fiscal(to_email: str, dados: dict) -> bool:
        """
        Envia a nota fiscal em HTML para o cliente após pagamento aprovado.

        dados deve conter:
            numero_pedido, data_emissao (datetime ou str), forma_pagamento,
            tipo_entrega, status_pagamento,
            cliente: {nome, sobrenome, cpf, email},
            endereco_entrega: {logradouro, numero, bairro, cidade, estado, complemento},
            restaurante: {nome_fantasia, razao_social, cnpj, logradouro, numero, bairro, cidade, estado, cep, telefone, email},
            itens: [{nome, quantidade, preco_unitario_centavos, adicionais: [{nome, preco_centavos}]}],
            subtotal_centavos, taxa_entrega_centavos, taxa_moto_flash_centavos,
            desconto_centavos, total_centavos
        """
        sg_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('SENDGRID_FROM_EMAIL')

        if not sg_api_key or not from_email:
            print("AVISO: Chaves do SendGrid não configuradas — nota fiscal não enviada.")
            return False

        def fmt_reais(centavos: int) -> str:
            return f"R$ {centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def mask_cpf(cpf: str) -> str:
            c = (cpf or "").replace(".", "").replace("-", "").strip()
            if len(c) == 11:
                return f"***.{c[3:6]}.{c[6:9]}-**"
            return cpf or "Não informado"

        def fmt_cnpj(cnpj: str) -> str:
            c = (cnpj or "").replace(".", "").replace("/", "").replace("-", "").strip()
            if len(c) == 14:
                return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
            return cnpj or ""

        # Formatar data
        data_emissao = dados.get("data_emissao")
        if isinstance(data_emissao, datetime):
            tz_br = pytz.timezone("America/Sao_Paulo")
            if data_emissao.tzinfo is None:
                data_emissao = pytz.utc.localize(data_emissao).astimezone(tz_br)
            data_str = data_emissao.strftime("%d/%m/%Y %H:%M")
        else:
            data_str = str(data_emissao or "")

        numero_pedido = str(dados.get("numero_pedido", ""))
        nf_numero = "NF-" + numero_pedido[-8:].upper() if numero_pedido else "NF-00000000"

        cliente = dados.get("cliente", {})
        endereco = dados.get("endereco_entrega", {})
        rest = dados.get("restaurante", {})
        itens = dados.get("itens", [])

        subtotal = dados.get("subtotal_centavos", 0)
        frete = dados.get("taxa_entrega_centavos", 0)
        flash = dados.get("taxa_moto_flash_centavos", 0)
        desconto = dados.get("desconto_centavos", 0)
        total = dados.get("total_centavos", 0)

        tipo_map = {"MOTO": "Moto", "BICICLETA": "Bicicleta", "MOTO_FLASH": "Moto Flash (Expresso)"}
        pagto_map = {"CREDIT_CARD": "Cartao de Credito (App)", "PIX": "PIX", "CASH": "Dinheiro", "CARD_MACHINE": "Maquininha"}
        tipo_label = tipo_map.get(dados.get("tipo_entrega", "MOTO"), dados.get("tipo_entrega", "Moto"))
        pagto_label = pagto_map.get(dados.get("forma_pagamento", ""), dados.get("forma_pagamento", ""))

        # Montar linhas de itens
        itens_rows = ""
        for item in itens:
            adicionais_str = ""
            for ad in item.get("adicionais", []):
                ad_preco = ad.get("preco_unitario_centavos") or ad.get("preco_centavos", 0)
                adicionais_str += f"<div style='color:#888;font-size:11px;padding-left:8px;'>+ {ad.get('nome','')} ({fmt_reais(ad_preco)})</div>"
            qtd = item.get("quantidade", 1)
            unit = item.get("preco_unitario_centavos", 0)
            # preco unitario inclui adicionais
            ad_total = sum((a.get("preco_unitario_centavos") or a.get("preco_centavos", 0)) for a in item.get("adicionais", []))
            item_total = (unit + ad_total) * qtd
            itens_rows += f"""
            <tr>
                <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;">
                    <div style="font-weight:600;color:#1a1a1a;">{item.get('nome','')}</div>
                    {adicionais_str}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;text-align:center;color:#555;">{qtd}x</td>
                <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;text-align:right;color:#555;">{fmt_reais(unit + ad_total)}</td>
                <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:600;color:#1a1a1a;">{fmt_reais(item_total)}</td>
            </tr>"""

        # Linhas de totais
        totais_rows = f"""
        <tr>
            <td colspan="3" style="padding:6px 8px;text-align:right;color:#666;">Subtotal</td>
            <td style="padding:6px 8px;text-align:right;color:#333;">{fmt_reais(subtotal)}</td>
        </tr>
        <tr>
            <td colspan="3" style="padding:6px 8px;text-align:right;color:#666;">Frete</td>
            <td style="padding:6px 8px;text-align:right;color:#333;">{"Gratis" if frete == 0 else fmt_reais(frete)}</td>
        </tr>"""

        if flash and flash > 0:
            totais_rows += f"""
        <tr>
            <td colspan="3" style="padding:6px 8px;text-align:right;color:#d97706;">Taxa Moto Flash</td>
            <td style="padding:6px 8px;text-align:right;color:#d97706;">{fmt_reais(flash)}</td>
        </tr>"""

        if desconto and desconto > 0:
            totais_rows += f"""
        <tr>
            <td colspan="3" style="padding:6px 8px;text-align:right;color:#16a34a;">Desconto</td>
            <td style="padding:6px 8px;text-align:right;color:#16a34a;">- {fmt_reais(desconto)}</td>
        </tr>"""

        totais_rows += f"""
        <tr style="background:#fff8f6;">
            <td colspan="3" style="padding:10px 8px;text-align:right;font-size:15px;font-weight:800;color:#1a1a1a;border-top:2px solid #e5e7eb;">TOTAL</td>
            <td style="padding:10px 8px;text-align:right;font-size:15px;font-weight:800;color:#e74c3c;border-top:2px solid #e5e7eb;">{fmt_reais(total)}</td>
        </tr>"""

        end_entrega_str = ", ".join(filter(None, [
            endereco.get("logradouro"), endereco.get("numero"),
            endereco.get("bairro"),
            f"{endereco.get('cidade','')}-{endereco.get('estado','')}" if endereco.get("cidade") else None,
            endereco.get("complemento")
        ]))

        rest_end_str = ", ".join(filter(None, [
            rest.get("logradouro"), rest.get("numero"),
            rest.get("bairro"),
            f"{rest.get('cidade','')}-{rest.get('estado','')}" if rest.get("cidade") else None,
            rest.get("cep")
        ]))

        html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Nota Fiscal - Zupps Eats</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0;">
  <tr><td align="center">
    <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

      <!-- HEADER -->
      <tr>
        <td style="background:linear-gradient(135deg,#e74c3c 0%,#c0392b 100%);padding:32px 36px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="font-size:26px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;">⚡ Zupps Eats</div>
                <div style="font-size:13px;color:rgba(255,255,255,0.8);margin-top:4px;">Nota Fiscal Eletrônica (Comprovante de Pedido)</div>
              </td>
              <td align="right">
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:10px 16px;text-align:center;">
                  <div style="font-size:11px;color:rgba(255,255,255,0.7);text-transform:uppercase;letter-spacing:1px;">Nº Documento</div>
                  <div style="font-size:18px;font-weight:800;color:#ffffff;margin-top:2px;">{nf_numero}</div>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- STATUS APROVADO -->
      <tr>
        <td style="background:#f0fdf4;border-bottom:1px solid #dcfce7;padding:12px 36px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <span style="display:inline-block;background:#16a34a;color:#fff;font-size:11px;font-weight:700;padding:4px 12px;border-radius:100px;text-transform:uppercase;letter-spacing:1px;">✓ Pagamento Aprovado</span>
              </td>
              <td align="right" style="font-size:12px;color:#6b7280;">Emitido em {data_str}</td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- CORPO -->
      <tr><td style="padding:28px 36px;">

        <!-- DADOS EM DUAS COLUNAS -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
          <tr valign="top">
            <!-- DADOS DO CLIENTE -->
            <td width="48%" style="padding-right:16px;">
              <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">Dados do Cliente</div>
              <div style="background:#f9fafb;border-radius:10px;padding:14px;">
                <div style="font-size:13px;font-weight:700;color:#1a1a1a;">{cliente.get('nome','')} {cliente.get('sobrenome','')}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">CPF: {mask_cpf(cliente.get('cpf',''))}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:2px;">{cliente.get('email','')}</div>
              </div>
            </td>
            <!-- EMITENTE (RESTAURANTE) -->
            <td width="52%">
              <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">Estabelecimento Emitente</div>
              <div style="background:#f9fafb;border-radius:10px;padding:14px;">
                <div style="font-size:13px;font-weight:700;color:#1a1a1a;">{rest.get('nome_fantasia','')}</div>
                <div style="font-size:11px;color:#6b7280;margin-top:2px;">{rest.get('razao_social','')}</div>
                <div style="font-size:11px;color:#6b7280;margin-top:2px;">CNPJ: {fmt_cnpj(rest.get('cnpj',''))}</div>
                <div style="font-size:11px;color:#6b7280;margin-top:2px;">{rest_end_str}</div>
                <div style="font-size:11px;color:#6b7280;margin-top:2px;">Tel: {rest.get('telefone','')}</div>
              </div>
            </td>
          </tr>
        </table>

        <!-- ENDEREÇO DE ENTREGA -->
        <div style="margin-bottom:28px;">
          <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">Endereço de Entrega</div>
          <div style="background:#f9fafb;border-radius:10px;padding:14px;font-size:13px;color:#374151;">
            📍 {end_entrega_str if end_entrega_str else 'Endereço não informado'}
          </div>
        </div>

        <!-- ITENS DO PEDIDO -->
        <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">Itens do Pedido</div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #f0f0f0;border-radius:10px;overflow:hidden;margin-bottom:28px;">
          <thead>
            <tr style="background:#f9fafb;">
              <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Produto</th>
              <th style="padding:10px 8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Qtd</th>
              <th style="padding:10px 8px;text-align:right;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Unit.</th>
              <th style="padding:10px 8px;text-align:right;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Total</th>
            </tr>
          </thead>
          <tbody>
            {itens_rows}
            {totais_rows}
          </tbody>
        </table>

        <!-- FORMA DE PAGAMENTO E ENTREGA -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
          <tr>
            <td width="50%" style="padding-right:8px;">
              <div style="background:#f9fafb;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Forma de Pagamento</div>
                <div style="font-size:13px;font-weight:700;color:#1a1a1a;">💳 {pagto_label}</div>
              </div>
            </td>
            <td width="50%" style="padding-left:8px;">
              <div style="background:#f9fafb;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Entrega</div>
                <div style="font-size:13px;font-weight:700;color:#1a1a1a;">🛵 {tipo_label}</div>
              </div>
            </td>
          </tr>
        </table>

      </td></tr>

      <!-- RODAPÉ -->
      <tr>
        <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:20px 36px;text-align:center;">
          <div style="font-size:11px;color:#9ca3af;">
            Este documento é um comprovante de pedido gerado automaticamente pela plataforma Zupps Eats.<br>
            Número do pedido: <strong style="color:#6b7280;">{numero_pedido}</strong> &nbsp;|&nbsp; {nf_numero}<br>
            Em caso de dúvidas, entre em contato com <strong>{rest.get('nome_fantasia','o restaurante')}</strong>: {rest.get('email','')}
          </div>
          <div style="margin-top:12px;font-size:10px;color:#d1d5db;">© {datetime.now().year} Zupps Eats — Todos os direitos reservados</div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=f"Nota Fiscal - Pedido {nf_numero} | Zupps Eats",
            html_content=html_content
        )

        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            print(f"[EmailService] Nota fiscal enviada para {to_email} — status {response.status_code}")
            return response.status_code in [200, 202]
        except Exception as e:
            print(f"[EmailService] Erro ao enviar nota fiscal: {str(e)}")
            return False
