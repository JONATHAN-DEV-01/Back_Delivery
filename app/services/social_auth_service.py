"""
Serviço: SocialAuthService
Responsável por validar tokens de provedores OAuth (Google e Facebook) de forma
Server-to-Server, eliminando qualquer dependência de SDK no servidor.

Princípios arquiteturais aplicados:
  - RF-04: Validação backend via Graph APIs oficiais (sem decodificação local de JWT).
  - RNF – TLS 1.2+: Todas as chamadas externas usam HTTPS. A lib `requests`
    respeita o bundle de CAs do sistema operacional; em produção, certifique-se de
    que o contêiner Docker possua o pacote `ca-certificates` atualizado.
  - RNF – Latência < 1.2 s: As chamadas externas possuem timeout de 5 s para
    evitar bloqueio indefinido. Adicione um cache Redis (TTL ~ 60 s) em produção
    para evitar chamadas repetidas ao Google/Meta com o mesmo access_token.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de endpoint (não altere; use variáveis de ambiente para override)
# ---------------------------------------------------------------------------
_GOOGLE_TOKENINFO_URL: str = os.getenv(
    "GOOGLE_TOKENINFO_URL",
    "https://www.googleapis.com/oauth2/v3/tokeninfo",
)
_FACEBOOK_ME_URL: str = os.getenv(
    "FACEBOOK_ME_URL",
    "https://graph.facebook.com/me",
)
_REQUEST_TIMEOUT: int = int(os.getenv("SOCIAL_REQUEST_TIMEOUT", "5"))  # segundos


class SocialAuthService:
    """Métodos estáticos de validação Server-to-Server para cada provedor."""

    # ------------------------------------------------------------------
    # Google
    # ------------------------------------------------------------------
    @staticmethod
    def validate_google_token(access_token: str) -> Optional[dict]:
        """
        Valida um Google Access Token consultando o endpoint tokeninfo do Google.

        Retorna um dicionário com os campos do usuário em caso de sucesso,
        ou None se o token for inválido / expirado.

        Campos retornados pelo Google (subset relevante):
            sub      – ID único do usuário no Google (usado como id_provedor)
            email    – Endereço de e-mail verificado
            name     – Nome completo
            picture  – URL da foto de perfil

        RNF – TLS 1.2+: a URL https://... garante transporte cifrado.
        """
        try:
            # RNF – Latência: timeout curto evita que uma chamada lenta bloqueie
            # o event loop do Flask por mais de 5 s.
            response = requests.get(
                _GOOGLE_TOKENINFO_URL,
                params={"access_token": access_token},
                timeout=_REQUEST_TIMEOUT,
            )

            if not response.ok:
                logger.warning(
                    "[SocialAuth] Google tokeninfo retornou %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data: dict = response.json()

            # Garante que o token não está expirado
            if data.get("error_description"):
                logger.warning("[SocialAuth] Google token inválido: %s", data)
                return None

            return {
                "id_provedor": data.get("sub"),
                "email": data.get("email", "").lower().strip(),
                "nome_completo": data.get("name", ""),
                "foto_url": data.get("picture", ""),
                "provedor": "GOOGLE",
            }

        except requests.Timeout:
            logger.error("[SocialAuth] Timeout ao validar token Google.")
            return None
        except requests.RequestException as exc:
            logger.error("[SocialAuth] Erro de rede ao validar token Google: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Facebook / Meta
    # ------------------------------------------------------------------
    @staticmethod
    def validate_facebook_token(access_token: str) -> Optional[dict]:
        """
        Valida um Facebook User Access Token consultando a Graph API do Meta.

        O endpoint /me retorna dados do usuário somente para tokens válidos.
        Campos solicitados: id, name, email, picture.

        Observação: o e-mail pode estar ausente se o usuário não concedeu
        permissão ou não possui e-mail cadastrado no Facebook. Nesse caso,
        retornamos None para forçar o fluxo de coleta de e-mail alternativo
        (fora do escopo deste PR, mas tratado com erro 422).

        RNF – TLS 1.2+: URL HTTPS garante transporte cifrado.
        """
        try:
            response = requests.get(
                _FACEBOOK_ME_URL,
                params={
                    "access_token": access_token,
                    "fields": "id,name,email,picture.type(large)",
                },
                timeout=_REQUEST_TIMEOUT,
            )

            if not response.ok:
                logger.warning(
                    "[SocialAuth] Facebook /me retornou %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data: dict = response.json()

            # Facebook retorna {"error": {...}} em tokens inválidos
            if "error" in data:
                logger.warning("[SocialAuth] Facebook token inválido: %s", data["error"])
                return None

            email: str = data.get("email", "").lower().strip()
            if not email:
                logger.warning(
                    "[SocialAuth] Facebook não retornou e-mail para id_provedor=%s",
                    data.get("id"),
                )
                # Retorna None – sem e-mail não é possível vincular/criar usuário
                return None

            foto_url: str = ""
            picture_data = data.get("picture", {})
            if isinstance(picture_data, dict):
                foto_url = picture_data.get("data", {}).get("url", "")

            return {
                "id_provedor": data.get("id"),
                "email": email,
                "nome_completo": data.get("name", ""),
                "foto_url": foto_url,
                "provedor": "FACEBOOK",
            }

        except requests.Timeout:
            logger.error("[SocialAuth] Timeout ao validar token Facebook.")
            return None
        except requests.RequestException as exc:
            logger.error("[SocialAuth] Erro de rede ao validar token Facebook: %s", exc)
            return None
