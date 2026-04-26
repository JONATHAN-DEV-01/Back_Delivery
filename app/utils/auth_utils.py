import os
import jwt
from functools import wraps
from flask import request, jsonify, g


def require_auth(f):
    """
    Decorator que protege rotas com autenticação JWT de usuário.
    Extrai o user_id do token e o disponibiliza em flask.g.usuario_id.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token de autenticação não informado.'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET', 'zupps-secret-key'),
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado. Faça login novamente.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido.'}), 401

        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({'error': 'Token não contém identidade de usuário.'}), 401

        g.usuario_id = user_id
        return f(*args, **kwargs)

    return decorated
