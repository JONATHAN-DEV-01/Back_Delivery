import os
from flask import Flask
from flask_cors import CORS
from app.extensions import db, migrate


def create_app():
    app = Flask(__name__)

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Em produção lemos as origens permitidas da variável de ambiente
    # ALLOWED_ORIGINS (separadas por vírgula). Em desenvolvimento, libera tudo.
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    allowed_origins = (
        [o.strip() for o in raw_origins.split(",") if o.strip()]
        if raw_origins
        else "*"
    )
    CORS(app, origins=allowed_origins, supports_credentials=True)

    # ── Banco de Dados ────────────────────────────────────────────────────────
    # Render/Supabase entregam DATABASE_URL com prefixo "postgres://"
    # mas o SQLAlchemy >= 1.4 exige "postgresql://".
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:admin@db:5432/delivery_db",
    )
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ── Extensões ─────────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.controllers.usuario_controller import users_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.restaurante_controller import restaurante_bp
    from app.controllers.produto_controller import produto_bp
    from app.controllers.social_auth_controller import social_auth_bp
    from app.controllers.buscar_controller import busca_bp
    from app.controllers.categoria_controller import categoria_bp
    from app.controllers.carrinho_controller import carrinho_bp
    from app.controllers.pedido_controller import pedido_bp
    from app.controllers.Intergração_Pagamento import pagamento_bp
    from app.controllers.dashboard_controller import dashboard_bp
    from app.controllers.estoque_controller import estoque_bp  # Módulo 10 — Gestão de Estoque

    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurante_bp)
    app.register_blueprint(produto_bp)
    app.register_blueprint(social_auth_bp)
    app.register_blueprint(busca_bp)
    app.register_blueprint(categoria_bp)
    app.register_blueprint(carrinho_bp)
    app.register_blueprint(pedido_bp)
    app.register_blueprint(pagamento_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(estoque_bp)   # Módulo 10 — Gestão de Estoque

    # ── Modelos (necessário para Alembic/Flask-Migrate detectar) ──────────────
    from app.models import identidade_social  # noqa: F401
    from app.models import loja_categoria     # noqa: F401
    from app.models import carrinho           # noqa: F401
    from app.models import cupom              # noqa: F401
    from app.models import pedido             # noqa: F401
    from app.models import pagamento          # noqa: F401
    from app.models import cartoes_clientes   # noqa: F401

    # ── Rota de arquivos locais (uploads legados) ─────────────────────────────
    from flask import send_from_directory

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(
            os.path.join(app.root_path, "../uploads"), filename
        )

    return app
