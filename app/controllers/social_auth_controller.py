"""
Controller: Social Auth
Implementa o fluxo completo de Login Social (Google e Facebook) para o app Zupps.

Fluxo orquestrado:
  1. Frontend recebe o Access Token do SDK do provedor.
  2. Frontend envia o token para POST /auth/google/callback ou /auth/facebook/callback.
  3. Backend valida o token Server-to-Server (RF-04) via SocialAuthService.
  4. Se e-mail já existir → cria vínculo (identidades_sociais) e retorna JWT. (RF-06)
  5. Se e-mail NÃO existir → retorna HTTP 202 + token_provisorio + require_phone=True. (RF-08)
  6. Frontend abre Modal de Coleta de Telefone → dispara OTP → POST /auth/social/complete-registration.
  7. Backend persiste o usuário, cria o vínculo e retorna JWT final.

RNF – TLS 1.2+:
  Toda comunicação Flask → Provedores é feita via HTTPS (ver social_auth_service.py).
  Em produção, configure o Nginx/Load Balancer como terminador TLS. O Flask em si
  nunca deve ser exposto diretamente sem TLS na frente.

RNF – Latência < 1.2 s:
  - A validação do token (chamada externa) tem timeout de 5 s configurável.
  - As queries ao banco usam índices únicos (email, provedor+id_provedor) = O(log n).
  - O processamento da foto_url é salvo diretamente como string (sem download
    síncrono nesta rota). O download/resize pode ser feito via job assíncrono (Celery)
    em iterações futuras (RF-07 completo).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from flask import Blueprint, jsonify, request, current_app

from app.extensions import db
from app.models.identidade_social import IdentidadeSocial
from app.models.otp_code import OTPCode
from app.models.usuario import Usuario
from app.services.social_auth_service import SocialAuthService
from app.utils.validators import sanitize_phone, validate_phone

logger = logging.getLogger(__name__)

social_auth_bp = Blueprint("social_auth", __name__)

# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

_JWT_SECRET: str = os.getenv("JWT_SECRET", "zupps-secret-key")
_PROVISIONAL_TOKEN_SECRET: str = os.getenv("PROVISIONAL_TOKEN_SECRET", "zupps-provisional-secret")
_PROVISIONAL_TOKEN_TTL_MINUTES: int = int(os.getenv("PROVISIONAL_TOKEN_TTL", "15"))


def _generate_jwt(usuario: Usuario) -> str:
    """
    Gera o JWT de sessão definitivo para o usuário.

    RNF – Persistência de sessão: TTL de 7 dias alinhado com o auth_controller.py.
    """
    payload = {
        "user_id": str(usuario.id),
        "perfil": usuario.perfil,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _generate_provisional_token(dados_sociais: dict) -> str:
    """
    Gera um Token Provisório (JWT de curta duração) para o fluxo de
    interceptação de novo usuário (RF-08).

    O payload carrega os dados já validados do provedor para evitar
    nova chamada Server-to-Server na rota de conclusão.

    TTL configurável via PROVISIONAL_TOKEN_TTL (default: 15 min).
    """
    payload = {
        "type": "PROVISIONAL_SOCIAL",
        "provedor": dados_sociais["provedor"],
        "id_provedor": dados_sociais["id_provedor"],
        "email": dados_sociais["email"],
        "nome_completo": dados_sociais.get("nome_completo", ""),
        "foto_url": dados_sociais.get("foto_url", ""),
        "exp": datetime.utcnow() + timedelta(minutes=_PROVISIONAL_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, _PROVISIONAL_TOKEN_SECRET, algorithm="HS256")


def _decode_provisional_token(token: str) -> Optional[dict]:
    """
    Decodifica e valida o Token Provisório.
    Retorna o payload ou None em caso de token inválido/expirado.
    """
    try:
        payload = jwt.decode(token, _PROVISIONAL_TOKEN_SECRET, algorithms=["HS256"])
        if payload.get("type") != "PROVISIONAL_SOCIAL":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _handle_social_callback(dados_sociais: dict):
    """
    Lógica central de callback compartilhada entre Google e Facebook.

    RF-06: Vínculo de conta existente.
    RF-08: Interceptação de novo usuário.
    """
    email: str = dados_sociais["email"]
    id_provedor: str = dados_sociais["id_provedor"]
    provedor: str = dados_sociais["provedor"]

    # -------------------------------------------------------------------
    # 1. Verifica se já existe um vínculo social direto para este provedor
    # -------------------------------------------------------------------
    vinculo_existente: Optional[IdentidadeSocial] = IdentidadeSocial.query.filter_by(
        provedor=provedor, id_provedor=id_provedor
    ).first()

    if vinculo_existente:
        # Login direto via provedor social já vinculado
        usuario = Usuario.query.get(vinculo_existente.usuario_id)
        if not usuario:
            # Inconsistência de dados – orphan record
            db.session.delete(vinculo_existente)
            db.session.commit()
            return jsonify({"error": "Conta social inválida. Tente novamente."}), 400

        # RF-06: Atualiza ultimo_login
        usuario.etapa_registro = "COMPLETED"
        db.session.commit()

        logger.info("[SocialAuth] Login direto por vínculo existente: user_id=%s", usuario.id)
        return jsonify({
            "message": "Login social realizado com sucesso.",
            "token": _generate_jwt(usuario),
            "user": usuario.to_dict(),
        }), 200

    # -------------------------------------------------------------------
    # 2. Verifica se o e-mail já existe na tabela usuarios (qualquer etapa)
    # -------------------------------------------------------------------
    usuario_existente: Optional[Usuario] = Usuario.query.filter_by(email=email).first()

    if usuario_existente:
        # RF-06: E-mail já cadastrado em qualquer etapa — vincula e faz login
        # Verifica se o vínculo para este provedor já existe antes de criar
        vinculo_ja_existe = IdentidadeSocial.query.filter_by(
            provedor=provedor, id_provedor=id_provedor
        ).first()

        if not vinculo_ja_existe:
            novo_vinculo = IdentidadeSocial(
                usuario_id=usuario_existente.id,
                provedor=provedor,
                id_provedor=id_provedor,
            )
            db.session.add(novo_vinculo)

        # Atualiza foto se o usuário ainda não tiver uma
        if not usuario_existente.foto_url and dados_sociais.get("foto_url"):
            usuario_existente.foto_url = dados_sociais["foto_url"]

        # Garante que a conta fica marcada como completa ao vincular social
        if usuario_existente.etapa_registro != "COMPLETED":
            usuario_existente.etapa_registro = "COMPLETED"

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("[SocialAuth] Erro ao vincular conta existente: %s", exc)
            return jsonify({"error": "Erro ao vincular conta. Tente novamente."}), 500

        logger.info(
            "[SocialAuth] Login via social para usuário existente: user_id=%s, provedor=%s",
            usuario_existente.id, provedor,
        )
        return jsonify({
            "message": "Conta vinculada e login realizado com sucesso.",
            "token": _generate_jwt(usuario_existente),
            "user": usuario_existente.to_dict(),
        }), 200

    # -------------------------------------------------------------------
    # 3. RF-08: Novo usuário – NÃO inserir na tabela (falharia no NOT NULL
    #    do telefone). Retornar 202 + token_provisorio + require_phone=True.
    # -------------------------------------------------------------------
    token_provisorio = _generate_provisional_token(dados_sociais)

    logger.info(
        "[SocialAuth] Novo usuário via social. Interceptando para coleta de telefone. email=%s",
        email,
    )
    return jsonify({
        "message": "Cadastro social iniciado. Precisamos do seu telefone para continuar.",
        "require_phone": True,
        "token_provisorio": token_provisorio,
        "nome_completo": dados_sociais.get("nome_completo", ""),
        "email": email,
    }), 202


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@social_auth_bp.route("/auth/google/callback", methods=["POST"])
def google_callback():
    """
    RF-04 + RF-06/RF-08: Callback de autenticação Google.

    Recebe:
        Body JSON: { "access_token": "<Google Access Token>" }

    Retorna:
        200 → Login bem-sucedido    { token, user }
        202 → Novo usuário          { require_phone, token_provisorio, nome_completo, email }
        400 → Token ausente/inválido
        502 → Falha de comunicação com a Graph API
    """
    # RNF – Latência: parse JSON nativo do Flask é O(n) no tamanho do body.
    data: Optional[dict] = request.get_json(silent=True)
    if not data or "access_token" not in data:
        return jsonify({"error": "access_token não informado."}), 400

    access_token: str = data["access_token"].strip()

    # RF-04: Validação Server-to-Server
    dados_sociais = SocialAuthService.validate_google_token(access_token)
    if not dados_sociais:
        return jsonify({"error": "Token Google inválido ou expirado."}), 400

    if not dados_sociais.get("email"):
        return jsonify({"error": "O token Google não retornou um e-mail verificado."}), 422

    return _handle_social_callback(dados_sociais)


@social_auth_bp.route("/auth/facebook/callback", methods=["POST"])
def facebook_callback():
    """
    RF-04 + RF-06/RF-08: Callback de autenticação Facebook.

    Recebe:
        Body JSON: { "access_token": "<Facebook User Access Token>" }

    Retorna:
        200 → Login bem-sucedido    { token, user }
        202 → Novo usuário          { require_phone, token_provisorio, nome_completo, email }
        400 → Token ausente/inválido
        422 → Facebook não retornou e-mail (permissão negada pelo usuário)
        502 → Falha de comunicação com a Graph API
    """
    data: Optional[dict] = request.get_json(silent=True)
    if not data or "access_token" not in data:
        return jsonify({"error": "access_token não informado."}), 400

    access_token: str = data["access_token"].strip()

    # RF-04: Validação Server-to-Server
    dados_sociais = SocialAuthService.validate_facebook_token(access_token)
    if not dados_sociais:
        return jsonify({
            "error": (
                "Token Facebook inválido ou o usuário não concedeu permissão de e-mail. "
                "Verifique as permissões do app."
            )
        }), 400

    return _handle_social_callback(dados_sociais)


@social_auth_bp.route("/auth/social/complete-registration", methods=["POST"])
def complete_social_registration():
    """
    Rota de conclusão de cadastro social.

    Chamada após o usuário fornecer o telefone (e confirmar via OTP pelo fluxo existente).

    Recebe:
        Body JSON:
        {
            "token_provisorio": "<string>",
            "telefone": "<11 dígitos, com ou sem máscara>"
        }

    Retorna:
        201 → Usuário criado        { token, user }
        400 → Dados inválidos
        401 → Token provisório expirado/inválido
        409 → Telefone ou e-mail já cadastrado

    Orquestração:
        1. Decodifica e valida o token_provisorio.
        2. Higieniza e valida o telefone (11 dígitos, RF-08).
        3. Verifica duplicidade de e-mail e telefone.
        4. Persiste Usuario (etapa_registro='COMPLETED').
        5. RF-07: Salva foto_url diretamente (download assíncrono em iteração futura).
        6. Cria registro em identidades_sociais.
        7. Retorna JWT definitivo.

    RNF – Latência: todas as operações são síncronas em uma única transação de banco;
    não há chamada externa nesta rota (o token_provisorio carrega os dados já validados).
    """
    data: Optional[dict] = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Body JSON obrigatório."}), 400

    token_provisorio: str = data.get("token_provisorio", "").strip()
    telefone_raw: str = data.get("telefone", "").strip()

    # ------------------------------------------------------------------
    # 1. Validar token provisório
    # ------------------------------------------------------------------
    if not token_provisorio:
        return jsonify({"error": "token_provisorio é obrigatório."}), 400

    payload = _decode_provisional_token(token_provisorio)
    if payload is None:
        return jsonify({
            "error": "Token provisório inválido ou expirado. Reinicie o login social."
        }), 401

    # ------------------------------------------------------------------
    # 2. Validar telefone (obrigatório – NOT NULL na tabela usuarios)
    # ------------------------------------------------------------------
    if not telefone_raw:
        return jsonify({"error": "O campo telefone é obrigatório."}), 400

    if not validate_phone(telefone_raw):
        return jsonify({
            "error": "Telefone inválido. Informe DDD + número com 10 ou 11 dígitos, sem +55."
        }), 400

    telefone_clean: str = sanitize_phone(telefone_raw)  # somente dígitos

    # ------------------------------------------------------------------
    # 3. Verificar duplicidades
    # ------------------------------------------------------------------
    email: str = payload["email"]
    provedor: str = payload["provedor"]
    id_provedor: str = payload["id_provedor"]
    nome_completo: str = payload.get("nome_completo", "")
    foto_url: str = payload.get("foto_url", "")

    # ------------------------------------------------------------------
    # 3a. Race condition: o e-mail pode ter sido cadastrado enquanto o
    #     token provisório estava ativo (ou o usuário já tinha conta via OTP).
    #     Neste caso fazemos login/vinculação em vez de retornar 409.
    # ------------------------------------------------------------------
    usuario_existente: Optional[Usuario] = Usuario.query.filter_by(email=email).first()

    if usuario_existente:
        # Verifica se o vínculo social para este provedor já existe
        vinculo_existente = IdentidadeSocial.query.filter_by(
            provedor=provedor, id_provedor=id_provedor
        ).first()

        if not vinculo_existente:
            novo_vinculo = IdentidadeSocial(
                usuario_id=usuario_existente.id,
                provedor=provedor,
                id_provedor=id_provedor,
            )
            db.session.add(novo_vinculo)

        if not usuario_existente.foto_url and foto_url:
            usuario_existente.foto_url = foto_url

        if usuario_existente.etapa_registro != "COMPLETED":
            usuario_existente.etapa_registro = "COMPLETED"

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("[SocialAuth] Erro ao vincular conta existente em complete-registration: %s", exc)
            return jsonify({"error": "Erro ao vincular conta. Tente novamente."}), 500

        logger.info(
            "[SocialAuth] complete-registration: conta existente vinculada. user_id=%s",
            usuario_existente.id,
        )
        return jsonify({
            "message": "Conta vinculada e login realizado com sucesso!",
            "token": _generate_jwt(usuario_existente),
            "user": usuario_existente.to_dict(),
        }), 200

    if Usuario.query.filter_by(telefone=telefone_clean).first():
        return jsonify({"error": "Este telefone já está cadastrado."}), 409

    if IdentidadeSocial.query.filter_by(
        provedor=provedor, id_provedor=id_provedor
    ).first():
        return jsonify({
            "error": "Esta conta social já está vinculada a outro usuário."
        }), 409

    # ------------------------------------------------------------------
    # 4 + 5. Persistir Usuario
    # RF-07: foto_url salva como referência direta (URL do provedor).
    # Para resize/otimização, um worker Celery pode processar de forma assíncrona.
    # ------------------------------------------------------------------
    novo_usuario = Usuario(
        email=email,
        telefone=telefone_clean,
        nome=nome_completo.split(" ")[0] if nome_completo else None,
        sobrenome=" ".join(nome_completo.split(" ")[1:]) if nome_completo and " " in nome_completo else None,
        foto_url=foto_url if foto_url else None,
        etapa_registro="COMPLETED",
        perfil="CLIENTE",
    )
    db.session.add(novo_usuario)
    db.session.flush()  # Gera o UUID antes do commit para usar na FK

    # ------------------------------------------------------------------
    # 6. Criar vínculo em identidades_sociais
    # ------------------------------------------------------------------
    novo_vinculo = IdentidadeSocial(
        usuario_id=novo_usuario.id,
        provedor=provedor,
        id_provedor=id_provedor,
    )
    db.session.add(novo_vinculo)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("[SocialAuth] Erro ao persistir novo usuário social: %s", exc)
        return jsonify({"error": "Erro interno ao finalizar cadastro. Tente novamente."}), 500

    logger.info(
        "[SocialAuth] Novo usuário criado via social. user_id=%s, provedor=%s",
        novo_usuario.id, provedor,
    )

    # 7. Retornar JWT definitivo
    return jsonify({
        "message": "Cadastro social finalizado com sucesso!",
        "token": _generate_jwt(novo_usuario),
        "user": novo_usuario.to_dict(),
    }), 201
